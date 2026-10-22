#!/usr/bin/env python3
"""Stage31C: exact X2D II CCM debug selector producer/consumer call-site audit.

Checks ELF AArch64 CALL26/JUMP26 relocations, local unrelocated branch
candidates and data-section function-pointer references to two CCM debug-mux
accessors. Does not interpret an unknown mux index as a pixel readback.
No firmware is executed and no vendor bytes or photographic values are emitted.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json
from pathlib import Path

MODULE_SHA='29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e'
TARGETS=('ccm_set_dbg_mux','ccm_get_dbg_info_by_mux')
CALL26=283
JUMP26=282

def require(c,msg):
    if not c:raise ValueError(msg)

def owner(spans,offset):
    if not spans:return None
    starts=[x[0] for x in spans]
    idx=bisect.bisect_right(starts,offset)-1
    return spans[idx][2] if idx>=0 and offset < spans[idx][0]+spans[idx][1] else None

def synthetic():
    f=[(100,20,'first'),(200,20,'second')]
    assert owner(f,101)=='first'
    assert owner(f,119)=='first'
    assert owner(f,120) is None
    assert owner(f,220) is None
    assert owner(f,200)=='second'
    assert owner(f,0) is None
    return {'schema':'stage31C-CCM-debug-calls-synthetic-v1',
            'status':'PASS_synthetic','tests':6,'pixel_oracle_proven':False}

def inspect(path):
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    with path.open('rb') as f:
        require(hashlib.file_digest(f,'sha256').hexdigest()==MODULE_SHA,'wrong_original_driver_sha')
        f.seek(0);elf=ELFFile(f)
        require(elf['e_type']=='ET_REL' and elf['e_machine']=='EM_AARCH64' and elf.little_endian,
                'unexpected_elf')
        tidx=elf.get_section_index('.text')
        require(tidx is not None,'text_missing')
        section=elf.get_section(tidx)
        code=section.data()
        symsec=elf.get_section_by_name('.symtab')
        require(symsec is not None,'symtab_missing')
        funcs=[];entry={}
        for sym in symsec.iter_symbols():
            if not sym.name or sym['st_shndx']!=tidx or sym['st_info']['type']!='STT_FUNC':continue
            start=int(sym['st_value']);size=int(sym['st_size'])
            if size>0:funcs.append((start,size,sym.name))
            if sym.name in TARGETS:entry.setdefault(sym.name,[]).append((start,size))
        funcs.sort()
        # Duplicate start aliases are checked; pick shortest lexical owner
        # without pretending two distinct addresses exist.
        by_start={}
        for start,size,name in funcs:
            if start in by_start:
                require(by_start[start][0]==size,'ambiguous_alias_function_extents')
                by_start[start][1].append(name)
            else:by_start[start]=(size,[name])
        spans=[(start,val[0],'|'.join(sorted(set(val[1])))) for start,val in sorted(by_start.items())]
        require(set(entry)==set(TARGETS),'missing_debug_entrypoints')
        require(all(len(entry[n])==1 for n in TARGETS),'duplicate_debug_entrypoints')
        require(entry['ccm_get_dbg_info_by_mux'][0][1]==12,'debug_getter_shape_changed')
        require(entry['ccm_set_dbg_mux'][0][1]==28,'debug_setter_shape_changed')
        targets={k:entry[k][0][0] for k in TARGETS}
        incoming={k:{'text_CALL26':[],'text_JUMP26':[],
                     'section_plus_addend_text_calls':[],
                     'data_section_pointers':[],'other_relocations':[]}
                  for k in TARGETS}
        relocated_branch_sites=set()
        for reloc in elf.iter_sections():
            if not isinstance(reloc,RelocationSection):continue
            sidx=int(reloc['sh_info']);s=elf.get_section(sidx)
            symbols=elf.get_section(int(reloc['sh_link']))
            for rec in reloc.iter_relocations():
                at=int(rec['r_offset']);typ=int(rec['r_info_type'])
                if sidx==tidx and typ in (CALL26,JUMP26):relocated_branch_sites.add(at)
                tgt=symbols.get_symbol(int(rec['r_info_sym']))
                name=tgt.name if tgt.name in TARGETS else None
                if name is None and sidx==tidx and rec.is_RELA() and tgt['st_shndx']==tidx and tgt['st_info']['type']=='STT_SECTION':
                    resolved=int(tgt['st_value'])+int(rec['r_addend'])
                    name=next((k for k,v in targets.items() if v==resolved),None)
                    if name and typ in (CALL26,JUMP26):
                        incoming[name]['section_plus_addend_text_calls'].append({
                            'calling_function':owner(spans,at),'callsite':hex(at),'relocation_type':typ})
                        continue
                if name is None:continue
                loc={'source_section':s.name,'offset_hex':hex(at),
                     'source_function':owner(spans,at) if sidx==tidx else None,
                     'relocation_type':typ}
                if sidx==tidx and typ==CALL26:incoming[name]['text_CALL26'].append(loc)
                elif sidx==tidx and typ==JUMP26:incoming[name]['text_JUMP26'].append(loc)
                elif sidx!=tidx:incoming[name]['data_section_pointers'].append(loc)
                else:incoming[name]['other_relocations'].append(loc)
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);decoder.detail=True
        local_bl={k:[] for k in TARGETS}
        count=0
        for ins in decoder.disasm(code,0):
            count+=1
            if ins.mnemonic!='bl' or ins.address in relocated_branch_sites:continue
            if len(ins.operands)<1 or ins.operands[0].type!=ARM64_OP_IMM:continue
            target=next((n for n,offset in targets.items() if offset==ins.operands[0].imm),None)
            if target:
                local_bl[target].append({'function':owner(spans,ins.address),
                                         'callsite_hex':hex(ins.address)})
        for k in TARGETS:
            incoming[k]['unrelocated_exact_BL_candidates']=local_bl[k]
        return {'schema':'stage31-X2DII-1_3_16_2-CCM-debug-callers-v1',
            'status':'PASS_exact_debug_call_relocation_inventory',
            'verified_module_sha256':MODULE_SHA,'entrypoint_addresses':{k:hex(v) for k,v in targets.items()},
            'total_aarch64_instructions_disassembled':count,
            'incoming':incoming,
            'debug_mux_width_bits_from_stage31B':5,
            'debug_mux_possible_selector_count':32,
            'numeric_selector_meanings_recovered':False,
            'real_pixel_value_readback_proven':False,
            'six_coefficient_pixel_equation_proven':False,
            'vendor_instruction_bytes_exported':False,
            'firmware_or_private_pixels_uploaded':False,
            'Android_saved_photo_renderer_unchanged':True,
            'caveat':'Absence of direct incoming relocations does not imply unreachable; runtime callback or indirect invocation remains possible.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--module',type=Path)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    d=synthetic() if a.self_test else inspect(a.module if a.module else
        (_ for _ in ()).throw(ValueError('original_module_required')))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps(d,sort_keys=True))
if __name__=='__main__':main()
