#!/usr/bin/env python3
"""Stage24: X2D II original eFuse secure-session destination and command ID.

Hash-pinned original libamt_util.so. Read-only static disassembly around the
already verified efuse_pro TEEC_OpenSession(x2=UUID) and
TEEC_InvokeCommand(w1=commandID). Compare actual UUID memory addresses
with filenames of the two known encrypted TAs, rather than guessing that
a string present elsewhere in the library is actually used by efuse_pro.

No vendor code execution, eFuse programming, cryptographic secrets,
original instruction/pseudocode bytes or private photographs in public JSON.
"""
from __future__ import annotations
import argparse,hashlib,json,uuid
from pathlib import Path

FILE="system/lib64/libamt_util.so"
SHA="63a4addc9179587363bdc8f045d9cb4686855aa413873db8b5fdcd15bdab5902"
TARGET_FUNCS=("efuse_pro","pro_state","sec_debug_state")
TA_NAMES=(
 "09db16c0-873b-4fed-b87e-a5d2b86293a2",
 "e91c9402-64a0-470f-88e7-bf5d3c606b6a",
)
MAX_LOOKBACK=70

def canon(name):
    if name and name[0] in "wx" and name[1:].isdigit():return "x"+name[1:]
    return name

def backing_elf(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    whole=path.read_bytes()
    if len(whole)>2*1024*1024 or hashlib.sha256(whole).hexdigest()!=SHA:
        raise ValueError("unexpected_original_efuse_source")
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("not_AArch64")
        dyn=elf.get_section_by_name(".dynsym")
        symbols={}
        for nm in (".dynsym",".symtab"):
            sec=elf.get_section_by_name(nm)
            if not sec:continue
            for s in sec.iter_symbols():
                if s.name in TARGET_FUNCS and s["st_info"]["type"]=="STT_FUNC" and s["st_shndx"]!="SHN_UNDEF":
                    symbols[s.name]=(int(s["st_value"]),int(s["st_size"]))
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        if not all((plt,rela,dyn)):raise ValueError("missing_PLT")
        pltmap={int(plt["sh_addr"])+32+16*k:dyn.get_symbol(r["r_info_sym"]).name
                for k,r in enumerate(rela.iter_relocations())}
        text=elf.get_section_by_name(".text")
        raw=text.data()
        origin=int(text["sh_addr"])
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);md.detail=True
        funcs={}
        for nm in TARGET_FUNCS:
            if nm not in symbols:continue
            va,size=symbols[nm]
            offset=va-origin
            if not 0<size<8192 or offset<0 or offset+size>len(raw):
                raise ValueError("unexpected_function_extent_"+nm)
            items=list(md.disasm(raw[offset:offset+size],va))
            if len(items)*4!=size:raise ValueError("AArch64_decoding_gap_"+nm)
            funcs[nm]=items
        images=[]
        for ident in TA_NAMES:
            u=uuid.UUID(ident)
            for kind,payload in (("RFC4122_be",u.bytes),("TEEC_le",u.bytes_le)):
                start=0
                while True:
                    index=whole.find(payload,start)
                    if index<0:break
                    possible=[]
                    for segment in elf.iter_segments():
                        if segment["p_type"]!="PT_LOAD":continue
                        fo=int(segment["p_offset"]);sz=int(segment["p_filesz"])
                        if fo<=index and index+len(payload)<=fo+sz:
                            possible.append(hex(int(segment["p_vaddr"])+index-fo))
                    images.append({"TA_filename_UUID":ident,"encoding":kind,
                                   "file_offset":hex(index),
                                   "possible_memory_vas":possible})
                    start=index+1
    return funcs,pltmap,images

def current_writer(insns, idx, name, limit=MAX_LOOKBACK):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    goal=canon(name)
    for k in range(idx-1,max(-1,idx-limit-1),-1):
        ins=insns[k]
        if ins.mnemonic in ("b","bl","br","blr","ret","eret") or ins.mnemonic.startswith(("b.","cb","tb")):
            return {"kind":"crosses_control_flow_or_call_boundary"}
        try:_,writes=ins.regs_access()
        except Exception:continue
        if not any(canon(ins.reg_name(r))==goal for r in writes):continue
        result={"kind":"written","site_va":hex(ins.address),
                "instruction_class":ins.mnemonic,"instruction_index":k}
        if not ins.operands or ins.operands[0].type!=ARM64_OP_REG:
            return result
        if canon(ins.reg_name(ins.operands[0].reg))!=goal:return result
        o=ins.operands
        if ins.mnemonic in ("mov","movz","adr","adrp") and len(o)>=2:
            if o[1].type==ARM64_OP_REG:
                result["operand_kind"]="register"
                result["register_source"]=ins.reg_name(o[1].reg)
            elif o[1].type==ARM64_OP_IMM:
                result["operand_kind"]="immediate"
                result["immediate_value"]=int(o[1].imm)
        elif ins.mnemonic in ("add","sub") and len(o)>=3:
            if o[1].type==ARM64_OP_REG and o[2].type==ARM64_OP_IMM:
                result["operand_kind"]="base_plus_constant"
                result["register_source"]=ins.reg_name(o[1].reg)
                result["immediate_value"]=int(o[2].imm)*(1 if ins.mnemonic=="add" else -1)
        elif ins.mnemonic in ("ldr","ldur") and len(o)>=2 and o[1].type==ARM64_OP_MEM:
            result["operand_kind"]="load_from_memory"
            result["memory_base"]=ins.reg_name(o[1].mem.base)
            result["memory_offset"]=int(o[1].mem.disp)
        return result
    return {"kind":"unresolved_no_local_writer"}

