# Stage41L — smooth highlights and regional colour failures

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Baseline research commit: `2cf9274c6ace7db8d539ea698c280fff3da65563` (Stage41K).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

The smooth highlight curve improves the primary held-out RGB score in all four scenes by 8.5–22.9% relative to Stage41K. None of its shared-shape or training-exposure fits reaches a bound. A separate saturated-red check rejects the neutral-axis gamut-contraction trial: its red-region RGB error is more than twice the previous model's. The global colour trial helps sampled skin but worsens the light shirt and dark background. Retain the smooth curve with ordinary channel clipping as an offline candidate; do not promote either global colour or gamut handling from aggregate scores alone.

This is empirical rendering research on four real 3FR/JPEG pairs, not a recovered Hasselblad pixel equation or an HNCS implementation. No Android rendering or APK changed.

## Inputs and evaluation

Reuse the four verified Stage41J linear-sRGB caches, default-crop/alignment work, metadata-based black handling and white balance. Actual CFA samples were already decoded and checked against TIFF storage in Stage41J. This stage does not repeat that intake or substitute thumbnails for sensor data.

Apply the fixed Display P3-to-sRGB conversion established in Stage41K to embedded previews. This interpretation is empirical and conflicts with the parent EXIF colour-space label; it is not an ICC declaration in the preview. Independently score the supplied tagged sRGB JPEGs. The capture firmware is 1.1.6.3; the extracted firmware used for structural checks is 1.3.16.2.

For each held-out scene, train shared tone/chroma only on the other three scenes, using 8,192 evenly sampled eligible pixels per training scene. The loss, sample masks, Lab conversion and exposure treatment remain those of Stage41K. Held-out exposure is estimated from reference-assisted calibration tiles. Scoring uses disjoint tiles with a five-pixel inset in each 40-pixel cell. Repeat with a shifted tile phase.

Alignment and masks are reference-assisted. The four images have already guided development, and choosing this curve after Stage41K makes this a development-set comparison, not fresh independent validation or blind auto-exposure. Pixel counts are descriptive, not independent experimental replicates or confidence intervals.

## The retained tone candidate

Stage41K's second shape parameter repeatedly reached its lower bound. Take its mathematical limit as that parameter tends to zero, then extend continuously to nonnegative gained luminance:

`f(Y) = sigmoid(p * log(Y / 0.18) + logit(0.18))`, with `f(0) = 0`.

There is one positive shared exponent, constrained to `[0.4, 2.5]`. The curve fixes middle gray, is strictly increasing, and approaches display white asymptotically. It removes Stage41K's rule that all gained luminance at or above one becomes white. Apply `f(Y)/Y` equally to linear RGB, then encode to sRGB with ordinary display clipping. This does not restore sensor or earlier pipeline clipping.

All four fits converge in five or six evaluations without shape or training-exposure bounds being reached. A separate all-four research candidate also converges without reaching bounds; it is not an additional validation result. Fitted parameters remain private.

Primary phase-0 RGB mean absolute error, on the 0–255 scale; lower is better:

| Scene | Scoring pixels | Previous tone | Smooth tone | Reduction |
| --- | ---: | ---: | ---: | ---: |
| A, red car | 12,186 | 3.826 | 3.409 | 10.9% |
| B, tower | 29,845 | 4.415 | 3.403 | 22.9% |
| C, portrait | 39,194 | 4.828 | 3.742 | 22.5% |
| D, St Paul's | 40,955 | 5.632 | 5.152 | 8.5% |

The second tile phase gives respective reductions of 10.3%, 22.8%, 18.8% and 9.5%. Against the supplied tagged JPEGs, phase-0 reductions are 10.5%, 22.5%, 22.1% and 8.1%; phase 1 agrees in direction for every scene.

In bright reference pixels (`L* >= 80`), tower mean absolute L* error falls from 3.352 to 1.012 (1,697 pixels), and portrait error from 9.683 to 3.872 (838 pixels). The other two scenes have too few eligible bright pixels for a broad highlight claim: car has 63 and cathedral has two in phase 0. Phase-1 tower and portrait results agree. These masks exclude near-clipped reference values and do not measure recovery of lost sensor highlights.

## Rejected gamut trial: saturated-red appearance

The fixed gamut trial contracts overflowing linear RGB towards equal RGB at the same luminance. It preserves linear luminance and direction from neutral, not necessarily perceptual hue. It has no learned coefficients. Its benefit is not uniform even in the primary mask: portrait RGB error is 3.850 with gamut contraction versus 3.742 with ordinary clipping.

