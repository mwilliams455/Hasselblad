#!/usr/bin/env python3
"""Stage16: verify original X2D II userland post-TEE memory-copy interface.

The previous Stage15 command2 p0 links to an ION/FD registered shared-memory
object and is declared PARTIAL_INOUT. This checks the outer libfw_util.so
wrapper for a host-side copy after command2 returns, without assuming the
copied bytes are decrypted plaintext. No original code is executed or exported.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from inspect_cfg_sources14 import cfg,canon

SOURCE="system/lib64/libfw_util.so"
EXPECTED_SHA="3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d"
FN="plt_fw_verify_load2mem_with_heap_mask"
CALLS={"0x2330":"memcpy","0x2344":"fw_util_verify_load2ion","0x23dc":"memcpy"}

def get_original(path):
    from elftools.elf.elffile import ELFFile
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED_SHA:raise ValueError("wrong_original_elf")
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("not_AArch64")
        dyn=elf.get_section_by_name(".dynsym")
        sym=[x for x in dyn.iter_symbols() if x.name==FN and x["st_shndx"]!="SHN_UNDEF"]
        if len(sym)!=1:raise ValueError("original_function_absent")
        start,size=int(sym[0]["st_value"]),int(sym[0]["st_size"])
        sec=elf.get_section_by_name(".text")
        off=start-int(sec["sh_addr"])
        if off<0 or size>4096:raise ValueError("function_over_bound")
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);md.detail=True
        insns=list(md.disasm(sec.data()[off:off+size],start))
        if len(insns)*4!=size:raise ValueError("decode_gap")
        plt=elf.get_section_by_name(".plt");rela=elf.get_section_by_name(".rela.plt")
        names={}
        for j,rel in enumerate(rela.iter_relocations()):
            names[int(plt["sh_addr"])+32+16*j]=dyn.get_symbol(rel["r_info_sym"]).name
        return insns,names

def path_exists(graph,src,dest):
    todo=[src];seen=set()
    while todo:
        a=todo.pop()
        if a==dest:return True
        if a in seen:continue
        seen.add(a)
        if len(seen)>1000:raise ValueError("reach_budget_exceeded")
        todo.extend(graph.get(a,[]))
    return False

def recent_definition(insns,index,reg,max_steps=48):
    """Same-basic-block nearest register definition, with bounded alias."""
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    target=canon(reg)
    for j in range(index-1,max(-1,index-max_steps-1),-1):
        ins=insns[j]
        if ins.mnemonic in ("bl","blr","ret","b","br") or ins.mnemonic.startswith(("b.","cb","tb")):
            return {"kind":"crosses_call_or_control_flow"}
        try:_,wr=ins.regs_access()
        except Exception:continue
        if not any(canon(ins.reg_name(r))==target for r in wr):continue
        o=ins.operands
        row={"site_va":hex(ins.address),"instruction_class":ins.mnemonic}
        if len(o)>1 and o[0].type==ARM64_OP_REG and canon(ins.reg_name(o[0].reg))==target:
            if ins.mnemonic in ("mov","movz"):
                if o[1].type==ARM64_OP_REG:
                    row["kind"]="alias";row["source"]=ins.reg_name(o[1].reg)
                elif o[1].type==ARM64_OP_IMM:
                    row["kind"]="literal";row["number"]=int(o[1].imm) if 0<=int(o[1].imm)<=65535 else None
            elif ins.mnemonic in ("ldr","ldur","ldrsw","ldrb") and o[1].type==ARM64_OP_MEM:
                row["kind"]="load";row["base"]=ins.reg_name(o[1].mem.base);row["offset"]=int(o[1].mem.disp)
            elif ins.mnemonic in ("add","sub") and len(o)>2 and o[1].type==ARM64_OP_REG and o[2].type==ARM64_OP_IMM:
                row["kind"]="pointer_arithmetic"
                row["source"]=ins.reg_name(o[1].reg)
                row["offset"]=int(o[2].imm)*(1 if ins.mnemonic=="add" else -1)
        return row
    return {"kind":"not_found_in_basic_block"}

def evaluate(insns,pltmap):
    from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG
    addresses={x.address for x in insns}
    graph=cfg(insns)
    matched={}
    for i,ins in enumerate(insns):
        if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:continue
        nm=pltmap.get(int(ins.operands[0].imm))
        if hex(ins.address) in CALLS:
            if nm!=CALLS[hex(ins.address)]:raise ValueError("original_call_target_changed")
            matched[ins.address]=(i,nm)
    if len(matched)!=3:raise ValueError("expected_three_original_calls")
    calls=[]
    for addr,(idx,name) in sorted(matched.items()):
        refs={f"x{i}":recent_definition(insns,idx,f"x{i}") for i in range(3)}
        calls.append({"va":hex(addr),"target":name,"argument_definitions":refs})
    start=0x2348
    after=0x23dc
    if start not in addresses:raise ValueError("post_service_path_missing")
    selection=[]
    for ins in insns:
        if 0x2344<ins.address<after and (ins.mnemonic.startswith(("b.","cb","tb"))):
            detail={"va":hex(ins.address),"class":ins.mnemonic}
            if ins.operands and ins.operands[0].type==ARM64_OP_REG:
                detail["test_reg"]=ins.reg_name(ins.operands[0].reg)
            selection.append(detail)
    # No assumption about branch outcomes or returned bytes; only static CFG.
    return {"original_host_wrapper":FN,"entry_va":hex(insns[0].address),
            "instruction_count":len(insns),
            "call_sequence":calls,
            "post_service_memcpy_reachable_from_CA_return":path_exists(graph,start,after),
            "conditional_branches_between_service_return_and_copy":selection[:20],
            "post_service_copy_source_points_to_ION_proven":False,
            "caller_output_is_decrypted_plaintext_proven":False,
            "secure_service_runtime_success_proven":False,
            "source_trace_is_same_basic_block_only":True}

def audit(root):
    insns,names=get_original(root/SOURCE)
    return {"schema":"hasselblad-stage16-original-post-TEE-copy-audit-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":EXPECTED_SHA,
            "wrapper":evaluate(insns,names),
            "no_original_user_or_camera_code_executed":True,
            "no_original_bytes_or_vendor_disassembly_exported":True,
            "no_decrypted_TA_or_TBIE_key_recovered":True}

def synthetic():
    graph={0:[4],4:[8],8:[]}
    assert path_exists(graph,0,8) and not path_exists(graph,8,0)
    assert len(CALLS)==3 and FN.startswith("plt_")
    return {"status":"PASS_synthetic","checks":3,"original_input_used":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_verifier_audited"),
      "return_to_memcpy_path":d.get("wrapper",{}).get("post_service_memcpy_reachable_from_CA_return"),
      "secure_key_recovered":False},sort_keys=True))
if __name__=="__main__":main()
