#!/usr/bin/env python3
"""Stage5: original X2D II TEE key-selector *normal-world* call-flow audit.

Actual firmware binaries are private transient inputs. The JSON receipt contains
only exact function/call identities, bounded ABI register provenance summaries
and uncertainty flags; no raw disassembly, vendor text, decompiled code, secret
materials or private camera data. No firmware executable is run.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

EXPECTED_FIRMWARE_VERSION="1.3.16.2"
EXPECTED_SHA={
    "system/lib64/libfw_util_ca.so":"96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b",
    "system/lib64/libfw_util.so":"3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d",
}
PATHS=(
    ("system/lib64/libfw_util_ca.so",(
        "fw_util_verify_init_ext","fw_util_verify_load2ion","fw_util_verify_init",
        "fw_util_verify_update","fw_util_verify_final",
    )),
    ("system/lib64/libfw_util.so",(
        "dji_fw_verify_file","dji_fw_verify_load2mem",
    )),
    ("system/bin/dji_fw_verify",("main",)),
)
TARGET_CALLS=frozenset((
    "TEEC_InvokeCommand","fw_util_verify_init_ext",
    "fw_util_verify_init","fw_util_verify_load2ion",
    "dji_fw_verify_file","fw_util_verify","fw_util_load",
    "memcpy","strncpy",
))
MAX_ELF_SIZE=20*1024*1024
MAX_FUNCTION=12000


def normal_reg(r):
    r=r.lower()
    if re.fullmatch(r"[wx][0-9]+",r):
        return "r"+str(int(r[1:]))
    return r


def ins_summary(ins):
    """No user/vendor instruction text exported: only bounded data provenance."""
    from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG, ARM64_OP_MEM
    ops=ins.operands
    if ins.mnemonic in ("mov","movz") and len(ops)>=2:
        if ops[1].type==ARM64_OP_IMM:
            v=int(ops[1].imm)
            return {"kind":"literal","small_value":v if -1<=v<=65535 else None}
        if ops[1].type==ARM64_OP_REG:
            return {"kind":"reg_copy","from_reg":normal_reg(ins.reg_name(ops[1].reg))}
    if ins.mnemonic in ("ldr","ldur","ldrb","ldrh","ldrsw") and len(ops)>=2 and ops[1].type==ARM64_OP_MEM:
        m=ops[1].mem
        base=ins.reg_name(m.base)
        return {"kind":"memory_load","base_reg":normal_reg(base),
                "displacement":int(m.disp)}
    if ins.mnemonic in ("add","sub") and len(ops)>=3:
        if ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
            return {"kind":"offset_pointer","base_reg":normal_reg(ins.reg_name(ops[1].reg)),
                    "offset":int(ops[2].imm) * (1 if ins.mnemonic=="add" else -1)}
    return {"kind":"other","instruction_class":ins.mnemonic}


def latest_arg_def(instructions,call_index,arg,lookback=45):
    """Nearest local definition, not general proof through branch/stack aliases."""
    try:
        from capstone.arm64 import ARM64_OP_REG
    except ImportError:
        return {"kind":"provider_unavailable"}
    norm=normal_reg(arg)
    for k in range(call_index-1,max(-1,call_index-lookback-1),-1):
        ins=instructions[k]
        if ins.mnemonic=="bl" or ins.mnemonic in ("b","br","ret","blr") or ins.mnemonic.startswith(("b.","cb","tb")):
            return {"kind":"crosses_control_flow_boundary"}
        # Capstone register writes are authoritative for assigning provenance
        try:
            _,writes=ins.regs_access()
        except Exception:
            continue
        if not any(normal_reg(ins.reg_name(reg))==norm for reg in writes):
            continue
        if not ins.operands or ins.operands[0].type!=ARM64_OP_REG:
            return {"kind":"unknown_register_write"}
        if normal_reg(ins.reg_name(ins.operands[0].reg))!=norm:
            return {"kind":"implicit_or_unclassified_write"}
        s=ins_summary(ins)
        s["distance_to_call"]=call_index-k
        return s
    return {"kind":"not_defined_in_local_window"}


def callsite_args(insns,idx):
    return {str(r):latest_arg_def(insns,idx,"x"+str(r))
            for r in (1,2,3,4,5,6,7)}


def file_dossier(root, rel, wanted):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    from elftools.elf.elffile import ELFFile
    path=root/rel
    data_size=path.stat().st_size
    if data_size>MAX_ELF_SIZE:raise ValueError("source_over_bound_"+rel)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if rel in EXPECTED_SHA and sha!=EXPECTED_SHA[rel]:
        raise ValueError("unexpected_original_digest_"+rel)
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":
            raise ValueError("unexpected_machine_"+rel)
        code=elf.get_section_by_name(".text")
        if code is None:raise ValueError("no_text_"+rel)
        symbols={}
        addr_names={}
        dyn=elf.get_section_by_name(".dynsym")
        for secn in (".symtab",".dynsym"):
            sec=elf.get_section_by_name(secn)
            if sec is None:continue
            for sym in sec.iter_symbols():
                if sym["st_info"]["type"]!="STT_FUNC" or sym["st_shndx"]=="SHN_UNDEF" or not sym.name:
                    continue
                a=int(sym["st_value"]);z=int(sym["st_size"])
                if z>0:
                    symbols.setdefault(sym.name,(a,z))
                    addr_names.setdefault(a,sym.name)
        plt_names={}
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        if dyn is not None and plt is not None and rela is not None:
            for i,reloc in enumerate(rela.iter_relocations()):
                si=reloc["r_info_sym"]
                nm=dyn.get_symbol(si).name
                # Original AArch64 .plt ELF layout, verified in earlier stages.
                plt_names[int(plt["sh_addr"])+32+16*i]=nm
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        decoder.detail=True
        code_raw=code.data()
        code_va=int(code["sh_addr"])
        results=[]
        for name in wanted:
            loc=symbols.get(name)
            if not loc:
                results.append({"function":name,"present":False})
                continue
            entry,length=loc
            if length>MAX_FUNCTION or entry<code_va or entry+length>code_va+len(code_raw):
                results.append({"function":name,"present":True,"analysis":"out_of_bound"})
                continue
            start=entry-code_va
            insns=list(decoder.disasm(code_raw[start:start+length],entry))
            calls=[]
            for idx,ins in enumerate(insns):
                if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:
                    continue
                dest=int(ins.operands[0].imm)
                callee=plt_names.get(dest) or addr_names.get(dest)
                if callee not in TARGET_CALLS:continue
                rec={"site_va":hex(ins.address),"target":callee,
                     "target_class":"plt" if dest in plt_names else "internal"}
                if callee in ("TEEC_InvokeCommand","fw_util_verify_init_ext","fw_util_verify_init"):
                    rec["local_register_definitions"]=callsite_args(insns,idx)
                calls.append(rec)
            results.append({"function":name,"present":True,
                            "entry_va":hex(entry),"size_bytes":length,
                            "instructions_analysed":len(insns),
                            "selected_calls":calls,
                            "selected_calls_count":len(calls),
                            "full_control_flow_equivalence_proven":False})
        return {"path":rel,"sha256":sha,"bytes":data_size,
                "selected_functions":results,
                "symbol_table_available":bool(symbols),
                "plt_import_count":len(plt_names),
                "ELF_executable_code_read_only":True}


def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!=EXPECTED_FIRMWARE_VERSION:
        raise ValueError("version_mismatch")
    return {"schema":"hasselblad-rea-key-selector-normal-world-stage5-v1",
            "firmware":EXPECTED_FIRMWARE_VERSION,
            "files":[file_dossier(root,path,names) for path,names in PATHS],
            "original_functions_executed":False,
            "TEE_key_value_or_plaintext_recovered":False,
            "TEE_operation_parameter_values_proven":False,
            "local_register_definitions_are_not_interprocedural_proof":True,
            "no_original_instruction_bytes_or_text_exported":True,
            "DSP_and_TA_encrypted_unchanged":True,
            "normal_Photon_camera_output_unchanged":True}


def synthetic():
    assert normal_reg("w3")==normal_reg("x3")=="r3"
    assert normal_reg("wzr")=="wzr"
    assert normal_reg("sp")=="sp"
    assert MAX_FUNCTION<=MAX_ELF_SIZE
    return {"status":"PASS_synthetic","checks":4,
            "firmware_analyzed":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if not args.self_test and not args.firmware_root:p.error("--firmware-root required")
    data=synthetic() if args.self_test else audit(args.firmware_root)
    args.output.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"schema":data.get("schema","synthetic"),
                      "analyzed_elfs":len(data.get("files",[])),
                      "functions_found":sum(y["present"] for x in data.get("files",[])
                                            for y in x["selected_functions"]),
                      "calls":sum(y.get("selected_calls_count",0) for x in data.get("files",[])
                                  for y in x["selected_functions"])},sort_keys=True))


if __name__=="__main__":main()
