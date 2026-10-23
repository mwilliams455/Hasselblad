#!/usr/bin/env python3
"""Stage41: exact X2D II native live-view/SBPC symbol and string provenance.

Read-only original-firmware inventory for a label used by an independent
third-party UVC bridge. Original packet/image content is never requested.
No runtime functions are invoked. Presence of a name != pixel-stage location.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import lzma
import re
from pathlib import Path

VERSION='1.3.16.2'
ARCHIVE_SHA='9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'
KHEADERS_SHA='b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b'
KNOWN={
    'system/lib64/librcam.so':'3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66',
    'system/lib64/libdcam_pp.so':'bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9',
    'system/lib64/libdcam_pp_base.so':'72934142975fa88ee65e331767e8b9badd9ca40bc987e3c9a2a5cf0ff60b3f76',
    'system/lib64/libduml_hal.so':'adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20',
    'system/lib/modules/vcam_driver.ko':'29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e',
    'system/lib/modules/cam_vreg.ko':'26cf2246d56a36a5f7d107799ddced307ed94e53ac22c9928962a0fcff920ff6',
}
ROOTS=('system/lib64','system/bin','system/lib/modules','vendor/lib64','vendor/bin')
LABELS=(b'liveview_after_sbpc',b'sbpc',b'liveview',b'v4l2',b'nv12')
DISPLAY_LABELS=tuple(x.decode() for x in LABELS)
MAX_FILES=1800
MAX_EACH_BYTES=128*1024*1024
MAX_SCAN_BYTES=3*1024*1024*1024
MAX_DEBUG_BYTES=64*1024*1024
MAX_RETURN_FILES=65
MAX_NAMES=32
SAFE_NAME=re.compile(r'^[A-Za-z_.$@][A-Za-z0-9_.$@:+\-]{0,130}$')
SAFE_PATH=re.compile(r'^[A-Za-z0-9_.+/-]{1,200}$')

def safe_path(rel):
    return SAFE_PATH.fullmatch(rel) is not None and not rel.startswith('/') and '..' not in rel.split('/')
SYMBOL_MATCH=re.compile(r'(?:liveview|sbpc|nv12|v4l2|video_frame|uvc)',re.I)


def ensure(cond, msg):
    if not cond:raise ValueError(msg)


def digest(p:Path):
    with p.open('rb') as s:return hashlib.file_digest(s,'sha256').hexdigest()


def eligible(path:Path):
    return path.suffix in ('.so','.ko') or path.suffix==''


def candidate_paths(root:Path):
    paths=[];skipped_unsafe_names=0
    for sub in ROOTS:
        b=root/sub
        if not b.is_dir():continue
        for p in b.rglob('*'):
            if not p.is_file() or not eligible(p):continue
            rel=p.relative_to(root).as_posix()
            if not safe_path(rel):
                skipped_unsafe_names+=1
                continue
            paths.append((rel,p))
    ensure(len(paths)<=MAX_FILES,'original_elf_inventory_exceeds_limit')
    return sorted(paths),skipped_unsafe_names


def scan_raw_markers(path:Path):
    # Match bytes across chunk boundaries; only presence, no text export.
    found=set();carry=b''
    with path.open('rb') as f:
        while block:=f.read(1024*1024):
            blob=(carry+block).lower()
            for key in LABELS:
                if key in blob:found.add(key.decode())
            carry=blob[-32:]
    return sorted(found)


def symbol_hits(path:Path):
    from elftools.elf.elffile import ELFFile
    with path.open('rb') as f:
        elf=ELFFile(f)
        ensure(elf['e_machine']=='EM_AARCH64' and elf.little_endian,'unexpected_matched_elf')
        result=[]
        defined_total=0
        for section_name in ('.dynsym','.symtab'):
            sec=elf.get_section_by_name(section_name)
            if sec is None:continue
            for sym in sec.iter_symbols():
                if (not sym.name or sym['st_info']['type']!='STT_FUNC' or
                    sym['st_shndx']=='SHN_UNDEF' or not SAFE_NAME.fullmatch(sym.name)):
                    continue
                defined_total+=1
                if SYMBOL_MATCH.search(sym.name):result.append(sym.name)
        debug=elf.get_section_by_name('.gnu_debugdata')
        debug_checked=False
        if debug is not None and int(debug['sh_size'])<=MAX_DEBUG_BYTES:
            data=lzma.decompress(debug.data(),memlimit=MAX_DEBUG_BYTES*4)
            ensure(len(data)<=MAX_DEBUG_BYTES,'original_minidebug_exceeds_bound')
            mini=ELFFile(io.BytesIO(data))
            symbols=mini.get_section_by_name('.symtab')
            debug_checked=True
            if symbols is not None:
                for sym in symbols.iter_symbols():
                    if (not sym.name or sym['st_info']['type']!='STT_FUNC' or
                        sym['st_shndx']=='SHN_UNDEF' or not SAFE_NAME.fullmatch(sym.name)):
                        continue
                    defined_total+=1
                    if SYMBOL_MATCH.search(sym.name):result.append(sym.name)
        seen=sorted(set(result))
        return {'matching_defined_function_names':seen[:MAX_NAMES],
                'matching_names_total':len(seen),
                'name_list_truncated':len(seen)>MAX_NAMES,
                'defined_function_entries_examined':defined_total,
                'mini_debugdata_checked':debug_checked,
                'original_colour_stage_verified':False}


def inspect(root:Path):
    version=root/'system/etc/VERSION'
    ensure(version.is_file() and version.read_text().strip()==VERSION,'wrong_original_firmware_version')
    ensure(digest(root/'system/lib/modules/kheaders.ko')==KHEADERS_SHA,'third_party_kernel_identity_does_not_match')
    for rel,expected in KNOWN.items():
        ensure((root/rel).is_file() and digest(root/rel)==expected,'known_original_binary_mismatch_'+rel)
    rows=[];size_total=0;elfs=0;skipped=[]
    candidates,skipped_unsafe_names=candidate_paths(root)
    exact_label=[];string_related=[]
    for rel,p in candidates:
        size=p.stat().st_size
        if size<=0 or size>MAX_EACH_BYTES:
            skipped.append(rel);continue
        size_total+=size
        ensure(size_total<=MAX_SCAN_BYTES,'original_scan_bytes_exceeds_budget')
        with p.open('rb') as f:
            magic=f.read(4)
        if magic!=b'\x7fELF':continue
        elfs+=1
        markers=scan_raw_markers(p)
        if not markers and rel not in KNOWN:continue
        symbols=symbol_hits(p)
        if 'liveview_after_sbpc' in markers or 'liveview_after_sbpc' in symbols['matching_defined_function_names']:
            exact_label.append(rel)
        if any(x in markers for x in ('sbpc','liveview')) or symbols['matching_names_total']:
            string_related.append(rel)
        rows.append({'file':rel,
                     'source_sha256':digest(p),
                     'raw_ascii_byte_substring_presence':{key:key in markers for key in DISPLAY_LABELS},
                     'symbol_inventory':symbols,
                     'exact_third_party_hook_name_is_usable_export':False,
                     'stage_before_or_after_MAIN_CCM_proven':False})
    # Public directory basename metadata and no original instruction/text data.
    ensure(len(exact_label)<=MAX_RETURN_FILES,'excess_exact_label_hits')
    return {
        'schema':'hasselblad-stage41-original-sbpc-liveview-surface-v1',
        'status':'PASS_original_1_3_16_2_liveview_surface_inventory',
        'original_full_archive_sha256':ARCHIVE_SHA,
        'firmware_version':VERSION,
        'x_unleashed_kheaders_module_sha256_matches':True,
        'candidate_firmware_paths_examined':len(candidates),
        'paths_skipped_nonreportable_names_count':skipped_unsafe_names,
        'aarch64_elf_files_examined':elfs,
        'files_skipped_oversize_or_empty_count':len(skipped),
        'files_skipped_oversize_or_empty_paths':skipped[:MAX_RETURN_FILES],
        'exact_liveview_after_sbpc_literal_found_in':[x for x in exact_label[:MAX_RETURN_FILES]],
        'related_files_count':len(string_related),
        'related_files':rows[:MAX_RETURN_FILES],
        'related_files_truncated':len(rows)>MAX_RETURN_FILES,
        'original_liveview_hook_runtime_entry_proven':False,
        'MAIN_CCM_pre_post_pixel_stage_exposed':False,
        'original_main_colour_equation_proven':False,
        'private_frames_or_camera_identifiers_exported':False,
        'original_vendor_code_or_tuning_exported':False,
        'source_scope':'Bounded exact-hash native ELF symbol and byte substring search; no execution, runtime graph, ISP readback or camera access.'
    }


def synthetic():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        f=Path(tmp)/'demo.so'
        f.write_bytes(b'header' + b'liveview_after_'+b'sbpc\x00 NV12\x00')
        assert scan_raw_markers(f)==['liveview','liveview_after_sbpc','nv12','sbpc']
        f.write_bytes(b'ABC' + b'x'*((1024*1024)-3) + b'liveview_' + b'after_sbpc')
        assert scan_raw_markers(f)==['liveview','liveview_after_sbpc','sbpc']
        f.write_bytes(b'not a camera')
        assert scan_raw_markers(f)==[]
        assert eligible(Path('system/lib64/librcam.so'))
        assert eligible(Path('system/lib/modules/vcam_driver.ko'))
        assert not eligible(Path('system/etc/iq/hb722_config.json'))
        assert SAFE_NAME.fullmatch('liveview_after_sbpc')
        assert not SAFE_NAME.fullmatch('a\npassword')
        assert safe_path('system/lib64/librcam.so')
        assert not safe_path('../unsafe.bin')
        assert len(KNOWN)==6
        assert VERSION=='1.3.16.2'
        assert KHEADERS_SHA.startswith('b7cbbd598')
        assert 'ccm' not in SYMBOL_MATCH.pattern
    return {'status':'PASS_synthetic','checks':14,
            'original_firmware_loaded':False,'camera_accessed':False,
            'pre_post_ccm_pixel_oracle_proven':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--firmware-root',type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.self_test:d=synthetic()
    else:
        ensure(args.firmware_root is not None,'exact_original_firmware_root_required')
        d=inspect(args.firmware_root)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':d['status'],
                     'aarch64_elfs':d.get('aarch64_elf_files_examined',0),
                     'literal_matches':d.get('exact_liveview_after_sbpc_literal_found_in',[]),
                     'related_files_count':d.get('related_files_count',0),
                     'original_ccm_pixel_oracle_proven':False},sort_keys=True))

if __name__=='__main__':main()