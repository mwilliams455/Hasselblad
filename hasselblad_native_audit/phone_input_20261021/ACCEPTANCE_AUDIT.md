# Phone neutral acceptance audit — 21 October 2026

The Scene1B device capture already proved that the diagnostic runs on the phone
and matches an offline Java/JNI replay. This audit investigates its restrictive
acceptance settings. It changes no native runtime, app, policy default or
photographic rendering. Keep the validated Scene1B build installed.

## Findings

The existing phone sweep tests six radii around the same **zero-tint** locus.
It does not test a temperature/tint region. A block outside that curve's narrow
bands is rejected even if another representable tint curve passes nearby.
Capture-specific distances and interpretations remain in the private evidence.
An inverted HAL neutral is a reference comparison, not ground-truth lighting
or an independently estimated neutral.

The native matrix/gain calculation matches an independent NumPy float64 oracle
over all tested points. The matrix direction and multiplication order agree
with Camera2: the color transform maps XYZ to reference sensor space, and the
calibration transform maps reference sensor space to actual sensor space, so
the product is `calibration @ color`. The AOSP DNG implementation likewise
interpolates endpoint products in reciprocal temperature. No numerical matrix
or gain-normalization correction was identified by this audit. This verifies
the implementation of the declared model, not the physical accuracy of a
phone's supplied calibration.

The constructor also requires **all 81 temperature points** to fit its positive
signed-16-bit scene-gain domain. Some test tint curves have a representable
middle range but fail construction because of their low-temperature tail.
The audit records each point's status and explores distance to valid points;
that exploration does not call the native candidate filter or optimizer and
must not be described as a working alternative native policy.

A separate sensitivity replay applies the original Camera2 lens-shading map
bilinearly before block averaging. It uses original active-array pixel
coordinates and keeps the original eligibility decisions. Camera2 green map
channels follow even/odd sensor rows; the owned grid follows the red/blue rows,
so their mapping is tested for all four Bayer layouts. Lens shading alone does
not remove the latest capture's narrow-policy rejection. This is an offline
sensitivity calculation, not a recommendation to apply shading twice or a
change to the renderer or RAW input contract.

## Fresh checks

- Three hash-bound original capture replays; 3,072 independent RAW block checks.
- 2,187 independent matrix/gain checks: 9 tint values × 81 temperatures × 3 captures.
- 108 successful native policy runs and 54 explained model-construction rejections.
- Six exact comparisons with the policies saved by the Scene1B phone capture.
- Four analytic spatial-interpolation checks and four Bayer/map-channel checks.

`ACCEPTANCE_AUDIT_RESULT.json` contains aggregate counts and source hashes.
`Hasselblad_Acceptance_Audit_PRIVATE_20261021.zip` contains all capture-derived
measurements, per-point coverage, the plot and the run log. No original capture
pixels, sensor matrices or derived capture ratios are included in this public
checkpoint. This audit uses owned code and public conventions; it is not a new
original-firmware parity run or an Android performance measurement.

## Reproduce

With host `cc`, Python, NumPy and optionally Matplotlib, provide a private JSON
array with `label`, `capture` and `dng` absolute paths for each input. The DNG
filename and hash must match the original capture record.

```sh
python3 hasselblad_native_audit/phone_input_20261021/audit_phone_acceptance.py \
  --manifest /private/capture-manifest.json \
  --out /private/acceptance-audit \
  --public-report /private/aggregate-result.json --plot
```

The shading calculation deliberately supports only the bound full active-array
layout with both active-array rectangles equal to the RAW buffer extent.
Unknown spatial transforms reject rather than guessing a map placement.

## Next implementation boundary

Define a bounded diagnostic representation of the valid temperature/tint region
with explicit domain exclusions. Preserve the existing 81-point ABI and its
rejection behavior unless introducing and testing a separate explicit API.
Do not silently skip points, clip gains, widen radii or fit tint from HAL to
manufacture a candidate. Confirm the target's actual surface color and lighting
before interpreting any fit as neutral-target calibration. Neither a shifted
test curve nor acceptance of one image establishes a shipping AWB policy.

Full automatic phone initialization/profile, photographic WB acceptance and
the saved-photo HNCS per-pixel renderer remain open. No new APK is needed for
this audit; Photon continues to render the photographs.

## Primary convention references

- [CameraCharacteristics](https://developer.android.com/reference/android/hardware/camera2/CameraCharacteristics): sensor color and calibration transform directions.
- [AOSP DNG color specification](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_color_spec.cpp): endpoint products and reciprocal-temperature interpolation.
- [CaptureResult](https://developer.android.com/reference/android/hardware/camera2/CaptureResult): remaining RAW shading correction and full active-array map coordinates.
- [LensShadingMap](https://developer.android.com/reference/android/hardware/camera2/params/LensShadingMap): bilinear map and even/odd sensor-row green channels.
