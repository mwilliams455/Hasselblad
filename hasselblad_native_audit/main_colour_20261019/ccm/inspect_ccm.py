#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect exact-firmware CCM preparation; emit hashes/metadata, never coefficients.

Requires pyelftools and capstone. Inputs are user-supplied extracted firmware;
this tool neither downloads nor publishes firmware. It does not execute it.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

LIB_SHA = '3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66'
SCHEMA_SHA = '59ec3b0d019b9e8873f3d005c041b4e3ca1a2b930c503c110c51531f8bd30e40'
PARSER_SHA = '0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec'
SOURCE_SHA = '59d1b6c8a291280a8749f5ca190370e5dbff8ce0e6694a7da779ae5488ae641e'
SYMBOLS = {
    'dcam_isp_vreg_get_type': (0x54b88, 4),
    'mm_get_coeff': (0x2bac00, 160),
    'mm_lerp': (0x2baca0, 44),
    'mm_mx_lerp_gap': (0x2bb138, 1228),
    'DIQ_iq_main_ccm_lmtx_fw': (0x33f960, 64),
    'DIQ_mod_main_ccm_lmtx_fw': (0x33f9a0, 60),
    'main_ccm_init': (0x39d6f0, 332),
    'main_ccm_calc_global': (0x39d840, 1048),
    'main_ccm_calc_frame': (0x39e4b0, 2148),
    'post_scap3_calc_ccm': (0x2f2698, 820),
    '_Calc_GetLerpInfo': (0x3b2cd0, 440),
    '_Calc_GetCoeff': (0x3b42a8, 5840),
    '_calc_lerp_mx_lut_reg_idx_v5': (0x3b9ea8, 464),
    '_calc_lerp_mx_lut_reg_idx_v5_enh': (0x3c3ad8, 484),
    '_update_ccm_debug_func': (0x31af98, 1132),
    'DjiIsp_Reg_GetGroupNum': (0x251a10, 4),
    'isp_drv_reg_get_group_num': (0x2771d0, 64),
}


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def own_module(name, path):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def va_bytes(elf, va, size):
    for segment in elf.iter_segments():
        if (segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= va and
                va + size <= segment['p_vaddr'] + segment['p_filesz']):
            start = va - segment['p_vaddr']
            return segment.data()[start:start + size]
    raise ValueError('Requested extent is not file-backed')


def enum_values(schema, name):
    plain = re.sub(r'//[^\n]*|/\*.*?\*/', '', schema, flags=re.S)
    match = re.search(r'enum\s+' + re.escape(name) + r'\s*:\s*int\s*\{(.*?)\}', plain, re.S)
    if not match:
        raise ValueError('Missing audited enum')
    result, value = {}, -1
    for field in match.group(1).split(','):
        if not field.strip():
            continue
        parts = field.strip().split('=')
        if len(parts) > 2 or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', parts[0].strip()):
            raise ValueError('Unsupported enum syntax')
        value = int(parts[1].strip(), 0) if len(parts) == 2 else value + 1
        result[parts[0].strip()] = value
    return result


