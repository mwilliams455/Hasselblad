#!/usr/bin/env python3
"""Reproduce bounded MAIN LUT register/header findings from local vendor files.

Only metadata, counts, hashes, symbol locations and selected register constants
are written. This never extracts vendor headers, disassembly or colour arrays.
It also never opens a camera device or loads a kernel module.
Requires pyelftools and Capstone; the frozen inert IQ parser is reused.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import lzma
from pathlib import Path
import re
import struct
import sys
import tarfile

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection


AUDIT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AUDIT_ROOT / "photographic_path"))
from inspect_iq_config import read_config  # noqa: E402; original frozen inert parser


PINNED = {
    "system/lib/modules/vcam_driver.ko": "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e",
    "system/lib/modules/cam_vreg.ko": "26cf2246d56a36a5f7d107799ddced307ed94e53ac22c9928962a0fcff920ff6",
    "system/lib/modules/kheaders.ko": "b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b",
    "system/lib64/librcam.so": "3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66",
    "system/lib64/libdcam_dump_register.so": "657cadb8d39b141aad22f432a9df9151ac1feab8b4289ee35465230dfe4d3f0d",
    "system/etc/iq/hb722_config.json": "2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned_file(root: Path, relative: str) -> bytes:
    data = (root / relative).read_bytes()
    if sha256(data) != PINNED[relative]:
        raise ValueError(f"Hash mismatch for {relative}")
    return data


def function_metadata(elf: ELFFile, name: str) -> dict:
    symbols = elf.get_section_by_name(".symtab").get_symbol_by_name(name)
    if not symbols or len(symbols) != 1:
        raise ValueError(f"Missing or ambiguous kernel symbol {name}")
    symbol = symbols[0]
    section_index = symbol["st_shndx"]
    section = elf.get_section(section_index)
    offset, size = int(symbol["st_value"]), int(symbol["st_size"])
    code = section.data()[offset:offset + size]
    if len(code) != size:
        raise ValueError("Function outside section")
    relocation_records = []
    for relocation_section in elf.iter_sections():
        if not isinstance(relocation_section, RelocationSection) or relocation_section["sh_info"] != section_index:
            continue
        symbols_for_reloc = elf.get_section(relocation_section["sh_link"])
        for relocation in relocation_section.iter_relocations():
            where = int(relocation["r_offset"])
            if offset <= where < offset + size:
                target = symbols_for_reloc.get_symbol(relocation["r_info_sym"])
                # Non-code relocation values are intentionally not expanded to vendor strings.
                if relocation["r_info_type"] == 283:  # R_AARCH64_CALL26
                    relocation_records.append({"call_section_offset": hex(where), "target": target.name,
                                               "target_section_offset": hex(int(target["st_value"])),
                                               "target_addend": int(relocation["r_addend"])})
    instructions = list(Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN).disasm(code, offset))
    if sum(instruction.size for instruction in instructions) != size:
        raise ValueError(f"Incomplete AArch64 decode for {name}")
    return {"name": name, "section": section.name, "section_offset": hex(offset), "bytes": size,
            "code_sha256": sha256(code), "instruction_count": len(instructions),
            "instruction_mnemonic_counts": dict(sorted(Counter(i.mnemonic for i in instructions).items())),
            "resolved_external_call_relocations": relocation_records}


def section_relative_call_targets(elf: ELFFile, addresses: list[int]) -> list[dict]:
    wanted = set(addresses)
    result = []
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection) or elf.get_section(section["sh_info"]).name != ".text":
            continue
        symbols = elf.get_section(section["sh_link"])
        for relocation in section.iter_relocations():
            offset = int(relocation["r_offset"])
            if offset in wanted:
                target = symbols.get_symbol(relocation["r_info_sym"])
                if relocation["r_info_type"] != 283:
                    raise ValueError("Expected AArch64 CALL26 relocation")
                result.append({"section_offset": hex(offset), "target": target.name,
                               "target_section_offset": hex(int(target["st_value"]))})
    if len(result) != len(wanted):
        raise ValueError("A selected direct-call relocation is missing")
    return sorted(result, key=lambda item: int(item["section_offset"], 16))


def virtual_bytes(elf: ELFFile, address: int, count: int) -> bytes:
    for segment in elf.iter_segments():
        if segment["p_type"] == "PT_LOAD" and segment["p_vaddr"] <= address and address + count <= segment["p_vaddr"] + segment["p_filesz"]:
            offset = address - segment["p_vaddr"]
            return segment.data()[offset:offset + count]
    raise ValueError("Address is outside file-backed PT_LOAD")


def register_descriptors(elf: ELFFile) -> list[dict]:
    result = []
    names = {2967: "MAIN_3DLUT control word", 2968: "tlut_en", 2969: "enable_pre_gamma",
             2970: "module_en_lut", 2996: "pre_gamma containing register array",
             2997: "pre_gamma element field", 2998: "lut_data"}
    for register_id, name in names.items():
        address = 0x4E6BD0 + 16 * register_id
        words = struct.unpack("<4I", virtual_bytes(elf, address, 16))
        kind = words[0] & 0xFFFF
        record = {"register_id": register_id, "name": name, "descriptor_va": hex(address),
                  "descriptor_type": kind, "virtual_byte_offset": hex(words[1])}
        if kind in (1, 2):
            record.update(physical_address=hex(words[2]), word_count=words[3])
        elif kind == 3:
            record.update(containing_register_id_high16=words[0] >> 16,
                          bit_position=words[2], mask=hex(words[3]))
        else:
            raise ValueError("Unexpected register descriptor type")
        result.append(record)
    return result


def inspect_headers(elf: ELFFile) -> dict:
    archive_bytes = elf.get_section_by_name(".rodata").data()
    tar_bytes = lzma.decompress(archive_bytes)
    if len(tar_bytes) > 100 * 1024 * 1024:
        raise ValueError("Header archive exceeds analysis bound")
    patterns = {
        "main_lut_name_or_address": re.compile(rb"MAIN_3DLUT|main_3dlut|0x[fF]320[0-9a-fA-F]{4}"),
        "lut_name": re.compile(rb"3d[_ -]?lut|lut[_ -]?3d|tlut", re.I),
    }
    selected = {
        "./include/media/dji/cs_isp_sc.h",
        "./include/soc/dji/display/dji_lcdc_e2.h",
        "./include/soc/dji/display/dji_lcdc_reg.h",
        "./include/uapi/dji/display/dji_lcdc_common_uapi.h",
        "./include/uapi/dji/rcam.h",
        "./include/uapi/dji/isp-dji.h",
    }
    macro_names = {
        "LCDC_V3_MIPI0_TLUT_OFFSET", "LCDC_V3_MIPI0_TLUT_MASK", "LCDC_V3_MIPI0_TLUT_ADDRESS",
        "LCDC_V3_MIPI0_TLUT_NUM", "LCDC_V3_HDMI_TLUT_ADDRESS", "LCDC_V3_HDMI_TLUT_NUM",
    }
    hits = []
    selected_records = []
    macros = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        members = archive.getmembers()
        total_regular_bytes = 0
        for member in members:
            if not member.isfile():
                continue
            total_regular_bytes += member.size
            content = archive.extractfile(member).read()
            counts = {key: len(pattern.findall(content)) for key, pattern in patterns.items()}
            record = {"path": member.name, "bytes": len(content), "sha256": sha256(content), "pattern_counts": counts}
            if any(counts.values()):
                hits.append(record)
            if member.name in selected:
                selected_records.append(record)
            if member.name == "./include/soc/dji/display/dji_lcdc_e2.h":
                for number, line in enumerate(content.decode().splitlines(), 1):
                    match = re.match(r"\s*#define\s+(\w+)\s+(\S+)", line)
                    if match and match.group(1) in macro_names:
                        macros.append({"name": match.group(1), "integer_value": int(match.group(2), 0), "line": number})
    return {"xz_bytes": len(archive_bytes), "xz_sha256": sha256(archive_bytes),
            "archive_member_count": len(members), "regular_file_bytes": total_regular_bytes,
            "scan_patterns": {name: pattern.pattern.decode() for name, pattern in patterns.items()},
            "hit_headers": hits, "selected_headers": selected_records,
            "display_only_macros": macros,
            "limitation": "Matching display TLUT extent is not MAIN packing, domain or interpolation evidence; E4 headers also occur in this multi-platform archive."}


def inspect_config(root: Path) -> dict:
    config = read_config(root / "system/etc/iq/hb722_config.json")
    selected = []
    for group in config["iq_table"]["data"]:
        if "main_3dlut" not in group:
            continue
        for record in group["main_3dlut"]:
            item = {"mode": group.get("mod_iq_mode")}
            for name in ("enable_pre_gamma", "module_en_lut", "tlut_en"):
                if name in record:
                    item[name] = record[name]
            if "pre_gamma" in record:
                values = record["pre_gamma"]
                packed = struct.pack(f"<{len(values)}I", *values)
                item["pre_gamma_summary"] = {
                    "word_count": len(values), "minimum": min(values), "maximum": max(values),
                    "json_array_sha256": sha256(json.dumps(values, separators=(",", ":")).encode()),
                    "uint32_little_endian_sha256": sha256(packed),
                }
            if len(item) > 1:
                selected.append(item)
    descriptor = config["iq_table"]["module"]["main_3dlut"]
    return {"pre_gamma_descriptor": descriptor["pre_gamma"],
            "pre_gamma_enable_descriptor": descriptor["enable_pre_gamma"],
            "selected_mode_values": selected,
            "parser_relative_path": "../../photographic_path/inspect_iq_config.py",
            "parser_sha256": sha256((AUDIT_ROOT / "photographic_path/inspect_iq_config.py").read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = {name: pinned_file(args.firmware_root, name) for name in PINNED}
    vcam = ELFFile(io.BytesIO(inputs["system/lib/modules/vcam_driver.ko"]))
    vreg = ELFFile(io.BytesIO(inputs["system/lib/modules/cam_vreg.ko"]))
    rcam = ELFFile(io.BytesIO(inputs["system/lib64/librcam.so"]))
    kheaders = ELFFile(io.BytesIO(inputs["system/lib/modules/kheaders.ko"]))
    vcam_functions = [function_metadata(vcam, name) for name in
                      ("lut_set_lut_info", "lut_set_format", "lut_set_size", "lut_init_seq", "lut_probe")]
    vreg_functions = [function_metadata(vreg, name) for name in
                      ("_vreg_get_access_addr", "_sync_single_data_node", "_vreg_io_if_write32")]
    dump_path = "/system/etc/cam_dump_register.json"
    dump_bytes = inputs["system/lib64/libdcam_dump_register.so"]
    dump_offset = dump_bytes.find(dump_path.encode() + b"\0")
    if dump_offset < 0:
        raise ValueError("Audited optional register JSON path disappeared")
    result = {
        "schema": 1,
        "scope": "MAIN camera register consumer and exact pre-gamma register/config provenance",
        "sources": [{"relative_path": name, "bytes": len(data), "sha256": sha256(data)} for name, data in inputs.items()],
        "vcam_functions": vcam_functions,
        "camera_vreg_functions": vreg_functions,
        "component_binding_calls": section_relative_call_targets(vcam, [0x59FBC, 0x5A0F4, 0x5A190, 0x5C300, 0x5C310, 0x6EA18]),
        "component_binding_observations": {
            "mapped_platform_resource": "yuv_pp_base",
            "resource_lookup_call": ".text+0x5c300",
            "resource_mapping_call": ".text+0x5c310",
            "mapping_result_field": "resource object+0x48; object saved at platform context+0x2a0",
            "lut_component_id": 78,
            "lut_binding": ".text+0x5a1a4..0x5a1c0: component ID0x4e; base is mapped yuv_pp_base",
            "ccm_component_id": 75,
            "ccm_binding": ".text+0x59fd0..0x59ff0: component ID0x4b; base is mapped yuv_pp_base+0x2c000",
            "gamma_component_id": 77,
            "gamma_binding": ".text+0x5a108..0x5a128: component ID0x4d; base is mapped yuv_pp_base+0x2e000",
            "precision_limit": "lut_set_format forwards width and height to lut_set_size; these functions contain no RGB precision or grid-axis selector",
        },
        "librcam_main_register_descriptors": register_descriptors(rcam),
        "kernel_headers": inspect_headers(kheaders),
        "actual_config_pre_gamma": inspect_config(args.firmware_root),
        "optional_register_map": {"library": "system/lib64/libdcam_dump_register.so", "path": dump_path,
                                  "path_string_file_offset": hex(dump_offset),
                                  "present_in_extracted_system": (args.firmware_root / dump_path.lstrip("/")).exists()},
        "not_established": ["MAIN RGB/component bank order", "MAIN grid-axis strides and knot positions",
                            "MAIN input/output normalization or transfer domain",
                            "MAIN hardware interpolation, integer rounding or saturation",
                            "A CPU pixel sampler linked to this MAIN table"],
        "source_sha256": sha256(Path(__file__).read_bytes()),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "report_sha256": sha256(args.output.read_bytes()),
                      "vcam_function_count": len(vcam_functions), "pre_gamma_register_count": 33,
                      "main_name_or_address_header_hits": sum(x["pattern_counts"]["main_lut_name_or_address"] for x in result["kernel_headers"]["hit_headers"])}))


if __name__ == "__main__":
    main()
