# Stage6 — bounded Bayer2Float GPU readback

**Status:** signed Stage6 27185 APK built and host-verified; GPU readback requires real-phone validation. This is NOT Hasselblad AWB acceptance, renderer colour, a calibrated HNCS profile, or GPU parity evidence.

## Purpose

Stage4 and Stage5 independently studied an RGGB RAW colour basis, using the Camera2 lens-shading map after float16 texture quantisation. They do not prove that the GPU receives or renders exactly that basis. Stage6 adds a **one-shot, user-armed observation** of the existing `Bayer2Float/tofloat` output, which is RGBA16F, after it has been drawn and before demosaic, tone mapping or JPEG encoding.

There are **16 spatially distributed 8 x 8 patches (1,024 pixels total)**. The probe reads only the output channel holding the Bayer pixel's value. It does not snapshot the full frame, reprocess a DNG on device, modify OpenGL shaders, apply white balance, or insert a second render pass. The probe preserves the GL read-framebuffer binding and pixel-pack state. Each result identifies the exact saved DNG SHA-256, physical sensor, RAW frame number and sensor timestamp before the GPU stage is entered.

## Opt-in test

1. Install Stage6 27185 over Domain3 27184 (same package and certificate).
2. Open **Hasselblad Development Check** and choose **Arm Stage6 GPU comparison for next RAW photo**. It is not the separate Domain1 grid button.
3. Return to the camera. Take one ordinary **4:3, RAW+JPEG** single-frame photo on a regular RGGB RAW camera; do not use 16:9 crop, quad mode, remosaic, software zoom, video, HDR burst or stacking. A simple, non-clipped neutral/pale surface is useful, but **not** a measured neutral reference.
4. Allow DNG/JPEG processing to finish. Reopen the development screen and choose **Copy Stage6 GPU report JSON**. Share that JSON **and the exact new matching DNG and .capture.json**; the report is a separate copy action, because the original sidecar is written before GPU rendering.
5. If the status is **skipped**, copy that JSON too. It gives a reason (unusable provenance, geometry, unsupported GL read format, etc.). Do not assume a skip means a colour error.

The Stage6 session is in-memory, for the current app process only. It is not a permanent stored image attachment. The capture is ordinary Photon processing except for the manually requested bounded readback.

## Source boundary

- `HasselbladStage6Contract.java` is independently testable. It defines 16 CFA-even-aligned patch rectangles and guards against unknown capture modes and invalid WB metadata.
- `HasselbladGpuStageProbe.java` implements arming, frame-bound sessions, GL state restoration, read-format fallback, base64 sample packing and status reporting.
- `HasselbladCaptureEvidence.stage6OriginalIdentity` publishes **only** the proven physical sensor/frame/timestamp plus the already saved DNG filename, byte count and SHA-256.
- `HdrxProcessor` assigns the session to its own `PostPipeline`; `Bayer2Float` samples only after the normal shader draw. The session never searches for an unverified global "current camera".
- No original `Converter.java`, `Parameters.java`, shader assets or colour calculations were modified.
- `hasselblad_native_audit/phone_input_20261021/stage6_gpu_reference/verify_stage6_gpu.py` verifies all identity and RAW/DNG checksums, patch layout and encoded samples, then evaluates a source-aligned CPU hypothesis. It retains separate upright/reversed-row hypotheses and excludes highlight reconstruction pixels.

## Verification

GitHub Actions `Hasselblad Stage6 GPU probe signed APK` succeeded for app source commit `608bb7ef61898f828836ac2d64d229d67cd1a42f`. The deterministic Stage6 ROI tests pass, existing Photon shaders and calibration files are unchanged against the Domain3 checkpoint, and the signed APK verification confirms:

- Application ID: `com.mwilliams.hasselbladphoton`
- Version: `0.1-hb-gpu6`, code `27185`
- APK SHA-256: `cc9973dcb69d6b952622866490cd8adc38b0d293e05a690ca278abef9e5f43a9`
- Native Scene1B and Domain1 diagnostic libraries remain packaged; native ELF 16 KB alignment is retained.
- Stage6 actual GPU on-device status: **not tested**.
- Stage6 CPU/GPU pixel parity: **not yet demonstrated**.

All real DNGs, JSON captures and sensor-specific derived figures stay in the private Library. Do not commit photographic pixels or private Camera2 sensor matrices to the public GitHub recovery branch.

## Immediate next decision

Use one returned Stage6 GPU report and its exact DNG/.capture.json to establish numerical GPU-versus-CPU agreement, determine raw-row coordinate ordering, quantify shader-gain and half-float error, and measure the readback time. Only then design labelled neutral/non-neutral reference tests for Stage4 acceptance. The full firmware-derived automatic controller and independent Hasselblad HNCS CCM/tone/LUT pipeline remain open.

Do not enable an automatic WB policy merely because 707/729 CT/tint points are representable or because many RAW blocks lie near that grid. For scene ambiguity and mixed illuminants the correct experimental response remains abstention.

**Repository:** `mwilliams455/Hasselblad` branch `recovery/awb-rebuild-20261021`. Keep `main` untouched.
