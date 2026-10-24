#!/usr/bin/env python3
"""Stage19: normal-world X2D II post-TEE return-value contract, static only.

Do not confuse a host memcpy with successful decrypt: find every normal return
after the secure command2 host wrapper resumes, whether memcpy is mandatory
on those paths, and which AArch64 reaching definitions form the return status.

Only hash-pinned original system/lib64/libfw_util.so is inspected.
No original binary, raw instruction bytes, decompiled text, secrets or private
photos are exported. Static CFG is not a runtime successful-decrypt oracle.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

from inspect_host_return17 import read_original, defs_with_abi_clobber, SOURCE, SHA, FN, SERVICE, OUTCOPY
from inspect_cfg_sources14 import cfg, canon
from inspect_post_return18 import shortest_path, STATUS, BOUNDS, local_compare, stack20

MAX_DEFS=18

def describe_definition(ins):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    o=ins.operands
    d={"va":hex(ins.address),"instruction_class":ins.mnemonic}
    if len(o)>1 and o[1].type==ARM64_OP_REG:
        d["reads_register"]=ins.reg_name(o[1].reg)
    elif len(o)>1 and o[1].type==ARM64_OP_IMM:
        x=int(o[1].imm)
        d["small_immediate"]=x if 0<=x<=65535 else None
    elif len(o)>1 and o[1].type==ARM64_OP_MEM:
        d["memory_base_register"]=ins.reg_name(o[1].mem.base)
        d["memory_relative_offset"]=int(o[1].mem.disp)
    return d

def nearby_pltcalls(insns):
    """Only return known PLT-call addresses from prior proved stages."""
    return {"fw_util_verify_load2ion":"0x2344",
            "post_service_memcpy":"0x23dc"}

def audit(root):
    insns=read_original(root/SOURCE)
    by={i.address:i for i in insns}
    graph=cfg(insns)
    entry_after_service=SERVICE+4
    if entry_after_service not in by or OUTCOPY not in by:
        raise ValueError("original_call_or_copy_missing")
    ret_nodes=[i.address for i in insns if i.mnemonic=="ret"]
    if not ret_nodes:raise ValueError("original_returns_not_found")
    via_copy=[]
    bypass_copy=[]
    for ret in ret_nodes:
        if shortest_path(graph,entry_after_service,ret) is None:continue
        route_without=shortest_path(graph,entry_after_service,ret,forbidden={OUTCOPY})
        row={"return_va":hex(ret),
             "return_reachable_from_service":True,
             "return_may_bypass_host_copy":route_without is not None}
        if route_without is not None:
            row["shortest_bypass_path_instructions"]=len(route_without)
            bypass_copy.append(row)
        else:via_copy.append(row)
    from_ret=defs_with_abi_clobber(insns,graph,0)
    from_reg19=defs_with_abi_clobber(insns,graph,19)
    reg2=defs_with_abi_clobber(insns,graph,2)
    return_rows=[]
    for row in via_copy+bypass_copy:
        addr=int(row["return_va"],16)
        definitions=from_ret.get(addr,set())
        ret_defs=[]
        for d in sorted(definitions):
            if d==-1:
                ret_defs.append({"type":"original_input_abi_x0"})
            elif d in by:
                ret_defs.append(describe_definition(by[d]))
        # If return is a MOV w0,w19, find the actual source of w19.
        r19defs=from_reg19.get(addr,set())
        status_candidate=[]
        for d in sorted(r19defs):
            if d==-1:status_candidate.append({"type":"unmodified_callee_saved_input"})
            elif d in by:status_candidate.append(describe_definition(by[d]))
        return_rows.append(dict(row,
                  x0_reaching_definitions=ret_defs[:MAX_DEFS],
                  x19_reaching_definitions=status_candidate[:MAX_DEFS],
                  single_x0_reaching_definition=len(definitions)==1,
                  return_value_equivalence_to_secure_status_proven=False))
    cmp_def=reg2.get(BOUNDS,set())
    cmp_src=[]
    for d in sorted(cmp_def):
        if d==-1:cmp_src.append({"type":"original_incoming_x2"})
        elif d in by:cmp_src.append(describe_definition(by[d]))
    stack=stack20(insns)
    direct_after_write=[x for x in stack if x["operation"]=="write" and x["after_secure_call"]]
    return {
        "schema":"hasselblad-stage19-original-TEE-command2-copy-return-contract-v1",
        "firmware":"X2D II 100C 1.3.16.2",
        "source":SOURCE,"source_sha256":SHA,"function":FN,
        "service_call_va":hex(SERVICE),"host_copy_va":hex(OUTCOPY),
        "normal_returns_reachable_after_service":len(return_rows),
        "normal_returns_with_copy_dominating":len(via_copy),
        "normal_returns_with_bypass_path":len(bypass_copy),
        "copy_dominates_all_observed_normal_returns_after_service":
            bool(return_rows) and not bypass_copy,
        "normal_return_paths":return_rows,
        "secondary_conditional_site_va":hex(BOUNDS),
        "secondary_conditional_local_cmp":local_compare(insns,BOUNDS),
        "secondary_cmp_x2_reaching_defs":cmp_src[:MAX_DEFS],
        "output_length_stack_sp20_direct_accesses":stack,
        "direct_SP20_stores_after_TEE":direct_after_write,
        "any_alias_store_could_modify_SP20_excluded":False,
        "actual_decrypted_payload_output_observed":False,
        "verified_secure_service_success_required_for_copy":False,
        "secure_world_key_or_plaintext_recovered":False,
        "TEE_or_camera_firmware_executed":False,
        "raw_vendor_code_or_disassembly_exported":False,
    }

def selftest():
    graph={0:[4,8],4:[12],8:[16],12:[],16:[]}
    assert shortest_path(graph,0,16,forbidden={8}) is None
    assert shortest_path(graph,0,12)==[0,4,12]
    assert len(SHA)==64
    return {"status":"PASS_synthetic","checks":3,"original_firmware_loaded":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    x=p.parse_args()
    if not x.self_test and not x.firmware_root:p.error("--firmware-root required")
    d=selftest() if x.self_test else audit(x.firmware_root)
    x.output.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")
    print(json.dumps({
      "status":d.get("status","original_pinned_static"),
      "return_nodes_after_service":d.get("normal_returns_reachable_after_service"),
      "bypass_copy_normal_returns":d.get("normal_returns_with_bypass_path"),
      "key_or_plaintext_recovered":False},sort_keys=True))
if __name__=="__main__":main()
