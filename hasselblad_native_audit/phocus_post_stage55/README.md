# Stage55 — bounded native CPU finishing

The saved-DNG comparison gains a fourth view: Stage54 prepared-RGB highlight
reconstruction and verified colour/film, followed by default SDR gradation and
an explicit native CPU sRGB output route. No coefficients are fitted to a scene.
Old profiles retain their three views. New profiles retain the same colour/LUT/
film payload and old display adapter, with a separate data-only output extension.
Capture processing is unchanged.

## Recovered ordering and scope

The original SDR import sets processing tool version 4. Executing its HNCS graph
builder selects gradation version 1. The recorded order is colour, film,
gradation, sharpening, output. Graph ownership and sharpening construction are
fixtures in this audit; sharpening has not been ported.

The selected gradation has identity contrast and luma user tables, two luma
points, and a common RGB curve. All 65,536 curve entries are reconstructed from
endpoint normalization. Version 1 also performs a hue-preserving HSL round trip;
float-rounded fractional constants promoted to double, explicit fused operations,
float stores, ratio multiplication and final truncation matter at one-code scale.
The implementation is limited to these unedited SDR defaults.

Output uses the original `CCustomCMM` CPU special-profile 0 to special-profile 2
route, including 65,535 input normalization, float decode/matrix stores and uint16
rounding. Output matrix and power exponent are private profile data. The Android
live graph instead requests D50-adapted P3 linear output; its final surface and
compositor are still unverified. This CPU sRGB reference does not reproduce that
live display chain or establish full Phocus equivalence.

## Profile extension

`HB55LUT1` keeps the Stage43 header and payload, then appends 96 bytes before the
SHA-256 checksum: four little-endian integers (extension 1, source profile 0,
destination profile 2, gradation version 1), nine doubles for the output matrix,
and one double for the decode exponent. The checksum covers the entire preceding
file. Unsupported routes, nonfinite/out-of-range values and length/checksum errors
are rejected before saving. `HB43LUT1` remains supported. No private profile,
recovered vendor table/matrix, original binary or photograph is bundled in source,
CI or APK.

## Validation

- `check_host55.py` builds the actual Java/JNI bridge and runs previous Stage42,
  Stage43, Stage48 and Stage54 synthetic regressions plus Stage55 numeric, profile
  compatibility and malformed-input checks. It requires Java 17, GCC and JNI headers.
- `audit_post55.py` runs original routines from a separately supplied private APK.
  It binds the actual SDR-import gradation flag, compares synthetic colours/ramps,
  and optionally measures retained private Stage54 arrays. It creates the private
  profile extension locally; only its aggregate receipt is public.
- `Stage55PrivateCheck` verifies all preview RGB16 channels through the actual JNI
  against the separately executed C path. The full prior preparation, colour and
  legacy display arrays must remain byte-identical when loading the extended profile.

The preview still uses a bilinear, clipped, post-gainmap prepared RGB16 input.
Sensor calibration equivalence, original raw headroom/demosaicing, sharpening,
GPU/display equivalence and phone pixel equivalence remain unverified. Manual LUT
temperature is preserved; this stage does not infer an illuminant or fit a look.