def resolve_source(insns,idx,reg,steps=0,seen=None):
    if seen is None:seen=set()
    if steps>6 or (idx,canon(reg)) in seen:return {"kind":"bounded_unknown"}
    seen.add((idx,canon(reg)))
    writer=current_writer(insns,idx,reg)
    if writer["kind"]!="written":return writer
    k=writer["instruction_index"]
    result={"writer_va":writer["site_va"],
            "kind":writer.get("operand_kind","unclassified"),
            "class":writer["instruction_class"]}
    typ=writer.get("operand_kind")
    if typ=="immediate":
        result["resolved_small_constant"]=writer["immediate_value"] if writer["immediate_value"]<=65535 else None
        if writer["instruction_class"] in ("adr","adrp"):
            result["absolute_address_va"]=hex(writer["immediate_value"])
    elif typ=="register":
        if writer["register_source"] in ("wzr","xzr"):
            result["resolved_small_constant"]=0
        else:
            result["input"]=resolve_source(insns,k,writer["register_source"],steps+1,seen)
    elif typ=="base_plus_constant":
        base=writer["register_source"]
        result["offset"]=writer["immediate_value"]
        if base=="sp":
            result["stack_based_argument"]=True
        else:
            previous=resolve_source(insns,k,base,steps+1,seen)
            result["base_provenance"]=previous
            baseva=previous.get("absolute_address_va")
            if baseva is not None:
                result["absolute_address_va"]=hex(int(baseva,16)+result["offset"])
    elif typ=="load_from_memory":
        result["memory_base"]=writer["memory_base"]
        result["memory_offset"]=writer["memory_offset"]
    return result

def search_addresses(obj):
    acc=[]
    if isinstance(obj,dict):
        if "absolute_address_va" in obj:acc.append(obj["absolute_address_va"])
        for value in obj.values():acc+=search_addresses(value)
    elif isinstance(obj,list):
        for value in obj:acc+=search_addresses(value)
    return acc

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("wrong_firmware")
    funcs,plt,uuidmatches=backing_elf(root/FILE)
    from capstone.arm64 import ARM64_OP_IMM
    records=[]
    for name in TARGET_FUNCS:
        if name not in funcs:continue
        insns=funcs[name]
        for i,ins in enumerate(insns):
            if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:continue
            api=plt.get(int(ins.operands[0].imm))
            if api not in ("TEEC_OpenSession","TEEC_InvokeCommand"):continue
            arg="x2" if api=="TEEC_OpenSession" else "w1"
            origin=resolve_source(insns,i,arg)
            vas=search_addresses(origin)
            match=[]
            for m in uuidmatches:
                if set(vas).intersection(m["possible_memory_vas"]):
                    match.append({"TA_filename_UUID":m["TA_filename_UUID"],
                                  "encoding":m["encoding"],
                                  "referenced_memory_va":list(set(vas).intersection(m["possible_memory_vas"]))})
            records.append({"function":name,"call_va":hex(ins.address),
                            "api":api,"relevant_ABI_argument":arg,
                            "static_register_provenance":origin,
                            "exact_UUID_virtual_address_match_candidates":match,
                            "no_UUID_match_does_not_exclude_stack_construction":True})
    return {"schema":"hasselblad-stage24-original-efuse-TEE-session-UUID-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "original_elf_sha256":SHA,
            "known_TA_UUID_literal_locations":uuidmatches[:20],
            "resolved_relevant_tee_calls":records,
            "known_key_material_extracted":False,
            "eFuse_function_executed":False,
            "encrypted_TA_decompiled":False,
            "UUID_bytes_in_library_do_not_alone_prove_session_selection":True,
            "vendor_machine_code_or_decompilation_exported":False}

def synthetic():
    assert canon("w1")==canon("x1")=="x1"
    assert len(TA_NAMES)==2 and len(TARGET_FUNCS)==3
    assert len(SHA)==64
    return {"status":"PASS_synthetic","checks":3,"original_firmware_loaded":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if not a.self_test and not a.firmware_root:ap.error("--firmware-root required")
    o=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":o.get("status","original_read_only"),
       "TEE_call_count":len(o.get("resolved_relevant_tee_calls",[])),
       "session_UUID_exact_match_count":sum(len(x["exact_UUID_virtual_address_match_candidates"])
            for x in o.get("resolved_relevant_tee_calls",[]) if x["api"]=="TEEC_OpenSession"),
       "keys_recovered":False},sort_keys=True))
if __name__=="__main__":main()
