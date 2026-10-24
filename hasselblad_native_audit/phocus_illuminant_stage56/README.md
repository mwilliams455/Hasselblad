# Stage56: metadata-selected colour LUT

Saved-DNG previews previously used the profile's fixed diagnostic LUT temperature.
Stage56 adds an opt-in **Automatic colour** comparison. It estimates the DNG's
selected white point from ColorMatrix and AsShotNeutral metadata, rounds the
temperature using the recovered normal import rule, and interpolates the private
LUT data for that selection. The DNG camera-to-D50 transform, white balance,
prepared highlight input, colour core, film curve and Stage55 finishing stay fixed.
There are no parameters fitted to image pixels or to the retained photograph.

## Method and boundaries

1. Use the same selected metadata and CameraCalibration signature rule as the
   existing reader. Missing AnalogBalance defaults to unity and missing selected
   CameraCalibration defaults to identity.
2. Normalize each ColorMatrix using the public DNG SDK's D50/max-response rule
   and rounding to four decimal places. Interpolate calibration matrices in
   inverse Kelvin, clamped to their calibration illuminants.
3. Solve `XYZtoCamera = AnalogBalance * CameraCalibration * ColorMatrix` against
   AsShotNeutral, iterating white-point xy from D50. Require convergence in at most
   30 passes and a reconstructed neutral-ratio residual below `1e-7`.
4. Use the public Robertson temperature table. Its 124 numbers match the original
   native temperature table exactly. DNG tint is only a validity diagnostic;
   native tint uses a different interpolation and is not substituted for DNG WB.
5. Round integer Kelvin, then apply the existing native selection grid: 50 K to
   8000 K, 100 K to 10000 K, 1000 K to 20000 K and 5000 K to 50000 K. The colour
   LUT accepts 2000–10000 K. Its private anchor interpolation is linear in Kelvin,
   with the recovered endpoint extrapolation within that supported LUT range.

This estimates the **metadata white point**, not the physical lamp spectrum or
temperature. The display label reports the LUT step, not a new white-balance
setting. Existing manual previews remain available. Missing/invalid selector
metadata disables only the automatic comparison and records its reason.

The bounded route supports three-channel, single/dual-illuminant metadata and
equal selected CameraCalibration matrices, with CCT 1667–100000 K and DNG tint
within ±150. Three-illuminant metadata, singular matrices, unknown/duplicate dual
illuminants and failed convergence fall back. These bounds do not broaden the
existing RAW reader's compatibility; it still requires its supported ForwardMatrix,
calibration and preparation path. Nonpositive inferred XYZ is rejected.

`HB56LUT1` extends the private Stage55 data-only format with a version/count header
and three ordered temperature/grid records before its checksum. Earlier profiles
still load. Automatic profiles require normal model 0. No private grids, matrices,
photos, input hashes or original executable bytes are bundled or committed.

## Evidence

- 1440 synthetic metadata cases across eight camera encodings, temperatures and
  tints; independent scalar bisection reference, neutral rescaling, swapped anchor
  order, non-diagonal calibration and non-unity AnalogBalance.
- Nine synthetic DNG metadata fixtures cover selection, single illuminant,
  signature mismatch, SHORT neutral and unsupported/malformed optional metadata.
- Existing Stage42/43/48/54/55 regression and actual host JNI checks remain passing.
- 144 original-native temperature cases agree at integer Kelvin and selection;
  eleven LUT temperatures agree within `1e-12` for all grid entries.
- The private photograph is an execution fixture only. Its metadata solution is
  about 3566 K, selecting 3550 K; this replaces the prior 3050 K diagnostic anchor
  only in the new comparison. The manual colour and finishing outputs remain
  byte-identical. Full-frame colour agrees exactly with an independent trace;
  original-native samples also agree. See aggregate receipts in `evidence/stage56`.

These checks establish numerical behavior, not sensor-to-sensor colour equivalence.
Physical phone colour matching, the complete original RAW graph, lost headroom,
native live display and sharpness remain unvalidated or unported. Camera capture
still uses the existing Photon renderer. Stage56 needs its own phone smoke test.

## Reproduce

Public synthetic checks need Java 17, a C compiler and the dependencies pinned in
`.github/workflows/hb-photon-illuminant56.yml`:

```sh
python3 hasselblad_native_audit/phocus_illuminant_stage56/check_host56.py --work /tmp/hb56
```

`audit_native56.py`, `Stage56PrivateCheck.java` and `audit_preview56.py` accept
explicit private local inputs. Only their aggregate safe receipts may be published.
The original private APK is not a CI dependency.

## Public method references

- [Adobe DNG specification 1.7.1](https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf), printed pp.100–103.
- [DNG SDK colour specification](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_color_spec.cpp): neutral-to-xy iteration.
- [DNG SDK camera profile](https://android.googlesource.com/platform/external/dng_sdk/+/master/source/dng_camera_profile.cpp), blob `34a31057907907a87cc34f478d466d2c6cfc496b`: matrix normalization and illuminant anchors.
- [DNG SDK temperature](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_temperature.cpp), blob `47318abb306a231e04140ff57caee2d8a3b77b6c`: public Robertson table and temperature/tint geometry.

Implementation and independent tests were written for this project; the public
numerical table is used explicitly. No proprietary sensor calibration is in source.
