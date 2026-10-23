# Stage41Q — isolate colour correction from rejected gamut handling

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Baseline research commit: `20a4ebce360bf8fdb5dc3500e444e595b790b4b0` (Stage41P).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

The four-coefficient protected colour trial reduces primary RGB error on all four scenes, in both tile phases and against both available references. It improves sampled skin and sky while avoiding the earlier dark-background regression. The light shirt still worsens. An exploratory lightness-dependent extension also fails that shirt check. These are useful empirical candidates, not an accepted universal renderer or recovered Eagle2 MAIN equation. No APK or production photo output changes.

## What changed

Stage41L tested colour correction together with neutral-axis gamut contraction, but subsequently rejected that gamut step. Stage41Q removes this confound: every new candidate starts from exactly the retained Stage41L smooth tone with ordinary channel clipping. The frozen Stage41L baseline reproduces with zero metric difference for all prior regions, both reference types and both tile phases.

The first two candidates were fixed before this stage's scoring:

1. **Global:** a four-coefficient, zero-offset residual transform of Lab a/b, applied after tone and display clipping. Neutral a=b=0 has no correction.
2. **Protected:** the same four-coefficient family, with its residual multiplied by `C²/(C²+12²) × 4l(1−l)`, where `l=L*/100`. This empirical gate suppresses correction near neutral and at lightness extremes. The constants are hypotheses, not firmware values.

Both use ridge regularization towards zero residual, with multiplier 0.05 and the same ungated feature energy setting the penalty. Scene training weights, tone fits, reference encoding, sample masks and exposure treatment remain unchanged. Differential Lab-to-RGB conversion subtracts the unchanged roundtrip, so a zero colour correction is identity to float precision. Final RGB gamut clipping can still alter luminance and hue.

After inspecting the primary shirt regression, an explicitly **exploratory lightness-dependent** candidate was added. Its protected a/b coefficients vary affinely with `2l−1`, giving eight fitted coefficients. No further hyperparameter search or hand-picked shirt/skin exceptions were performed. This extension is recorded alongside the primary results; it is not fresh independent validation.

## Validation and scope

Reuse the four verified real 3FR linear-sRGB caches from Stage41J. Each scene is excluded from training its shared tone and colour model. Each training scene contributes 8,192 sampled pixels. Held-out scalar exposure uses reference-assisted calibration tiles; score tiles are disjoint, with five-pixel guards. Both tile phases are scored.

Embedded previews use the fixed empirical Display P3-to-sRGB conversion established in Stage41K. Supplied tagged sRGB JPEGs are scored separately. The references derive from the same captures and are not independent scenes. Initial alignment and masks are reference-assisted. These four images have already guided model development; none of this is a blind camera-output or new-scene generalization test.

The original portrait boxes, saturated-red check and sky check remain evaluation-only. New low-chroma (`C* <= 12`) and dark (`L* <= 20`) reporting masks never affect fitting. A light shirt is not assumed to be a calibrated neutral surface.

## Main results

Phase-0 RGB mean absolute error on the 0–255 scale; lower is better:

| Scene | Retained tone | Global colour | Protected colour | Exploratory lightness-dependent |
| --- | ---: | ---: | ---: | ---: |
| A, red car | 3.409 | 2.951 | 2.749 | 2.433 |
| B, tower | 3.403 | 3.222 | 3.258 | 3.202 |
| C, portrait | 3.742 | 3.675 | 3.506 | 3.618 |
| D, St Paul's | 5.152 | 3.810 | 3.464 | 3.643 |

Protected-colour reductions versus retained tone are 19.4%, 4.3%, 6.3% and 32.8%. Phase 1 gives 15.4%, 3.6%, 8.5% and 32.7%. The separately scored JPEGs agree in direction for every scene and both phases (phase-0 reductions 19.3%, 3.5%, 5.9%, 32.5%).

The global colour model reduces portrait RGB error slightly but increases phase-0 mean a/b error from 2.762 to 2.843. This further illustrates why a single aggregate metric is insufficient.

## Regions expose both progress and limits

Phase-0 mean Lab a/b distance:

