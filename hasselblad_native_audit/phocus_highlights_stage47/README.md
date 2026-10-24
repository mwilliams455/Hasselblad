# Stage47 — highlight handling at unchanged room brightness

Date: 2026-10-24. This controlled experiment keeps the Stage46 image-3 profile
(curve0, 4000 K LUT), DNG white balance and exposure fixed. It compares two new
highlight adapters. Neither adapter is claimed to be recovered Hasselblad
processing, and neither is deployed to the app. The portable C core, source
photographs, imported profiles and current defaults are unchanged.

## Result and decision

The output-only candidate gently reduces the brightest displayed values while
leaving 97.2223% of this room preview's RGB pixels exactly unchanged. Every pixel
in the selected skin, wood, blue-wall, sofa and carpet patches is unchanged.
Across 509,471 eligible midtone pixels, both median and 99th-percentile absolute
linear-luminance changes are zero stops. The blinds change by 0.00093 displayed
channel levels on average; the selected white frame changes by 0.00936 levels.

The earlier adapter reduces the channels before the finite film-curve lookup as
well as at the output. It retains stronger colour variation in the TV, including
pronounced pink and cyan. This capture already contains saturated RAW channels,
and no matched reference establishes whether those revealed colours are correct.
Fewer clipped values must not be used as a proxy for colour accuracy.

Retain the output-only result as the conservative visual candidate. Its visual
effect is deliberately modest and does not establish a closer Hasselblad match.
The earlier adapter is an investigative control, not a proposed default.

| Room-preview measure | Current image 3 | Output-only trial | Earlier + output trial |
| --- | ---: | ---: | ---: |
| Pixels exactly unchanged from current | 100% | 97.2223% | 97.2223% |
| Mean absolute channel change, 0–255 | 0 | 0.2144 | 0.8371 |
| TV mean absolute channel change, 0–255 | 0 | 8.0377 | 32.6884 |
| TV pixels with all displayed channels ≥250 | 38.3092% | 0% | 0% |
| TV pixels exceeding the pre-curve upper limit | 81.7640% | 81.7640% | 0% |
| TV pixels exceeding the final linear-sRGB upper limit | 86.7854% | 0% | 0% |

The zero upper-limit results arise from the function's construction. The
output-only candidate cannot recover variation already lost at the earlier
clamps. The thresholds and denominators describe this preview, not the original
CFA sample counts. This is single-frame SDR processing; no fusion is performed.

## Operation and placement

The new function takes the maximum positive RGB component `m`. Below the knee
`k`, it is identity. Above the knee it maps the maximum to:

```text
f(m) = k + (m - k) / (1 + (m - k) / (1 - k))
RGB_out = RGB_in * f(m) / m
```

The function is continuous, has unit slope at the knee, and approaches one
asymptotically. One common positive scalar preserves component ratios in that
domain. This is not a perceptual hue guarantee across a nonlinear film curve
and colour-space conversion. Negative components keep their sign and still
encounter the existing final lower clamp; full gamut mapping is not implemented.

- Output-only: apply the function in linear sRGB immediately before the existing
  sRGB display encoding, with `k=0.85`.
- Earlier + output: first apply it to the reconstructed pre-curve internal RGB
  normalized by 65535, with `k=0.75`, then apply the same output function.

The knees are explicit engineering trial settings, not values extracted from
Hasselblad and not fitted against this room. No local masks drive either render.
Reporting polygons only select areas for measurement. The LUT, film-curve table,
exposure and WB values are identical across all three versions.

## Validation and limits

The unmodified baseline matches all 2,359,296 saved host Java/JNI RGB16 channels
and the displayed RGB8 image from Stage46 exactly. The earlier indoor scene's
baseline also matches its retained RGB16 reference hash exactly. On that second
scene, the output-only trial leaves 98.9891% of pixels unchanged, with a mean
absolute channel difference of 0.04989/255. Its median and 99th-percentile
midtone luminance differences are also zero. This is a second regression scene,
not a new controlled Hasselblad reference.

For each knee, 2,051 independent scalar comparisons pass, including zero and
negative values. Checks also cover exact identity below the knee, preserved
component ratios, upper bounds, monotonic ramps over 200,000 samples and the
unit slope at the join. A 100,001-sample neutral ramp through the actual film
curve and both adapters has nondecreasing luminance. Nonfinite inputs are
rejected. These checks establish implementation properties, not photographic
fidelity. Source input bytes are checked for immutability.

The room's RAW preparation is reused from Stage46; this stage does not rerun
the decoder or claim another original ARM64 replay. The earlier adapter changes
the operation before the original bounded film lookup, so its output cannot be
labelled an exact vendor render. No camera-sensor calibration is fitted. These
are 1024×768 sampled development previews with orientation applied, not new
full-resolution capture JPEGs.

The next substantial fidelity question is still the phone sensor adaptation and
its comparison to known-settings Hasselblad/Phocus output. A gentle shoulder can
improve the handling of finite sRGB output, but it cannot answer that question.

## Reproduction and privacy

Run `analyse_highlights47.py` with `--dng`, `--java` (Stage46 dump directory),
`--profile` (curve0/4000 K), `--comparison-bundle` (retained curve0 indoor scene),
`--out` (private output directory), and `--safe-receipt` (aggregate JSON path).
It reuses the Stage42/44/46 Python environment. Assertions must be enabled.

Only this source, this README and the aggregate receipt are public. Profiles,
calibration matrices, input hashes, DNGs, reference bundles and comparison images
stay outside public git, CI and APK assets. Private comparison panels are tagged
with sRGB; their JPEG encoding is for viewing, while exact comparisons use the
uncompressed arrays. The single candidate PNG retains the exact preview pixels.
