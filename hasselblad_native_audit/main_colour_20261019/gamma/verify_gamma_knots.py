#!/usr/bin/env python3
"""Compare the recovered MAIN knot primitive with exact original instructions.

Runs a bounded instruction slice, not the whole TMC function or camera.
Reads a user-supplied pinned ELF. No vendor code or LUT payload is retained.
"""
import argparse
import hashlib
import io
import json
import lzma
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True

import capstone
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import arm64_const as reg

from gamma_knots import main_gamma_knots, REGION_BOUNDARIES

LIB_SHA = "3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66"
FUNCTION, FUNCTION_VA, FUNCTION_BYTES = "tmc_v1_0_calc_tmc", 0x381bc8, 22816
START, STOP = 0x3866b0, 0x386d28
CONSTANT_VA, CONSTANT_BYTES = 0x479220, 16
STACK, STACK_BYTES, KNOT_OFFSET = 0x40000000, 0x20000, 0x144c0
CASES = (
    ("actual_still_divisions", (2, 2, 3, 4, 5, 6, 7)),
    ("reversed_divisions", (7, 6, 5, 4, 3, 2, 2)),
    ("asymmetric_permutation", (6, 2, 7, 4, 2, 5, 3)),
    ("three_dense_regions", (6, 6, 6, 4, 4, 4, 4)),
    ("dense_first_region", (6, 5, 5, 5, 5, 5, 5)),
    ("dense_last_region", (5, 5, 5, 5, 5, 5, 6)),
    ("alternate_partition", (7, 5, 5, 5, 4, 3, 3)),
    ("alternate_partition_reversed", (3, 3, 4, 5, 5, 5, 7)),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_original(path):
    data = path.read_bytes()
    if sha(data) != LIB_SHA:
        raise ValueError("Unsupported librcam SHA-256")
    elf = ELFFile(io.BytesIO(data))
    if elf.elfclass != 64 or not elf.little_endian or elf["e_machine"] != "EM_AARCH64":
        raise ValueError("Expected little-endian AArch64 ELF64")
    debug = lzma.decompress(elf.get_section_by_name(".gnu_debugdata").data())
    if len(debug) > 64 * 1024 * 1024:
        raise ValueError("Debug metadata exceeds bound")
    symbols = ELFFile(io.BytesIO(debug)).get_section_by_name(".symtab")
    matches = [symbol for symbol in symbols.iter_symbols() if symbol.name == FUNCTION]
    if len(matches) != 1 or (matches[0]["st_value"], matches[0]["st_size"]) != (FUNCTION_VA, FUNCTION_BYTES):
        raise ValueError("Original function address/extent mismatch")
    def read_va(address, length):
        for section in elf.iter_sections():
            if section["sh_type"] == "SHT_NOBITS" or not section["sh_flags"] & 2:
                continue
            offset = address - section["sh_addr"]
            if 0 <= offset and offset + length <= section["sh_size"]:
                return section.data()[offset:offset + length]
        raise ValueError("Address outside file-backed ELF section")
    code = read_va(START, STOP - START)
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    instructions = list(md.disasm(code, START))
    if len(instructions) != len(code) // 4 or any(item.mnemonic in ("bl", "blr", "br", "ret", "svc") for item in instructions):
        raise ValueError("Unexpected transfer in bounded knot-construction slice")
    def require_instruction(address, mnemonic, operands):
        decoded = list(md.disasm(read_va(address, 4), address))
        if len(decoded) != 1 or (decoded[0].mnemonic, decoded[0].op_str) != (mnemonic, operands):
            raise ValueError("MAIN consumer provenance instruction mismatch at %#x" % address)
    require_instruction(0x38410c, "mov", "w1, #0x10aa")
    require_instruction(0x384128, "bl", "#0x251a18")
    require_instruction(0x384130, "cmp", "w4, #0x101")
    require_instruction(0x38413c, "mov", "w2, #0x404")
    for index, call in enumerate(range(0x384474, 0x384505, 24)):
        require_instruction(call - 16, "mov", "w1, #%#x" % (4221 + index))
        require_instruction(call - 20, "add", "x2, x19, #%#x" % (0x50c + index * 4))
        require_instruction(call, "bl", "#0x251ab8")
    for address, number, offset in ((0x386684, 25, 0x1368), (0x386688, 24, 0x136c),
                                    (0x386690, 23, 0x1370), (0x386698, 22, 0x1374),
                                    (0x3866a0, 20, 0x1378), (0x3866a4, 19, 0x137c),
                                    (0x3866a8, 26, 0x1364)):
        require_instruction(address, "ldr", "w%d, [sp, #%#x]" % (number, offset))
    provenance_spans = [{"start_va": hex(begin), "stop_before_va": hex(end),
                         "sha256": sha(read_va(begin, end - begin))}
                        for begin, end in ((0x381bc8, 0x381c10), (0x384104, 0x38414c),
                                           (0x38445c, 0x384508), (0x386678, 0x3866b0))]
    return code, read_va(CONSTANT_VA, CONSTANT_BYTES), {
        "library_sha256": LIB_SHA,
        "function": FUNCTION, "function_va": hex(FUNCTION_VA), "function_bytes": FUNCTION_BYTES,
        "function_sha256": sha(read_va(FUNCTION_VA, FUNCTION_BYTES)),
        "slice_start_va": hex(START), "slice_stop_before_va": hex(STOP),
        "slice_bytes": len(code), "slice_sha256": sha(code),
        "constant_va": hex(CONSTANT_VA), "constant_bytes": CONSTANT_BYTES,
        "constant_sha256": sha(read_va(CONSTANT_VA, CONSTANT_BYTES)),
        "consumer_provenance_spans": provenance_spans,
        "main_register_calls_and_live_register_loads_checked": True,
    }


def execute(code, constant, name, divisions):
    expected = main_gamma_knots(divisions)
    machine = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
    machine.mem_map(START & ~4095, 4096, unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
    machine.mem_write(START, code)
    machine.mem_map(CONSTANT_VA & ~4095, 4096, unicorn.UC_PROT_READ)
    machine.mem_write(CONSTANT_VA, constant)
    machine.mem_map(STACK, STACK_BYTES, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
    before = bytearray(b"\xa5" * STACK_BYTES)
    struct.pack_into("<Q", before, 0x58, 0x12345678)
    machine.mem_write(STACK, bytes(before))
    machine.reg_write(reg.UC_ARM64_REG_SP, STACK)
    machine.reg_write(reg.UC_ARM64_REG_X28, STACK + 0x10ca8)
    # These live registers are loaded from the seven MAIN register results
    # at original VAs 0x386684..0x3866a8. They are not a callable C ABI.
    for register, division in zip((26, 25, 24, 23, 22, 20, 19), divisions):
        machine.reg_write(getattr(reg, "UC_ARM64_REG_W" + str(register)), division)
    machine.reg_write(reg.UC_ARM64_REG_W21, 256)
    visited, reads, writes = set(), [], []
    def code_hook(uc, address, size, unused):
        if not START <= address < STOP or size != 4:
            raise RuntimeError("Execution left the audited instruction interval")
        visited.add(address)
    def memory_hook(uc, access, address, size, value, unused):
        if access == unicorn.UC_MEM_READ:
            # Unicorn may report one vector load as two 8-byte reads.
            valid = ((address == STACK + 0x58 and size == 8) or
                     (CONSTANT_VA <= address and address + size <= CONSTANT_VA + CONSTANT_BYTES))
            if not valid:
                raise RuntimeError("Unexpected knot-slice memory read: address=%#x size=%d PC=%#x" % (address, size, uc.reg_read(reg.UC_ARM64_REG_PC)))
            reads.append((address, size))
        else:
            if not STACK + KNOT_OFFSET <= address or address + size > STACK + KNOT_OFFSET + 257 * 4:
                raise RuntimeError("Write outside 257-knot destination")
            writes.append((address, size))
    machine.hook_add(unicorn.UC_HOOK_CODE, code_hook)
    machine.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory_hook)
    machine.emu_start(START, STOP, timeout=1_000_000, count=10_000)
    if machine.reg_read(reg.UC_ARM64_REG_PC) != STOP:
        raise RuntimeError("Knot-slice instruction/time bound exhausted")
    actual = bytes(machine.mem_read(STACK, STACK_BYTES))
    expected_memory = bytearray(before)
    payload = struct.pack("<257I", *expected)
    expected_memory[KNOT_OFFSET:KNOT_OFFSET + len(payload)] = payload
    if actual != bytes(expected_memory):
        raise AssertionError("Original knots or surrounding guard bytes differ")
    if machine.reg_read(reg.UC_ARM64_REG_SP) != STACK:
        raise AssertionError("Knot construction unexpectedly changes SP")
    steps = [b - a for a, b in zip(expected, expected[1:])]
    return {
        "name": name, "divisions": list(divisions), "interval_counts": [1 << d for d in divisions],
        "result": "pass", "knots": len(expected), "first": expected[0], "last": expected[-1],
        "minimum_step": min(steps), "maximum_step": max(steps), "uniform": len(set(steps)) == 1,
        "knots_u32le_sha256": sha(payload), "all_knots_match": True, "guard_bytes_unchanged": True,
        "unique_instructions_executed": len(visited), "memory_reads": len(reads), "memory_writes": len(writes),
    }, visited


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code, constant, provenance = load_original(args.firmware_root / "system/lib64/librcam.so")
    cases, coverage = [], set()
    for name, divisions in CASES:
        result, visited = execute(code, constant, name, divisions)
        cases.append(result)
        coverage.update(visited)
    invalid = [None, (), (2, 2, 3, 4, 5, 6), (2, 2, 3, 4, 5, 6, 8),
               (-1, 2, 3, 4, 5, 6, 7), (True, 2, 3, 4, 5, 6, 7),
               (2.0, 2, 3, 4, 5, 6, 7), (2, 2, 3, 4, 5, 6, 6)]
    for values in invalid:
        try:
            main_gamma_knots(values)
        except ValueError:
            continue
        raise AssertionError("Portable adapter accepted invalid division metadata")
    result = {
        "result": "pass", "firmware": "X2D II 100C 1.3.16.2", "provenance": provenance,
        "method": "Unicorn executes exact original inline knot-construction instructions; owned live registers/stack; no full TMC function or camera execution",
        "live_ins": {"SP": "private stack base", "X28": "SP+0x10ca8", "W26,W25,W24,W23,W22,W20,W19": "lut_div[0..6]", "W21": 256, "SP+0x58": "inert saved context value"},
        "source_mapping": {"gamma_register_id": 4266, "gamma_get_lut_call_va": "0x384128",
                           "division_register_ids": list(range(4221, 4228)),
                           "division_get_call_vas": [hex(x) for x in range(0x384474, 0x384505, 24)],
                           "division_stack_offsets": [hex(x) for x in range(0x1364, 0x1380, 4)],
                           "register_load_interval": ["0x386684", "0x3866ac"],
                           "destination": "SP+0x144c0, 257 uint32 coordinates"},
        "region_boundaries": list(REGION_BOUNDARIES), "cases": cases,
        "case_count": len(cases), "coordinates_compared": 257 * len(cases),
        "portable_guard_cases": len(invalid), "unique_instructions_executed": len(coverage),
        "limits": "Proves a MAIN-linked consumer's positive-domain knot positions only; not hardware pixel interpolation, signed-domain behavior, output quantization, dither or a photographic transfer function",
        "tool_sha256": sha(Path(__file__).read_bytes()),
        "primitive_sha256": sha(Path(__file__).with_name("gamma_knots.py").read_bytes()),
        "versions": {"unicorn": unicorn.__version__, "capstone": capstone.__version__},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"result": "pass", "cases": len(cases), "coordinates_compared": 257 * len(cases), "output": str(args.output)}))


if __name__ == "__main__":
    main()
