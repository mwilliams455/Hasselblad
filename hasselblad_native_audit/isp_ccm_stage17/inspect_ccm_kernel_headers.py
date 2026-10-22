#!/usr/bin/env python3
"""Bounded original X2D II kernel header search for ISP CCM register/math clues.

Processes the verified kheaders.ko built-in XZ archive as inert input. Reports
file identities, lexical hit counts and matching macro NAMES only, not header
contents, firmware instructions or proprietary photographic tuning tables.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import lzma
from pathlib import Path
import re
import tarfile

KHEADERS_SHA="b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b"
XZ_SHA="e0a474714b6980b41d9d7701a6bd768240a63d0889d8b37ae726f976d3199c27"
MAX_TAR=45*1024*1024
MAX_MEMBER=2*1024*1024
TOKENS={
 "ccm_token":re.compile(rb"(?<![A-Za-z0-9_])CCM(?![A-Za-z0-9_])|(?<![A-Za-z0-9_])ccm(?![A-Za-z0-9_])"),
 "ccm_identifier":re.compile(rb"(?i)\b[a-z0-9_]*ccm[a-z0-9_]*\b"),
 "lmtx_fw":re.compile(rb"(?i)lmtx[_-]?fw"),
 "main_ccm":re.compile(rb"(?i)main[_-]?ccm"),
 "known_register_base":re.compile(rb"(?i)0xf322c[0-9a-f]{3}"),
 "ccm_q_format":re.compile(rb"(?i)\b(?:ccm|color|colour)[_a-z0-9]{0,40}(?:q\d+|fraction|precision|shift|fixed[_-]?point)[a-z0-9_]*\b"),
}
MACRO=re.compile(rb"(?m)^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b")

def sha(x):return hashlib.sha256(x).hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)

def inspect(module:Path):
    from elftools.elf.elffile import ELFFile
    expected=KHEADERS_SHA
    with module.open('rb') as f:
        h=hashlib.file_digest(f,'sha256').hexdigest()
        require(h==expected,'wrong_original_kheaders_identity')
        f.seek(0)
        elf=ELFFile(f)
        require(elf['e_machine']=='EM_AARCH64','not_original_aarch64_kernel_module')
        raw=elf.get_section_by_name('.rodata').data()
    require(sha(raw)==XZ_SHA,'wrong_internal_header_archive_hash')
    unpacked=lzma.decompress(raw)
    require(len(unpacked)<=MAX_TAR,'header_archive_size_limit')
    records=[];total=0;total_entries=0
    with tarfile.open(fileobj=io.BytesIO(unpacked),mode='r:') as archive:
        for member in archive:
            total_entries+=1
            if not member.isfile():continue
            total+=member.size
            require(total<=MAX_TAR and member.size<=MAX_MEMBER,'header_file_size_limit')
            payload=archive.extractfile(member).read()
            hits={k:len(p.findall(payload)) for k,p in TOKENS.items()}
            matched=sum(hits.values())
            if not matched:continue
            names=[x.decode('ascii','replace') for x in MACRO.findall(payload)]
            ccm_macros=[n for n in names if 'ccm' in n.lower() or 'lmtx' in n.lower()]
            # Some files are large and have generic platform names. Retain only
            # vendor/media/ISP headers or explicit CCM names for the priority list.
            relevant=bool(re.search(r'(dji|eagle|muse|camera|isp|ccm|media|lmtx)',member.name,re.I))
            records.append({"path":member.name,"file_sha256":sha(payload),"file_bytes":member.size,
                            "matching_token_counts":hits,"ccm_macro_names":sorted(set(ccm_macros))[:100],
                            "prioritized_vendor_or_ISP_filename":relevant})
    interesting=[x for x in records if x['prioritized_vendor_or_ISP_filename']]
    best=sorted(interesting,key=lambda x:(-sum(x['matching_token_counts'].values()),x['path']))
    candidates=[x for x in best if x['matching_token_counts']['main_ccm'] or x['matching_token_counts']['lmtx_fw'] or x['matching_token_counts']['known_register_base'] or x['matching_token_counts']['ccm_q_format']]
    result={"schema":"hasselblad-stage17b-original-kheaders-ccm-search-v1",
            "status":"verified_header_archive_bounded_content_search",
            "original_kheaders_module_sha256":KHEADERS_SHA,
            "internal_original_xz_sha256":XZ_SHA,
            "member_count":total_entries,
            "regular_file_bytes_checked":total,
            "files_with_ccm_hits":len(records),
            "prioritized_vendor_or_ISP_header_hits":len(interesting),
            "candidate_headers_for_pixel_math":candidates[:25],
            "other_prioritized_header_hits":best[:35],
            "unresolved_core_pixel_ccm_equation":True,
            "vendor_header_contents_exported":False,
            "firmware_tables_or_values_exported":False,
            "source":"original_kheaders_ko_elf_inert_static_archive",
            "limits":["Names and regex matches do not establish pixel arithmetic or numeric Q encoding.",
                      "Only compiled kernel-header archive examined, not an exhaustive documentation/source search.",
                      "No MAIN CCM runtime ISP input-output observation recorded."]}
    return result

def self_test():
    payload=b'#define ISP_CCM_SHIFT 9\n#define CCM_Q12 7\n#define MUSE_CCM_WIDTH 16\n' \
            b'/* main_ccm lmtx_fw 0xf322c1cc */\n'
    assert TOKENS['ccm_identifier'].search(payload)
    assert TOKENS['main_ccm'].search(payload)
    assert TOKENS['lmtx_fw'].search(payload)
    assert TOKENS['known_register_base'].search(payload)
    assert len(MACRO.findall(payload))==3
    assert sum('ccm' in n.decode().lower() for n in MACRO.findall(payload))==3
    print(json.dumps({"status":"PASS","fixture":"synthetic_header_regex_positive_and_negative",
                     "vendor_input_loaded":False,"main_ccm_equation_proven":False}))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--module',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test();return
    require(a.module and a.output,'module_and_output_required')
    report=inspect(a.module)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({"status":report['status'],"headers_scanned":report['member_count'],
          "candidate_headers":len(report['candidate_headers_for_pixel_math']),
          "main_ccm_equation_proven":False}))
if __name__=='__main__':main()
