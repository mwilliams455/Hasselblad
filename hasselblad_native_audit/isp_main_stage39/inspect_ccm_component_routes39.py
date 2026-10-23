#!/usr/bin/env python3
"""Stage39: exact firmware kernel CCM function-pointer and buffer-route audit.

Read-only static analysis of original vcam_driver.ko. Inspects relocations,
function names and instruction classes. Does not load kernel code or manipulate
MMIO, export firmware instructions or claim a hardware pixel oracle.
"""
from __future__ import annotations
import argparse
import bisect
import hashlib
import json
import re
from collections import Counter,defaultdict
from pathlib import Path

DRIVER_SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
FIRMWARE_SHA="9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6"
LIMIT_BYTES=16384
LIMIT_FUNCTIONS=160
LIMIT_REFS=36
REGEX_NAME=re.compile(r'^[A-Za-z_][A-Za-z_0-9.$]{0,119}$')
REGEX_SECTION=re.compile(r'^[.A-Za-z_][.A-Za-z_0-9.$]{0,119}$')
R_AARCH64_CALL26=283
R_AARCH64_JUMP26=282
R_AARCH64_ABS64=257


def must(c:bool,msg:str):
    if not c: raise ValueError(msg)


def owner(spans, section, at, kind):
    # Using real function/object extents, never the nearest symbol alone.
    items=spans.get((section,kind),())
    if not items: return None
    start=[v[0] for v in items]
    i=bisect.bisect_right(start,at)-1
    for j in range(i,max(-1,i-5),-1):
        a,n,name=items[j]
        if a<=at<a+n:return name
    return None


def is_colour_module_name(name:str)->bool:
    return bool(re.match(r'^(?:ccm_|main_ccm_)',name,re.I))


def api_signal(name:str):
    n=name.lower()
    words=('pixel','readback','frame','capture','dump','dma','vb2','video','mmap','buffer','export','buf','memcpy')
    return [k for k in words if k in n]


def safe_name(s:str):
    return s if isinstance(s,str) and REGEX_NAME.fullmatch(s) else 'redacted_invalid_symbol'


def safe_section(s:str):
    return s if isinstance(s,str) and REGEX_SECTION.fullmatch(s) else 'redacted_invalid_section'


def collect(elf):
    tab=elf.get_section_by_name('.symtab')
    must(tab is not None,'original_symtab_missing')
    sym=[]; spans=defaultdict(list); by_target=defaultdict(set)
    for i,s in enumerate(tab.iter_symbols()):
        sec=s['st_shndx']; nm=s.name
        if not nm or not REGEX_NAME.fullmatch(nm): continue
        if not isinstance(sec,int): continue
        st=int(s['st_value']); sz=int(s['st_size']); typ=s['st_info']['type']
        if typ not in ('STT_FUNC','STT_OBJECT') or sz<1:continue
        # Only originals, no source bytes in metadata.
        rec={'name':nm,'section':sec,'offset':st,'bytes':sz,'type':typ,'symbol_index':i}
        sym.append(rec)
        spans[(sec,typ)].append((st,sz,nm));by_target[(sec,st)].add(nm)
    for k in spans:spans[k].sort(key=lambda x:(x[0],-x[1],x[2]))
    return tab,sym,spans,by_target


def resolved_target(symbol,reloc,sec):
    target_sec=symbol['st_shndx'];val=int(symbol['st_value']);
    if not isinstance(target_sec,int):return None
    if symbol['st_info']['type']=='STT_SECTION' and reloc.is_RELA():
        val+=int(reloc['r_addend'])
    elif reloc.is_RELA() and symbol['st_info']['type'] not in ('STT_SECTION',):
        val+=int(reloc['r_addend'])
    return (target_sec,val)


