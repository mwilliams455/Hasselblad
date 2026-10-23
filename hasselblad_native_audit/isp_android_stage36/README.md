# HasselbladPhoton Stage36 — same RAW, two neutral sources, native PCS-only

**Date:** 23 October 2026. **Branch:** `recovery/awb-rebuild-20261021`.
**Android intended APK:** versionCode `27190`, `0.1-hb-dual36`, package `com.mwilliams.hasselbladphoton`.
**Production `main` and photographic JPEG/RAW save:** unchanged.

## Motivating evidence

- Stage32 processed a real user-selected Xiaomi DNG: RGGB 4096×3072, four OpcodeList2 GainMaps, 1024 centre camera-linear pixels, native Stage24 JNI status 0.
- Stage33 privately matched the independently read DNG SHA256, file size, original RAW_SENSOR frame number, physical Camera2 ID, selected still sensor timestamp, uncropped RAW copy and required calibration metadata to a previously saved `.capture.json`.
- Stage34 directly read the original DNG `AsShotNeutral`. It equals Photon-effective values and differs from the original Camera2 result (blue by +0.0029296875). The DNG ForwardMatrix1/2 and CameraCalibration1/2 match both sidecar sources.
- Stage35 compared the single-profile DNG camera-to-PCS transform under both neutral inputs; the input blue-column weighting differs by approximately −0.831%, with otherwise matching column inputs. This is **matrix sensitivity**, not an image measurement or colour fidelity score.

## What Stage36 actually implements

An additional development-screen button **Stage36: Compare Camera2 vs Photon white balance on real RAW** is enabled after two explicit user choices in the same screen session:

1. **Stage32** select the original DNG and reach `PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY`.
2. **Stage34** select that DNG's matching `.capture.json` and reach `PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED`.
3. **Stage36** press the comparison button; no new file picker or photograph is needed. It independently reruns Stage34's strict DNG/hash/frame/physical-camera validation; rereads exactly the same chosen DNG into an app-private temporary file, verifies SHA256 and byte count against both receipts and checks matrix consistency.

Stage36 uses **the same** 34×34 RAW neighbourhood and corrected 32×32 (1024-pixel) demosaiced camera-linear RGB tile from Stage32's strict DNG reader. It calls the existing original Stage26 JNI twice, with the same DNG ForwardMatrix1/2, CameraCalibration1/2, AnalogBalance and input array:

- Pass A: original selected Camera2 `android.sensor.neutralColorPoint` from the verified capture sidecar.
- Pass B: DNG `AsShotNeutral`, independently verified to match the Photon-effective neutral by Stage34.

Both native calls must succeed with `hb24_process` **PCS_ONLY**; dual-illuminant or other unsupported profiles fail closed. No camera pipeline hook, saved DNG/JPEG edit, preview renderer, firmware CCM, HNCS or LUT invocation is implemented.

The copyable **Stage36 dual-neutral JSON** reports categorical proof flags, mean linear sRGB for each pass, per-channel mean signed and absolute differences, RMS differences, P95 absolute differences, maximum component differences, over-unity/negative output counts and the two-native-pass duration. Only aggregated numeric statistics leave private memory; **no private camera ID, actual neutral triple, DNG SHA256, sidecar path, image pixel list, colour matrix or proprietary firmware contents are exported**.

## Important caveats

- An original Camera2 neutral does not automatically mean a more accurate colour rendering, and the stored Photon-effective neutral is not established as wrong for every scene. This tests *sensitivity* to one metadata choice, not which white balance is preferable.
- Output is linear sRGB from the Stage24 DNG-PCS mathematical reference. Difference metrics are **not** ΔE, perceptual fidelity, JPEG appearance, original X2D II MAIN CCM, true HNCS nor full-frame rendering quality.
- The two passes process only **1024 pixels**. Timing includes JNI round trips; no claims about 12 MP throughput.
- The original DNG was not supplied to the development repository or GitHub CI, so true device execution remains unverified until the Stage36 report is sent back.
- Stage36 intentionally requires the original and effective neutrals to be distinct and the DNG AsShotNeutral to match **Photon effective only**, as established for the current real sample. A different input configuration reports `NOT_PROVEN` rather than guesses.
- Stage34's verified comparison uses strict numerical tolerances for profile tags; Stage36 requires the four relevant matrix tags to match both reference sources.
- The normal Photon DNG colour metadata and saved JPEG remain unchanged, and the signed Stage34 version `27189` remains a rollback baseline.

## Host checks

`HasselbladDualNeutralMath36` is Android-independent and has 30 synthetic bounded array tests, including nonfinite/alias rejection, nearest-rank P95 and original-site preservation. `Stage36NativeDngSmoke` feeds a synthetic GainMap-corrected DNG tile to the **actual** Stage26 JNI twice and checks detectable native delta, deterministic same-neutral output, unclipped highlight values, reject-on-mismatched dual profile, and unchanged RAW input.

Stage36 CI also reruns Stage26 JNI 11/11, Stage32 25 synthetic DNG checks, Stage34 32 matrix-source checks, Stage33 capture-to-sidecar regression and Stage24 native colour numerics. The APK verification checks prior signing identity, app package, version and 16 KiB native ELF load alignment. Real images and camera metadata must **never** be sent to GitHub Actions.

## Genuine X2D II work remains blocked

The exact Eagle2 MAIN CCM six-coefficient pixel formula, Q scale, RGB order, rounding, clipping, gamma and LUT pixel sampling are not recovered, and sensor-dependent HNCS calibration remains unverified. Stage36 solves none of these. Continue firmware-based recovery separately, without guessing a 3×3 colour matrix or installing a third-party appearance LUT as a firmware substitute.
