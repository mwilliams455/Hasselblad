#!/usr/bin/env python3
"""Stage37B: exact original X2D II named MAIN CCM function call provenance.

Looks up direct ARM64 BL targets and bounded symbol/API relationships for the
three Stage37A-nominated `main_ccm_calc_*` functions. No pixel code executed,
no instructions or vendor coefficient values emitted. Calls are path-insensitive.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
import lzma
from pathlib import Path

from inspect_main_ccm_cpu37 import PIN, MAX_FUNC_BYTES, MAX_DEBUG_UNCOMPRESSED, require, code_slice, Function

LIB_PATH="system/lib64/librcam.so"
SOURCES=("main_ccm_calc_frame","main_ccm_calc_global","main_ccm_calc_mode")
EXPECTED=("DIQ_iq_main_ccm_lmtx_fw","_calc_lerp_mx_lut_reg_idx_v5")
MAX_CALLS=300
MAX_DIRECT_TARGET_NAMES=45


def collect_names(elf):
    """Only symbol names/addresses. Never extract source code or vendor records."""
    from elftools.elf.elffile import ELFFile
    names={}
    num=0
    for tab in (elf.get_section_by_name('.dynsym'), elf.get_section_by_name('.symtab')):
        if tab is None:continue
        for s in tab.iter_symbols():
            num+=1
            if s.name and s['st_shndx']!='SHN_UNDEF' and s['st_info']['type']=='STT_FUNC':
                va=int(s['st_value']);size=int(s['st_size'])
                if size>=4:
                    names.setdefault(va,[]).append((s.name,size,s['st_shndx']))
    mini=elf.get_section_by_name('.gnu_debugdata')
    if mini is not None:
        raw=lzma.decompress(mini.data(),memlimit=MAX_DEBUG_UNCOMPRESSED*4)
        require(len(raw)<=MAX_DEBUG_UNCOMPRESSED,'oversize_mini_debugdata')
        mini_elf=ELFFile(io.BytesIO(raw))
        tab=mini_elf.get_section_by_name('.symtab')
        if tab is not None:
            for s in tab.iter_symbols():
                num+=1
                if s.name and s['st_shndx']!='SHN_UNDEF' and s['st_info']['type']=='STT_FUNC':
                    va=int(s['st_value']);size=int(s['st_size'])
                    if size>=4:names.setdefault(va,[]).append((s.name,size,s['st_shndx']))
    # Prefer largest matching function and deterministic string name, but reject
    # ambiguity at the *three named target* entry points below.
    lookup={k:sorted(set(v),key=lambda a:(-a[1],a[0])) for k,v in names.items()}
    return lookup,num


def plt_imports(elf):
    """AArch64 SysV .plt: 32-byte header and 16-byte stubs; fail closed if layout differs."""
    from elftools.elf.relocation import RelocationSection
    plt=elf.get_section_by_name('.plt')
    rela=elf.get_section_by_name('.rela.plt')
    if not plt or not rela or not isinstance(rela,RelocationSection):
        return {},False
    refs=list(rela.iter_relocations())
    start=int(plt['sh_addr']); size=int(plt['sh_size'])
    if size!=32+16*len(refs):
        return {},False
    symtab=elf.get_section(int(rela['sh_link']))
    if symtab is None:return {},False
    result={}
    for n,reloc in enumerate(refs):
        name=symtab.get_symbol(int(reloc['r_info_sym'])).name
        if name:result[start+32+16*n]=name
    return result,True


def select_target(by_addr,name):
    matches=[]
    for addr,rows in by_addr.items():
        for sym,sz,shndx in rows:
            if sym==name:matches.append((addr,sz,shndx))
    matches=sorted(set(matches),key=lambda x:(x[0],x[1]))
    require(len(matches)==1,'absent_or_ambiguous_original_target_'+name)
    require(4<=matches[0][1]<=MAX_FUNC_BYTES,'unsupported_original_size_'+name)
    return matches[0]


def read_calls(elf,fn,by_addr,plt_map):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
    cs.detail=True
    code=code_slice(elf,fn)
    inst=list(cs.disasm(code,fn.addr))
    require(sum(i.size for i in inst)==fn.size,'partial_disassembly')
    direct=Counter(); indirect=0; total=0
    for i in inst:
        if i.mnemonic=='blr':
            indirect+=1;total+=1
        elif i.mnemonic=='bl':
            total+=1
            destinations=[int(o.imm) for o in i.operands if o.type==ARM64_OP_IMM]
            require(len(destinations)==1,'unexpected_bl_target')
            at=destinations[0]
            if at in plt_map:name='plt:'+plt_map[at]
            elif at in by_addr:name='local:'+by_addr[at][0][0]
            else:name='unresolved_local_target'
            direct[name]+=1
    require(total<=MAX_CALLS,'oversized_original_call_count')
    # direct counts only; not necessarily reached in a particular camera mode.
    top=sorted(direct.items(),key=lambda p:(-p[1],p[0]))
    return dict(function_bytes=fn.size,decoded_instructions=len(inst),
                direct_call_instructions=sum(direct.values()),indirect_call_instructions=indirect,
                named_call_target_count=sum(1 for name,v in direct.items() if name!='unresolved_local_target'),
                resolved_callee_names=[{"name":name,"callsite_count":n} for name,n in top[:MAX_DIRECT_TARGET_NAMES]],
                targets_export_truncated=len(top)>MAX_DIRECT_TARGET_NAMES,
                calls_to_main_ccm_named_functions=sum(v for name,v in direct.items() if 'main_ccm' in name),
                calls_to_parameter_or_register_apis=sum(v for name,v in direct.items() if any(x in name.lower() for x in ('djiisp_reg_set','_calc_lerp_','diq_'))),
                pixel_memory_abi_proven=False,
                original_ccm_pixel_operation_proven=False)


def synthetic():
    by={0x100:[('main_ccm_calc_frame',64,1)],0x200:[('dummy',64,1)]}
    assert select_target(by,'main_ccm_calc_frame')==(0x100,64,1)
    assert 'x' not in (n for n,sz,_ in by[0x100])
    assert sorted(by)==[0x100,0x200]
    assert len(SOURCES)==3
    assert len(EXPECTED)==2
    assert LIB_PATH in PIN
    assert all(x.startswith('main_ccm_') for x in SOURCES)
    assert MAX_DIRECT_TARGET_NAMES<MAX_CALLS
    assert sorted(set(SOURCES))==sorted(SOURCES)
    assert 'lmtx_fw' in EXPECTED[0]
    return {'status':'PASS_synthetic','checks':10,'firmware_loaded':False,
            'original_pixel_equation_proven':False}


def original(path:Path):
    from elftools.elf.elffile import ELFFile
    require(path.exists() and path.is_file(),'missing_firmware_elf')
    with path.open('rb') as f:
        require(hashlib.file_digest(f,'sha256').hexdigest()==PIN[LIB_PATH],'wrong_librcam_sha256')
        f.seek(0)
        elf=ELFFile(f)
        require(elf['e_machine']=='EM_AARCH64' and elf.little_endian and elf['e_type']=='ET_DYN','unexpected_elf')
        symbols,entries=collect_names(elf)
        for required in EXPECTED:select_target(symbols,required)
        mapping,plt_proven=plt_imports(elf)
        reports={}
        for name in SOURCES:
            addr,size,section=select_target(symbols,name)
            reports[name]=read_calls(elf,Function(name,addr,size,section,100),symbols,mapping)
        return {'schema':'hasselblad-stage37b-original-main-ccm-call-provenance-v1',
                'status':'PASS_exact_original_named_callsite_audit',
                'original_librcam_sha256':PIN[LIB_PATH],
                'symbol_table_entries_considered':entries,
                'aarch64_plt_ordinal_mapping_proven':plt_proven,
                'named_sources':reports,
                'control_plane_vs_pixel_disambiguation':'not yet demonstrated: callsites and matched symbol names require per-buffer dataflow/ABI proof',
                'actual_original_isp_ccm_pixel_equation_recovered':False,
                'pixel_domain_or_qscale_or_clipping_proven':False,
                'vendor_ELF_or_disassembly_or_calibration_exported':False,
                'phone_photographic_output_changed':False,
                'important_limit':'BL calls are a static may-call inventory; PLT name mapping is conditional on exact layout; unresolved or indirect paths are not excluded.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    d=synthetic() if a.self_test else original((a.firmware_root if a.firmware_root else
      (_ for _ in ()).throw(ValueError('firmware_root_required')))/LIB_PATH)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':d['status'],
        'original_pixel_equation_proven':False,
        'sources':{n:{'call_sites':v['direct_call_instructions'],
                      'called_colour_named_functions':v['calls_to_main_ccm_named_functions'],
                      'call_parameter_register_apis':v['calls_to_parameter_or_register_apis'],
                      'target_names':v['resolved_callee_names']}
                   for n,v in d.get('named_sources',{}).items()}}))

if __name__=='__main__':main()