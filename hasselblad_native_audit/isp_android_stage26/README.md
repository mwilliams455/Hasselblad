# Stage 26 — guarded Android neutral colour-reference JNI

**22 October 2026 · HasselbladPhoton · firmware-first / no HNCS claim**

## What has been connected

- The Stage24 C11 engine (Stage18 DNG ForwardMatrix/AsShotNeutral camera-to-XYZ D50 and Stage19 XYZ D50 to **linear** sRGB or Display P3) is now part of the standalone app's **arm64-v8a** native build as `libhasselblad_colour_reference_jni.so`.
- The opt-in `HasselbladColourReferenceCheck` JNI accepts one 1–1024-pixel tile of **already-demosaiced, black-corrected camera-native linear RGB**, matching DNG matrices and neutral, and a selected gamut. It calls `HB24_PCS_ONLY` exclusively. The Stage21 MAIN hypothetical sampler is **never accessible through this JNI**.
- Fail-closed guards validate input/output lengths, nulls, in/out object aliases, profile compatibility, finite source values, gamut, chunk extent and Stage24 photographic-authorization flags. Ordinary errors leave caller output unchanged.
- An explicit development-screen button runs **synthetic** white, dark, headroom, sRGB/P3, full-tile and invalid-input checks. Host JNI parity executes the same Java class with the same C implementation outside Android. It does **not** read camera images, write files or change colour settings.
- The phone's existing Photon viewfinder, capture, photo processing, saved JPEG, and DNG writer remain untouched.

## Why this is not Hasselblad colour yet

This stage does **not** decode DNG, process its OpcodeList2, perform demosaic or lens shading correction, estimate scene AWB, adjust exposure, reconstruct original MAIN CCM/gamma/LUT pixel operations, emulate tone/atmosphere processing, render film curve or perform HDR/stacking. An app developer must not pass unverified linear samples, disconnected physical-sensor metadata or arbitrary DNG transforms and call the output camera-grade.

The JNI export exists for a future **opt-in, separately stored, provenance-verified diagnostic**, not for normal saved JPEG production. DNG ForwardMatrix camera-neutral conversion is a colourimetric reference independent of Hasselblad's manufacturer-specific colour rendering. `hb24_process` still retains negative and >1 light values until any separately chosen final output stage.

## Real-frame prerequisites

Before connecting actual RAW tiles, require: physical sensor ID + Camera2 frame/timestamp + source DNG hash binding; correct plane/Bayer sites and black/white levels; removal or implementation of DNG opcodes and shading metadata; proven demosaic path; valid matched native DNG ForwardMatrix, CameraCalibration, AnalogBalance and AsShotNeutral; source-linear precision and memory bounds; and reliable per-lens/illumination regression comparisons. Never enable on a different phone based solely on its model name.

## Firmware work continues separately

Stage25 verified 27 MAIN CCM parameter-name/driver-family joins and 16×6 signed `lmtx_fw` destination mapping in the exact X2D II 1.3.16.2 firmware. The authentic six-coefficient pixel equation, Q scale, selection/rounding/clipping, MAIN gamma pixel math and MAIN LUT grid/input space still need direct hardware-specific evidence or an oracle. No speculative 3×3 interpretation is compiled into the Android diagnostic.

## Files

- `HasselbladPhoton/app/src/main/cpp/hasselblad/hb_colour_reference_jni.c`
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladColourReferenceCheck.java`
- `HasselbladPhoton/app/src/main/cpp/CMakeLists.txt`
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDevelopmentActivity.java`
- `HasselbladPhoton/app/src/main/res/layout/activity_hasselblad_development.xml`
- `tests/Stage26BridgeSmoke.java`
- `.github/workflows/hb-photon-stage26-neutral-bridge.yml`

This branch deliberately retains the signed Stage8 27186 phone-tested rollback. Any successful new build must have a **larger** versionCode, unchanged application ID/signing certificate, correct ARM64 16KiB ELF alignment and a pass-only synthetic native receipt. The new neutral mode is **not** a default capture option and does not modify `main`.
