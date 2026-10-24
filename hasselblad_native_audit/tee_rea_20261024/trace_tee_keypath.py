#!/usr/bin/env python3
"""Focused original X2D II secure key-path audit; no vendor bytes are exported.

Unlike the completed IMaH header inventory this traces *normal-world* AArch64
call sites to standard TEEC operations, and inspects non-OTA boot candidates.
REA objdump/Ghidra may be used separately for the same original source.
Findings are static only and explicitly do not claim secure-world decryption.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

VERSION="1.3.16.2"
CLIENT="system/lib64/libfw_util_ca.so"
EXPECTED="9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6"
TARGET_IMPORTS=("TEEC_OpenSession","TEEC_InvokeCommand",
                "TEEC_AllocateSharedMemory","TEEC_RegisterSharedMemoryFileDescriptor")
INTEREST=re.compile(r"bootarea|(?:^|[/_.-])(?:tos|tee|trustzone|bootloader|secureboot|uboot)(?:$|[/_.-])",re.I)
MAX_BOOT=32*1024*1024


def classify_bytes(data):
    return ("ELF" if data.startswith(b"\x7fELF") else
            "IMAH" if data.startswith(b"IM*H") else
            "ANDROID_BOOT" if data.startswith(b"ANDROID!") else
            "ZIP" if data.startswith(b"PK\x03\x04") else
            "GZIP" if data.startswith(b"\x1f\x8b") else
            "RAW_OR_OTHER")


def boot_probe(data, source):
    if len(data)>MAX_BOOT: return {"source":source,"status":"over_32MiB_limit"}
    keys=(b"TBIE",b"PRAK",b"TEEC_",b"keymaster",b"TZOS",b"OP-TEE")
    rows={key.decode():data.count(key) for key in keys}
    elf_offsets=[]
    p=0
    while len(elf_offsets)<12:
        p=data.find(b"\x7fELF",p)
        if p<0:break
        elf_offsets.append(p)
        p+=4
    imah_offsets=[]
    p=0
    while len(imah_offsets)<12:
        p=data.find(b"IM*H",p)
        if p<0:break
        imah_offsets.append(p)
        p+=4
    return {"source":source,"size_bytes":len(data),"outer_magic":classify_bytes(data),
            "embedded_elf_offset_count_observed":len(elf_offsets),
            "embedded_elf_offsets_first_twelve":elf_offsets,
            "embedded_imah_offsets_first_twelve":imah_offsets,
            "cleartext_marker_counts":rows,
            "is_unencrypted_native_ELF_proven":classify_bytes(data)=="ELF",
            "decrypted_key_found":False}


def inspect_boot(root,firmware_path):
    container=root/"container.json"
    names=[]
    probes=[]
    if container.is_file():
        d=json.loads(container.read_text())
        for x in d.get("items",[]):
            n=x.get("name","")
            if INTEREST.search(n):
                names.append({"name":n,"size_bytes":x.get("length"),"origin":"CIM_component"})
    ota=root/"ota.zip"
    if ota.is_file():
        with zipfile.ZipFile(ota) as z:
            for info in z.infolist():
                if not INTEREST.search(info.filename):continue
                names.append({"name":info.filename,"size_bytes":info.file_size,"origin":"OTA_member"})
                if 0<info.file_size<=MAX_BOOT and not info.is_dir():
                    try: probes.append(boot_probe(z.read(info),"OTA:"+info.filename))
                    except (ValueError,EOFError):pass
    for prefix in ("system","vendor"):
        area=root/prefix
        if not area.is_dir():continue
        for p in area.rglob("*"):
            if not p.is_file() or p.is_symlink() or not INTEREST.search(p.name):
                continue
            rel=p.relative_to(root).as_posix()
            names.append({"name":rel,"size_bytes":p.stat().st_size,"origin":"extracted_filesystem"})
            if p.stat().st_size<=MAX_BOOT and ("bootarea" in p.name.lower() or p.name=="tos.img"):
                probes.append(boot_probe(p.read_bytes(),"filesystem:"+rel))
    # Only inspect the original *outer* CIM component if the named bootarea
    # actually exists; do not redo full unpacking or export decrypted bytes.
    itemnames={n["name"] for n in names if n["origin"]=="CIM_component"}
    target_names=[n for n in itemnames if "bootarea" in n.lower() or n.lower() in ("tos.img","boot.img")]
    if target_names and firmware_path and firmware_path.is_file():
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        import cim_reader
        data=firmware_path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=EXPECTED:
            raise ValueError("original_cim_hash_mismatch")
        _, encrypted, iv, _, items=cim_reader.load_container(data)
        for item in items:
            if item["name"] not in target_names or item["length"]>MAX_BOOT:
                continue
            raw=(cim_reader.decrypt_component(data,item,iv) if encrypted else
                 data[item["offset_in_cim"]:item["offset_in_cim"]+item["length"]])
            probes.append(boot_probe(raw,"CIM:"+item["name"]))
    return {"candidate_inventory":sorted(names,key=lambda r:(r["origin"],r["name"]))[:60],
            "candidate_count":len(names),"boot_container_probes":probes,
            "trustzone_decryption_not_attempted":True}


def native_trace(path):
    from elftools.elf.elffile import ELFFile
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_REG_W1,ARM64_REG_X1
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":
            raise ValueError("not_aarch64")
        sec=elf.get_section_by_name(".text")
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        symtab=elf.get_section_by_name(".dynsym")
        if not sec or not plt or not rela or not symtab:
            raise ValueError("missing_PLT_or_text")
        text_start=int(sec["sh_addr"])
        text_size=int(sec["sh_size"])
        if text_size>4*1024*1024:raise ValueError("unexpected_large_text")
        plt_map={}
        for idx,rel in enumerate(rela.iter_relocations()):
            sym=symtab.get_symbol(rel["r_info_sym"])
            # AArch64 .plt initial header = 32 bytes, stub size = 16.
            plt_map[int(plt["sh_addr"])+32+16*idx]=sym.name
        dyn_names={s.name for s in symtab.iter_symbols()
                   if s.name and s["st_shndx"]=="SHN_UNDEF"}
        owners=[]
        for symbol_section in (".symtab",".dynsym"):
            ssec=elf.get_section_by_name(symbol_section)
            if not ssec:continue
            for s in ssec.iter_symbols():
                if s["st_info"]["type"]!="STT_FUNC" or s["st_shndx"]=="SHN_UNDEF" or not s.name:continue
                addr=int(s["st_value"]);size=int(s["st_size"])
                if size>0 and text_start<=addr<text_start+text_size:
                    owners.append((addr,addr+size,s.name))
        owners.sort(key=lambda x:(x[0],x[1]))
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);md.detail=True
        instructions=list(md.disasm(sec.data(),text_start))
        def owner(address):
            xs=[x for x in owners if x[0]<=address<x[1]]
            if not xs:return None
            return min(xs,key=lambda x:x[1]-x[0])[2]
        callsites=[]
        found={k:0 for k in TARGET_IMPORTS}
        for idx,ins in enumerate(instructions):
            if ins.mnemonic!="bl" or len(ins.operands)!=1 or ins.operands[0].type!=ARM64_OP_IMM:
                continue
            target=int(ins.operands[0].imm)
            name=plt_map.get(target)
            if name is None or not name.startswith("TEEC_"):continue
            if name in found:found[name]+=1
            row={"api":name,"site_va":hex(ins.address),
                 "caller_symbol":owner(ins.address),"command_id_abi_slot":"w1" if name=="TEEC_InvokeCommand" else None}
            if name=="TEEC_InvokeCommand":
                row["w1_local_predecessor"]="unresolved"
                row["command_id_static_immediate"]=None
                # Conservative straight-line register definition only. A predecessor
                # must appear after a call or branch boundary, and be the nearest
                # instruction writing W1/X1. Do not propagate through PHIs.
                for prev in reversed(instructions[max(0,idx-20):idx]):
                    if prev.mnemonic in ("bl","b","br","ret") or prev.mnemonic.startswith(("b.","cb","tb")):
                        break
                    if prev.operands and prev.operands[0].type==ARM64_OP_REG and prev.operands[0].reg in (ARM64_REG_W1,ARM64_REG_X1):
                        row["w1_local_predecessor"]=prev.mnemonic
                        if prev.mnemonic in ("mov","movz") and len(prev.operands)>=2 and prev.operands[1].type==ARM64_OP_IMM:
                            row["command_id_static_immediate"]=int(prev.operands[1].imm)
                            row["command_id_proof_scope"]="straight_line_local_only"
                        break
            callsites.append(row)
        crypto_regex=re.compile(r"(^|_)(?:AES|EVP|decrypt|mbedtls|crypto|sha|hkdf|hmac)(?:_|$)",re.I)
        observed_imports=sorted(x for x in dyn_names if crypto_regex.search(x))
        return {"source":CLIENT,"architecture":"AArch64",
                "text_instructions_examined":len(instructions),
                "plt_stub_count":len(plt_map),
                "plt_symbols":{k:v for k,v in sorted(found.items())},
                "tee_call_sites":callsites[:70],
                "total_direct_tee_calls":len(callsites),
                "selected_direct_crypto_imports":observed_imports[:30],
                "direct_imports_do_not_exclude_static_crypto_or_secure_world":True,
                "callsite_analysis_is_static_not_runtime":True,
                "secure_world_plaintext_recovered":False}


def audit(root,firmware_path):
    if (root/"system/etc/VERSION").read_text().strip()!=VERSION:
        raise ValueError("wrong_original_firmware_version")
    return {"schema":"hasselblad-rea-tee-keypath-stage4-v1",
            "firmware":VERSION,"host_tee_trace":native_trace(root/CLIENT),
            "boot_and_tos":inspect_boot(root,firmware_path),
            "normal_world_does_not_prove_secure_world_key_origin":True,
            "cryptographic_key_recovered":False,
            "vendor_binaries_exported":False,
            "camera_executed":False}


def synthetic():
    assert classify_bytes(b"\x7fELFzz")=="ELF"
    assert classify_bytes(b"IM*Hzz")=="IMAH"
    assert boot_probe(b"abcTBIE123","fixture")["cleartext_marker_counts"]["TBIE"]==1
    assert boot_probe(b"abcd","fixture")["embedded_elf_offset_count_observed"]==0
    return {"status":"PASS_synthetic","checks":4,"original_firmware_used":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--cim",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    result=synthetic() if a.self_test else audit(a.firmware_root,a.cim)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result.get("status","completed"),
                      "tee_calls":result.get("host_tee_trace",{}).get("total_direct_tee_calls"),
                      "boot_candidates":result.get("boot_and_tos",{}).get("candidate_count")},sort_keys=True))


if __name__=="__main__":
    main()
