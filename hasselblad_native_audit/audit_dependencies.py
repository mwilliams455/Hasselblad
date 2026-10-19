#!/usr/bin/env python3
"""Static ELF dependency inventory; does not load or execute firmware code."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import sys

from elftools.elf.elffile import ELFFile

DEFAULT_CANDIDATES = [
    'libdcam_adj_product.so', 'libadj_base.so', 'libalgo_share.so', 'libaaa.so',
    'libdcamecg_process.so', 'libdcam_pp.so', 'libdcam_pp_base.so', 'librcam.so',
    'libdcam_image_file_writer_base.so', 'libdcam_muxer.so',
]
ANDROID_CORE = {'libc.so', 'libm.so', 'libdl.so', 'liblog.so', 'ld-android.so'}


def inspect(path, root):
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            return None
        stream.seek(0)
        elf = ELFFile(stream)
        needed, search_paths, soname = [], {}, None
        dynamic = elf.get_section_by_name('.dynamic')
        init = {}
        for tag in dynamic.iter_tags() if dynamic else []:
            kind = tag.entry.d_tag
            if kind == 'DT_NEEDED':
                needed.append(tag.needed)
            elif kind == 'DT_SONAME':
                soname = tag.soname
            elif kind in ('DT_RPATH', 'DT_RUNPATH'):
                search_paths[kind] = getattr(tag, kind[3:].lower())
            elif kind in ('DT_INIT', 'DT_INIT_ARRAY', 'DT_INIT_ARRAYSZ'):
                init[kind] = int(tag.entry.d_val)
        symbols = elf.get_section_by_name('.dynsym')
        undefined = []
        export_count = 0
        for symbol in symbols.iter_symbols() if symbols else []:
            if not symbol.name:
                continue
            if symbol['st_shndx'] == 'SHN_UNDEF':
                undefined.append(symbol.name)
            elif symbol['st_info']['bind'] in ('STB_GLOBAL', 'STB_WEAK'):
                export_count += 1
        versions = {}
        verneed = elf.get_section_by_name('.gnu.version_r')
        for version, aux in verneed.iter_versions() if verneed else []:
            versions[version.name] = [item.name for item in aux]
        machine, elfclass, kind = elf['e_machine'], elf.elfclass, elf['e_type']
        load_segments = [{key: int(segment[key]) for key in
                          ('p_offset', 'p_vaddr', 'p_filesz', 'p_memsz', 'p_align')}
                         for segment in elf.iter_segments()
                         if segment['p_type'] == 'PT_LOAD']
        debug = elf.get_section_by_name('.gnu_debugdata') is not None
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {
        'path': str(path.relative_to(root)), 'name': path.name,
        'sha256': digest, 'bytes': path.stat().st_size, 'machine': machine,
        'elf_class': elfclass, 'elf_type': kind, 'soname': soname,
        'needed': needed, 'search_paths': search_paths,
        'symbol_version_requirements': versions,
        'initializers': init, 'gnu_debugdata': debug,
        'load_segments': load_segments,
        'load_segments_congruent_16k': all(
            (segment['p_vaddr'] - segment['p_offset']) % 16384 == 0
            for segment in load_segments),
        'dynamic_export_count': export_count,
        'undefined_symbols': sorted(set(undefined)),
    }


def closure(name, index):
    found, missing, queue = {}, set(), deque([name])
    while queue:
        requested = queue.popleft()
        if requested in found or requested in missing:
            continue
        info = index.get(requested)
        if info is None:
            missing.add(requested)
            continue
        found[requested] = info
        queue.extend(info['needed'])
    return {
        'candidate': name, 'library_count': len(found),
        'bytes': sum(info['bytes'] for info in found.values()),
        'libraries': sorted(found), 'missing': sorted(missing),
        'android_core_libraries': sorted(set(found) & ANDROID_CORE),
        'private_android_symbol_versions': {
            dependency: {library: versions for library, versions in info['symbol_version_requirements'].items()
                         if any('PRIVATE' in version or 'PLATFORM' in version for version in versions)}
            for dependency, info in found.items()
            if any('PRIVATE' in version or 'PLATFORM' in version
                   for versions in info['symbol_version_requirements'].values() for version in versions)
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent / 'firmware/extracted/system')
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent / 'dependency_report.json')
    parser.add_argument('candidates', nargs='*')
    args = parser.parse_args()
    index, duplicates = {}, {}
    # Root lib64 wins over subdirectory names. No symlinks are followed.
    files = sorted((args.root / 'lib64').rglob('*.so'), key=lambda path: (len(path.parts), str(path)))
    for path in files:
        info = inspect(path, args.root)
        if info is None:
            continue
        for name in {info['name'], info['soname']} - {None}:
            if name in index and index[name]['path'] != info['path']:
                duplicates.setdefault(name, [index[name]['path']]).append(info['path'])
            else:
                index[name] = info
    selected = args.candidates or DEFAULT_CANDIDATES
    closures = [closure(name, index) for name in selected]
    report = {
        'firmware_version': '1.3.16.2',
        'firmware_sha256': '9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6',
        'root': str(args.root),
        'method': 'Static ELF DT_NEEDED recursion; not runtime namespace or constructor proof. Dynamic dlopen targets are not inferred.',
        'duplicate_library_names': duplicates,
        'libraries': list({info['path']: info for info in index.values()}.values()),
        'candidate_closures': closures,
    }
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    for item in closures:
        print(json.dumps(item))
    print('REPORT', args.out)


if __name__ == '__main__':
    main()
