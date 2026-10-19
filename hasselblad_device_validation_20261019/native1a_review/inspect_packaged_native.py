#!/usr/bin/env python3
"""Recheck Native1A package bytes; reuse byte-identical prior ELF evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zipfile

sys.path.insert(0, '/tmp/hasselblad-audit-python')
from elftools.elf.elffile import ELFFile

PAGE = 16384


def sha(data):
    return hashlib.sha256(data).hexdigest()


def overlap(a, b):
    return max(a[0], b[0]) < min(a[1], b[1])


def inspect_elf(data):
    elf = ELFFile(io.BytesIO(data))
    loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    relros = [s for s in elf.iter_segments() if s['p_type'] == 'PT_GNU_RELRO']
    conflicts = []
    for segment in relros:
        start, end = segment['p_vaddr'], segment['p_vaddr'] + segment['p_memsz']
        protection = (start // PAGE * PAGE, (end + PAGE - 1) // PAGE * PAGE)
        for section in elf.iter_sections():
            if section['sh_flags'] & 3 != 3 or not section['sh_size']:
                continue
            ss, se = section['sh_addr'], section['sh_addr'] + section['sh_size']
            outside = [(ss, min(se, start)), (max(ss, end), se)]
            if any(a < b and overlap((a, b), protection) for a, b in outside):
                conflicts.append({'section': section.name, 'section_start': hex(ss), 'section_end': hex(se),
                                  'relro_start': hex(start), 'relro_end': hex(end),
                                  'rounded_protection_start': hex(protection[0]), 'rounded_protection_end': hex(protection[1])})
    dynamic = elf.get_section_by_name('.dynamic')
    needed = [t.needed for t in dynamic.iter_tags() if t.entry.d_tag == 'DT_NEEDED']
    symtab = elf.get_section_by_name('.dynsym')
    selected_symbols = [s.name for s in symtab.iter_symbols()
                        if any(x in s.name for x in ('createDng', 'SetWhiteLevelRational', 'SetCustomFieldULong'))]
    return {
        'elf_class': elf.elfclass, 'machine': elf.header['e_machine'],
        'load_alignments': sorted(set(s['p_align'] for s in loads)),
        'elf_load_alignment_16k': all(s['p_align'] >= PAGE and s['p_align'] % PAGE == 0 and
                                     (s['p_vaddr'] - s['p_offset']) % PAGE == 0 for s in loads),
        'load_segments': [{'offset': s['p_offset'], 'virtual_address': s['p_vaddr'],
                           'file_bytes': s['p_filesz'], 'memory_bytes': s['p_memsz'],
                           'flags': s['p_flags'], 'alignment': s['p_align']} for s in loads],
        'relro_writable_page_overlap_at_16k': conflicts,
        'needed': needed, 'selected_dynamic_symbols': selected_symbols,
        'new_white_level_error_marker_present': b'WhiteLevel cannot be represented as an unsigned TIFF LONG' in data,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--prior-review', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    apk_data = args.apk.read_bytes()
    assert sha(apk_data) == args.expected_sha256
    prior = json.loads(args.prior_review.read_text())
    old = {row['path']: row for row in prior['libraries']}
    rows = []
    changed = []
    with zipfile.ZipFile(io.BytesIO(apk_data)) as archive:
        native = [i for i in archive.infolist() if i.filename.startswith('lib/') and i.filename.endswith('.so')]
        assert {i.filename for i in native} == set(old)
        for item in native:
            data = archive.read(item)
            checksum = sha(data)
            identical = checksum == old[item.filename]['sha256']
            row = dict(old[item.filename]) if identical else {'path': item.filename, **inspect_elf(data)}
            if not identical:
                changed.append(item.filename)
            name_length, extra_length = struct.unpack_from('<HH', apk_data, item.header_offset + 26)
            assert apk_data[item.header_offset:item.header_offset+4] == b'PK\x03\x04'
            data_offset = item.header_offset + 30 + name_length + extra_length
            row.update({'sha256': checksum, 'bytes': len(data),
                        'payload_identical_to_prior_review': identical,
                        'previous_payload_sha256': old[item.filename]['sha256'],
                        'zip_compression': 'stored' if item.compress_type == zipfile.ZIP_STORED else item.compress_type,
                        'zip_data_offset': data_offset,
                        'zip_data_alignment_16k': data_offset % PAGE == 0})
            assert row['zip_compression'] == 'stored' and row['zip_data_alignment_16k']
            rows.append(row)
    assert sorted(changed) == ['lib/arm64-v8a/libdngCreator.so', 'lib/armeabi-v7a/libdngCreator.so']
    for row in rows:
        if row['path'] in changed:
            assert row['elf_load_alignment_16k']
            assert not row['relro_writable_page_overlap_at_16k']
            assert row['new_white_level_error_marker_present']
            assert sorted(row['needed']) == sorted(old[row['path']]['needed'])
    arm64 = [row for row in rows if row['path'].startswith('lib/arm64-v8a/')]
    assert len(arm64) == 9
    assert all(row['elf_load_alignment_16k'] and not row['relro_writable_page_overlap_at_16k'] for row in arm64)
    result = {
        'artifact': {'filename': args.apk.name, 'bytes': len(apk_data), 'sha256': sha(apk_data)},
        'result': 'pass',
        'method': 'Rehash every final APK native payload and recompute local ZIP data offsets. Reuse prior ELF evidence only for matching hashes. Independently parse the two changed DNG writer ELFs with pyelftools.',
        'prior_review': {'filename': args.prior_review.name, 'sha256': sha(args.prior_review.read_bytes()), 'artifact': prior['artifact']},
        'native_library_count': len(rows), 'unchanged_payload_count': len(rows)-len(changed),
        'changed_payloads': changed, 'all_native_zip_offsets_align16k': True,
        'all_arm64_elfs_pass_static16k': True,
        'all_bundled_elfs_pass_static16k': all(r['elf_load_alignment_16k'] and not r['relro_writable_page_overlap_at_16k'] for r in rows),
        'retained_architecture_exception': prior['native_packaging_summary']['exception'],
        'libraries': rows,
        'scope': 'Static package/ELF checks. The previous Native1 device result does not establish this changed DNG writer has run on the physical device.'
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('libraries', 'prior_review', 'retained_architecture_exception')}, indent=2))


if __name__ == '__main__':
    main()
