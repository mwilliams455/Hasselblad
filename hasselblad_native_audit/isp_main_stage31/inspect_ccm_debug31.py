#!/usr/bin/env python3
"""Stage31 exact X2D II Eagle2 CCM debug-interface capability inventory.

Bounded original ELF inspection. This script inventories instruction classes,
register-memory load/store shapes and debug-mux bounded immediate fields in
identified kernel CCM debug entrypoints. It NEVER executes firmware, publishes
code bytes, IQ tables or outputs claimed RGB samples. A debug getter's name or
scalar load does NOT prove exposure of before-/after-CCM camera pixels.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MODULE_SHA='29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e'
FNS=(
    'ccm_get_dbg_info_by_mux',
    'ccm_set_dbg_mux',
    'ccm_get_dbg_err_info_hsize','ccm_get_dbg_err_info_vsize',
    'ccm_get_dbg_res_cnt_in_hsize','ccm_get_dbg_res_cnt_in_vsize',
    'ccm_get_dbg_res_cnt_prc_hsize','ccm_get_dbg_res_cnt_prc_vsize',
    'ccm_get_dbg_h_busy','ccm_get_dbg_v_busy',
    'ccm_get_dbg_shd_id_rcam','ccm_get_dbg_shd_id_vcam',
    'ccm_set_fmt','ccm_set_fn0_config',
)
REQUIRED=set(FNS)
MAX_BYTES=4096

def require(ok:bool, reason:str):
    if not ok: raise ValueError(reason)

def classify_mem(mnemonic:str):
    if mnemonic.startswith(('ld','prfm')): return 'read'
    if mnemonic.startswith(('st',)): return 'write'
    return 'other'

def summary_mem_records(records:list[tuple[str,str,int,int]]) -> list[dict[str,Any]]:
    # Records (kind, base, displacement, width-in-bits). Preserve only
    # section-relative memory addressing, not raw vendor instructions.
    out=[]
    for (kind,base,disp,width) in sorted(set(records)):
        require(kind in ('read','write','other'),'invalid_kind')
        require(-0x1000000<=disp<=0x1000000,'offset_out_of_bound')
        require(width in (0,8,16,32,64,128),'invalid_width')
        out.append({'access':kind,'base_register':base,
                    'signed_register_relative_offset':disp,'operand_bits':width,
                    'physical_MMIO_offset_proven':False})
    return out

def self_test()->dict[str,Any]:
    require(classify_mem('ldr')=='read','ldr')
    require(classify_mem('ldrb')=='read','ldrb')
    require(classify_mem('str')=='write','str')
    require(classify_mem('stp')=='write','stp')
    require(classify_mem('add')=='other','add')
    regs=summary_mem_records([('read','x0',0x40,32),('read','x0',0x40,32),
                              ('write','x0',0x44,32),('read','sp',-8,64)])
    require(len(regs)==3,'dedup')
    require(all(v['physical_MMIO_offset_proven'] is False for v in regs),'mmio_not_proven')
    require(any(v['signed_register_relative_offset']==0x40 for v in regs),'sorting')
    return {'schema':'stage31-ccm-debug-interface-synthetic-v1',
            'status':'PASS_synthetic', 'checks':8,
            'synthetic_fixture_only':True,'pixel_oracle_proven':False,
            'phone_renderer_modified':False}

def register_bits(ins,register):
    name=ins.reg_name(register)
    if not name:return 0
    if name.startswith(('q','v')):return 128
    if name.startswith('x') or name=='sp':return 64
    if name.startswith('w') or name=='wsp':return 32
    if name.startswith('h'):return 16
    if name.startswith('b'):return 8
    return 0

def inspect(path:Path)->dict[str,Any]:
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_MEM,ARM64_OP_REG,ARM64_OP_IMM
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    with path.open('rb') as f:
        require(hashlib.file_digest(f,'sha256').hexdigest()==MODULE_SHA,'wrong_X2DII_driver')
        f.seek(0)
        elf=ELFFile(f)
        require(elf['e_type']=='ET_REL' and elf['e_machine']=='EM_AARCH64'
                and elf.little_endian and elf.elfclass==64,
                'wrong_original_kernel_elf')
        tidx=elf.get_section_index('.text')
        require(tidx is not None,'missing_text')
        text=elf.get_section(tidx).data()
        sec=elf.get_section_by_name('.symtab')
        require(sec is not None,'missing_symtab')
        syms={}
        for s in sec.iter_symbols():
            if s.name in REQUIRED and s['st_shndx']==tidx and s['st_info']['type']=='STT_FUNC':
                syms.setdefault(s.name,[]).append(s)
        require(set(syms)==REQUIRED,'missing_CCM_debug_function')
        require(all(len(v)==1 for v in syms.values()),'ambiguous_CCM_debug_function')
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        decoder.detail=True
        results={}
        total_instr=0
        for name in FNS:
            s=syms[name][0]
            start=int(s['st_value']);size=int(s['st_size'])
            require(4<=size<=MAX_BYTES and start+size<=len(text),
                    'unexpected_debug_accessor_size_'+name)
            inst=list(decoder.disasm(text[start:start+size],start))
            require(sum(x.size for x in inst)==size,'incomplete_AArch64_function_'+name)
            total_instr+=len(inst)
            mem=[]
            mnemonics=set()
            writes=[]
            vector_count=0
            calls=0
            bitwise_fields=[]
            for i in inst:
                mnemonics.add(i.mnemonic)
                if i.mnemonic in ('bl','blr'):calls+=1
                # A bounded semantic synopsis, not a reconstructed vendor
                # instruction listing. This applies ONLY to the two original
                # CCM debug-mux accessor functions.
                if name in ('ccm_get_dbg_info_by_mux','ccm_set_dbg_mux') and \
                        i.mnemonic in ('ubfx','sbfx','ubfiz','sbfiz','and','orr','lsl','lsr'):
                    imms=[int(o.imm) for o in i.operands if o.type==ARM64_OP_IMM]
                    bitwise_fields.append({'operator':i.mnemonic,
                                           'encoded_constants':imms[:2]})
                for o in i.operands:
                    if o.type==ARM64_OP_REG and register_bits(i,o.reg)==128:
                        vector_count+=1
                    if o.type!=ARM64_OP_MEM:continue
                    base=i.reg_name(o.mem.base)
                    # Pairs also load/write two registers; separate widths in
                    # the JSON would overstate precision, so report operand 0.
                    width=(register_bits(i,i.operands[0].reg)
                           if len(i.operands) and i.operands[0].type==ARM64_OP_REG else 0)
                    kind=classify_mem(i.mnemonic)
                    mem.append((kind,base,int(o.mem.disp),width))
                    if kind=='write':writes.append(int(o.mem.disp))
            results[name]={
                'text_section_start':hex(start), 'function_bytes':size,
                'decoded_instruction_count':len(inst),
                'load_store_records':summary_mem_records(mem),
                'raw_load_store_operand_count':len(mem),
                'register_relative_write_offsets':sorted(set(writes)),
                'decoded_call_instruction_count':calls,
                'debug_mux_bitfield_operations':bitwise_fields,
                'potential_128bit_register_operand_occurrences':vector_count,
                'has_arithmetic_multiply_mnemonic':bool({'mul','madd','smaddl','fmul','fmadd'}&mnemonics),
                'actual_image_samples_or_pixel_math_proven':False,
                'physical_register_meanings_proven':False,
            }
        require(results['ccm_get_dbg_info_by_mux']['decoded_instruction_count']==3,
                'original_debug_mux_getter_shape_changed')
        require(results['ccm_set_dbg_mux']['decoded_instruction_count']==7,
                'original_debug_mux_setter_shape_changed')
        require(results['ccm_get_dbg_info_by_mux']['raw_load_store_operand_count']==1,
                'original_debug_mux_getter_read_shape_changed')
        require(results['ccm_set_dbg_mux']['raw_load_store_operand_count']==2,
                'original_debug_mux_setter_RMW_shape_changed')
        require(all(results[n]['potential_128bit_register_operand_occurrences']==0
                    for n in FNS if 'dbg' in n),
                'unexpected_vector_access_in_original_debug_interface')
        # A scalar debug getter may read hardware status fields; this alone
        # is NOT an oracle for actual input/output RGB of the CCM datapath.
        require(results['ccm_set_fmt']['function_bytes']==80,'CCM_set_fmt_identity_changed')
        require(results['ccm_set_fn0_config']['function_bytes']==92,'CCM_set_fn0_identity_changed')
        return {
            'schema':'stage31-X2DII1_3_16_2-CCM-debug-interface-v1',
            'status':'PASS_exact_driver_debug_accessor_inventory',
            'original_module_sha256':MODULE_SHA,
            'original_firmware':'X2D II 100C 1.3.16.2',
            'debug_accessor_count':sum('dbg' in x for x in FNS),
            'total_functions_checked':len(FNS),
            'total_decoded_instructions':total_instr,
            'functions':results,
            'proven_pixel_input_RGB_readback':False,
            'proven_pixel_output_RGB_readback':False,
            'hardware_debug_mux_semantics_recovered':False,
            'original_debug_mux_scalar_read_write_rmw_shape_verified':True,
            'CCM_debug_getter_is_a_multiframe_RGB_stream_proven':False,
            'six_coefficient_pixel_equation_recovered':False,
            'vendor_instruction_bytes_exported':False,
            'vendor_coefficients_exported':False,
            'vendor_firmware_uploaded':False,
            'Android_saved_photo_renderer_modified':False,
            'limits':[
                'Static memory operands are relative to decoded registers, not proven hardware MMIO offsets.',
                'Function names describe intended usage but are not a verified per-pixel colour contract.',
                'No actual camera, ISP or hardware debug port is operated by this tool.',
                'No user photo, firmware bytes, IQ values or original instruction sequences are exported.',
                'Pixel sample readback requires independent hardware register contract and live proof.'
            ],
        }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--module',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=self_test() if a.self_test else inspect(a.module if a.module else
        (_ for _ in ()).throw(ValueError('exact_module_required')))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