def analyze(elf, tab, syms, spans, by_target):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM
    from elftools.elf.relocation import RelocationSection
    targets={x['name']:x for x in syms if x['type']=='STT_FUNC' and is_colour_module_name(x['name'])}
    must('ccm_set_ig0_config' in targets and 'ccm_probe' in targets and 'ccm_set_fmt' in targets,
         'missing_exact_original_ccm_anchors')
    must(len(targets)<=LIMIT_FUNCTIONS,'unexpected_ccm_function_population')
    mod=Counter(); bindings=defaultdict(list); direct=defaultdict(Counter); other_section_refs=Counter();
    target_keys={(a['section'],a['offset']):a['name'] for a in targets.values()}
    all_noncall=[]
    reloc_sites=set()
    tex=elf.get_section_index('.text')
    must(tex is not None,'original_text_missing')
    for rsec in elf.iter_sections():
        if not isinstance(rsec,RelocationSection):continue
        secidx=int(rsec['sh_info']);targtab=elf.get_section(int(rsec['sh_link']))
        for r in rsec.iter_relocations():
            typ=int(r['r_info_type']); at=int(r['r_offset']); s=targtab.get_symbol(int(r['r_info_sym']))
            tgt=resolved_target(s,r,secidx)
            if secidx==tex and typ in (R_AARCH64_CALL26,R_AARCH64_JUMP26):reloc_sites.add(at)
            if tgt is None or tgt not in target_keys:continue
            name=target_keys[tgt]
            if secidx==tex and typ in (R_AARCH64_CALL26,R_AARCH64_JUMP26):
                caller=owner(spans,secidx,at,'STT_FUNC') or 'unresolved_caller'
                direct[name][caller]+=1
            else:
                # Distinguish table pointer from code literal relocation.
                containing=owner(spans,secidx,at,'STT_OBJECT') or 'unresolved_object'
                src_section=safe_section(elf.get_section(secidx).name)
                kind='non_text_pointer' if secidx!=tex else 'text_other_relocation'
                mod[kind]+=1
                desc={'from_section':src_section,
                    'from_offset':hex(at),
                    'target_function':safe_name(name),
                    'owner':safe_name(containing),
                    'owner_is_original_object_extent':containing!='unresolved_object',
                    'relocation_kind':typ,
                    'is_known_direct_executable_call':False,
                    'role':'source-side relocation, NOT proven camera pixel callback'}
                bindings[name].append(desc)
                all_noncall.append(desc)
    # Scan only original CCM functions for direct local callsites and memory ops.
    cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
    section=elf.get_section(tex);buf=section.data()
    routines={}
    for name,meta in sorted(targets.items()):
        # Fail closed with explicit skipped metadata if unexpected size.
        if meta['section']!=tex or meta['bytes']>LIMIT_BYTES or meta['offset']+meta['bytes']>len(buf):
            routines[name]={'analyzed':False,'size':meta['bytes'],'skip':'bounded_extent_or_text'}
            continue
        inst=list(cs.disasm(buf[meta['offset']:meta['offset']+meta['bytes']],meta['offset']))
        must(sum(i.size for i in inst)==meta['bytes'],'incomplete_ccm_disassembly_'+name)
        counts=Counter();calls=Counter()
        for i in inst:
            if i.mnemonic in ('bl','blr'):counts[i.mnemonic]+=1
            if i.mnemonic.startswith(('ldr','ldp','ldur','ldaxr')):counts['read']+=1
            if i.mnemonic.startswith(('str','stp','stur','stlxr')):counts['write']+=1
            if i.mnemonic in ('mul','madd','smaddl','fmul','fmadd'):counts['multiply_like']+=1
            if i.mnemonic=='bl' and i.address not in reloc_sites:
                t=[int(o.imm) for o in i.operands if o.type==ARM64_OP_IMM]
                if len(t)==1:
                    nm=target_keys.get((tex,t[0]))
                    if nm: calls[nm]+=1
        routines[name]={'analyzed':True,'bytes':meta['bytes'],
            'instructions':len(inst), 'loads':counts['read'],'stores':counts['write'],
            'local_bl':sum(calls.values()),'blr_count':counts['blr'],
            'multiply_like':counts['multiply_like'],
            'local_ccm_calls':dict(sorted(calls.items())),
            'buffer_or_pixel_math_proven':False}
    anchor=('ccm_probe','ccm_set_ig0_config','ccm_set_fmt','ccm_get_dbg_info_by_mux','ccm_set_dbg_mux')
    details={name:{
        'defined':name in targets,
        'direct_callsite_total':sum(direct[name].values()),
        'direct_callers': [{'name':n,'calls':v} for n,v in direct[name].most_common(LIMIT_REFS)],
        'noncall_relocation_count':len(bindings[name]),
        'candidate_callback_refs': bindings[name][:LIMIT_REFS],
        'readback_or_file_transfer_proven':False,
    } for name in anchor}
    # Exact register/memory caller names in CCM-reachable local code are not a
    # proof of same-frame pixels. Use names for follow-up only.
    return {'schema':'hasselblad-stage39-original-ccm-component-and-callback-audit-v1',
        'status':'PASS_exact_original_component_relocation_inventory',
        'firmware':'X2D II 100C 1.3.16.2', 'original_driver_sha256':DRIVER_SHA,
        'component_function_count':len(targets),
        'all_noncall_references':sorted(all_noncall,key=lambda x:(x['from_section'],x['from_offset'],x['target_function'])),
        'component_functions':routines,
        'selected_function_references':details,
        'all_ccm_noncall_data_pointer_references':sum(len(v) for v in bindings.values()),
        'ccm_referenced_from_other_sections':dict(mod),
        'possible_buffer_related_ccm_names':[n for n in targets if api_signal(n)],
        'live_original_camera_accessed':False,
        'original_ccm_pixel_oracle_proven':False,
        'original_ccm_pixel_equation_proven':False,
        'original_isp_register_controls_modified':False,
        'original_vendor_function_bytes_or_calibration_exported':False,
        'photon_saved_photographs_or_main_modified':False,
        'evidence_boundary':'Direct relocations and local instruction groups in one driver only; memory-mapped inline hardware and indirect callbacks are not exhaustively excluded.'}


