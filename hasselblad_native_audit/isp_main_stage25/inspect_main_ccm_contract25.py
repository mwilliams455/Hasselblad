#!/usr/bin/env python3
"""Stage25 X2D II MAIN CCM descriptor-to-driver contract join.

This tool does not render pixels and never exports vendor tuning values. It joins:
1. MAIN_CCM IQ getter symbols from exact librcam.so;
2. the previously verified relocated MAIN CCM register-metadata receipt;
3. the previously verified ccm_set_ig0_config destination ranges.

The result names hardware register families without inventing the six-coefficient
pixel equation, Q format, RGB order, region selector, clamp or rounding rules.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import lzma
from pathlib import Path
import re
from typing import Any

LIBRCAM_SHA="3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66"
DRIVER_SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
CONFIG_SHA="2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286"
PRIOR_METADATA_SHA="ce743634dcb8767b42e8c9513034fca80e90a6db786e23521bbe68e84c0e79ea"
PARSER_SHA="0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec"
CCM_BASE=0xF322C000
EXPECTED_LMTX_GETTER=0x33F960
EXPECTED_DRIVER_FUNCTION=(0x30E9C,1280)

# Destination ranges independently verified by the bounded Stage17/main_colour
# ccm_set_ig0_config audit. Stage25 only joins exact names to these ranges.
DRIVER_ARRAY_FAMILIES=(
    (0x014,5,4,"param_struct_0x13_5xu8_to_register_low8"),
    (0x028,16,4,"param_struct_0x58_16xu8_to_register_low8"),
    (0x068,5,4,"param_struct_0x88_5xu8_to_register_low8"),
    (0x07C,3,4,"param_struct_0x10_3xu8_to_register_low8"),
    (0x094,6,4,"param_struct_0x48_6xu16_to_register_low16"),
    (0x0AC,25,4,"param_struct_0x8d_25xu8_to_register_low8"),
    (0x110,25,4,"param_struct_0xa6_25xu8_to_register_low8"),
    (0x174,6,4,"param_struct_0xc0_6xu16_to_register_low9"),
    (0x18C,16,4,"param_struct_0x68_16xu16_to_register_low16"),
    (0x1CC,96,4,"param_struct_0xcc_6xint16_repeated_16_groups_sign_extended"),
    (0x34C,9,4,"param_struct_0x1e_9xu16_to_register_low8"),
    (0x370,9,4,"param_struct_0x30_9xu16_to_register_low16"),
)

def require(ok:bool,reason:str)->None:
    if not ok: raise ValueError(reason)

def sha256(path:Path)->str:
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def all_symbols(elf)->list[Any]:
    out=[]
    for name in (".dynsym",".symtab"):
        sec=elf.get_section_by_name(name)
        if sec is not None and hasattr(sec,"iter_symbols"):
            out.extend(s for s in sec.iter_symbols() if s["st_shndx"]!="SHN_UNDEF" and s.name)
    debug=elf.get_section_by_name(".gnu_debugdata")
    if debug is not None:
        data=lzma.decompress(debug.data())
        require(len(data)<=64*1024*1024,"debugdata_too_large")
        from elftools.elf.elffile import ELFFile
        de=ELFFile(io.BytesIO(data))
        sec=de.get_section_by_name(".symtab")
        if sec is not None and hasattr(sec,"iter_symbols"):
            out.extend(s for s in sec.iter_symbols() if s["st_shndx"]!="SHN_UNDEF" and s.name)
    return out

def driver_family(offset:int)->str:
    for start,count,stride,name in DRIVER_ARRAY_FAMILIES:
        end=start+(count-1)*stride
        if start<=offset<=end and (offset-start)%stride==0: return name
    return "scalar_or_bitfield_not_in_prior_array_family_summary"

def summarize_records(records:list[dict[str,Any]],getter_names:dict[int,str])->list[dict[str,Any]]:
    by_index={}
    for rec in records:
        if rec.get("event")=="parameter":
            by_index.setdefault(int(rec["index"]),[]).append(rec)
    require(sorted(by_index)==list(range(27)),"expected_exact_27_parameter_indices")
    result=[]
    for index in range(27):
        rows=by_index[index]
        getter=int(rows[0]["iq_getter_va"],16)
        require(all(int(x["iq_getter_va"],16)==getter for x in rows),"getter_mismatch_within_parameter")
        full_name=getter_names.get(getter)
        require(full_name is not None,f"missing_getter_symbol_at_{getter:#x}")
        prefix="DIQ_iq_main_ccm_"
        require(full_name.startswith(prefix),"unexpected_getter_prefix")
        families=[]
        for row in rows:
            addr=int(row["parent_word2"],16); off=addr-CCM_BASE
            require(0<=off<0x1000,"register_outside_expected_ccm_page")
            families.append({
                "register_parent_id":int(row["parent_register_id"]),
                "register_offset_hex":f"0x{off:03x}",
                "group_num":int(row["group_num"]),
                "field_mask":int(row["descriptor_word3"]),
                "driver_destination_family":driver_family(off)})
        result.append({
            "parameter_index":index,
            "parameter_name":full_name[len(prefix):],
            "iq_getter_va":f"0x{getter:x}",
            "register_family_count":len(families),
            "register_families":families})
    return result

def config_parameter_names(config:Path,parser_path:Path)->set[str]:
    import importlib.util,sys
    require(sha256(parser_path)==PARSER_SHA,"unexpected_iq_parser")
    spec=importlib.util.spec_from_file_location("hb25_iq_parser",parser_path)
    require(spec is not None and spec.loader is not None,"parser_import_failed")
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    conf=mod.read_config(config)
    record=conf["iq_table"]["data"][0]["main_ccm"][0]
    require(isinstance(record,dict),"missing_main_ccm_record")
    return set(record.keys())

def inspect(repo_root:Path,firmware_root:Path)->dict[str,Any]:
    from elftools.elf.elffile import ELFFile
    audit=repo_root/"hasselblad_native_audit"
    lib=firmware_root/"system/lib64/librcam.so"
    driver=firmware_root/"system/lib/modules/vcam_driver.ko"
    config=firmware_root/"system/etc/iq/hb722_config.json"
    prior=audit/"main_colour_20261019/ccm/ccm_metadata_original_execution.json"
    parser_path=audit/"photographic_path/inspect_iq_config.py"
    require(sha256(lib)==LIBRCAM_SHA,"wrong_librcam")
    require(sha256(driver)==DRIVER_SHA,"wrong_vcam_driver")
    require(sha256(config)==CONFIG_SHA,"wrong_iq_config")
    require(sha256(prior)==PRIOR_METADATA_SHA,"wrong_prior_metadata_receipt")
    metadata=json.loads(prior.read_text())
    require(metadata.get("library_sha256")==LIBRCAM_SHA,"prior_receipt_library_mismatch")
    require(metadata.get("pixel_renderer_validated") is False,"prior_receipt_scope_changed")

    with lib.open("rb") as f:
        elf=ELFFile(f)
        require(elf["e_machine"]=="EM_AARCH64" and elf.elfclass==64,"unexpected_librcam_elf")
        symbols=all_symbols(elf)
    dup={}
    for sym in symbols:
        if sym.name.startswith("DIQ_iq_main_ccm_") and int(sym["st_value"]):
            dup.setdefault(int(sym["st_value"]),[]).append(sym.name)
    getter_names={}
    for va,names in dup.items():
        unique=sorted(set(names))
        require(len(unique)==1,f"ambiguous_ccm_getter_symbol_{va:#x}")
        getter_names[va]=unique[0]

    parameters=summarize_records(metadata["records"],getter_names)
    require(len(parameters)==27,"parameter_join_count")
    require(parameters[24]["parameter_name"]=="lmtx_fw","lmtx_index_changed")
    require(int(parameters[24]["iq_getter_va"],16)==EXPECTED_LMTX_GETTER,"lmtx_getter_changed")
    require(parameters[24]["register_family_count"]==16,"lmtx_register_family_count")
    offsets=[int(x["register_offset_hex"],16) for x in parameters[24]["register_families"]]
    require(offsets[0]==0x1CC and offsets[-1]==0x334,"lmtx_parent_offsets_changed")
    require(all(x["group_num"]==6 and x["field_mask"]==0xFFFF for x in parameters[24]["register_families"]),"lmtx_descriptor_shape_changed")
    require(all(x["driver_destination_family"].startswith("param_struct_0xcc") for x in parameters[24]["register_families"]),"lmtx_driver_join_changed")

    iq_names=config_parameter_names(config,parser_path)
    joined_names={x["parameter_name"] for x in parameters}

    with driver.open("rb") as f:
        de=ELFFile(f)
        require(de["e_machine"]=="EM_AARCH64","unexpected_driver_elf")
        symtab=de.get_section_by_name(".symtab")
        require(symtab is not None,"driver_symtab_missing")
        match=[s for s in symtab.iter_symbols() if s.name=="ccm_set_ig0_config"]
        require(len(match)==1,"ccm_set_ig0_config_symbol_count")
        require((int(match[0]["st_value"]),int(match[0]["st_size"]))==EXPECTED_DRIVER_FUNCTION,"driver_function_identity_changed")

    named={}
    for p in parameters:
        for rf in p["register_families"]:
            named.setdefault(rf["driver_destination_family"],[]).append(p["parameter_name"])
    named={k:sorted(set(v)) for k,v in sorted(named.items())}
    equation_tokens=re.compile(r"(?:offdiag|row[_-]?sum|col[_-]?sum|pairwise|neutral[_-]?preserv|matrix[_-]?mul|rgb2rgb)",re.I)
    hits=sorted(n for n in joined_names if equation_tokens.search(n))
    return {
        "schema":"hasselblad-stage25-main-ccm-descriptor-driver-join-v1",
        "status":"PASS_exact_source_descriptor_driver_join",
        "firmware":"Hasselblad X2D II 100C 1.3.16.2",
        "source_identity":{"librcam_sha256":LIBRCAM_SHA,"vcam_driver_sha256":DRIVER_SHA,"iq_config_sha256":CONFIG_SHA,"prior_metadata_sha256":PRIOR_METADATA_SHA},
        "parameter_count":len(parameters),
        "parameters":parameters,
        "config_parameter_name_count":len(iq_names),
        "config_names_missing_from_register_join":sorted(iq_names-joined_names),
        "register_join_names_absent_from_data0_config":sorted(joined_names-iq_names),
        "named_driver_destination_families":named,
        "lmtx_fw":{
            "parameter_index":24,"register_groups":16,"coefficients_per_group":6,
            "descriptor_mask":65535,"first_register_offset_hex":"0x1cc",
            "last_group_base_offset_hex":"0x334","last_scalar_register_offset_hex":"0x348",
            "driver_source_family":"param_struct_0xcc_6xint16_repeated_16_groups_sign_extended",
            "pixel_equation_proven":False,"fraction_bits_proven":False,
            "region_selector_proven":False,"channel_order_proven":False},
        "six_coefficient_candidate_review":{
            "direct_parameter_name_hits_supporting_pairwise_or_row_sum_equation":hits,
            "neutral_preserving_constrained_3x3_hypothesis_promoted":False,
            "reason":"No exact field/symbol name is sufficient to establish the six-coefficient hardware multiply; a matched ISP oracle or MAIN-specific hardware specification is still required."},
        "vendor_tuning_values_exported":False,"vendor_instruction_bytes_exported":False,
        "pixel_samples_processed":False,"photographic_render_authorized":False,
        "production_phone_renderer_modified":False,
        "next_gate":"Use the exact parameter-to-register names to target a MAIN-specific Eagle2 component description or a controlled before/after ISP pixel oracle; do not infer the six-coefficient equation from shape alone."}

def self_test()->None:
    names={0x1000+0x80*i:f"DIQ_iq_main_ccm_p{i}" for i in range(27)}
    names[0x1000+0x80*24]="DIQ_iq_main_ccm_lmtx_fw"
    records=[]
    starts=[0x004,0x004,0x004,0x004,0x00c,0x088,0x08c,0x090,0x090,0x094,0x098,0x09c,0x0a0,0x0a4,0x0a8,0x014,0x028,0x068,0x07c,0x0ac,0x110,0x174,0x180,0x18c]
    for i,off in enumerate(starts):
        count={15:5,16:16,17:5,18:3,19:25,20:25,21:3,22:3,23:16}.get(i,1)
        records.append({"event":"parameter","index":i,"iq_getter_va":hex(0x1000+0x80*i),"parent_word2":hex(CCM_BASE+off),"parent_register_id":4000+i,"group_num":count,"descriptor_word3":0xFFFF})
    for g in range(16):
        records.append({"event":"parameter","index":24,"iq_getter_va":hex(0x1000+0x80*24),"parent_word2":hex(CCM_BASE+0x1cc+g*0x18),"parent_register_id":4125+3*g,"group_num":6,"descriptor_word3":0xFFFF})
    for i,off in ((25,0x34c),(26,0x370)):
        records.append({"event":"parameter","index":i,"iq_getter_va":hex(0x1000+0x80*i),"parent_word2":hex(CCM_BASE+off),"parent_register_id":4173+3*(i-25),"group_num":9,"descriptor_word3":0xFFFF})
    out=summarize_records(records,names)
    assert len(out)==27
    assert out[15]["register_families"][0]["driver_destination_family"].startswith("param_struct_0x13")
    assert out[24]["parameter_name"]=="lmtx_fw"
    assert out[24]["register_families"][0]["register_offset_hex"]=="0x1cc"
    assert out[25]["register_families"][0]["driver_destination_family"].startswith("param_struct_0x1e")
    assert driver_family(0x004).startswith("scalar_or_bitfield")
    print(json.dumps({"status":"PASS","synthetic_parameter_indices":27,"driver_family_join_cases":12,"vendor_assets_loaded":False,"pixel_equation_proven":False}))

def main()->None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--repo-root",type=Path,default=Path.cwd())
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    if a.self_test: self_test(); return
    require(a.firmware_root is not None and a.output is not None,"firmware_root_and_output_required")
    report=inspect(a.repo_root.resolve(),a.firmware_root.resolve())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":report["status"],"parameter_count":report["parameter_count"],"config_name_count":report["config_parameter_name_count"],"lmtx_pixel_equation_proven":False}))

if __name__=="__main__":
    main()
