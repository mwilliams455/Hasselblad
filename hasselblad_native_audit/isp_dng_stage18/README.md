# Stage 18 — Portable DNG ForwardMatrix → CIE XYZ D50 bridge

**22 October 2026 · HasselbladPhoton · Research only**

## Why this stage exists

Stage17 isolated the X2D II 100C original firmware MAIN CCM tuning and original driver registers but did **not** recover the ISP's six-coefficient RGB pixel equation. The original camera's 16 CCM groups are equal in the examined global still profile and its four colour-temperature anchor groups differ. Those facts cannot authorize an assumed 3×3 transform.

A separate, necessary task for cross-phone portability is bringing each phone's native camera measurements into a common defined **profile-connection space (CIE XYZ D50)**. This stage implements only the bounded Adobe DNG `ForwardMatrix` route; it provides a usable mathematical adapter, *not* a Hasselblad ISP replica or HNCS look.

## Mathematical contract and upstream source

Source: publicly available **Adobe DNG SDK**, `dng_color_spec.cpp` (`SetWhiteXY`) and `dng_camera_profile.cpp` (`NormalizeForwardMatrix`). The DNG specification separately describes the camera-to-PCS calculation and `AnalogBalance`/`CameraCalibration` meaning. This implementation was authored independently and uses no Adobe SDK source or proprietary Hasselblad camera tables.

For a 3-channel camera, defining `AB = diag(AnalogBalance)`, `CC = CameraCalibration`, stored camera neutral `N = AsShotNeutral / max(AsShotNeutral)`, and `FM = ForwardMatrix`:

```
FM_normalized = diag(D50 / (FM*[1,1,1])) * FM
IndividualToReference = inv(AB*CC)
ReferenceNeutral = IndividualToReference * N
CameraToXYZ_D50 = FM_normalized * diag(1 / ReferenceNeutral)
                * IndividualToReference
```

D50 is the **ICC profile-connection-space** convention `[0.9642,1.0,0.8249]`, not another CIE D50 tabulation. The resulting matrix maps the neutral to D50. For a diagonal calibration matrix the calibration factors cancel in the final product; this is a property of the formula and does not license discarding arbitrary non-diagonal matrices.

**Scope limit versus complete Adobe SDK:** the stored `AsShotNeutral` is used as the bounded white-coordinate input; the full `NeutralToXY` iterative solver, colour-matrix/illuminant selection, profile calibration signature logic, SDK rounding and Adobe HSM/LookTable stages are *not* implemented. When `ForwardMatrix1 != ForwardMatrix2` or `CameraCalibration1 != CameraCalibration2`, the adapter rejects the input rather than guessing a temperature interpolation. A missing calibration matrix may be passed as NULL to request identity. No ColorMatrix-only branch is provided. This is a **reference sub-path with a known restricted domain**, not general DNG decoding.

Input to `hb_dng_pcs_apply` must already be **demosaiced linear camera RGB with black level and camera opcodes handled appropriately by the caller**. No Bayer/RAW reconstruction is performed by this module. Negative and high-headroom values are not clipped. No gamma curve, tone mapping, colour look or RGB-to-display conversion is performed.

## Code and tests

- `src/hb_dng_pcs_bridge.c/.h` — portable C11 forward-matrix numerical bridge; exact input lengths; refusal of invalid matrices, non-finite/zero neutrals, overlapping storage, and differing dual-illuminant forward/calibration matrices; transactionally preserves output on error. It has no sensor IDs, phone-specific defaults, firmware imports, JNI, camera or renderer calls.
- `tests/test_dng_pcs_bridge.py` — builds with GCC and Clang; verifies independent NumPy matrix results and camera neutral D50 response for 128 synthetic camera profiles × 512 probe pixels per compiler, including out-of-range linear samples; negative cases and buffer nonmutation checks.
- `tests/asan_bridge.c` — additional isolated ASan/UBSan-compatible smoke.
- `tests/dng_cfa_probe.py` — **diagnostic-only** RGGB bilinear reconstruction: 324 synthetic Bayer-centre checks; a separate private 1,024-location RAW sampling exercise feeds Stage18 C/NumPy conversion. It is not the Photon or Hasselblad demosaic and performs no saved-photo rendering.
- `.github/workflows/hb-isp-stage18-dng-pcs.yml` — synthetic-only hosted tests, production source protection, public metadata receipt.

Run locally:

```bash
python3 hasselblad_native_audit/isp_dng_stage18/tests/test_dng_pcs_bridge.py \
  --output /tmp/STAGE18_PUBLIC_TEST.json
```

### Original phone DNG metadata check (private only)

The original 4096×3072 Stage6/7 camera DNG was checked **locally** using `--private-dng` against this same C bridge and an independent NumPy reference. Its two ForwardMatrix values and two CameraCalibration values agree, so this restricted code path is applicable. The neutral maps to D50 within floating-point precision. The resulting camera matrix and per-capture hashes are retained **only** in the private handoff/Library, never GitHub.

This test confirms **numeric consistency with the DNG metadata**, not true scene colour or neutral calibration.

**Private actual pixel exercise:** 1,024 interior RGGB sampling locations from that original DNG were reconstructed with a simple independent bilinear CFA diagnostic; Stage18 C and NumPy XYZ results agreed to `1.11e-16`. Four resulting XYZ components were below zero, and all were preserved rather than clipped. This explicitly tests finite signed intermediate behaviour, **not** the original photographic reconstruction, corrected lens shading or a Hasselblad visual match. No pixel coordinates, XYZ samples, source hashes, or camera-calibration matrices are committed. The original phone's `AsShotNeutral` is still the Android HAL/Photon white point; Stage7's physically calibrated neutral policy still abstains. No X2D II camera colour transform, Film Curve or HNCS is inferred.

## Next photographic-colour gates

1. Obtain a verified ORIGINAL `MAIN_CCM` six-coefficient pixel formula or use an explicitly labelled empirical HNCS target, not a guessed formula.
2. Resolve ORIGINAL MAIN gamma evaluation, MAIN 3DLUT colour coordinates and interpolation, or evaluate a reference-image-trained replacement separately.
3. Connect a certified phone reference neutral and apply genuine illuminant/forward-matrix interpolation on devices requiring it. The fixed-forward-matrix fast path is device-neutral **but not universally available**.
4. Define a D50-to-Hasselblad target working-space mapping only with actual colourimetric evidence. Stage18 output is XYZ D50, not Hasselblad RAW colour.
5. Validate saved still single-frame processing, highlight headroom, output gamut/transfer, frame metadata, preview consistency and fallback before enabling photographic code in an APK.

**Production gate:** `photographic_render_authorized=false`. HasselbladPhoton app, `main` and current phone Stage8 build 27186 remain unchanged. Do not publish the original user DNG, its camera matrix, hashes, private scene content or vendor tuning payloads to public GitHub.
