# Stage 41J — Four real X2D II RAW/reference comparisons

2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.

Four supplied 3FR files now have a reproducible conventional RAW rendering baseline, aligned to their own embedded rendered previews. All four supplied JPEGs were matched to those previews in the intake investigation. This stage establishes a useful measurement basis and identifies tone/brightness and blue chroma as concrete investigation targets. It does not implement HNCS or recover the internal MAIN CCM equation.

Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`. No Android code, saved-photo pipeline, firmware tuning, or APK was changed. Private photographs, calibration arrays, source filenames, input hashes and the private contact sheet are excluded from this repository.

## Input and decoding checks

The four files identify as X2D II 100C, capture software **1.1.6.3**. The firmware under investigation remains **1.3.16.2**. These samples are a valid earlier-version end-to-end reference set; they are not evidence that those firmware versions render identically.

Each file stores 105,255,168 uint16 CFA samples in an 8842 by 11904 array. LibRaw 0.22.1, through rawpy 0.27.1, unpacked every sample identically to direct memory-mapped TIFF storage. This independent decoder comparison passed for all four full arrays. Original-file hashes were unchanged after processing. Hashes and identity mappings are retained only in a private local ledger.

LibRaw identifies an RGGB Bayer layout, with RGBG channel indices `0,1 / 3,2`. Its normalized as-shot RGB white balance agrees with the inverse of the file's AsShotNeutral to approximately machine precision. The applied RGB gains were checked again after processing. Decoder white levels agree with file metadata. No new AWB policy was introduced.

Two preprocessing differences needed an explicit policy:

- LibRaw reports the full sensor as its visible image and does not apply the file's `DefaultCropOrigin=(128,96)` and `DefaultCropSize=(11656,8742)`. The harness applies that crop before orientation. The resulting geometric registration supports this choice.
- Decoder per-channel black levels differ from the declared scalar level by -3 through +2 counts across the set. The baseline explicitly uses the declared scalar black level, with zero additional per-channel offsets. This is a documented baseline choice, not a finding that LibRaw's estimated levels or Hasselblad's own corrections are wrong. These tiny offsets do not explain the large brightness difference.

The baseline requests half-size Bayer reduction, camera WB, linear sRGB primaries, uint16 output, fixed brightness 1, no automatic brightness, disabled maximum adjustment, explicit metadata black and white, and clipping highlight mode. It applies the declared crop and orientation, downsamples in linear light, then uses an explicit sRGB transfer function. LibRaw's conventional colour conversion remains part of this baseline; its matrix is not labelled Hasselblad's MAIN CCM.

## Alignment and measurement

The analysis resolution is 768 by 576 for A and 576 by 768 for B–D. Grayscale SIFT correspondences and a RANSAC similarity transform register each RAW render to its embedded preview. There are 86–1522 inliers per image, with median inlier errors of **0.15–0.61 pixels** at this analysis resolution. Estimated scale corrections range from 0.9982 to 1.0064. This is sufficient for bounded low-gradient colour comparisons, not a claim of exact optical or pixelwise equivalence.

The metric mask excludes borders, high-gradient detail, reference values near black/clipping, and baseline linear values near black/clipping. It retains roughly 93k–290k pixels per scene. One scalar linear-light brightness multiplier is fitted independently for each image. Evaluation uses the same mask as fitting: the results below are descriptive within-image improvements, **not held-out validation**. The exposure values are adjustments to this specific baseline, not camera exposure recommendations.

The embedded previews have no ICC profile; interpreting them as sRGB is an explicit assumption. The supplied JPEGs have sRGB ICC profiles and are also measured independently after profile handling. Preview and supplied JPEG are not numerically interchangeable: their masked RGB MAE ranges from 1.24 to 4.05 on an 8-bit scale. Use the same-file preview as the principal rendering reference, and the tagged JPEG as a secondary check. Their differences may include export processing, resizing and compression.

| Pair | Fitted brightness | Initial RGB MAE | After brightness only | Reduction | Median DeltaE76 after brightness |
|---|---:|---:|---:|---:|---:|
| A | +1.459 EV | 22.03 | 7.69 | 65.1% | 3.83 |
| B | +0.634 EV | 24.98 | 6.45 | 74.2% | 2.68 |
| C | +2.077 EV | 36.58 | 7.91 | 78.4% | 4.44 |
| D | +0.541 EV | 21.82 | 8.19 | 62.4% | 7.56 |

RGB MAE is the mean absolute channel difference on a 0–255 scale. DeltaE76 is a rendered-image difference under the stated sRGB/D65 interpretation, not colour-chart accuracy or a claim of perceptual equivalence. Residuals include tone, colour conversion, optics, noise, sharpening and registration. Any clipping introduced by the fitted brightness multiplier is part of the measured result.

## Concrete first colour target

A manually inspected clear-sky region in D was measured separately, using normalized coordinates `(0.10,0.06)` to `(0.85,0.23)` intersected with the existing mask. It contains 56,592 eligible pixels.

After the global brightness fit, the median signed baseline-minus-preview Lab differences are approximately **(-2.95, +4.00, -6.34)**: the baseline remains darker, with a positive-a / negative-b colour displacement. Its median chroma is about **6.19 Lab units higher**. The same region compared with the independently tagged JPEG still shows a positive-a / negative-b displacement and about **3.09 units higher chroma**. Median a/b distance is about 7.50 against the preview and 7.43 against the JPEG.

This supports investigating a blue/magenta chroma mismatch after brightness normalization. It does not isolate an internal firmware block, establish a camera-wide hue correction, or justify applying a sky correction to the phone. The large global brightness improvements also make tone/exposure mapping an immediate prerequisite for interpreting candidate colour transforms.

## Validation and reproduction

Local validation completed:

- Four complete real sensor arrays agree with the independent stored TIFF data; all originals remain unchanged.
- All four camera-WB and white-level checks pass, and applied WB is checked after processing.
- All four image registrations meet the bounded geometry and coverage assertions.
- Five synthetic numerical/geometry tests pass: sRGB round-trip and breakpoints, crop/orientation order, invalid-crop rejection, known exposure recovery, and subpixel translation/direction recovery.
- The contact sheet was rendered and visually inspected. Images and private caches are not uploaded to public CI. No GitHub Actions run is claimed for this stage.

From `hasselblad_native_audit/isp_3fr_stage41j/`, install `requirements41j.txt`, then:

```bash
python -m unittest discover -s . -p test_pairs41j.py -v
python compare_hasselblad_pairs41j.py \
  --manifest /private/pairs.json \
  --private-dir /private/baseline \
  --receipt /private/STAGE41J_REAL_3FR_BASELINE_SAFE.json
