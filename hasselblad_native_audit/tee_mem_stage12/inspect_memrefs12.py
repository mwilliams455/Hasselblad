#!/usr/bin/env python3
"""X2D II Stage12: bounded, original host-side TEE shared-memory mapping.

Static analysis only. Input is the hash-pinned, previously extracted X2D II
system/lib64/libfw_util_ca.so. Do not execute vendor code. Public JSON contains
stack offsets, operand/register provenance and API names only, never firmware
bytes, plaintext/key candidates, camera images, raw disassembly, or strings.
Every stack-field association is labelled structural, not secure-world behaviour.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SOURCE="system/lib64/libfw_util_ca.so"
SOURCE_SHA256="96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b"
SPEC={
 "fw_util_verify_init_ext":{"command":6,"invoke":0x1ef8,"operation_sp":192,"paramTypes":0x1ddd,
     "expected_allocations":3,"expected_copies":3},
 "fw_util_verify_load2ion":{"command":2,"invoke":0x18d8,"operation_sp":168,"paramTypes":0x11df,
     "expected_allocations":1,"expected_copies":1},
 "fw_util_load":{"command":1,"invoke":0x162c,"operation_sp":184,"paramTypes":0x11dd,
     "expected_allocations":1,"expected_copies":0},
 "fw_util_verify_init":{"command":3,"invoke":0x1b5c,"operation_sp":120,"paramTypes":0x000d,
     "expected_allocations":1,"expected_copies":1},
}
ALLOWED_CALLS={
 "TEEC_AllocateSharedMemory","TEEC_RegisterSharedMemoryFileDescriptor",
 "TEEC_InvokeCommand","TEEC_ReleaseSharedMemory","strncpy","memcpy",
 "TEEC_OpenSession","TEEC_CloseSession"
}
MAX_BYTECOUNT=256*1024
MEMREF_SIZE=24
OP_PARAMS_OFFSET=8

def load_original(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    if path.stat().st_size>1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=SOURCE_SHA256:
        raise ValueError("wrong_original_X2DII_client_binary")
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("not_AArch64")
        dyn=elf.get_section_by_name(".dynsym")
        text=elf.get_section_by_name(".text")
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        if not all((dyn,text,plt,rela)):raise ValueError("missing_sections")
        funcs={x.name:(int(x["st_value"]),int(x["st_size"])) for x in dyn.iter_symbols()
               if x.name in SPEC and x["st_shndx"]!="SHN_UNDEF"}
        if set(funcs)!=set(SPEC):raise ValueError("required_original_function_missing")
        pltmap={}
        for i,rel in enumerate(rela.iter_relocations()):
            pltmap[int(plt["sh_addr"])+32+16*i]=dyn.get_symbol(rel["r_info_sym"]).name
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        decoder.detail=True
        raw=text.data()
        start=int(text["sh_addr"])
        def read_func(n):
            addr,sz=funcs[n]
            off=addr-start
            if sz<=0 or sz>MAX_BYTECOUNT or off<0 or off+sz>len(raw):
                raise ValueError("invalid_function_extent_"+n)
            res=list(decoder.disasm(raw[off:off+sz],addr))
            if len(res)*4!=sz:raise ValueError("decode_gap_"+n)
            return res
        return {n:read_func(n) for n in SPEC},pltmap

def regname(ins,op):
    return ins.reg_name(op.reg)

def simple_reg_source(insns,idx,reg,lookback=40):
    """Use only same basic block. Return unresolved on control-flow boundaries."""
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    canonical=lambda s:("x"+s[1:] if s and s[0]=="w" and s[1:].isdigit() else s)
    goal=canonical(reg)
    for j in range(idx-1,max(-1,idx-lookback-1),-1):
        ins=insns[j]
        if ins.mnemonic in ("bl","blr","b","br","ret","eret") or ins.mnemonic.startswith(("b.","cb","tb")):
            return {"kind":"control_flow_boundary"}
        try:_,wr=ins.regs_access()
        except Exception:continue
        if not any(canonical(ins.reg_name(r))==goal for r in wr):continue
        if not ins.operands or ins.operands[0].type!=ARM64_OP_REG or canonical(regname(ins,ins.operands[0]))!=goal:
            return {"kind":"implicit_write"}
        ops=ins.operands
        if ins.mnemonic in ("mov","movz") and len(ops)>1:
            if ops[1].type==ARM64_OP_IMM:
                v=int(ops[1].imm)
                return {"kind":"constant","value":v if -1<=v<=65535 else None}
            if ops[1].type==ARM64_OP_REG:
                src=regname(ins,ops[1])
                if src in ("wzr","xzr"):return {"kind":"constant","value":0}
                return {"kind":"register_alias","source":src}
        if ins.mnemonic=="add" and len(ops)>2 and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
            return {"kind":"pointer_base_plus_offset","base":regname(ins,ops[1]),"offset":int(ops[2].imm)}
        if ins.mnemonic in ("ldr","ldur","ldrsw","ldrb","ldrh") and len(ops)>1 and ops[1].type==ARM64_OP_MEM:
            m=ops[1].mem
            return {"kind":"memory_load","base":ins.reg_name(m.base),"offset":int(m.disp)}
        return {"kind":"other_definition","mnemonic_class":ins.mnemonic}
    return {"kind":"not_defined_in_bounded_basic_block"}

def direct_sp_store(insns,idx,ins):
    from capstone.arm64 import ARM64_OP_MEM,ARM64_OP_REG
    if ins.mnemonic not in ("str","stur","stp","stnp"):return []
    ops=ins.operands
    if ins.mnemonic in ("stp","stnp"):
        if len(ops)<3 or ops[2].type!=ARM64_OP_MEM:return []
        m=ops[2].mem
        val=ops[:2]
    else:
        if len(ops)<2 or ops[1].type!=ARM64_OP_MEM:return []
        m=ops[1].mem
        val=ops[:1]
    if ins.reg_name(m.base)!="sp" or m.index or ins.writeback:return []
    o=[]
    for j,src in enumerate(val):
        if src.type!=ARM64_OP_REG:continue
        register=regname(ins,src)
        # Str W and X are 4 and 8-byte storage; SIMD stores are not
        # interpreted as scalar ownership, though still counted.
        width=(4 if register.startswith("w") else 8 if register.startswith("x") else None)
        off=int(m.disp)+j*(width or 0)
        o.append({"va":hex(ins.address),"sp_offset":off,
                  "width_bytes":width,
                  "register":register,
                  "source":simple_reg_source(insns,idx,register)})
    return o

def all_calls(insns,pltmap):
    from capstone.arm64 import ARM64_OP_IMM
    result=[]
    for i,ins in enumerate(insns):
        if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:
            continue
        name=pltmap.get(int(ins.operands[0].imm))
        if name not in ALLOWED_CALLS:continue
        args={}
        for arg in (0,1,2):
            args[str(arg)]=simple_reg_source(insns,i,"x"+str(arg))
        result.append({"va":hex(ins.address),"target":name,"register_args":args})
    return result

def function_dossier(name,insns,pltmap):
    expected=SPEC[name]
    base=expected["operation_sp"]
    invoke_hex=hex(expected["invoke"])
    calls=all_calls(insns,pltmap)
    assert len([r for r in calls if r["target"]=="TEEC_InvokeCommand" and r["va"]==invoke_hex])==1,"wrong original invocation"
    copy_count=sum(x["target"]=="strncpy" for x in calls)
    alloc_count=sum(x["target"]=="TEEC_AllocateSharedMemory" for x in calls)
    if copy_count!=expected["expected_copies"] or alloc_count!=expected["expected_allocations"]:
        raise ValueError("expected_original_shared_memory_call_count_changed_"+name)
    writes=[field for i,ins in enumerate(insns) for field in direct_sp_store(insns,i,ins)
            if ins.address < expected["invoke"]]
    # TEE Operation declared struct: started(uint32),paramTypes(uint32),
    # params[4] with 24-byte union slots on AArch64. Every match below
    # is a structural candidate and NOT path-sensitive or type-proven.
    slots=[]
    for k in range(4):
        start=base+OP_PARAMS_OFFSET+k*MEMREF_SIZE
        candidates=[x for x in writes if start<=x["sp_offset"]<start+MEMREF_SIZE]
        slots.append({"param_index":k,"declared_type":(expected["paramTypes"]>>(k*4))&15,
                      "candidate_stores":[dict(x,slot_offset=x["sp_offset"]-start)
                           for x in candidates[:24]],"total_direct_stores":len(candidates)})
    op_start=base
    op_end=base+OP_PARAMS_OFFSET+4*MEMREF_SIZE
    others=[x for x in writes if op_start<=x["sp_offset"]<op_start+OP_PARAMS_OFFSET]
    # The recorded ranges overlap other local variables on some paths.
    # Do not describe all such stores as *effective* param writes.
    allocations=[c for c in calls if c["target"] in (
        "TEEC_AllocateSharedMemory","TEEC_RegisterSharedMemoryFileDescriptor")]
    copy=[c for c in calls if c["target"] in ("strncpy","memcpy")]
    return {"function":name,"command_id":expected["command"],
            "original_invoke_va":invoke_hex,
            "paramtypes_verified_previous_stage":hex(expected["paramTypes"]),
            "operation_stack_base_observed_previous_stage":base,
            "alloc_or_register_calls":allocations,
            "copy_calls":copy,
            "declared_operation_slots":slots,
            "operation_header_write_candidates":others[:16],
            "total_direct_sp_stores_before_call":len(writes),
            "path_sensitive_buffer_ownership_proven":False,
            "TEE_returned_decrypted_plaintext_proven":False}

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("wrong_version")
    funcs,pltmap=load_original(root/SOURCE)
    return {"schema":"hasselblad-stage12-original-tee-memref-provenance-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "hash_pinned_client":SOURCE_SHA256,
            "functions":[function_dossier(n,funcs[n],pltmap) for n in SPEC],
            "data_includes_original_vendor_instruction_bytes":False,
            "data_includes_secret_key_or_plaintext":False,
            "vendor_binary_executed":False,
            "TEE_or_DSP_decryption_performed":False,
            "AArch64_TEEC_struct_layout_assumed_not_proven":True}

def selftest():
    assert (0x1ddd&15, (0x1ddd>>4)&15, (0x1ddd>>8)&15, (0x1ddd>>12)&15)==(13,13,13,1)
    assert (0x11df&15, (0x11df>>4)&15)==(15,13)
    assert [8+24*i for i in range(4)]==[8,32,56,80]
    assert SOURCE_SHA256.startswith("96e6")
    return {"status":"PASS_synthetic","checks":4,"original_input_loaded":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--firmware-root",type=Path)
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not args.self_test and not args.firmware_root:parser.error("--firmware-root required")
    result=selftest() if args.self_test else audit(args.firmware_root)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result.get("status","original_source_read_only"),
                      "inspected_functions":len(result.get("functions",[])),
                      "total_calls":sum(len(d["alloc_or_register_calls"])+len(d["copy_calls"]) for d in result.get("functions",[]))},
                      sort_keys=True))
if __name__=="__main__":main()
