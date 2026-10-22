#!/usr/bin/env python3
"""Stage28 original X2D II Eagle2 CCM entry-point and callback relocation audit.

Pin the *exact* vcam_driver.ko and previously reviewed source evidence, then
inspect ELF symbols, code-call relocations, and data-function references.
A relocation is a pointer/call relationship, NOT an ISP pixel implementation.
Never export code bytes, register images, IQ coefficients or user photos.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DRIVER_SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
PRIOR_SHA="845212d4aa458fc3ffd200dd019a03cc50c8213dc758a32b6e6292cadd29dd59"
EXPECTED={
    "ccm_set_fn0_config":(0x30e40,92),
    "ccm_set_ig0_config":(0x30e9c,1280),
    "ccm_set_fmt":(0x314c8,80),
    "ccm_probe":(0x31518,204),
}
CALL26=283
TARGETS=tuple(EXPECTED)
def require(ok:bool, msg:str)->None:
    if not ok: raise ValueError(msg)
def file_sha(path:Path)->str:
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def enclosing_function(functions:list[tuple[int,int,str]],offset:int)->str|None:
    matches=[name for start,size,name in functions if start<=offset<start+size]
    if not matches:return None
    require(len(matches)==1,f"ambiguous_function_owner_at_{offset:x}")
    return matches[0]

def records_for_target(raw:list[dict[str,Any]])->dict[str,list[dict[str,Any]]]:
    grouped={name:[] for name in TARGETS}
    for rec in raw:
        target=rec["target_symbol"]
        if target not in grouped: continue
        grouped[target].append(rec)
    for arr in grouped.values():
        arr.sort(key=lambda rec:(rec["source_section"],rec["source_offset"],rec["relocation_type"]))
    return grouped

def synthetic()->dict[str,Any]:
    fs=[(0x100,0x40,"caller"),(0x200,0x20,"callee")]
    require(enclosing_function(fs,0x111)=="caller","func_owner_bad")
    require(enclosing_function(fs,0x140) is None,"func_end_bad")
    require(enclosing_function(fs,0x999) is None,"unmapped_bad")
    raw=[
        {"source_section":".text","source_offset":0x111,"source_function":"caller",
         "target_symbol":"ccm_set_fmt","relocation_type":CALL26},
        {"source_section":".data","source_offset":0x20,"source_function":None,
         "target_symbol":"ccm_set_ig0_config","relocation_type":257},
        {"source_section":".text","source_offset":0x200,"source_function":"callee",
         "target_symbol":"another_function","relocation_type":CALL26},
    ]
    got=records_for_target(raw)
    require(len(got["ccm_set_fmt"])==1,"code_call_missing")
    require(len(got["ccm_set_ig0_config"])==1,"callback_pointer_missing")
    require(len(got["ccm_set_fn0_config"])==0,"missing_target_should_be_empty")
    return {"schema":"stage28-ccm-entrypoint-fixtures-v1","status":"PASS_synthetic",
            "owner_boundary_tests":3,"relocation_classification_tests":3,
            "original_firmware_loaded":False,"pixel_equation_proven":False,
            "camera_renderer_modified":False}

def inspect(driver:Path,prior_path:Path)->dict[str,Any]:
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    require(file_sha(driver)==DRIVER_SHA,"wrong_firmware_driver_hash")
    require(file_sha(prior_path)==PRIOR_SHA,"wrong_prior_driver_evidence")
    prior=json.loads(prior_path.read_text())
    require(prior["sha256"]==DRIVER_SHA and
            prior["component_binding"]["register_base_offset_verified"] is True,
            "prior_driver_boundary_changed")
    with driver.open("rb") as f:
        elf=ELFFile(f)
        require(elf["e_type"]=="ET_REL" and
                elf["e_machine"]=="EM_AARCH64" and
                elf.elfclass==64 and elf.little_endian,
                "unexpected_Eagle2_ELF")
        text_idx=elf.get_section_index(".text")
        require(text_idx is not None,"missing_text")
        symtab=elf.get_section_by_name(".symtab")
        require(symtab is not None,"missing_kernel_symtab")
        symbols=list(symtab.iter_symbols())
        by_name={}
        for sym in symbols:
            if sym.name and sym["st_shndx"]==text_idx and
                    sym["st_info"]["type"]=="STT_FUNC":
                by_name.setdefault(sym.name,[]).append(sym)
        for name,(at,size) in EXPECTED.items():
            arr=by_name.get(name,[])
            require(len(arr)==1 and (int(arr[0]["st_value"]),int(arr[0]["st_size"]))==(at,size),
                    f"ccm_symbol_identity_changed_{name}")

        # STT_FUNC and relocation addresses are *section offsets*, never
        # runtime virtual addresses. A collision is fail-closed.
        funcs=sorted((int(s["st_value"]),int(s["st_size"]),s.name)
                     for s in symbols if s.name and
                     s["st_shndx"]==text_idx and s["st_info"]["type"]=="STT_FUNC"
                     and int(s["st_size"])>0)
        require(not any(funcs[i][0]==funcs[i+1][0] for i in range(len(funcs)-1)),
                "duplicate_function_start_requires_manual_review")
        refs=[]
        total_relocations=0
        for sec in elf.iter_sections():
            if not isinstance(sec,RelocationSection):continue
            source_idx=int(sec["sh_info"])
            target_symbols=elf.get_section(int(sec["sh_link"]))
            src_section=elf.get_section(source_idx)
            for reloc in sec.iter_relocations():
                total_relocations+=1
                target=target_symbols.get_symbol(int(reloc["r_info_sym"]))
                if target.name not in TARGETS:continue
                source_off=int(reloc["r_offset"])
                # Incoming R_AARCH64_CALL26 is only a CALL when source is code.
                kind=int(reloc["r_info_type"])
                owner=enclosing_function(funcs,source_off) if source_idx==text_idx else None
                refs.append({
                    "source_section":src_section.name,
                    "source_offset":source_off,
                    "source_function":owner,
                    "target_symbol":target.name,
                    "relocation_type":kind})
        grouped=records_for_target(refs)
        # A direct relocation already independently demonstrated by Stage17;
        # pin it as a useful sanity check before trusting new incoming refs.
        found=grouped["ccm_set_fn0_config"]
        require(any(x["source_function"]=="ccm_set_fmt" and
                    x["source_section"]==".text" and
                    x["source_offset"]==0x314f0 and
                    x["relocation_type"]==CALL26 for x in found),
                "prior_ccm_set_fmt_call26_missing")
        # Count *all* CCM-prefixed functions; metadata alone is not an
        # assertion that there is or is not a pixel arithmetic implementation.
        names=sorted(s.name for s in symbols if s.name.startswith("ccm_")
                     and s["st_info"]["type"]=="STT_FUNC" and
                     s["st_shndx"]==text_idx)
        require("ccm_set_ig0_config" in names and "ccm_set_fmt" in names,
                "expected_ccm_family_missing")
        packed={}
        for name in TARGETS:
            arr=grouped[name]
            packed[name]={
                "relocation_count":len(arr),
                "incoming_text_CALL26":[{
                    "source_function":x["source_function"],
                    "source_offset_hex":hex(x["source_offset"])
                } for x in arr if x["source_section"]==".text"
                      and x["relocation_type"]==CALL26],
                "non_call_reference_families":sorted(set(x["source_section"] for x in arr
                                                if x["source_section"]!=".text")),
                "non_CALL26_text_references":sum(x["source_section"]==".text"
                                                and x["relocation_type"]!=CALL26 for x in arr),
                "data_references_by_section":{section:sum(x["source_section"]==section
                                                        for x in arr)
                                           for section in sorted(set(x["source_section"]
                                            for x in arr if x["source_section"]!=".text"))},
            }
    return {
        "schema":"stage28-X2DII1_3_16_2-Eagle2-CCM-entrypoint-links-v1",
        "status":"PASS_exact_source_entrypoint_metadata",
        "source_module_sha256":DRIVER_SHA,
        "prior_driver_metadata_sha256":PRIOR_SHA,
        "platform":"Eagle2",
        "target_kernel_module":"vcam_driver.ko",
        "elf_type":"ET_REL","elf_machine":"EM_AARCH64",
        "all_kernel_relocations_seen":total_relocations,
        "ccm_named_function_count":len(names),
        "ccm_function_names":names,
        "targets":packed,
        "source_callers_are_section_relative_not_live_addresses":True,
        "non_call_relocations_not_assumed_to_be_callers":True,
        "no_original_rgb_pixels_evaluated":True,
        "six_coefficient_pixel_formula_proven":False,
        "coefficient_Q_scale_proven":False,
        "main_ccm_pixel_input_domain_proven":False,
        "camera_saved_photo_render_authorized":False,
        "vendor_instruction_bytes_exported":False,
        "vendor_tuning_values_exported":False,
        "phone_renderer_modified":False,
        "next_hard_gate":"Exact MAIN CCM hardware specification or controlled isolated pre-post-CCM pixel oracle"
    }

def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--module",type=Path)
    parser.add_argument("--prior",type=Path,
        default=Path("hasselblad_native_audit/main_colour_20261019/ccm/ccm_driver_evidence.json"))
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.self_test:
        report=synthetic()
    else:
        require(args.module is not None,"module_required")
        report=inspect(args.module,args.prior)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
