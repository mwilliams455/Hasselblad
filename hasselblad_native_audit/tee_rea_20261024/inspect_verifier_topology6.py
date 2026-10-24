#!/usr/bin/env python3
"""Stage6: X2D II verifier-library selection and symbol-call graph discovery.

Focused original firmware: identify the actual II-generation wrapper and its
relation (if any) to TEE command 6. Static metadata only. No original code or
binary bytes, decryption material, raw string tables, device image data or
Ghidra pseudocode are exported. No vendor executable is run.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCES=(
 "system/lib64/libfw_util_ca.so",
 "system/lib64/libfw_util.so",
 "system/lib64/libfw_verify_util.so",
 "system/bin/dji_fw_verify",
)
PAT=re.compile(r"(?:^dji_fw|^fw_util_|^TEEC_|verify|cipher|_decrypt|key_version|sec_crypto|^strncpy$)",re.I)
MAX_FILE=16*1024*1024
MAX_RESULTS=100

def inspect_one(root,rel):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM
    from elftools.elf.elffile import ELFFile
    path=root/rel
    if not path.is_file():
        return {"path":rel,"present":False}
    if path.stat().st_size>MAX_FILE:raise ValueError("oversize_"+rel)
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("not_arm64_"+rel)
        names={}
        exports=[]
        imports=[]
        addr_owners=[]
        for symsec in (".dynsym",".symtab"):
            tab=elf.get_section_by_name(symsec)
            if tab is None:continue
            for s in tab.iter_symbols():
                name=s.name
                if not name or s["st_info"]["type"]!="STT_FUNC":continue
                undef=s["st_shndx"]=="SHN_UNDEF"
                val=int(s["st_value"]);size=int(s["st_size"])
                if undef and PAT.search(name):imports.append(name)
                elif not undef and PAT.search(name):
                    names.setdefault(name,(val,size))
                    if name not in (x["name"] for x in exports):
                        exports.append({"name":name,"va":hex(val),"size_bytes":size})
                if not undef and val and size>0:
                    addr_owners.append((val,val+size,name))
        addr_owners.sort()
        dynamic=elf.get_section_by_name(".dynamic")
        dependencies=[]
        if dynamic:
            for entry in dynamic.iter_tags():
                if entry.entry.d_tag=="DT_NEEDED":
                    dependencies.append(entry.needed)
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        dyn=elf.get_section_by_name(".dynsym")
        plt_names={}
        if plt and rela and dyn:
            for i,r in enumerate(rela.iter_relocations()):
                plt_names[int(plt["sh_addr"])+32+16*i]=dyn.get_symbol(r["r_info_sym"]).name
        addr_named={st:n for n,(st,_) in names.items()}
        code=elf.get_section_by_name(".text")
        refs=[]
        if code is not None:
            dis=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
            dis.detail=True
            for ins in dis.disasm(code.data(),int(code["sh_addr"])):
                if ins.mnemonic not in ("bl","b") or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:
                    continue
                addr=int(ins.operands[0].imm)
                callee=plt_names.get(addr) or addr_named.get(addr)
                if not callee or not PAT.search(callee):continue
                owners=[name for start,end,name in addr_owners if start<=ins.address<end]
                chosen=min(owners,key=len) if owners else None
                refs.append({"site_va":hex(ins.address),"to_symbol":callee,
                             "caller_named":chosen,
                             "via_plt":addr in plt_names,
                             "branch_type":"call" if ins.mnemonic=="bl" else "tail_or_branch"})
        return {"path":rel,"present":True,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes":path.stat().st_size,"dependencies":sorted(dependencies),
                "relevant_defined_symbols":sorted(exports,key=lambda x:x["name"])[:MAX_RESULTS],
                "relevant_undefined_symbols":sorted(set(imports))[:MAX_RESULTS],
                "relevant_original_branch_refs":refs[:MAX_RESULTS],
                "relevant_branch_ref_count":len(refs),
                "cmd6_wrapper_reachability_statically_proven":False,
                "no_unencrypted_TA_executable_presented":True}


def audit(root):
    version=root/"system/etc/VERSION"
    if version.read_text().strip()!="1.3.16.2":
        raise ValueError("unexpected_firmware_version")
    out=[inspect_one(root,p) for p in SOURCES]
    if not out[0]["present"] or not out[1]["present"]:
        raise ValueError("missing_core_TEE_client_binaries")
    return {"schema":"hasselblad-stage6-original-verifier-symbol-topology-v1",
            "camera_version":"1.3.16.2",
            "sources":out,"cryptographic_key_recovered":False,
            "vendor_instructions_exported":False,
            "command6_host_selector_equivalence_to_DSP_decrypt_proven":False,
            "original_vendor_code_executed":False}


def synthetic():
    assert PAT.search("fw_util_verify_init_ext")
    assert PAT.search("sec_cipher_ecc_sha256_verify")
    assert not PAT.search("random unrelated calibration")
    assert len(SOURCES)==4
    return {"status":"PASS_synthetic","checks":4,"original_used":False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if not a.self_test and not a.firmware_root:ap.error("--firmware-root required")
    result=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result.get("status","done"),
                      "sources":len(result.get("sources",[])),
                      "found":sum(int(x["present"]) for x in result.get("sources",[])),
                      "matching_edges":sum(x.get("relevant_branch_ref_count",0) for x in result.get("sources",[]))},
                     sort_keys=True))

if __name__=="__main__":main()
