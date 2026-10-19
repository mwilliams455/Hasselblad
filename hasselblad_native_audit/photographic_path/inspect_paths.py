#!/usr/bin/env python3
"""Hash-specific static function/call inventory; executes no vendor code."""
from pathlib import Path
import argparse
import bisect
import hashlib
import json
import re
import struct
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'colour_audit'))
from disassemble_colour import all_symbols, ELFFile


def inspect(path):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        symbols = all_symbols(elf)
        functions = {}
        labels = {}
        for symbol in symbols:
            address = int(symbol['st_value'])
            if not address:
                continue
            labels[address] = symbol.name
            if symbol['st_info']['type'] == 'STT_FUNC':
                functions[symbol.name] = {'name': symbol.name, 'address': address,
                                          'size': int(symbol['st_size']), 'calls': []}
        dyn = elf.get_section_by_name('.dynsym')
        plt = elf.get_section_by_name('.plt')
        reloc = elf.get_section_by_name('.rela.plt')
        if dyn and plt and reloc:
            for index, entry in enumerate(reloc.iter_relocations()):
                labels[int(plt['sh_addr']) + 32 + 16 * index] = dyn.get_symbol(entry['r_info_sym']).name + '@plt'
        section = elf.get_section_by_name('.text')
        raw, base = section.data(), int(section['sh_addr'])
        for function in functions.values():
            start = function['address'] - base
            if start < 0 or not function['size']:
                continue
            stop = min(len(raw), start + function['size'])
            for offset in range(start, stop - 3, 4):
                word = struct.unpack_from('<I', raw, offset)[0]
                if word & 0x7c000000 != 0x14000000:
                    continue
                immediate = word & 0x3ffffff
                if immediate & 0x2000000:
                    immediate -= 0x4000000
                target = base + offset + immediate * 4
                if function['address'] <= target < function['address'] + function['size']:
                    continue
                function['calls'].append({'address': base + offset, 'target': target,
                                          'symbol': labels.get(target),
                                          'instruction': 'bl' if word & 0x80000000 else 'b'})
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'file': path.name, 'sha256': digest, 'functions': list(functions.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--match', default='hncs|ccm|gamma|3dlut|hbl_calib|dsp_tone|drc_tone|raw2rgb|tone_mapping|curve_gen')
    parser.add_argument('libraries', nargs='*', default=['librcam.so','libdcam_pp.so','libdcam_pp_base.so','libalgo_share.so','libadj_base.so','libdcam_adj_product.so'])
    args = parser.parse_args()
    result = [inspect(BASE / 'firmware/extracted/system/lib64' / name) for name in args.libraries]
    (Path(__file__).parent / 'call_inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    pattern = re.compile(args.match, re.I)
    for library in result:
        selected = [function for function in library['functions'] if pattern.search(function['name']) and not function['name'].startswith('DIQ_')]
        print(json.dumps({'file': library['file'], 'sha256': library['sha256'], 'selected': selected}))


if __name__ == '__main__':
    main()
