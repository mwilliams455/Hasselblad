#!/usr/bin/env python3
"""Stage38B — exact X2D II selected dump/test-pattern call-graph triage.

Inspects only identified original ELF functions. Preserves a strict boundary:
original named entrypoint/caller != input/output of MAIN_CCM. Does not export
vendor instruction bytes, parameters, images or live hardware registers.
"""
from __future__ import annotations
import argparse
import bisect
import hashlib
import io
import json
import lzma
from collections import Counter
from pathlib import Path
from typing import Any

from inspect_original_pixel_oracle_surfaces38 import PINS, MAX_DEBUG_BYTES, require, sha, safe_export_name

TARGETS = {
    'system/lib64/librcam.so': (
        'rcam_dbg_capture', 'rcam_dbg_dump_isp',
        'rcam_dbg_enable_segment_switch_isp_dump',
        'rcam_dev_get_cam_dump_controller_ops',
        'rcam_iq_vreg_dump_current_frame',
        '_imgsys_set_test_pattern',
        '_imx861_exmcu_imgsys_set_test_pattern',
    ),
    'system/lib64/libdcam_pp.so': (
        'dump_buffer', 'dump_buffer_path',
        'cap3_fusion17_in_buff_dump', 'cap3_fusion17_out_buff_dump',
    ),
    'system/lib64/libdcam_pp_base.so': (
        'pp_dump_frame_to_file_base', 'pp_dump_plane_to_file',
        'pp_dump_frame_buffer_info', 'pp_dump_buf',
        'pp_override_adj_dump_cfg_via_debug',
    ),
    'system/lib/modules/vcam_driver.ko': (
        '_vdev_export_buffer', 'reader_force_export_buffer',
        'e2_vdev_export_done_buffer',
    ),
}
MAX_FUNCTION_BYTES = 65536
MAX_DIRECT_CALLEES = 35
MAX_CALLER_NAMES = 35
R_AARCH64_CALL26 = 283
R_AARCH64_JUMP26 = 282


def collect_symbols(elf) -> tuple[dict[str, tuple[int,int,Any]],dict[int,list[tuple[str,int,Any]]],int]:
    from elftools.elf.elffile import ELFFile
    by_name:dict[str,tuple[int,int,Any]]={}
    by_address:dict[int,list[tuple[str,int,Any]]]={}
    n=0
    def consume(s):
        nonlocal n
        if not s or not hasattr(s,'iter_symbols'):return
        for x in s.iter_symbols():
            name=x.name
            if not name or not safe_export_name(name) or x['st_shndx']=='SHN_UNDEF' or x['st_info']['type']!='STT_FUNC':continue
            st,size=int(x['st_value']),int(x['st_size'])
            if size<4: continue
            n+=1
            val=(st,size,x['st_shndx'])
            if name in by_name and by_name[name] != val:
                continue
            by_name[name]=val
            by_address.setdefault(st,[]).append((name,size,x['st_shndx']))
    consume(elf.get_section_by_name('.dynsym'))
    consume(elf.get_section_by_name('.symtab'))
    d=elf.get_section_by_name('.gnu_debugdata')
    if d is not None:
        data=lzma.decompress(d.data(),memlimit=MAX_DEBUG_BYTES*4)
        require(len(data)<=MAX_DEBUG_BYTES,'debugdata_exceeds_bound')
        consume(ELFFile(io.BytesIO(data)).get_section_by_name('.symtab'))
    return by_name,by_address,n


def required_symbol(byname,name):
    require(name in byname,'missing_original_target_'+name)
    v=byname[name]
    require(4<=v[1]<=MAX_FUNCTION_BYTES,'unexpected_original_function_extent_'+name)
    return v


def code_slice(elf, fn):
    addr,size,shndx=fn
    if elf['e_type']=='ET_REL':
        require(isinstance(shndx,int),'original_symbol_missing_section_index')
        section=elf.get_section(shndx)
        require(bool(int(section['sh_flags']) & 4),'function_not_executable')
        require(addr>=0 and addr+size<=int(section['sh_size']),'function_out_of_section')
        return section.data()[addr:addr+size]
    for segment in elf.iter_segments():
        if segment['p_type']!='PT_LOAD' or not (int(segment['p_flags'])&1):continue
        v=int(segment['p_vaddr']);s=int(segment['p_filesz'])
        if v<=addr and addr+size<=v+s:
            off=addr-v
            return segment.data()[off:off+size]
    raise ValueError('original_function_not_in_executable_load_segment')