| Region | Retained tone | Global | Protected | Lightness-dependent |
| --- | ---: | ---: | ---: | ---: |
| Portrait sampled skin | 7.573 | 2.127 | 2.691 | 2.389 |
| Portrait dark background | 1.535 | 1.677 | 1.509 | 1.601 |
| Portrait light shirt | 2.520 | 5.161 | 3.978 | 3.356 |
| Cathedral clear sky | 8.197 | 5.627 | 5.770 | 5.482 |

The protected trial improves sampled skin a/b error by about 64% in phase 0 and 61% in phase 1. Skin RGB error falls from 5.992 to 2.614 and from 6.099 to 2.773. The dark background's RGB and chroma errors improve slightly in both phases. The same portrait's low-chroma and dark reporting masks also improve.

However, the shirt RGB error rises from 7.651 to 8.835 in phase 0, and from 10.793 to 11.949 in phase 1. Its chroma error rises in both phases as well. Private mean-colour inspection shows that its baseline pixels already carry sufficient warm chroma to receive a substantial correction. The correction adds red where the reference requires much less. Neutral protection alone therefore does not resolve this failure. This is a diagnosis of this empirical model's response, not proof about the camera's scene recognition or processing architecture.

The exploratory lightness-dependent model reduces the shirt's chroma regression but increases its RGB error further, to 9.046 and 12.417, while reintroducing a dark-background regression. Do not promote it on its lower red-car score alone.

The saturated-red appearance check includes clipped reference pixels excluded from primary scoring. Protected colour changes red-region RGB error from 11.091 to 9.767 in phase 0, but from 10.248 to 10.356 in phase 1. Red a/b distance improves in both phases while luminance error rises. The lightness-dependent variant improves red RGB error in both phases (8.730 and 9.221), but its portrait failures remain. Neither this check nor the primary score establishes recovery of pre-clipping colour.

Small bright regions also contain regressions. For example, the car's eligible bright mask has only 63/32 pixels and protected-colour RGB error rises in both phases. All regional results, including failures, are retained in the aggregate receipt.

## Decision and next useful evidence

Retain the protected four-coefficient version as an offline comparison candidate. Keep the tone-only result as the established baseline. No candidate passes a universal no-regression claim, and no automatic switch of Android rendering is justified by these four development scenes.

The useful next empirical evidence is additional RAW/reference scenes spanning similar warm colours at different lightness and saturation, or reproducible Phocus exports of the existing RAWs. Phocus has not been executed in this environment and no Phocus output is represented here. Further arbitrary gating tuned to this one shirt would not establish generality.

Firmware work remains at the Stage41P evidence boundary. A newly decrypted DSP payload or MAIN pixel evaluator would be useful. The existing Android-host preparations, register writers and SUB DSP-dispatch wrapper do not establish MAIN arithmetic. Successful outer firmware/filesystem extraction alone does not demonstrate that the DSP processing payload is decoded, and decryption alone does not guarantee a software implementation of fixed-function hardware.

## Reproduction and checks

Source: `hasselblad_native_audit/isp_3fr_stage41q/`. It imports adjacent Stage41J/K/L helpers. Requirements delegate to Stage41J.

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python hasselblad_native_audit/isp_3fr_stage41q/test_colour41q.py \
  --cache-dir /private/stage41j/baseline \
  --private-dir /private/stage41q \
  --receipt /private/STAGE41Q_ISOLATED_COLOUR_SAFE.json \
  --stage41l-receipt hasselblad_native_audit/evidence/stage41l/STAGE41L_HIGHLIGHTS_REGIONS_SAFE.json

python hasselblad_native_audit/isp_3fr_stage41q/test_math41q.py
```

Four mathematical test methods pass, including no-op behaviour, neutral/lightness endpoint protection, synthetic fit recovery on new colours for all three model families, and bounded finite outputs/rejection of invalid coefficients. Frozen baseline metrics reproduce exactly. Source-cache SHA256 checks confirm no changes to inputs. The repository-layout rerun produces a byte-identical aggregate receipt, and its mathematical tests also pass.

The public receipt contains aggregate measurements and model descriptions only. Photographs, pixel arrays, capture hashes/calibration, fitted coefficients and the comparison figure stay private. The private fit file stores per-fold tone, exposure and colour parameters so that these exact comparisons can be reproduced. No all-four production colour fit is implied.
