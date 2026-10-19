#!/usr/bin/env python3
"""Execute pinned gamma_set_info on owned RAM; never load a kernel driver.

Only original instructions are read temporarily from a user-supplied module.
The output contains metadata and hashes, not original code or table bytes.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

import capstone
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import arm64_const as reg

MODULE_SHA = "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
FUNCTION, OFFSET, LENGTH = "gamma_set_info", 0x31a50, 796
CODE, RETURN = 0x10000000, 0x10001000
MMIO_MAP, PARAM_MAP, STACK = 0x50000000, 0x60000000, 0x70000000
MMIO, PARAM = MMIO_MAP + 0x400, PARAM_MAP + 0x400
PARAM_BYTES, MAP_BYTES = 0x6c4, 0x2000
TABLES = ((0x1c, 0x800, 257), (0x420, 0x1000, 9),
          (0x444, 0x1080, 32), (0x4c4, 0x1100, 32),
          (0x544, 0x1180, 32), (0x5c4, 0x1200, 32), (0x644, 0x1280, 32))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_original(path):
    data = path.read_bytes()
    if sha(data) != MODULE_SHA:
        raise ValueError("Unsupported vcam_driver.ko SHA-256")
    elf = ELFFile(io.BytesIO(data))
    if (elf.elfclass, elf.little_endian, elf["e_machine"], elf["e_type"]) != (64, True, "EM_AARCH64", "ET_REL"):
        raise ValueError("Expected little-endian AArch64 ELF64 relocatable module")
    symbols = elf.get_section_by_name(".symtab")
    matches = [s for s in symbols.iter_symbols() if s.name == FUNCTION]
    if len(matches) != 1 or (matches[0]["st_value"], matches[0]["st_size"]) != (OFFSET, LENGTH):
        raise ValueError("Original function address/extent mismatch")
    text_index = matches[0]["st_shndx"]
    text_section = elf.get_section(text_index)
    if text_section.name != ".text":
        raise ValueError("Expected .text symbol")
    for section in elf.iter_sections():
        if section["sh_type"] in ("SHT_RELA", "SHT_REL") and section["sh_info"] == text_index:
            if any(OFFSET <= item["r_offset"] < OFFSET + LENGTH for item in section.iter_relocations()):
                raise ValueError("Unresolved relocation inside original function")
    code = text_section.data()[OFFSET:OFFSET + LENGTH]
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    insns = list(md.disasm(code, CODE))
    if len(insns) * 4 != LENGTH or any(i.mnemonic in ("bl", "blr", "br", "svc") for i in insns):
        raise ValueError("Unexpected call/indirect transfer in leaf function")
    return code, {"module_sha256": MODULE_SHA, "function": FUNCTION,
                  "section": ".text", "section_offset": hex(OFFSET), "function_bytes": LENGTH,
                  "function_sha256": sha(code), "relocations_in_function": 0}


def get32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def put32(data, offset, value):
    struct.pack_into("<I", data, offset, value & 0xffffffff)


def synthetic_bytes(count, seed):
    output = bytearray(count)
    for offset in range(0, count, 4):
        seed = (seed * 1664525 + 1013904223) & 0xffffffff
        put32(output, offset, seed)
    return output


def expected_registers(before, params):
    """Own reference model of register packing/copy, not a gamma evaluator."""
    result = bytearray(before)
    origin = MMIO - MMIO_MAP
    enabled = get32(params, 0) != 0
    put32(result, origin, (get32(result, origin) & ~2) | 2)
    put32(result, origin + 4, (get32(result, origin + 4) & ~1) | int(enabled))
    if not enabled:
        return result
    put32(result, origin, (get32(result, origin) & ~1) | 14)
    knee = get32(params, 4) != 0
    put32(result, origin + 4, (get32(result, origin + 4) & ~2) | (int(knee) << 1))
    put32(result, origin + 0x1c, sum((params[8 + i] & 15) << (4 * i) for i in range(8)))
    for source, destination, mask, fmt in ((0x10, 8, 0xfff, "<H"),
                                         (0x12, 0xc, 0x3ff, "<H"),
                                         (0x14, 0x10, 0x3ff, "<H"),
                                         (0x16, 0x14, 0x3ff, "<H"),
                                         (0x18, 0x18, 0xff, "<B")):
        value = struct.unpack_from(fmt, params, source)[0]
        old = get32(result, origin + destination)
        put32(result, origin + destination, (old & ~mask) | (value & mask))
    for source, destination, words in TABLES:
        result[origin + destination:origin + destination + 4 * words] = params[source:source + 4 * words]
    return result


def execute(code, name, enable, knee, seed):
    machine = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
    machine.mem_map(CODE, 8192, unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
    machine.mem_write(CODE, code)
    machine.mem_map(MMIO_MAP, MAP_BYTES, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
    before = synthetic_bytes(MAP_BYTES, seed)
    machine.mem_write(MMIO_MAP, bytes(before))
    params = synthetic_bytes(PARAM_BYTES, seed ^ 0x13579bdf)
    put32(params, 0, enable)
    put32(params, 4, knee)
    # Deliberately distinct upper/lower nibbles: proves hardware-field masking.
    params[8:16] = bytes((0xa2, 0xb7, 0xc1, 0xd4, 0xe3, 0xf5, 0x16, 0x28))
    machine.mem_map(PARAM_MAP, MAP_BYTES, unicorn.UC_PROT_READ)
    parameter_memory = bytearray(b"\xa5" * MAP_BYTES)
    parameter_memory[PARAM - PARAM_MAP:PARAM - PARAM_MAP + PARAM_BYTES] = params
    machine.mem_write(PARAM_MAP, bytes(parameter_memory))
    machine.mem_map(STACK, 4096, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
    stack_memory = b"\x3c" * 4096
    machine.mem_write(STACK, stack_memory)
    machine.reg_write(reg.UC_ARM64_REG_SP, STACK + 2048)
    machine.reg_write(reg.UC_ARM64_REG_X0, MMIO)
    machine.reg_write(reg.UC_ARM64_REG_X1, PARAM)
    machine.reg_write(reg.UC_ARM64_REG_LR, RETURN)
    preserved = {}
    for number in range(19, 30):
        register = getattr(reg, "UC_ARM64_REG_X" + str(number))
        preserved[register] = 0x1234000000000000 + number
        machine.reg_write(register, preserved[register])
    visited, reads, writes = set(), [], []
    allowed_writes = {MMIO + i for i in range(0, 0x20, 4)}
    for _, destination, words in TABLES:
        allowed_writes.update(MMIO + destination + 4 * i for i in range(words))
    def code_hook(uc, address, size, unused):
        if not CODE <= address < CODE + LENGTH or size != 4:
            raise RuntimeError("Execution left the audited leaf function")
        visited.add(address)
    def memory_hook(uc, access, address, size, value, unused):
        if access == unicorn.UC_MEM_WRITE:
            if address not in allowed_writes or size != 4:
                raise RuntimeError("Unexpected synthetic MMIO write")
            writes.append(address - MMIO)
        else:
            valid = (PARAM <= address and address + size <= PARAM + PARAM_BYTES)
            valid |= address in allowed_writes and size == 4
            if not valid:
                raise RuntimeError("Unexpected input/MMIO read")
            reads.append((address, size))
    machine.hook_add(unicorn.UC_HOOK_CODE, code_hook)
    machine.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory_hook)
    machine.emu_start(CODE, RETURN, timeout=1_000_000, count=10_000)
    if machine.reg_read(reg.UC_ARM64_REG_PC) != RETURN or machine.reg_read(reg.UC_ARM64_REG_X0) != 0:
        raise AssertionError("Expected bounded return 0")
    actual = bytes(machine.mem_read(MMIO_MAP, MAP_BYTES))
    if actual != bytes(expected_registers(before, params)):
        raise AssertionError("Original register writes differ from reference/guard bytes")
    if bytes(machine.mem_read(PARAM_MAP, MAP_BYTES)) != bytes(parameter_memory):
        raise AssertionError("Input parameter bytes changed")
    if bytes(machine.mem_read(STACK, 4096)) != stack_memory or machine.reg_read(reg.UC_ARM64_REG_SP) != STACK + 2048:
        raise AssertionError("Leaf routine changed stack")
    if any(machine.reg_read(key) != value for key, value in preserved.items()):
        raise AssertionError("Callee-saved register changed")
    table_results = [{"input_offset": hex(source), "register_offset": hex(destination), "words": words,
                      "synthetic_source_sha256": sha(params[source:source + words * 4]),
                      "full_u32_copy_verified": True} for source, destination, words in TABLES] if enable else []
    return {"name": name, "enable_input": enable, "knee_enable_input": knee, "synthetic_seed": seed,
            "result": "pass", "return": 0, "exact_register_image_and_guards_match": True,
            "parameters_and_stack_unchanged": True, "callee_saved_registers_preserved": True,
            "unique_instructions_executed": len(visited), "memory_reads": len(reads), "memory_writes": len(writes),
            "synthetic_register_image_sha256": sha(actual), "tables": table_results}, visited


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code, provenance = load_original(args.firmware_root / "system/lib/modules/vcam_driver.ko")
    cases, coverage = [], set()
    for values in (("disabled", 0, 0xffffffff, 0x27176),
                   ("enabled_without_knee", 1, 0, 0x722),
                   ("nonboolean_enable_and_knee", 0xffffffff, 0x80000000, 0xabcdef),
                   ("enabled_with_knee", 1, 1, 0x10aa)):
        result, visited = execute(code, *values)
        cases.append(result)
        coverage.update(visited)
    result = {"result": "pass", "firmware": "X2D II 100C 1.3.16.2", "provenance": provenance,
              "method": "Full original leaf gamma_set_info executed in Unicorn; MMIO replaced by owned synthetic RAM; no kernel module loaded and no camera/hardware execution",
              "inferred_abi": {"x0": "mapped register base", "x1": "input parameter object, 0x6c4 bytes read when enabled", "return_w0": "0"},
              "cases": cases, "case_count": len(cases), "unique_instructions_executed": len(coverage),
              "available_instructions": LENGTH // 4,
              "field_contract": {"division_register_offset": "0x1c", "division_input_offsets": "0x8..0xf",
                                 "division_field_bits": 4, "division_field_shifts": [0, 4, 8, 12, 16, 20, 24, 28],
                                 "knee_clip_bits": 12, "knee_y_coefficient_bits": 10, "knee_blend_bits": 8},
              "limits": "Proves parameter packing and complete 32-bit table-word writes only; physical MMIO side effects, gamma interpolation, numerical output precision and dither are not emulated",
              "tool_sha256": sha(Path(__file__).read_bytes()),
              "versions": {"unicorn": unicorn.__version__, "capstone": capstone.__version__}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"result": "pass", "cases": len(cases), "instructions_covered": len(coverage), "output": str(args.output)}))


if __name__ == "__main__":
    main()
