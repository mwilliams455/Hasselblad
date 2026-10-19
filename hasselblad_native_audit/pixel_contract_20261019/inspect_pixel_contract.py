#!/usr/bin/env python3
"""Record exact ELF evidence and optional IQ-array hash relationships, without payloads."""
import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path
from elftools.elf.elffile import ELFFile

PINS = {
    'librcam.so': '3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66',
    'libduml_hal.so': 'adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20',
}
TARGETS = {
    '_Z24lookup_rgb_pixel_plt_fmtPKvRKmS2_S2_R8PixelRGB': (0x74fb0, 148),
    '_Z14do_3dlut_transR8PixelRGBRKiPFS0_PKvRKmS6_S6_S0_ES4_m': (0x72dc0, 1564),
    '_Z22get_plt_fmt_unit_3dlutPvRKm': (0x74e50, 348),
    '_Z28set_rgb_pixel_to_plt_fmt_lutPjRKjS1_S1_RKdS3_S3_': (0x74c88, 452),
}
PARSER_SHA = '0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root', required=True, type=Path)
    p.add_argument('--output-directory', required=True, type=Path)
    p.add_argument('--iq-parser', type=Path,
                   help='Optional exact-hash inspect_iq_config.py from the prior frozen audit')
    a = p.parse_args()
    root = a.firmware_root.resolve()
    libroot = root / 'system/lib64'
    a.output_directory.mkdir(parents=True, exist_ok=True)
    for name, digest in PINS.items():
        if sha(libroot/name) != digest:
            raise ValueError(f'Unsupported {name} SHA256')
    with (libroot/'libduml_hal.so').open('rb') as f:
        elf = ELFFile(f)
        syms = {s.name:s for s in elf.get_section_by_name('.dynsym').iter_symbols()}
        text = elf.get_section_by_name('.text')
        evidence = []
        for name,(va,size) in TARGETS.items():
            s = syms[name]
            if (s['st_value'],s['st_size']) != (va,size):
                raise ValueError('Export address/extent mismatch')
            data = text.data()[va-text['sh_addr']:va-text['sh_addr']+size]
            evidence.append({'name':name, 'va':hex(va), 'bytes':size,
                             'code_sha256':hashlib.sha256(data).hexdigest()})
        dependencies = [t.needed for t in elf.get_section_by_name('.dynamic').iter_tags()
                        if t.entry.d_tag == 'DT_NEEDED']
        segments = [{k:int(s[k]) for k in ('p_vaddr','p_offset','p_filesz','p_memsz','p_flags')}
                    for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    refs = []
    scanned = 0
    for path in sorted(libroot.rglob('*')):
        if not path.is_file():
            continue
        with path.open('rb') as f:
            if f.read(4) != b'\x7fELF':
                continue
            f.seek(0)
            elf = ELFFile(f)
            scanned += 1
            sec = elf.get_section_by_name('.dynsym')
            if sec is None:
                continue
            symbols = [s for s in sec.iter_symbols() if s.name in TARGETS or
                       s.name in ('duss_hal_cube_to_plt_fmt_vaddr','duss_hal_tdlut_cube_to_bin')]
            if symbols:
                refs.append({'path':str(path.relative_to(root)), 'sha256':sha(path),
                             'symbols':[{'name':s.name,'defined':s['st_shndx']!='SHN_UNDEF',
                                         'va':hex(s['st_value'])} for s in symbols]})
    result = {
        'scope':'Exact export metadata and bounded dynamic-symbol survey; missing imports do not rule out indirect/hardware links',
        'library_pins':PINS, 'display_exports':evidence,
        'display_dependencies':dependencies, 'display_load_segments':segments,
        'system_lib64_elfs_scanned':scanned, 'dynamic_symbol_references':refs,
        'tool_sha256':sha(Path(__file__)),
    }
    (a.output_directory/'pixel_contract_static_evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    if a.iq_parser:
        if sha(a.iq_parser) != PARSER_SHA:
            raise ValueError('IQ parser does not match the prior audited source')
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('frozen_iq_parser',a.iq_parser)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config_path = root/'system/etc/iq/hb722_config.json'
        config = module.read_config(config_path)
        arrays = []
        def walk(v, path):
            if isinstance(v,dict):
                for k,x in v.items(): walk(x,path+'.'+k)
            elif isinstance(v,list):
                if len(v)>=6144 and all(isinstance(x,int) and 0<=x<=0xffffffff for x in v):
                    if any(k in path.lower() for k in ('3dlut','lut3d','tlut')):
                        packed = struct.pack('<'+'I'*len(v),*v)
                        record = {'path':path,'words':len(v),'sha256':hashlib.sha256(packed).hexdigest()}
                        if len(v)%6144==0:
                            record['chunks_6144_sha256']=[hashlib.sha256(packed[i:i+24576]).hexdigest()
                                                          for i in range(0,len(packed),24576)]
                        arrays.append(record)
                else:
                    for i,x in enumerate(v): walk(x,f'{path}[{i}]')
        walk(config,'root')
        main_hashes={h for r in arrays if 'main_3dlut' in r['path']
                     for h in r.get('chunks_6144_sha256',[])}
        for r in arrays:
            r['matches_main_profile_chunks']=[i for i,h in enumerate(r.get('chunks_6144_sha256',[]))
                                              if h in main_hashes]
        result={'config_sha256':sha(config_path),'parser_sha256':PARSER_SHA,
                'method':'Only hashes and lengths of existing uint32 arrays; slicing does not assume packing or meaning',
                'arrays':arrays,'tool_sha256':sha(Path(__file__))}
        (a.output_directory/'asset_format_relationship.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'display_exports':len(evidence),'elfs_scanned':scanned,
                      'dynamic_symbol_reference_files':[r['path'] for r in refs],
                      'output_directory':str(a.output_directory)}))

if __name__ == '__main__':
    main()