def parse_plt(elf):
    from elftools.elf.relocation import RelocationSection
    if elf['e_type']=='ET_REL':return {},False
    s=elf.get_section_by_name('.plt')
    r=elf.get_section_by_name('.rela.plt')
    if s is None or r is None or not isinstance(r,RelocationSection):return {},False
    reloc=list(r.iter_relocations())
    if int(s['sh_size'])!=32+16*len(reloc):return {},False
    symbols=elf.get_section(int(r['sh_link']))
    mapped={}
    for i,entry in enumerate(reloc):
        name=symbols.get_symbol(int(entry['r_info_sym'])).name
        if name and safe_export_name(name):mapped[int(s['sh_addr'])+32+i*16]=name
    return mapped,True


def owner_by_start(allbyaddr,site):
    starts=sorted(allbyaddr)
    idx=bisect.bisect_right(starts,site)-1
    if idx<0:return 'unresolved_function_owner'
    start=starts[idx]
    names=allbyaddr[start]
    # Aliases exist; only use symbol if inside at least one function extent.
    available=sorted(set(name for name,length,_ in names if site<start+length))
    return available[0] if available else 'unresolved_function_owner'


def inspect_calls(elf, fn, byaddr, plt):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_MEM
    addr,size,_=fn
    cap=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
    cap.detail=True
    inst=list(cap.disasm(code_slice(elf,fn),addr))
    require(len(inst)>0 and sum(i.size for i in inst)==size,'partial_target_disassembly')
    calls=Counter();bl=blr=memr=memw=0
    for i in inst:
        m=i.mnemonic.lower()
        if m=='bl':
            bl+=1
            targets=[int(o.imm) for o in i.operands if o.type==ARM64_OP_IMM]
            require(len(targets)==1,'unexpected_original_bl')
            target=targets[0]
            if target in plt:c='plt:'+plt[target]
            elif target in byaddr:c='local:'+sorted(z[0] for z in byaddr[target])[0]
            else:c='unresolved_direct_target'
            calls[c]+=1
        elif m=='blr':blr+=1
        if m.startswith(('ld','prfm')) and any(o.type==ARM64_OP_MEM for o in i.operands):memr+=1
        if m.startswith('st') and any(o.type==ARM64_OP_MEM for o in i.operands):memw+=1
    top=sorted(calls.items(),key=lambda kv:(-kv[1],kv[0]))
    io_refs=sum(calls[k] for k in calls if any(s in k.lower() for s in ('open','fwrite','write','read','ioctl','fclose','printf','memcpy','dump_','fopen','save_','rename')))
    register_refs=sum(calls[k] for k in calls if any(s in k.lower() for s in ('djiisp_reg','isp_vreg','vreg_','register_')))
    return {
        'function_bytes':size,'decoded_instructions':len(inst),
        'load_instructions':memr,'store_instructions':memw,
        'static_direct_call_count':bl,'static_indirect_call_count':blr,
        'bounded_callee_names':[{'name':k,'call_count':v} for k,v in top[:MAX_DIRECT_CALLEES]],
        'callee_names_truncated':len(top)>MAX_DIRECT_CALLEES,
        'calls_with_name_suggesting_file_or_dump_io':io_refs,
        'calls_with_name_suggesting_isp_register_api':register_refs,
        'actual_image_buffer_abi_proven':False,
        'original_ccm_isolated_pixel_readback_proven':False,
    }


def direct_caller_inventory(elf, byaddr, byname, names):
    """Read only direct BL candidates in original .text; never execute code.

    ET_DYN: compare BL computed immediate target to exact VA of named original
    functions. ET_REL: use CALL26 relocations when available. No exhaustive
    indirect-call or out-of-module reachability claims.
    """
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    from elftools.elf.relocation import RelocationSection
    target_addresses={name:byname[name][0] for name in names}
    records={name:Counter() for name in names}
    if elf['e_type']=='ET_REL':
        tidx=elf.get_section_index('.text')
        require(tidx is not None,'no_original_text_section')
        for relsection in elf.iter_sections():
            if not isinstance(relsection,RelocationSection) or int(relsection['sh_info'])!=tidx:continue
            table=elf.get_section(int(relsection['sh_link']))
            for rel in relsection.iter_relocations():
                if int(rel['r_info_type']) not in (R_AARCH64_CALL26,R_AARCH64_JUMP26):continue
                s=table.get_symbol(int(rel['r_info_sym']))
                name=s.name if s.name in records else None
                if name is None and rel.is_RELA() and s['st_info']['type']=='STT_SECTION' and s['st_shndx']==tidx:
                    addr=int(s['st_value'])+int(rel['r_addend'])
                    name=next((n for n,a in target_addresses.items() if a==addr),None)
                if name is not None:records[name][owner_by_start(byaddr,int(rel['r_offset']))]+=1
        mode='original_relocated_text_calls_only'
    else:
        sec=elf.get_section_by_name('.text')
        require(sec is not None and int(sec['sh_size'])<100*1024*1024,'missing_or_oversize_text_section')
        data=sec.data();cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
        found=0
        targets={v:k for k,v in target_addresses.items()}
        for inst in cs.disasm(data,int(sec['sh_addr'])):
            if inst.mnemonic!='bl':continue
            for op in inst.operands:
                if op.type==ARM64_OP_IMM and int(op.imm) in targets:
                    records[targets[int(op.imm)]][owner_by_start(byaddr,inst.address)]+=1
                    found+=1
        mode='original_aarch64_direct_bl_local_candidates'
    result={}
    for name,counts in records.items():
        top=sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))
        result[name]={
            'direct_call_candidate_count':sum(counts.values()),
            'top_named_static_callers':[{'name':k,'callsite_count':v} for k,v in top[:MAX_CALLER_NAMES]],
            'caller_names_truncated':len(top)>MAX_CALLER_NAMES,
            'indirect_callers_excluded':True,
            'actual_runtime_called_or_pixel_domain_proven':False,
        }
    return mode,result


