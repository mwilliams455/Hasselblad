#!/usr/bin/env python3
"""Stage8: strict same-source version-slot proof in original X2D II 1.3.16.2.

Follow one verified wrapper and its immediate direct callsite, including the
callee-saved input register provenance. This is static ABI analysis of readable
Android host code; NOT TEE decryption, key derivation, command acceptance, or
proof that secure-world material versions map to available key bytes.

No original disassembly, machine bytes, key material, photos or tuning exported.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SHA="3e56db44845b23905355b6ef8550ff618d6de53db9e24d"
LIB="system/lib64/libfw_util.so"
WRAPPER="plt_fw_verify_file"
TARGET="fw_util_verify_init_ext"

def nreg(name):
    if len(name)>1 and name[0] in "wx" and name[1:].isdigit():
        return "r"+str(int(name[1:]))
    return name

def audit(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM
    from elftools.elf.elffile import ELFFile
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:
        raise ValueError("original_wrapper_hash_does_not_match")
    with path.open("rb") as f:
        elf=ELFFile(f)
        assert elf["e_machine"]=="EM_AARCH64"
        tab=elf.get_section_by_name(".dynsym")
        syms={s.name:(int(s["st_value"]),int(s["st_size"])) for s in tab.iter_symbols()
              if s.name and s["st_shndx"]!="SHN_UNDEF"}
        if WRAPPER not in syms:raise ValueError("original_wrapper_not_present")
        off,length=syms[WRAPPER]
        textsec=elf.get_section_by_name(".text")
        start=off-int(textsec["sh_addr"])
        if length>4096 or start<0:raise ValueError("wrapper_outside_bounds")
        dis=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);dis.detail=True
        insns=list(dis.disasm(textsec.data()[start:start+length],off))
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        plt_targets={}
        for j,reloc in enumerate(rela.iter_relocations()):
            name=tab.get_symbol(reloc["r_info_sym"]).name
            plt_targets[int(plt["sh_addr"])+32+16*j]=name
        calls=[]
        for i,ins in enumerate(insns):
            if ins.mnemonic!="bl" or not ins.operands or ins.operands[0].type!=ARM64_OP_IMM:continue
            name=plt_targets.get(int(ins.operands[0].imm))
            if name in (TARGET,"fw_util_verify_init"):
                calls.append((name,i,ins.address))
        extended=[(name,i,va) for name,i,va in calls if name==TARGET]
        if len(extended)!=1:raise ValueError("expected_one_extended_call")
        _,idx,site=extended[0]
        # Raw instruction shape is checked locally, but only the derived ABI
        # register provenance is published. No heuristic guessing of keys.
        def nearest_definition(reg,index):
            for j in range(index-1,-1,-1):
                ins=insns[j]
                if ins.mnemonic in ("bl","ret","b","br","blr") or ins.mnemonic.startswith(("b.","cb","tb")):
                    break
                try: _,writes=ins.regs_access()
                except Exception:continue
                if not any(nreg(ins.reg_name(k))==reg for k in writes):continue
                if len(ins.operands)>1 and ins.operands[0].type==ARM64_OP_REG and nreg(ins.reg_name(ins.operands[0].reg))==reg:
                    if ins.mnemonic in ("mov","movz") and ins.operands[1].type==ARM64_OP_REG:
                        return {"type":"register","source":nreg(ins.reg_name(ins.operands[1].reg)),
                                "site":hex(ins.address)}
                    if ins.mnemonic in ("mov","movz") and ins.operands[1].type==ARM64_OP_IMM:
                        return {"type":"immediate","value":int(ins.operands[1].imm),"site":hex(ins.address)}
                return {"type":"other","site":hex(ins.address)}
            return {"type":"not_in_same_basic_block"}
        arguments={k:nearest_definition("r"+str(k),idx) for k in (2,3,4,5)}
        both=(arguments[3].get("type")=="register" and
              arguments[5].get("type")=="register" and
              arguments[3].get("source")==arguments[5].get("source")=="r23")
        origin={}
        for reg in (23,24,25):
            writes=[]
            for ins in insns[:idx]:
                try:_,wr=ins.regs_access()
                except Exception:continue
                if not any(nreg(ins.reg_name(k))=="r"+str(reg) for k in wr):continue
                if ins.operands and ins.operands[0].type==ARM64_OP_REG and nreg(ins.reg_name(ins.operands[0].reg))=="r"+str(reg):
                    source={"type":"other"}
                    if ins.mnemonic in ("mov","movz") and len(ins.operands)>1 and ins.operands[1].type==ARM64_OP_REG:
                        source={"type":"register","source":nreg(ins.reg_name(ins.operands[1].reg))}
                    elif ins.mnemonic in ("ldr","ldur","ldrsw"):
                        source={"type":"memory_load"}
                    writes.append({"site":hex(ins.address),"classification":source})
            origin[str(reg)]={"writes_before_call":writes[:24],"total":len(writes),
                               "unique_source_verified":len(writes)==1 and
                                  writes[0]["classification"]["type"]=="register" if writes else False}
    return {"schema":"hasselblad-stage8-original-x2dii-selector-alias-v1",
            "source":LIB,"source_sha256":SHA,"entry_va":hex(off),
            "extended_call_site":hex(site),
            "basic_init_call_sites":[hex(va) for nm,_,va in calls if nm=="fw_util_verify_init"],
            "selector_arguments":arguments,
            "version_slots_both_from_same_callee_saved_register":both,
            "callee_saved_register_provenance":origin,
            "different_versions_forwarded_at_this_call":not both,
            "command6_runtime_execution_proven":False,
            "TEE_key_derivation_or_decryption_proven":False,
            "original_vendor_code_executed":False,
            "original_instruction_bytes_or_disassembly_exported":False}

def selftest():
    assert nreg("w23")==nreg("x23")=="r23"
    assert nreg("sp")=="sp"
    assert SHA.startswith("3e56")
    return {"status":"PASS_synthetic","checks":3,"original_vendor_data_loaded":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    if not args.self_test and not args.firmware_root:ap.error("--firmware-root required")
    output=selftest() if args.self_test else audit(args.firmware_root/LIB)
    args.output.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":output.get("status","original_source_analyzed"),
                      "common_version_source":output.get("version_slots_both_from_same_callee_saved_register"),
                      "wrapper_bytes_exported":False},sort_keys=True))

if __name__=="__main__":main()
