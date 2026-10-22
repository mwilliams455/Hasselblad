# Stage 19 — XYZ D50 output bridge and Phocus temperature selection (research only)

**22 October 2026 — HasselbladPhoton.** This is a source-only, reproducible numerical checkpoint on `recovery/awb-rebuild-20261021`. It changes **no** Photon camera, demosaic, GPU, JPEG, white balance or Android signing. No new APK is produced.

## Important result and limits

Stage18 validated an Adobe DNG `ForwardMatrix` sub-path for taking an individual phone's **already demosaiced linear camera RGB** to **CIE XYZ D50**. Stage19 implements the corresponding **standard display-primary output** from XYZ D50 to **linear sRGB or linear Display P3** with explicit D50-to-D65 Bradford adaptation. It also implements the **WB selector arithmetic described by a separate, public Phocus 4.0.1 HNCS reconstruction**, without its private camera matrices, colour-correction LUT records, or Film Tone.

**Neither operation is the original Hasselblad X2D II ISP photographic transform.** Standard P3 is not proof of X2D II's original MAIN colour LUT working domain. An ICC output matrix is not a Hasselblad look; the publicly reconstructed Phocus selector alone cannot apply HNCS.

### Distinguish two camera/desktop pipelines

| Property | X2D II 1.3.16.2 original MAIN firmware (original native preparation already verified) | Independent Phocus 4.0.1 X2D 100C Standard reconstruction |
|---|---|---|
| Profile-LUT anchors | 2400, 3050, 5550, 9100 K | 3100, 5550, 9100 K |
| Matrix anchors | 2400, 3050, 5550, 9100 K for verified CCM **preparation** | 2400, 3100, 5550, 9100 K for separate reconstructed camera matrices |
| Secondary controls | MAIN LUT also indexed by output gamut sRGB/P3; CCM source includes two identical high-ISO banks | Public WB ColorCorrect selector uses integer Kelvin, no Lightroom tint parameter |
| Pixel maths | MAIN CCM six-coefficient equation, MAIN gamma and MAIN LUT hardware sampler **unproven** | Public `apply_color_correct` evaluator exists, but original recovered numeric records are local and not distributed |
| Proven on phone | Stage8 profile-preparation diagnostic PASS, and Stage18 DNG-to-XYZ numeric pass | **Not** run with complete camera tuning payload on phone |

The distinct 3050 K vs 3100 K anchors must **not** be merged. The target selector in this stage is labelled `phocus`, not `MAIN`, and has **zero real camera matrix/LUT data**.

## 1. Standard XYZ D50 to output-linear RGB

`src/hb_colour_stage19.c/.h` builds a row-major 3×3 matrix as

```
D50_ICC = (0.9642, 1.0, 0.8249)
D65     = (0.3127/0.3290, 1.0, (1 - 0.3127 - 0.3290)/0.3290)
B       = Bradford cone response matrix
CAT     = inv(B) × diag((B × D65) / (B × D50_ICC)) × B
P       = XYZ columns of sRGB or Display P3 xy primaries
S       = inv(P) × D65
M_RGB_to_XYZ_D65 = P × diag(S)
M_XYZ_D50_to_linear_output = inv(M_RGB_to_XYZ_D65) × CAT
```

The sRGB primaries are R (.640,.330), G (.300,.600), B (.150,.060); Display P3 primaries are R (.680,.320), G (.265,.690), B (.150,.060). Output primaries **share D65 but differ in gamut**. The implementation computes all matrices using explicit 3×3 inversion and checks `M × D50 = (1,1,1)`.

- Accepts only finite, already linear XYZ D50, at most 4,096 pixels per invocation; preserves negative values and highlights above 1.0 without clipping, OETF, dither, display encoding or Film Tone.
- Fails transactionally (out-of-bounds, invalid gamut, non-finite inputs, source/destination overlap, arithmetic overflow); no partial output writes. Successful receipts explicitly prohibit claiming HNCS or original MAIN pixel parity.
- Compatible with any sensor that supplies Stage18's **restricted** DNG ForwardMatrix contract, not globally compatible with phones requiring dual-illuminant interpolation. This is standard output colourimetry and cannot substitute for Adobe/Hasselblad creative colour rendering.

## 2. Independent Phocus401 Kelvin-selector reference