python summarize_pairs41j.py \
  --receipt /private/STAGE41J_REAL_3FR_BASELINE_SAFE.json \
  --private-dir /private/baseline \
  --panel /private/comparison.png \
  --region-label D --region-box 0.1 0.06 0.85 0.23 \
  --region-name 'clear sky; inspected manually'
```

The manifest is a JSON array of `{ "label": "A", "raw": "/private/input.3fr", "jpeg": "/private/reference.jpg" }` entries. Labels A–D bind to the private input ledger. The summary script optionally accepts a private names JSON for contact-sheet labels. Do not commit the manifest, private ledger, source images, caches or rendered panels. Inspect aggregate receipts before publication.

The safe receipt is under `evidence/stage41j/`; the source and requirements are under `isp_3fr_stage41j/`. Package documentation used to specify the conventional baseline: [rawpy Params](https://letmaik.github.io/rawpy/api/rawpy.Params.html) and [rawpy RawPy](https://letmaik.github.io/rawpy/api/rawpy.RawPy.html).

## Next bounded experiment

Use these aligned references to separate tone mapping from chromatic residuals before evaluating the next firmware-derived colour candidate. A shared tone mapping experiment should report per-scene and leave-one-scene-out behaviour; do not present four per-image brightness fits as a deployable universal rendering rule. Track blue sky, red, neutral and skin regions independently so an improvement to D cannot conceal a regression in A–C. Continue pursuing the original MAIN CCM semantics, with this dataset now providing an external image-level check. No additional RAWs or firmware update are required to begin that work.
