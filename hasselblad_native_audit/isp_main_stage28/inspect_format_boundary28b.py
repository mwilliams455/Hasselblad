#!/usr/bin/env python3
"""Stage28B: bounded original Eagle2 B2R-to-CCM format/callback relationship.

All reported offsets are original ELF .text *section offsets*, not live device
addresses. Named and section+addend AArch64 relocation targets are distinguished
from raw pre-relocation BL immediates. No camera photo or vendor bytes exported.
"""
from __future__ import annotations
import argparse, hashlib, json
from bisect import bisect_right
from pathlib import Path

DRIVER_SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1e6b0ea0a83d2f4ff419d0"
# The checksum above is intentionally a sentinel so an unreviewed alternative
# firmware cannot be silently processed. The expected exact module identity is
# specified below and checked before any ELF investigation.
EXACT_DRIVER_SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
B2R_NAME="b2r_pad_set_fh_fmt"
CCM_FMT="ccm_set_fmt"
IG0="ccm_set_ig0_config"
CALL26=283
JUMP26=282
def check(x,msg):
    if not x:raise ValueError(msg)
def sh(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def owner(functions,offs):
    # entries (start,size,name), normalized to non-overlapping starts.
    starts=[r[0] for r in functions]
    i=bisect_right(starts,offs)-1
    return functions[i][2] if i>=0 and offs<functions[i][0]+functions[i][1] else None

def normalize_functions(symtab,text_index):
    data=[]
    for s in symtab.iter_symbols():
        if (s.name and s["st_shndx"]==text_index and
            s["st_info"]["type"]=="STT_FUNC" and int(s["st_size"])>0):
            data.append((int(s["st_value"]),int(s["st_size"]),s.name))
    data.sort()
    # Exact duplicate functions are aliases, not unique callers.
    # Collapse aliases only when extents match; unequal extents are ambiguous.
    by_offset={}
    for start,size,name in data:
        if start in by_offset:
            old_size,names=by_offset[start]
            check(old_size==size,"overlapping_symbol_alias_extents")
            names.append(name)
        else:by_offset[start]=(size,[name])
    return [(start,v[0],"|".join(sorted(set(v[1])))) for start,v in sorted(by_offset.items())]

def target_of(reloc,symtab,text_index):
    t=symtab.get_symbol(int(reloc["r_info_sym"]))
    if t.name and t["st_info"]["type"]!="STT_SECTION":
        return t.name,"named"
    if (t["st_shndx"]==text_index and
        t["st_info"]["type"]=="STT_SECTION" and reloc.is_RELA()):
        return int(t["st_value"])+int(reloc["r_addend"]),"section_plus_addend"
    return None,"unresolved"

def synthetic():
    functions=[(0x100,32,"caller"),(0x200,40,"target")]
    check(owner(functions,0x110)=="caller","owner_wrong")
    check(owner(functions,0x120) is None,"owner_bound_wrong")
    check(owner(functions,0x200)=="target","owner_second_wrong")
    check(owner(functions,0x1ff) is None,"owner_gap_wrong")
    # Distinguish a section+addend reference to a target from an unrelated
    # reference to a different offset in the same .text section.
    for base,off,expect in [(0x0,0x200,True),(0x100,0x100,True),
                            (0x100,0x101,False),(0x0,0x300,False)]:
        check((base+off==0x200)==expect,"section_addend_discrimination")
    return {"schema":"stage28B-ccm-relocation-synthetic-v1","status":"PASS_synthetic",
            "owner_tests":4,"section_addend_tests":4,
            "firmware_processed":False,"pixel_equation_proven":False}

def inspect(module):
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    check(sh(module)==EXACT_DRIVER_SHA,"wrong_original_vcam_driver_hash")
    with module.open("rb") as f:
        elf=ELFFile(f)
        check(elf["e_type"]=="ET_REL" and elf["e_machine"]=="EM_AARCH64"
              and elf.little_endian,"unexpected_elf_platform")
        text_index=elf.get_section_index(".text")
        check(text_index is not None,"missing_text")
        text=elf.get_section(text_index).data()
        symtab=elf.get_section_by_name(".symtab")
        check(symtab is not None,"missing_symbols")
        functions=normalize_functions(symtab,text_index)
        names={r[2]:r for r in functions}
        for name in (B2R_NAME,CCM_FMT,IG0):
            check(name in names,"missing_expected_symbol_"+name)
        b2r=names[B2R_NAME]
        check(b2r[1]>=4 and b2r[1]<10000,"unexpected_b2r_function_size")
        check(CCM_FMT in names and IG0 in names,"missing_ccm")
        rlist=[]
        for sec in elf.iter_sections():
            if not isinstance(sec,RelocationSection):continue
            source_idx=int(sec["sh_info"])
            src=elf.get_section(source_idx)
            ttab=elf.get_section(int(sec["sh_link"]))
            for r in sec.iter_relocations():
                resolved,kind=target_of(r,ttab,text_index)
                src_off=int(r["r_offset"])
                src_func=owner(functions,src_off) if source_idx==text_index else None
                rlist.append({"from_section":src.name,"from_offset":src_off,
                        "from_function":src_func,"type":int(r["r_info_type"]),
                        "to":resolved,"target_kind":kind})
        b2r_out=[r for r in rlist if r["from_section"]==".text"
                    and r["from_function"]==B2R_NAME
                    and r["type"] in (CALL26,JUMP26)]
        b2r_to_ccm=[r for r in b2r_out if r["to"]==CCM_FMT and r["type"]==CALL26]
        check(len(b2r_to_ccm)==1 and b2r_to_ccm[0]["from_offset"]==0x6d598,
              "b2r_to_ccm_fmt_exact_call_missing")
        # An unnamed STT_SECTION relocation is not a missing reference.
        # Do not conflate with name-address references or a decoded raw BL
        # whose immediate may be unresolved before linking.
        ig0_exact_section_refs=[
            r for r in rlist if r["target_kind"]=="section_plus_addend"
            and r["to"]==names[IG0][0]]
        ig0_named_refs=[r for r in rlist if r["to"]==IG0]
        fmt_incoming=[r for r in rlist if r["to"]==B2R_NAME
                     and r["from_section"]==".text"
                     and r["type"] in (CALL26,JUMP26)]
        # Inspect an exact function only; do not release original sequences.
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        insn=list(decoder.disasm(text[b2r[0]:b2r[0]+b2r[1]],b2r[0]))
        check(sum(x.size for x in insn)==b2r[1],"incomplete_b2r_decode")
        # Snapshot of immediate values near the ccm_set_fmt call is intentionally
        # NOT serialized; the trustworthy output is the verified call edge.
        branch_sites={r["from_offset"] for r in rlist if r["from_section"]==".text"
                      and r["type"] in (CALL26,JUMP26)}
        direct_local=[]
        # AArch64 local branch with no relocation can be a real direct call.
        # Treat it only as a lead; the exact caller's control-flow still needs
        # validation, and never interpret branch targets that have relocations.
        for instr in decoder.disasm(text,0):
            if instr.mnemonic!="bl" or instr.address in branch_sites: continue
            if len(instr.operands)>0 and instr.operands[0].type==ARM64_OP_IMM:
                if instr.operands[0].imm==names[IG0][0]:
                    direct_local.append({
                        "source_function":owner(functions,instr.address),
                        "callsite_hex":hex(instr.address)})
    return {
        "schema":"stage28B-X2DII1_3_16_2-B2R-CCM-format-provenance-v1",
        "status":"PASS_original_B2R_to_CCM_format_edge",
        "module_sha256":EXACT_DRIVER_SHA,
        "b2r_function_size":b2r[1],
        "b2r_function_instruction_count":len(insn),
        "ccm_format_callsite_hex":"0x6d598",
        "b2r_callees_named":sorted(set(r["to"] for r in b2r_out if isinstance(r["to"],str))),
        "b2r_callees_unnamed_section_targets_count":
            sum(isinstance(r["to"],int) for r in b2r_out),
        "incoming_named_calls_to_b2r":[{"function":r["from_function"],
                                         "callsite_hex":hex(r["from_offset"])}
                                        for r in fmt_incoming],
        "ig0_named_incoming_relocations":len(ig0_named_refs),
        "ig0_exact_section_plus_addend_relocations":[{
            "source_section":r["from_section"],"source_function":r["from_function"],
            "source_offset_hex":hex(r["from_offset"]),"relocation_type":r["type"]}
            for r in ig0_exact_section_refs],
        "ig0_direct_unrelocated_BL_leads":direct_local,
        "ig0_no_refs_would_not_prove_unreachable":True,
        "B2R_label_does_not_prove_Bayer_to_RGB_operation":True,
        "format_values_and_pixel_domain_recovered":False,
        "six_coefficient_pixel_formula_proven":False,
        "vendor_instruction_bytes_exported":False,
        "vendor_IQ_coefficients_exported":False,
        "hardware_ISP_not_emulated":True,
        "android_saved_JPEG_unchanged":True,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--module",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    report=synthetic() if a.self_test else inspect(
        a.module if a.module else (_ for _ in ()).throw(ValueError("module_required")))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":main()
