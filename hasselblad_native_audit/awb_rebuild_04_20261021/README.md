# Hasselblad Photon — AWB Lost Stages Rebuild 04

**21 October 2026 — checkpoint `AWB_LOST_STAGE_REBUILD_04`.**

**Classification: test-verified owned source and recovery tooling; ORIGINAL VENDOR OPTIMIZER NOT RECOVERED.**

This is the executable continuation of Rebuild 03, preserving all of the earlier portable source and tests. Rebuild 04 reconstructs *the two-phase optimizer/caller state handoff* that the historical 20 October AWB research identified. It does not infer the numerical candidate optimizer, colour temperature conversion, actual E2 field mappings, or source-specific calibration coefficients. The old code and its original-firmware test harness were lost and are not included in this package.

## New C source

- `src/hb_awb_optimizer_boundary.{h,c}` — a versioned, trace-driven interface that binds an externally observed optimizer trace to the exact candidate accumulation via a reproducible, field-serialized FNV-1a fingerprint. An actual call to the original optimizer is **not** made. The trace can stage its observed status and opaque 32-byte fixture, but **cannot** itself establish vendor authenticity.
- `hb_awb_optimizer_stage_observation` does not alter caller state; `hb_awb_optimizer_apply_observed_caller_update` applies *explicitly supplied* post-return deltas in a second step. This addresses the historical requirement to preserve caller-side updates that occur after the optimizer returns. The delta formula and error-condition behaviour remain unknown and therefore MUST come from original-code observation rather than a guess.
- Double updates and older-frame updates are rejected; mismatched candidate fingerprints, unobserved caller windows, contradictory counts, overflow and unsupported conditions fail without partial publication. The replay never produces a fresh Hasselblad selected neutral.
- `src/hb_awb_state_diff.{h,c}` — exact byte and return-code comparator for two 920,560-byte AWB contexts and 1,000-byte REAWB handles from the **same initialized execution**, reporting counts and first differing offsets only. An equal synthetic fixture is **not** a proof of original-state equivalence.
- `tools/firmware_gate.py` — explicitly pinned official firmware recovery/verification gate. It knows the official package URL, expected length and SHA-256, and the original `libaaa.so` SHA-256. Local paths remain private. It does not execute firmware and does not embed or publish vendor binaries.

## Fresh host verification (Rebuild 04)

| Scope | Result |
|---|---|
| Optimizer-boundary owned C checks, GCC optimized | 150,334 passed |
| Optimizer-boundary owned C checks, GCC ASan/UBSan | 150,334 passed |
| Optimizer-boundary owned C checks, Clang optimized | 150,334 passed |
| Optimizer-boundary owned C checks, Clang ASan/UBSan | 150,334 passed |
| Independent Python optimizer trace/delta/fingerprint | 2,048 complete fixtures |
| Independent Python full-state diff oracle | 80 complete synthetic fixtures |
| Offline exact-firmware gate fail/pass controls | 8 passed |
| Real Native1C DNG -> bounded scene prep | 1,024/1,024 blocks matched |
| Real DNG -> staged optimizer/caller replay | passed; 320 survivors under explicitly synthetic masks/coefficients/deltas |
| Inherited Rebuild01 C checks | 33,327 optimized and sanitizer each |
| Inherited Rebuild02 C checks | 33,960 optimized and sanitizer each |
| Inherited Rebuild03 C checks | 801,012 optimized and sanitizer each |
| Inherited independent Python RAW/accumulation/filtering/scene checks | passed |
| **Original X2D II `libaaa.so` ARM64 comparison** | **NOT RUN — exact firmware unavailable in workspace** |

`evidence/PRIVATE_REPLAY_SUMMARY.json` contains only a sanitized summary from the original preserved DNG. RAW pixels, full unredacted capture sidecar, proprietary firmware payloads and vendor code are not included in this archive or GitHub.

## Exact firmware dependency, recovered from the Native1A provenance

The original **Hasselblad X2D II 100C firmware 1.3.16.2** was located historically at:

`https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim`

Pinned package SHA-256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` (364,814,336 bytes).

Pinned original extracted `system/lib64/libaaa.so` SHA-256:
`7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`.

The pinned archive and ELF are **not** in the current working directory; downloading via the tool environment was not possible. `tools/firmware_gate.py` can verify an existing private copy or download the exact official archive on a machine with authorized network access. The separately preserved Native1A source contains the original `extract_official.py`, `cim_reader.py` and ARM64 runtime setup scripts for processing the pinned official archive **locally**. Do not publish these vendor inputs to GitHub.

## Reproduce this checkpoint

```sh
make clean && make check
clang -std=c11 -Wall -Wextra -Werror -pedantic -O2 -Isrc \
  -o build/tests_optimizer_clang src/*.c tests/test_optimizer_boundary.c
./build/tests_optimizer_clang
clang -std=c11 -Wall -Wextra -Werror -pedantic -O1 -g \
  -fsanitize=address,undefined -fno-omit-frame-pointer -Isrc \
  -o build/tests_optimizer_clang_san src/*.c tests/test_optimizer_boundary.c
./build/tests_optimizer_clang_san
```

Private DNG regression (locally only):

```sh
python3 tests/test_private_optimizer_handoff.py \
  --private-dng /private/IMG_20261020_062344.dng \
  --report /private/private_replay.json
```

Private official firmware gate (locally only):

```sh
python3 tools/firmware_gate.py --package /private/X2DII_100C_v1_3_16_2.cim
python3 tools/firmware_gate.py --library /private/extracted/system/lib64/libaaa.so
# Optional downloading, only if required and network permitted:
python3 tools/firmware_gate.py --download-to /private/X2DII_100C_v1_3_16_2.cim
```

All verification outputs must retain **separate** `original_firmware_compared=false` and `produces_selected_neutral=false` status until an actual original ARM64 matched execution proves otherwise.

## Next genuine research stage

1. Restore verified official `.cim` and `libaaa.so` outside Git; reconstruct the valid initialized AWB context/config and 7-frame original comparison harness from preserved source + firmware.
2. Confirm true E2 field units, calibration, classifier, zone weighting and adjacency with byte-exact original stage/context comparisons.
3. Reimplement the **actual** scene optimizer arithmetic, temperature lookup and return-status branches; replace the supplied trace deltas with verified original caller updates. Rerun the historically recorded 256 optimizer / 512 temperature cases and seven-frame context comparisons.
4. Continue the prior history/atmosphere/CT/tint/post/outer estimator chain, including original selected-neutral provenance and fallback freshness. Do not transfer X2D sensor calibration into the phone sensor.
5. Finish signed/highlight-preserving RAW-to-linear, one-time WB, photographic HNCS colour rendering, then native Android validation.

Canonical GitHub branch: `mwilliams455/Hasselblad:recovery/awb-rebuild-20261021`. `main` remains untouched; the installed Native1C application (versionCode 27179) is not replaced by a downgrade. No new APK is supplied by this recovery checkpoint.