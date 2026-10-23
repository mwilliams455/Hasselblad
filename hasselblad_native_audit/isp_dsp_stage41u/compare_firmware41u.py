#!/usr/bin/env python3
"""Compare two pinned X2D II firmware revisions without exporting vendor bytes.

Requires private, separately extracted OTA filesystems and an unmodified upstream
IMaH tool. Failed decoder output and per-image key files are always temporary.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import zipfile
from importlib.metadata import version

from dissect.extfs import ExtFS
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
for sibling in ('isp_dsp_stage41r', 'isp_dsp_stage41t'):
    sys.path.insert(0, str(HERE.parent/sibling))
from audit_imah41r import (parse, options, checksum, decode_independently,
    synthetic_checks, UPSTREAM_SHA256, UPSTREAM_COMMIT)
from audit_bootarea41t import public_key, verifies, changed, boot_layout, PINS

RELEASES = {
 '1.2.7.16': {
  'cim': '68aa9bce63c303a7d13ca4c14aae76be935925d596094bdcb92549cff42e1bc1',
  'ota': 'fdc6660f001c52c057f05840d7b6d7685ac4ebe631289e36c77089cb2ac41646',
  'system': '3019ed75cdb7bcf5a33be9e8e6b4d48db9e4e5f7288f9b60de57757d9de9e63d',
  'vendor': '40fdb05fb05007f1e517ffb983494daf9f3b2bb077bb805f2b175b4d926320d0'},
 '1.3.16.2': {
  'cim': '9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6',
  'ota': '7ccd5df4dab8d098d9895973fb62bcedcaa379f75fb044408a8263ce2d1f9a57',
  'system': '24aba59a96dfb93485fbf7ab899b3dc6522e203aa39cb810745a72b0115e8c21',
  'vendor': 'f459a6a9bd32b9bc09e3c9f175b80d6fe61e54215ca28b69510f0cf1166162d1'},
}
HOST_PATHS = [
 'system/bin/ss_dsp_manager', 'system/lib64/libfw_util.so',
 'system/lib64/libfw_util_ca.so', 'system/lib64/libteec.so',
 'system/lib64/libdcam_pp.so', 'system/lib64/libdcam_pp_base.so',
 'system/lib64/librcam.so', 'system/lib64/libduml_hal.so',
 'system/lib64/libduml_hal_cam.so', 'system/lib/modules/eagle_dsp.ko',
 'system/lib/modules/ask_dsp_driver.ko', 'system/lib/modules/vcam_driver.ko',
 'system/lib64/camera/plugins/pp_algo/libdcam_pp_e2_hiso.so',
 'system/lib64/camera/plugins/pp_algo/libdcam_pp_rdns_grain.so',
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_release(root, cim, release):
    pins = RELEASES[release]
    assert file_sha(cim) == pins['cim']
    assert file_sha(root/'ota.zip') == pins['ota']
    assert (root/'system/etc/VERSION').read_text().strip() == release
    records = {}
    targets = list(PINS) + HOST_PATHS
    # Bind selected files directly to pinned filesystem images, independently
    # of extraction-manifest claims. Also rehash every recorded regular file.
    for partition in ('system', 'vendor'):
        image = root/(partition+'.img')
        assert file_sha(image) == pins[partition]
        with image.open('rb') as stream:
            fs = ExtFS(stream)
            for name in targets:
                if name.startswith(partition+'/'):
                    node = fs.get('/'+name.split('/', 1)[1])
                    assert node.filetype == 0o100000
                    with node.open() as src:
                        assert src.read() == (root/name).read_bytes()
        manifest = json.loads((root/(partition+'_manifest.json')).read_text())
        assert manifest['image_sha256'] == pins[partition]
        for row in manifest['records']:
            if row['kind'] != 'file':
                continue
            name = partition+'/'+row['path']
            relative = Path(name)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert name not in records
            assert file_sha(root/name) == row['sha256']
            records[name] = row['sha256']
    containers = {name: (root/name).read_bytes() for name in PINS}
    if release == '1.3.16.2':
        assert all(sha(containers[name]) == pin for name, pin in PINS.items())
    with zipfile.ZipFile(root/'ota.zip') as archive:
        for name in ('tos.img', 'bootarea.img'):
            assert archive.namelist().count(name) == 1
        boot = archive.read('bootarea.img')
        containers['OTA/tos.img'] = archive.read('tos.img')
    offsets = [i for i in range(len(boot)-3) if boot[i:i+4] == b'IM*H']
    assert offsets == [1024, 233472]
    for offset in offsets:
        size = struct.unpack_from('<I', boot, offset+8)[0]
        assert offset+size <= len(boot)
        containers[f'OTA/bootarea.img@{offset}'] = boot[offset:offset+size]
    return boot, containers, records


def verify_signed(data, keys):
    info = parse(data)
    h, s = info['header_size'], info['signature_size']
    assert info['payload_digest_matches'] and info['encrypted_checksum_matches']
    for backend, key in keys.items():
        assert verifies(key, data[:h], data[h:h+s], backend)
        assert not verifies(key, changed(data[:h], 64), data[h:h+s], backend)
        assert not verifies(key, data[:h], changed(data[h:h+s], 0), backend)
    bad = parse(changed(data, len(data)-1))
    assert not bad['payload_digest_matches'] and not bad['encrypted_checksum_matches']
    return info


def strict_trials(module, data, info):
    names = [n for n in module.keys if n.startswith(info['encryption_id']+'-')]
    assert len(names) == 6 and info['encryption_id'] == 'TBIE'
    rows = []
    for name in names:
        plain = decode_independently(data, info, module.keys[name])
        matched = checksum(plain) == struct.unpack_from('<I', data, 152)[0]
        with tempfile.TemporaryDirectory(prefix='stage41u-private-') as tmp:
            root = Path(tmp)
            source = root/'input.img'
            source.write_bytes(data)
            po = options(source, root/'out', ['PRAK-STAGE41U', name], force=False)
            po.verbose = 2
            stdout, stderr = io.StringIO(), io.StringIO()
            reason = None
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    with source.open('rb') as stream:
                        module.imah_unsign(po, stream)
                except ValueError as exc:
                    reason = str(exc)
            assert 'Image file head signature verification passed.' in stdout.getvalue()
            assert reason == 'Decrypted chunks checksum verification failed.' and not matched
            counts = {}
            for chunk in info['chunks']:
                cid = chunk['id']; occurrence = counts.get(cid, 0)
                counts[cid] = occurrence+1
                suffix = cid if occurrence == 0 else cid+chr(96+occurrence)
                assert (root/f'out_{suffix}.bin').read_bytes() == plain[
                    chunk['offset']:chunk['offset']+chunk['size']]
            assert sha(source.read_bytes()) == sha(data)
        del plain
        rows.append({'key_name': name, 'force_continue': False,
            'signature_passes': True, 'plaintext_checksum_passes': False,
            'upstream_chunks_equal_independent_decoder': True,
            'stopped_at': reason, 'temporary_outputs_removed': True})
    return rows


def elf_sections(path):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        assert elf['e_machine'] == 'EM_AARCH64'
        rows = {}
        for section in elf.iter_sections():
            assert section.name not in rows
            rows[section.name] = {
                'type': section['sh_type'], 'flags': section['sh_flags'],
                'bytes': section['sh_size'],
                'sha256': None if section['sh_type'] == 'SHT_NOBITS' else sha(section.data())}
        return rows


def main():
    ap = argparse.ArgumentParser()
    for name in ('older-root', 'newer-root', 'older-cim', 'newer-cim', 'upstream-tool', 'receipt'):
        ap.add_argument('--'+name, type=Path, required=True)
    args = ap.parse_args()
    tool = args.upstream_tool.resolve()
    assert file_sha(tool) == UPSTREAM_SHA256
    spec = importlib.util.spec_from_file_location('stage41u_imah', tool)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    positive_controls = synthetic_checks(module)
    older = read_release(args.older_root, args.older_cim, '1.2.7.16')
    newer = read_release(args.newer_root, args.newer_cim, '1.3.16.2')
    assert older[0][:780] == newer[0][:780]
    record, pycrypto, openssl, key_info = public_key(older[0])
    keys = {'pycryptodome': pycrypto, 'cryptography_openssl': openssl}
    module.keys['PRAK-STAGE41U'] = record
    rows = []
    try:
        for name, a in older[1].items():
            b = newer[1][name]
            ia, ib = verify_signed(a, keys), verify_signed(b, keys)
            ha, hb = ia['header_size'], ib['header_size']
            pa, pb = ha+ia['signature_size'], hb+ib['signature_size']
            row = {'path': name, 'older_sha256': sha(a), 'newer_sha256': sha(b),
                'older_bytes': len(a), 'newer_bytes': len(b),
                'header_identical': a[:ha] == b[:hb],
                'signature_identical': a[ha:pa] == b[hb:pb],
                'ciphertext_identical': a[pa:] == b[pb:],
                'older_ciphertext_sha256': sha(a[pa:]), 'newer_ciphertext_sha256': sha(b[pb:]),
                'wrapped_key_field_identical': a[48:64] == b[48:64],
                'plaintext_checksum_field_identical': a[152:156] == b[152:156],
                'chunk_descriptors_identical': ia['chunks'] == ib['chunks'],
                'header_difference_offsets': [i for i in range(min(ha,hb)) if a[i] != b[i]],
                'auth_id': ia['auth_id'], 'encryption_id': ia['encryption_id'],
                'both_revisions_pass_signature_and_ciphertext_integrity': True,
                'both_revisions_reject_header_signature_and_payload_mutations': True,
                'independent_signature_backends': 2,
                'older_key_trials': strict_trials(module, a, ia)}
            rows.append(row)
            print(json.dumps({'path': name, 'ciphertext_identical': row['ciphertext_identical'],
                'older_strict_key_trials': len(row['older_key_trials']), 'valid_plaintexts': 0}), flush=True)
    finally:
        del module.keys['PRAK-STAGE41U']
    hosts = []
    for name in HOST_PATHS:
        a, b = args.older_root/name, args.newer_root/name
        sa, sb = elf_sections(a), elf_sections(b)
        common = set(sa) & set(sb)
        changed_sections = [n for n in sorted(common) if sa[n] != sb[n]]
        executable = [n for n in common if sa[n]['flags'] & 4 or sb[n]['flags'] & 4]
        hosts.append({'path': name, 'older_sha256': file_sha(a), 'newer_sha256': file_sha(b),
            'file_identical': a.read_bytes() == b.read_bytes(),
            'changed_sections': changed_sections,
            'older_only_sections': sorted(set(sa)-common), 'newer_only_sections': sorted(set(sb)-common),
            'common_executable_section_bytes_identical': all(sa[n] == sb[n] for n in executable),
            'common_executable_sections': sorted(executable)})
    common = set(older[2]) & set(newer[2])
    same = sum(older[2][n] == newer[2][n] for n in common)
    regions = []
    for a, b in zip(boot_layout(older[0])['regions'], boot_layout(newer[0])['regions']):
        assert (a['offset'],a['bytes'],a['classification']) == (b['offset'],b['bytes'],b['classification'])
        regions.append({**a, 'older_sha256': a['sha256'], 'newer_sha256': b['sha256'],
            'identical': a['sha256'] == b['sha256']})
        del regions[-1]['sha256']
    assert file_sha(tool) == UPSTREAM_SHA256
    receipt = {'schema': 'hasselblad-stage41u-two-revision-comparison-v1',
        'releases': RELEASES, 'upstream_commit': UPSTREAM_COMMIT,
        'upstream_tool_sha256': UPSTREAM_SHA256, 'positive_and_negative_controls': positive_controls,
        'public_key_identical': True, 'public_key': key_info, 'containers': rows,
        'compared_container_pairs': len(rows), 'strict_older_decryption_trials': sum(len(r['older_key_trials']) for r in rows),
        'valid_older_plaintexts': 0, 'host_components': hosts, 'boot_regions': regions,
        'regular_file_manifest_comparison': {'common': len(common), 'identical': same,
            'different': len(common)-same, 'older_only': len(set(older[2])-common),
            'newer_only': len(set(newer[2])-common), 'recorded_file_hashes_rechecked': True},
        'selected_files_checked_against_pinned_filesystem_images': True,
        'runtime': {n: version(n) for n in ['numpy','pycryptodome','cryptography','pyelftools','dissect.extfs']},
        'trust_scope': 'Same-package embedded public key; no independent manufacturer trust anchor or device fuse check.',
        'limits': ['Equal 32-bit plaintext checksums do not prove equal plaintext.',
            'Different ciphertext does not prove a DSP algorithm changed.',
            'Failed published TBIE keys do not prove a live camera is required.',
            'Unclassified boot tail remains unclassified despite identical bytes.'],
        'encryption_key_recovered': False, 'main_pixel_implementation_recovered': False,
        'production_rendering_changed': False, 'device_accessed': False,
        'vendor_code_executed': False, 'vendor_payload_or_key_bytes_exported': False}
    args.receipt.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'compared_container_pairs': len(rows), 'strict_older_decryption_trials': 54,
        'identical_host_files': sum(h['file_identical'] for h in hosts), 'valid_plaintexts': 0}))


if __name__ == '__main__':
    main()
