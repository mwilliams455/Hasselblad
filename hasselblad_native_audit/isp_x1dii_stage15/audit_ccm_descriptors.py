#!/usr/bin/env python3
"""Inert ARM32 X1D II IQ CCM descriptor-layout and accessor-class audit.

Read-only original code/data introspection on pinned public firmware inputs.
This tool never publishes CCM source payloads or treats a descriptor as a
known photographic pixel equation. It runs on the CI runner, not on a camera.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from inspect_x1dii_isp import (download_asset, REPOSITORY, REV, gitblob)

CAMERA_NAMES = (
    "x1dm2_iq_ccm_settings", "x1dm2_iq_gamma_settings",
    "x1dm2_iq_gamma_fe_settings", "x1dm2_iq_apost_lut3d_settings",
    "x1dm2_color_settings",
)
GENERIC_NAMES = (
    "imx378_iq_ccm_settings", "imx378_iq_gamma_settings",
    "imx378_iq_gamma_fe_settings", "imx378_iq_apost_lut3d_settings",
    "imx378_color_settings",
)
FRAMEWORK_NAMES = ("image_get_color_matrix1", "image_get_color_matrix2", "image_get_white_balance", "image_get_color_mode")


def vh(elf, va, size):
    if va < 0 or size < 0:
        raise ValueError("invalid range")
    for p in elf.iter_segments():
        if p["p_type"] != "PT_LOAD":
            continue
        begin,end=int(p["p_vaddr"]),int(p["p_vaddr"])+int(p["p_filesz"])
        if begin <= va and va+size <= end:
            return p.data()[va-begin:va-begin+size]
    raise ValueError("data range not found in file-backed PT_LOAD")


def section_for(elf, va):
    for section in elf.iter_sections():
        start=int(section["sh_addr"]); end=start+int(section["sh_size"])
        if (int(section["sh_flags"]) & 2) and start <= va < end:
            return section.name
    return None


def mapped_target(elf, candidate):
    # Avoid identifying arbitrary scalar fields as pointers on appearance alone.
    region=section_for(elf,candidate)
    return region if region and region not in (".bss",) else None


def dynsymbols(elf):
    section=elf.get_section_by_name(".dynsym")
    if section is None:
        raise ValueError("missing .dynsym")
    return {s.name:s for s in section.iter_symbols() if s.name}


def descriptor(elf, sym, symbol_by_va):
    if sym is None or sym["st_shndx"]=="SHN_UNDEF":
        return {"found":False}
    va=int(sym["st_value"]); size=int(sym["st_size"])
    if size<4 or size>256 or size%4:
        raise ValueError("unexpected descriptor byte size")
    data=vh(elf,va,size)
    all_relocations={}
    for s in elf.iter_sections():
        if not isinstance(s, RelocationSection):
            continue
        symtable=elf.get_section(s["sh_link"])
        for r in s.iter_relocations():
            offset=int(r["r_offset"])
            if va <= offset < va+size:
                idx=int(r["r_info_sym"])
                item={"relocation_type":int(r["r_info_type"])}
                if idx>0 and symtable is not None:
                    target=symtable.get_symbol(idx)
                    if target.name:
                        item["named_target"]=target.name
                all_relocations[offset]=item
    slots=[]
    for word in range(size//4):
        offset=va+4*word
        value=struct.unpack_from("<I",data,word*4)[0]
        relocation=all_relocations.get(offset)
        # Classify targets without including a proprietary tuning value.
        sec=mapped_target(elf,value)
        rec={"slot":word,"has_relocation":bool(relocation),"is_zero":value==0}
        if relocation:
            rec.update(relocation)
            if sec:
                rec["raw_word_resolves_to_section"]=sec
                if value in symbol_by_va:
                    rec["target_export_name"]=symbol_by_va[value]
        elif sec:
            # No relocation => coincidental scalar often looks pointer-like.
            rec["possible_pointer_without_relocation_not_proven"]=sec
        slots.append(rec)
    return {"found":True,"va":hex(va),"bytes":size,"section":section_for(elf,va),
            "descriptor_bytes_sha256":hashlib.sha256(data).hexdigest(),
            "slots":slots,"number_relocated_slots":sum(s["has_relocation"] for s in slots),
            "contains_proprietary_value_dump":False}


def audit_mod(key,names):
    data=download_asset(key)
    elf=ELFFile(io.BytesIO(data));sym=dynsymbols(elf)
    byva={int(s["st_value"]):s.name for s in sym.values() if s["st_shndx"]!="SHN_UNDEF"}
    desc={name:descriptor(elf,sym.get(name),byva) for name in names}
    if not all(d["found"] for d in desc.values()):
        raise ValueError("model-specific IQ symbol missing from exact pinned module")
    return {"binary":key,"git_blob_sha1":gitblob(data),"descriptors":desc,
            "direct_pixel_math_derived":False,"compiled_vendor_payload_embedded":False}


def audit_frwk():
    key="lib/libdcam_frwk.so";data=download_asset(key)
    elf=ELFFile(io.BytesIO(data));syms=dynsymbols(elf)
    wanted={}
    for name in FRAMEWORK_NAMES:
        s=syms.get(name)
        if s:
            wanted[name]={"va":hex(int(s["st_value"]) & ~1),"bytes":int(s["st_size"]),
                          "kind":str(s["st_info"]["type"]),"defined":s["st_shndx"]!="SHN_UNDEF"}
    defined=sorted((int(s["st_value"])&~1,s.name) for s in syms.values()
                   if s["st_shndx"]!="SHN_UNDEF" and str(s["st_info"]["type"])=="STT_FUNC")
    nearby={}
    for name in ("image_get_color_matrix1","image_get_color_matrix2"):
        if name not in wanted:continue
        address=int(wanted[name]["va"],16)
        near=sorted(defined,key=lambda k:abs(k[0]-address))[:11]
        nearby[name]=[{"name":n,"va":hex(x)} for x,n in near]
    return {"binary":key,"git_blob_sha1":gitblob(data),
            "accessors":wanted,"nearest_named_functions":nearby,
            "classify_as_pixel_ccm_equation":False,
            "caution":"Names and locality establish possible metadata accessors, not a numerical pixel transform"}


def self_test():
    from inspect_x1dii_isp import MANIFEST
    assert MANIFEST["lib/libmod_x1dm2.so"][0] > 1000000
    assert "x1dm2_iq_ccm_settings" in CAMERA_NAMES
    assert "imx378_iq_ccm_settings" in GENERIC_NAMES
    assert len(CAMERA_NAMES)==len(GENERIC_NAMES)==5
    assert all(a.replace("x1dm2_","imx378_")==b for a,b in zip(CAMERA_NAMES,GENERIC_NAMES))

    print("PASS Stage15 descriptor matching, source separation and missing-proof guard")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.self_test:
        self_test();return
    if args.output is None:p.error("--output required")
    out={"schema":"hasselblad-stage15b-x1dii-iq-descriptor-relationships-v1",
         "source_repository":REPOSITORY,"source_revision":REV,
         "x1dm2":audit_mod("lib/libmod_x1dm2.so",CAMERA_NAMES),
         "generic_imx378":audit_mod("lib/libmod_dji.so",GENERIC_NAMES),
         "camera_framework":audit_frwk(),
         "x1dm2_same_isp_as_x2dii_proven":False,
         "x2dii_ccm_16_by_6_pixel_equation_proven":False,
         "vendor_numeric_tables_in_report":False,
         "photographic_pixels_processed":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if len(data)>60000:raise ValueError("unexpected oversized descriptor report")
    args.output.write_text(data)
    print(json.dumps({"result":"PASS","output":str(args.output),"descriptors":10,
                      "x1dm2_ccm_va":out["x1dm2"]["descriptors"]["x1dm2_iq_ccm_settings"]["va"]}),flush=True)


if __name__=="__main__":main()
