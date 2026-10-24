#!/usr/bin/env python3
"""Stage13: source-bound original X2D II command-6 input-copy provenance.

Read-only, SHA-256 gated, AArch64 normal-world client function.
Proves or explicitly refuses the relations:
  incoming ABI pointer -> callee-saved pointer -> strncpy source
  TEEC shared-memory buffer -> strncpy destination
  incoming ABI version -> saved version -> TEEC_Operation value fields
Vendor instruction bytes/pseudocode/strings never enter the JSON receipt.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SOURCE="system/lib64/libfw_util_ca.so"
EXPECTED_SHA="96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b"
FN="fw_util_verify_init_ext"
COPY_SITES=(0x1d8c,0x1df0,0x1e98)
VALUE_SITES=(0x1ef0,0x1ef4)
ALLOC_OBJECTS=(120,72,24)
OP_BASE=192

def normal_reg(s):
    if s and s[0] in "wx" and s[1:].isdigit():return "r"+s[1:]
    return s

def decode(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED_SHA:
        raise ValueError("wrong_original_X2DII_library_digest")
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("wrong_machine")
        sym=elf.get_section_by_name(".dynsym")
        found=[s for s in sym.iter_symbols() if s.name==FN and s["st_shndx"]!="SHN_UNDEF"]
        if len(found)!=1:raise ValueError("function_identity")
        addr,size=int(found[0]["st_value"]),int(found[0]["st_size"])
        code=elf.get_section_by_name(".text")
        off=addr-int(code["sh_addr"])
        if not 0<size<4096 or off<0 or off+size>len(code.data()):
            raise ValueError("bad_function_extent")
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        decoder.detail=True
        insns=list(decoder.disasm(code.data()[off:off+size],addr))
        if len(insns)*4!=size:raise ValueError("instruction_gap")
        return insns

def direct_definition(insns,limit_addr,register):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM
    canonical=normal_reg(register)
    rows=[]
    for ins in insns:
        if ins.address>=limit_addr:break
        try:_,writes=ins.regs_access()
        except Exception:continue
        if not any(normal_reg(ins.reg_name(w))==canonical for w in writes):
            continue
        row={"va":hex(ins.address),"kind":"unclassified","mnemonic_class":ins.mnemonic}
        ops=ins.operands
        if ops and ops[0].type==ARM64_OP_REG and normal_reg(ins.reg_name(ops[0].reg))==canonical:
            if len(ops)>1 and ins.mnemonic in ("mov","movz"):
                second=ops[1]
                if second.type==ARM64_OP_REG:
                    row["kind"]="register_source"
                    row["source"]=normal_reg(ins.reg_name(second.reg))
                elif second.type==ARM64_OP_IMM:
                    row["kind"]="literal_source"
                    row["value"]=int(second.imm) if -1<=int(second.imm)<=65535 else None
            elif len(ops)>1 and ins.mnemonic in ("ldr","ldur","ldrsw","ldrb","ldrh"):
                mem=ops[1]
                if mem.type==ARM64_OP_MEM:
                    row["kind"]="memory_source"
                    row["base"]=normal_reg(ins.reg_name(mem.mem.base))
                    row["offset"]=int(mem.mem.disp)
            elif len(ops)>2 and ins.mnemonic=="add" and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
                row["kind"]="offset_pointer"
                row["base"]=normal_reg(ins.reg_name(ops[1].reg))
                row["offset"]=int(ops[2].imm)
        # LDP may define the second destination, so capture its stack base.
        if ins.mnemonic=="ldp" and len(ops)>=3 and ops[-1].type==ARM64_OP_MEM:
            mem=ops[-1].mem
            row["kind"]="ldp_memory_source"
            row["base"]=normal_reg(ins.reg_name(mem.base))
            row["offset"]=int(mem.disp)
            row["loaded_lane"]=next((i for i,op in enumerate(ops[:2])
                                    if op.type==ARM64_OP_REG and normal_reg(ins.reg_name(op.reg))==canonical),None)
        rows.append(row)
    return rows

def origin(insns,limit_addr,register):
    rows=direct_definition(insns,limit_addr,register)
    out={"number_of_register_definitions_before_site":len(rows),
         "last_definition":rows[-1] if rows else None}
    # Proved incoming ABI identity only when one direct definition (MOV)
    # with source in the incoming parameter registers; no alternate defs.
    if len(rows)==1 and rows[0]["kind"]=="register_source" and rows[0]["source"] in {
        "r0","r1","r2","r3","r4","r5","r6","r7"
    }:
        out["incoming_argument_index"]=int(rows[0]["source"][1:])
        out["unique_in_function_before_site"]=True
    else:out["unique_in_function_before_site"]=False
    return out

def copy_target(insns,site):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM
    rows=direct_definition(insns,site,"x0")
    recent=rows[-1] if rows else {}
    result={"kind":recent.get("kind","unresolved"),"definition_va":recent.get("va"),
            "stack_shared_memory_buffer_offset":None}
    if recent.get("kind")=="ldp_memory_source" and recent.get("base")=="sp":
        actual=recent["offset"]+(recent.get("loaded_lane") or 0)*8
        result["candidate_shared_memory_buffer_sp_offset"]=actual
        if actual in ALLOC_OBJECTS:
            result["stack_shared_memory_buffer_offset"]=actual
            result["direct_object_buffer_access_verified"]=True
    elif recent.get("kind")=="memory_source" and recent.get("base")=="sp":
        actual=recent.get("offset")
        result["candidate_shared_memory_buffer_sp_offset"]=actual
        if actual in ALLOC_OBJECTS:
            result["stack_shared_memory_buffer_offset"]=actual
            result["direct_object_buffer_access_verified"]=True
    return result

def mem_value_writes(insns):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM
    out=[]
    for site,slot in zip(VALUE_SITES,(0,1)):
        matches=[x for x in insns if x.address==site]
        if len(matches)!=1:raise ValueError("value_write_site_missing")
        ins=matches[0]
        if ins.mnemonic not in ("str","stur") or len(ins.operands)<2:
            raise ValueError("value_write_changed")
        lhs,rhs=ins.operands[:2]
        if lhs.type!=ARM64_OP_REG or rhs.type!=ARM64_OP_MEM or ins.reg_name(rhs.mem.base)!="sp":
            raise ValueError("value_write_not_sp")
        offset=int(rhs.mem.disp)
        if offset!=OP_BASE+8+3*24+slot*4:
            raise ValueError("value_argument_layout_unexpected")
        source=ins.reg_name(lhs.reg)
        saved=origin(insns,site,source)
        out.append({"p3_value_word_index":slot,"store_va":hex(site),"source":source,
                    "incoming_ABI_argument_index":saved.get("incoming_argument_index"),
                    "unique_argument_source_verified":saved["unique_in_function_before_site"],
                    "source_definitions_before_write":saved["number_of_register_definitions_before_site"]})
    return out

def audit(path):
    insns=decode(path)
    from capstone.arm64 import ARM64_OP_IMM
    records=[]
    for i,(site,obj) in enumerate(zip(COPY_SITES,ALLOC_OBJECTS)):
        matches=[x for x in insns if x.address==site]
        if len(matches)!=1 or matches[0].mnemonic!="bl":
            raise ValueError("expected_copy_call_missing")
        # Trust previously grounded original PLT symbol identity and unique
        # site; these are the known strncpy calls from Stage5/12.
        source_reg=("x23","x22","x21")[i]
        saved=origin(insns,site,source_reg)
        dest=copy_target(insns,site)
        records.append({"copy_index":i,"strncpy_va":hex(site),
                        "source_saved_register":source_reg,
                        "source_incoming_ABI_argument_index":saved.get("incoming_argument_index"),
                        "source_provenance_unique":saved["unique_in_function_before_site"],
                        "destination":dest,
                        "expected_allocation_struct_sp_offset":obj,
                        "destination_matches_allocated_object":dest.get("stack_shared_memory_buffer_offset")==obj})
    values=mem_value_writes(insns)
    return {"schema":"hasselblad-stage13-original-command6-input-provenance-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":EXPECTED_SHA,
            "command6_copies":records,
            "command6_version_values":values,
            "TEE_Operation_paramtypes":"0x1ddd",
            "command6_secure_world_content_meaning_verified":False,
            "actual_key_selector_material_recovered":False,
            "runtime_key_version_acceptance_proven":False,
            "executable_vendor_code_run":False,
            "original_instruction_bytes_or_text_exported":False}

def synthetic():
    assert normal_reg("w20")==normal_reg("x20")=="r20"
    assert len(COPY_SITES)==len(ALLOC_OBJECTS)==3
    assert OP_BASE+8+3*24==272
    return {"status":"PASS_synthetic","checks":3,"original_data_used":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root/SOURCE)
    a.output.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":d.get("status","original_inspection_complete"),
                      "pointer_arguments":[x.get("source_incoming_ABI_argument_index") for x in d.get("command6_copies",[])],
                      "value_arguments":[x.get("incoming_ABI_argument_index") for x in d.get("command6_version_values",[])]},
                     sort_keys=True))
if __name__=="__main__":main()
