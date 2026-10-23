# Stage 35 — quantify original Camera2 vs Photon-effective DNG neutral sensitivity

**23 October 2026 | Reference-only, no Android rendering changes.**

## Grounded on-device finding

The user has completed Stage34 with status `PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED`.
The DNG hash and app-recorded Camera2 physical-sensor/frame/timestamp matched.
The original DNG `AsShotNeutral` tag **matches the Photon-effective neutral
only**, *not* the original selected Camera2 sensor neutral.
Both DNG ForwardMatrix and CameraCalibration pairs matched original/effective
records. Stage34 did **not** render HNCS; saved JPEG colour remains Photon.

The first actual source was captured under Stage26 and re-read by Stage32/34.
Its original and effective neutral differ only in the blue component by
`0.0029296875`, approximately 0.84% of the original blue neutral.
The Stage34 on-device evidence is preserved without source DNG, hash, camera ID
or original matrix values in
`../isp_android_stage34/STAGE34_REAL_DEVICE_WB_PROVENANCE_PASS_20261023.json`.

## Stage 35 local differential

`neutral_sensitivity35.py` compares the Stage18/24 **neutral PCS mathematical
reference** under two neutral inputs while keeping both original and effective
ForwardMatrix and CameraCalibration data otherwise identical.
It reproduces the **validated single-profile DNG ForwardMatrix**
normalization-to-D50, the inverse of AnalogBalance × CameraCalibration and
the camera-neutral reference-white diagonal conversion.

The chosen frame's private, local numerical analysis found:

- Effective versus original **camera-to-D50 blue input column scale**
  `0.9916897506925207` (about **−0.831%**).
- Red and green input columns unchanged (matrix-element difference 0).
- Overall camera-to-D50 matrix Frobenius relative change about **0.781%**.
- Each corresponding neutral still maps to D50 as designed.

These are **mathematical matrix sensitivities**, not measured pixel/image
difference, visual colour difference, ΔE or a recovered Hasselblad transform.
An identity AnalogBalance is assumed, as in the Stage24 bridge default,
because the independent DNG `AnalogBalance` tag was not included in the
provided Stage34 report. The original camera ForwardMatrix and
CameraCalibration were confirmed matching, and they were used only in private
memory. More general non-diagonal AnalogBalance or a different calibrated
profile would require a new, separately validated run. No underlying
calibration matrices, lens-shading gains, DNG SHA-256, source IDs or pixel
values were committed.

Source evidence for Photon's setter:
- `Camera2ApiAutoFix.ApplyRes()` calls `whitePoint()`, which writes
  `SENSOR_NEUTRAL_COLOR_POINT` from `CaptureController.mPreviewTemp`.
- `Parameters.ReCalcColor` computes `whitePoint` based on a capture result.
- `DngCreator.setParameters` calls
  `setAsShotNeutral(toDouble(parameters.whitePoint))`.
The specific stored DNG value was verified by Stage34, not merely inferred
from these setter names.

## Reproduction (private input only)

```bash
python3 hasselblad_native_audit/isp_android_stage35/neutral_sensitivity35.py \
  --capture-sidecar /private/matched_original_photo.capture.json \
  --output /private/STAGE35_SENSITIVITY.json
```

Never upload real user sidecars or original matrices to a public repository or
Actions artifacts. This tool emits only bounded scalar matrix-sensitivity
numbers and explicit non-equivalence status flags. Its report should remain
private unless individually reviewed.

Run eight independent synthetic tests without any user files:

```bash
python3 -m unittest discover \
  -s hasselblad_native_audit/isp_android_stage35/tests \
  -p test_neutral_sensitivity35.py -v
```

## Engineering decision

Do **not** silently overwrite either the existing Photon saved DNG or the
saved-JPEG colour. In a future Stage36 developer-only analysis we can evaluate
both (a) original selected Camera2 neutral and (b) Photon-effective neutral
against **the same bound DNG camera-linear tile**. The existing Stage26 JNI
accepts 1024 camera-linear samples; it must receive independently validated
metadata and never be called from the ordinary shutter/save path.

The actual goal still includes a firmware-equivalent X2D II MAIN CCM,
gamma/LUT and colour-rendering reconstruction. The signed16 six-coefficient
pixel equation, Q scale, channel order, rounding, clipping and HNCS pixel
equivalence remain unproven. A WB-metadata correction does not solve them.

Production `main` remains unchanged; last Stage34 signed test APK
`27189` remains the installed baseline, with no Stage35 APK.
