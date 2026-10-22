#!/usr/bin/env python3
"""Stage29C: identify original B2R frame-record pointer/field relationships.

Only a hash-pinned AArch64 kernel is inspected as inert ELF data. V4L2's
standard subdev record is an independent C-ABI candidate, NOT an established
X2D struct. Do not export camera data or vendor instruction sequences.
"""
from __future__ import annotations
import argparse, ctypes, hashlib, json
from collections import Counter
from pathlib import Path

DRIVER_SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
B2R_NAME="b2r_pad_set_fh_fmt"
B2R_SIZE=912
CCM_CALL=0x6d598
RECORD_ASSIGN=0x6d314
CCM_ARG1_LOAD=0x6d58c
CCM_ARG2_LOAD=0x6d594

def check(ok, why):
    if not ok:raise ValueError(why)

def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def public_v4l2_candidate():
    # Only the public UAPI prefix is modeled. It does not identify the X2D
    # vendor's original type unless separately supported by original code.
    class FramePrefix(ctypes.Structure):
        _fields_=[("width",ctypes.c_uint32),("height",ctypes.c_uint32)]
    class SubdevPrefix(ctypes.Structure):
        _fields_=[("which",ctypes.c_uint32),("pad",ctypes.c_uint32),("format",FramePrefix)]
    w=SubdevPrefix.format.offset+FramePrefix.width.offset
    h=SubdevPrefix.format.offset+FramePrefix.height.offset
    check((w,h)==(8,12),"public_abi_prefix_unexpected")
    return {"standard_V4L2_subdev_format_width_offset":w,
            "standard_V4L2_subdev_format_height_offset":h,
            "X2D_function_record_proven_to_have_this_type":False}

def self_test():
    a=public_v4l2_candidate()
    check(a["standard_V4L2_subdev_format_width_offset"]==8,"candidate_width")
    check(a["standard_V4L2_subdev_format_height_offset"]==12,"candidate_height")
    check(a["X2D_function_record_proven_to_have_this_type"] is False,"candidate_mislabeled")
    return {"schema":"stage29c-b2r-layout-synthetic-v1","status":"PASS_synthetic",
            "candidate_layout_tests":3,"candidate_layout":a,
            "original_firmware_inspected":False,
            "original_CCM_pixel_equation_proven":False}

