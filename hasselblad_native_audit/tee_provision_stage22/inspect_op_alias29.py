#!/usr/bin/env python3
"""X2D II Stage29: identify indirect initialisation of second-TA command 0.

The earlier scalar/wide direct SP store audits found no write covering
TEEC_Operation.paramTypes at SP+76. This probe traces register aliases of SP
and recognised libc zeroing calls (memset, bzero, explicit_bzero) to locate
potential indirect writes. Conclusions remain path-conservative.

Original hash-pinned host-side libamt_util.so only. Manufacturer executable,
TEE, fuses and camera are never executed. Do not export source bytes, unknown
literal data, keys, private photographs or original disassembly.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

from trace_efuse_session24 import backing_elf,FILE,SHA
from prove_uuid_cfg26 import successors,reachable

FUNCTION="efuse_pro"
INVOKE=0x2b6c
OP_START=72
OP_SIZE=104
TYPES=set(range(76,80))
MAX_CANDIDATES=48
ZERO_FUNCS={"memset","__memset_chk","bzero","explicit_bzero"}

def width(name):
    return {"w":4,"x":8,"q":16,"d":8,"s":4,"v":16,"h":2,"b":1}.get(name[0]) if name else None

def loc(ins,reg):
    return ins.reg_name(reg)

def overlaps(a,n,b,m):
    return a<b+m and a+n>b

def is_zero(reg, zero_vec):
    if reg in ("xzr","wzr"):return True
    if reg and reg[0] in "vqsd" and reg[1:].isdigit():
        return int(reg[1:]) in zero_vec
    return False

def analyze(root):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    funcs,plt,uuids=backing_elf(root/FILE)
    if FUNCTION not in funcs:raise ValueError("original_function_missing")
    insns=funcs[FUNCTION]
    by={ins.address:ins for ins in insns}
    if INVOKE not in by:raise ValueError("original_invoke_missing")
    # Unconditional abstract interpretation of register aliases. A branch or
    # aliased pointer escaping into a call is an uncertainty, not a proof.
    pointers={"sp":0}
    constants={}
    zero_vec=set()
    candidates=[]
    opaque_calls=[]
    unhandled_store_bases=set()
    for ins in insns:
        if ins.address>=INVOKE:break
        m=ins.mnemonic;ops=ins.operands
        if m=="bl" and len(ops)==1 and ops[0].type==ARM64_OP_IMM:
            callee=plt.get(int(ops[0].imm))
            if callee in ZERO_FUNCS:
                dst=pointers.get("x0")
                n=constants.get("x2") if callee in ("memset","__memset_chk") else constants.get("x1")
                val=constants.get("x1") if callee in ("memset","__memset_chk") else 0
                if isinstance(dst,int) and isinstance(n,int) and n>=0 and n<=2048:
                    if overlaps(dst,n,OP_START,OP_SIZE):
                        candidates.append({"site_va":hex(ins.address),"kind":"libc_zeroing",
                            "api":callee,"offset_sp":dst,"width":n,
                            "source_zero":val==0,
                            "overlaps_paramTypes":overlaps(dst,n,76,4)})
            elif callee and (pointers.get("x0") is not None or pointers.get("x1") is not None):
                opaque_calls.append({"va":hex(ins.address),"api_class":"other_host_call"})
            # x0..x18 and V0..V7 are caller-clobbered.
            for j in range(19):
                pointers.pop("x"+str(j),None)
                constants.pop("x"+str(j),None)
                constants.pop("w"+str(j),None)
            zero_vec.difference_update(range(8))
            continue
        if m in ("movi",) and len(ops)>=2 and ops[0].type==ARM64_OP_REG:
            n=loc(ins,ops[0].reg)
            if n[1:].isdigit() and n[0] in "vqsd":
                imms=[int(op.imm) for op in ops[1:] if op.type==ARM64_OP_IMM]
                idx=int(n[1:])
                if imms and all(i==0 for i in imms):zero_vec.add(idx)
                else:zero_vec.discard(idx)
        if m in ("str","stur","stp","stnp"):
            paired=m in ("stp","stnp")
            if (paired and len(ops)>=3 and ops[2].type==ARM64_OP_MEM):
                mem=ops[2].mem;srcs=ops[:2]
            elif (not paired and len(ops)>=2 and ops[1].type==ARM64_OP_MEM):
                mem=ops[1].mem;srcs=ops[:1]
            else:continue
            base=loc(ins,mem.base)
            p=pointers.get(base)
            if base=="sp":p=0
            if p is None or mem.index or ins.writeback:
                if base!="sp":unhandled_store_bases.add(base)
                continue
            for k,src in enumerate(srcs):
                if src.type!=ARM64_OP_REG:continue
                reg=loc(ins,src.reg);w=width(reg)
                if w is None:continue
                start=p+int(mem.disp)+k*w
                if overlaps(start,w,OP_START,OP_SIZE):
                    candidates.append({"site_va":hex(ins.address),
                        "kind":"alias_sp_store" if base!="sp" else "direct_sp_store",
                        "offset_sp":start,"width":w,"source_zero":is_zero(reg,zero_vec),
                        "register_class":reg[0],
                        "overlaps_paramTypes":overlaps(start,w,76,4)})
            continue
        # Update pointer and immediate-register provenance only for
        # straightforward AArch64 register-defining instructions.
        if not ops or ops[0].type!=ARM64_OP_REG:continue
        dest=loc(ins,ops[0].reg)
        if not dest or dest in ("sp","xzr","wzr"):continue
        if dest[0] not in "wx":continue
        if m in ("mov","movz") and len(ops)>=2:
            if ops[1].type==ARM64_OP_REG:
                src=loc(ins,ops[1].reg)
                pointers[dest]=pointers.get(src)
                constants[dest]=0 if src in ("xzr","wzr") else constants.get(src)
            elif ops[1].type==ARM64_OP_IMM:
                v=int(ops[1].imm)
                pointers.pop(dest,None)
                constants[dest]=v
            else:
                pointers.pop(dest,None);constants.pop(dest,None)
        elif m in ("add","sub") and len(ops)>=3 and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
            base=loc(ins,ops[1].reg)
            v=0 if base=="sp" else pointers.get(base)
            delta=int(ops[2].imm)*(1 if m=="add" else -1)
            if isinstance(v,int):pointers[dest]=v+delta
            else:pointers.pop(dest,None)
            val=constants.get(base)
            if isinstance(val,int):constants[dest]=val+delta
            else:constants.pop(dest,None)
        else:
            # Instruction writing wN also invalidates xN's known value.
            pointers.pop(dest,None);constants.pop(dest,None)
    graph=successors(insns)
    entry=insns[0].address
    covers=[]
    for cand in candidates:
        if not cand["overlaps_paramTypes"]:continue
        a=int(cand["site_va"],16)
        dominates=reachable(graph,entry,INVOKE) and not reachable(graph,entry,INVOKE,remove=a)
        covers.append({**cand,"dominates_invocation":dominates})
    zeros=[x for x in covers if x["source_zero"] and x["dominates_invocation"] and
           x["offset_sp"]<=76 and x["offset_sp"]+x["width"]>=80]
    # Strict, path-independent proof still needs full alias analysis; no
    # incomplete source-zero marker should be called definitive here.
    strict= len(zeros)==1 and len(covers)==1 and not unhandled_store_bases
    return {"schema":"hasselblad-stage29-original-command0-indirect-TEE-operation-init-v1",
        "source":"system/lib64/libamt_util.so","source_sha256":SHA,
        "function":FUNCTION,"TEE_command_id":0,"TEE_operation_sp":72,
        "candidate_alias_or_libc_writes_to_operation":candidates[:MAX_CANDIDATES],
        "candidate_paramtypes_writes":covers[:20],
        "explicit_zero_write_covers_paramtypes_and_dominates":bool(zeros),
        "no_conflicting_detected_writes":len(covers)==1,
        "strict_nonzero_or_zero_proof_is_incomplete":not strict,
        "possible_unresolved_store_base_count":len(unhandled_store_bases),
        "possible_opaque_calls_with_pointer_args":len(opaque_calls),
        "actual_TEE_paramTypes_in_ta_proven":False,
        "secure_world_command0_effect_proven":False,
        "secret_material_or_proprietary_code_exported":False,
        "original_TEE_or_eFuse_executed":False}

def synthetic():
    assert overlaps(72,16,76,4)
    assert not overlaps(64,8,76,4)
    assert width("q0")==16 and width("x3")==8 and width("w7")==4
    assert is_zero("xzr",set()) and is_zero("v0",{0})
    return {"status":"PASS_synthetic","checks":4,"original_firmware_used":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else analyze(a.firmware_root)
    a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":d.get("status","original_static_audit"),
        "paramtypes_store_candidates":len(d.get("candidate_paramtypes_writes",[])),
        "zero_store_candidates":d.get("explicit_zero_write_covers_paramtypes_and_dominates"),
        "key_or_plaintext_exported":False},sort_keys=True))
if __name__=="__main__":main()