def inspect(root):
    audit = Path(__file__).resolve().parents[2]
    lib = root / 'system/lib64/librcam.so'
    schema_path = root / 'system/etc/iq/config.fbs'
    parser_path = audit / 'photographic_path/inspect_iq_config.py'
    if sha(lib) != LIB_SHA or sha(schema_path) != SCHEMA_SHA or sha(parser_path) != PARSER_SHA:
        raise ValueError('Unsupported library, schema or parser hash')
    parser = own_module('hb_ccm_iq_parser', parser_path)
    config_path = root / 'system/etc/iq/hb722_config.json'
    config = parser.read_config(config_path)
    parameter = config['iq_table']['module']['main_ccm']['lmtx_fw']
    expected_parameter = {'type': 'lerp_1d_lut_reg_idx_v5', 'group': 'global_frame',
                          'axis': ['cc_color_temp', 'color_hiso'], 'total': 16}
    values = config['iq_table']['data'][0]['main_ccm'][0]['lmtx_fw']
    axis = config['iq_table']['data'][0]['mode_axis']['cc_color_temp']
    if parameter != expected_parameter or axis != [2400, 3050, 5550, 9100] or len(values) != 768:
        raise ValueError('Unexpected audited CCM table shape')
    payload = struct.pack('<768i', *values)
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA:
        raise ValueError('Unexpected coefficient source hash')
    schema = schema_path.read_text()
    calc = enum_values(schema, 'calc')
    axes = enum_values(schema, 'calc_axis')
    if (calc['lerp_1d_lut_reg_idx_v5'], axes['cc_color_temp'], axes['color_hiso']) != (50, 6, 17):
        raise ValueError('Unexpected audited enum mapping')

    helper_path = audit / 'colour_audit/disassemble_colour.py'
    helper = own_module('hb_ccm_symbols', helper_path)
    functions = []
    with lib.open('rb') as source:
        elf = ELFFile(source)
        if elf['e_machine'] != 'EM_AARCH64' or elf.elfclass != 64 or not elf.little_endian:
            raise ValueError('Expected little-endian AArch64 ELF64')
        symbols = helper.all_symbols(elf)
        by_name = {symbol.name: symbol for symbol in symbols}
        labels = {symbol['st_value']: symbol.name for symbol in symbols}
        plt, rel = elf.get_section_by_name('.plt'), elf.get_section_by_name('.rela.plt')
        dynsym = elf.get_section_by_name('.dynsym')
        for i, item in enumerate(rel.iter_relocations()):
            labels[plt['sh_addr'] + 32 + 16*i] = dynsym.get_symbol(item['r_info_sym']).name + '@plt'
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        for name, (va, size) in SYMBOLS.items():
            symbol = by_name[name]
            if (symbol['st_value'], symbol['st_size']) != (va, size):
                raise ValueError('Unexpected function identity or extent: ' + name)
            code = va_bytes(elf, va, size)
            calls = []
            for ins in md.disasm(code, va):
                if ins.mnemonic in ('b', 'bl') and ins.op_str.startswith('#'):
                    target = int(ins.op_str[1:], 0)
                    if not va <= target < va + size:
                        calls.append({'site': hex(ins.address), 'target_va': hex(target),
                                      'target': labels.get(target), 'tail_branch': ins.mnemonic == 'b'})
            functions.append({'name': name, 'va': hex(va), 'bytes': size,
                              'code_sha256': hashlib.sha256(code).hexdigest(), 'direct_calls': calls})
        jump_table = va_bytes(elf, 0x520224, 108*4)
        targets = {name: 0x520224 + struct.unpack_from('<i', jump_table, axes[name]*4)[0]
                   for name in ('cc_color_temp', 'color_hiso')}
        if targets != {'cc_color_temp': 0x3b45e4, 'color_hiso': 0x3b445c}:
            raise ValueError('Unexpected coefficient-axis dispatch')

    profiles = [values[i*96:(i+1)*96] for i in range(8)]
    data = config['iq_table']['data'][0]['main_ccm'][0]
    result = {
        'firmware': 'Hasselblad X2D II 100C 1.3.16.2', 'library_sha256': LIB_SHA,
        'schema_sha256': SCHEMA_SHA, 'config_sha256': sha(config_path),
        'parser_sha256': PARSER_SHA, 'symbol_helper_sha256': sha(helper_path),
        'inspector_sha256': sha(Path(__file__)), 'functions': functions,
        'parameter': parameter, 'calc_enum': 50, 'cct_axis': axis,
        'axis_dispatch': {name: {'enum': axes[name], 'target_va': hex(target)}
                          for name, target in targets.items()},
        'source': {'encoding': 'little-endian int32 slots containing signed16 coefficients',
                   'values': 768, 'bytes': len(payload), 'sha256': SOURCE_SHA,
                   'profiles': 8, 'values_per_profile': 96,
                   'all_values_within_signed16': all(-32768 <= value <= 32767 for value in values),
                   'each_profile_has_16_equal_six_coefficient_rows':
                       all(all(p[k*6:(k+1)*6] == p[:6] for k in range(16)) for p in profiles),
                   'secondary_banks_identical': profiles[:4] == profiles[4:]},
        'color_hiso_gain_rate': config['iq_table']['data'][0]['mode_axis']['color_hiso'],
        'disabled_in_global_data0': {name: all(value == 0 for value in data[name])
                                    for name in ('enable_lpf', 'enable_hue_mod',
                                                 'enable_desaturation', 'enable_level_ctrl')},
        'static_witnesses': [
            {'site': '0x3b9fa4', 'meaning': 'Register group count multiplied by parameter total gives coefficient stride.'},
            {'site': '0x3b9fb4', 'meaning': '_Calc_GetLerpInfo multiplies axis sizes to validate the complete source extent.'},
            {'site': '0x3b9ff8', 'meaning': 'Original mm_mx_lerp_gap is called once per register-group component.'},
            {'site': '0x3ba01c', 'meaning': 'Each scalar is written through DjiIsp_Reg_Set.'},
            {'site': '0x3b52b4', 'meaning': 'color_hiso resets its interval index to zero before interpolating two gain-selected rates.'},
            {'site': '0x3b52b8', 'meaning': 'Original mm_lerp calculates the secondary Q8 weight.'},
            {'site': '0x3b52bc', 'meaning': 'color_hiso returns axis size two, independently of the four gain/rate records.'},
            {'function': '_update_ccm_debug_func', 'meaning': 'Requires 96 values and sign-extends 16-bit register coefficients for debug inspection.'}
        ],
        'coefficients_published': False, 'pixel_ccm_formula_proven': False,
        'limits': ['Source/config linkage is static plus relocated metadata, not a recorded camera capture.',
                   'Six coefficients per group do not establish a conventional 3x3 matrix, fraction bits, channel order or clamp rule.',
                   'The two identical secondary banks are a property of this exact global still table.']
    }
    return result, values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result, _ = inspect(args.firmware_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'functions': len(result['functions']),
                      'source_values': result['source']['values']}))


if __name__ == '__main__':
    main()