def inspect(path):
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_MEM,ARM64_OP_REG
    check(sha(path)==DRIVER_SHA,"wrong_X2D_original_kernel_driver")
    with path.open("rb") as stream:
        elf=ELFFile(stream)
        check(elf["e_type"]=="ET_REL" and elf["e_machine"]=="EM_AARCH64"
              and elf.elfclass==64 and elf.little_endian,"unexpected_kernel_ELF")
        tidx=elf.get_section_index(".text")
        check(tidx is not None,"missing_text")
        s=elf.get_section_by_name(".symtab")
        check(s is not None,"missing_symtab")
        symbols=list(s.iter_symbols())
        targets=[a for a in symbols if a.name==B2R_NAME and a["st_shndx"]==tidx]
        check(len(targets)==1,"missing_or_ambiguous_B2R")
        start,size=(int(targets[0]["st_value"]),int(targets[0]["st_size"]))
        check(size==B2R_SIZE and start<=RECORD_ASSIGN<start+size
              and start<=CCM_CALL<start+size,"unexpected_B2R_identity")
        text=elf.get_section(tidx).data()
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        md.detail=True
        ins=list(md.disasm(text[start:start+size],start))
        by_at={i.address:i for i in ins}
        check(len(ins)==size//4 and all(x in by_at for x in
              (RECORD_ASSIGN,CCM_ARG1_LOAD,CCM_ARG2_LOAD,CCM_CALL)),
              "B2R_instruction_layout_changed")
        mov=by_at[RECORD_ASSIGN]
        check(mov.mnemonic=="mov" and len(mov.operands)==2 and
              all(o.type==ARM64_OP_REG for o in mov.operands) and
              md.reg_name(mov.operands[0].reg)=="x19" and
              md.reg_name(mov.operands[1].reg)=="x1", "record_pointer_provenance_changed")
        # This is a bounded instruction-order property, not a full CFG proof.
        before=[i for i in ins if i.address<RECORD_ASSIGN]
        check(not any(md.reg_name(reg) in ("x1","w1")
                      for i in before for reg in i.regs_access()[1]),
              "input_x1_modified_before_record_binding")
        def exact_load(at,reg,disp):
            instr=by_at[at]
            check(instr.mnemonic in ("ldr","ldur") and
                  instr.operands[0].type==ARM64_OP_REG and
                  md.reg_name(instr.operands[0].reg)==reg,"expected_word_load_changed")
            mem=[o for o in instr.operands if o.type==ARM64_OP_MEM]
            check(len(mem)==1 and md.reg_name(mem[0].mem.base)=="x19" and
                  mem[0].mem.disp==disp,"input_record_field_offset_changed")
        exact_load(CCM_ARG1_LOAD,"w1",8)
        exact_load(CCM_ARG2_LOAD,"w2",12)
        record_fields=[]
        for instr in ins:
            for o in instr.operands:
                if o.type==ARM64_OP_MEM and md.reg_name(o.mem.base)=="x19":
                    kind="read" if instr.mnemonic.startswith("ld") else (
                         "write" if instr.mnemonic.startswith("st") else "other")
                    record_fields.append((o.mem.disp,kind))
        fields={str(off):dict(Counter(kind for v,kind in record_fields if v==off))
                for off in sorted(set(v for v,_ in record_fields))}
        # Search both named and .text section+addend references. No inference
        # that every reference represents a callable V4L2 subdev operation.
        incoming=[]
        for sec in elf.iter_sections():
            if not isinstance(sec,RelocationSection):continue
            src=elf.get_section(int(sec["sh_info"]))
            symtab=elf.get_section(int(sec["sh_link"]))
            for rel in sec.iter_relocations():
                target=symtab.get_symbol(int(rel["r_info_sym"]))
                match=target.name==B2R_NAME
                if not match and rel.is_RELA() and target["st_shndx"]==tidx:
                    match=(int(target["st_value"])+int(rel["r_addend"])==start)
                if match:
                    incoming.append({"section":src.name,
                          "source_offset_hex":hex(int(rel["r_offset"])),
                          "relocation_type":int(rel["r_info_type"]),
                          "named_symbol_reference":target.name==B2R_NAME})
        incoming.sort(key=lambda e:(e["section"],e["source_offset_hex"]))
        return {
          "schema":"stage29c-X2DII-original-B2R-record-fields-v1",
          "status":"PASS_original_B2R_record_pointer_and_field_reads",
          "source_sha256":DRIVER_SHA,"B2R_start_offset_hex":hex(start),
          "B2R_pointer_x19_bound_to_entry_x1_at_hex":hex(RECORD_ASSIGN),
          "entry_x1_unchanged_before_pointer_binding":True,
          "CCM_argument_1_word32_from_record_offset":8,
          "CCM_argument_2_word32_from_record_offset":12,
          "B2R_record_memory_field_access_classes":fields,
          "B2R_incoming_relocation_metadata":incoming,
          "public_V4L2_subdev_format_layout_candidate":public_v4l2_candidate(),
          "X2D_vendor_record_type_identified":False,
          "format_fields_proven_to_be_dimensions":False,
          "CCM_colour_encoding_or_Q_scale_proven":False,
          "six_coefficient_pixel_equation_proven":False,
          "original_camera_frames_processed":False,
          "vendor_instruction_bytes_exported":False,
          "vendor_tuning_values_exported":False,
          "Android_saved_photo_renderer_changed":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--module",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    r=self_test() if a.self_test else inspect(a.module if a.module else
                            (_ for _ in ()).throw(ValueError("original_kernel_module_required")))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print(json.dumps(r,sort_keys=True))

if __name__=="__main__":main()
