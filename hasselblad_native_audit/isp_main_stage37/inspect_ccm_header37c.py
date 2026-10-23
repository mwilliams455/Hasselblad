#!/usr/bin/env python3
"""Stage37C: hash-pinned X2D II Eagle2 CCM register-contract header triage.

Read-only probe of official 1.3.16.2 kheaders module and textual firmware header
files. Never exports vendor header contents, tuning arrays, offsets from header
contents, firmware bytes, or a purported ISP colour equation.

Embedded kernel headers, when present, are NOT automatically a MAIN ISP pixel
specification. Any matching file names are review leads, not proof of arithmetic.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import re
import tarfile
from pathlib import Path

KHEADERS_SHA = 'b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b'
FULL_FIRMWARE_ID = 'X2D_II_100C_1.3.16.2'
XZ_MAGIC = b'\xfd7zXZ\x00'
ARCHIVE_LIMIT = 128 * 1024 * 1024
ARCHIVE_CANDIDATE_LIMIT = 24
TEXT_FILE_LIMIT = 2 * 1024 * 1024
MEMBER_LIMIT = 60000
SCAN_TOTAL_LIMIT = 96 * 1024 * 1024
# Exact symbol/string candidates from prior audited X2D II firmware, not a
# general 'ccm' search (which also matches unrelated acronyms). These can be
# seen as bytes or metadata; never output a source context or numeric payload.
ANCHORS = {
    'main_ccm': re.compile(rb'(?i)main[_-]?ccm'),
    'lmtx_fw': re.compile(rb'(?i)lmtx[_-]?fw'),
    'ccm_set_ig0_config': re.compile(rb'(?i)ccm[_-]?set[_-]?ig0[_-]?config'),
    'ccm_debug_mux': re.compile(rb'(?i)ccm[_-]?(?:set|get)[_-]?dbg[_-]?(?:mux|info)'),
    'eagle2': re.compile(rb'(?i)eagle[_-]?2'),
    'yuv_pp_ccm': re.compile(rb'(?i)yuv[_-]?pp[_-]?ccm'),
    'level_ctrl_inv_lut': re.compile(rb'(?i)level[_-]?ctrl[_-]?inv[_-]?lut'),
}
# Confirm useful exact nouns without emitting proprietary header text.
STRICT = {'lmtx_fw','ccm_set_ig0_config','yuv_pp_ccm','level_ctrl_inv_lut'}
TEXT_SUFFIXES = {'.h','.hpp','.hh','.inc','.dts','.dtsi','.txt','.md','.json','.xml'}
ALLOWED_TOPS = {'system','vendor'}


def require(ok: bool, msg: str):
    if not ok:
        raise ValueError(msg)


def is_safe_name(name: str):
    parts = name.split('/')
    return (0 < len(name) <= 240 and '\x00' not in name and '\\' not in name
            and not name.startswith('/') and all(p not in ('','..') for p in parts))


def classify(data: bytes):
    return [key for key, pattern in ANCHORS.items() if pattern.search(data)]


def empty_stats():
    return {'text_files_examined':0,'bytes_examined':0,
            'anchor_file_hits':{name:0 for name in ANCHORS},
            'review_paths_by_anchor':{'eagle2':[],'main_ccm':[]},
            'eagle2_files_with_same_file_ccm_or_yuvpp_terms':0,
            'oversized_text_paths_skipped':[],
            'strict_anchor_member_paths':[],
            'strict_anchor_file_count':0,
            'any_exact_hardware_pixel_contract_proven':False}


def scan_content(name: str, data: bytes, stats: dict):
    # Append no data bytes, lines, words, numeric tuning, or disassembly.
    require(is_safe_name(name), 'unsafe_tar_member_name')
    require(len(data) <= TEXT_FILE_LIMIT, 'unexpected_text_size')
    require(stats['bytes_examined'] + len(data) <= SCAN_TOTAL_LIMIT, 'excessive_text_scan')
    stats['bytes_examined'] += len(data)
    stats['text_files_examined'] += 1
    found = classify(data)
    for key in found:
        stats['anchor_file_hits'][key] += 1
        if key in stats['review_paths_by_anchor'] and len(stats['review_paths_by_anchor'][key]) < 32:
            stats['review_paths_by_anchor'][key].append(name)
    if 'eagle2' in found and re.search(rb'(?i)(?:\bccm\b|\byuv[_-]?pp\b|\blmtx\b)',data):
        stats['eagle2_files_with_same_file_ccm_or_yuvpp_terms'] += 1
    if any(key in STRICT for key in found):
        stats['strict_anchor_file_count'] += 1
        # Restrict to validated relative header paths, not actual contents.
        if len(stats['strict_anchor_member_paths']) < 24:
            stats['strict_anchor_member_paths'].append(name)


def parse_tar(data: bytes):
    stats = empty_stats()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tf:
        members = tf.getmembers()
        require(len(members) <= MEMBER_LIMIT,'too_many_tar_members')
        stats['tar_member_count'] = len(members)
        for m in members:
            require(is_safe_name(m.name.rstrip('/')), 'unsafe_member')
            if not m.isfile() or Path(m.name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            if m.size > TEXT_FILE_LIMIT:
                stats['oversized_text_files_skipped'] = stats.get('oversized_text_files_skipped',0)+1
                if len(stats['oversized_text_paths_skipped']) < 24:
                    stats['oversized_text_paths_skipped'].append(m.name)
                continue
            f = tf.extractfile(m)
            require(f is not None, 'unreadable_tar_text_member')
            scan_content(m.name, f.read(TEXT_FILE_LIMIT+1), stats)
    return stats


def probe_kheaders(path: Path):
    with path.open('rb') as f:
        data = f.read()
    require(hashlib.sha256(data).hexdigest() == KHEADERS_SHA, 'wrong_exact_kheaders_ko')
    positions = [m.start() for m in re.finditer(re.escape(XZ_MAGIC), data)]
    require(len(positions) <= ARCHIVE_CANDIDATE_LIMIT,'too_many_embedded_xz_candidates')
    archives = []
    for pos in positions:
        try:
            d = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128*1024*1024)
            raw = d.decompress(data[pos:], max_length=ARCHIVE_LIMIT+1)
            if not d.eof or len(raw) > ARCHIVE_LIMIT:
                continue
            result = parse_tar(raw)
            archives.append(result)
        except (lzma.LZMAError, tarfile.TarError, EOFError):
            continue
    return {'original_module_sha256':KHEADERS_SHA,'embedded_xz_signatures':len(positions),
            'parseable_bounded_embedded_header_archives':len(archives),
            'header_archives':archives,'vendor_bytes_exported':False}


def probe_loose_headers(root: Path):
    stats = empty_stats()
    for top in sorted(ALLOWED_TOPS):
        base = root / top
        if not base.exists():
            continue
        for path in sorted(base.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = path.relative_to(root).as_posix()
            require(is_safe_name(rel),'unsafe_loose_path')
            if path.stat().st_size > TEXT_FILE_LIMIT:
                stats['oversized_text_files_skipped'] = stats.get('oversized_text_files_skipped',0)+1
                if len(stats['oversized_text_paths_skipped']) < 24:
                    stats['oversized_text_paths_skipped'].append(rel)
                continue
            scan_content(rel,path.read_bytes(),stats)
    return stats


def inspect(root: Path):
    require(root.is_dir(),'missing_extracted_firmware')
    expected = root / 'system/lib/modules/kheaders.ko'
    require(expected.is_file(),'kheaders_module_missing')
    k = probe_kheaders(expected)
    loose = probe_loose_headers(root)
    return {
        'schema':'hasselblad-stage37c-exact-original-header-contract-triage-v1',
        'status':'PASS_pinned_vendor_header_contract_triage',
        'original_firmware':FULL_FIRMWARE_ID,
        'source': k,
        'loose_text_scan':loose,
        'strict_pixel_equation_proven':False,
        'six_coefficients_Q_scale_proven':False,
        'six_coefficients_channel_order_proven':False,
        'six_coefficients_clipping_proven':False,
        'original_pixel_oracle_obtained':False,
        'vendor_headers_contents_exported':False,
        'private_pixels_or_calibration_exported':False,
        'android_photographic_renderer_unchanged':True,
        'interpretation':'Counts or positive path names are discovery leads only; no firmware CCM arithmetic or bit exact pixel result was validated.'
    }


def synthetic():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)
        payloads={
            'include/uapi/generic.h':b'hello ioctl world',
            'include/linux/camera.h':b'camera main_ccm lmtx_fw names only',
            'include/soc/possible_ccm.h':b'level_ctrl_inv_lut and yuv_pp_ccm',
            'include/linux/eagle2_isp.h':b'Eagle2 imaging platform',
        }
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w:') as tar:
            for name,data in payloads.items():
                ti=tarfile.TarInfo(name);ti.size=len(data);tar.addfile(ti,io.BytesIO(data))
        tar_data=out.getvalue()
        roundtrip=lzma.decompress(lzma.compress(tar_data))
        require(roundtrip==tar_data,'xz_roundtrip')
        a=parse_tar(roundtrip)
        require(a['tar_member_count']==4,'tar_count')
        require(a['text_files_examined']==4,'scanned_count')
        require(a['strict_anchor_file_count']==2,'strict_count')
        require(a['anchor_file_hits']['lmtx_fw']==1,'lmtx_match')
        require(a['anchor_file_hits']['main_ccm']==1,'ccm_match')
        require(a['anchor_file_hits']['yuv_pp_ccm']==1,'yuv_match')
        require(a['anchor_file_hits']['eagle2']==1,'eagle2_match')
        require(a['review_paths_by_anchor']['eagle2']==['include/linux/eagle2_isp.h'],'paths')
        require(a['eagle2_files_with_same_file_ccm_or_yuvpp_terms']==0,'cooccurrence_negative')
        require(not a['any_exact_hardware_pixel_contract_proven'],'no_claim')
        require(classify(b'synthetic colour matrix')==[],'no_vague_matrix')
        require(classify(b'decoy CCM-administration')==[],'no_ccm_false_positive')
        require(not is_safe_name('../private/file.h'),'reject_traversal')
        require(not is_safe_name('/absolute.h'),'reject_absolute')
        require(is_safe_name('include/linux/hello.h'),'accept_path')
        require(not is_safe_name('hi\\bye'),'reject_backslash')
        return {'status':'PASS_synthetic','checks':15,'vendor_assets_loaded':False,
                'original_pixel_equation_proven':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--self-test',action='store_true')
    a=p.parse_args()
    if a.self_test:
        result=synthetic()
    else:
        require(a.firmware_root is not None,'extracted_firmware_required')
        result=inspect(a.firmware_root)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],
                     'checks':result.get('checks'),
                     'header_archives':result.get('source',{}).get('parseable_bounded_embedded_header_archives'),
                     'strict_header_paths':sum(len(a['strict_anchor_member_paths']) for a in result.get('source',{}).get('header_archives',[])),
                     'loose_firmware_paths':result.get('loose_text_scan',{}).get('strict_anchor_file_count'),
                     'original_pixel_equation_proven':False}))

if __name__=='__main__':
    main()