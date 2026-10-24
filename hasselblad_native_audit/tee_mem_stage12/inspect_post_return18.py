#!/usr/bin/env python3
"""Stage18: read-only original X2D II post-TEE status/length gate audit.

This uses the same hash-pinned host binary as Stages 16–17, then:
- branches from the actual command-2 return through the output memcpy,
- records conditional predicates that discriminate copy and early-exit paths,
- finds original SP+20 output-length stores and loads before and after service,
- classifies but does NOT execute/assume security success or decoded payloads.

Only bounded control-flow/ABI metadata is exported, not proprietary binary,
assembly text, plaintext, signatures, key material or private photographs.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import deque
from pathlib import Path

from inspect_host_return17 import read_original, SOURCE, SHA, FN, SERVICE, OUTCOPY, INCOPY
from inspect_cfg_sources14 import cfg

STATUS = 0x234c
BOUNDS = 0x23b4
MAX_GRAPH_NODES = 650
MAX_PATH = 350
INTERESTING_STACK = 20

def shortest_path(graph, start, end, forbidden=frozenset()):
    if start in forbidden:return None
    q=deque([(start, [start])])
    visited={start}
    while q:
        here,seq=q.popleft()
        if here==end:return seq
        if len(seq)>MAX_PATH:raise ValueError("path_exceeded_budget")
        for nxt in graph.get(here, []):
            if nxt not in visited and nxt not in forbidden:
                visited.add(nxt);q.append((nxt,seq+[nxt]))
        if len(visited)>MAX_GRAPH_NODES:raise ValueError("graph_exceeded_budget")
    return None

def summaries_of_path(nodes, by):
    return [{"va":hex(a),"kind":by[a].mnemonic}
            for a in nodes if (a in by and
              (by[a].mnemonic.startswith("b.") or by[a].mnemonic in ("cbz","cbnz","tbz","tbnz")))]

def conditional(ins):
    return ins.mnemonic.startswith("b.") or ins.mnemonic in ("cbz","cbnz","tbz","tbnz")

def branch_case(ins, graph, by, outcopy):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM
    if not conditional(ins):raise ValueError("not_conditional")
    if len(ins.operands)<1 or ins.operands[-1].type!=ARM64_OP_IMM:
        raise ValueError("unsupported_original_branch_form")
    target=int(ins.operands[-1].imm)
    fall=ins.address+4
    if target not in by or fall not in by:
        raise ValueError("branch_outside_function")
    result={"site_va":hex(ins.address),"branch_class":ins.mnemonic,
            "taken_destination":hex(target),"fallthrough_destination":hex(fall)}
    if ins.mnemonic in ("cbz","cbnz"):
        result["test_register"]=ins.reg_name(ins.operands[0].reg)
        result["taken_when"]=("value_equals_zero" if ins.mnemonic=="cbz" else "value_nonzero")
    for label,address in (("taken",target),("fallthrough",fall)):
        route=shortest_path(graph,address,outcopy)
        result[label+"_can_reach_output_copy"]=route is not None
        if route is not None:
            result[label+"_shortest_path_instruction_count"]=len(route)
            result[label+"_conditional_steps"]=summaries_of_path(route,by)[:18]
        # An early return can be reached without copying (this is an
        # over-approximation of runtime paths, not a decryption status).
        returnpoints=[x.address for x in by.values() if x.mnemonic=="ret"]
        exiting=[shortest_path(graph,address,e,forbidden={outcopy}) for e in returnpoints]
        good=[v for v in exiting if v]
        result[label+"_may_return_without_output_copy"]=bool(good)
        if good:result[label+"_shortest_return_without_copy"]=len(min(good,key=len))
    return result

def operand(ins,op):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    if op.type==ARM64_OP_REG:
        return {"kind":"register","name":ins.reg_name(op.reg)}
    if op.type==ARM64_OP_IMM:
        n=int(op.imm)
        return {"kind":"immediate","value":n if -65536<=n<=65536 else "larger_constant"}
    if op.type==ARM64_OP_MEM:
        return {"kind":"memory","base":ins.reg_name(op.mem.base),
                "offset":int(op.mem.disp),
                "indexed":bool(op.mem.index)}
    return {"kind":"other"}

def local_compare(insns, address):
    idx=next(i for i,v in enumerate(insns) if v.address==address)
    for v in reversed(insns[max(0,idx-22):idx]):
        if conditional(v) or v.mnemonic in ("b","bl","blr","ret","br"):
            return {"kind":"not_in_same_basic_block"}
        if v.mnemonic in ("cmp","cmn","tst","ccmp","ccmn","subs","ands"):
            return {"kind":"flag_setter","site_va":hex(v.address),
                    "mnemonic_class":v.mnemonic,
                    "arguments":[operand(v,x) for x in v.operands[:4]]}
    return {"kind":"no_recognized_flag_source_in_local_window"}

def stack20(insns):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM
    records=[]
    for ins in insns:
        if ins.mnemonic not in ("ldr","ldur","str","stur") or len(ins.operands)<2:
            continue
        ops=ins.operands
        if ops[1].type!=ARM64_OP_MEM:
            continue
        mem=ops[1].mem
        if ins.reg_name(mem.base)!="sp" or mem.index or int(mem.disp)!=INTERESTING_STACK:
            continue
        if ops[0].type!=ARM64_OP_REG:continue
        reg=ins.reg_name(ops[0].reg)
        if reg[0] not in "wx":continue
        row={"site_va":hex(ins.address),
             "operation":"write" if ins.mnemonic in ("str","stur") else "read",
             "register":reg,
             "width_bytes":4 if reg.startswith("w") else 8,
             "before_secure_call":ins.address<SERVICE,
             "after_secure_call":ins.address>SERVICE}
        records.append(row)
    return records

def audit(path):
    insns=read_original(path)
    if len(insns)>MAX_GRAPH_NODES:raise ValueError("unexpected_insn_count")
    graph=cfg(insns)
    by={v.address:v for v in insns}
    for spot in (SERVICE+4,STATUS,BOUNDS,OUTCOPY):
        if spot not in by:raise ValueError("required_original_site_missing_"+hex(spot))
    if by[STATUS].mnemonic!="cbz" or by[BOUNDS].mnemonic!="b.lo":
        raise ValueError("unexpected_original_status_or_bound_shape")
    res={
      "schema":"hasselblad-stage18-original-post-tee-conditional-copy-contract-v1",
      "source":SOURCE,"source_sha256":SHA,"function":FN,
      "original_instructions_examined":len(insns),
      "secure_call_at":hex(SERVICE),"host_copy_at":hex(OUTCOPY),
      "service_resume_can_reach_copy":shortest_path(graph,SERVICE+4,OUTCOPY) is not None,
      "status_branch":branch_case(by[STATUS],graph,by,OUTCOPY),
      "bounds_branch":branch_case(by[BOUNDS],graph,by,OUTCOPY),
      "bounds_condition_source":local_compare(insns,BOUNDS),
      "original_shared_output_length_stack_sp20":stack20(insns),
      "post_service_memcpy_actual_bytes_observed":False,
      "output_length_initialized_and_updated_by_TEE_proven":False,
      "secure_world_return_value_semantics_proven":False,
      "ciphertext_vs_decrypted_plaintext_proven":False,
      "original_vendor_code_executed":False,
      "vendor_instruction_text_or_bytes_exported":False}
    return res

def selftest():
    toy={0:[4,8],4:[12],8:[16],12:[],16:[]}
    assert shortest_path(toy,0,16)==[0,8,16]
    assert shortest_path(toy,0,16,forbidden={8}) is None
    assert shortest_path(toy,0,12)==[0,4,12]
    return {"status":"PASS_synthetic","checks":3,"original_input_loaded":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--firmware-root",type=Path)
    args=p.parse_args()
    if not args.self_test and not args.firmware_root:p.error("--firmware-root required")
    result=selftest() if args.self_test else audit(args.firmware_root/SOURCE)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result.get("status","original_completed"),
                      "output_copy_reachable":result.get("service_resume_can_reach_copy"),
                      "length_ops":len(result.get("original_shared_output_length_stack_sp20",[])),
                      "decryption_proven":False},sort_keys=True))

if __name__=="__main__":
    main()