def synthetic():
    samples={
        0x100:[('pp_dump_plane_to_file',0x60,1)],
        0x250:[('caller',0x90,1)],
    }
    assert owner_by_start(samples,0x100)=='pp_dump_plane_to_file'
    assert owner_by_start(samples,0x253)=='caller'
    assert owner_by_start(samples,0x500)=='unresolved_function_owner'
    assert owner_by_start(samples,0x150)=='pp_dump_plane_to_file'
    assert owner_by_start(samples,0x160)=='unresolved_function_owner'
    assert len(TARGETS)==4
    assert all(name in PINS for name in TARGETS)
    assert all(len(v)>=3 for v in TARGETS.values())
    assert MAX_FUNCTION_BYTES>=65536
    assert 'ccm_get_dbg_info_by_mux' not in TARGETS['system/lib/modules/vcam_driver.ko']
    assert R_AARCH64_CALL26==283 and R_AARCH64_JUMP26==282
    assert MAX_DIRECT_CALLEES<=35
    assert sum(len(v) for v in TARGETS.values())==19
    return {'schema':'hasselblad-stage38b-original-oracle-direct-call-synthetic-v1',
            'status':'PASS_synthetic','checks':13,
            'firmware_loaded':False,'pixel_oracle_proven':False,
            'phone_photographic_renderer_unchanged':True}


def inspect(root:Path)->dict:
    from elftools.elf.elffile import ELFFile
    reports={}
    for source,names in TARGETS.items():
        path=root/source
        require(path.is_file() and sha(path)==PINS[source],'wrong_or_missing_original_binary_'+source)
        with path.open('rb') as f:
            elf=ELFFile(f)
            require(elf['e_machine']=='EM_AARCH64' and elf.little_endian,'unexpected_original_elf')
            byname,byaddr,total=collect_symbols(elf)
            mapping,valid=parse_plt(elf)
            routines={}
            for name in names:
                fn=required_symbol(byname,name)
                routines[name]=inspect_calls(elf,fn,byaddr,mapping)
            mode,callers=direct_caller_inventory(elf,byaddr,byname,names)
            for name in routines:routines[name]['reverse_direct_callers']=callers[name]
            reports[source]={
                'sha256':PINS[source],
                'defined_function_symbols_seen':total,
                'plt_import_layout_validated':valid,
                'reverse_callsite_provenance_mode':mode,
                'routines':routines,
                'original_image_or_frame_data_processed_by_this_audit':False,
            }
    return {
        'schema':'hasselblad-stage38b-original-dump-oracle-callers-v1',
        'status':'PASS_original_static_named_callee_caller_audit',
        'exact_original_X2DII_1_3_16_2':True,
        'source_reports':reports,
        'same_stage_pre_post_ccm_RGB_pixels_demonstrated':False,
        'original_six_coefficient_ccm_pixel_arithmetic_recovered':False,
        'vendor_code_instruction_bytes_or_private_tuning_exported':False,
        'saved_photographs_or_production_branch_modified':False,
        'limits':'Direct static CALL26/BL relationships only. No live firmware calls, indirect dispatch closure, or verified pixel-buffer ABI.'
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    d=synthetic() if a.self_test else inspect(a.firmware_root if a.firmware_root is not None else
        (_ for _ in ()).throw(ValueError('original_firmware_root_required')))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':d['status'],
        'original_pixel_oracle_proven':False,
        'routines':{s:{name:{'calls':p['static_direct_call_count'],
                             'called_by':p['reverse_direct_callers']['direct_call_candidate_count'],
                             'callee_names':[x['name'] for x in p['bounded_callee_names'][:8]],
                             'caller_names':[x['name'] for x in p['reverse_direct_callers']['top_named_static_callers'][:8]]}
                       for name,p in z['routines'].items()}
                    for s,z in d.get('source_reports',{}).items()}},sort_keys=True))

if __name__=='__main__':main()