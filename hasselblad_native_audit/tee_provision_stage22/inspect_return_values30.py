#!/usr/bin/env python3
"""X2D II Stage30: post-TEE output-value contract of the second secure TA.

Inspect original host AArch64 code of efuse_pro (command0), pro_state
(command3) and sec_debug_state (command32) without executing any of them.
Find actual reads of TEEC_Operation param0.value.a/b (SP+80/84) after
InvokeCommand and trace simple return/status forwarding. Only structural
evidence is reported; names alone do not establish fuse/key semantics.

No eFuse read/write, camera access, TEE invocation, original instruction
bytes, decompiled code, unknown literal strings, or secrets are exported.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

from trace_efuse_session24 import backing_elf,FILE,SHA
from inspect_efuse_contract27 import CASES

OP_BASE=72
VALUE_A=OP_BASE+8
VALUE_B=OP_BASE+12
MAX_ROWS=28
MAX_INSNS=1200

def scan_load(ins,site):
    from capstone.arm64 import ARM64_OP_MEM,ARM64_OP_REG
    if ins.mnemonic not in ("ldr","ldur","ldp","ldnp","ldrb","ldrh","ldrsw"):
        return []
    ops=ins.operands
    paired=ins.mnemonic in ("ldp","ldnp")
    if paired and len(ops)>=3 and ops[2].type==ARM64_OP_MEM:
        mem=ops[2].mem; dests=ops[:2]
    elif not paired and len(ops)>=2 and ops[1].type==ARM64_OP_MEM:
        mem=ops[1].mem;dests=ops[:1]
    else:return []
    if ins.reg_name(mem.base)!="sp" or mem.index or ins.writeback:return []
    res=[]
    for i,d in enumerate(dests):
        if d.type!=ARM64_OP_REG:continue
        n=ins.reg_name(d.reg)
        width=8 if n.startswith("x") else 4 if n.startswith("w") else None
        if width is None:continue
        off=int(mem.disp)+i*width
        if not (off<=VALUE_B+3 and off+width>VALUE_A):continue
        res.append({"site_va":hex(ins.address),"operation":"stack_load",
                    "destination_register":n,
                    "offset_sp":off,"width_bytes":width,
                    "reads_value_a":off<=VALUE_A<off+width,
                    "reads_value_b":off<=VALUE_B<off+width})
    return res

def scan_store(ins):
    from capstone.arm64 import ARM64_OP_MEM,ARM64_OP_REG
    if ins.mnemonic not in ("str","stur","stp","stnp"):return []
    ops=ins.operands
    paired=ins.mnemonic in ("stp","stnp")
    if paired and len(ops)>=3 and ops[2].type==ARM64_OP_MEM:
        mem=ops[2].mem;srcs=ops[:2]
    elif not paired and len(ops)>=2 and ops[1].type==ARM64_OP_MEM:
        mem=ops[1].mem;srcs=ops[:1]
    else:return []
    if ins.reg_name(mem.base)!="sp" or mem.index or ins.writeback:return []
    res=[]
    for i,s in enumerate(srcs):
        if s.type!=ARM64_OP_REG:continue
        n=ins.reg_name(s.reg)
        width=8 if n.startswith("x") else 4 if n.startswith("w") else None
        if width is None:continue
        off=int(mem.disp)+i*width
        if off<=VALUE_B+3 and off+width>VALUE_A:
            res.append({"site_va":hex(ins.address),"source_register":n,
                        "offset_sp":off,"width_bytes":width})
    return res

def inspect(name,insns,plt,expect):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    if len(insns)>MAX_INSNS:raise ValueError("function_too_long")
    by={i.address:i for i in insns}
    at=expect["invoke"]
    if at not in by or by[at].mnemonic!="bl":raise ValueError("missing_invoke_"+name)
    invoke_idx=next(i for i,x in enumerate(insns) if x.address==at)
    inv=by[at]
    if inv.operands[0].type!=ARM64_OP_IMM or plt.get(int(inv.operands[0].imm))!="TEEC_InvokeCommand":
        raise ValueError("unexpected_original_call_"+name)
    rows=[];post_calls=[];pre_writes=[]
    for idx,ins in enumerate(insns):
        if idx<invoke_idx:pre_writes.extend(scan_store(ins))
        if idx<=invoke_idx:continue
        rows.extend(scan_load(ins,at))
        if ins.mnemonic=="bl" and len(ins.operands)==1 and ins.operands[0].type==ARM64_OP_IMM:
            n=plt.get(int(ins.operands[0].imm))
            if n and n.startswith("TEEC_"):
                post_calls.append({"site_va":hex(ins.address),"api":n})
    returns=[]
    for idx,ins in enumerate(insns):
        if idx<=invoke_idx or ins.mnemonic!="ret":continue
        last=None
        for p in reversed(insns[max(invoke_idx+1,idx-25):idx]):
            if p.mnemonic in ("bl","blr","b","br","ret") or p.mnemonic.startswith(("b.","cb","tb")):
                last={"kind":"crosses_basic_block_or_call"};break
            try:_,writes=p.regs_access()
            except Exception:continue
            if not any(p.reg_name(x) in ("w0","x0") for x in writes):continue
            last={"kind":"register_definition","site_va":hex(p.address),
                  "instruction_class":p.mnemonic}
            if len(p.operands)>1 and p.operands[1].type==ARM64_OP_REG:
                last["source_register"]=p.reg_name(p.operands[1].reg)
            elif len(p.operands)>1 and p.operands[1].type==ARM64_OP_MEM:
                last["memory_base"]=p.reg_name(p.operands[1].mem.base)
                last["memory_offset"]=int(p.operands[1].mem.disp)
            break
        returns.append({"site_va":hex(ins.address),
                        "last_local_return_register_definition":last})
    return {"function":name,"TEE_command_id":expect["command"],
            "original_TEE_InvokeCommand_va":hex(at),
            "operation_param0_value_a_sp":VALUE_A,
            "operation_param0_value_b_sp":VALUE_B,
            "output_value_field_loads_after_InvokeCommand":rows[:MAX_ROWS],
            "post_InvokeCommand_value_load_count":len(rows),
            "pre_InvokeCommand_value_field_scalar_store_candidates":pre_writes[:MAX_ROWS],
            "post_InvokeCommand_TEE_api_calls":post_calls[:16],
            "normal_return_site_candidates":returns[:16],
            "full_control_flow_proof_of_success_or_output_delivery":False}

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("incorrect_original_firmware")
    funcs,plt,_=backing_elf(root/FILE)
    return {"schema":"hasselblad-stage30-original-second-TEE-value-return-contract-v1",
            "original_firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":SHA,
            "functions":[inspect(n,funcs[n],plt,q) for n,q in CASES.items()],
            "known_output_paramTypes_proven_by_Stage27":True,
            "eFuse_or_TEE_executed":False,
            "actual_TBIE_derive_or_key_retrieval_proven":False,
            "original_vendor_disassembly_or_private_data_exported":False}

def synthetic():
    assert VALUE_A==80 and VALUE_B==84
    assert len(CASES)==3
    return {"status":"PASS_synthetic","checks":2,"original_data_loaded":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    res=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(res,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":res.get("status","original_read_only"),
        "post_tee_value_reads":sum(x["post_InvokeCommand_value_load_count"] for x in res.get("functions",[])),
        "TA_decrypted":False},sort_keys=True))
if __name__=="__main__":main()
