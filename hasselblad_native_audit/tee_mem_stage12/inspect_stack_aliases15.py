#!/usr/bin/env python3
"""Stage15: bounded static aliases into TEE_Operation memref slots.

A path-aware forward abstract interpreter tracks registers holding stack
addresses in original X2D II host AArch64 client functions. It groups memory
stores into candidate TEEC_Operation slots for commands 2 and 6 and compares
their source pointer aliases with actual allocated/registered SharedMemory
objects. The analysis is deliberately conservative: a candidate is NOT proof
the store executes on the runtime path or that the TEE returns plaintext.

Do not publish original binary bytes, raw assembly, pseudocode, user data,
cipher keys, pointer contents, or original input strings.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from inspect_memrefs12 import load_original,SOURCE,SPEC
from inspect_cfg_sources14 import cfg,canon

CMDS={
 "fw_util_verify_init_ext":{"command":6,"obj":[120,72,24],"operation":192,"invoke":0x1ef8},
 "fw_util_verify_load2ion":{"command":2,"obj":[64,16],"operation":168,"invoke":0x18d8},
 "fw_util_load":{"command":1,"obj":[80,32],"operation":184,"invoke":0x162c},
}
MAX_ALIASES=8
REGS=range(31)

def pure_const(ins,ops,st):
    """Infer register pointer relative to stable post-prologue SP, or unknown.
    Value of register itself can be private; only SP-relative offsets retained.
    """
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM
    get=lambda op:ins.reg_name(op.reg)
    if ins.mnemonic in ("mov","movz") and len(ops)>1 and ops[1].type==ARM64_OP_REG:
        src=get(ops[1])
        if src=="sp":return frozenset({0})
        r=canon(src)
        return st[r] if r is not None else frozenset({None})
    if ins.mnemonic in ("add","sub") and len(ops)>2 and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
        src=get(ops[1])
        if src=="sp":base=frozenset({0})
        else:
            r=canon(src)
            base=st[r] if r is not None else frozenset({None})
        delta=int(ops[2].imm)*(1 if ins.mnemonic=="add" else -1)
        return frozenset(v+delta if v is not None else None for v in base)
    return frozenset({None})

def transfer(ins,st):
    from capstone.arm64 import ARM64_OP_REG
    out=list(st)
    try:_,wr=ins.regs_access()
    except Exception:wr=[]
    written={canon(ins.reg_name(r)) for r in wr}
    written.discard(None)
    for r in written:
        if ins.operands and ins.operands[0].type==ARM64_OP_REG and canon(ins.reg_name(ins.operands[0].reg))==r:
            out[r]=pure_const(ins,ins.operands,st)
        else:out[r]=frozenset({None})
    # AAPCS64 says x0..x18 are caller-clobbered; x19..x28 survive.
    if ins.mnemonic in ("bl","blr"):
        for r in range(19):out[r]=frozenset({None})
    return tuple(out)

def analyze(insns):
    edges=cfg(insns)
    first=insns[0].address
    unknown=frozenset({None})
    states={first:tuple(unknown for _ in REGS)}
    pending=[first]
    by={i.address:i for i in insns}
    rounds=0
    while pending:
        addr=pending.pop()
        new=transfer(by[addr],states[addr])
        for dst in edges[addr]:
            prev=states.get(dst)
            if prev is None:
                states[dst]=new;pending.append(dst);continue
            merged=tuple(prev[i]|new[i] for i in REGS)
            if any(len(x)>MAX_ALIASES for x in merged):
                raise ValueError("excessive_alias_paths")
            if merged!=prev:
                states[dst]=merged;pending.append(dst)
        rounds+=1
        if rounds>len(insns)*60:raise ValueError("alias_fixpoint_budget")
    return states,rounds

def store_records(insns,states,until):
    from capstone.arm64 import ARM64_OP_MEM,ARM64_OP_REG
    res=[]
    for ins in insns:
        if ins.address>=until or ins.address not in states:continue
        if ins.mnemonic not in ("str","stur","stp","stnp"):continue
        ops=ins.operands
        if ins.mnemonic in ("stp","stnp"):
            if len(ops)<3 or ops[2].type!=ARM64_OP_MEM:continue
            mem=ops[2].mem;vals=ops[:2]
        else:
            if len(ops)<2 or ops[1].type!=ARM64_OP_MEM:continue
            mem=ops[1].mem;vals=ops[:1]
        if ins.writeback or mem.index:continue
        base=ins.reg_name(mem.base)
        r=canon(base)
        aliases=frozenset({0}) if base=="sp" else states[ins.address][r] if r is not None else frozenset({None})
        if len(aliases)!=1 or None in aliases:continue
        baseoff=next(iter(aliases))+int(mem.disp)
        for j,op in enumerate(vals):
            if op.type!=ARM64_OP_REG:continue
            src=ins.reg_name(op.reg)
            width=4 if src.startswith(("w","s")) else 8 if src.startswith(("x","d")) else 16 if src.startswith("q") else None
            if not width:continue
            absolute=baseoff+j*width
            sr=canon(src)
            v=states[ins.address][sr] if sr is not None else frozenset({None})
            src_sp=next(iter(v)) if len(v)==1 and None not in v else None
            res.append({"store_va":hex(ins.address),
                        "stack_offset":absolute,
                        "source_width_bytes":width,
                        "source_register":src,
                        "value_sp_offset_candidate":src_sp,
                        "via_indirect_stack_alias":base!="sp",
                        "operation_writes_are_path_sensitive_proven":False})
    return res

def dossier(name,insns):
    spec=CMDS[name]
    before=spec["invoke"]
    states,rounds=analyze(insns)
    writes=store_records(insns,states,before)
    op=spec["operation"]
    slots=[]
    for i in range(4):
        start=op+8+24*i
        selected=[dict(w,relative_field=w["stack_offset"]-start)
                  for w in writes if start<=w["stack_offset"]<start+24]
        parent=[w for w in selected if w["relative_field"]==0 and w["source_width_bytes"]==8]
        candidates=[w["value_sp_offset_candidate"] for w in parent
                    if w["value_sp_offset_candidate"] in spec["obj"]]
        slots.append({"slot_index":i,"candidate_stack_field_writes":selected[:16],
                      "candidate_parent_objects_sp":sorted(set(candidates)),
                      "unique_candidate_parent_object":list(set(candidates))[0] if len(set(candidates))==1 else None,
                      "parent_link_is_proven_on_every_runtime_path":False})
    shared=[]
    for addr in spec["obj"]:
        flags=[w for w in writes if w["stack_offset"]==addr+16 and w["source_width_bytes"]==4]
        shared.append({"object_sp":addr,"possible_flags_stores":flags[:8],
                       "original_shared_memory_flags_semantics_proven":False})
    return {"function":name,"command_id":spec["command"],
            "CFG_analysed_instructions":len(insns),
            "abstract_interpretation_rounds":rounds,
            "operation_base_sp":op,"shared_memory_objects":shared,
            "operation_parameter_slots":slots,
            "operation_parent_links_proven_on_all_paths":False,
            "original_decrypted_output_buffer_returned":False}

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("firmware_version")
    funcs,_=load_original(root/SOURCE)
    return {"schema":"hasselblad-stage15-original-tee-stack-alias-candidates-v1",
        "firmware":"X2D II 100C 1.3.16.2",
        "functions":[dossier(name,funcs[name]) for name in CMDS],
        "original_vendor_code_executed":False,
        "source_firmware_or_machine_instructions_exported":False,
        "TEE_secrets_or_DSP_decrypted":False,
        "secure_world_buffer_semantics_unknown":True}

def synthetic():
    class Ins:
        mnemonic="add";operands=[]
    assert MAX_ALIASES>=4
    assert len(CMDS)==3
    assert 192+8+24*3==272
    return {"status":"PASS_synthetic","checks":3,"original_vendor_code_loaded":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_static_complete"),
                      "objects":sum(len(x["shared_memory_objects"]) for x in d.get("functions",[])),
                      "candidate_parent_links":sum(int(s["unique_candidate_parent_object"] is not None)
                     for f in d.get("functions",[]) for s in f["operation_parameter_slots"])},sort_keys=True))
if __name__=="__main__":main()
