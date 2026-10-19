#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild and replay the bounded X2D II WB probes on Linux.

The caller supplies an Android NDK, qemu-aarch64-static, and the extracted
official firmware. No original firmware libraries are included in this kit.
This runner executes the original code in the matching Android 9 runtime;
it does not install anything on a phone or modify a camera.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys


HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent
LIB_SHA256 = "7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba"
CORE_SHA256 = "99d56c2ed9a72411d64b732100e016d40660bbc3ee75858dfb3de37bdc1fef5e"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounded_child() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, required=True,
                        help="Android NDK r27 root (Linux x86_64 toolchain)")
    parser.add_argument("--qemu", type=Path, required=True,
                        help="qemu-aarch64-static executable; tested with 7.2.0")
    parser.add_argument("--firmware-root", type=Path,
                        default=AUDIT / "firmware/extracted")
    parser.add_argument("--output", type=Path, default=HERE / "results_replayed")
    args = parser.parse_args()
    firmware = args.firmware_root.resolve()
    output = args.output.resolve()
    qemu = args.qemu.resolve()
    compiler = (args.ndk.resolve() / "toolchains/llvm/prebuilt/linux-x86_64/bin/"
                "aarch64-linux-android28-clang")
    library_dir = firmware / "system/lib64"
    original = library_dir / "libaaa.so"
    portable = AUDIT / "colour_audit/portable"
    core = portable / "hb_awb_recalib.c"
    if digest(original) != LIB_SHA256:
        raise ValueError("Input libaaa.so differs from the audited X2D II firmware")
    if digest(core) != CORE_SHA256:
        raise ValueError("Portable C differs from the verified Native1 core")
    if (firmware / "system/etc/VERSION").read_text().strip() != "1.3.16.2":
        raise ValueError("The supplied Android runtime has a different version")
    for required in (qemu, compiler, firmware / "system/bin/linker64"):
        if not required.is_file():
            raise FileNotFoundError(required)
    output.mkdir(parents=True, exist_ok=True)
    build = output / "build"
    build.mkdir(exist_ok=True)
    compiler_version = subprocess.run([str(compiler), "--version"], check=True,
                                     capture_output=True, text=True).stdout.splitlines()[0]
    flags = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-fPIE", "-pie",
             "-Wl,-z,max-page-size=16384"]
    probes = {}
    for name in ("load_probe", "awb_recalib_probe", "awb_portable_compare"):
        target = build / (name + "_android28_arm64")
        command = [str(compiler), *flags]
        if name == "awb_portable_compare":
            command += ["-I", str(portable), str(HERE / (name + ".c")), str(core)]
        else:
            command += [str(HERE / (name + ".c"))]
        command += ["-ldl", "-o", str(target)]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
        probes[name] = target

    # qemu is statically linked. This search path is consumed by the original
    # Android Bionic linker, with its original Android 9 dependencies.
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = str(library_dir)
    records = []
    jobs = [("load_libc", "load_probe", library_dir / "libc.so"),
            ("load_fcali", "load_probe", library_dir / "libdcam_fcali.so"),
            ("load_aaa", "load_probe", original),
            ("original_awb_recalib", "awb_recalib_probe", original),
            ("android_portable_vs_original", "awb_portable_compare", original)]
    for name, probe_name, library in jobs:
        command = [str(qemu), "-L", str(firmware), str(probes[probe_name]), str(library)]
        record = {"name": name, "library_sha256": digest(library),
                  "probe_sha256": digest(probes[probe_name])}
        try:
            result = subprocess.run(command, env=environment, capture_output=True,
                                    text=True, timeout=20, preexec_fn=bounded_child)
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            record.update(exit=result.returncode, stdout=result.stdout, stderr=result.stderr,
                          events=events, passed=(result.returncode == 0 and bool(events)))
            if probe_name == "awb_recalib_probe":
                record["passed"] &= (events[-1].get("cases") == 9 and
                                     events[-1].get("failed") == 0)
            elif probe_name == "awb_portable_compare":
                record["passed"] &= (events[-1].get("cases") == 10000 and
                                     events[-1].get("failed") == 0)
        except subprocess.TimeoutExpired:
            record.update(passed=False, error="Timed out after 20 seconds")
        except (ValueError, IndexError) as error:
            record.update(passed=False, error="Invalid probe output: " + str(error))
        (output / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n")
        records.append(record)
        print(name + ": " + ("PASS" if record["passed"] else "FAIL"), flush=True)

    report = {
        "firmware": "Hasselblad X2D II 100C 1.3.16.2",
        "compiler": compiler_version,
        "qemu_sha256": digest(qemu),
        "linker_sha256": digest(firmware / "system/bin/linker64"),
        "portable_c_sha256": digest(core),
        "all_passed": all(record["passed"] for record in records),
        "physical_android_device_tested": False,
        "full_awb_or_hncs_validated": False,
        "records": records,
    }
    (output / "REPLAY_SUMMARY.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
