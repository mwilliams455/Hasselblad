#!/usr/bin/env python3
"""Stage29D: exact X2D II B2R callback table provenance (metadata only).

Reconstruct ELF relocations around a verified B2R function-pointer slot. A
callback-table name alone is not an original argument-type proof or pixel oracle.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SHA="29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
REFERENCE_SECTION=".rodata"
REFERENCE_OFFSET=0x5658
CALLBACK_NAME="b2r_pad_set_fh_fmt"
ABS64=257
WINDOW=0x80

def require(x,msg):
    if not x:raise ValueError(msg)

def sha(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()

def containing_object(objects,offset):
    return [item for item in objects if item[0]<=offset<item[0]+item[1]]

def test():
    a=[(0x100,24,"ops"),(0x200,32,"another")]
    require(containing_object(a,0x108)==[a[0]],"owner_interval")
    require(containing_object(a,0x118)==[],"owner_end_exclusive")
    require(containing_object(a,0x1010)==[],"owner_outside")
    return {"schema":"stage29d-callback-object-synthetic-v1",
            "status":"PASS_synthetic","object_boundary_cases":3,
            "firmware_loaded":False,"X2D_record_type_proven":False}

def inspect(path):
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    require(sha(path)==SHA,"original_kernel_hash_mismatch")
    with path.open("rb") as f:
        elf=ELFFile(f)
        require(elf["e_type"]=="ET_REL" and elf["e_machine"]=="EM_AARCH64" and
                elf.elfclass==64 and elf.little_endian,"not_original_arm64_ELF")
        roindex=elf.get_section_index(REFERENCE_SECTION)
        require(roindex is not None,"rodata_missing")
        s=elf.get_section_by_name(".symtab")
        require(s is not None,"symtab_missing")
        symbols=list(s.iter_symbols())
        objects=[(int(sym["st_value"]),int(sym["st_size"]),sym.name)
                 for sym in symbols if sym.name and sym["st_shndx"]==roindex and
                 sym["st_info"]["type"]=="STT_OBJECT" and int(sym["st_size"])>0]
        objects.sort()
        rel=[]
        for sec in elf.iter_sections():
            if not isinstance(sec,RelocationSection) or int(sec["sh_info"])!=roindex:
                continue
            tab=elf.get_section(int(sec["sh_link"]))
            for row in sec.iter_relocations():
                off=int(row["r_offset"])
                if abs(off-REFERENCE_OFFSET)>WINDOW:continue
                target=tab.get_symbol(int(row["r_info_sym"]))
                rel.append({"source_offset":off,"source_offset_hex":hex(off),
                    "relocation_type":int(row["r_info_type"]),
                    "target_symbol":target.name or None,
                    "target_symbol_type":target["st_info"]["type"],
                    "target_section_index":str(target["st_shndx"]),
                    "addend":int(row["r_addend"]) if row.is_RELA() else None})
        rel.sort(key=lambda x:(x["source_offset"],x["relocation_type"]))
        matches=[a for a in rel if a["source_offset"]==REFERENCE_OFFSET and
                 a["target_symbol"]==CALLBACK_NAME and a["relocation_type"]==ABS64]
        require(len(matches)==1,"expected_B2R_pointer_slot_changed")
        owners=containing_object(objects,REFERENCE_OFFSET)
        # Section index-only references are not silently assigned an address
        # when the target uses an unnamed local symbol.
        neighborhood=[{"slot_offset_hex":a["source_offset_hex"],
                        "relative_to_B2R_slot_bytes":a["source_offset"]-REFERENCE_OFFSET,
                        "target_symbol":a["target_symbol"],
                        "relocation_type":a["relocation_type"],
                        "target_is_function":a["target_symbol_type"]=="STT_FUNC"}
                      for a in rel]
        return {"schema":"stage29d-X2DII-1_3_16_2-B2R-callback-ownership-v1",
                "status":"PASS_original_B2R_callback_reference_verified",
                "module_sha256":SHA,"B2R_function_pointer_rodata_offset_hex":hex(REFERENCE_OFFSET),
                "B2R_pointer_relocation_type":ABS64,
                "candidate_containing_STT_OBJECT_symbols":[
                    {"name":name,"start_hex":hex(offset),"size_bytes":size}
                    for offset,size,name in owners],
                "neighboring_relocation_symbols":neighborhood,
                "nearby_struct_name_is_not_type_or_ABI_proof":True,
                "original_X2D_B2R_record_type_identified":False,
                "X2D_frame_width_height_semantics_proven":False,
                "MAIN_CCM_pixel_equation_proven":False,
                "vendor_instruction_bytes_exported":False,
                "vendor_IQ_values_exported":False,
                "Android_saved_photo_changed":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--module",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    d=test() if a.self_test else inspect(a.module if a.module else
          (_ for _ in ()).throw(ValueError("module_required")))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps(d,sort_keys=True))

if __name__=="__main__":main()
