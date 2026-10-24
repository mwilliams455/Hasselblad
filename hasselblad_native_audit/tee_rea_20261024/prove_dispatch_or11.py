#!/usr/bin/env python3
"""Stage11: prove both sources of the original X2D II command-6 ORR predicate.

Restricted to exact original hash-pinned libfw_util.so and exact instruction sites.
No vendor disassembly, encrypted firmware, unknown strings, secrets, or photo bytes
are emitted. Static register provenance is scoped to the wrapper and guards.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SRC="system/lib64/libfw_util.so"
SHA="3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d"
WRAPPER="plt_fw_verify_file"
OR_SITE=0x1dcc
BR_SITE=0x1dd0

def reg(ins,op):
    return ins.reg_name(op.reg)

def one_original(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_REG
    from elftools.elf.elffile import ELFFile
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:
        raise ValueError("unexpected_original_elf_hash")
    with path.open("rb") as fh:
        elf=ELFFile(fh)
        sym=elf.get_section_by_name(".dynsym")
        funcs=[s for s in sym.iter_symbols() if s.name==WRAPPER and s["st_shndx"]!="SHN_UNDEF"]
        if len(funcs)!=1:raise ValueError("original_wrapper_symbol")
        start,length=int(funcs[0]["st_value"]),int(funcs[0]["st_size"])
        text=elf.get_section_by_name(".text")
        off=start-int(text["sh_addr"])
        if off<0 or length>4096:raise ValueError("range")
        dis=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);dis.detail=True
        insns=list(dis.disasm(text.data()[off:off+length],start))
    byaddr={i.address:i for i in insns}
    if OR_SITE not in byaddr or BR_SITE not in byaddr:
        raise ValueError("exact_original_instruction_missing")
    ins=byaddr[OR_SITE];nxt=byaddr[BR_SITE]
    if ins.mnemonic!="orr" or len(ins.operands)!=3 or nxt.mnemonic!="cbz":
        raise ValueError("original_dispatch_shape_changed")
    if any(op.type!=ARM64_OP_REG for op in ins.operands):
        raise ValueError("nonregister_ORR_has_different_proof")
    dst,left,right=[reg(ins,op) for op in ins.operands]
    if dst!="x8" or reg(nxt,nxt.operands[0])!="x8":
        raise ValueError("ORR_to_branch_connection_changed")
    shift_kind=int(getattr(ins.operands[-1].shift,"type",0))
    shift_bits=int(getattr(ins.operands[-1].shift,"value",0))
    srcs=[]
    for rr in (left,right):
        preceding=[]
        for older in insns:
            if older.address>=OR_SITE:break
            try:_,writes=older.regs_access()
            except Exception:continue
            if not any(older.reg_name(w)==rr for w in writes):continue
            preceding.append(older)
        if not preceding:
            srcs.append({"register":rr,"origin":"not_defined_locally"})
            continue
        old=preceding[-1]
        row={"register":rr,"last_definition_va":hex(old.address),
             "last_definition_class":old.mnemonic,
             "number_of_definitions_before_ORR":len(preceding)}
        if old.mnemonic=="mov" and len(old.operands)>1 and old.operands[1].type==ARM64_OP_REG:
            row["immediate_source_reg"]=reg(old,old.operands[1])
            row["origin_is_incoming_argument"]=row["immediate_source_reg"] in ("x5","x7","x0","x1","x2","x3","x4","x6")
        else:row["origin_is_incoming_argument"]=False
        srcs.append(row)
    distinct_args=sorted(x.get("immediate_source_reg") for x in srcs
                         if x.get("origin_is_incoming_argument"))
    exact_or_presence=(shift_kind==0 and shift_bits==0 and set(distinct_args)=={"x5","x7"} and
                       len(distinct_args)==2 and all(x.get("number_of_definitions_before_ORR")==1
                                                  for x in srcs))
    return {"schema":"hasselblad-stage11-original-extended-init-presence-branch-v1",
            "source":SRC,"source_sha256":SHA,
            "or_site_va":hex(OR_SITE),"branch_site_va":hex(BR_SITE),
            "predicate_operation":"ORR","predicate_output_register":"x8",
            "raw_operand_register_names":{"left":left,"right":right},
            "right_shift_type":shift_kind,"right_shift_amount":shift_bits,
            "operands_origin":[{"register":x["register"],"origin_incoming_ABI":x.get("immediate_source_reg"),
                                "last_definition_va":x.get("last_definition_va"),
                                "last_definition_class":x.get("last_definition_class"),
                                "unique_qualified_definition":x.get("number_of_definitions_before_ORR")==1}
                               for x in srcs],
            "extended_when_either_selector_nonnull_locally_proven":exact_or_presence,
            "key_version_controls_extended_branch_proven":False,
            "TEE_execution_or_key_origin_proven":False,
            "vendor_binary_or_disassembly_exported":False}

def synthetic():
    assert bool(0x1|0x0)
    assert not bool(0x0|0x0)
    assert bool(0x0|0x100)
    return {"status":"PASS_synthetic","checks":3,"original_firmware_loaded":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if not a.self_test and not a.firmware_root:ap.error("--firmware-root required")
    d=synthetic() if a.self_test else one_original(a.firmware_root/SRC)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_static_complete"),
         "extended_selection_proven":d.get("extended_when_either_selector_nonnull_locally_proven"),
         "key_or_plaintext_recovered":False},sort_keys=True))
if __name__=="__main__":main()
