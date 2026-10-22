# Hasselblad Photon Stage4 — source-only verified checkpoint (22 October 2026)

**GitHub recovery branch:** `recovery/awb-rebuild-20261021`.
**Source verification commit:** `b5067661f6fd9d67550457cde199e57cb1253150`.
**CI run:** https://github.com/mwilliams455/Hasselblad/actions/runs/39730266907 — PASS.
**Installed APK:** Domain3 27184 (unchanged). **No Stage4 APK or photo-colour change.** `main` remains intentionally unchanged.

Stage4 introduces new owned C11 `hb_phone_neutral_observation` types and a typed bridge from existing `hb_phone_raw_grid` and `hb_phone_domain_result`. It records experimental neighbourhoods around only valid two-dimensional domain knots; rejects unbound frames, unsupported exposure/basis, clipped/brightness/green-site/signed-gain blocks; and measures bounded 32×32 true 8-neighbour spatial support. It always **ABSTAINS**: `render_permitted=0`, `calibrated_policy=0`; it contains no selected WB vector or HAL fit. The recovered original scene ABI is untouched. No invented spectral or X2D device calibration data were used.

**Completed verification:**
- Original, hash-paired private Domain3 RAW tested at four explicitly experimental comparison radii against independent Python/NumPy nearest-valid-knot and 8-neighbour component oracles: 4,096 block comparisons, zero mismatches.
- 14 malformed input / untouched-output checks and six synthetic abstention scenarios; separate AddressSanitizer and UBSan probes pass. Host GCC O0, GCC O2 and Clang output on the tested frame matched byte-for-byte.
- Typed bridge compiles against **actual** repository headers and passes synthetic positive/negative checks in hosted CI.
- Android API28 ARM64 native library cross-compiled using pinned NDK r27; three loadable segments satisfy 16 KB ELF alignment. This is **not** an Android-device execution test.
- Photon default shader source audit passes 14 static checks. `PostPipeline` uses `Bayer2Float`; its Bayer shader consumes mean-normalised Camera2 gain-map channels and divides RAW data by `whitePoint` before subsequent tone rendering. This is a **source contract**, not GPU parity or permission to insert another WB step. The RGB-layout and inpaint paths require separate validation.

The previous hypothetical full lens-shading and the new approximate shader-normalised shading calculations remain separate **private sensitivity experiments**, not saved-photo corrections or valid shipping WB policies. The source code and public aggregate test result have no original user pixels, complete Camera2 matrices or proprietary firmware calibration constants.

**Next bounded work:** establish shader-stage/GPU colour-basis parity and consistent one-time WB semantics, obtain controlled neutral and non-neutral reference scenes under documented illuminants and cameras/modes, validate hold-out abstention and false positives, complete the supported phone automatic-controller profile (exposure/spatial/history/absent spectral route), and separately complete HNCS per-pixel colour/tone pipeline research. Preserve RAW+JPEG and one-frame/no-HDR operation.

References: `STAGE4_NEUTRAL_OBSERVATION.md`, `STAGE4_PHOTON_COLOR_BASIS.md`, `STAGE4_PUBLIC_RESULT.json`, `STAGE4_ANDROID_ARM64_RESULT.json` and `STAGE4_PHOTON_COLOR_BOUNDARY_RESULT.json` in this directory. Use source checkout rather than reconstructing already verified Domain3 work.
