# Stage 21 — offline MAIN 3D LUT *candidate*, no photographic permission

**22 October 2026 · HasselbladPhoton research · X2D II 100C firmware 1.3.16.2**

## What was added

We now have an actual **per-pixel mathematical candidate** for the photographic `MAIN_3DLUT` path, rather than merely interpolation of camera LUT *parameters*. The code is a **hypothesis**, not a replica of the camera ISP. We have not identified the authentic MAIN pixel sampler, its canonical RGB axis/channel order or its input transfer domain. Do not use any Stage21 output to claim colour accuracy or an HNCS look.

Stage20, on exact original-camera LUT tables, strongly favoured a planar over an interleaved layout using an identity/smoothness *heuristic*. That heuristic leaves six mutually indistinguishable RGB relabellings. Stage21 explicitly carries **all six**, rather than declaring a winner.

`src/hb_main_candidate21.c` supports:

- one prepared 6,144-word, 16³ three-bank *candidate* table, two 12-bit values per 32-bit word, normalized to `[0,1]`;
- explicit independent permutations for physical grid-axis to input RGB and component bank to output RGB;
- **trilinear** sampling using the verified Stage9 **DISPLAY** decoder's mathematics as an assumption for MAIN;
- **tetrahedral** sampling as a separate, common mathematical alternative, with no claim of ISP use;
- strict finite in-range RGB inputs, rejecting negatives or values above 1 instead of destroying exposure headroom by implicit clipping;
- length, source-word, output overlap and permutation validation before any pixel output; output and receipt unchanged on failure;
- inputs/output aliases permitted only for identical buffers (full in-place) and independent per-pixel application;
- a receipt that **always** says `main_isp_pixel_equivalence_proven=0` and `photographic_render_authorized=0`.

It neither calls Camera2 nor applies a result to saved photos. **There is no hidden production bypass.** The permanent absence of a phone-render hook is a deliberate safety boundary, not a bug.

## Validation layers

1. **Independent synthetic mathematics:** `tests/test_candidate21.py` compiles original Stage8 owned profile-preparation source, Stage9 DISPLAY reference source and Stage21 C together. NumPy independently decodes the hypothetical cube and implements both trilinear and tetrahedral interpolation. Three asymmetric synthetic LUT types × six simultaneous RGB relabellings × both interpolation modes × 1,024 pixels are compared under **GCC and Clang**; tests check invalid input/nonmutation, in-place behavior and a selected Stage9 baseline sample subset. The Stage9 comparison proves only that our trilinear equations agree with the DISPLAY original-function reconstruction, not MAIN.
2. **Memory safety:** `tests/test_candidate21_sanitized.c` runs AddressSanitizer and UndefinedBehaviorSanitizer with 8,192 synthetic pixels, identity LUT, both interpolation modes, invalid final pixel and source bounds. Both algorithms must preserve identity for an identity 12-bit LUT, to float error tolerance.
3. **Original table experiment:** `src/original_candidate_probe21.py` accepts **only** an original X2D II IQ configuration with the known SHA256. The original firmware is transient in CI. It uses the already verified Stage8 portable profile generator and checks its prepared profile hashes against **ten previously executed original `librcam.so` reference outputs**. It evaluates candidate trilinear and tetrahedral output on deterministic *synthetic* RGB points for six CCT conditions and both gamuts. It reports **aggregate** effects of interpolation choice, CCT, gamut and the six RGB relabellings. NumPy independently cross-checks the candidate at disjoint points. Original profile words, per-node RGB values, photographic samples and output pixels remain in temporary memory and are **never exported**.
4. CI: `.github/workflows/hb-stage21-main-candidate.yml` runs the first two tests; downloads and validates the original official camera firmware, extracts it transiently, runs the third test, and allows uploading **only a numerical aggregate report**.

### Reproduce synthetic tests

From repository root:

```sh
export HB_STAGE8_C="$PWD/hasselblad_native_audit/photographic_profile_stage8/src/hb_main_lut_profile.c"
export HB_STAGE9_C="$PWD/hasselblad_native_audit/photographic_pixel_stage9/src/hb_display_lut16.c"
python3 hasselblad_native_audit/isp_main_stage21/tests/test_candidate21.py --cc gcc --opt=-O2
python3 hasselblad_native_audit/isp_main_stage21/tests/test_candidate21.py --cc clang --opt=-O0
```

Run the original-asset probe **only** with the extracted exact X2D II 1.3.16.2 source (never inside the mobile app):

```sh
python3 hasselblad_native_audit/isp_main_stage21/src/original_candidate_probe21.py \
  --original-root /path/to/extracted --output /tmp/STAGE21_SAFE_AGGREGATES.json
```

## Why this cannot yet produce Hasselblad photographs

The full saved-photo colour chain is still incomplete. In particular:

- It is not known which of the six equally plausible RGB permutations is the physical MAIN interpretation; smoothness scores cannot distinguish them.
- The source-table planar form is still a **heuristic lead**, not a MAIN-ISP verified byte/coordinate layout.
- It is not known whether MAIN ISP uses trilinear, tetrahedral, another interpolation, or different input grid coordinates.
- The physical input domain after MAIN CCM/gamma, its clipping and possible nonlinear shaper are unproven; Stage21 accepts only *hypothetical* linear normalized RGB inputs.
- The original **six-coefficient MAIN CCM pixel equation**, gamma pixel sampling and shading/R2Y/output order are missing.
- Stage7 calibrated sensor-neutral AWB still abstains on real phone captures. Stage18→19 provide a reference D50→sRGB/P3 colourimetric bridge but not a genuine X2D camera-colour-to-phone-colour adaptation.
- There is no original camera pixel output oracle or matched X2D II RAW/Phocus image reference in this test. There is also no HDR gain-map path or exposure stacking.

**The original table in tests is used only to measure sensitivity to unresolved assumptions. There is no claim that either chosen sampler matches the actual camera ISP.**

## Next evidence gate

First, quantify whether real X2D MAIN photographic profiles show a substantial **trilinear versus tetrahedral difference** at off-grid synthetic input coordinates. If the effect is small, this may reduce the urgency of disambiguating interpolation, but would **not** prove trilinear. Separately identify the RGB mapping through a MAIN hardware oracle or a faithful ISP description. Then establish the six-coefficient CCM and gamma pixel mathematics, plus calibrated phone sensor neutrality. Only then consider enabling an explicitly opt-in photographic preview or comparing to original X2D II Phocus/3FR render pairs.

The repo's `main` and the Photon camera renderer remain unchanged; baseline phone build is Stage8 `27186` and Stage8 colour is still Photon. Original vendor firmware and personal phone captures remain private and outside public Git commits.
