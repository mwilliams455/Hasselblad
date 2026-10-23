# Stage 33 — bind the first real DNG colour test to original capture evidence

**Checkpoint:** 23 October 2026. Active branch: `recovery/awb-rebuild-20261021`. Baseline Android APK remains Stage32 versionCode **27188**. The app's capture and saved-JPEG pipelines were **not changed**.

## Result that motivated this stage

The user ran a **real** Stage32 `OpenDocument` DNG test on the phone and supplied a result with status `PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY`. That result verified:
- 4096×3072 RGGB uncompressed 16-bit DNG input, one RAW strip;
- four supported `OpcodeList2` GainMap records successfully applied to the centre neighbourhood;
- 32×32 = 1024 demosaiced camera-linear samples fed through the Stage24 neutral native bridge;
- native status **0**, no nonfinite/negative/>1 values on the tested centre tile;
- 102 ms for the **entire** bounded on-device diagnostic (not a full-frame benchmark);
- temporary local copy deleted, original DNG and saved JPEG unchanged.

**Private input withheld from GitHub:** the original user's DNG SHA-256, exact byte length, colour means/minima/maxima, filename, physical camera identities, raw pixels and original metadata values. The Stage32 privacy-safe evidence receipt is in `../isp_android_stage32/STAGE32_REAL_DNG_DEVICE_RECEIPT_20261023.json`.

## Why capture provenance remains the next hard gate

A user-selected DNG is not automatically bound to a Camera2 physical sensor, RAW ImageReader, frame number or sensor timestamp. Stage32 correctly returned both:
- `source_timestamp_is_camera_capture_timestamp: false`
- `physical_sensor_binding_proven: false`

These flags mean the **standalone picker did not establish provenance**; they do not mean the source photo is invalid.

The existing Photon capture path already writes a separately saved `<original-image>.capture.json` file through `HasselbladCaptureEvidence.finishRawSave`, including a SHA-256 of the actual saved DNG, capture frame identity, Camera2 sensor timestamp and physical sensor observations.

Stage33 adds `verify_capture_binding33.py`, a **local-only, metadata-only, fail-closed matcher**. It never loads or edits photographic pixels. Only when the Stage32 independently read DNG hash **and byte count** match the sidecar can it accept the capture context. It additionally requires the original capture's own calibration usable status, RAW/still pairing, physical camera matching, exact frame number and selected RAW sensor timestamp agreement, uncropped/unbinned original RAW geometry, CFA RGGB and RAW_SENSOR format.

The conclusion is **source-file provenance against app-recorded capture metadata**, not a hardware-signed sensor attestation and not proof that the observed phone rendering matches the X2D II firmware.

## How to validate the user's actual capture

Find the `.capture.json` file that was saved **beside the exact DNG selected in Stage32**, not a sidecar from another exposure. Keep both files and the Stage32 copied JSON in a **private** directory and run:

```sh
python3 hasselblad_native_audit/isp_android_stage33/verify_capture_binding33.py \
  --stage32-json /private/Stage32_phone_report.json \
  --capture-sidecar-json /private/matching_photo.capture.json \
  --output /private/Stage33_Binding_Result.json
```

A pass means `PASS_RECORDED_DNG_PHYSICAL_FRAME_BINDING`; a mismatch means `NOT_PROVEN` with a fixed reason code, and a nonzero exit status. No user file names, serials, hashes, camera IDs, timestamps, calibration arrays or pixels are copied to the resulting JSON. Do not put the private input files into public GitHub or CI.

**Status of real-file Stage33 verification:** not done; only the Stage32 summary was provided. The corresponding capture sidecar is still needed to assert a physical capture binding.

## Host checks

```sh
python3 -m unittest discover -s hasselblad_native_audit/isp_android_stage33/tests \
    -p test_capture_binding33.py -v
```

Synthetic suite: one valid matched sidecar and **25 negative corruption/identity tests**. CI:
[Stage33 host-provenance verification](https://github.com/mwilliams455/Hasselblad/actions/runs/39895559142).

No real/private CaptureEvidence JSON or RAW sample was included in tests or artifacts, and no new APK was built.

## Still unresolved

1. Stage32 supported GainMap interpolation is not proven Adobe SDK bit-exact, and the Stage24 RGB transform is not X2D II HNCS.
2. The original X2D II Eagle2 **six-coefficient MAIN CCM pixel equation**, Q scale, RGB order and clipping remain unproven; so do authentic MAIN gamma and LUT pixel operations.
3. Sensor calibration equivalence and matched exposure/white-balance control must be validated using real source pairs before future photographic accuracy claims.
4. A bounded wider-frame neutral diagnostic can come next, preferably with a colour-managed comparison/reference, without altering Photon capture or saved photographs.

Do not promote Stage32's 102 ms centre-test timing to a 12 MP render time, or interpret a centre tile's mean RGB components as a tested Hasselblad colour signature.
