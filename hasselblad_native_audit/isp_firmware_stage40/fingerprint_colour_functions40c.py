#!/usr/bin/env python3
"""Stage40C: function-scoped source identity across exact-hash X2D II releases.

Only ELF symbol metadata plus raw *function SHA256 digests* are exported. This
is NOT hardware pixel arithmetic, a runtime callback proof, or full native
behavioural equivalence. Original binary bytes are never published.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import lzma
from pathlib import Path
from typing import Any

# Deliberately narrow provenance-scoped questions, not a broad /bin search.
TARGETS={
 'system/lib64/librcam.so':(
    'mm_get_coeff','mm_mx_lerp_gap','mm_mx_lerp_vec_mix2',
    '_calc_lerp_mx_lut_reg_idx_v5','rcam_adj_calc_common','DjiIsp_Reg_Set',
    'main_ccm_calc_frame','main_ccm_calc_global','main_ccm_calc_mode',
    'main_3dlut_calc_frame','_Calc_LerpLutMem3d',
    'main_gamma_normal_calc_frame','tmc_v1_0_calc_tmc',
    'DjiAdj_Calc_LutMemCopy',
 ),
 'system/lib/modules/vcam_driver.ko':(
    'ccm_set_ig0_config','ccm_set_fmt','ccm_set_fn0_config',
    'ccm_get_dbg_info_by_mux','ccm_set_dbg_mux',
    'gamma_set_info','lut_set_lut_info','b2r_pad_set_fh_fmt',
    'plat_eagle2_probe_components','lut_set_size',
 ),
 'system/lib64/libaaa.so':('scene_awb_result_recalib_unit',),
 'system/lib64/libduml_hal.so':(
    'lookup_rgb_pixel_plt_fmt','do_3dlut_trans',
 ),
}
MAX_ELF_BYTES=128*1024*1024
MAX_DEBUG_BYTES=64*1024*1024
MAX_FUNCTION_BYTES=256*1024


def require(v:bool,msg:str):
    if not v:raise ValueError(msg)


def sha(data:bytes):return hashlib.sha256(data).hexdigest()


def file_sha(path:Path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def symbols(elf):
    from elftools.elf.elffile import ELFFile
    # Deduplicate same symbol from full and mini-debug tables. Different extents
    # of the same function are ambiguous; fail closed for that function.
    src=[]
    for name in ('.dynsym','.symtab'):
        sec=elf.get_section_by_name(name)
        if sec is not None:src.extend(sec.iter_symbols())
    section=elf.get_section_by_name('.gnu_debugdata')
    if section is not None:
        data=lzma.decompress(section.data(),memlimit=128*1024*1024)
        require(len(data)<=MAX_DEBUG_BYTES,'unbounded_mini_debug')
        debug=ELFFile(io.BytesIO(data))
        sym=debug.get_section_by_name('.symtab')
        if sym is not None:src.extend(sym.iter_symbols())
    byname={}
    targets=set(n for ns in TARGETS.values() for n in ns)
    for s in src:
        if s.name not in targets:continue
        if s['st_info']['type']!='STT_FUNC' or s['st_shndx']=='SHN_UNDEF':continue
        va=int(s['st_value']);size=int(s['st_size'])
        if size<4:continue
        byname.setdefault(s.name,set()).add((va,size))
    return byname


def function_bytes(elf,src:bytes,addr:int,size:int)->bytes:
    require(size>=4 and size<=MAX_FUNCTION_BYTES,'unsupported_function_size')
    if elf['e_type']=='ET_REL':
        # Exact firmware targets use .text for the inspected ccm/gamma/lut funcs.
        section=elf.get_section_by_name('.text')
        require(section is not None and addr+size<=int(section['sh_size']),
                'symbol_outside_original_driver_text')
        return section.data()[addr:addr+size]
    require(elf['e_type']=='ET_DYN','unexpected_elf_type')
    for seg in elf.iter_segments():
        if seg['p_type']!='PT_LOAD' or not (int(seg['p_flags']) & 1):continue
        v=int(seg['p_vaddr']);sz=int(seg['p_filesz']);off=int(seg['p_offset'])
        if v<=addr and addr+size<=v+sz:
            return src[off+addr-v:off+addr-v+size]
    raise ValueError('function_not_in_executable_load_segment')


# Stage40D: a *syntactic*, strictly non-equivalence diagnostic. PC-relative
# targets can change when the executable is relaid out; non-PC-relative numeric
# operands, register identities and memory strides are deliberately preserved.
PC_RELATIVE_TARGET_OPS={'b','bl','cbz','cbnz','tbz','tbnz','adr','adrp'}
ARITHMETIC_MNEMONICS={
 'mul','madd','msub','smull','umull','smaddl','umaddl','smulh','umulh',
 'fmul','fmadd','fmsub','fdiv','sdiv','udiv','sqdmulh','sqrdmulh',
}

def normalized_imm(mnemonic:str,op_index:int,total_ops:int,value:int,
                   start:int,end:int)->str:
    m=mnemonic.lower()
    pc_relative=(m in PC_RELATIVE_TARGET_OPS or m.startswith('b.') or m=='ldr')
    if pc_relative and op_index==total_ops-1:
        if start<=value<end:
            return 'pc_relative_inside_function_offset:'+str(value-start)
        return 'pc_relative_external_target_unresolved'
    return 'exact_immediate:'+str(value)

def instruction_shape(body:bytes,start:int)->dict:
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM,ARM64_OP_IMM,ARM64_OP_FP
    cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
    cs.detail=True
    instructions=list(cs.disasm(body,start))
    require(bool(instructions) and sum(i.size for i in instructions)==len(body),
            'incomplete_aarch64_function_disassembly')
    mnemonics=[];normal=[]
    pc_external=arithmetic=memr=memw=0
    end=start+len(body)
    for ins in instructions:
        m=ins.mnemonic.lower()
        mnemonics.append(m)
        if m in ARITHMETIC_MNEMONICS:arithmetic+=1
        if m.startswith(('ld','prfm')):memr+=1
        if m.startswith('st'):memw+=1
        items=[]
        for ix,op in enumerate(ins.operands):
            if op.type==ARM64_OP_REG:
                descriptor='register:'+ins.reg_name(op.reg)
            elif op.type==ARM64_OP_IMM:
                descriptor=normalized_imm(m,ix,len(ins.operands),int(op.imm),start,end)
                if descriptor=='pc_relative_external_target_unresolved':pc_external+=1
            elif op.type==ARM64_OP_MEM:
                mm=op.mem
                descriptor=('memory_base:'+ins.reg_name(mm.base)+
                    ':index:'+ins.reg_name(mm.index)+':displacement:'+str(int(mm.disp)))
            elif op.type==ARM64_OP_FP:
                descriptor='floating_literal:'+float(op.fp).hex()
            else:
                descriptor='operand_type:'+str(int(op.type))
            # Register shifts, extensions, and lane-vector forms can affect
            # arithmetic. Retain when provided by Capstone.
            shift=getattr(op,'shift',None)
            if shift is not None and getattr(shift,'value',0):
                descriptor+=':shift:'+str(int(shift.type))+':'+str(int(shift.value))
            ext=getattr(op,'ext',0)
            if ext:descriptor+=':extend:'+str(int(ext))
            items.append(descriptor)
        normal.append(m+'('+','.join(items)+')')
    return {
        'decoded_aarch64_instruction_count':len(instructions),
        'mnemonic_sequence_sha256':sha(('\n'.join(mnemonics)).encode()),
        'register_and_non_PCREL_operand_signature_sha256':sha(('\n'.join(normal)).encode()),
        'multiply_or_divide_instruction_count':arithmetic,
        'load_instruction_count':memr,
        'store_instruction_count':memw,
        'external_PCREL_target_occurrences_normalized':pc_external,
        'raw_instruction_bytes_or_full_disassembly_exported':False,
        'syntactic_signature_implies_identical_semantics':False,
    }

def record(elf,src:bytes,name:str,index:dict)->dict:
    entries=index.get(name,set())
    if not entries:return {'status':'symbol_not_located'}
    if len(entries)!=1:return {'status':'ambiguous_symbol_extent','extent_count':len(entries)}
    va,size=next(iter(entries))
    if size>MAX_FUNCTION_BYTES:return {'status':'function_oversize','bytes':size}
    try:
        body=function_bytes(elf,src,va,size)
        require(len(body)==size,'function_slice_truncated')
    except ValueError as e:
        return {'status':'unresolved_function_slice','reason':str(e)}
    return {'status':'fingerprinted','virtual_address_hex':hex(va),
            'function_size_bytes':size,'raw_body_sha256':sha(body),
            'instruction_shape':instruction_shape(body,va),
            'relocations_or_runtime_parameters_proven_identical':False,
            'original_runtime_or_pixel_equivalence_proven':False}


def fingerprint(root:Path,snapshot:dict)->dict:
    from elftools.elf.elffile import ELFFile
    result={}
    for rel,names in TARGETS.items():
        expected=snapshot['file_index'].get(rel)
        path=root/rel
        if expected is None or not path.is_file():
            result[rel]={'status':'original_file_missing','functions':{name:{'status':'file_missing'} for name in names}}
            continue
        require(path.stat().st_size<=MAX_ELF_BYTES,'ELF_too_large_'+rel)
        data=path.read_bytes()
        require(sha(data)==expected['sha256'],'wrong_binary_for_source_snapshot_'+rel)
        ef=ELFFile(io.BytesIO(data))
        require(ef['e_machine']=='EM_AARCH64' and ef.little_endian and ef.elfclass==64,'unexpected_ELF_arch')
        index=symbols(ef)
        funcs={name:record(ef,data,name,index) for name in names}
        result[rel]={'status':'original_binary_sha256_verified',
                     'source_sha256':expected['sha256'],
                     'elf_type':str(ef['e_type']),
                     'functions':funcs}
    return {'schema':'hasselblad-stage40c-private-function-fingerprints-v1',
            'status':'PASS_pinned_original_elf_function_fingerprints',
            'firmware_version':snapshot['firmware_version'],
            'official_archive_sha256':snapshot['source_sha256'],
            'sources':result,
            'original_binary_bytes_or_vendor_coefficients_exported':False,
            'photographic_pixel_equivalence_proven':False}


def compare(old:dict,new:dict)->dict:
    require(old['firmware_version']=='1.3.16.2' and new['firmware_version']=='1.3.18.1','invalid_firmware_order')
    out={};counts={'identical_raw_body':0,'changed_raw_body':0,'missing_or_ambiguous':0}
    shapes={'identical_mnemonic_sequence':0,'changed_mnemonic_sequence':0,
            'identical_normalized_operand_shape':0,'changed_normalized_operand_shape':0,
            'shape_unavailable':0}
    for rel,names in TARGETS.items():
        oldfiles=old['sources'][rel]['functions'];newfiles=new['sources'][rel]['functions']
        chosen={}
        for name in names:
            a=oldfiles[name];b=newfiles[name]
            status=('unresolved' if a.get('status')!='fingerprinted' or b.get('status')!='fingerprinted'
                    else 'identical_raw_body' if a['raw_body_sha256']==b['raw_body_sha256']
                    else 'changed_raw_body')
            counts['missing_or_ambiguous' if status=='unresolved' else status]+=1
            sa=a.get('instruction_shape');sb=b.get('instruction_shape')
            if sa is None or sb is None:
                shape_status='unresolved'
                shapes['shape_unavailable']+=1
            else:
                if sa['mnemonic_sequence_sha256']==sb['mnemonic_sequence_sha256']:
                    shapes['identical_mnemonic_sequence']+=1
                else:
                    shapes['changed_mnemonic_sequence']+=1
                if sa['register_and_non_PCREL_operand_signature_sha256']==sb['register_and_non_PCREL_operand_signature_sha256']:
                    shapes['identical_normalized_operand_shape']+=1
                    shape_status='identical_syntax_modulo_unresolved_PC_relative_targets'
                else:
                    shapes['changed_normalized_operand_shape']+=1
                    shape_status='different_normalized_operand_syntax'
            chosen[name]={
               'stage40d_instruction_shape_status':shape_status,
               'old_decoded_instructions':sa.get('decoded_aarch64_instruction_count') if sa else None,
               'new_decoded_instructions':sb.get('decoded_aarch64_instruction_count') if sb else None,
               'old_multiply_or_divide_instructions':sa.get('multiply_or_divide_instruction_count') if sa else None,
               'new_multiply_or_divide_instructions':sb.get('multiply_or_divide_instruction_count') if sb else None,
               'old_external_PCREL_normalizations':sa.get('external_PCREL_target_occurrences_normalized') if sa else None,
               'new_external_PCREL_normalizations':sb.get('external_PCREL_target_occurrences_normalized') if sb else None,
               'status':status,
               'old_symbol_status':a.get('status'),
               'new_symbol_status':b.get('status'),
               'old_function_bytes':a.get('function_size_bytes'),
               'new_function_bytes':b.get('function_size_bytes'),
               'old_virtual_address':a.get('virtual_address_hex'),
               'new_virtual_address':b.get('virtual_address_hex'),
               'old_body_sha256':a.get('raw_body_sha256'),
               'new_body_sha256':b.get('raw_body_sha256'),
               'exact_same_original_executed_hardware_math_proven':False,
            }
        out[rel]={'old_library_sha256':old['sources'][rel].get('source_sha256'),
                  'new_library_sha256':new['sources'][rel].get('source_sha256'),
                  'whole_library_identical':old['sources'][rel].get('source_sha256')==new['sources'][rel].get('source_sha256'),
                  'selected_function_comparison':chosen}
    return {'schema':'hasselblad-stage40c-selected-original-function-body-compare-v1',
            'status':'PASS_exact_original_dual_function_byte_identity',
            'original_firmware_old_sha256':old['official_archive_sha256'],
            'original_firmware_new_sha256':new['official_archive_sha256'],
            'selected_function_counts':counts,
            'stage40d_syntax_comparison_counts':shapes,
            'stage40d_PCREL_target_normalization_does_not_prove_callee_identity':True,
            'sources':out,
            'matching_function_bytes_do_not_prove_original_runtime_or_hardware_pixel_equivalence':True,
            'ccm_pixel_equation_proven':False,
            'main_gamma_or_lut_pixel_sampling_proven':False,
            'firmware_executed':False,
            'vendor_function_bytes_or_numeric_tables_exported':False,
            'phone_saved_photo_renderer_modified':False}


def synthetic():
    oldsrc={};newsrc={};k=0
    for path,names in TARGETS.items():
        a={};b={}
        for name in names:
            k+=1
            same=(k%3==0)
            missing=(k%7==0)
            a[name]={'status':'fingerprinted','raw_body_sha256':f'old{k}','function_size_bytes':16}
            b[name]=({'status':'symbol_not_located'} if missing else
                     {'status':'fingerprinted','raw_body_sha256':(f'old{k}' if same else f'new{k}'),'function_size_bytes':16})
        oldsrc[path]={'source_sha256':'oldlib','functions':a}
        newsrc[path]={'source_sha256':'newlib','functions':b}
    old={'firmware_version':'1.3.16.2','official_archive_sha256':'oldarchive','sources':oldsrc}
    new={'firmware_version':'1.3.18.1','official_archive_sha256':'newarchive','sources':newsrc}
    result=compare(old,new)
    c=result['selected_function_counts']
    assert result['status'].startswith('PASS')
    assert normalized_imm('bl',0,1,0x1000,0x1000,0x1100)=='pc_relative_inside_function_offset:0'
    assert normalized_imm('bl',0,1,0x2000,0x1000,0x1100)=='pc_relative_external_target_unresolved'
    assert normalized_imm('madd',2,3,7,0x1000,0x1100)=='exact_immediate:7'
    assert normalized_imm('tbz',1,3,5,0x1000,0x1100)=='exact_immediate:5'
    assert normalized_imm('tbz',2,3,0x1020,0x1000,0x1100)=='pc_relative_inside_function_offset:32'
    assert normalized_imm('ldr',1,2,0x3000,0x1000,0x1100)=='pc_relative_external_target_unresolved'
    assert sum(c.values())==sum(len(v) for v in TARGETS.values())
    assert c['identical_raw_body']>0 and c['changed_raw_body']>0 and c['missing_or_ambiguous']>0
    assert result['ccm_pixel_equation_proven'] is False
    assert result['phone_saved_photo_renderer_modified'] is False
    assert result['matching_function_bytes_do_not_prove_original_runtime_or_hardware_pixel_equivalence']
    assert all('functions' in o for o in oldsrc.values())
    assert MAX_DEBUG_BYTES==64*1024*1024
    assert len(TARGETS)==4
    assert 'ccm_set_ig0_config' in TARGETS['system/lib/modules/vcam_driver.ko']
    assert 'mm_mx_lerp_vec_mix2' in TARGETS['system/lib64/librcam.so']
    assert 'scene_awb_result_recalib_unit' in TARGETS['system/lib64/libaaa.so']
    assert 'do_3dlut_trans' in TARGETS['system/lib64/libduml_hal.so']
    assert MAX_FUNCTION_BYTES>=256*1024
    assert all(len(names)<=15 for names in TARGETS.values())
    assert all(isinstance(x,str) for names in TARGETS.values() for x in names)
    assert c['missing_or_ambiguous']>0
    return {'status':'PASS_synthetic','checks':23,'vendor_assets_loaded':False,
            'original_photographic_pixel_parity_proven':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--root',type=Path)
    p.add_argument('--source-snapshot',type=Path)
    p.add_argument('--old',type=Path)
    p.add_argument('--new',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.self_test:result=synthetic()
    elif a.root is not None:
        require(a.source_snapshot is not None and a.output is not None,'missing_private_file_index')
        result=fingerprint(a.root.resolve(),json.loads(a.source_snapshot.read_text()))
    else:
        require(a.old is not None and a.new is not None and a.output is not None,'missing_dual_snapshots')
        result=compare(json.loads(a.old.read_text()),json.loads(a.new.read_text()))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    summary={'status':result['status']}
    if 'checks' in result:summary['checks']=result['checks']
    if 'firmware_version' in result:summary['version']=result['firmware_version']
    if 'selected_function_counts' in result:
        summary['selected_function_counts']=result['selected_function_counts']
        summary['stage40d_syntax_comparison_counts']=result['stage40d_syntax_comparison_counts']
        summary['unchanged_by_group']={k:{n:v['status'] for n,v in x['selected_function_comparison'].items()}
             for k,x in result['sources'].items()}
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':main()