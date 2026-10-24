#!/usr/bin/env python3
"""Stage9: original X2D II command-3/6 CFG and command-1/2/3/6 TEEC operation contracts.

Static only, on hash-pinned 1.3.16.2 original host ELFs.
No original instruction text/bytes, decompiled code, photographic pixels,
key candidates or secure-world material are emitted.
A candidate stack write is NOT automatically a proven paramTypes value.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

UTIL = "system/lib64/libfw_util.so"
CA = "system/lib64/libfw_util_ca.so"
SHA = {
    UTIL: "3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d",
    CA: "96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b",
}
WRAPPER = "plt_fw_verify_file"
COMMAND_FUNCTIONS = {
    "fw_util_load": 1,
    "fw_util_verify_load2ion": 2,
    "fw_util_verify_init": 3,
    "fw_util_verify_init_ext": 6,
}
PARAM_KINDS = {
    0:"NONE",1:"VALUE_INPUT",2:"VALUE_OUTPUT",3:"VALUE_INOUT",
    5:"TEMP_INPUT",6:"TEMP_OUTPUT",7:"TEMP_INOUT",
    12:"WHOLE",13:"PARTIAL_INPUT",14:"PARTIAL_OUTPUT",15:"PARTIAL_INOUT",
}
MAX_SIZE = 4*1024*1024
MAX_FUNC = 4096

def c_name(ins, reg):
    try:return ins.reg_name(reg)
    except Exception:return ""

def is_branch_cond(m):
    return m.startswith("b.") or m in ("cbz","cbnz","tbz","tbnz")

def parse_elf(path, expected):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    if path.stat().st_size > MAX_SIZE:raise ValueError("unexpected_ELF_size")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("unexpected_original_ELF_hash")
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("not_aarch64")
        code=elf.get_section_by_name(".text")
        plt=elf.get_section_by_name(".plt")
        rel=elf.get_section_by_name(".rela.plt")
        dyn=elf.get_section_by_name(".dynsym")
        if not all((code,plt,rel,dyn)):raise ValueError("missing_elf_components")
        symbols={}
        for secn in (".dynsym",".symtab"):
            sec=elf.get_section_by_name(secn)
            if not sec:continue
            for s in sec.iter_symbols():
                if not s.name or s["st_shndx"]=="SHN_UNDEF" or s["st_info"]["type"]!="STT_FUNC":
                    continue
                addr,size=int(s["st_value"]),int(s["st_size"])
                if size and s.name not in symbols:symbols[s.name]=(addr,size)
        pltmap={}
        for i,x in enumerate(rel.iter_relocations()):
            pltmap[int(plt["sh_addr"])+32+16*i]=dyn.get_symbol(x["r_info_sym"]).name
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        md.detail=True
        raw=code.data(); origin=int(code["sh_addr"])
        return md,raw,origin,symbols,pltmap

def get_function(index,name):
    md,raw,origin,symbols,pltmap=index
    if name not in symbols:return None
    addr,size=symbols[name]
    off=addr-origin
    if not 0<=off<len(raw) or not 0<size<=MAX_FUNC or off+size>len(raw):
        raise ValueError("function_bounds_error_"+name)
    ins=list(md.disasm(raw[off:off+size],addr))
    if len(ins)*4!=size:raise ValueError("unexpected_decoding_gap_"+name)
    return ins

def successors(ins, addresses):
    from capstone.arm64 import ARM64_OP_IMM
    m=ins.mnemonic; follow=ins.address+ins.size
    if m in ("ret","eret","br","braa","brab"):
        return []
    if m=="b" and ins.operands and ins.operands[-1].type==ARM64_OP_IMM:
        dest=int(ins.operands[-1].imm)
        return [("unconditional",dest)] if dest in addresses else []
    if is_branch_cond(m):
        if not ins.operands or ins.operands[-1].type!=ARM64_OP_IMM:
            return [("unresolved",follow)] if follow in addresses else []
        dest=int(ins.operands[-1].imm)
        out=[]
        if dest in addresses:out.append(("taken",dest))
        if follow in addresses:out.append(("fallthrough",follow))
        return out
    return [("next",follow)] if follow in addresses else []

def reach_targets(start,graph,terminal,limit=3000):
    seen=set(); found=set(); pending=[start]
    while pending:
        a=pending.pop()
        if a in seen:continue
        seen.add(a)
        if len(seen)>limit:raise ValueError("control_flow_budget_exceeded")
        if a in terminal:
            found.add(terminal[a])
            continue
        for _,v in graph.get(a,[]):pending.append(v)
    return sorted(found)

def operand_summary(ins, op):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG
    if op.type==ARM64_OP_REG:return {"reg":c_name(ins,op.reg)}
    if op.type==ARM64_OP_IMM:
        val=int(op.imm)
        return {"imm":val if -1<=val<=0xffff else "non_small_imm"}
    return {"type":"other"}

def nearest_flag_op(insns,index,limit=14):
    """Return only the nearest local flag-setting operation and operand types."""
    for i in range(index-1,max(-1,index-limit-1),-1):
        ins=insns[i]
        if ins.mnemonic in ("b","bl","blr","ret","br") or is_branch_cond(ins.mnemonic):
            break
        if ins.mnemonic in ("cmp","cmn","tst","subs","ands"):
            return {"site_va":hex(ins.address),"mnemonic":ins.mnemonic,
                    "operands":[operand_summary(ins,x) for x in ins.operands[:3]],
                    "flag_definition_in_local_window":True}
    return {"flag_definition_in_local_window":False}

def wrapper_cfg(index):
    from capstone.arm64 import ARM64_OP_IMM
    insns=get_function(index,WRAPPER)
    if not insns:raise ValueError("missing_original_wrapper")
    pltmap=index[4]
    callsites={}
    for ins in insns:
        if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:
            continue
        target=pltmap.get(int(ins.operands[0].imm))
        if target in ("fw_util_verify_init","fw_util_verify_init_ext"):
            callsites[ins.address]=target
    if len(callsites)!=2 or set(callsites.values())!={"fw_util_verify_init","fw_util_verify_init_ext"}:
        raise ValueError("inconsistent_original_init_calls")
    addrs={x.address for x in insns}
    graph={ins.address:successors(ins,addrs) for ins in insns}
    from_entry=reach_targets(insns[0].address,graph,callsites)
    candidates=[]
    for ix,ins in enumerate(insns):
        if not is_branch_cond(ins.mnemonic):continue
        edges=graph[ins.address]
        if len(edges)!=2:continue
        targets={label:reach_targets(dst,graph,callsites) for label,dst in edges}
        if targets.get("taken")==targets.get("fallthrough"):continue
        reachable=set(v for ts in targets.values() for v in ts)
        if not reachable:continue
        row={"site_va":hex(ins.address),"branch_class":ins.mnemonic,
             "taken_reaches":targets.get("taken",[]),
             "fallthrough_reaches":targets.get("fallthrough",[]),
             "predicate_operands":[operand_summary(ins,x) for x in ins.operands[:-1]][:3],
             "flag_source":nearest_flag_op(insns,ix) if ins.mnemonic.startswith("b.") else None}
        row["discriminates_init_paths"]=(len(targets.get("taken",[]))==1 and
                                        len(targets.get("fallthrough",[]))==1 and
                                        targets["taken"]!=targets["fallthrough"])
        candidates.append(row)
    return {"wrapper":WRAPPER,"wrapper_entry_va":hex(insns[0].address),
            "instructions_decoded":len(insns),
            "extended_call_sites":[hex(a) for a,n in callsites.items() if n=="fw_util_verify_init_ext"],
            "basic_call_sites":[hex(a) for a,n in callsites.items() if n=="fw_util_verify_init"],
            "entry_reaches":from_entry,
            "conditional_candidates":candidates[:24],
            "candidate_count":len(candidates),
            "discriminating_branches_found":sum(int(c["discriminates_init_paths"]) for c in candidates),
            "path_reachability_is_static_not_runtime":True,
            "branch_predicate_not_proven_if_no_local_flag_source":True}

def nearest_reg_literal(insns,i,register,max_lookback=36):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG
    if register in ("wzr","xzr"):return {"kind":"constant","value":0}
    regbase=register.replace("w","x",1) if register.startswith("w") else register
    for j in range(i-1,max(-1,i-max_lookback-1),-1):
        x=insns[j]
        if x.mnemonic in ("b","bl","br","blr","ret") or is_branch_cond(x.mnemonic):
            return {"kind":"control_flow_boundary"}
        try:_,wr=x.regs_access()
        except Exception:continue
        def same(a,b):return a.replace("w","x",1)==b.replace("w","x",1)
        if not any(same(c_name(x,v),regbase) for v in wr):continue
        if (x.operands and x.operands[0].type==ARM64_OP_REG and
                same(c_name(x,x.operands[0].reg),regbase)):
            if x.mnemonic in ("mov","movz") and len(x.operands)>1:
                src=x.operands[1]
                if src.type==ARM64_OP_IMM:return {"kind":"constant","value":int(src.imm)}
                if src.type==ARM64_OP_REG and c_name(x,src.reg) in ("wzr","xzr"):
                    return {"kind":"constant","value":0}
                if src.type==ARM64_OP_REG:return {"kind":"forwarded_register",
                    "reg":c_name(x,src.reg)}
            return {"kind":"nonliteral_definition","instruction_class":x.mnemonic}
        return {"kind":"implicit_write"}
    return {"kind":"not_observed"}

def find_operation_pointer(insns,idx):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM
    for i in range(idx-1,max(-1,idx-35),-1):
        x=insns[i]
        if x.mnemonic in ("bl","b","ret","br","blr") or is_branch_cond(x.mnemonic):
            break
        if len(x.operands)<2 or x.operands[0].type!=ARM64_OP_REG:
            continue
        dest=c_name(x,x.operands[0].reg)
        if dest not in ("x2","w2"):continue
        if x.mnemonic=="add" and len(x.operands)==3 and x.operands[1].type==ARM64_OP_REG and x.operands[2].type==ARM64_OP_IMM:
            if c_name(x,x.operands[1].reg)=="sp":
                return {"kind":"stack_pointer_offset","base":"sp","offset":int(x.operands[2].imm),
                        "assignment_va":hex(x.address)}
        if x.mnemonic=="mov" and x.operands[1].type==ARM64_OP_REG and c_name(x,x.operands[1].reg)=="sp":
            return {"kind":"stack_pointer_offset","base":"sp","offset":0,
                    "assignment_va":hex(x.address)}
        return {"kind":"other_register_definition","instruction_class":x.mnemonic}
    return {"kind":"not_found"}

def operation_contract(index,name,known_command):
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_MEM,ARM64_OP_REG
    insns=get_function(index,name)
    if not insns:return {"function":name,"present":False}
    pltmap=index[4]
    calls=[]
    invoke=[]
    for i,ins in enumerate(insns):
        if ins.mnemonic!="bl" or not ins.operands or ins.operands[0].type!=ARM64_OP_IMM:continue
        target=pltmap.get(int(ins.operands[0].imm))
        if target=="TEEC_InvokeCommand":invoke.append((i,ins))
        if target in ("TEEC_AllocateSharedMemory","TEEC_RegisterSharedMemoryFileDescriptor","TEEC_ReleaseSharedMemory"):
            calls.append({"site_va":hex(ins.address),"api":target})
    for ix,call in invoke:
        pointer=find_operation_pointer(insns,ix)
        param_writes=[]
        if pointer["kind"]=="stack_pointer_offset":
            param_address=pointer["offset"]+4
            for j,ins in enumerate(insns[:ix]):
                if ins.mnemonic not in ("str","stur") or len(ins.operands)<2:
                    continue
                if ins.operands[0].type!=ARM64_OP_REG or ins.operands[1].type!=ARM64_OP_MEM:
                    continue
                mem=ins.operands[1].mem
                if c_name(ins,mem.base)!="sp" or int(mem.disp)!=param_address:
                    continue
                src_reg=c_name(ins,ins.operands[0].reg)
                if not src_reg.startswith("w"):continue  # paramTypes is uint32_t.
                val=nearest_reg_literal(insns,j,src_reg)
                row={"store_va":hex(ins.address),"relative_to_operation":4,
                     "source_register":src_reg,"value_provenance":val}
                if val.get("kind")=="constant" and val["value"]<=0xffff:
                    code=val["value"]
                    row["candidate_param_types_hex"]=hex(code)
                    row["candidate_param_kinds"]=[PARAM_KINDS.get((code>>(4*k))&15,"UNKNOWN")
                                                  for k in range(4)]
                    row["static_store_not_path_sensitive"]=True
                param_writes.append(row)
        # If multiple reachable stores can write the same slot, don't assert final runtime value.
        resolved=[w["candidate_param_types_hex"] for w in param_writes
                  if "candidate_param_types_hex" in w]
        value=resolved[0] if len(resolved)==1 and len(param_writes)==1 else None
        return {"function":name,"entry_va":hex(insns[0].address),
                "expected_command_id_from_verified_prior_stage":known_command,
                "TEEC_InvokeCommand_va":hex(call.address),
                "operation_pointer":pointer,
                "candidate_paramtype_writes":param_writes[:12],
                "candidate_paramtype_write_count":len(param_writes),
                "unambiguous_static_paramtype_store":value,
                "memory_management_calls":calls[:24],
                "memory_transfer_direction_from_runtime_proven":False,
                "caller_owned_decrypted_plaintext_return_proven":False,
                "static_stack_pointer_layout_assumed_stable":True}
    return {"function":name,"present":True,"TEEC_InvokeCommand_count":0,
            "reason":"no_direct_TEEC_InvokeCommand"}

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("firmware_version_mismatch")
    util=parse_elf(root/UTIL,SHA[UTIL])
    ca=parse_elf(root/CA,SHA[CA])
    result={"schema":"hasselblad-rea-tee-stage9-original-init-branch-operation-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "branch":wrapper_cfg(util),
            "operations":[operation_contract(ca,n,v) for n,v in COMMAND_FUNCTIONS.items()],
            "decryption_key_or_plaintext_recovered":False,
            "trusted_application_decompiled":False,
            "vendor_code_executed":False,
            "raw_vendor_instruction_or_pseudocode_exported":False,
            "probe_is_read_only":True,
            "cross_function_interprocedural_key_equivalence_proven":False}
    return result

def synthetic():
    g={0:[("taken",4),("fallthrough",8)],4:[("next",12)],8:[("next",16)],
       12:[],16:[]}
    term={12:"cmd6",16:"cmd3"}
    assert reach_targets(4,g,term)==["cmd6"]
    assert reach_targets(8,g,term)==["cmd3"]
    assert [PARAM_KIN[(0x11df>>(4*k))&15] for k in range(4)]==[
        "PARTIAL_INOUT","PARTIAL_INPUT","VALUE_INPUT","VALUE_INPUT"]
    assert is_branch_cond("cbnz") and is_branch_cond("b.eq") and not is_branch_cond("bl")
    return {"status":"PASS_synthetic","tests":4,"original_firmware_loaded":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    out=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":out.get("status","original_static_audit"),
      "branch_candidates":out.get("branch",{}).get("candidate_count"),
      "discriminators":out.get("branch",{}).get("discriminating_branches_found"),
      "operation_contracts":len(out.get("operations",[])),
      "vendor_key_exported":False},sort_keys=True))

if __name__=="__main__": main()
