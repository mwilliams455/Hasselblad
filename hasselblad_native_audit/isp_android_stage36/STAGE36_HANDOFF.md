# HasselbladPhoton — Stage 36 verified signed dual-neutral real-DNG diagnostic

**Date:** 23 October 2026 (UK)
**Research repository:** https://github.com/mwilliams455/Hasselblad
**Branch:** `recovery/awb-rebuild-20261021`
**Verified Android build commit:** `949d7d935e4897e190bc08d8ce5f7a488534606a`
**Final successful CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39903851434
**Branch head after documentation:** `884673bc09787af573437897532c2d185a39fa00`
**Production `main`:** `929f523aa02ae5b224be39b9c36cce5975691a10` — unchanged.

## Proven facts before Stage36

1. Stage32: original 4096×3072 RGGB DNG, supported four `OpcodeList2` GainMaps, 1024 demosaiced camera-linear centre samples, Stage24 JNI PCS pass on a **real Android DNG**, read-only.
2. Stage33: original CaptureEvidence sidecar's saved-DNG hash, size, selected physical Camera2 frame number, sensor timestamp, single uncropped RAW_SENSOR frame and calibration evidence verified against independent Stage32 DNG read.
3. Stage34: **on-device direct tag evidence** shows saved DNG `AsShotNeutral` equals **Photon-effective** white balance **only**, not the original selected Camera2 neutral. The original and Photon neutral differ by `0.0029296875` in blue (0.84% relative) for that capture. DNG ForwardMatrix1/2 and CameraCalibration1/2 match both capture records. The saved photograph's pixels were not changed by the check.
4. Stage35: offline neutral-only Stage18/24 matrix sensitivity suggests −0.831% weighting of the blue input column for Photon-effective versus original neutral. This is a matrix effect, **not measured photographic colour error**.

## New signed APK

- Filename: `HasselbladPhoton-Stage36-27190-debug.apk`
- VersionCode: **27190**; versionName **`0.1-hb-dual36`**.
- Application package: `com.mwilliams.hasselbladphoton`.
- APK size: **70,919,918 bytes**.
- SHA256: **`4195998396bde52b3f6604c337797be8f49a38beee714d4e4129afd693e48d29`**.
- Same signing identity as Stage34/Stage26 checked in CI; arm64 JNI has 16 KiB LOAD segment alignment. In-place install over versionCode 27189 is expected.
- Photo capture, native photo processing, DNG writer, photographic shader path and saved JPEG rendering are unchanged. Stage34 rollback versionCode 27189 is preserved.

## Engineering implementation

New files:

- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDualNeutralMath36.java`: standalone, input-safe scene-linear 32×32 RGB numeric delta aggregator.
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDualNeutralDiagnostic36.java`: read-only SAF document diagnostic. Revalidates matching Stage32 and Stage34 pass reports, reopens both user-chosen source documents, independently hashes DNG bytes again, requires matched original Camera2 source record and exact DNG matrix equality, and only then invokes the same existing Stage26 native PCS-only JNI twice with the same DNG samples.
- `hasselblad_native_audit/isp_android_stage36/tests/Stage36MathSmoke.java`, `Stage36NativeDngSmoke.java`: synthetic bounded tests. No user photos or vendor assets included.
- Developer UI and layout add **Stage36: Compare Camera2 vs Photon white balance on real RAW** and **Copy Stage36 dual-neutral JSON**. Stage36 button is enabled only after existing Stage32 and Stage34 read-only checks pass in the current activity session.
- `.github/workflows/hb-photon-stage36-dual-neutral.yml` builds, verifies and publishes the signed upgrade. Earlier Stage34 workflow is frozen to its previously verified successful APK source and manual dispatch only.

