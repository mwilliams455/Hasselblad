# Stage 34 — Real DNG AsShotNeutral versus original Camera2 and Photon export

**23 October 2026 — HasselbladPhoton research branch only.**

Stage33 matched a user-selected 12 MP DNG by exact SHA-256 and byte length
to its original `.capture.json`. The capture sidecar proved app-recorded
physical Camera2 sensor identity, RAW ImageReader request binding, single
frame number, sensor timestamp, uncropped RGGB RAW_SENSOR geometry and
usable sensor characteristics. It was recorded under Stage26 and was later
read successfully on-device by Stage32 (native Stage24 PCS-only 1024-pixel
center tile, four DNG OpcodeList2 GainMaps).

The original selected Camera2 sensor neutral **differs in one component**
from `effective_photon_export.neutral_used`. The original and effective
ForwardMatrix and CameraCalibration fields agree. Source review recovered
the path `Camera2ApiAutoFix.ApplyRes() -> whitePoint() -> SENSOR_NEUTRAL_COLOR_POINT`
and `DngCreator.setAsShotNeutral(parameters.whitePoint)`. **That is a
possible writer path, not proof of the exact saved DNG tag contents.**

Stage34 adds an **on-device, read-only comparison** to answer the missing
question with the original DNG bytes themselves.

## Android test flow

Install signed Stage34 APK versionCode **27189** over Stage32 **27188**
without uninstalling. On the **Hasselblad Development** screen:

1. Select **Stage32: Pick existing DNG for neutral tile test** and choose
   the previously saved DNG which has a matching `.capture.json`.
   Stage32 must complete with `PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY`.
2. Select **Stage34: Pick matching capture JSON to verify DNG white balance**.
   Choose the `.capture.json` saved next to **that same DNG**. This picker
   is enabled only following the successful Stage32 DNG import.
3. Select **Copy Stage34 WB provenance report** and share the JSON, not
   the original DNG.

Stage34 independently streams and SHA-256-hashes the same chosen DNG,
verifies the length against the Stage32 report and the original
CaptureEvidence sidecar, validates the app-recorded Camera2 physical sensor,
frame, timestamp, CFA and uncropped RAW geometry, and reads the **actual DNG
AsShotNeutral and calibration/ForwardMatrix tags** using the pre-existing
strict bounded DNG reader. The DNG remains unchanged. No saved JPEG, preview,
camera AE/AWB, shutter or ISP code is changed.

## What the result means

The report contains `DNG_AsShotNeutral_origin`, classified as one of:

- `MATCHES_ORIGINAL_CAMERA2_ONLY`
- `MATCHES_PHOTON_EFFECTIVE_ONLY`
- `MATCHES_BOTH_INDISTINGUISHABLE`
- `MATCHES_NEITHER`

It separately reports whether DNG ForwardMatrix1/2 and
CameraCalibration1/2 match the original Camera2 or Photon export. Missing
matrix tags are distinguished from identity; unknown or unsupported DNG
profiles fail closed.

Numeric comparison uses absolute tolerance **0.00012 per neutral component**
and **0.0005 per matrix entry**, sufficient to guard routine rational
rounding but **not** asserted DNG-SDK bit-exact equality. If both sources
are too close to distinguish, it will say so.

The selected DNG remains in an app-private temporary cache only for
bounded random-access reads. The `.capture.json` is read from the
system document picker with a 4 MiB bound. The JSON result **never exports**
the original hash, RAW pixel samples, sensor ID, timestamps, neutral triples,
camera matrices, file paths, or private vendor assets. Only categorical
matches and aggregate maximum absolute differences are emitted.
Temporary copies must be deleted; an unsuccessful deletion refuses PASS.

**Only an on-device real-file Stage34 JSON can prove which actual DNG
neutral was stored.** Host checks and successful APK signing do not.

## Synthetic host regression

```bash
javac --release 17 -d /tmp/hb-stage34-classes \
  HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladNeutralCompare34.java \
  hasselblad_native_audit/isp_android_stage34/tests/Stage34NeutralSmoke.java
java -cp /tmp/hb-stage34-classes \
  com.particlesdevs.photoncamera.hasselblad.Stage34NeutralSmoke
```

The synthetic suite has 32 checks for original-only, Photon-only, both,
neither, boundary tolerance, nonfinite invalid inputs, and matrix tag
comparisons. Stage34 CI reruns the Stage32 DNG fixture tests, Stage33
capture pairing tests, Stage26 JNI synthetic tests and Stage24 native
colour mathematics before signing and publishing the Android upgrade.

## Hard photographic limits

- Stage34 does **not** assert DNG SDK bit-exact GainMap or profile arithmetic.
- Stage24 remains a neutral DNG PCS reference, **not** a port of HNCS.
- The original X2D II Eagle2 MAIN CCM six-coefficient pixel equation, Q scale,
  channel order, gamma interpolation and native MAIN LUT sampler remain unknown.
- Actual saved JPEG output remains Photon; no new photographic renderer,
  AWB controller, camera focus or full-frame colour has been enabled.
- The production `main` branch is preserved; development stays on
  `recovery/awb-rebuild-20261021`.
