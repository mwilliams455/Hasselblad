#!/usr/bin/env python3
"""Stage10: original X2D II cbz-x8 dispatch provenance, read-only.

Resolve *why* plt_fw_verify_file chooses the command-6 init path rather than
command-3. All observations are bounded static normal-world AArch64 facts.
No original bytes, pseudocode, disassembly or proprietary literals exported.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SOURCE="system/lib64/libfw_util.so"
SHA="3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d"
WRAPPER="plt_fw_verify_file"
BRANCH=0x1dd0
GUARD=0x1d94

def norm(reg):
    if reg.startswith(("w","x")) and reg[1:].isdigit():
        return "r"+str(int(reg[1:]))
    return reg

def reg_name(ins,op):
    return norm(ins.reg_name(op.reg))

def src_operand(ins,op):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    if op.type==ARM64_OP_REG:return {"type":"register","name":reg_name(ins,op)}
    if op.type==ARM64_OP_IMM:
        v=int(op.imm)
        return {"type":"literal","value":v if -1<=v<=65535 else "large_or_address"}
    if op.type==ARM64_OP_MEM:
        return {"type":"memory","base":norm(ins.reg_name(op.mem.base)),
                "index":norm(ins.reg_name(op.mem.index)) if op.mem.index else None,
                "displacement":int(op.mem.disp)}
    return {"type":"other"}

def unwind_sp(insns):
    """Recognise common prologue SP adjustments, refuse unknown writeback."""
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    sp=0; frame=None; certain=True; rows={}
    for ins in insns:
        rows[ins.address]={"sp_relative_to_entry":sp if certain else None,
                           "fp_relative_to_entry":frame if certain else None}
        ops=ins.operands
        if ins.mnemonic in ("add","sub") and len(ops)>=3 and ops[0].type==ARM64_OP_REG and reg_name(ins,ops[0])=="sp":
            if ops[1].type==ARM64_OP_REG and reg_name(ins,ops[1])=="sp" and ops[2].type==ARM64_OP_IMM:
                sp+=(1 if ins.mnemonic=="add" else -1)*int(ops[2].imm)
            else:certain=False
        elif ins.mnemonic=="mov" and len(ops)>=2 and ops[0].type==ARM64_OP_REG:
            if reg_name(ins,ops[0])=="r29" and ops[1].type==ARM64_OP_REG and reg_name(ins,ops[1])=="sp":
                frame=sp if certain else None
            elif reg_name(ins,ops[0])=="sp" and ops[1].type==ARM64_OP_REG:
                certain=False
        elif ins.writeback:
            mem=[x for x in ops if x.type==ARM64_OP_MEM and norm(ins.reg_name(x.mem.base))=="sp"]
            if mem:
                if "!" in ins.op_str:sp+=int(mem[-1].mem.disp)
                else:
                    # A post-index writeback may use a subsequent literal.
                    if ops[-1].type==ARM64_OP_IMM:sp+=int(ops[-1].imm)
                    else:certain=False
        # Other changes to SP invalidate stack-argument inference.
    return rows,certain

def locate_writer(insns,index,reg):
    """A64 def-use, caller-saved barrier; no CFG dataflow, explicitly bounded."""
    from capstone.arm64 import ARM64_OP_REG
    for j in range(index-1,-1,-1):
        ins=insns[j]
        if ins.mnemonic in ("bl","blr") and (reg.startswith("r") and
                                             int(reg[1:])<19):
            return {"kind":"caller_saved_call_boundary","call_va":hex(ins.address)}
        try:_,writes=ins.regs_access()
        except Exception:continue
        if not any(norm(ins.reg_name(w))==reg for w in writes):
            continue
        if ins.operands and ins.operands[0].type==ARM64_OP_REG and reg_name(ins,ins.operands[0])==reg:
            ret={"kind":"direct_definition","instruction_class":ins.mnemonic,
                 "site_va":hex(ins.address),"index":j}
            if len(ins.operands)>1:ret["operand"]=src_operand(ins,ins.operands[1])
            return ret
        return {"kind":"implicit_or_unclassified_write","site_va":hex(ins.address)}
    if reg.startswith("r") and reg[1:].isdigit() and int(reg[1:])<=7:
        return {"kind":"incoming_abi_register","reg":reg}
    return {"kind":"no_in_function_definition","reg":reg}

def trace_reg(insns,index,reg,stack_rows,depth=0,seen=None):
    if seen is None:seen=set()
    key=(index,reg)
    if key in seen or depth>=7:return {"kind":"alias_budget_or_cycle"}
    seen.add(key)
    w=locate_writer(insns,index,reg)
    if w["kind"]!="direct_definition":return w
    ins=insns[w["index"]]
    out={"kind":"direct_definition","site_va":w["site_va"],
         "instruction_class":w["instruction_class"]}
    second=w.get("operand")
    if second:out["input"]=second
    # Trace most common move aliases to their original ABI registers.
    if ins.mnemonic in ("mov","movz") and second:
        if second["type"]=="register":
            r=second["name"]
            if r in ("xzr","wzr"):out["origin"]={"kind":"literal","value":0}
            else:out["origin"]=trace_reg(insns,w["index"],r,stack_rows,depth+1,seen)
        elif second["type"]=="literal":
            out["origin"]=second
    # A memory read may be a stack argument when its address refers to entry SP.
    if ins.mnemonic in ("ldr","ldur","ldrsw","ldrb","ldrh") and second and second["type"]=="memory":
        base=second["base"];disp=second["displacement"]
        row=stack_rows.get(ins.address,{})
        base_delta=row.get("sp_relative_to_entry") if base=="sp" else (
            row.get("fp_relative_to_entry") if base=="r29" else None)
        if base_delta is not None and second.get("index") is None:
            absolute=base_delta+disp
            out["entry_sp_displacement"]=absolute
            if absolute>=0 and absolute%8==0:
                out["incoming_stack_argument_index"]=8+absolute//8
                out["stack_arg_inference_requires_stable_sp_prologue"]=True
        elif base.startswith("r"):
            out["pointer_base_origin"]=trace_reg(insns,w["index"],base,stack_rows,depth+1,seen)
    if ins.mnemonic in ("add","sub") and second and second["type"]=="register":
        out["base_origin"]=trace_reg(insns,w["index"],second["name"],stack_rows,depth+1,seen)
    return out

def audit(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_REG
    from elftools.elf.elffile import ELFFile
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:
        raise ValueError("unexpected_original_X2DII_hash")
    with path.open("rb") as stream:
        elf=ELFFile(stream)
        syms=elf.get_section_by_name(".dynsym")
        found=[s for s in syms.iter_symbols() if s.name==WRAPPER and s["st_shndx"]!="SHN_UNDEF"]
        if len(found)!=1:raise ValueError("unexpected_wrapper_symbol_count")
        entry,size=int(found[0]["st_value"]),int(found[0]["st_size"])
        code=elf.get_section_by_name(".text")
        off=entry-int(code["sh_addr"])
        if size>4096 or off<0 or off+size>int(code["sh_size"]):
            raise ValueError("wrapper_bounds_failed")
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);md.detail=True
        insns=list(md.disasm(code.data()[off:off+size],entry))
    if len(insns)*4!=size:raise ValueError("unexpected_instruction_gap")
    candidates={ins.address:i for i,ins in enumerate(insns)}
    if BRANCH not in candidates or GUARD not in candidates:
        raise ValueError("original_branches_not_present")
    branch=insns[candidates[BRANCH]]
    guard=insns[candidates[GUARD]]
    if branch.mnemonic!="cbz" or guard.mnemonic!="cbz":
        raise ValueError("original_branch_op_changed")
    if not branch.operands or branch.operands[0].type!=ARM64_OP_REG or reg_name(branch,branch.operands[0])!="r8":
        raise ValueError("x8_test_mismatch")
    rows,stable=unwind_sp(insns[:candidates[BRANCH]+1])
    main=trace_reg(insns,candidates[BRANCH],"r8",rows)
    g_reg=reg_name(guard,guard.operands[0])
    guard_rows,_=unwind_sp(insns[:candidates[GUARD]+1])
    g=trace_reg(insns,candidates[GUARD],g_reg,guard_rows)
    return {"schema":"hasselblad-stage10-original-command6-branch-input-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "source":SOURCE,"source_sha256":SHA,
            "branch_site_va":hex(BRANCH),"branch_test":"cbz x8",
            "command6_when_branch_not_taken":True,
            "command3_when_branch_taken":True,
            "x8_provenance":main,
            "early_guard":{"site_va":hex(GUARD),"test_reg":g_reg,"provenance":g},
            "stack_delta_static_single_path":stable,
            "general_interprocedural_equivalence_proven":False,
            "original_executable_code_run":False,
            "vendor_bytes_or_instruction_text_exported":False,
            "secure_world_key_or_plaintext_recovered":False}

def selftest():
    assert norm("w8")==norm("x8")=="r8"
    assert norm("sp")=="sp"
    assert SHA.endswith("e24d")
    return {"status":"PASS_synthetic","checks":3,"original_firmware_used":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=selftest() if a.self_test else audit(a.firmware_root/SOURCE)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","static_original_verified"),
       "x8_provenance_kind":d.get("x8_provenance",{}).get("kind"),
       "stack_prologue_stable":d.get("stack_delta_static_single_path"),
       "secure_world_key_recovered":False},sort_keys=True))

if __name__=="__main__":main()