Procedure: independently read and verify original DNG; use identical camera-linear 1024 RGB pixels, identical DNG ForwardMatrix/CameraCalibration/AnalogBalance, and invoke Stage24 `PCS_ONLY` JNI under **(a) original selected Camera2 neutral** and **(b) the verified DNG/Photon-effective neutral**. Calculate per-channel mean signed, mean absolute, RMS, p95 absolute and maximum absolute linear sRGB differences plus aggregate metrics and negative/over-one component counters. **No raw samples, original camera IDs, actual neutrals, matrices, DNG hash or original photographs are exported.**

The DNG is never edited. Temporary copies are deleted before PASS. The tested Stage34 original DNG has four GainMaps and matching profile pairs. Unknown variants fail closed. Stage36 requires proven distinct original/Photon neutrals and Photon-only DNG neutral origin, as established for this test case.

## Verification

[GitHub Actions run 39903851434](https://github.com/mwilliams455/Hasselblad/actions/runs/39903851434) — **SUCCESS**, including:

| Verification | Result |
|---|---|
| Stage36 bounded linear aggregator synthetic regression | **30 PASS** |
| Stage36 actual Stage26 native-JNI two-neutral synthetic DNG tiles | **16 PASS** |
| Stage26 synthetic native-colour bridge | **11/11 PASS** |
| Stage32 strict uncompressed DNG/GainMap parser | **25 PASS** |
| Stage34 neutral origin and matrix classification | **32 PASS** |
| Stage33 RAW/physical-sensor hash and frame provenance | **PASS** |
| Stage24 original native colour mathematical reference | **PASS** |
| Android build, signature, package/version, arm64 alignment, scope | **PASS** |

A synthetic test initially failed because its example RAW with GainMaps produced linear values above 1.0; since the native reference **must preserve** HDR headroom before display clipping, the test was corrected to assert preservation. The subsequent complete run passed. The original user DNG was never uploaded to CI.

**Real phone Stage36 diagnostic not yet performed**: signed build verification is not a measurement of a true real-file two-neutral difference.

## User phone test — no new photograph needed

1. Install Stage36 APK versionCode 27190 over Stage34 versionCode 27189, without uninstalling or clearing data.
2. Open **Hasselblad Development** → **Stage32: Pick existing DNG for neutral tile test**. Select the previously verified real DNG. Require `PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY`.
3. Press **Stage34: Pick matching capture JSON to verify DNG white balance**, select its matching original `.capture.json` file, require `PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED` and `MATCHES_PHOTON_EFFECTIVE_ONLY`.
4. Press **Stage36: Compare Camera2 vs Photon white balance on real RAW**, then **Copy Stage36 dual-neutral JSON** and paste it in ChatGPT.
5. Expected valid outcome: `PASS_BOUND_REAL_DNG_DUAL_NEUTRAL_LINEAR_TILE`, `same_RAW_tile_and_DNG_matrices_for_both_native_calls:true`, two native status codes `0`, and numeric aggregate differences. If a source or profile changed, report `NOT_PROVEN` rather than claim a match.

The Stage36 elapsed time includes two additional local DNG reads/sidecar checks and JNI calls. `native_two_passes_elapsed_ms` measures only the two bounded JNI calls. **Neither is full-frame photographic rendering latency**.

## Next technical work

- Analyse **real** Stage36 aggregate linear differences under the two original/Photon WB sources. Decide whether this warrants an optional original-Camera2 neutral DNG output setting in a later, separately validated build. Do not change default DNG/JPEG colour merely because the matrix sensitivity is nonzero.
- Validate full-frame tiled neutral colour against a trusted colour-managed DNG SDK conversion before enabling an optional photographic output; preserve source sensor and frame bindings.
- Continue the independent firmware-first X2D II colour arithmetic investigation. The real **Eagle2 MAIN CCM six-signed-coefficient pixel formula**, Q scale, channels, rounding, clipping, gamma and LUT samplers, calibrated Hasselblad AWB, and genuine HNCS pixel equivalence remain unproven. No arbitrary LUT is installed or declared equivalent.
