#!/usr/bin/env python3
"""Execute the exact X2D II kernel LUT register writer against guarded RAM.

This is a register-submission probe, not a pixel renderer or hardware emulator.
It reads a separately supplied, exact-hash original module. No vendor machine
code, original colour tables, photographs, or device files are written out.
Requires pyelftools and Unicorn. Outputs hashes/counts and derived conclusions.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
import unicorn
from unicorn import arm64_const as arm64


MODULE_PATH = "system/lib/modules/vcam_driver.ko"
MODULE_SHA256 = "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
FUNCTION = "lut_set_lut_info"
FUNCTION_OFFSET = 0x31F48
FUNCTION_BYTES = 324
FUNCTION_SHA256 = "d56ec8d675a29416ad0fca213aa4ff83e2b33cf5743453db1591fd7a045d3da4"

CODE = 0x100000
RETURN_PC = CODE + 0x800
POINTER_PAGE = 0x200000
PRE_PAGE = 0x300000
LUT_PAGES = 0x400000
MMIO_RAM = 0x500000
MMIO_BYTES = 0x10000
PRE_WORDS = 33
LUT_WORDS = 6144
POINTERS = POINTER_PAGE + 0x1000 - 16
PRE_INPUT = PRE_PAGE + 0x1000 - 4 * (PRE_WORDS + 1)
LUT_INPUT = LUT_PAGES + 0x7000 - 4 * (LUT_WORDS + 1)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_function(module_path: Path) -> bytes:
    payload = module_path.read_bytes()
    if sha256(payload) != MODULE_SHA256:
        raise ValueError("vcam_driver.ko does not match the audited firmware hash")
    elf = ELFFile(io.BytesIO(payload))
    if elf["e_type"] != "ET_REL" or elf["e_machine"] != "EM_AARCH64":
        raise ValueError("Expected the audited AArch64 relocatable kernel module")
    symbols = elf.get_section_by_name(".symtab").get_symbol_by_name(FUNCTION)
    if not symbols or len(symbols) != 1:
        raise ValueError("Function symbol missing or ambiguous")
    symbol = symbols[0]
    if (symbol["st_value"], symbol["st_size"]) != (FUNCTION_OFFSET, FUNCTION_BYTES):
        raise ValueError("Function extent changed")
    section = elf.get_section(symbol["st_shndx"])
    if section.name != ".text":
        raise ValueError("Unexpected function section")
    for relocation_section in elf.iter_sections():
        if (isinstance(relocation_section, RelocationSection)
                and relocation_section["sh_info"] == symbol["st_shndx"]):
            for relocation in relocation_section.iter_relocations():
                if FUNCTION_OFFSET <= relocation["r_offset"] < FUNCTION_OFFSET + FUNCTION_BYTES:
                    raise ValueError("A relocation exists inside the isolated function")
    code = section.data()[FUNCTION_OFFSET:FUNCTION_OFFSET + FUNCTION_BYTES]
    if sha256(code) != FUNCTION_SHA256:
        raise ValueError("Function code hash changed")
    return code


def synthetic_words(count: int, salt: int) -> bytes:
    """A full-width deterministic fixture, with both packed halves distinctive."""
    words = []
    for index in range(count):
        value = ((index + 1) * 0x9E3779B9 + salt) & 0xFFFFFFFF
        value ^= value >> 13
        value = (value * 0x85EBCA6B) & 0xFFFFFFFF
        value ^= value >> 16
        words.append(value)
    return struct.pack(f"<{count}I", *words)


def set_word(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value & 0xFFFFFFFF)


def word(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def run_case(code: bytes, module_enabled: bool, pre_enabled: bool,
             lut_enabled: bool, shadow_valid: bool, irq_masked: bool) -> dict:
    initial_mmio = synthetic_words(MMIO_BYTES // 4, 0x12345678)
    pre_table = synthetic_words(PRE_WORDS, 0x55667788)
    lut_table = synthetic_words(LUT_WORDS, 0xA55A19E7)
    # Non-unit true flags also verify that the original writer treats them as booleans.
    pre_source = struct.pack("<I", 7 if pre_enabled else 0) + pre_table
    lut_source = struct.pack("<I", 3 if lut_enabled else 0) + lut_table
    pointer_source = struct.pack("<QQ", PRE_INPUT, LUT_INPUT)
    shadow_id = 0xA7 if shadow_valid else 0xFFFFFF00
    pstate = 0x85 if irq_masked else 0x05  # EL1h; only the IRQ mask differs.

    # Independent final-state specification of register submission.
    expected = bytearray(initial_mmio)
    set_word(expected, 0x04, word(expected, 0x04) | 1)
    set_word(expected, 0x1C, (word(expected, 0x1C) & ~4) | (4 if module_enabled else 0))
    allowed_write_offsets = {0x04, 0x1C}
    if module_enabled:
        set_word(expected, 0x08, word(expected, 0x08) | 1)
        allowed_write_offsets.add(0x08)
        if shadow_valid:
            set_word(expected, 0x10, (word(expected, 0x10) & ~0xFF) | shadow_id)
            allowed_write_offsets.add(0x10)
        set_word(expected, 0x1C, (word(expected, 0x1C) & ~3)
                 | (2 if pre_enabled else 0) | (1 if lut_enabled else 0))
        if pre_enabled:
            expected[0x7F7C:0x8000] = pre_table
            allowed_write_offsets.update(range(0x7F7C, 0x8000, 4))
        if lut_enabled:
            expected[0x8000:0xE000] = lut_table
            allowed_write_offsets.update(range(0x8000, 0xE000, 4))

    emulator = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
    for address, length in ((CODE, 0x1000), (POINTER_PAGE, 0x1000),
                            (PRE_PAGE, 0x1000), (LUT_PAGES, 0x7000),
                            (MMIO_RAM, MMIO_BYTES)):
        emulator.mem_map(address, length)
    emulator.mem_write(CODE, code)
    emulator.mem_write(POINTERS, pointer_source)
    emulator.mem_write(PRE_INPUT, pre_source)
    emulator.mem_write(LUT_INPUT, lut_source)
    emulator.mem_write(MMIO_RAM, initial_mmio)
    emulator.mem_protect(CODE, 0x1000, unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
    for address, length in ((POINTER_PAGE, 0x1000), (PRE_PAGE, 0x1000), (LUT_PAGES, 0x7000)):
        emulator.mem_protect(address, length, unicorn.UC_PROT_READ)

    input_ranges = ((POINTERS, POINTERS + len(pointer_source)),
                    (PRE_INPUT, PRE_INPUT + len(pre_source)),
                    (LUT_INPUT, LUT_INPUT + len(lut_source)))
    violations = []
    writes = []

    def observe_read(uc, access, address, size, value, user_data):
        del uc, access, value, user_data
        if MMIO_RAM <= address and address + size <= MMIO_RAM + MMIO_BYTES:
            return
        if not any(begin <= address and address + size <= end for begin, end in input_ranges):
            violations.append({"kind": "unexpected_data_read", "address": hex(address), "size": size})

    def observe_write(uc, access, address, size, value, user_data):
        del uc, access, value, user_data
        offset = address - MMIO_RAM
        if size != 4 or offset not in allowed_write_offsets:
            violations.append({"kind": "unexpected_data_write", "address": hex(address), "size": size})
        writes.append(offset)

    emulator.hook_add(unicorn.UC_HOOK_MEM_READ, observe_read)
    emulator.hook_add(unicorn.UC_HOOK_MEM_WRITE, observe_write)
    for register, value in ((arm64.UC_ARM64_REG_X0, MMIO_RAM),
                            (arm64.UC_ARM64_REG_X1, 5 if module_enabled else 0),
                            (arm64.UC_ARM64_REG_X2, POINTERS),
                            (arm64.UC_ARM64_REG_X3, shadow_id),
                            (arm64.UC_ARM64_REG_X30, RETURN_PC),
                            (arm64.UC_ARM64_REG_PSTATE, pstate)):
        emulator.reg_write(register, value)
    emulator.emu_start(CODE, RETURN_PC, timeout=5_000_000, count=100_000)
    actual = bytes(emulator.mem_read(MMIO_RAM, MMIO_BYTES))
    checks = {
        "returned_to_sentinel": emulator.reg_read(arm64.UC_ARM64_REG_PC) == RETURN_PC,
        "full_register_window_equal": actual == expected,
        "inputs_unchanged": (bytes(emulator.mem_read(POINTERS, len(pointer_source))) == pointer_source
                             and bytes(emulator.mem_read(PRE_INPUT, len(pre_source))) == pre_source
                             and bytes(emulator.mem_read(LUT_INPUT, len(lut_source))) == lut_source),
        "data_accesses_bounded": not violations,
        "exact_write_locations": set(writes) == allowed_write_offsets,
        "daif_masks_restored": (emulator.reg_read(arm64.UC_ARM64_REG_PSTATE) & 0x3C0) == (pstate & 0x3C0),
    }
    if not all(checks.values()):
        raise AssertionError({"flags": [module_enabled, pre_enabled, lut_enabled, shadow_valid, irq_masked],
                              "checks": checks, "violations": violations[:8]})
    return {
        "module_enabled": module_enabled,
        "pre_gamma_enabled": pre_enabled,
        "lut_enabled": lut_enabled,
        "shadow_id_valid": shadow_valid,
        "irq_masked_on_entry": irq_masked,
        "checks": checks,
        "register_word_writes": len(writes),
        "pre_gamma_words_copied": PRE_WORDS if module_enabled and pre_enabled else 0,
        "lut_words_copied": LUT_WORDS if module_enabled and lut_enabled else 0,
        "output_window_sha256": sha256(actual),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    code = load_function(args.firmware_root / MODULE_PATH)
    cases = [run_case(code, *flags) for flags in itertools.product((False, True), repeat=5)]
    result = {
        "schema": 1,
        "scope": "Complete original kernel register-writer instructions against synthetic RAM only",
        "not_proved": ["Any RGB pixel conversion", "MAIN colour-table axes or grid knots",
                       "Hardware interpolation, rounding, saturation or timing"],
        "module": {"relative_path": MODULE_PATH, "sha256": MODULE_SHA256},
        "function": {"name": FUNCTION, "section": ".text", "section_offset": hex(FUNCTION_OFFSET),
                     "bytes": FUNCTION_BYTES, "sha256": FUNCTION_SHA256, "relocations_in_body": 0},
        "emulator": {"name": "Unicorn", "version": unicorn.__version__, "architecture": "AArch64",
                     "execution_state": "EL1h, IRQ mask tested both set and clear",
                     "mmio": "ordinary guarded emulator RAM; no device access"},
        "fixtures": {"provenance": "Original deterministic synthetic full-width uint32 fixtures",
                     "pre_gamma_words": PRE_WORDS, "lut_words": LUT_WORDS,
                     "pre_gamma_sha256": sha256(synthetic_words(PRE_WORDS, 0x55667788)),
                     "lut_sha256": sha256(synthetic_words(LUT_WORDS, 0xA55A19E7)),
                     "initial_register_window_sha256": sha256(synthetic_words(MMIO_BYTES // 4, 0x12345678))},
        "total_cases": len(cases),
        "passed_cases": sum(all(case["checks"].values()) for case in cases),
        "total_lut_words_compared_after_copy": sum(case["lut_words_copied"] for case in cases),
        "total_pre_gamma_words_compared_after_copy": sum(case["pre_gamma_words_copied"] for case in cases),
        "source_sha256": sha256(Path(__file__).read_bytes()),
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed_cases": result["passed_cases"], "total_cases": len(cases),
                      "output": str(args.output), "report_sha256": sha256(args.output.read_bytes())}))


if __name__ == "__main__":
    main()
