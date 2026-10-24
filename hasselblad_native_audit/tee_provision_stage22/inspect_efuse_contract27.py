#!/usr/bin/env python3
"""X2D II Stage27: independently audit three original second-TA TEE operations.

Original hash-pinned AArch64 libamt_util.so, STATIC ONLY. Recover the command
ID, operation-pointer provenance, candidate TEEC_Operation.paramTypes and
input/output direction; inspect limited structural stack writes and return
status flow. No eFuse/TEE invocation, no hardware writes, no private literal
or plaintext export, and no inference that TBIE key derivation is present.

This does NOT assume a nominally eFuse-related function actually programs
an eFuse; operations must be distinguished by ABI contract and original calls.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from trace_efuse_session24 import backing_elf, FILE, SHA, resolve_source

CASES={
  "efuse_pro":{"invoke":0x2b6c,"command":0},
  "pro_state":{"invoke":0x2ca0,"command":3},
  "sec_debug_state":{"invoke":0x2e0c,"command":32},
}
KIND={0:"NONE",1:"VALUE_INPUT",2:"VALUE_OUTPUT",3:"VALUE_INOUT",
      5:"TEMP_INPUT",6:"TEMP_OUTPUT",7:"TEMP_INOUT",12:"WHOLE",
      13:"PARTIAL_INPUT",14:"PARTIAL_OUTPUT",15:"PARTIAL_INOUT"}
MAX_STACK=512
MAX_STORES=50

def safe_reg(ins,op):
    from capstone.arm64 import ARM64_OP_REG
    return ins.reg_name(op.reg) if op.type==ARM64_OP_REG else None

def stack_stores(insns,before):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM
    rows=[]
    for ix,ins in enumerate(insns):
        if ins.address>=before:break
        if ins.mnemonic not in ("str","stur","stp","stnp"):continue
        ops=ins.operands
        if ins.mnemonic in ("stp","stnp"):
            if len(ops)!=3 or ops[2].type!=ARM64_OP_MEM:continue
            sources=ops[:2];mem=ops[2].mem
        else:
            if len(ops)<2 or ops[1].type!=ARM64_OP_MEM:continue
            sources=ops[:1];mem=ops[1].mem
        if ins.reg_name(mem.base)!="sp" or mem.index or ins.writeback:continue
        offset=int(mem.disp)
        if offset<0 or offset>MAX_STACK:continue
        for n,op in enumerate(sources):
            reg=safe_reg(ins,op)
            if not reg or reg[0] not in "wx":continue
            width=4 if reg.startswith("w") else 8
            row={"va":hex(ins.address),"offset_sp":offset+n*width,
                 "source_register":reg,"width_bytes":width}
            # Original register value can be proprietary; export only small
            # numeric selectors when proven local without an intervening call.
            src=resolve_source(insns,ix,reg)
            if src.get("resolved_small_constant") is not None:
                v=src["resolved_small_constant"]
                if 0<=v<=0xffff:row["small_constant"]=v
            if src.get("kind")=="base_plus_constant" and src.get("stack_based_argument"):
                row["pointer_to_sp_offset"]=src.get("offset")
            rows.append(row)
    return rows[:MAX_STORES]

def target_api(ins,plt):
    from capstone.arm64 import ARM64_OP_IMM
    if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:return None
    return plt.get(int(ins.operands[0].imm))

def decompose(code):
    return [{"index":i,"kind":KIND.get((code>>(4*i))&15,"UNRECOGNISED"),
             "nibble":(code>>(4*i))&15} for i in range(4)]

def examine_case(name,insns,plt,expected):
    matches=[(i,x) for i,x in enumerate(insns) if x.address==expected["invoke"]]
    if len(matches)!=1:raise ValueError("original_invoke_site_missing_"+name)
    ix,inv=matches[0]
    if target_api(inv,plt)!="TEEC_InvokeCommand":
        raise ValueError("actual_original_call_is_not_InvokeCommand_"+name)
    command=resolve_source(insns,ix,"w1")
    if command.get("resolved_small_constant")!=expected["command"]:
        raise ValueError("original_command_value_did_not_match_"+name)
    op=resolve_source(insns,ix,"x2")
    # We first distinguish an absent operation from a stack-backed one. Only
    # then attempt to decode the paramTypes at TEEC_Operation offset +4.
    op_off=op.get("offset") if op.get("stack_based_argument") else None
    absent=op.get("resolved_small_constant")==0
    stores=stack_stores(insns,inv.address)
    candidates=[]
    fields=[]
    if op_off is not None and 0<=op_off<=MAX_STACK-104:
        for s in stores:
            rel=s["offset_sp"]-op_off
            if rel==4 and s["width_bytes"]==4:
                candidates.append(s)
            if 0<=rel<104:
                fields.append({"va":s["va"],"relative_op_offset":rel,
                               "width_bytes":s["width_bytes"],
                               "is_candidate_paramTypes":rel==4,
                               "has_proven_small_constant":"small_constant" in s,
                               "small_constant":s.get("small_constant") if rel==4 else None,
                               "is_stack_pointer":s.get("pointer_to_sp_offset") is not None})
    value=candidates[0].get("small_constant") if len(candidates)==1 else None
    return {"function":name,"original_invoke_va":hex(inv.address),
            "verified_command_id":expected["command"],
            "operation_argument_provenance":op,
            "operation_pointer_is_null_proven":bool(absent),
            "operation_pointer_stack_offset":op_off,
            "all_direct_stack_writes_before_call_count":len(stores),
            "paramtypes_write_candidates":candidates[:8],
            "static_single_paramtypes_constant":value,
            "decoded_TEE_param_types":decompose(value) if value is not None else None,
            "operation_local_field_store_candidates":fields[:38],
            "operation_layout_structural_not_runtime_proven":True,
            "TEE_operation_memory_directions_proven_only_if_constant":value is not None,
            "TEE_secure_command_effect_not_observed":True}

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("wrong_original_firmware_version")
    funcs,plt,uuid_literals=backing_elf(root/FILE)
    results=[]
    for name,expect in CASES.items():
        if name not in funcs:raise ValueError("no_original_func_"+name)
        results.append(examine_case(name,funcs[name],plt,expect))
    return {"schema":"hasselblad-stage27-original-e91c-TEE-operation-ABI-v1",
            "original_firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":SHA,"analysis":["Capstone AArch64","original ELF PLT"],
            "functions":results,
            "original_eFuse_or_device_operation_executed":False,
            "source_TA_or_DSP_decrypted":False,
            "key_derivation_or_TBIE_key_material_found":False,
            "private_literal_bytes_or_vendor_pseudocode_exported":False}

def synthetic():
    assert [x["kind"] for x in decompose(0x1ddd)]==[
        "PARTIAL_INPUT","PARTIAL_INPUT","PARTIAL_INPUT","VALUE_INPUT"]
    assert [x["kind"] for x in decompose(0x12)]==[
        "VALUE_OUTPUT","VALUE_INPUT","NONE","NONE"]
    assert len(CASES)==3 and SHA.startswith("63a4")
    return {"status":"PASS_synthetic","checks":3,"original_vendor_data_read":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--firmware-root",type=Path)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_binary_analyzed"),
         "functions":len(d.get("functions",[])),
         "paramtypes_values":[z["static_single_paramtypes_constant"] for z in d.get("functions",[])],
         "key_recovered":False},sort_keys=True))
if __name__=="__main__":main()
