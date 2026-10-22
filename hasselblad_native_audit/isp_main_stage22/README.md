# Stage 22 — sRGB/P3 MAIN profile relationship; input-axis ambiguity preserved

**22 October 2026 — research-only HasselbladPhoton X2D II 100C (1.3.16.2)**

## Question and crucial limits

Stage 21 prepared genuine X2D II `MAIN_3DLUT` profiles with native-reference-tested firmware mathematics, but the *per-pixel MAIN interpolation, cube packing, input domain and RGB ordering* are unproven. The X2D II IQ configuration names `color_gamut` values 0=sRGB and 1=P3, so can their two distinct source-table banks reveal a physical output-channel mapping?

This study tests that **conditional possibility** against independent standard colourimetry. It **does not** assume the two MAIN LUT banks are pure colour-space conversions, that their 12-bit outputs encode linear RGB, or that our Stage21 planar decode is hardware-correct. Different creative tuning, internal working spaces, gamut mapping, and transfer encoding could invalidate all three tested relationships.

## New original-source test

`src/gamut_relation22.py` takes the exact X2D II IQ configuration (SHA256 pinned by the existing Stage21 `originals()` implementation) as **transient local data**, prepares matched sRGB/P3 profiles at **2400, 4300, 5550, 7001, 9100 K**, and checks all **10 full-size output hashes** against prior original-`librcam.so` native-reference executions. It verifies 128 exact-grid samples from Stage21 C match the independent decoded array at 5550 K. No original vendor functions are executed in this step.

The original 6144-word profiles are decoded only through Stage21's explicit *hypothetical* 16×16×16, 3-planar-bank representation. **Only the 4096 exact grid nodes** are used for the main gamut comparison, so the result does not depend on whether MAIN hardware uses trilinear, tetrahedral or any other off-grid interpolation.

The two candidate output arrays are compared under all six bank-to-output-channel permutations against three hypotheses:

1. **Identity/no gamut conversion:** normalized output values directly match across banks.
2. **Linear standard gamut change:** `P3_linear ≈ M_sRGB_to_P3 × sRGB_linear`.
3. **sRGB-transfer encoded gamut change:** `P3_encoded ≈ OETF(M_sRGB_to_P3 × EOTF(sRGB_encoded))`.

The matrix is constructed **independently** from standard sRGB (R=.64/.33, G=.30/.60, B=.15/.06) and Display P3 (R=.68/.32, G=.265/.69, B=.15/.06) chromaticities, both referenced to D65. Stage19 native D50-to-sRGB/P3 output matrices independently agree with the derived cross-gamut matrix to double-precision tolerance. The same sRGB transfer function is used for the *encoded hypothesis*, reflecting the usual Display P3 profile convention. The original MAIN post-gamma pixel transfer domain is **not** known.

Per-temperature output contains **aggregate mean/P95/max residuals and fractions exceeding one 12-bit step**, plus per-model best score and all bank-order mean errors. There are **no input LUT words, colour components, rendered pixels, original images, vendor code, source image positions or camera metadata** in the results.

### Mathematical identifiability limit

A full uniformly sampled grid is symmetric to **all six permutations of the three input axes**. Changing the input-axis interpretation just reorders the matched grid-node pairs; for a given bank-to-output mapping, the aggregate cross-gamut residual is unchanged. The synthetic tests *prove this invariance*. Thus, even if a bank-to-output ordering happens to score best, this experiment **cannot determine the input-axis mapping**. More fundamentally, a lowest-residual bank ordering is not a hardware proof if the gamma/linear conversion model is wrong or the LUTs have distinct creative rendering.

We deliberately do **not** select an output order or transfer function for the Android app, and always report `photographic_render_authorized=false`, `main_pixel_sampler_validated=false`, and `output_bank_order_hardware_proven=false`.

## Controls and CI

The selftest runs under **GCC and Clang** with no vendor files and verifies:

- 3×3 primaries-based matrix equals the Stage19 existing native D50 bridge's gamut conversion;
- a synthetic known permuted bank pair is correctly recognized as a **linear** gamut transform;
- a known encoded-gamut pair is recognized as an **encoded** transform;
- identical bank pairs yield identity best, a required negative control;
- all six input-grid relabellings leave aggregate residuals identical;
- grey/identical component banks remain ambiguous rather than forcing a channel identity.

Hosted workflow `.github/workflows/hb-stage22-gamut-relation.yml` reruns those guards and, in a temporary runner only, retrieves the **hash-pinned official X2D II firmware**, extracts IQ inertly, computes the gamut relation aggregates, and publishes only a compact non-proprietary JSON result. The runner is checked to leave the Stage8, Stage9, Stage14, Stage18, Stage19, Stage20, Stage21 and app production source unchanged. It does not access Camera2, save photos, build an APK, or deploy code to a device.

### Reproduce synthetic tests

From repository root:

```sh
python hasselblad_native_audit/isp_main_stage22/src/gamut_relation22.py \
    --selftest --cc gcc --output /tmp/STAGE22_GCC.json
python hasselblad_native_audit/isp_main_stage22/src/gamut_relation22.py \
    --selftest --cc clang --output /tmp/STAGE22_CLANG.json
```

For original IQ (only in a private ephemeral environment):

```sh
python hasselblad_native_audit/isp_main_stage22/src/gamut_relation22.py \
    --original-root /private/firmware/extracted --cc gcc \
    --output /tmp/STAGE22_SAFE_ORIGINAL_GAMUT_SUMMARY.json
```

## Following this study

An actual MAIN-linked pixel oracle, or matched genuine X2D II 3FR/Phocus captures with known illuminant, scene and source gamut, is required to resolve the remaining physical RGB ordering, gamma/CCM behaviour and working-space connection. Stage22 is *evidence about which assumptions are numerically plausible on available tables*, not a reconstruction of Hasselblad colour rendering. Stage8 Android build **27186** remains the phone-tested baseline, with **Photon photographic colour still active**. No HDR or scene-dependent look was introduced here.
