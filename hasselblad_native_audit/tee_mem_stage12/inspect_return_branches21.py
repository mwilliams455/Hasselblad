#!/usr/bin/env python3
"""Stage21 — branch-rooted original X2D II command2 return register audit.

The Stage20 whole-function reaching-definition result includes unrelated
pre-service/early-exit paths. Stage21 intentionally seeds separate data-flow
at the two post-service status-branch successors. This isolates normal paths
after TEE command2 and before the host output copy and return-value assignment.

This is a read-only original AArch64 static analysis: no camera, TA/DSP
execution, decrypted output, key material or raw disassembly in public report.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from inspect_host_return17 import read_original,SOURCE,SHA,SERVICE,OUTCOPY
from inspect_cfg_sources14 import cfg,canon
from inspect_post_return18 import shortest_path,STATUS
from inspect_status_provenance20 import RETVAL_MOV,RET_VA

MAX_REACH=16
MAX_ITERATIONS=30000

def explicit_def(ins, reg):
    # Preflight can run without Capstone installed.
    # Data-processing alias CMP / TST writes flags, not operand 0.
    if ins.mnemonic in ("cmp","cmn","tst","ccmp","ccmn","str","stur","stp","stnp","b","bl","blr"):
        return False
    ops=ins.operands
    if not ops:return False
    from capstone.arm64 import ARM64_OP_REG
    potential=ops[:2] if ins.mnemonic in ("ldp","ldnp") else ops[:1]
    return any(o.type==ARM64_OP_REG and canon(ins.reg_name(o.reg))==reg for o in potential)

def rooted_defs(insns,graph,seed,reg):
    by={i.address:i for i in insns}
    reachable={seed:{-1}}
    todo=[seed]
    iters=0
    while todo:
        va=todo.pop()
        cur=reachable[va]
        ins=by[va]
        # Nonvolatile x19..x28 are preserved by all conforming external calls.
        out={va} if explicit_def(ins,reg) else cur
        for nxt in graph.get(va,()):
            if nxt not in reachable:
                reachable[nxt]=set(out);todo.append(nxt)
            elif not out.issubset(reachable[nxt]):
                reachable[nxt].update(out)
                if len(reachable[nxt])>MAX_REACH:raise ValueError("too_many_joined_definitions")
                todo.append(nxt)
        iters+=1
        if iters>MAX_ITERATIONS:raise ValueError("CFG_iteration_limit")
    return reachable,iters

def decoded_definition(ins):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    result={"site_va":hex(ins.address),"instruction_class":ins.mnemonic}
    if ins.mnemonic in ("mov","movz") and len(ins.operands)>=2:
        o=ins.operands[1]
        if o.type==ARM64_OP_REG:
            src=ins.reg_name(o.reg)
            result["register_source"]=src
            result["assigns_literal_zero"]=src in ("wzr","xzr")
        elif o.type==ARM64_OP_IMM:
            val=int(o.imm)
            result["literal"]=val if -65536<=val<=65536 else None
            result["assigns_literal_zero"]=val==0
    elif ins.mnemonic in ("add","sub") and len(ins.operands)>=3:
        o1,o2=ins.operands[1:3]
        if o1.type==ARM64_OP_REG:result["relative_source"]=ins.reg_name(o1.reg)
        if o2.type==ARM64_OP_IMM:
            result["offset"]=int(o2.imm) if -65536<=int(o2.imm)<=65536 else None
    return result

def audit(root):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG
    insns=read_original(root/SOURCE)
    by={i.address:i for i in insns}
    for site in (STATUS,SERVICE,OUTCOPY,RETVAL_MOV,RET_VA):
        if site not in by:raise ValueError("required_original_function_site_missing")
    ins=by[STATUS]
    if (ins.mnemonic!="cbz" or ins.operands[0].type!=ARM64_OP_REG or
        ins.reg_name(ins.operands[0].reg)!="w8"):
        raise ValueError("status_test_has_changed")
    if ins.operands[-1].type!=ARM64_OP_IMM:
        raise ValueError("branch_target_has_changed")
    success=int(ins.operands[-1].imm)
    nonzero=STATUS+4
    graph=cfg(insns)
    cases=[]
    for case,start in (("service_result_zero",success),
                       ("service_result_nonzero",nonzero)):
        flow,n=rooted_defs(insns,graph,start,19)
        defs=sorted(flow.get(RETVAL_MOV,set()))
        rows=[]
        for d in defs:
            rows.append({"kind":"incoming_saved_x19_unknown"} if d==-1 else decoded_definition(by[d]))
        allzero=bool(rows) and len(rows)==1 and rows[0].get("assigns_literal_zero") is True
        cases.append({"case":case,"seed_va":hex(start),
                      "reaches_host_memcpy":shortest_path(graph,start,OUTCOPY) is not None,
                      "reaches_original_return_status_write":RETVAL_MOV in flow,
                      "w19_reaching_definition_count":len(defs),
                      "w19_reaching_definitions":rows[:MAX_REACH],
                      "w19_guaranteed_zero_on_all_modelled_normal_paths":allzero,
                      "control_flow_iterations":n,
                      "return_value_proof_only_if_branch_feasible_at_runtime":True})
    return {"schema":"hasselblad-stage21-original-TEE-return-status-rooted-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":SHA,
            "service_call_va":hex(SERVICE),
            "output_copy_va":hex(OUTCOPY),
            "original_public_return_register_write_va":hex(RETVAL_MOV),
            "status_branch_va":hex(STATUS),
            "cases":cases,
            "secure_world_decrypted_result_observed":False,
            "vendor_binary_or_instructions_published":False,
            "host_original_firmware_executed":False}

def selftest():
    class Inst:
        mnemonic="mov";operands=[]
    assert not explicit_def(Inst(),19)
    assert canon("w19")==canon("x19")==19
    assert MAX_REACH>=8
    return {"status":"PASS_synthetic","checks":3,"source_firmware_read":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=selftest() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_static"),
                      "cases":len(d.get("cases",[])),
                      "status_zero_cases":sum(x["w19_guaranteed_zero_on_all_modelled_normal_paths"]
                                               for x in d.get("cases",[])),
                      "decryption_proven":False},sort_keys=True))
if __name__=="__main__":main()
