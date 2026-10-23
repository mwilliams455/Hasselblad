# Stage 41K — Reference encoding correction and shared tone holdout

2026-10-23. Research only, on `recovery/awb-rebuild-20261021`, following Stage41J commit `2c743cce03743359f646b3fa31f03ef50d22c7d5`.

The four real RAW pairs have produced two useful results: a reference colour-space mismatch is now accounted for, and a small shared tone model improves every scene when that scene is excluded from model training. A separate chroma trial is promising but not accepted as a universal correction. MAIN CCM semantics and HNCS equivalence remain unresolved. No APK, Android source, camera firmware or production photo output was changed.

## Reference encoding: correction to Stage41J

Stage41J treated untagged embedded JPEG previews as sRGB. During the first holdout experiment, a chroma correction improved the previews while worsening the independently sRGB-tagged JPEGs. That disagreement prompted a fixed-standard encoding check before accepting a learned correction.

Three predefined interpretations were tested: sRGB, Display P3 and Adobe RGB (1998). No colour coefficients were fitted to the photographs in this check. The standard primary chromaticities and transfer functions were used to transform preview values to sRGB, with output clipping. The measurements below use the original Stage41J mask intersected with the first guarded scoring layout.

| Pair | Preview treated as sRGB: RGB MAE to JPEG | Display P3 converted to sRGB | Adobe RGB converted to sRGB |
|---|---:|---:|---:|
| A | 3.910 | **0.726** | 6.476 |
| B | 1.277 | **0.741** | 1.448 |
| C | 2.143 | **0.900** | 4.854 |
| D | 4.066 | **0.760** | 4.443 |

The second scoring layout corroborates the result. The common fixed Display P3 interpretation gives the closest agreement across all four scenes. It is now the working reference-normalization policy. It resolves the previous opposing conclusions from the two reference types.

This is an **empirical encoding inference**, not discovery of an embedded ICC profile. Inspection of all four original 3FR Exif dictionaries found `ColorSpace=1`, which normally means sRGB. That parent metadata conflicts with the observed preview-to-JPEG relationship; the exact encoder provenance or metadata scope is not established. We retain the inference and conflict explicitly, rather than relabelling the original files or claiming the metadata proves P3. Sources are never modified.

The conversions operate on the existing 768-edge comparison caches. The embedded preview had already been resized in encoded space in Stage41J; this is not a full-resolution colour-managed export. Low-gradient masks and the independent tagged JPEG check bound that limitation. The original Stage41J geometric transform remains fixed; no colour-dependent spatial warp was fitted.

The Stage41J report now carries a prominent correction. Its original receipt remains historical evidence. Its complete RAW sample, WB, crop and alignment findings still stand, but its sRGB-assumed colour metrics must not be used as current colour calibration targets.

## Shared-model test design

Each of four folds trains on three scenes and excludes the fourth scene from both shared tone and chroma fitting. Training uses 8,192 evenly sampled eligible pixels per scene, so a large sky mask does not outweigh another entire scene.

The held-out scene still receives one scalar brightness fit from separate calibration tiles. Scoring uses disjoint tiles: 40-pixel blocks with five-pixel insets, calibration where `(tile_x+tile_y+phase)%4=0`, evaluation where it equals 2. Two phases, 0 and 1, check sensitivity to patch placement. The initial geometry and eligibility mask remain reference-assisted from Stage41J. After the P3 conversion, values near reference clipping are additionally excluded before any current fit or scoring.

This is **conditional generalization with reference-assisted brightness**, not a blind automatic-exposure or camera-rendering test. Held-out scoring pixels do not choose brightness, tone shape or chroma coefficients. The fixed reference-encoding policy was selected using the four supplied references before the corrected model test, so this small dataset is not an untouched final benchmark.

### Tone model

For positive shape parameters p and q, the mapping is:

`logit(f(Y)) = p log(Y/0.18) - q log((1-Y)/0.82) + logit(0.18)`

with endpoints fixed at f(0)=0 and f(1)=1. The model is monotonic, fixes middle gray, and is the identity when p=q=1. A scalar exposure multiplies linear RGB, then RGB is multiplied by f(Y)/Y. This preserves linear chromaticity before display clipping. The model has only two shared shape parameters, plus independent training-scene exposures.

The fit uses soft-L1 loss on L*/100, scale 0.02, p/q bounds [0.4,2.5], and exposure bounds +/-4 EV. Brightness-only baselines use the same luminance loss and calibration patches. These baseline values therefore differ from Stage41J's RGB-loss, all-mask fits; compare only within this stage.

### Chroma diagnostic

After tone fitting, a small zero-offset 2x2 transform of Lab a/b is fitted to the three training scenes, with a fixed ridge penalty toward identity. It leaves neutral a=b=0 unchanged and does not intentionally alter L*. It is an empirical rendered-colour diagnostic, not the camera's native CCM. No per-hue or scene-specific mask drives this fit.

## Corrected holdout results

