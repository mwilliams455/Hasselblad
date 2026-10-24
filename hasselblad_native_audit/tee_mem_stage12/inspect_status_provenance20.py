#!/usr/bin/env python3
"""Stage20: original X2D II host-side return-status provenance after TEE command 2.

Analyze the saved w19 source at the wrapper's move-to-w0, before the AArch64
callee-saved register restoration. Split paths by the zero/nonzero result of
the secure-service call. This is static, read-only AArch64 analysis only:
NO keys, DSP/TA decryption, vendor code execution or raw code exports.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from inspect_host_return17 import read_original,defs_with_abi_clobber,SOURCE,SHA,SERVICE,OUTCOPY
from inspect_cfg_sources14 import cfg,canon
from inspect_post_return18 import shortest_path,STATUS

RETVAL_MOV=0x23f8
SERVICE_RESULT_MOV=0x2348
RET_VA=0x2418

def describe(ins):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    v={"site_va":hex(ins.address),"instruction_class":ins.mnemonic}
    if len(ins.operands)>1:
        p=ins.operands[1]
        if p.type==ARM64_OP_REG:
            v["source_register"]=ins.reg_name(p.reg)
        elif p.type==ARM64_OP_IMM:
            x=int(p.imm)
            v["immediate"]=x if -65536<=x<=65536 else None
        elif p.type==ARM64_OP_MEM:
            v["source_memory_base"]=ins.reg_name(p.mem.base)
            v["source_memory_disp"]=int(p.mem.disp)
    return v

def case_for_status(insns,graph,label,branch_succ):
    by={i.address:i for i in insns}
    edges={k:list(v) for k,v in graph.items()}
    edges[STATUS]=[branch_succ]
    flow19=defs_with_abi_clobber(insns,edges,19)
    flow8=defs_with_abi_clobber(insns,edges,8)
    flow0=defs_with_abi_clobber(insns,edges,0)
    definitions=sorted(flow19.get(RETVAL_MOV,set()))
    results=[]
    for site in definitions:
        if site==-1:
            results.append({"definition_kind":"callee_saved_input",
                            "direct_service_result_proven":False})
            continue
        i=by[site]
        item=describe(i)
        source=item.get("source_register")
        direct=False
        if i.mnemonic in ("mov","movz") and source in ("w8","x8"):
            x=sorted(flow8.get(site,set()))
            item["w8_reaching_definitions"]=[hex(z) if z>=0 else "entry" for z in x]
            direct=(x==[SERVICE_RESULT_MOV] and
                    by[SERVICE_RESULT_MOV].mnemonic=="mov" and
                    by[SERVICE_RESULT_MOV].reg_name(by[SERVICE_RESULT_MOV].operands[1].reg) in ("w0","x0"))
        elif i.mnemonic in ("mov","movz") and source in ("w0","x0"):
            x=sorted(flow0.get(site,set()))
            item["w0_reaching_definitions"]=[hex(z) if z>=0 else "entry" for z in x]
            direct=(x==[SERVICE])
        item["direct_service_result_proven"]=direct
        results.append(item)
    return {"case":label,
            "edge_target_va":hex(branch_succ),
            "reaches_return_assignment":shortest_path(edges,branch_succ,RETVAL_MOV) is not None,
            "w19_reaching_definitions":results,
            "unique_w19_definition":len(definitions)==1,
            "unambiguously_returns_service_status":
                len(results)==1 and len(definitions)==1 and
                results[0]["direct_service_result_proven"]}

def audit(root):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM
    insns=read_original(root/SOURCE)
    by={i.address:i for i in insns}
    for va in (STATUS,SERVICE,SERVICE_RESULT_MOV,OUTCOPY,RETVAL_MOV,RET_VA):
        if va not in by:raise ValueError("required_original_instruction_absent")
    mov=by[RETVAL_MOV]
    if (mov.mnemonic!="mov" or len(mov.operands)!=2 or
        any(op.type!=ARM64_OP_REG for op in mov.operands) or
        mov.reg_name(mov.operands[0].reg)!="w0" or
        mov.reg_name(mov.operands[1].reg)!="w19"):
        raise ValueError("expected_original_return_assignment_changed")
    branch=by[STATUS]
    if branch.mnemonic!="cbz" or branch.operands[-1].type!=ARM64_OP_IMM:
        raise ValueError("original_return_branch_changed")
    target=int(branch.operands[-1].imm)
    fallthrough=STATUS+4
    if target not in by or fallthrough not in by:raise ValueError("branch_leaves_wrapper")
    graph=cfg(insns)
    cases=[
      case_for_status(insns,graph,"service_result_zero",target),
      case_for_status(insns,graph,"service_result_nonzero",fallthrough),
    ]
    return {"schema":"hasselblad-stage20-original-TEE-command2-return-status-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "original_host_library_sha256":SHA,
            "secure_result_to_w8_site":hex(SERVICE_RESULT_MOV),
            "status_to_public_return_register_site":hex(RETVAL_MOV),
            "normal_return_site":hex(RET_VA),
            "cases":cases,
            "all_normal_paths_from_TEE_call_copy_back_before_return":True,
            "TEE_successful_decryption_established":False,
            "secret_material_or_plaintext_extracted":False,
            "vendor_pseudocode_or_original_code_bytes_exported":False,
            "original_camera_accessed":False}

def selftest():
    graph={0:[4,8],4:[12],8:[16],12:[],16:[]}
    assert shortest_path(graph,4,12)==[4,12]
    assert shortest_path(graph,8,12) is None
    assert canon("w19")==canon("x19")==19
    return {"status":"PASS_synthetic","checks":3,"vendor_binary_loaded":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if not a.self_test and not a.firmware_root:ap.error("--firmware-root required")
    d=selftest() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":d.get("status","original_verified"),
                      "cases":len(d.get("cases",[])),
                      "status_aliased_cases":sum(q["unambiguously_returns_service_status"] for q in d.get("cases",[])),
                      "decryption_proven":False},sort_keys=True))
if __name__=="__main__":main()
