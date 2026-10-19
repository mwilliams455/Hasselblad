#!/usr/bin/env python3
"""Metadata-only audit of four CCM setters in one pinned ET_REL module.

No module loading, vendor execution, hardware access or full disassembly output.
Requires pyelftools and capstone. Section offsets are not loaded virtual addresses.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection


MODULE_SHA256 = "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
FUNCTIONS = {
    "ccm_set_fn0_config": (0x30E40, 92),
    "ccm_set_ig0_config": (0x30E9C, 1280),
    "ccm_set_fmt": (0x314C8, 80),
    "ccm_probe": (0x31518, 204),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(path):
    data = path.read_bytes()
    require(sha(data) == MODULE_SHA256, "Wrong firmware/module identity")
    elf = ELFFile(io.BytesIO(data))
    require(elf["e_type"] == "ET_REL" and elf["e_machine"] == "EM_AARCH64"
            and elf.little_endian, "Expected little-endian AArch64 ET_REL")
    text_index = elf.get_section_index(".text")
    text = elf.get_section(text_index).data()
    symbols = {s.name: s for s in elf.get_section_by_name(".symtab").iter_symbols()}
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    results = {}
    for name, (offset, size) in FUNCTIONS.items():
        s = symbols[name]
        require(s["st_shndx"] == text_index and (s["st_value"], s["st_size"]) == (offset, size),
                f"Function symbol mismatch: {name}")
        code = text[offset:offset + size]
        instructions = list(decoder.disasm(code, offset))
        require(sum(i.size for i in instructions) == size, f"Incomplete decode: {name}")
        relocations = []
        for section in elf.iter_sections():
            if not isinstance(section, RelocationSection) or section["sh_info"] != text_index:
                continue
            symtab = elf.get_section(section["sh_link"])
            for r in section.iter_relocations():
                if offset <= r["r_offset"] < offset + size:
                    target = symtab.get_symbol(r["r_info_sym"])
                    relocations.append({"at_text_offset": hex(r["r_offset"]),
                                        "aarch64_type": r["r_info_type"], "symbol": target.name,
                                        "symbol_section_index": target["st_shndx"],
                                        "addend": hex(r["r_addend"])})
        results[name] = {"text_offset": hex(offset), "bytes": size, "sha256": sha(code),
                         "instruction_count": len(instructions),
                         "mnemonics": sorted({i.mnemonic for i in instructions}),
                         "relocations": relocations}
    require(not results["ccm_set_fn0_config"]["relocations"], "Unexpected fn0 relocation")
    require(not results["ccm_set_ig0_config"]["relocations"], "Unexpected ig0 relocation")
    call = [r for r in results["ccm_set_fmt"]["relocations"] if r["at_text_offset"] == "0x314f0"]
    require(len(call) == 1 and call[0]["symbol"] == "ccm_set_fn0_config"
            and call[0]["aarch64_type"] == 283, "set_fmt CALL26 target mismatch")
    for name in ("ccm_set_fn0_config", "ccm_set_ig0_config"):
        require(not {"bl", "blr", "mul", "madd", "smaddl", "fmul", "fmadd"}
                .intersection(results[name]["mnemonics"]), "Unexpected call or multiply in setter")
    # Follow the one separately identified CCM component-binding slice, not the
    # rest of this large platform constructor. Resolve the ET_REL call relocation.
    binding_relocations = []
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection) or section["sh_info"] != text_index:
            continue
        symtab = elf.get_section(section["sh_link"])
        for r in section.iter_relocations():
            if r["r_offset"] == 0x59FBC:
                binding_relocations.append((r["r_info_type"], symtab.get_symbol(r["r_info_sym"]).name))
    require(binding_relocations == [(283, "ccm_probe")], "CCM component probe CALL26 mismatch")
    selected = {i.address: i for i in decoder.disasm(text[0x59FBC:0x59FF4], 0x59FBC)}
    for at, mnemonic, register, base, offset in (
        (0x59FC0, "str", "x0", "x28", 0x510),
        (0x59FD4, "str", "w1", "x0", 0x44),
        (0x59FDC, "ldr", "x1", "x28", 0x2A0),
        (0x59FE4, "ldr", "x2", "x28", 0x510),
        (0x59FE8, "ldr", "x1", "x1", 0x48),
        (0x59FF0, "str", "x1", "x2", 0x50),
    ):
        ins = selected[at]
        require(ins.mnemonic == mnemonic and ins.reg_name(ins.operands[0].reg) == register,
                f"Binding data register mismatch: {at:#x}")
        mem = ins.operands[1]
        require(mem.type == ARM64_OP_MEM and ins.reg_name(mem.mem.base) == base and mem.mem.disp == offset,
                f"Binding memory offset mismatch: {at:#x}")
    add, component = selected[0x59FEC], selected[0x59FD0]
    require(add.mnemonic == "add" and add.reg_name(add.operands[0].reg) == "x1"
            and add.reg_name(add.operands[1].reg) == "x1" and add.operands[2].type == ARM64_OP_IMM
            and add.operands[2].imm << add.operands[2].shift.value == 0x2C000, "CCM register base offset mismatch")
    require(component.mnemonic == "mov" and component.reg_name(component.operands[0].reg) == "w1"
            and component.operands[1].imm == 0x4B, "CCM component ID mismatch")
    return {
        "schema": 1, "audit_date": "2026-10-19", "firmware": "X2D II 1.3.16.2",
        "file": "system/lib/modules/vcam_driver.ko", "bytes": len(data), "sha256": MODULE_SHA256,
        "elf_type": "ET_REL", "elf_machine": "EM_AARCH64", "section": ".text",
        "script_sha256": sha(Path(__file__).read_bytes()), "functions": results,
        "component_binding": {
            "container_function": "plat_eagle2_probe_components", "slice_text_offset": "0x59fbc",
            "slice_bytes": 56, "slice_sha256": sha(text[0x59FBC:0x59FF4]),
            "probe_relocation": "R_AARCH64_CALL26 -> ccm_probe at .text+0x59fbc",
            "context_member": "0x510", "component_id": "0x4b", "register_base_member": "0x50",
            "register_base_source": "[[platform_context+0x2a0]+0x48] +0x2c000",
            "source_is_common_mapped_yuv_pp_base": "identified by the separate MAIN format audit",
            "register_base_offset_verified": True,
        },
        "manual_dataflow_findings": {
            "fn0": "Two input fields are packed into low/high 16 bits of register +0x10; no channel-order enum or pixel arithmetic established",
            "ig0_copy_loops": [
                {"input_offset": "0x1e", "input_stride": 2, "input_read_bits": 16,
                 "count": 9, "register_start": "0x34c", "register_stride": 4,
                 "register_bits_written": 8, "loop_text_offset": "0x31068"},
                {"input_offset": "0x30", "input_stride": 2, "input_read_bits": 16,
                 "count": 9, "register_start": "0x370", "register_stride": 4,
                 "register_bits_written": 16, "loop_text_offset": "0x31094"},
                {"input_offset": "0x58", "input_stride": 1, "input_read_bits": 8,
                 "count": 16, "register_start": "0x28", "register_stride": 4,
                 "register_bits_written": 8, "loop_text_offset": "0x31168"},
                {"input_offset": "0x68", "input_stride": 2, "input_read_bits": 16,
                 "count": 16, "register_start": "0x18c", "register_stride": 4,
                 "register_bits_written": 16, "loop_text_offset": "0x31194"},
                {"input_offset": "0x8d", "input_stride": 1, "input_read_bits": 8,
                 "count": 25, "register_start": "0xac", "register_stride": 4,
                 "register_bits_written": 8, "loop_text_offset": "0x31238"},
                {"input_offset": "0xa6", "input_stride": 1, "input_read_bits": 8,
                 "count": 25, "register_start": "0x110", "register_stride": 4,
                 "register_bits_written": 8, "loop_text_offset": "0x31260"},
            ],
            "ig0_unrolled_array_transfers": [
                {"input_offset": "0x10", "input_stride": 1, "input_read_bits": 8,
                 "count": 3, "register_start": "0x7c", "register_stride": 4,
                 "register_field_bits": 9, "note": "Input byte cannot set bit8; full9-bit destination field is cleared first"},
                {"input_offset": "0x13", "input_stride": 1, "input_read_bits": 8,
                 "count": 5, "register_start": "0x14", "register_stride": 4, "register_field_bits": 8},
                {"input_offset": "0x48", "input_stride": 2, "input_read_bits": 16,
                 "count": 6, "register_start": "0x94", "register_stride": 4, "register_field_bits": 16},
                {"input_offset": "0x88", "input_stride": 1, "input_read_bits": 8,
                 "count": 5, "register_start": "0x68", "register_stride": 4, "register_field_bits": 8},
                {"input_offset": "0xc0", "input_stride": 2, "input_read_bits": 16,
                 "count": 6, "register_start": "0x174", "register_stride": 4, "register_field_bits": 9},
            ],
            "ig0_sign_extended_fields": "Input six int16 values at +0xcc..+0xd6 are sign-extended and repeated into 16 groups of six 32-bit registers at +0x1cc..+0x348",
            "ig0_end": "Updates register +0x39c low five bits to 1, sets bit0 of base register, returns 0",
        },
        "limits": [
            "Selected function bytes and relocations were inspected statically; the module was not loaded or executed",
            "These functions program configuration registers; no RGB multiply/accumulate pixel implementation is present in the two setters",
            "Nine fields are consistent with coefficient groups, but field names, combined representation, sign, Q scale, matrix order, input/output colour spaces and clamp rules remain unproven",
            "The verified CCM mapping offset+0x2c000 and 96-word region+0x1cc..+0x348 match the separate MAIN lmtx physical descriptors; common physical base0xf3200000 is inferred from that cross-audit match, not from an absolute address literal in the binding slice",
            "No inference is made from unrelated display or other-SoC headers",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.module)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": str(args.out), "functions_verified": len(report["functions"]),
                      "module_sha256": report["sha256"]}))
