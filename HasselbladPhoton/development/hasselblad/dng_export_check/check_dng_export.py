#!/usr/bin/env python3
"""Verify the actual app DNG writer against the preserved Native1 creator.

All image samples are synthetic. Build outputs and small generated fixtures go
to --work-dir; only the JSON report needs to be retained with the source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_tiff(path):
    data = Path(path).read_bytes()
    if data[:4] != b"II*\0":
        raise AssertionError("Expected classic little-endian TIFF")
    offset = struct.unpack_from("<I", data, 4)[0]
    fields = {}
    count = struct.unpack_from("<H", data, offset)[0]
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8, 11: 4, 12: 8}
    for index in range(count):
        start = offset + 2 + index * 12
        tag, kind, n = struct.unpack_from("<HHI", data, start)
        length = sizes[kind] * n
        ptr = start + 8 if length <= 4 else struct.unpack_from("<I", data, start + 8)[0]
        payload = data[ptr:ptr + length]
        if len(payload) != length or tag in fields:
            raise AssertionError("Truncated or duplicate TIFF tag")
        fields[tag] = (kind, n, payload)

    def integers(tag):
        kind, n, payload = fields[tag]
        return struct.unpack("<" + {3: "H", 4: "I"}[kind] * n, payload)

    strip_offsets = integers(273)
    strip_counts = integers(279)
    strip = b"".join(data[pos:pos + n] for pos, n in zip(strip_offsets, strip_counts))
    assert len(strip) == sum(strip_counts)
    return fields, strip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-source", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, default=os.environ.get("JAVA_HOME"))
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    assert sys.byteorder == "little", "This Android-equivalent fixture uses a little-endian host"
    here = Path(__file__).resolve().parent
    project = here.parents[2]
    cpp = project / "app/src/main/cpp"
    current = cpp / "dngCreator.cpp"
    jdk = args.java_home
    if jdk is None or not (jdk / "include/jni.h").is_file():
        raise SystemExit("Pass --java-home pointing to a JDK with JNI headers")
    compiler = shutil.which(args.cxx)
    if compiler is None:
        raise SystemExit("A C++17 compiler is required")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    commands = []
    for name, source in [("native1", args.baseline_source.resolve()), ("native1a", current)]:
        executable = args.work_dir / (name + "_fixture")
        command = [compiler, "-std=c++17", "-O1", "-fno-strict-aliasing",
                   "-I" + str(here / "host_include"), "-I" + str(cpp),
                   "-I" + str(cpp / "deps"), "-I" + str(jdk / "include"),
                   "-I" + str(jdk / "include/linux"),
                   '-DPHOTON_DNG_SOURCE="' + str(source) + '"']
        if name == "native1a":
            command.append("-DNATIVE1A_GUARDS=1")
        command += [str(here / "dng_export_fixture.cpp"), "-ldl", "-o", str(executable)]
        commands.append(command)
        with (args.work_dir / (name + "_compile.log")).open("w") as stream:
            subprocess.run(command, check=True, stdout=stream, stderr=subprocess.STDOUT)
        with (args.work_dir / (name + "_execution.log")).open("w") as stream:
            subprocess.run([str(executable), str(args.work_dir / name)], check=True,
                           stdout=stream, stderr=subprocess.STDOUT)

    cases = []
    expected = [
        ("raw16_1023", 1023, 16, 1), ("raw16_65535", 65535, 16, 1),
        ("jpeg16_1023", 1023, 16, 7), ("jpeg16_65535", 65535, 16, 7),
        ("raw10_1023", 1023, 10, 1), ("raw10_linearized_4095", 65535, 10, 1)
    ]
    for name, level, bits, compression in expected:
        old_fields, old_strip = parse_tiff(args.work_dir / "native1" / (name + ".dng"))
        fields, strip = parse_tiff(args.work_dir / "native1a" / (name + ".dng"))
        assert old_fields[50717][:2] == (5, 1), "Baseline did not reproduce the RATIONAL defect"
        numerator, denominator = struct.unpack("<II", old_fields[50717][2])
        assert denominator and numerator / denominator == level
        assert fields[50717] == (4, 1, struct.pack("<I", level)), "WhiteLevel must be LONG/count1/exact value"
        assert struct.unpack("<H", fields[258][2])[0] == bits
        assert struct.unpack("<H", fields[259][2])[0] == compression
        assert strip == old_strip, "The export fix changed the encoded RAW strip"
        # Offsets change because LONG fits inline and RATIONAL did not. Every
        # other field payload, including the compression table, must match.
        assert {k: v for k, v in fields.items() if k not in (50717, 273)} == {
            k: v for k, v in old_fields.items() if k not in (50717, 273)}
        before = (args.work_dir / "native1a" / (name + ".input.bin")).read_bytes()
        after = (args.work_dir / "native1a" / (name + ".after.bin")).read_bytes()
        old_after = (args.work_dir / "native1" / (name + ".after.bin")).read_bytes()
        assert after == old_after, "The export fix changed the input-buffer handling"
        if bits == 16:
            assert before == after, "16-bit export modified input samples"
        if bits == 16 and compression == 1:
            assert strip == before, "Uncompressed RAW strip differs from input samples"
        if "linearized" in name:
            assert fields[50712][:2] == (3, 1024), "Expected the existing 10-bit linearization table"
        cases.append({"name": name, "result": "pass", "white_level_type": "LONG",
                      "white_level_tiff_type": 4, "white_level_count": 1, "white_level_value": level,
                      "bits_per_sample": bits, "compression": compression,
                      "encoded_strip_bytes": len(strip), "encoded_strip_sha256": hashlib.sha256(strip).hexdigest(),
                      "encoded_strip_identical_to_native1": True,
                      "all_other_metadata_payloads_identical_except_strip_offset": True,
                      "uncompressed_u16_strip_equals_input": True if bits == 16 and compression == 1 else None,
                      "input_sample_buffer_unchanged": before == after,
                      "existing_input_buffer_handling_matches_native1": True})
    guards = json.loads((args.work_dir / "native1a/guards.json").read_text())
    assert guards == {"invalid_native_calls_rejected": 12, "representable_boundaries_accepted": 4}
    report = {"checkpoint": "Native1A", "result": "pass", "fixture_cases": cases,
              "guards": guards, "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
              "compile_commands": commands,
              "source_hashes": {str(path): sha(path) for path in [current, args.baseline_source.resolve(),
                    cpp / "dngWhiteLevel.h", cpp / "deps/tiny_dng_writer.h",
                    here / "dng_export_fixture.cpp", here / "host_include/android/log.h", Path(__file__)]},
              "scope": "Actual production C++ creator and retained TIFF writer; Android logging stub only; all samples synthetic",
              "limits": ["Host execution, not a new phone capture",
                         "Compressed strip equality proves this metadata fix retains Native1 encoded payload; no new independent JPEG-lossless decoder test",
                         "Existing 10-bit encoding intentionally changes/repacks input samples; that branch is disabled by Native1 capture policy",
                         "Software provenance must also be checked in compiled Java/DEX and confirmed on the next phone DNG"]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "cases": len(cases), "guards": guards, "report": str(args.report)}))


if __name__ == "__main__":
    main()
