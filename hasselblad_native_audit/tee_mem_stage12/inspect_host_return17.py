#!/usr/bin/env python3
"""Stage17: original X2D II host output-copy identity and service-status guard.

Follow the already verified two-memcpy / TEE command2 wrapper with CFG
reaching-definition analysis. Prove which incoming ABI argument becomes the
post-service memcpy destination and distinguish the shared FD+mapped-memory
fields. This is static host-side code, NOT proof of successful decryption,
dumped payloads, or a way to bypass authentication.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from inspect_cfg_sources14 import cfg,canon,def_origin

SOURCE="system/lib64/libfw_util.so"
SHA="3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d"
FN="plt_fw_verify_load2mem_with_heap_mask"
SERVICE=0x2344
OUTCOPY=0x23dc
INCOPY=0x2330
BRANCH=0x234c
MAX_DEFS=24

def read_original(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise ValueError("original_X2DII_file_digest_mismatch")
    with path.open("rb") as f:
        elf=ELFFile(f)
        dyn=elf.get_section_by_name(".dynsym")
        found=[s for s in dyn.iter_symbols() if s.name==FN and s["st_shndx"]!="SHN_UNDEF"]
        if len(found)!=1:raise ValueError("original_wrapper_missing")
        va,size=int(found[0]["st_value"]),int(found[0]["st_size"])
        section=elf.get_section_by_name(".text")
        off=va-int(section["sh_addr"])
        if size>4096 or off<0 or off+size>len(section.data()):raise ValueError("out_of_bounds")
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);md.detail=True
        insns=list(md.disasm(section.data()[off:off+size],va))
        if len(insns)*4!=size:raise ValueError("instruction_gap")
        return insns

def defs_with_abi_clobber(insns,edges,r):
    by={x.address:x for x in insns}
    first=insns[0].address
    values={first:{-1}}
    queue=[first]
    n=0
    while queue:
        va=queue.pop()
        ins=by[va]
        incoming=values[va]
        try:_,writes=ins.regs_access()
        except Exception:writes=[]
        written=any(canon(ins.reg_name(k))==r for k in writes)
        # Unlike simple Capstone regs_access, AAPCS64 demands that we
        # invalidate caller-saved x0..x18 on an opaque external call.
        if ins.mnemonic in ("bl","blr") and r<=18:
            written=True
        out={va} if written else incoming
        for nxt in edges[va]:
            if nxt not in values:
                values[nxt]=set(out);queue.append(nxt)
            elif not out.issubset(values[nxt]):
                values[nxt].update(out)
                if len(values[nxt])>MAX_DEFS:raise ValueError("too_many_reaching_defs")
                queue.append(nxt)
        n+=1
        if n>len(insns)*70:raise ValueError("CFG_over_budget")
    return values

def can_reach(graph,start,end):
    todo=[start];seen=set()
    while todo:
        x=todo.pop()
        if x==end:return True
        if x in seen:continue
        seen.add(x)
        todo.extend(graph.get(x,[]))
    return False

def local_reg(insns,at,reg):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    target=canon(reg)
    idx=next(i for i,x in enumerate(insns) if x.address==at)
    for p in reversed(insns[max(0,idx-26):idx]):
        if p.mnemonic in ("bl","blr","ret","b","br") or p.mnemonic.startswith(("b.","cb","tb")):
            return {"kind":"control_flow_boundary"}
        try:_,writes=p.regs_access()
        except Exception:continue
        if not any(canon(p.reg_name(k))==target for k in writes):continue
        o=p.operands
        row={"at_va":hex(p.address),"instruction_class":p.mnemonic}
        if len(o)>1 and o[0].type==ARM64_OP_REG and canon(p.reg_name(o[0].reg))==target:
            if p.mnemonic in ("mov","movz") and o[1].type==ARM64_OP_REG:
                row["kind"]="register_alias";row["source"]=p.reg_name(o[1].reg)
            elif p.mnemonic in ("ldr","ldur") and o[1].type==ARM64_OP_MEM:
                row["kind"]="memory_load";row["base"]=p.reg_name(o[1].mem.base)
                row["offset"]=int(o[1].mem.disp)
            elif p.mnemonic=="add" and len(o)>2 and o[1].type==ARM64_OP_REG and o[2].type==ARM64_OP_IMM:
                row["kind"]="address";row["base"]=p.reg_name(o[1].reg);row["offset"]=int(o[2].imm)
        return row
    return {"kind":"not_local"}

def audit(path):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG
    insns=read_original(path)
    by={x.address:x for x in insns}
    graph=cfg(insns)
    for va in (SERVICE,OUTCOPY,INCOPY,BRANCH):
        if va not in by:raise ValueError("missing_verified_instruction_site")
    bran=by[BRANCH]
    if bran.mnemonic!="cbz" or bran.operands[0].type!=ARM64_OP_REG or bran.reg_name(bran.operands[0].reg)!="w8":
        raise ValueError("unexpected_status_branch_shape")
    taken=int(bran.operands[-1].imm) if bran.operands[-1].type==ARM64_OP_IMM else None
    fall=BRANCH+4
    def flows():
        watched={0,1,2,3,4,5,6,7,20,21,22,23,24}
        return {r:defs_with_abi_clobber(insns,graph,r) for r in watched}
    active=flows()
    mapped=[]
    for name,site,reg in (("incoming_pre_service_buffer",INCOPY,"x23"),
                          ("incoming_pre_service_length",INCOPY,"w24"),
                          ("caller_output_buffer",OUTCOPY,"x20"),
                          ("mapped_ION_object",OUTCOPY,"x22")):
        res=def_origin(insns,site,reg,active)
        res["role"]=name
        mapped.append(res)
    original=by[BRANCH]
    raw_status=local_reg(insns,BRANCH,"w8")
    calls={
      "before_service":{"copy_site":hex(INCOPY),
                        "destination":local_reg(insns,INCOPY,"x0"),
                        "source":local_reg(insns,INCOPY,"x1"),
                        "length":local_reg(insns,INCOPY,"x2")},
      "TEE_service":{"call_site":hex(SERVICE),
                     "fd_argument":local_reg(insns,SERVICE,"x0"),
                     "returned_length_pointer":local_reg(insns,SERVICE,"x1")},
      "after_service":{"copy_site":hex(OUTCOPY),
                       "destination":local_reg(insns,OUTCOPY,"x0"),
                       "source":local_reg(insns,OUTCOPY,"x1"),
                       "returned_length":local_reg(insns,OUTCOPY,"x2")}}
    return {"schema":"hasselblad-stage17-original-host-buffer-return-path-v1",
        "source_sha256":SHA,
        "analyzed_instructions":len(insns),
        "original_wrapper":FN,
        "original_ABI_argument_origins":mapped,
        "host_buffer_copy_operations":calls,
        "post_service_branch":{
            "va":hex(BRANCH),"test_reg":"w8","value_origin":raw_status,
            "taken_reaches_output_copy":bool(taken is not None and can_reach(graph,taken,OUTCOPY)),
            "fallthrough_reaches_output_copy":can_reach(graph,fall,OUTCOPY)},
        "TEE_plaintext_actually_returned_proven":False,
        "secret_material_or_private_photographs_exported":False,
        "original_binary_executed":False,
        "raw_vendor_instructions_or_pseudocode_exported":False}

def synthetic():
    graph={0:[4,8],4:[12],8:[16],12:[],16:[]}
    assert can_reach(graph,0,16) and not can_reach(graph,16,4)
    assert canon("w20")==canon("x20")==20
    assert len(SHA)==64
    return {"status":"PASS_synthetic","checks":3,"original_code_loaded":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root/SOURCE)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_read_only"),
        "argument_origins_proven":sum(q["unique_incoming_ABI_argument_proven"]
                                for q in d.get("original_ABI_argument_origins",[])),
        "decrypted_plaintext_observed":False},sort_keys=True))
if __name__=="__main__":main()
