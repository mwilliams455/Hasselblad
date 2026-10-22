#!/usr/bin/env python3
"""Stage29: hash-pinned X2D II Eagle2 CCM format-call ABI provenance.

Analyzes reaching register definitions across static AArch64 control-flow paths.
Does not infer meaning of register values or export original instruction bytes,
IQ coefficient payloads or photographic samples. Heuristic register provenance
is never an original pixel-processing equation or a live ISP trace.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path

DRIVER_SHA = "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
CCM_FMT = (0x314c8, 80)
CCM_FN0 = (0x30e40, 92)
B2R_SIZE = 912
B2R_CALL_CCM = 0x6d598
CCM_CALL_FN0 = 0x314f0
CALL26 = 283
STAGES = ("wbc_set_fmt", "demosaic_set_fmt", "ccm_set_fmt", "gamma_set_fmt", "hncs_set_fmt")
ABI = tuple(f"x{i}" for i in range(4))


def require(condition: bool, why: str) -> None:
    if not condition:
        raise ValueError(why)


def file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized_reg(name: str) -> str | None:
    if name[:1] in ("w", "x") and name[1:].isdigit():
        i = int(name[1:])
        if 0 <= i <= 30:
            return "x" + str(i)
    return None


def solve(addresses: list[int], successor: dict[int, set[int]],
          writes: dict[int, set[str]], callsites: set[int]) -> dict[int, dict[str, frozenset[str]]]:
    """Forward may-reaching definitions, merging all static feasible paths.

    Clobber after calls per AArch64 ABI. Unknown branches must be signalled by
    the caller; this routine does not claim dynamic path feasibility.
    """
    require(addresses and len(addresses) == len(set(addresses)), "duplicate_addresses")
    require(set(successor) == set(addresses), "missing_successor_entries")
    domain = set(addresses)
    require(all(set(v) <= domain for v in successor.values()), "out_of_function_edge")
    entry = addresses[0]
    incoming: dict[int, dict[str, frozenset[str]]] = {
        entry: {r: frozenset({"entry:" + r}) for r in ABI}
    }
    queue = deque([entry])
    iterations = 0
    while queue:
        at = queue.popleft()
        iterations += 1
        require(iterations < 30000, "dataflow_did_not_converge")
        previous = incoming[at]
        current = dict(previous)
        if at in callsites:
            for reg in ABI:
                current[reg] = frozenset({"call:" + hex(at)})
        for reg in (writes.get(at, set()) - ({*ABI} if at in callsites else set())):
            if reg in ABI:
                current[reg] = frozenset({"write:" + hex(at)})
        for after in successor[at]:
            existing = incoming.get(after)
            if existing is None:
                incoming[after] = dict(current)
                queue.append(after)
                continue
            union = {reg: existing[reg] | current[reg] for reg in ABI}
            require(all(len(v) <= 512 for v in union.values()), "ambiguous_writer_set_overflow")
            if union != existing:
                incoming[after] = union
                queue.append(after)
    return incoming


def mock_tests() -> dict[str, object]:
    # Shared last writer through a branch remains unique.
    a = [0, 4, 8, 12, 16]
    edges = {0: {4}, 4: {8, 12}, 8: {16}, 12: {16}, 16: set()}
    got = solve(a, edges, {0: {"x1"}}, set())
    require(got[16]["x1"] == {"write:0x0"}, "must_writer_branch")
    # Different path-dependent writers must never be described as proven.
    got = solve(a, edges, {8: {"x1"}, 12: {"x1"}}, set())
    require(got[16]["x1"] == {"write:0x8", "write:0xc"}, "branch_ambiguity")
    # A call invalidates return/clobbered arguments, not x19 callee-saved.
    got = solve([0, 4, 8], {0: {4}, 4: {8}, 8: set()}, {0: {"x0"}}, {4})
    require(got[8]["x0"] == {"call:0x4"}, "abi_call_clobber")
    # Unreachable instructions do not manufacture reaching definitions.
    got = solve([0, 4, 8], {0: {8}, 4: {8}, 8: set()}, {4: {"x3"}}, set())
    require(got[8]["x3"] == {"entry:x3"}, "unreachable_writer")
    # Cyclic control flow terminates via a monotonically growing set lattice.
    got = solve([0, 4, 8], {0: {4}, 4: {8}, 8: {4}}, {8: {"x2"}}, set())
    require(got[4]["x2"] == {"entry:x2", "write:0x8"}, "loop_join")
    # W and X names denote the same physical argument register.
    require(normalized_reg("w2") == normalized_reg("x2") == "x2", "register_alias")
    require(normalized_reg("sp") is None and normalized_reg("wzr") is None, "invalid_register")
    return {"schema": "hasselblad-stage29-CFG-ABI-synthetic-v1",
            "status": "PASS_synthetic", "invariant_cases": 7,
            "vendor_firmware_loaded": False,
            "hardware_pixel_equation_recovered": False,
            "photo_renderer_changed": False}


def extract_graph(inst, function_start: int, function_end: int):
    """Capstone basic CFG; mark an unresolved branch as not fully proven."""
    from capstone.arm64 import ARM64_OP_IMM
    insmap = {i.address: i for i in inst}
    addr = [i.address for i in inst]
    require(addr and addr[0] == function_start and addr[-1] + 4 == function_end,
            "incomplete_function_decode")
    successors = {}
    writes = {}
    calls = set()
    unresolved = []
    for i in inst:
        m = i.mnemonic
        at = i.address
        after = at + 4
        follow = {after} if after in insmap else set()
        is_call = m in ("bl", "blr", "blraa", "blrab")
        if is_call:
            calls.add(at)
        if m in ("ret", "eret", "br"):
            follow = set()
            if m == "br":
                unresolved.append(hex(at))
        elif m == "b" or m.startswith("b.") or m in ("cbz", "cbnz", "tbz", "tbnz"):
            immediates = [o.imm for o in i.operands if o.type == ARM64_OP_IMM]
            if len(immediates) != 1 or immediates[0] not in insmap:
                unresolved.append(hex(at))
                # A path outside the function may never return; do not invent a
                # local destination. A guarded result is a static lower bound.
                if m == "b":
                    follow = set()
            else:
                if m == "b":
                    follow = {immediates[0]}
                else:
                    follow.add(immediates[0])
        successors[at] = follow
        try:
            _, write_ids = i.regs_access()
            writes[at] = {r for id in write_ids if (r := normalized_reg(i.reg_name(id)))}
        except Exception:
            unresolved.append(hex(at))
            writes[at] = set(ABI)  # fail conservatively: unknown instruction effects
    return addr, successors, writes, calls, sorted(set(unresolved))


def writer_summary(writer: str, instruction_map: dict[int, object]) -> dict[str, object]:
    if writer.startswith("entry:"):
        return {"last_writer_kind": "function_entry_unknown", "candidate_input_register": writer[6:]}
    if writer.startswith("call:"):
        return {"last_writer_kind": "earlier_call_clobber", "at_section_offset": writer[5:]}
    if not writer.startswith("write:"):
        return {"last_writer_kind": "unclassified"}
    at = int(writer[6:], 16)
    ins = instruction_map[at]
    m = ins.mnemonic
    # Do not serialize the original opcodes, instructions, raw operands or
    # field payloads. These are structural classification hints, not values.
    if m in ("ldrb", "ldrsb"):
        cat = "load_8bit"
    elif m in ("ldrh", "ldrsh"):
        cat = "load_16bit"
    elif m in ("ldr", "ldur", "ldrsw", "ldp"):
        cat = "memory_load"
    elif m in ("mov", "orr"):
        cat = "move_or_bitwise"
    elif m in ("add", "sub", "adrp", "adr"):
        cat = "pointer_or_arithmetic"
    elif m in ("movz", "movn", "movk"):
        cat = "immediate_materialization"
    elif m in ("csel", "csinc", "csinv", "csneg"):
        cat = "conditional_select"
    else:
        cat = "other_or_unresolved"
    out = {"last_writer_kind": cat, "at_section_offset": hex(at)}
    # A constrained structural operand summary is useful for later provenance
    # tracing; do not export original disassembly, instruction bytes or values.
    from capstone.arm64 import ARM64_OP_MEM, ARM64_OP_REG
    if cat in ("load_8bit", "load_16bit", "memory_load"):
        for op in ins.operands:
            if op.type == ARM64_OP_MEM:
                base = ins.reg_name(op.mem.base)
                index = ins.reg_name(op.mem.index) if op.mem.index else None
                out["input_memory_address"] = {
                    "base_register": base,
                    "displacement": op.mem.disp,
                    "index_register": index,
                    "is_stack_relative": base == "sp"}
                break
        if ins.operands and ins.operands[0].type == ARM64_OP_REG:
            out["destination_register_width"] = (
                64 if ins.reg_name(ins.operands[0].reg).startswith("x") else 32)
    if cat == "move_or_bitwise" and len(ins.operands) >= 2:
        second = ins.operands[1]
        if second.type == ARM64_OP_REG:
            out["direct_register_source"] = ins.reg_name(second.reg)
    return out


def analyze_function(text: bytes, entry: int, size: int, observations: dict[str, int]):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    ins = list(decoder.disasm(text[entry:entry + size], entry))
    addresses, edges, writers, calls, unresolved = extract_graph(ins, entry, entry + size)
    states = solve(addresses, edges, writers, calls)
    imap = {i.address: i for i in ins}
    result = {}
    for label, at in observations.items():
        require(at in imap and imap[at].mnemonic == "bl", "expected_callsite_changed_" + label)
        state = states.get(at)
        require(state is not None, "target_callsite_not_reachable_" + label)
        arg = {}
        for reg in ABI:
            last = sorted(state[reg])
            arg[reg] = {
                "unique_reaching_writer_in_static_CFG": len(last) == 1 and not unresolved,
                "writer_count": len(last),
                "proven_value_or_parameter_semantics": False,
                "last_writers": [writer_summary(k, imap) for k in last[:8]],
                "truncated_if_more_than_eight": len(last) > 8}
        result[label] = {"callsite_section_offset": hex(at),
                         "candidate_ABI_argument_registers": arg,
                         "complete_static_branch_targets": not unresolved}
    return result, {"instruction_count": len(ins),
                    "unknown_or_unresolved_branch_offsets": unresolved,
                    "function_size_bytes": size}


def inspect(path: Path) -> dict[str, object]:
    from elftools.elf.elffile import ELFFile
    from elftools.elf.relocation import RelocationSection
    require(file_sha(path) == DRIVER_SHA, "unapproved_original_vcam_driver")
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        require(elf["e_type"] == "ET_REL" and elf["e_machine"] == "EM_AARCH64"
                and elf.elfclass == 64 and elf.little_endian, "incorrect_arch_or_elf")
        tidx = elf.get_section_index(".text")
        require(tidx is not None, "missing_text")
        text = elf.get_section(tidx).data()
        symbols = elf.get_section_by_name(".symtab")
        require(symbols is not None, "missing_function_symbols")
        wanted = ("b2r_pad_set_fh_fmt", "ccm_set_fmt", "ccm_set_fn0_config")
        funcs = {}
        for sym in symbols.iter_symbols():
            if sym.name in wanted and sym["st_shndx"] == tidx:
                require(sym.name not in funcs, "duplicate_target_symbol_" + sym.name)
                funcs[sym.name] = (int(sym["st_value"]), int(sym["st_size"]))
        require(set(funcs) == set(wanted), "missing_verified_functions")
        require(funcs["ccm_set_fmt"] == CCM_FMT and funcs["ccm_set_fn0_config"] == CCM_FN0,
                "CCM_prior_address_or_size_changed")
        require(funcs["b2r_pad_set_fh_fmt"][1] == B2R_SIZE,
                "B2R_prior_function_size_changed")
        require(funcs["b2r_pad_set_fh_fmt"][0] <= B2R_CALL_CCM <
                sum(funcs["b2r_pad_set_fh_fmt"]), "B2R_ccm_callsite_not_in_function")
        named_relocations = {}
        for section in elf.iter_sections():
            if not isinstance(section, RelocationSection) or int(section["sh_info"]) != tidx:
                continue
            symtab = elf.get_section(int(section["sh_link"]))
            for reloc in section.iter_relocations():
                if int(reloc["r_info_type"]) != CALL26:
                    continue
                sym = symtab.get_symbol(int(reloc["r_info_sym"]))
                at = int(reloc["r_offset"])
                named_relocations[at] = sym.name
        require(named_relocations.get(B2R_CALL_CCM) == "ccm_set_fmt",
                "B2R_to_CCM_relocation_not_valid")
        require(named_relocations.get(CCM_CALL_FN0) == "ccm_set_fn0_config",
                "CCM_to_FN0_relocation_not_valid")
        start, size = funcs["b2r_pad_set_fh_fmt"]
        related_sites = {
            name: at for at, name in sorted(named_relocations.items())
            if name in STAGES and start <= at < start + size}
        require(related_sites.get("ccm_set_fmt") == B2R_CALL_CCM,
                "unexpected_CCM_stage_edge")
        b2r, b2r_stats = analyze_function(text, start, size, related_sites)
        fstart, fsize = funcs["ccm_set_fmt"]
        ccm, ccm_stats = analyze_function(text, fstart, fsize,
                                          {"ccm_set_fn0_config": CCM_CALL_FN0})
        # Input register range is a static ABI candidate, not the count of
        # parameters accepted by the kernel setter (that is still unknown).
        return {
            "schema": "hasselblad-stage29-main-ccm-format-argflow-v1",
            "status": "PASS_hash_pinned_static_argument_reaching_definitions",
            "original_X2DII_firmware_version": "1.3.16.2",
            "original_vcam_driver_sha256": DRIVER_SHA,
            "B2R_to_CCM_callsite_verified": True,
            "CCM_to_fn0_callsite_verified": True,
            "B2R_related_format_callsite_argflow": b2r,
            "CCM_format_to_fn0_argflow": ccm,
            "B2R_CFG_summary": b2r_stats,
            "CCM_CFG_summary": ccm_stats,
            "analysis_is_path_insensitive_over_approximating": True,
            "last_writer_does_not_equal_original_argument_value": True,
            "no_live_register_or_camera_pixel_samples": True,
            "CCM_two_16bit_fields_from_previous_driver_audit": True,
            "CCM_16bit_field_semantics_proven": False,
            "CCM_six_coefficient_pixel_equation_proven": False,
            "CCM_Q_scale_or_RGB_order_proven": False,
            "original_vendor_instruction_bytes_exported": False,
            "vendor_IQ_array_data_exported": False,
            "photographic_HNCS_authorized": False,
            "Android_Photon_renderer_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--module", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        report = mock_tests()
    else:
        require(args.module is not None, "original_module_required")
        report = inspect(args.module)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()
