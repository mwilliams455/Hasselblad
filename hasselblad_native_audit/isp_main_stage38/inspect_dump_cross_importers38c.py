#!/usr/bin/env python3
"""Stage38C — original-camera cross-library direct callers of frame dump APIs.

Uses matching exact-firmware ELF PLT import metadata and AArch64 BL targets.
No camera ISP operation is invoked. Reporting a dump *call* is not verifying
MAIN CCM pre/post pixels or that the call executes in an ordinary still.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from inspect_original_pixel_oracle_calls38b import collect_symbols, parse_plt, owner_by_start
from inspect_original_pixel_oracle_surfaces38 import PINS, require, sha

IMPORTER_PINS = {
    'system/lib64/libdcam_pp.so':PINS['system/lib64/libdcam_pp.so'],
    'system/lib64/libdcam_adj_product.so':'bd42b0ff4eae48cd9cc1637220d6b73dd97898c2190ae0d3d8f4fd93e26e60ea',
    'system/lib64/librcam.so':PINS['system/lib64/librcam.so'],
}
DUMP_IMPORTS = (
    'pp_dump_frame_to_file_base',
    'pp_dump_plane_to_file',
    'pp_dump_frame_buffer_info',
    'pp_dump_buf',
)
MAX_RETURN_CALLERS = 110


def analyze_code(elf, byaddr, plt):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    from collections import Counter
    sec=elf.get_section_by_name('.text')
    require(sec is not None and 0<int(sec['sh_size'])<100*1024*1024,'text_missing_or_oversize')
    # Matching original file means the PLT ordinal mapping was checked upstream.
    stubs={va:name for va,name in plt.items() if name in DUMP_IMPORTS}
    calls={n:Counter() for n in DUMP_IMPORTS}
    cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
    cs.detail=True
    op_count=0
    for i in cs.disasm(sec.data(),int(sec['sh_addr'])):
        if i.mnemonic!='bl':continue
        op_count+=1
        for a in i.operands:
            if a.type != ARM64_OP_IMM:continue
            named=stubs.get(int(a.imm))
            if named:
                calls[named][owner_by_start(byaddr,i.address)]+=1
    summary={}
    for n in DUMP_IMPORTS:
        top=sorted(calls[n].items(),key=lambda x:(-x[1],x[0]))
        summary[n]={
            'imported_by_binary':n in plt.values(),
            'direct_callsite_count':sum(calls[n].values()),
            'known_direct_caller_names':[{'name':k,'callsite_count':v} for k,v in top[:MAX_RETURN_CALLERS]],
            'names_truncated':len(top)>MAX_RETURN_CALLERS,
            'name_only_same_stage_ccm_proof':False,
        }
    return summary,op_count


def synthetic():
    fake={0x1000:[('cap3_fusion17_in_buff_dump',256,1)],
          0x1400:[('raw2rgb_proc',100,1)]}
    assert owner_by_start(fake,0x1000)=='cap3_fusion17_in_buff_dump'
    assert owner_by_start(fake,0x1430)=='raw2rgb_proc'
    assert owner_by_start(fake,0x1600)=='unresolved_function_owner'
    assert len(IMPORTER_PINS)==3
    assert len(DUMP_IMPORTS)==4
    assert 'pp_dump_frame_to_file_base' in DUMP_IMPORTS
    assert 'system/lib64/libdcam_pp.so' in IMPORTER_PINS
    assert len(IMPORTER_PINS['system/lib64/libdcam_adj_product.so'])==64
    return {'status':'PASS_synthetic','checks':8,'firmware_used':False,
            'original_ccm_pixel_oracle_proven':False,
            'photon_saved_photographs_unchanged':True}


def inspect(root:Path):
    from elftools.elf.elffile import ELFFile
    result={}
    for path,expected in IMPORTER_PINS.items():
        full=root/path
        require(full.is_file() and sha(full)==expected,'missing_or_wrong_original_importer_'+path)
        with full.open('rb') as src:
            elf=ELFFile(src)
            require(elf['e_machine']=='EM_AARCH64' and elf.little_endian
                    and elf['e_type']=='ET_DYN','wrong_original_importer_elf')
            _,byaddr,num=collect_symbols(elf)
            plt,valid=parse_plt(elf)
            if not valid:
                result[path]={
                    'source_sha256':expected,
                    'plt_ordinal_mapping_validated':False,
                    'defined_symbol_entries_count':num,
                    'total_original_direct_bl_in_text':None,
                    'dump_imports':None,
                    'failure_boundary':'original_PLT_ordinal_mapping_not_proven_no_calls_reported',
                }
            else:
                callsummary,bl_total=analyze_code(elf,byaddr,plt)
                result[path]={
                    'source_sha256':expected,
                    'plt_ordinal_mapping_validated':True,
                    'defined_symbol_entries_count':num,
                    'total_original_direct_bl_in_text':bl_total,
                    'dump_imports':callsummary,
                }
    return {
        'schema':'hasselblad-stage38c-original-dump-import-callers-v1',
        'status':'PASS_exact_original_ELF_cross_importers',
        'target':'X2D II 100C 1.3.16.2',
        'original_importer_sources':result,
        'isolated_original_ccm_before_after_samples_proven':False,
        'main_ccm_pixel_equation_proven':False,
        'dsp_or_camera_hardware_executed':False,
        'original_vendor_codes_or_tuning_or_pixels_exported':False,
        'photo_renderer_main_branch_unchanged':True,
        'scope_limit':'Direct BL through statically validated PLT only; indirect/other binary calls and runtime branches unexcluded. Exporting a frame is not an isolated CCM pixel oracle.'
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=synthetic() if a.self_test else inspect(a.firmware_root if a.firmware_root else
             (_ for _ in ()).throw(ValueError('original_firmware_root_required')))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],
                     'direct_calls':{p:{name:r['direct_callsite_count'] for name,r in data['dump_imports'].items()}
                            for p,data in result.get('original_importer_sources',{}).items() if data['dump_imports'] is not None},
                     'isolated_ccm_pixel_oracle_proven':False},sort_keys=True))

if __name__=='__main__':main()