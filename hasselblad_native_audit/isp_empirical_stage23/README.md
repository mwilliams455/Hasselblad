# Stage 23 — Genuine X2D II RAW + camera JPEG reference (offline, no render)

**2026-10-22 | Research branch `recovery/awb-rebuild-20261021` | Strictly no phone renderer changes**

## Purpose

Stage 22 showed that genuine X2D II sRGB/P3 `MAIN_3DLUT` banks do not identify an unambiguous RGB channel ordering by standard gamut conversion. Another LUT plausibility score will not recover a physical MAIN pixel input/output oracle. Stage 23 begins a parallel **empirical source-of-truth comparison** with genuine paired images.

An independent public HNCS measurement project, `songjiun10-collab/Hncs`, documented nine same-session X2D II 100C ColorChecker RAW+JPEG captures from a contributor in its [issue #4](https://github.com/songjiun10-collab/Hncs/issues/4). Their manifest is pinned by Git commit `5f1dd7e8f4fa64b16032842e4be50208c16a4140` and Git blob SHA `eddba2570ba2d19f443920483e5228685830127f`. The 24-patch chart captures were from the **same short session, same ISO 50, auto WB, single illuminant not measured**, not nine independent scene/light conditions. The JPEGs were provided as **in-camera** rendering, *not default Phocus TIFFs.* One chart pair, `B_31325.3FR` + `B_31325.JPG`, is the pinned Stage 23 smoke input.

The external project's report `camera_native_matrix_report.json` is valuable independent evidence: its `AsShotNeutral` `[0.36879,1,0.59168]` and native-decoded neutral `[0.40938,1,0.49396]` are expressed under different channel scaling conventions. Its measured matrix-fit improvement is **LibRaw 7.81 ΔE00 → chart-fit 2.83 ΔE00 (leave-one-image-out)**; this characterizes camera-to-XYZ, *not* in-camera HNCS/JPEG artistic intent or a Phocus output oracle. **Do not insert those numeric matrices into the phone app.**

## Implementation

- `src/pair_math23.py`: independently authored bounded 24-patch CIEDE2000 comparison of two **explicitly declared sRGB display-domain** interpretations. Compares LibRaw-derived camera-WB, no-autobright, linear-sRGB output versus the contributed in-camera JPEG's SDR base image, both before and after **one global exposure-scale** estimate based on six neutral ColorChecker patches. This is a *difference measurement* under one chosen LibRaw decoder, **not evidence that the same look should be ported**. The output is aggregate-only (mean/median/p95/max ΔE, neutral/chromatic partition and neutral exposure scale). Preflight rejects mismatched provenance, missing chart, mismatched patch shape and a false claim of a Phocus TIFF.
- `src/download_public23.py`: enforces an exact immutable public upstream manifest, two `https://drive.google.com/file/d/.../view` records, known camera/stem/ISO/chart labels and bounded downloads with required TIFF/3FR and JPEG signatures. **All photos remain in a temporary Actions workspace and are deleted; none are uploaded.** Downloading other files or arbitrary URLs is not supported. The upstream contributor remains the source; do not redistribute photos or original binary data.
- `src/run_public_pair23.py`: checks pair capture stem, camera model, ISO, and `DateTimeOriginal` (≤2 sec) with ExifTool; generates 16-bit LibRaw linear-sRGB half-size **diagnostic** samples without auto brightness; converts the camera JPEG's embedded ICC to sRGB when available; downsamples promptly to avoid loading 100 MP arrays as float64; detects the 24 ColorChecker patches **independently in each source** with OpenCV's `mcc` module; compares central chart-patch means through the bounded `pair_math23` arithmetic. JPEG gain maps, if present, are deliberately not decoded. Chart detection failure, unavailable public downloads or missing EXIF is a real research blocker, not a permission to invent measurements.
- `.github/workflows/hb-isp-stage23-reference-pair.yml`: local synthetic and provenance controls, pinned source guard, then a single real RAW+JPEG trial on an ephemeral GitHub runner; only aggregate JSON is published as an Actions artifact. No proprietary X2D firmware image, photography samples, pixel arrays or tuning payloads enter GitHub.

## Scientific boundaries

This test does **not** isolate the physical `MAIN_CCM` six-coefficient pixel equation, MAIN gamma interpolation, the original 3D LUT channel order, ISP hardware output or its working space. It does not fit a 3D LUT, discover the true Phocus colour transform, calibrate phone WB, enable HNCS, support gain-map HDR or re-render a photograph. LibRaw's colour transform, WB and demosaic are independent modelling choices and are part of the observed discrepancy. The contributor's scene illuminant was **not measured** and the camera `AsShotNeutral` is not a calibrated neutral target. A chart comparison is not a substitute for diverse matched scene pairs or a first-party Phocus TIFF export. The 9-frame chart burst counts as **one lighting session**, not independent illumination coverage.

### Result semantics

- `PASS_synthetic_arithmetic_and_provenance`: numerical controls only; no downloaded photos.
- `completed_with_comparable_chart_patches`: real files were fetched and verified, the same physical ColorChecker was detected separately in both renderings, and a *real camera JPEG versus LibRaw* residual was measured.
- Any other error: original reference data or program failed; do not claim Stage23 original-photo validation.

## Run (offline synthetic)

```sh
python3 hasselblad_native_audit/isp_empirical_stage23/src/pair_math23.py --selftest
python3 hasselblad_native_audit/isp_empirical_stage23/src/download_public23.py --selftest
```

## Real reference (ephemeral only)

```sh
export PAIR_TEMP=$(mktemp -d)
python3 hasselblad_native_audit/isp_empirical_stage23/src/download_public23.py --destination "$PAIR_TEMP"
python3 hasselblad_native_audit/isp_empirical_stage23/src/run_public_pair23.py \
  --raw "$PAIR_TEMP/B_31325.3FR" --jpeg "$PAIR_TEMP/B_31325.JPG" \
  --output /tmp/STAGE23_ORIGINAL_PUBLIC_AGGREGATES.json
rm -rf "$PAIR_TEMP"
```

Original images must be handled within the rights and limitations of the public contributor's sharing terms. This repository does not distribute those images. No external rendering source is executable by these research modules.

**Next scientific gate:** multiple independent X2D II same-shutter RAW+camera JPEG+**default Phocus TIFF** samples with an explicitly recorded illuminant/colour-chart target and several scene types; these can validate a real phone-to-HNCS approximation without pretending it matches the ISP instruction-for-instruction. The original pixel hardware oracle remains an independent goal. Phone baseline Stage8 `27186` remains unchanged; `photographic_render_authorized=false`.

## Completed original-image result (22 October 2026)

Exact published source: `kmichels-x2dii-2026-07` first pair `B_31325`; immutable Hncs manifest `eddba2570ba2d19f443920483e5228685830127f` at commit `5f1dd7e8f4fa64b16032842e4be50208c16a4140`. Authored research commit `41bc0e3722815f14b8bfe4003e33b3888e39eb77`; GitHub Actions run **39800282664**, with all job steps marked passed, retrieved artifact `Hasselblad-Stage23-Original-Camera-Reference-Metrics.zip`. The camera RAW and JPEG downloaded successfully into the temporary runner, were verified as the same source stem and X2D II camera, ISO50 with zero-second EXIF capture-time difference, and both yielded all 24 independently detected chart patches. Downloaded image bytes were deleted locally after the run and excluded from public source/artifacts.

The public aggregate-only result is `STAGE23_REFERENCE_PUBLIC_AGGREGATE.json`:

| Mean colour difference (CIEDE2000), 24-patch ColorChecker | Rawpy vs camera JPEG |
|---|---:|
| Unmodified LibRaw interpretation | **4.59745** |
| Following a single neutral-exposure scale of **1.11921×** | **3.37876** |
| Chromatic patch mean, exposure-scaled | **3.42121** |
| Neutral patch mean, exposure-scaled | **3.25140** |
| 95th-percentile patch discrepancy, exposure-scaled | **5.17445** |

The JPEG had **no embedded ICC profile**, so its SDR base is interpreted as sRGB (an assumption retained in the result). The original gain map, if any, was not decoded. The reference is the camera JPEG, **not a default Phocus export or physically characterized scene illuminant**. The experiment is one 24-patch chart from one lighting session and cannot support a measured illuminant-dependent interpolation rule, generalize to diverse scenes, prove the true six-coefficient MAIN CCM equation, or validate our Stage21 MAIN sampler's physical RGB ordering. Colour difference is relative to an explicitly chosen LibRaw colour/WB/demosaic path, not absolute colourimetric accuracy or camera-to-XYZ truth.

**Engineering consequence:** A real same-capture X2D reference comparison is now operational. The next gating data are genuine separately identified **camera JPEG and default Phocus 16-bit TIFF** exports under multiple lighting situations, ideally accompanied by measured ColorChecker illumination and varied real scenes. Comparing different decoding paths with the same TIFF/JPEG reference will identify which differences belong to basic RAW colour restoration and which to Hasselblad-specific artistic rendering. Do not optimize a production look based on one chart and one illumination.
