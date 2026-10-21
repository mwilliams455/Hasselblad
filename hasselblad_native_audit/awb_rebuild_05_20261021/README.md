# Hasselblad Photon — AWB Lost Stages Rebuild 05

**2026-10-21 — bounded, independently tested reconstruction checkpoint.**

## What was reconstructed

This checkpoint extends the complete Rebuild 04 source with a C **seven-frame result lifecycle journal**, an independent Python full-context oracle, and a seven-frame original-vs-owned snapshot comparator. All work is strictly downstream of the *recorded* AWB final-copy/outer-result evidence; it is not a recovered numerical scene optimizer.

- `src/hb_awb_lifecycle.{c,h}`: transactional, monotonic frame-journal around the historical final result publication, confirmed restoration and reference-override gates. Distinguishes inner statuses **40 and 151** from the possible final outer return **0**. It never promotes outer `0` into a fresh AWB estimate claim. It checks and preserves the entire passive **1000-byte REAWB handle** and the **920560-byte context** boundary.
- `tests/test_lifecycle.c`: **16,107 assertions / 700 complete synthetic frames** with exact whole-context comparisons and invalid-operation checks. GCC and Clang optimized and ASan/UBSan execution passed.
- `tests/test_lifecycle_python.py`: **144 synthetic full-context frames** compared against a separate Python branch-by-branch model.
- `tools/seven_frame_compare.py`: strict 7-frame per-stage comparison of context/REAWB/return status; **never runs original vendor code**. Synthetic and original_arm64 modes are separate. Original mode refuses execution without the **actual pinned SHA-256-matching** `libaaa.so`, explicit same-execution assertion, and valid private snapshots. Even matching snapshots are not proof of original scene-estimation provenance.
- `tests/test_evidence_gate.py`: **12 synthetic positive/negative fixture checks**, including deliberate context mutation, handle mutation, status difference, out-of-order frames, missing frame, missing/wrong vendor ELF and unsafe path.
- `evidence/SCENE_SYMBOL_MAP.json`: **39 exact recorded function addresses/sizes**, extracted from the preserved Native1A `colour_audit/inventory.json`, which pins the expected original ELF SHA. This is *historic source-backed symbol metadata*, not fresh ELF execution. Example: `scene_awb_scene_opt` **0x4a8c48, 1452 bytes**; weighting **0x4a7d00, 2120 bytes**; filtering **0x4a8548, 852 bytes**; scene controller **0x4a7560, 1948 bytes**.
- `tools/export_scene_symbol_map.py` and `tests/test_symbol_map.py`: reproducible index extraction and **8 negative/positive controls**. The full original inventory is in the separately preserved Native1A ZIP, not copied here.

## Tested boundaries

- `make check`: exit status 0, including all inherited Rebuild01–04 checks plus the new C/independent Python/evidence-integrity checks. Output: `evidence/check_stdout.txt`.
- Additional Clang optimized and Clang ASan/UBSan tests: passed the same **16,107** lifecycle assertions each.
- Native1C DNG replay against the inherited RAW → candidate/trace scaffold: **1024 blocks checked**, synthetic mask yielded 320 surviving blocks, no original AWB result/neutral; private full capture not shipped in this ZIP. See `evidence/PRIVATE_REPLAY_SUMMARY.json` for summary only.

## Crucial nonclaims

- `libaaa.so` original binary and seven-frame original harness were **not** recovered here. Original arm64 comparison **not run**.
- Real X2D E2 calibration, classification, scene weight arithmetic, optimizer numerical operation, temperature tables, live history policy, atmosphere correction, CT/tint matrices and full post-processing **remain unimplemented** in source.
- The new journal is an **owned contract** designed from the historical conversation; it is not a same-execution original-vendor match.
- No original AWB neutral is generated, no white balance is applied to saved images, and no new APK is built.
- Public GitHub never receives firmware, vendor libraries, proprietary LUTs, private photos, full sidecars or APK binaries.

## Next actual firmware work

1. Obtain the official X2D II firmware 1.3.16.2 privately, verify its expected **364814336 bytes** and SHA-256 **9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6**, then extract and rehash `libaaa.so`: **7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba**.
2. Recover the original Android 9 ARM64/QEMU runtime, initialized 920560-byte context and 1502800-byte config, authentic original E2 frame and statistics ABI and 7-frame same-execution comparison.
3. Reimplement from actual original instruction/ABI evidence the numerical weighting/filter/optimizer (`scene_awb_scene_opt` 0x4a8c48), temperature tables, and post-return caller count updates. Do not replace missing equations with synthetic test coefficients.
4. Rebuild history, atmosphere, calibrated CT/tint, result publication, smoothing, REAWB and outer completion until the original seven-frame comparison passes.
5. Only then integrate a justified phone calibration, clean RAW-to-linear, one-time WB and ultimately HNCS saved-photo renderer.

Canonical source branch is `recovery/awb-rebuild-20261021`. `main` must remain unchanged. Native1C versionCode 27179 remains installed; no downgrade.

## Build / test

```
make clean && make check
clang -std=c11 -Wall -Wextra -Werror -pedantic -O1 -g \
    -fsanitize=address,undefined -fno-omit-frame-pointer -Isrc \
    -o build/tests_lifecycle_clang_san src/*.c tests/test_lifecycle.c
./build/tests_lifecycle_clang_san
python3 tools/export_scene_symbol_map.py --inventory /private/Native1A/hasselblad_native_audit/colour_audit/inventory.json \
    --out /private/preserved_index.json
python3 tools/seven_frame_compare.py --manifest /private/frames/manifest.json \
    --private-root /private/frames --vendor-lib /private/extracted/system/lib64/libaaa.so
```

The last command requires a privately verified ELF and real same-execution snapshot evidence; running it with the current source archive alone intentionally fails closed.