Visual inspection exposed a larger red-paint failure that the primary mask missed. A post-hoc diagnostic therefore includes clipped red reference colours while retaining low-gradient pixels, the score-tile layout, a border exclusion and non-clipped source-cache channels. Red selection requires R greater than 1.5 times both G and B, with RGB span above 0.3. It never changes training or the primary score.

| Red-region diagnostic | Phase 0 | Phase 1 |
| --- | ---: | ---: |
| Pixels | 5,467 | 4,639 |
| Reference maximum channel at least 0.98 | 54.6% | 57.1% |
| Previous tone RGB MAE | 10.835 | 9.800 |
| Smooth tone, ordinary clipping | 11.091 | 10.248 |
| Smooth tone plus gamut contraction | 26.064 | 27.866 |
| Gamut plus global colour trial | 21.984 | 24.539 |

The tagged JPEG confirms the same failure. This measures final display appearance, including reference clipping, and cannot identify the reference's pre-clipping colour. It shows both that the neutral-axis contraction is unsuitable here and that the smooth curve is not uniformly better in every region. The red diagnostic was selected after seeing the failure; preserve it for future checks rather than claiming it as a preregistered benchmark.

## Regional colour: skin improves, shirt and background regress

The colour trial is a regularized 2×2 zero-offset transform of Lab a/b, trained on the other three scenes after the smooth tone and gamut trial. It is not the camera CCM. Portrait regions are fixed, inspected image rectangles used only for reporting, not fitting weights or a skin detector. The full receipt records their coordinates and both tile phases.

Phase-0 mean Lab a/b distance before versus after the colour trial:

| Portrait region | Pixels | Before colour | After colour |
| --- | ---: | ---: | ---: |
| Selected skin patches | 705 | 7.573 | 2.108 |
| Light shirt | 216 | 2.520 | 5.190 |
| Dark background | 2,696 | 1.535 | 1.706 |
| Outside selected skin patches | 38,489 | 2.600 | 2.909 |

Sampled skin chroma error falls by about 72% in phase 0 and 70% in phase 1. Its RGB error also falls (5.992 to 2.418 in phase 0). Thus the earlier whole-portrait chroma regression was not evidence of a skin regression. In both phases the light shirt and dark background worsen. The shirt is not asserted to be a calibrated neutral target under this lighting. These are descriptive checks on one portrait, not a skin-colour generalization claim.

## Connection to original firmware

The local original-firmware schema/config check confirms ownership of `knee_en` in `mod_main_gamma_common`; knee, gamma, gain and saturation fields in `mod_main_gamma_normal`; and enable/exposure-adjust fields in `mod_main_autoknee`. The `main_gamma_normal.gamma_lut` registration declares `simple_lut_mem` and `mode_frame`.

The evidence receipt includes firmware config/schema hashes and field names only. No original tuning arrays are exported. Static ownership does not identify the active bank, the runtime input scale or the original pixel equation, and does not prove that this fitted curve is the firmware knee. Original MAIN CCM grouping, scaling and rounding remain unresolved.

The next useful original-firmware task is to trace the knee/gamma input scale, runtime bank selection and interaction with saturation. For empirical work, retain separate bright, skin, low-chroma and saturated-red checks; a lower whole-image score is insufficient to accept a universal colour transform.

## Reproduction and verification

Code: `hasselblad_native_audit/isp_3fr_stage41l/`. It imports the adjacent Stage41J and Stage41K helpers and uses `isp_3fr_stage41j/requirements41j.txt`.

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python hasselblad_native_audit/isp_3fr_stage41l/test_highlights41l.py \
  --cache-dir /private/stage41j/baseline \
  --stage41k-models /private/stage41k/p3-corrected/private_fit_parameters.json \
  --private-dir /private/stage41l \
  --receipt /private/STAGE41L_HIGHLIGHTS_REGIONS_SAFE.json \
  --firmware-root /private/original-firmware/extracted

python hasselblad_native_audit/isp_3fr_stage41l/test_math41l.py
```

Four mathematical tests pass: the Stage41K limit and extended-domain monotonicity, continuity at the old white cutoff, gamut bounds/luminance preservation, and synthetic shape/exposure recovery. The frozen Stage41K scores reproduce exactly for both references and both phases. Source caches remain unchanged. Validation is local; no private image data was sent to public CI.

Public evidence: `hasselblad_native_audit/evidence/stage41l/STAGE41L_HIGHLIGHTS_REGIONS_SAFE.json`. Original photographs, pixel arrays, capture identifiers/hashes, metadata calibration arrays, fitted model arrays and the private comparison image are excluded from GitHub.
