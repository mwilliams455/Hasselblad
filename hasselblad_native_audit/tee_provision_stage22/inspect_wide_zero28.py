#!/usr/bin/env python3
"""X2D II Stage28: original command0 TEE_Operation zero-initialisation audit.

Examine AArch64 wide and SIMD stack stores omitted by Stage27's scalar-only
scan. Verify whether the command0 parameter-type word (SP+76) is cleared
before InvokeCommand. If a zeroing instruction is not clearly proven, report
unresolved; DO NOT infer an empty secure request from missing scalar stores.

Read-only original libamt_util.so. No TEE calls or eFuse operations executed,
no unknown literal content, vendor disassembly, key bytes or TA plaintext
exported in public report.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from trace_efuse_session24 import backing_elf,FILE,SHA
from prove_uuid_cfg26 import successors,reachable

FN="efuse_pro"
INVOKE=0x2b6c
OP_BASE=72
PARAMTYPE_BASE=OP_BASE+4
PARAMTYPE_BYTES=set(range(PARAMTYPE_BASE,PARAMTYPE_BASE+4))
MAX_ROWS=90

def vec_normal(name):
    match=re.fullmatch(r"[vqsdbh](\d+)",name or "")
    return ("vec"+match.group(1)) if match else name

def data_width(name):
    if not name:return None
    return {"w":4,"x":8,"s":4,"d":8,"q":16,"v":16,"h":2,"b":1}.get(name[0])

def overlap(start,width,low=OP_BASE,high=OP_BASE+104):
    return start<high and start+width>low

def zero_origin(insns,idx,name):
    """Classify zero registers or a local, non-branch-crossing vector zero."""
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM
    if name in ("xzr","wzr"):return {"zero":True,"basis":"architectural_zero_register"}
    normalized=vec_normal(name)
    for older in reversed(insns[max(0,idx-100):idx]):
        if older.mnemonic in ("bl","blr","b","br","ret") or older.mnemonic.startswith(("b.","cb","tb")):
            if normalized.startswith("vec"):
                # Vector registers are caller-saved; don't cross any call.
                return {"zero":False,"basis":"control_flow_or_call_boundary"}
            # Callee-saved general registers also need a CFG proof.
            return {"zero":False,"basis":"control_flow_or_call_boundary"}
        try:_,written=older.regs_access()
        except Exception:continue
        if not any(vec_normal(older.reg_name(r))==normalized for r in written):continue
        ops=older.operands
        if older.mnemonic in ("movi","mvni") and older.mnemonic=="movi":
            imms=[int(x.imm) for x in ops if x.type==ARM64_OP_IMM]
            return {"zero":bool(imms) and all(x==0 for x in imms),
                    "basis":"movi_all_imm_zero","def_va":hex(older.address)}
        if older.mnemonic=="eor" and len(ops)>=3 and all(x.type==ARM64_OP_REG for x in ops[:3]):
            b=vec_normal(older.reg_name(ops[1].reg))
            c=vec_normal(older.reg_name(ops[2].reg))
            return {"zero":b==c,"basis":"vector_register_self_xor",
                    "def_va":hex(older.address)}
        if older.mnemonic in ("mov","movz") and len(ops)>=2:
            if ops[1].type==ARM64_OP_REG and older.reg_name(ops[1].reg) in ("wzr","xzr"):
                return {"zero":True,"basis":"mov_from_zero_register","def_va":hex(older.address)}
            if ops[1].type==ARM64_OP_IMM and int(ops[1].imm)==0:
                return {"zero":True,"basis":"mov_immediate_zero","def_va":hex(older.address)}
        return {"zero":False,"basis":"nonzero_or_unknown_register_definition",
                "def_instruction_class":older.mnemonic,"def_va":hex(older.address)}
    return {"zero":False,"basis":"no_local_definition"}

def stores(insns):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM
    rows=[]
    for idx,ins in enumerate(insns):
        if ins.address>=INVOKE:break
        m=ins.mnemonic
        if m not in ("str","stur","stp","stnp"):continue
        ops=ins.operands
        if m in ("stp","stnp"):
            if len(ops)<3 or ops[2].type!=ARM64_OP_MEM:continue
            mem=ops[2].mem;srcs=ops[:2]
        else:
            if len(ops)<2 or ops[1].type!=ARM64_OP_MEM:continue
            mem=ops[1].mem;srcs=ops[:1]
        if ins.reg_name(mem.base)!="sp" or mem.index or ins.writeback:continue
        offset=int(mem.disp)
        for j,o in enumerate(srcs):
            if o.type!=ARM64_OP_REG:continue
            name=ins.reg_name(o.reg)
            width=data_width(name)
            if width is None:continue
            location=offset+j*width
            if not overlap(location,width):continue
            z=zero_origin(insns,idx,name)
            covered=sorted(PARAMTYPE_BYTES & set(range(location,location+width)))
            rows.append({"store_va":hex(ins.address),
                         "instruction_class":m,
                         "start_sp":location,
                         "width":width,
                         "register_class":name[0] if name else "unknown",
                         "source_zero_classification":z,
                         "paramtypes_bytes_overlapped":covered})
    return rows[:MAX_ROWS]

def inspect_one(root):
    funcs,plt,uuid=backing_elf(root/FILE)
    if FN not in funcs:raise ValueError("efuse_function_not_defined")
    insns=funcs[FN]
    by={x.address:x for x in insns}
    if INVOKE not in by or by[INVOKE].mnemonic!="bl":
        raise ValueError("wrong_original_invoke")
    graph=successors(insns);entry=insns[0].address
    rows=stores(insns)
    covers=[]
    for r in rows:
        if not r["paramtypes_bytes_overlapped"]:continue
        dom=reachable(graph,entry,INVOKE) and not reachable(graph,entry,INVOKE,remove=int(r["store_va"],16))
        covers.append({**r,"dominates_invocation":dom})
    # Require all four bytes to be written by a *single* dominating zero
    # store, and no later/other potentially overlapping store. This is
    # intentionally stronger than evidence from a linear walk alone.
    qualified=[r for r in covers if
               r["source_zero_classification"]["zero"] and r["dominates_invocation"] and
               set(r["paramtypes_bytes_overlapped"])==PARAMTYPE_BYTES]
    zero_proven=False
    if len(qualified)==1:
        candidate=qualified[0]
        other=[x for x in covers if x["store_va"]!=candidate["store_va"]]
        zero_proven=not other
    return {"schema":"hasselblad-stage28-original-eFuse-command0-zero-contract-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "hash_pinned_normal_world_libamt_sha256":SHA,
            "function":FN,"command_id":0,"TEE_InvokeCommand_va":hex(INVOKE),
            "operation_base_sp":OP_BASE,
            "paramtypes_field_sp":PARAMTYPE_BASE,
            "original_wide_store_candidates":rows,
            "stores_overlap_paramTypes":covers,
            "single_dominating_zero_store_covers_paramTypes_without_conflict":zero_proven,
            "candidate_paramTypes_hex":"0x0000" if zero_proven else None,
            "candidate_paramTypes_meaning":"all_NONE" if zero_proven else "unresolved",
            "statically_inferred_ABI_not_secure_world_behavior":True,
            "eFuse_pro_operation_executed":False,
            "TBIE_key_or_decrypted_TA_recovered":False,
            "raw_manufacturer_code_or_unknown_data_exported":False}

def synthetic():
    assert overlap(72,16)
    assert not overlap(0,8)
    assert set(range(72,88))>=PARAMTYPE_BYTES
    assert vec_normal("q0")==vec_normal("v0")=="vec0"
    return {"status":"PASS_synthetic","checks":4,"original_data_loaded":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if not a.self_test and not a.firmware_root:ap.error("--firmware-root required")
    d=synthetic() if a.self_test else inspect_one(a.firmware_root)
    a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":d.get("status","original_analyzed"),
        "zero_paramtypes_proven":d.get("single_dominating_zero_store_covers_paramTypes_without_conflict"),
        "key_recovered":False},sort_keys=True))

if __name__=="__main__":main()
