#!/usr/bin/env python3
"""Stage37A: bounded exact-firmware ARM-side MAIN CCM candidate triage.

Evidence only: never executes vendor code, decodes a vendor image to pixels,
exports instruction bytes, coefficients, calibration records or private photos.
A named, SIMD-using function is NOT proof of the Eagle2 pixel operation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PIN = {
    "system/lib64/librcam.so": "3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66",
    "system/lib64/libdcam_pp.so": "bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9",
    "system/lib64/libdcam_pp_base.so": "72934142975fa88ee65e331767e8b9badd9ca40bc987e3c9a2a5cf0ff60b3f76",
    "system/lib/modules/vcam_driver.ko": "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e",
}
EXPECTED_NAMES = {
    "system/lib64/librcam.so": ("DIQ_iq_main_ccm_lmtx_fw", "_calc_lerp_mx_lut_reg_idx_v5"),
    "system/lib64/libdcam_pp.so": ("raw2rgb_proc", "_raw2rgb_pull_buf_cb"),
    "system/lib64/libdcam_pp_base.so": ("message_trans_arm_proc_pull", "sl_message_trans_arm_proc_pull"),
    "system/lib/modules/vcam_driver.ko": ("ccm_set_ig0_config", "ccm_set_fmt", "ccm_set_fn0_config"),
}
MAX_DEBUG_UNCOMPRESSED = 64 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_FUNC_BYTES = 16384
MAX_SELECT = 60
MAX_EXPORT = 24
# Deliberately narrow: group by plausible pixel computation or a direct MAIN CCM
# namespace. Decoding the entire firmware here would conceal the evidence gate.
MAIN_WORDS = re.compile(r"(?:main_ccm|lmtx|(?:^|[_:])ccm(?:[_:]|$)|colou?r_?corr|color_?matrix|rgb2rgb|rgb_to_rgb)", re.I)
TRANSPORT_WORDS = re.compile(r"(?:raw2rgb|message_trans_arm_proc_pull|dsp_frwk|libpp_function_entry)", re.I)
# Mnemonics are only triage signals, never a proof of photo pixel semantics.
ARITHMETIC = {"mul", "madd", "msub", "smull", "umull", "smlal", "smlsl",
              "smaddl", "umsubl", "fmul", "fmadd", "fmsub", "fmla", "fmls",
              "mla", "mls", "smulh", "umulh", "sqrdmulh", "sqdmulh",
              "sqdmlal", "sqdmlsl", "sqdmull", "sqrdmlah", "sqrdmlsh",
              "fmlal", "fmlsl", "fcmla"}
NAMES_KNOWN_CONTROL = {
    "DIQ_iq_main_ccm_lmtx_fw": "profile_parameter_getter",
    "_calc_lerp_mx_lut_reg_idx_v5": "coefficient_preparation_from_stage17",
    "ccm_set_ig0_config": "mmio_register_writer_from_stage25",
    "ccm_set_fmt": "frame_format_setter_from_stage29",
    "ccm_set_fn0_config": "frame_format_register_writer_from_stage29",
    "raw2rgb_proc": "dsp_request_builder_from_prior_dispatch_audit",
    "_raw2rgb_pull_buf_cb": "dsp_parameter_copy_callback_from_prior_dispatch_audit",
    "message_trans_arm_proc_pull": "dsp_transport_wrapper_from_prior_dispatch_audit",
    "sl_message_trans_arm_proc_pull": "dsp_transport_wrapper_from_prior_dispatch_audit",
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def digest(path: Path) -> str:
    with path.open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def score(name: str) -> int:
    if name in NAMES_KNOWN_CONTROL:
        return 100
    n = name.lower()
    if "main_ccm" in n or "lmtx" in n:
        return 90
    if re.search(r"(^|[_:])ccm([_:]|$)", n):
        return 70
    if any(z in n for z in ("color_correct", "colour_correct", "colormatrix", "color_matrix", "rgb2rgb", "rgb_to_rgb")):
        return 60
    if "raw2rgb" in n:
        return 40
    if "message_trans_arm_proc_pull" in n:
        return 20
    return 0


def sanitized_kind(name: str) -> str:
    if name in NAMES_KNOWN_CONTROL:
        return NAMES_KNOWN_CONTROL[name]
    if MAIN_WORDS.search(name):
        return "unresolved_named_colour_candidate"
    if TRANSPORT_WORDS.search(name):
        return "unresolved_named_transport_or_raw2rgb"
    return "not_in_targeted_symbol_scope"


@dataclass(frozen=True)
class Function:
    name: str
    addr: int
    size: int
    shndx: Any
    rank: int


def add_symbols(symbols: dict[tuple[str, int], Function], sec: Any) -> None:
    if sec is None or not hasattr(sec, "iter_symbols"):
        return
    for sym in sec.iter_symbols():
        try:
            name = sym.name
            if not name or sym["st_info"]["type"] != "STT_FUNC" or sym["st_shndx"] == "SHN_UNDEF":
                continue
            addr, size = int(sym["st_value"]), int(sym["st_size"])
            if size < 4 or size > MAX_FUNC_BYTES or score(name) <= 0:
                continue
            key = (name, addr)
            x = Function(name, addr, size, sym["st_shndx"], score(name))
            if key in symbols:
                require(symbols[key].size == size, "duplicate_symbol_size_conflict")
            symbols[key] = x
        except KeyError:
            continue


def symbol_table(elf: Any) -> tuple[dict[tuple[str, int], Function], int]:
    found: dict[tuple[str, int], Function] = {}
    full_count = 0
    for section_name in (".dynsym", ".symtab"):
        sec = elf.get_section_by_name(section_name)
        if sec is not None and hasattr(sec, "iter_symbols"):
            full_count += sum(1 for _ in sec.iter_symbols())
            add_symbols(found, sec)
    mini = elf.get_section_by_name(".gnu_debugdata")
    if mini is not None:
        raw = lzma.decompress(mini.data(), memlimit=MAX_DEBUG_UNCOMPRESSED * 4)
        require(len(raw) <= MAX_DEBUG_UNCOMPRESSED, "mini_debugdata_too_large")
        from elftools.elf.elffile import ELFFile
        mb = ELFFile(io.BytesIO(raw))
        msec = mb.get_section_by_name(".symtab")
        if msec is not None:
            full_count += sum(1 for _ in msec.iter_symbols())
            add_symbols(found, msec)
    return found, full_count


def code_slice(elf: Any, fn: Function) -> bytes:
    if elf["e_type"] == "ET_REL":
        require(isinstance(fn.shndx, int), "non_section_relative_function")
        sec = elf.get_section(fn.shndx)
        require(bool(sec["sh_flags"] & 4), "non_executable_section")
        require(fn.addr + fn.size <= int(sec["sh_size"]), "function_outside_section")
        return sec.data()[fn.addr:fn.addr + fn.size]
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD" or not (int(segment["p_flags"]) & 1):
            continue
        v, size = int(segment["p_vaddr"]), int(segment["p_filesz"])
        if v <= fn.addr and fn.addr + fn.size <= v + size:
            start = fn.addr - v
            return segment.data()[start:start+fn.size]
    raise ValueError("function_not_in_executable_segment")


def disasm_summary(code: bytes, address: int) -> dict[str, int | bool]:
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoder.detail = True
    instructions = list(decoder.disasm(code, address))
    require(len(instructions) > 0 and sum(i.size for i in instructions) == len(code),
            "function_disassembly_incomplete")
    counts = dict(instructions=len(instructions), multiplications=0, vector_multiplications=0,
                  memory_reads=0, memory_writes=0, backward_branches=0, call_instructions=0)
    for ins in instructions:
        m = ins.mnemonic.lower()
        if m in ARITHMETIC:
            counts["multiplications"] += 1
            if any(o.type == ARM64_OP_REG and
                   ins.reg_name(o.reg).startswith(("v", "q")) for o in ins.operands):
                counts["vector_multiplications"] += 1
        if m in ("bl", "blr"):
            counts["call_instructions"] += 1
        if m.startswith(("ld", "prfm")) and any(o.type == ARM64_OP_MEM for o in ins.operands):
            counts["memory_reads"] += 1
        if m.startswith("st") and any(o.type == ARM64_OP_MEM for o in ins.operands):
            counts["memory_writes"] += 1
        if (m == "b" or m.startswith("b.") or m in ("cbz", "cbnz", "tbz", "tbnz")):
            if any(o.type == ARM64_OP_IMM and address <= int(o.imm) < ins.address
                   for o in ins.operands):
                counts["backward_branches"] += 1
    return counts


def inspect_elf(path: Path, pin: str, required: tuple[str, ...]) -> dict[str, Any]:
    from elftools.elf.elffile import ELFFile
    require(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES, "missing_or_oversize_elf")
    require(digest(path) == pin, "wrong_original_binary_sha256")
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        require(elf["e_machine"] == "EM_AARCH64" and elf.little_endian,
                "wrong_original_binary_architecture")
        require(elf["e_type"] in ("ET_REL", "ET_DYN", "ET_EXEC"), "unsupported_elf_type")
        found, sym_count = symbol_table(elf)
        funcs = list(found.values())
        present_names = {f.name for f in funcs}
        require(all(n in present_names for n in required), "missing_pinned_prior_stage_symbols")
        chosen = sorted(funcs, key=lambda x: (-x.rank, x.name, x.addr))[:MAX_SELECT]
        relevant = []
        for f in chosen:
            info = disasm_summary(code_slice(elf, f), f.addr)
            relevant.append({"symbol": f.name, "function_bytes": f.size,
                             "prior_classification": sanitized_kind(f.name),
                             "assembly_triage": info,
                             "pixel_input_buffer_abi_proven": False,
                             "isolated_original_ccm_pixel_arithmetic_proven": False})
        priorities = [x["symbol"] for x in relevant
                      if x["prior_classification"] == "unresolved_named_colour_candidate"
                      and x["assembly_triage"]["multiplications"] > 0
                      and x["assembly_triage"]["memory_reads"] > 0
                      and x["assembly_triage"]["memory_writes"] > 0]
        return {
            "sha256": pin, "symbol_table_entries_considered": sym_count,
            "bounded_names_matching_query": len(funcs),
            "bounded_functions_scanned": len(relevant),
            "selection_truncated": len(funcs) > MAX_SELECT,
            "required_prior_symbols_confirmed": list(required),
            "candidate_summary": relevant[:MAX_EXPORT],
            "candidate_export_truncated": len(relevant) > MAX_EXPORT,
            "unresolved_named_arithmetic_candidates_for_manual_review": priorities[:MAX_EXPORT],
            "unresolved_named_arithmetic_count": len(priorities),
            "previously_known_control_transport_names": [f.name for f in chosen
                if f.name in NAMES_KNOWN_CONTROL],
            "new_original_software_ccm_oracle_demonstrated": False,
        }


def synthetic() -> dict[str, Any]:
    # These do not use or fabricate Hasselblad register values.
    assert score("DIQ_iq_main_ccm_lmtx_fw") == 100
    assert score("ccm_set_ig0_config") == 100
    assert score("_calc_lerp_mx_lut_reg_idx_v5") == 100
    assert score("unrelated_memory_copy") == 0
    assert score("not_a_matrix") == 0
    assert score("x_ccm_y") == 70
    assert score("x_color_correct_x") == 60
    assert score("raw2rgb_raw_transform") == 40
    assert sanitized_kind("ccm_set_ig0_config") == "mmio_register_writer_from_stage25"
    assert sanitized_kind("x_ccm_y") == "unresolved_named_colour_candidate"
    assert sanitized_kind("random") == "not_in_targeted_symbol_scope"
    assert sanitized_kind("my_raw2rgb_proc") == "unresolved_named_transport_or_raw2rgb"
    assert len(PIN) == len(EXPECTED_NAMES) == 4
    assert not MAIN_WORDS.search("gamma_setting_without_colour")
    return {"status": "PASS_synthetic", "checks": 14,
            "vendor_assets_loaded": False, "pixels_processed": False,
            "ccm_pixel_equation_proven": False}


def original(firmware_root: Path) -> dict[str, Any]:
    source: dict[str, Any] = {}
    for relative, pin in PIN.items():
        source[relative] = inspect_elf(firmware_root / relative, pin,
                                       EXPECTED_NAMES[relative])
    return {
        "schema": "hasselblad-stage37-main-ccm-arm-candidate-triage-v1",
        "status": "PASS_exact_pinned_static_symbol_and_instruction_triage",
        "source_files": source,
        "scope": "Four hash-pinned ARM binaries only; named bounded functions and instruction class counts",
        "full_frame_or_pixel_samples_processed": False,
        "new_original_ccm_pixel_equation_recovered": False,
        "pixel_abi_or_qscale_or_clipping_proven": False,
        "DSP_remote_colour_implementation_recovered": False,
        "meaning_of_MMIO_16x6_lmtx_coefficients_proven": False,
        "firmware_OR_vendor_code_OR_coefficients_exported": False,
        "photographic_output_modified": False,
        "interpretation_limit": "Function symbol names and instruction classes cannot prove or exclude an unnamed/indirect software pixel kernel, an ISP hardware equation, or a remote DSP operation. Stage37 searches for CPU candidates only. Any discovered candidate requires separate ABI/dataflow and original pixel tests.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--firmware-root", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.self_test:
        data = synthetic()
    else:
        require(args.firmware_root is not None, "firmware_root_required")
        data = original(args.firmware_root)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": data["status"],
                      "source_count": len(data.get("source_files", {})),
                      "new_ccm_pixel_equation_recovered": False}))


if __name__ == "__main__":
    main()