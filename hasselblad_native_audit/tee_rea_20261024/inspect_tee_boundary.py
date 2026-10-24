#!/usr/bin/env python3
"""Read-only bounded TEE trustlet and host-client inventory from X2D II OTA extraction.

Privacy: emits only paths, magic classes, named standard TEEC imports,
UUID-encoding hit *presence*, and counts; no vendor bytes, disassembly,
keys, numeric tuning or private images. This cannot prove decryption.
"""
from __future__ import annotations
import argparse
import json
import re
import uuid
from pathlib import Path

UUID = uuid.UUID("09db16c0-873b-4fed-b87e-a5d2b86293a2")
MATCH = {
    "uuid_text": str(UUID).encode(),
    "uuid_hex": UUID.hex.encode(),
    "uuid_raw_be": UUID.bytes,
    "uuid_raw_teec_le": UUID.bytes_le,
}
TARGETS = ("ss_dsp_manager", "libfw_util_ca.so", "libfw_util.so",
           "libdsp_frwk.so", "libteec.so", "ss_dsp0.fw", "ss_dsp1.fw",
           "ss_dsp2.fw", "ask_dsp.img", "tos.img", "bootarea.img")
PATTERN = re.compile(r"(^|/)(?:tee|optee|trustzone|trustlet|qsee|secure_app|keymaster)(?:/|[-_.])", re.I)
SAFE = re.compile(r"^[A-Za-z0-9_+./-]{1,230}$")
BYTES_LIMIT = 96 * 1024 * 1024
SCAN_BUDGET = 3 * 1024 * 1024 * 1024


def inspect_elf(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as f:
        elf = ELFFile(f)
        imports = set()
        deps = set()
        dyn = elf.get_section_by_name(".dynsym")
        if dyn:
            for s in dyn.iter_symbols():
                if s.name.startswith("TEEC_") and s["st_shndx"] == "SHN_UNDEF":
                    imports.add(s.name)
        dynamic = elf.get_section_by_name(".dynamic")
        if dynamic:
            for tag in dynamic.iter_tags():
                if tag.entry.d_tag == "DT_NEEDED":
                    deps.add(tag.needed)
        return {"architecture": str(elf["e_machine"]),
                "standard_teec_imports": sorted(imports)[:30],
                "depends_on_libteec": "libteec.so" in deps,
                "elf_executable_type": str(elf["e_type"])}


def audit(root):
    if not (root / "system/etc/VERSION").is_file():
        raise ValueError("missing_extracted_system_version")
    if (root / "system/etc/VERSION").read_text().strip() != "1.3.16.2":
        raise ValueError("unexpected_firmware_version")
    files = [p for prefix in ("system", "vendor")
             for p in (root / prefix).rglob("*") if p.is_file() and not p.is_symlink()]
    files.sort()
    target_rows = []
    uuid_rows = []
    trusted_candidates = []
    scanned = 0
    skipped_big = 0
    unreadable = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        if not SAFE.fullmatch(rel) or ".." in rel.split("/"):
            continue
        name = path.name
        sz = path.stat().st_size
        important = name in TARGETS or name.lower().endswith((".ta", ".tlbin"))
        trust_name = bool(PATTERN.search(rel)) or name.lower().endswith((".ta", ".tlbin")) or name in ("tos.img", "bootarea.img")
        if trust_name:
            trusted_candidates.append(rel)
        if sz > BYTES_LIMIT or scanned + sz > SCAN_BUDGET:
            skipped_big += 1
            if important:
                target_rows.append({"path": rel, "bytes": sz,
                                    "content_scanned": False, "reason": "limit"})
            continue
        # Include all files in the bounded scan: UUID may be in a non-obvious ELF.
        try:
            data = path.read_bytes()
        except OSError:
            unreadable += 1
            continue
        scanned += len(data)
        hits = {kind: (value in data or
                       (kind in ("uuid_text", "uuid_hex")
                        and value.upper() in data)) for kind, value in MATCH.items()}
        if any(hits.values()):
            uuid_rows.append({"path": rel, "matching_encodings":
                              sorted(k for k,v in hits.items() if v)})
        if important:
            magic = ("ELF" if data[:4] == b"\x7fELF" else
                     "IMAH" if b"IM*H" in data[:256] else
                     "TBIE" if b"TBIE" in data[:256] else
                     "MCLF" if data[:4] == b"MCLF" else "unclassified")
            row = {"path": rel, "bytes": sz, "content_scanned": True, "magic": magic}
            if magic == "ELF":
                try:
                    row.update(inspect_elf(path))
                except Exception as exc:
                    row["elf_inspection"] = type(exc).__name__
            target_rows.append(row)
        # Keep original bytes out of any persisted output.
        del data
    return {
        "schema": "hasselblad-original-tee-boundary-inventory-20261024-v1",
        "firmware": "X2D II 100C 1.3.16.2",
        "original_firmware_executed": False,
        "original_firmware_decrypted_inner_dsp": False,
        "trusted_application_executed": False,
        "uuid": str(UUID),
        "uuid_encoding_patterns_examined": sorted(MATCH),
        "files_listed": len(files),
        "scanned_bytes": scanned,
        "unscanned_oversize_or_budget": skipped_big,
        "unreadable": unreadable,
        "named_targets": target_rows,
        "exact_ta_file_paths": sorted(x["path"] for x in target_rows if x["path"].lower().endswith((".ta", ".tlbin"))),
        "exact_ta_file_count": sum(1 for x in target_rows if x["path"].lower().endswith((".ta", ".tlbin"))),
        "named_imah_containers": [x["path"] for x in target_rows if x.get("magic") == "IMAH"],
        "uuid_match_files": uuid_rows[:60],
        "uuid_match_file_count": len(uuid_rows),
        "trusted_candidate_paths": trusted_candidates[:80],
        "trusted_candidate_count": len(trusted_candidates),
        "uuid_absence_excludes_hardware_secure_storage": False,
        "no_vendor_binary_bytes_exported": True,
        "host_library_call_imports_are_not_verified_runtime_dispatch": True,
    }


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "system/etc").mkdir(parents=True)
        (root / "system/etc/VERSION").write_text("1.3.16.2")
        (root / "system/bin").mkdir()
        (root / "system/bin/ss_dsp_manager").write_bytes(b"SS" + UUID.bytes_le)
        (root / "vendor/tee").mkdir(parents=True)
        (root / "vendor/tee/test.ta").write_bytes(b"no-secret" + str(UUID).encode())
        result = audit(root)
        assert result["uuid_match_file_count"] == 2
        assert result["trusted_candidate_count"] == 1
        assert result["exact_ta_file_count"] == 1
        assert not result["original_firmware_decrypted_inner_dsp"]
        return {"status": "PASS_synthetic", "checks": 4,
                "source_is_original": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--firmware-root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if not a.self_test and not a.firmware_root:
        p.error("--firmware-root required except for --self-test")
    result = selftest() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result.get("status", "completed"),
                      "uuid_hits": result.get("uuid_match_file_count", 0),
                      "named_targets": len(result.get("named_targets", [])),
                      "candidate_paths": result.get("trusted_candidate_count", 0)}))


if __name__ == "__main__":
    main()
