#!/usr/bin/env python3
"""Rebuild and replay the bounded MAIN_GAMMA relocated-metadata probe.

Requires a privately supplied, exact firmware extraction, NDK clang and QEMU.
Original code/configuration payloads are never copied into the output folder.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import resource
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile

LIB_SHA = "3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))


def symbols_and_dependencies(root, library):
    def read_elf(path):
        return ELFFile(io.BytesIO(path.read_bytes()))
    elf = read_elf(library)
    debug = lzma.decompress(elf.get_section_by_name(".gnu_debugdata").data())
    if len(debug) > 64 * 1024 * 1024:
        raise ValueError("Unexpected debug metadata size")
    mini = ELFFile(io.BytesIO(debug))
    names = {}
    for table in (elf.get_section_by_name(".dynsym"), mini.get_section_by_name(".symtab")):
        for item in table.iter_symbols():
            if item["st_value"] and item["st_size"]:
                names.setdefault(item["st_value"], set()).add(item.name)
    if "dcam_isp_vreg_get_type" not in names.get(0x54b88, set()):
        raise ValueError("Probe anchor symbol mismatch")
    runtime, pending = {}, [library, root / "system/bin/linker64"]
    while pending:
        path = pending.pop()
        relative = str(path.relative_to(root))
        if relative in runtime:
            continue
        runtime[relative] = sha(path)
        dynamic = read_elf(path).get_section_by_name(".dynamic")
        if dynamic is None:
            continue
        for item in dynamic.iter_tags():
            if item.entry.d_tag == "DT_NEEDED":
                name = item.needed
                if Path(name).name != name:
                    raise ValueError("Unexpected dependency name")
                matches = [root / part / name for part in ("system/lib64", "vendor/lib64")]
                match = next((candidate for candidate in matches if candidate.is_file()), None)
                if match is None:
                    raise ValueError("Missing original runtime dependency: " + name)
                pending.append(match)
    return names, dict(sorted(runtime.items()))


def annotate(records, names):
    parameters = [item for item in records if item.get("event") == "parameter"]
    if len(records) != 34 or len(parameters) != 30:
        raise ValueError("Unexpected bounded descriptor count")
    for item in parameters:
        iq = names.get(int(item["iq_getter_va"], 16), set())
        module = names.get(int(item["module_getter_va"], 16), set())
        selected = [name for name in iq if name.startswith("DIQ_iq_main_gamma_")]
        if len(selected) != 1 or selected[0].replace("DIQ_iq_", "DIQ_mod_") not in module:
            raise ValueError("MAIN_GAMMA getter symbol relationship mismatch")
        item["iq_getter"] = selected[0]
        item["module_getter"] = selected[0].replace("DIQ_iq_", "DIQ_mod_")
        item["parameter"] = selected[0].removeprefix("DIQ_iq_main_gamma_")
        kind = item["word0"] & 0xffff
        item["descriptor_type"] = kind
        item["vreg_offset"] = hex(item["word1"])
        if kind == 3:
            item["field_shift"] = item["word2"]
            item["field_mask"] = hex(item["word3"])
            item["field_bits"] = item["word3"].bit_count()
        elif kind == 1:
            item["physical_address"] = hex(item["word2"])
            item["word_count"] = item["word3"]
        else:
            raise ValueError("Unexpected MAIN_GAMMA descriptor type")
    main = [item for item in parameters if item["parameter"] == "normal_gamma_lut"]
    if len(main) != 1 or (main[0]["register_id"], main[0]["word2"], main[0]["word3"]) != (4266, 0xf322e800, 257):
        raise ValueError("Main positive gamma memory descriptor mismatch")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", type=Path, required=True)
    parser.add_argument("--clang", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.firmware_root.resolve()
    library = root / "system/lib64/librcam.so"
    if sha(library) != LIB_SHA:
        raise ValueError("Unsupported librcam SHA-256")
    names, runtime = symbols_and_dependencies(root, library)
    source = Path(__file__).resolve().with_name("inspect_main_gamma_metadata.c")
    clang, qemu = args.clang.resolve(), args.qemu.resolve()
    version = subprocess.run([str(clang), "--version"], capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="hb-main-gamma-metadata-") as directory:
        binary = Path(directory) / "inspect_main_gamma_metadata_android28_arm64"
        build = [str(clang), "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-ldl", "-o", str(binary)]
        subprocess.run(build, capture_output=True, text=True, check=True, timeout=30)
        run = [str(qemu), "-L", str(root), str(binary), str(library)]
        environment = os.environ.copy()
        for key in ("LD_PRELOAD", "LD_AUDIT", "LD_DEBUG"):
            environment.pop(key, None)
        environment["LD_LIBRARY_PATH"] = str(root / "system/lib64")
        child = subprocess.run(run, capture_output=True, text=True, timeout=20, env=environment, preexec_fn=limits)
        if child.returncode or child.stderr:
            raise RuntimeError("Metadata probe failed: exit=%d stderr=%r" % (child.returncode, child.stderr))
        records = annotate([json.loads(line) for line in child.stdout.splitlines()], names)
        result = {"result": "pass", "firmware": "X2D II 100C 1.3.16.2", "library_sha256": LIB_SHA,
                  "method": "Read exact linker-relocated MAIN_GAMMA descriptors using matching Android/Bionic under QEMU; dlopen initializers execute, no camera processing function is called",
                  "source_sha256": sha(source), "runner_sha256": sha(Path(__file__)), "probe_sha256": sha(binary),
                  "build_command": build, "run_command": run, "runtime_environment": {"LD_LIBRARY_PATH": environment["LD_LIBRARY_PATH"]},
                  "compiler_version": version, "compiler_entrypoint_sha256": sha(clang), "qemu_sha256": sha(qemu),
                  "runtime_dt_needed_closure_sha256": runtime,
                  "runtime_hash_scope": "Transitive DT_NEEDED dependencies and original linker; incidental dlopen dependencies are not traced",
                  "exit": child.returncode, "stderr": child.stderr, "records": records,
                  "pointer_provenance": {"register_table_pointer_va": "0x59e048",
                                         "normal_count_pointer_va": "0x59e168", "normal_groups_pointer_va": "0x59e170",
                                         "normal_memory_count_pointer_va": "0x59e178", "normal_memory_records_pointer_va": "0x59e180",
                                         "common_groups_va": "0x59ae60", "common_group_count": 2,
                                         "common_table_reference_vas": ["0x3a11ec", "0x3a11f0"], "common_count_comparison_va": "0x3a1350"},
                  "limits": "Register descriptors establish storage extents and bit fields; no LUT payload, hardware pixel precision, interpolation or dither algorithm is recovered by this probe"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"result": "pass", "records": len(records), "original_runtime_files_hashed": len(runtime), "output": str(args.output)}))


if __name__ == "__main__":
    main()
