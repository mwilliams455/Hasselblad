#!/usr/bin/env python3
"""Read-only X2D II 1.3.16.2 CIM/OTA extraction for local native-code audit.

Uses the pinned DevKit CIM reader alongside this file. Filesystem reconstruction
follows its full-OTA v3/v4 format handling, but preserves system AND vendor.
Only regular files are copied; links and devices are recorded, never created.
No firmware executable or update script is run.
"""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import zipfile

import brotli
from dissect.extfs import ExtFS
import cim_reader

EXPECTED = '9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'
MAX_IMAGE = 4 * 1024**3
ROOT = Path(__file__).resolve().parent / 'firmware'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse_ranges(text):
    values = [int(x) for x in text.split(',')]
    if not values or values[0] != len(values) - 1 or values[0] % 2:
        raise ValueError('Malformed OTA range list')
    ranges = list(zip(values[1::2], values[2::2]))
    if any(a < 0 or b <= a or b * 4096 > MAX_IMAGE for a, b in ranges):
        raise ValueError('OTA range exceeds size limit')
    return ranges


def reconstruct(transfer, source, destination):
    lines = transfer.splitlines()
    if len(lines) < 4 or lines[0] not in ('3', '4'):
        raise ValueError('Unsupported OTA transfer format')
    operations, end = [], 0
    for line in lines[4:]:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 2 or fields[0] not in ('new', 'zero', 'erase'):
            raise ValueError('Only full OTA new/zero/erase operations are supported')
        ranges = parse_ranges(fields[1])
        if not ranges:
            continue
        operations.append((fields[0], ranges))
        end = max(end, *(b for _, b in ranges))
    if not end:
        raise ValueError('Empty OTA')
    with destination.open('xb') as output:
        output.truncate(end * 4096)
        for operation, ranges in operations:
            if operation != 'new':
                continue
            for a, b in ranges:
                output.seek(a * 4096)
                remaining = (b - a) * 4096
                while remaining:
                    data = source.read(min(remaining, 1024**2))
                    if not data:
                        raise ValueError('Truncated OTA block data')
                    output.write(data)
                    remaining -= len(data)
    if source.read(1):
        raise ValueError('Unconsumed OTA block data')


def extract_regular(image, destination):
    destination.mkdir()
    records = []
    seen, total = set(), 0
    with image.open('rb') as stream:
        fs = ExtFS(stream)

        def walk(node, prefix='', depth=0):
            nonlocal total
            if depth > 32:
                raise ValueError('Unexpected filesystem depth')
            for child in node.iterdir():
                name = child.filename
                if name in ('.', '..'):
                    continue
                if '/' in name or '\\' in name or not name or '\x00' in name:
                    raise ValueError('Unsafe filesystem name')
                relative = prefix + name
                if relative in seen or len(seen) > 100000:
                    raise ValueError('Duplicate/excessive filesystem paths')
                seen.add(relative)
                target = destination / relative
                if child.filetype == 0o040000:
                    target.mkdir()
                    walk(child, relative + '/', depth + 1)
                elif child.filetype == 0o100000:
                    digest, size = hashlib.sha256(), 0
                    with child.open() as src, target.open('xb') as dest:
                        while chunk := src.read(1024**2):
                            total += len(chunk)
                            size += len(chunk)
                            if total > MAX_IMAGE:
                                raise ValueError('Filesystem expansion limit exceeded')
                            digest.update(chunk)
                            dest.write(chunk)
                    records.append({'path': relative, 'kind': 'file', 'bytes': size,
                                    'sha256': digest.hexdigest()})
                else:
                    entry = {'path': relative, 'kind': 'skipped',
                             'filetype_octal': oct(child.filetype)}
                    if child.filetype == 0o120000:
                        entry['kind'] = 'symlink'
                        entry['target'] = str(child.link)
                    records.append(entry)

        walk(fs.get('/'))
    return records


def main():
    source = ROOT / 'X2DII_100C_v1_3_16_2.cim'
    if sha256(source) != EXPECTED:
        raise ValueError('Official firmware SHA-256 differs from the pinned input')
    out = ROOT / 'extracted'
    out.mkdir(exist_ok=False)
    raw = source.read_bytes()
    public, encrypted, iv, private, items = cim_reader.load_container(raw)
    if not public['size_matches'] or public['product'] != '1800000_PVF':
        raise ValueError('Firmware container size/product mismatch')
    (out / 'container.json').write_text(json.dumps({'public': public, 'private': private,
                                                   'items': items}, indent=2) + '\n')
    candidates = [item for item in items if item['name'] == 'ota.zip']
    if len(candidates) != 1:
        raise ValueError('Expected one OTA ZIP')
    item = candidates[0]
    print('Decrypting OTA component', item['length'], flush=True)
    data = (cim_reader.decrypt_component(raw, item, iv) if encrypted else
            raw[item['offset_in_cim']: item['offset_in_cim'] + item['length']])
    del raw
    ota = out / 'ota.zip'
    ota.write_bytes(data)
    del data
    manifest = {'firmware_sha256': EXPECTED, 'ota_sha256': sha256(ota), 'partitions': {}}
    with zipfile.ZipFile(ota) as archive:
        names = archive.namelist()
        (out / 'ota_members.json').write_text(json.dumps(names, indent=2) + '\n')
        for partition in ('system', 'vendor'):
            transfer_name = partition + '.transfer.list'
            if transfer_name not in names:
                print('No separate OTA partition', partition, flush=True)
                continue
            dat_name = partition + '.new.dat.br'
            if dat_name not in names:
                dat_name = partition + '.new.dat'
            for member in (transfer_name, dat_name):
                if names.count(member) != 1 or archive.getinfo(member).file_size > MAX_IMAGE:
                    raise ValueError('Duplicate or oversized OTA input')
            transfer = archive.read(transfer_name).decode('ascii')
            (out / transfer_name).write_text(transfer)
            print('Expanding', partition, flush=True)
            dat = out / (partition + '.expanded.dat')
            decoder = brotli.Decompressor() if dat_name.endswith('.br') else None
            expanded = 0
            with archive.open(dat_name) as compressed, dat.open('xb') as dest:
                while chunk := compressed.read(65536):
                    block = decoder.process(chunk) if decoder else chunk
                    expanded += len(block)
                    if expanded > MAX_IMAGE:
                        raise ValueError('OTA data expansion limit exceeded')
                    dest.write(block)
            if decoder and not decoder.is_finished():
                raise ValueError('Truncated Brotli stream')
            image = out / (partition + '.img')
            with dat.open('rb') as stream:
                reconstruct(transfer, stream, image)
            dat.unlink()
            print('Reading filesystem', partition, flush=True)
            records = extract_regular(image, out / partition)
            manifest['partitions'][partition] = {
                'image_sha256': sha256(image), 'image_bytes': image.stat().st_size,
                'records': records}
            (out / (partition + '_manifest.json')).write_text(json.dumps(
                manifest['partitions'][partition], indent=2) + '\n')
            print('EXTRACTED', partition, len(records), 'entries', flush=True)
    version = (out / 'system/etc/VERSION').read_text().strip()
    if version != '1.3.16.2':
        raise ValueError('Extracted system version differs')
    (out / 'extraction_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('COMPLETE', out, 'VERSION', version, flush=True)


if __name__ == '__main__':
    main()
