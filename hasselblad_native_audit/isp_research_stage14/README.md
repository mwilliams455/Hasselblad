# HasselbladPhoton Stage 14 — bounded software ISP research core

**22 October 2026 · X2D II 100C firmware 1.3.16.2 · source-only host research**

This checkpoint begins the portable replacement of the *relevant mathematical operations* of the Hasselblad X2D II ISP, instead of attempting to install its proprietary driver, use the X2D sensor calibration on a phone, or rely on unavailable device DSP resources.

## Engineering decision

The ISP performs at least two different jobs: (1) prepares parameters for a frame, and (2) applies parameters to pixels. It is essential to preserve the original distinction.

- **Known original-code-equivalent preparation:** Stage8 MAIN LUT profile selection (`[cc_color_temp,color_gamut]`, original 12 native fixtures and 10 real-IQ profile receipts); original-referenced `hb_ccm_prepare` (96 signed coefficients) and MAIN positive gamma knot *coordinates* (257 points). Stage8 profile preparation returned 12/12 and 8/8 on the Android Stage8 APK, build 27186.
- **Known exact DISPLAY pixel computation:** Stage9 original `libduml_hal.so` 16×16×16 component-bank decoding and normalized trilinear sampling; prior original-native proof does not connect the DISPLAY format to MAIN.
- **Unproven pixel contracts:** phone-sensor-to-Hasselblad working domain, calibrated AWB, MAIN CCM 6-coefficient pixel equation/region selection/scale, MAIN GAMMA pixel interpolation/negative values/dithering, MAIN 3DLUT packing/input coordinates/interpolation/quantization, hardware operation order, R2Y/output transfer, and runtime post/HDR mode control. A single input RAW must preserve highlight headroom until this contract is known.
- **Atmosphere ambiguity:** earlier `scene_awb_atmos_proc` research concerns **AWB scene-state processing**. It is not itself proof of a separate photographic haze/atmosphere pixel renderer.

## New modules

`src/hb_isp_research.c/.h` implements a bounded, API-tested composition layer. It links three already audited research components (no new vendor code):

1. `hb_main_lut_prepare` — eight 6,144-word packed source profiles to one 6,144-word interpolated profile. This part has original `librcam.so` mathematical reference evidence.
2. `hb_ccm_prepare` — eight 96-value profiles to 96 interpolated CCM coefficients. This part has original native-reference evidence, but the coefficient-to-pixel equation is unknown.
3. `hb_isp_research_gamma_knots` — a new portable C implementation of the previously original-instruction-validated gamma coordinate construction. It produces 257 coordinates, not gamma pixel values.
4. `hb_isp_research_display_candidate` — takes only finite normalized RGB triples in `[0,1]`, and evaluates the **Stage9 DISPLAY sample model** against the prepared LUT as an explicit *hypothesis*. The upstream CCM/gamma pixel stages are not simulated. Rejects signed, over-range and non-finite values instead of silently clipping. Synthetic fixtures contain no vendor LUT bytes and no photographic pixels.
5. `hb_isp_research_main_gate` — returns `HB_ISP_UNVERIFIED_PHOTOGRAPHIC`, with the eight outstanding MAIN integration contracts marked. **There is no API path that authorizes saved-photo rendering.** Research-mode labels (`normal`, `enhanced normal`, `enhanced HDR`) do not alter source selection, and are not claimed to represent the vendor controllers.

The `prepare` operation is transactionally fail-closed: if any stage fails, all outputs and the receipt remain unchanged. It requires exact input/output array sizes and non-overlapping buffers. Sampling is bounded to 1,024 pixels and does not access Camera2, a photo, RAW, GPU or user storage.

## Host validation

The independent test `tests/test_isp_research.py` builds this module against the **existing** Stage8, Stage9 and CCM source files, compares prepared words, CCM values, all 257 gamma coordinates and 1,024 RGB probes against an independent Python reconstruction; validates unmodified outputs under malformed inputs; and checks conditional-mode *model* invariance. It uses deterministic **synthetic** reference profiles with six unique contents and deliberate duplicated warm endpoints. That fixture *resembles the profile-count pattern* of the original data but **does not contain any original table or prove the MAIN table format**.

Run in repository root:

```bash
export HB_STAGE8_LUT_C="$PWD/hasselblad_native_audit/photographic_profile_stage8/src/hb_main_lut_profile.c"
export HB_STAGE9_DISPLAY_C="$PWD/hasselblad_native_audit/photographic_pixel_stage9/src/hb_display_lut16.c"
export HB_CCM_PREPARE_C="$PWD/hasselblad_native_audit/main_colour_20261019/ccm/ccm_prepare.c"
python3 hasselblad_native_audit/isp_research_stage14/tests/test_isp_research.py \
    --output /tmp/STAGE14_SOFTWARE_ISP_REFERENCE.json
CC=clang python3 hasselblad_native_audit/isp_research_stage14/tests/test_isp_research.py \
    --output /tmp/STAGE14_SOFTWARE_ISP_CLANG_REFERENCE.json
```

An additional, standalone `tests/test_isp_sanitized.c` passes AddressSanitizer + UndefinedBehaviorSanitizer. Hosted CI is at `.github/workflows/hb-isp-stage14-reference.yml` and checks that no Photon production file or verified Stage8/9 source changed.

**Recorded host test result:** 72 scenarios per compiler; 1,024 synthetic RGB inputs per scenario; 221,184 compared scalar outputs per compiler, maximum error 0 against the independent Python evaluator. 690,650 independent checks per compiler. Test scope is composition and guards, *not* original ISP pixel parity.

## No incorrect claims

The Stage14 code **does not** call the proprietary X2D firmware. Original-reference routines were previously run separately; this stage tests the owned reconstructed code. The reported `MAIN` profile interpretation in the sampler is a deliberate hypothetical use of the known `DISPLAY` pixel math, and is not a proven Hasselblad saved-image pixel operation. These tests do not create a photographed colour look. Stage8 build 27186 remains the installed and phone-tested baseline; no replacement APK is produced by this research-only checkpoint.

## Next concrete proof gates

1. **MAIN pixel format oracle** — prove bank/component order, knot layout, input transfer domain and interpolation for real photographic MAIN. Use a MAIN-linked code/spec or controlled ISP input/output rather than the same-size DISPLAY implementation.
2. **MAIN CCM pixel equation** — verify 6-coefficient region interpretation, shifts/saturation, per-pixel selection; the existing coefficient preparation is not the pixel application.
3. **MAIN gamma pixel evaluation** — recover interpolation, negative and over-range response, output quantization/dither and its interface with MAIN LUT.
4. **Calibrated phone adapter** — same-frame physical sensor metadata, real neutral reference targets in at least daylight/warm light, camera matrices and a one-time WB policy. Stage7 explicitly abstains without this evidence.
5. **Only then connect to the Photon still renderer** behind an explicit opt-in mode; prove preview/still consistency, real captured pixels, cross-device fallback, headroom, performance and no HDR/stacking. Keep original DNG and Camera2 evidence unmodified.

We do **not** need to replicate the proprietary kernel driver, frame scheduler, entire DSP, or vendor hardware peripherals to port colour mathematics. We do need the actual mathematical pixel contract or an explicitly described and tested approximation. No unconditional claim of exact X2D colour is warranted without a corresponding oracle.

Privacy/licensing: source is owned research code under MIT; no source-derived private photographs, firmware libraries, camera IQ payloads or binaries belong on the public GitHub branch. Preserve user capture artifacts privately. Keep `main` unchanged.
