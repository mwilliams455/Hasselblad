# Hasselblad X2D II native-code research — Native1 checkpoint

This directory contains the reproducible research supporting the separate
`HasselbladPhoton` Android project. The work is specific to the official X2D II
100C firmware **1.3.16.2**. It is not a complete Hasselblad photographic renderer.

## What has actually run

1. The extracted Android 9 Bionic runtime loaded the original `libaaa.so`,
   `libdcam_fcali.so`, and core runtime in bounded QEMU ARM64 processes.
2. The original exported `scene_awb_result_recalib_unit` function executed with
   nine controlled cases. Its 56-byte instruction body and real callers establish
   a two-cell, unsigned Q12 calibration ABI.
3. A portable C reconstruction matched original ARM64 execution, including
   **10,000 deterministic valid comparisons compiled using Android NDK r27 and
   executed through the same Android 9 runtime**. Invalid-input guards are
   distinct from the original vendor return codes.
4. The standalone app calls the exact portable core through JNI. Its development
   check contains ten original-output vectors and four adapter guards. It does
   not load the original vendor ELF or apply this primitive to captured pixels.
5. The photographic-path investigation separately executed original `librcam.so`
   colour-profile coefficient and packed-LUT interpolation routines. Twelve
   bounded synthetic cases passed, followed by ten full-size profiles generated
   from the actual camera table. All 122,880 output lanes matched a C reference,
   with every byte also checked against an independent Python reference. See
   the separate report for the exact contract and limitations. These functions
   are not in the Native1 APK.

The original firmware's `system/build.prop` confirms Android 9, SDK 28,
`arm64-v8a`, and the `eagle2_hb722` target. Android provides a usable starting
point for runtime research. It does not make the camera's complete ISP or
sensor calibration an ordinary phone library.

## Evidence map

- `STATIC_NATIVE_FINDINGS.md`: official input, extraction, platform, dependencies.
- `firmware/firmware_provenance.json`: official URL, version, byte count, SHA-256.
- `firmware/manifests/`: extraction and per-file hashes, without firmware payloads.
- `colour_audit/portable/ABI_EVIDENCE.md`: recovered WB ABI and interpretation.
- `colour_audit/awb_recalib_unicorn_proof.json`: original instructions and guards.
- `colour_audit/portable/verification.json`: portable C versus original machine code.
- `runtime_probe/results/`: original matching-runtime load and WB execution logs.
- `runtime_probe/results/REPLAY_SUMMARY.json`: replay using the supplied runner.
- `photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.md`: active still-image colour path,
  original LUT-profile execution, and the remaining pixel-rendering work.
- The sibling app's `development/hasselblad/`: JNI host test, source provenance,
  capture-size selector tests, and exact retained native dependency headers.

Some recorded JSON includes absolute paths from the original build environment.
Those are provenance. The command-line runners accept relocated input paths,
or resolve their defaults relative to this research directory.

## Reproduce the firmware extraction

Use Linux and Python 3.11 or newer. Install the dependencies in an isolated
Python environment using `python -m pip install -r requirements.txt`.

Obtain the original firmware from:

https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim

Save it as `firmware/X2DII_100C_v1_3_16_2.cim`. The file must be 364,814,336 bytes
with SHA-256:

`9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`

Run from this directory:

```sh
python extract_official.py
python audit_dependencies.py
```

The extractor requires a fresh `firmware/extracted` output directory. It checks
the exact input hash, supports the observed full-OTA block format, copies regular
files only, and records rather than materializes filesystem links. It does not
invoke an updater, flash a device, or run extracted firmware executables.
Several gigabytes of free space are needed for the original package, temporary
partition images, extracted files, and reports.

## Replay original WB and portable-code execution

Supply Android NDK **27.0.12077973** and a Linux `qemu-aarch64-static` executable.
The recorded QEMU binary is 7.2.0 from the `multiarch/qemu-user-static`
`v7.2.0-1` release. Its SHA-256 is recorded in the runtime replay report.

```sh
python runtime_probe/run_android_probes.py \
  --ndk /absolute/path/to/Android/Sdk/ndk/27.0.12077973 \
  --qemu /absolute/path/to/qemu-aarch64-static \
  --firmware-root firmware/extracted \
  --output runtime_probe/results_replayed
```

This rebuilds the small probes for Android API 28, verifies the original ELF and
portable core hashes, uses the original Android linker and dependencies, and
runs five bounded jobs. Expected result: all five PASS, nine original WB cases
pass, and all 10,000 portable/original comparisons pass. No dependency function
is stubbed or replaced. The supplied output directory holds the rebuilt
executables and machine-readable results.

For the separate original-instruction proof and host differential check:

```sh
python colour_audit/prove_awb_recalib_unit.py \
  firmware/extracted/system/lib64/libaaa.so \
  colour_audit/awb_recalib_replayed.json
python colour_audit/portable/verify_against_arm64.py \
  firmware/extracted/system/lib64/libaaa.so \
  colour_audit/portable/verification_replayed.json
```

The photographic-path report documents the separate `replay_lut_probe.py` runner.
Its synthetic fixtures and optional exact-hash `--config` camera-table input
establish LUT-profile preparation; neither applies a photographic LUT to a frame.

## Scope and next rendering work

The WB leaf neither estimates scene white balance nor supplies calibration for
a phone sensor. Applying its integer arithmetic to arbitrary camera gains would
not establish a Hasselblad rendering path. Native1 therefore leaves the actual
photo colour processing in Photon while exposing the recovered function in an
explicit native development check.

The active still-processing paths examined enable `MAIN_CCM`, `MAIN_GAMMA`, and
`MAIN_3DLUT`, while bypassing the module named `MAIN_HNCS`. The next work follows
the active matrix/gamma/LUT stages: prove LUT storage and channel/grid layout,
input/output encoding and stage order, reproduce the hardware pixel application
in software, and establish the mapping from a phone's calibrated RAW data.
Controlled reference renders and on-phone captures are needed before claiming
complete Hasselblad photographic output.

## Sources and licensing

- Original Photon revision:
  https://github.com/eszdman/PhotonCamera/commit/b2eff821a858033515eb2700e7292befecc95225
- Official firmware catalogue:
  https://api.hasselblad.com/products/downloads/173/firmware
- Original CIM research:
  https://github.com/radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions
- Pinned QEMU DevKit:
  https://github.com/derrickyau9/Hasselblad-X-System-QEMU-DevKit/tree/d82dc3b0faa6456c260378df6352a07f929caed2

See `THIRD_PARTY_NOTICES.md` and the retained license texts. The firmware,
proprietary camera libraries, camera LUT payloads, and models must be obtained
separately; none is included in this bundle or the Native1 app.