def synthetic():
    fake={(1,'STT_FUNC'):[(100,48,'ccm_probe'),(200,24,'ccm_set_fmt')],
          (2,'STT_OBJECT'):[(0x100,32,'ccm_ops'),(0x200,16,'other')]}
    assert owner(fake,1,112,'STT_FUNC')=='ccm_probe'
    assert owner(fake,1,190,'STT_FUNC') is None
    assert owner(fake,1,200,'STT_FUNC')=='ccm_set_fmt'
    assert owner(fake,1,224,'STT_FUNC') is None
    assert owner(fake,2,0x118,'STT_OBJECT')=='ccm_ops'
    assert owner(fake,2,0x300,'STT_OBJECT') is None
    assert is_colour_module_name('ccm_set_ig0_config')
    assert is_colour_module_name('main_ccm_calc_frame')
    assert not is_colour_module_name('not_ccm_debug')
    assert api_signal('ccm_frame_dump')==['frame','dump']
    assert not api_signal('ccm_set_fmt')
    assert safe_name('../secret')=='redacted_invalid_symbol'
    assert R_AARCH64_CALL26==283 and R_AARCH64_ABS64==257
    assert safe_section('.rodata')=='.rodata'
    assert safe_section('.rela.text')=='.rela.text'
    assert safe_section('../secret')=='redacted_invalid_section'
    assert LIMIT_REFS<=36
    return {'schema':'hasselblad-stage39-synthetic-v1','status':'PASS_synthetic',
            'checks':17,'original_firmware_used':False,
            'pixel_oracle_proven':False,'photo_renderer_modified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module',type=Path)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.self_test: d=synthetic()
    else:
        must(a.module is not None and a.module.is_file(),'exact_driver_required')
        with a.module.open('rb') as f:
            must(hashlib.file_digest(f,'sha256').hexdigest()==DRIVER_SHA,'original_driver_sha_mismatch')
        from elftools.elf.elffile import ELFFile
        with a.module.open('rb') as f:
            elf=ELFFile(f)
            must(elf['e_type']=='ET_REL' and elf['e_machine']=='EM_AARCH64','unexpected_original_driver_elf')
            tab,syms,spans,tg=collect(elf)
            d=analyze(elf,tab,syms,spans,tg)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':d['status'], 'synthetic_checks':d.get('checks'),
        'ccm_functions':d.get('component_function_count'),
        'callback_refs':d.get('all_ccm_noncall_data_pointer_references'),
        'candidate_buffer_names':d.get('possible_buffer_related_ccm_names'),
        'original_pixel_oracle_proven':False},sort_keys=True))

if __name__=='__main__':main()