The public [HNCS-Lightroom](https://github.com/fishvivfish/HNCS-Lightroom) project at commit `38fbbfc9c593e3ba65ced3a7c08e1d3e84f91ca0` documents the algorithm in `docs/ALGORITHM.md` and publishes the selector in `hncs_core/phocus401_wb.py` (Git blob `6e09b0186f647c0e8ffb7af37a78a0cd563e7241`). These documents report a reconstruction of Phocus **4.0.1 / X2D 100C Standard**, **not** original X2D II firmware 1.3.16.2.

The port independently implements only these public rules:

- Kelvin is converted to an integer by truncating toward zero before selection.
- The LUT selector clamps the requested Kelvin to [2000,10000]; chooses adjacent anchors `[3100,5550,9100]`, and *extrapolates* on the outer pair if the clamped input lies beyond an anchor.
- The camera-matrix selector separately clamps to [2000,8000]; anchors `[2400,3100,5550,9100]` with the same edge extrapolation.
- The public interpolation stores the resulting LUT as float32; Stage19 has a **synthetic-only** blend helper for numeric checking, not a camera LUT decoder.

The source documentation explicitly says the original Phocus WB numerical records are **not distributed**. There is no real X2D/Phocus profile in this checkpoint, no conversion from XYZ D50 into the Phocus custom input colour domain, and no original HNCS image stage. The user must not interpret a successful selector as HNCS processing.

A second [independent empirical HNCS project](https://github.com/songjiun10-collab/Hncs) measures official photographs and RAW/JPEG pairs; its published errors and dependency on RAW baselines make it a potential **validation target**, not a bit-exact replacement for firmware. Its fitted curves, user reviews and population statistics must not be taken as the original `MAIN_CCM` formula.

## Validation

```
python3 hasselblad_native_audit/isp_colour_stage19/tests/test_colour_stage19.py \
    --output /tmp/STAGE19_PUBLIC_TEST.json
python3 hasselblad_native_audit/isp_colour_stage19/tests/test_stage18_stage19_chain.py \
    --output /tmp/STAGE19_CHAIN_PUBLIC_TEST.json
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
   -fno-omit-frame-pointer -I hasselblad_native_audit/isp_colour_stage19/src \
   hasselblad_native_audit/isp_colour_stage19/tests/asan_stage19.c \
   hasselblad_native_audit/isp_colour_stage19/src/hb_colour_stage19.c -lm \
   -o /tmp/hb_stage19_asan
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 /tmp/hb_stage19_asan
```

Recorded local independent GCC/Clang results:
- **1,250,958** double/scalar model comparisons, maximum absolute discrepancy **5.329e-15**; 8,050 independently checked Phocus selector states; 14,336 float32 LUT blend sample checks.
- Separate Stage18→Stage19 composition: **786,432** checked synthetic channel outputs across 64 camera profiles, 2 gamuts and 2 compilers; maximum discrepancy **1.066e-14**.
- ASan/UBSan standalone: PASS.
- **Private** original 4096×3072 phone DNG: 1,024 diagnostic RGGB bilinear samples independently evaluated through Stage18 and Stage19, both standard output gamuts; C versus NumPy maximum error **4.441e-16**. The private report retains full original DNG hash, per-channel extrema and scene-specific checksums; it is **never** committed to GitHub or uploaded in CI.

The private DNG command (only when the user explicitly provides the RAW and original Stage18 private matrix receipt):

```
python3 hasselblad_native_audit/isp_colour_stage19/tests/private_real_dng_pcs_output.py \
  --private-dng ORIGINAL.dng \
  --stage18-private-matrix PRIVATE_STAGE18_MATRIX_REPORT.json \
  --output PRIVATE_STAGE19_REPORT.json
```

This uses the **Stage18 research-only bilinear RGGB diagnostic**, not the deployed Photon demosaic, and uses the existing **uncalibrated Camera2 HAL neutral**. No real tone/HNCS calibration, image transformation, JPEG, gainmap, output-profile tagging or gain adjustment occurred.

## Next evidence gate

1. Determine which original photographic colour stage can be tied to exact input/output pixel samples: the X2D II MAIN 16×6 signed CCM hardware equation, gamma interpolation/clipping/dither or true MAIN 16³ LUT layout and domain. Stage14's DISPLAY candidate still cannot be asserted to be MAIN.
2. Alternatively obtain licensed/independent authentic X2D II RAW + **Phocus rendered** matched reference images and fit a *separately labelled empirical target* while validating by scene and illuminant. Do not treat Photon JPEG against its DNG as an authentic HNCS reference.
3. Recover camera-specific illuminant interpolation and calibrate Stage7 real neutral cards before trusting phone white balance as an HNCS variable. Stage18's fixed-forward-matrix path cannot calibrate sensors with different ForwardMatrix anchors.
4. Only after (1) or (2), evaluate film tone and HNCS SDR/P3/HDR output (and any gainmap) as **separate** photometric stages; measure colors and protected highlights against references before applying it to saved phone images.

Production policy: `photo_render_authorized=false`; no output clipping/encoding in this core; main branch untouched; `HasselbladPhoton-Stage8-27186` is still the last validated APK. Do not upload user DNGs, private calibration files, original Hasselblad firmware, recovered proprietary LUT bytes or Phocus tuning records to public GitHub.

Licence: owned Stage19 source is MIT research code; sources are attributed for ideas and independently represented mathematical contracts. HNCS-Lightroom is Apache-2.0; its original code, proprietary recovered data and Lightroom profile payload are **not copied into this project**.
