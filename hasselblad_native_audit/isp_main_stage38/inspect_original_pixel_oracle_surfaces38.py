#!/usr/bin/env python3
"""Stage38 — read-only source-bound inventory of *potential* original ISP pixel oracles.

Audits genuine X2D II 100C 1.3.16.2 ARM ELF symbol names and bounded text
strings for frame/image injection, capture, tap, dump, writeback and test-pattern
entrypoints. Symbol names are *triage*, not proof of a working pixel oracle.
No vendor code is executed, no images or tuned parameters are read or exported.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import lzma
import re
from collections import Counter
from pathlib import Path

PINS = {
    'system/lib/modules/vcam_driver.ko': '29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e',
    'system/lib/modules/cam_vreg.ko': '26cf2246d56a36a5f7d107799ddced307ed94e53ac22c9928962a0fcff920ff6',
    'system/lib64/librcam.so': '3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66',
    'system/lib64/libdcam_pp.so': 'bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9',
    'system/lib64/libdcam_pp_base.so': '72934142975fa88ee65e331767e8b9badd9ca40bc987e3c9a2a5cf0ff60b3f76',
    'system/lib64/libduml_hal.so': 'adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20',
}
FIRMWARE_SHA = '9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'
MAX_ELF_BYTES = 160 * 1024 * 1024
MAX_DEBUG_BYTES = 64 * 1024 * 1024
MAX_EXPORT_NAMES_PER_CLASS = 64
MAX_CSTR_SECTION_BYTES = 12 * 1024 * 1024
MAX_CSTR_LENGTH = 256

# 'Pixel' in a function name is not a dataflow proof; preserve uncertainty.
PIXEL_TERMS = re.compile(r'(?:pixel|frame|image|img|yuv|raw|rgb|dma|buf|b2r|r2y|isp|vcam|rcam|ccm|dsp|pp_)', re.I)
READOUT_TERMS = re.compile(r'(?:dump|readback|read_back|writeback|write_back|tap_|_tap|capture|snapshot|savedata|save_data|export|output_buf|out_buf|buf_out|frame_out)', re.I)
INJECT_TERMS = re.compile(r'(?:test.?pattern|test.?image|tpg|inject|input.?buf|buf.?input|frame.?input|offline.?reprocess|reprocess.?input)', re.I)
STATUS_TERMS = re.compile(r'(?:dbg|debug|trace|counter|status|peek|register|reg_dump|reg_read|log)', re.I)
FRAME_TERMS = re.compile(r'(?:b2r|r2y|v4l2|subdev|pad_|media_|vb2_|buf_|frame_|dma_|_dma|stream|yuv|raw2rgb|ccm|lut_|gamma_)', re.I)
KNOWN_NON_ORACLES = {
    'ccm_get_dbg_info_by_mux', 'ccm_set_dbg_mux', 'ccm_set_ig0_config',
    'ccm_set_fmt', 'ccm_set_fn0_config', 'main_ccm_calc_frame',
    'main_ccm_calc_global', 'main_ccm_calc_mode', 'raw2rgb_proc',
    '_raw2rgb_pull_buf_cb', 'message_trans_arm_proc_pull',
    'sl_message_trans_arm_proc_pull',
}
# Reject accidental exposure of addresses, secrets, filenames, coefficients or
# large vendor strings in exported candidate names. Names are public ELF symbols.
SAFE_NAME = re.compile(r'^[A-Za-z_.$@][A-Za-z0-9_.$@:+\-]{0,160}$')
TEXT_ANCHORS = {
    'camera_frame_dump': re.compile(rb'(?i)(?:dump[_ -]?(?:raw|yuv|rgb|frame|image|isp|ccm)|(?:raw|yuv|rgb|frame|image|isp|ccm)[_ -]?dump)'),
    'pixel_test_generator': re.compile(rb'(?i)(?:test[_ -]?pattern|test[_ -]?image|pattern[_ -]?generator|\btpg\b)'),
    'raw_stream_access': re.compile(rb'(?i)(?:/dev/video[0-9]+|v4l2[_ -]?subdev|/dev/vcam|/dev/media[0-9]+)'),
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tier(name: str) -> str | None:
    """Classify *names* only; never imply camera pixel content or access."""
    if name in KNOWN_NON_ORACLES:
        return 'prior_known_control_or_transport'
    if READOUT_TERMS.search(name) and PIXEL_TERMS.search(name):
        return 'potential_frame_readout_name'
    if INJECT_TERMS.search(name) and PIXEL_TERMS.search(name):
        return 'potential_synthetic_input_name'
    if INJECT_TERMS.search(name):
        return 'other_injection_or_pattern_name'
    if READOUT_TERMS.search(name):
        return 'other_readout_or_dump_name'
    if STATUS_TERMS.search(name) and (FRAME_TERMS.search(name) or PIXEL_TERMS.search(name)):
        return 'control_or_status_name'
    if FRAME_TERMS.search(name):
        return 'frame_transport_or_stream_name'
    return None


def safe_export_name(name: str) -> bool:
    return SAFE_NAME.fullmatch(name) is not None


def get_symbols(elf) -> tuple[dict[str, tuple[int, int]], dict[str, int]]:
    """Enumerate original ELF symbol tables, with bounded mini-debug decompression."""
    from elftools.elf.elffile import ELFFile
    out: dict[str, tuple[int, int]] = {}
    stats: dict[str, int] = {}

    def consume(sec, kind: str):
        n = 0
        if sec is None or not hasattr(sec, 'iter_symbols'):
            stats[kind] = 0
            return
        for sym in sec.iter_symbols():
            if not sym.name or sym['st_shndx'] == 'SHN_UNDEF':
                continue
            if sym['st_info']['type'] != 'STT_FUNC':
                continue
            start, length = int(sym['st_value']), int(sym['st_size'])
            if not length or not safe_export_name(sym.name):
                continue
            n += 1
            key = sym.name
            if key in out and out[key] != (start, length):
                # Different addresses can be symbol-version aliases. Never
                # conflate them silently or export raw instruction bytes.
                stats['duplicate_symbol_names_with_distinct_extents'] = stats.get('duplicate_symbol_names_with_distinct_extents', 0) + 1
                continue
            out[key] = (start, length)
        stats[kind] = n
    consume(elf.get_section_by_name('.dynsym'), 'dynsym_defined_func_count')
    consume(elf.get_section_by_name('.symtab'), 'symtab_defined_func_count')
    debug = elf.get_section_by_name('.gnu_debugdata')
    if debug is not None:
        raw = lzma.decompress(debug.data(), memlimit=MAX_DEBUG_BYTES*4)
        require(len(raw) <= MAX_DEBUG_BYTES, 'mini_debugdata_oversized')
        mini = ELFFile(io.BytesIO(raw))
        consume(mini.get_section_by_name('.symtab'), 'mini_debugdata_defined_func_count')
    else:
        stats['mini_debugdata_defined_func_count'] = 0
    return out, stats


def string_signal_summary(elf) -> dict[str, int]:
    """Count anchor types in bounded string sections, never export source text."""
    counts = Counter()
    for sec in elf.iter_sections():
        # Explicit .rodata and .dynstr only. Not .text or arbitrary binary.
        if not (sec.name in ('.rodata', '.dynstr', '.strtab') or sec.name.startswith('.rodata.')):
            continue
        size = int(sec['sh_size'])
        if size > MAX_CSTR_SECTION_BYTES:
            counts['skipped_oversize_sections'] += 1
            continue
        data = sec.data()
        # Narrow: requires printable ASCII bounded null-terminated string.
        for blob in data.split(b'\0'):
            if not (4 <= len(blob) <= MAX_CSTR_LENGTH) or any(x < 32 or x > 126 for x in blob):
                continue
            for label, pat in TEXT_ANCHORS.items():
                if pat.search(blob):
                    counts[label] += 1
    return {k:int(counts.get(k,0)) for k in [*TEXT_ANCHORS,'skipped_oversize_sections']}


def inspect_file(path: Path, expected: str) -> dict:
    from elftools.elf.elffile import ELFFile
    require(path.is_file() and 0 < path.stat().st_size <= MAX_ELF_BYTES, 'source_missing_or_oversize')
    require(sha(path) == expected, 'source_sha256_mismatch')
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        require(elf['e_machine'] == 'EM_AARCH64' and elf.little_endian, 'wrong_elf_architecture')
        syms, sym_stats = get_symbols(elf)
        ranked = {}
        for name in sorted(syms):
            category=tier(name)
            if category:
                ranked.setdefault(category, []).append(name)
        exported = {k:v[:MAX_EXPORT_NAMES_PER_CLASS] for k,v in sorted(ranked.items())}
        truncated={k:len(v)>MAX_EXPORT_NAMES_PER_CLASS for k,v in sorted(ranked.items())}
        result = {
            'sha256': expected,
            'total_distinct_named_defined_functions': len(syms),
            'symbol_source_counts': sym_stats,
            'candidate_categories_total': {k:len(v) for k,v in sorted(ranked.items())},
            'candidate_names_bounded': exported,
            'category_names_truncated': truncated,
            'bounded_string_signals': string_signal_summary(elf),
            'pixel_buffer_argument_dataflow_verified':False,
            'original_isp_input_or_output_pixels_captured':False,
        }
        return result


def synthetic() -> dict:
    fixtures = [
        ('ccm_set_ig0_config', 'prior_known_control_or_transport'),
        ('ccm_get_dbg_info_by_mux', 'prior_known_control_or_transport'),
        ('raw2rgb_proc', 'prior_known_control_or_transport'),
        ('main_ccm_calc_frame', 'prior_known_control_or_transport'),
        ('isp_dump_yuv_frame', 'potential_frame_readout_name'),
        ('ccm_pixel_readback', 'potential_frame_readout_name'),
        ('rgb_frame_capture', 'potential_frame_readout_name'),
        ('b2r_test_pattern_generator', 'potential_synthetic_input_name'),
        ('vcam_frame_inject', 'potential_synthetic_input_name'),
        ('test_pattern', 'other_injection_or_pattern_name'),
        ('dump_firmware', 'other_readout_or_dump_name'),
        ('ccm_dbg_status', 'control_or_status_name'),
        ('ccm_register_peek', 'control_or_status_name'),
        ('b2r_pad_set_fh_fmt', 'frame_transport_or_stream_name'),
        ('some_calculation', None),
    ]
    for name, expected in fixtures:
        require(tier(name)==expected, 'synthetic_classification_'+name)
    for name in ['i_should_contain_a_password\nSECRET', 'a'*162, 'input.json/../../private']:
        require(not safe_export_name(name), 'invalid_exported_symbol')
    require(safe_export_name('r2y_pad_set_fh_fmt'), 'valid_symbol_guard')
    require(TEXT_ANCHORS['camera_frame_dump'].search(b'dump_ccm_frame') is not None, 'test_frame_anchor')
    require(TEXT_ANCHORS['pixel_test_generator'].search(b'test_pattern_generator') is not None, 'test_pattern_anchor')
    require(TEXT_ANCHORS['raw_stream_access'].search(b'/dev/video1') is not None, 'test_device_anchor')
    return {
        'schema':'hasselblad-stage38-isp-oracle-surfaces-synthetic-v1',
        'status':'PASS_synthetic',
        'cases':len(fixtures)+3+1+3,
        'original_firmware_loaded':False,
        'original_isp_pixel_oracle_found':False,
        'photographic_renderer_changed':False,
    }


def inspect(root: Path) -> dict:
    files={name:inspect_file(root/name,pin) for name,pin in PINS.items()}
    return {
        'schema':'hasselblad-stage38-original-isp-pixel-oracle-interface-triage-v1',
        'status':'PASS_exact_original_elf_symbol_and_bounded_string_inventory',
        'firmware_model':'Hasselblad X2D II 100C',
        'firmware_version':'1.3.16.2',
        'firmware_sha256':FIRMWARE_SHA,
        'source_files':files,
        'total_potential_frame_readout_named_symbols':sum(f['candidate_categories_total'].get('potential_frame_readout_name',0) for f in files.values()),
        'total_potential_synthetic_input_named_symbols':sum(f['candidate_categories_total'].get('potential_synthetic_input_name',0) for f in files.values()),
        'candidate_names_mean_actual_capture_possible':False,
        'actual_isolated_MAIN_CCM_before_after_pixel_oracle':False,
        'original_six_coefficient_pixel_equation_proven':False,
        'MAIN_gamma_or_LUT_pixel_parity_proven':False,
        'vendor_original_ELF_data_or_instructions_exported':False,
        'private_images_or_sensor_calibration_exported':False,
        'phone_photo_pipeline_unchanged':True,
        'caveat':'Names and strings alone do not prove runtime viability, pixel memory arguments, graph connectivity, or that a dump is before/after MAIN CCM. Unnamed/stripped routines and the encrypted DSP are outside the scope.'
    }


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--firmware-root',type=Path)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args()
    if a.self_test:
        report=synthetic()
    else:
        require(a.firmware_root is not None and a.output is not None,'firmware_root_and_output_required')
        report=inspect(a.firmware_root)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],
                      'source_count':len(report.get('source_files',{})),
                      'readout_names':report.get('total_potential_frame_readout_named_symbols',0),
                      'synthetic_input_names':report.get('total_potential_synthetic_input_named_symbols',0),
                      'pixel_oracle_proven':False},sort_keys=True))

if __name__=='__main__':
    main()