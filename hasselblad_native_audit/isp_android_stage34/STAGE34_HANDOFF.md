# HasselbladPhoton Stage 34 — verified signed DNG AsShotNeutral provenance APK

**Checkpoint:** 23 October 2026 (UK)

**Recovery branch:** `recovery/awb-rebuild-20261021`, latest commit `e6cc4008e96e42cfe39250c682058ac91e3685ee`.
**Production main:** `929f523aa02ae5b224be39b9c36cce5975691a10`, unchanged.
**Signed APK source:** `6806fb50bdb87625dd77a3491a815649ff782245`.
**CI run:** https://github.com/mwilliams455/Hasselblad/actions/runs/39898510564 — completed SUCCESS.
**Artifact:** `HasselbladPhoton-Stage34-27189` (GitHub artifact ID `12477009287`).

## Completed

The user supplied a new Stage 32 actual-DNG centre-tile diagnostic and the corresponding original `.capture.json`. Stage 33 privately verified that the saved DNG hash, byte length, sensor timestamp, frame number, Camera2-selected physical camera and unmodified RAW_SENSOR copy geometry matched. The Stage 32 native neutral colour reference had passed on 1,024 real pixels; four supported DNG OpcodeList2 GainMaps were applied. The original DNG is not available in chat and its actual AsShotNeutral TIFF tag was **not** directly read.

A blue-neutral difference was found between the original Camera2 still result and the effective Photon export (about **0.002929688** absolute, **0.84%** relative); red and green neutrals and both ForwardMatrix/CameraCalibration pairs agree in this capture sidecar. Source inspection found `Camera2ApiAutoFix.ApplyRes()->whitePoint()` can substitute `SENSOR_NEUTRAL_COLOR_POINT` with preview neutral, while `DngCreator` uses `Parameters.whitePoint` for the DNG AsShotNeutral. This is a possible producer path, **not** yet proof of saved DNG tag values.

**Stage 34** adds read-only user-selected matching DNG/sidecar comparison to the development screen. It:

- Reuses an explicit Stage32 DNG selection that passed on the device; requests the matching `.capture.json` through a second system document picker.
- Streams and SHA-256 verifies the actual chosen DNG against **both** the successful Stage32 report and the saved capture sidecar, checks exact size and Camera2 recorded physical sensor/frame/timestamp/uncropped RAW identity.
- Reads actual DNG `AsShotNeutral` (and optional ForwardMatrix1/2, CameraCalibration1/2) using the pre-existing bounded Stage32 TIFF reader. No RAW images or actual neutral triplets are put into the reported JSON.
- Compares against original Camera2 and effective Photon records, classifying `MATCHES_PHOTON_EFFECTIVE_ONLY`, `MATCHES_ORIGINAL_CAMERA2_ONLY`, `MATCHES_BOTH_INDISTINGUISHABLE`, or `MATCHES_NEITHER`. Numeric tolerance: 0.00012 per neutral component, 0.0005 per matrix entry.
- Reports the match classifications and aggregate absolute differences only. No private DNG hash, camera ID, photo path, timestamps, raw pixel values or proprietary IQ values are exported.
- Uses a bounded app-private temporary copy and deletes it before success; source DNG, sidecar, saved RAW/JPEG, capture, AE/AWB and colour rendering remain untouched.

## Validation and APK

Host class comparisons: **32 synthetic checks PASS**. Stage32 DNG fixtures, Stage33 sensor binding tests, Stage26 JNI parity, Stage24 native numerical tests and all Android native build/signature checks passed in CI.

APK: `HasselbladPhoton-Stage34-27189-debug.apk`.
- Application ID: `com.mwilliams.hasselbladphoton`, unchanged.
- Version code **27189**, version name `0.1-hb-wb34`, upgrade from Stage32 `27188`.
- APK bytes **70,903,230**.
- SHA-256 **`0b43588dd4129200742b819800bbe8218575ba97f8226e5d856b0cb1bafb5590`**.
- Same signing certificate as Stage26/Stage32 checked in CI. Native arm64 library 16 KiB LOAD alignment verified.

No actual on-device Stage34 DNG-vs-sidecar matching report exists yet. The APK build is verified, not the photographic provenance result.

## What to test

1. Install Stage34 APK directly over Stage32 without removing user data.
2. Open the Hasselblad Development screen. Select **Stage32: Pick existing DNG for neutral tile test** and choose the DNG paired with the original `.capture.json`. It must return `PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY`.
3. Select **Stage34: Pick matching capture JSON to verify DNG white balance**; choose the original `.capture.json` saved next to that exact DNG.
4. Use **Copy Stage34 WB provenance report** and paste the generated JSON into the conversation. Check `status`, `DNG_AsShotNeutral_origin`, profile-matrix match classifications and `temporary_file_deleted`.

No new capture or photo export is needed if the matched DNG and sidecar remain on the phone. Do not upload the original DNG to public GitHub or publish its metadata sidecar in CI.

## Unresolved colour-science gates

The original X2D II firmware's 16 × 6 CCM register-coefficient groups have been identified, but the true Eagle2 pixel operation, fixed-point Q encoding, channel layout, rounding and clipping have **not** been proven. Original MAIN gamma and 3D LUT pixel semantics, calibrated Hasselblad AWB, HNCS rendering equivalence, full-frame phone rendering and face AF remain future work. Stage 34 is metadata provenance only and does not replace Photon saved JPEG rendering.

**Next:** analyse the Stage34 **real on-device** JSON before altering white-balance metadata. If the DNG AsShotNeutral matches the Photon effective neutral, assess an opt-in separately recorded original-Camera2 neutral for neutral/reference rendering, retaining Photon default behaviour; first validate a matched colour-managed image and the expected DNG metadata. If it matches neither source, investigate DNG writer rational encoding and HAL mutators. Continue firmware-equivalent original pixel equation recovery in parallel.