First tile phase, scored against the converted embedded reference; RGB MAE uses the 0–255 scale:

| Held-out pair | Brightness only | Shared tone | Tone reduction | Tone plus chroma trial |
|---|---:|---:|---:|---:|
| A | 8.856 | 3.826 | **56.8%** | 3.290 |
| B | 6.841 | 4.415 | **35.5%** | 4.365 |
| C | 7.457 | 4.828 | **35.3%** | 4.762 |
| D | 8.186 | 5.632 | **31.2%** | 3.839 |

Mean absolute L* error improves by 72.2%, 41.4%, 47.2% and 56.4%, respectively. Scored counts are 12,186 / 29,845 / 39,194 / 40,955 pixels. Tone gains persist in the second patch phase (53.4%, 32.2%, 43.3%, 30.6% RGB reductions).

The independently tagged JPEGs now agree: first-phase tone reductions are 56.7%, 35.3%, 34.4% and 31.1%. This agreement is a practical validation of the reference-normalization decision. It is not proof that the embedded preview or small supplied JPEG is the full-resolution final camera rendering.

The chroma trial further lowers RGB MAE against both references in all four folds and both phases. D benefits most (about 32% additional RGB reduction). But C's mean a/b error increases about 0.7% in phase 0, while improving about 4.4% in phase 1. Its RGB improvement is also small. That mixed portrait result prevents treating the global chroma mapping as a settled camera-wide correction. Averages must not hide skin or saturated-colour regressions.

The private visual comparison shows **tone only**, with corrected references, so it does not imply that the unaccepted chroma trial has been adopted.

## Highlight and parameter-bound findings

All four primary tone fits reach the q lower bound of 0.4. A labelled sensitivity experiment lowers the allowed bound to 0.1, still trains only on the other three scenes, and recalibrates held-out brightness only on calibration tiles. All four wider fits reach that new bound too. Their first-phase RGB MAEs are 3.474 / 3.570 / 4.179 / 5.262, better than the primary fits, but the primary results are retained to avoid choosing bounds from held-out scores.

This confirms that a simple shared mapping is useful, while the exact shoulder shape is not identified within this family. It calls for an explicit highlight-curve model or firmware-derived curve comparison. We did not repeatedly expand bounds until a desired score appeared.

Before output clipping, primary tone results have out-of-gamut fractions of about 0.36%, 0.34%, 2.89%, and 0% on first-phase scoring masks. Those pixels remain in the reported metrics; clipping is not silently removed. The high-ISO portrait needs particular attention to highlights, noise and skin colour.

After the four-fold tests, a single all-four tone candidate was fitted for subsequent offline experiments. Its coefficients and source-cache hashes are private. That final fit has no additional independent validation, is not used to inflate the holdout scores, and is not deployed to Android.

## Verification and files

- All four existing source caches were hash-checked unchanged. No new RAW decoding or modification was necessary.
- Four tone/chroma folds, two disjoint scoring layouts, both reference types, and four wider-bound sensitivity fits completed.
- Five synthetic tests pass: monotonicity/anchors/identity, preservation of pre-clip linear chromaticity, guarded tile separation, standard colour-primary and neutral conversion checks, and recovery of a known tone curve and exposures.
- The comparison panel was visually inspected. No public CI run is claimed.
- Original photographs, input identities, private hashes, fitted model arrays, caches and photographic panels remain outside the public repository. Public files contain original analysis code, methodological descriptions and aggregate scores.

Source is under `hasselblad_native_audit/isp_3fr_stage41k/`, safe evidence under `evidence/stage41k/`, and this report under `handoffs/`. It imports Stage41J's baseline helpers from the adjacent `isp_3fr_stage41j/` directory and uses its pinned `requirements41j.txt` environment.

```bash
python -m unittest discover -s . -p test_math41k.py -v
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python test_shared_render41k.py \
  --cache-dir /private/stage41j/baseline \
  --private-dir /private/stage41k \
  --receipt /private/STAGE41K_SHARED_TONE_HOLDOUT_SAFE.json \
  --preview-space DisplayP3
```

Reference definitions: [W3C CSS Color 4 predefined spaces](https://www.w3.org/TR/css-color/), [Adobe RGB encoding registry](https://registry.color.org/rgb-registry/adobergb), [CIPA Exif metadata mapping](https://cipa.jp/std/documents/e/DC-X010-2017.pdf), and [SciPy least-squares loss definitions](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.optimize.least_squares.html).

## Next work

Retain P3-to-sRGB normalization as the explicit working reference policy and keep checking it against the tagged JPEGs. Compare a better constrained highlight/tone mapping with any applicable original firmware gamma/tone evidence. Evaluate chroma regionally, especially skin, saturated red and sky, before accepting a shared correction. When relating this work to the phone, retain the existing camera-to-common-colour-space calibration boundary; these fits do not justify applying Hasselblad sensor-space coefficients directly to phone RAW values. This is an image-level benchmark to inform the firmware-first reconstruction, not a claim to have recovered its internal pipeline.
