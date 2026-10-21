# Hasselblad Photon — lost-stage reconstruction checkpoint 02

**Prepared:** 21 October 2026  
**Checkpoint:** `AWB_LOST_STAGE_REBUILD_02`  
**Status:** executable OWNED frame/statistics bridge + candidate accumulation; **NOT original E2 or scene-estimator equivalence**.

## Result and exact reconstruction boundary

Checkpoint 01 already recovered a bounded Q12 primitive, outer-confirmation/result-restoration fragment, supported scene/no-eligible gates, shading selection, publication validity rules and four/eight-connected component filtering. This second checkpoint keeps those sources and adds:

- `src/hb_awb_frame_stats.[ch]`: complete RAW_SENSOR (16-bit little endian, row/pixel stride, explicit crop, explicit Bayer pattern and **per-physical-site Q16 black**) to 32×32 block adapter. Each block contains four *separate* CFA colour-site signed black-subtracted sums/counts (R, green on red row, green on blue row, B), raw brightness **arithmetic sum**, original min/max, at/above/over sensor white counts and at/below black counts. No clipping, normalization to [0,1], WB, CCM, demosaicing, tone, LUT, highlight repair or scene-dependent ABLC is performed. Sensor white is diagnostic threshold, not sample clamp.
- Bayer **2×2 quads** are assigned to one of 32×32 cells using integer partitioning in the crop-relative quad domain. This avoids CFA phase jumps for uneven crop sizes. The exact vendor E2 bin geometry/units **were not preserved**; this mapping is a documented owned *provisional* choice and must not be called the original implementation.
- `hb_awb_accumulate_owned_candidates`: the Rebuild 01 connected-component filter is wired to caller-provided scene weights and optional classifier acceptance. A block with zone weight but classifier-rejection can contribute. The actual original weight assignment/zone rules **are unknown**, so callers must provide already computed weights; 4/8 adjacency must be selected explicitly; user-defined weights are limited to 0–32 to bound signed arithmetic. The function does not manufacture an AWB colour temperature or neutral.
- Explicit invalid-input and arithmetic-overflow rejection without partial caller-output publication.
- Independent C/NumPy/Python checks and a **private** actual Native1C DNG replay.

**Supported provenance:** the preserved 20 October conversation records an original E2 route operating on 32×32=1024 blocks, preserving brightness, and post-filter candidate accumulation. It does **not** contain the lost vendor field-layout/weight equations, exact per-block calibration or connected-component neighbour topology. Nothing in this checkpoint makes those unknowns known.

## Fresh checks, not historical counts

Run `make check` in this directory. This compiles and runs GCC optimized+ASan/UBSan test sets, independent Python reference checks and the previous Rebuild 01 checks.

| Boundary | Fresh verification |
| --- | --- |
| Rebuild 01 optimized C | 33,327 checks passed |
| Rebuild 01 GCC ASan/UBSan | 33,327 checks passed |
| Rebuild 02 frame/accumulation optimized C | 33,960 checks passed |
| Rebuild 02 GCC ASan/UBSan | 33,960 checks passed |
| Rebuild 02 Clang optimized C | 33,960 checks passed |
| Rebuild 02 Clang ASan/UBSan | 33,960 checks passed |
| Independent NumPy integer per-block reference | 64 synthetic random RAW frames passed, all 4 Bayer patterns and padded strides |
| Independent Python candidate accumulation | 256 random weighting and topology fixtures passed |
| Inherited independent connected-component BFS | 1,408 cases passed |
| Private Native1C DNG (4096×3072) | 1,024/1,024 blocks matched independent NumPy 4-channel integer sums, brightness, counts, min/max, white/black diagnostics |
| Alternate fractional dynamic black from captured Camera2 metadata | 1,024/1,024 blocks matched independent NumPy reference with original dynamic 63.9375 instead of DNG-selected 64 |
| DNG + sidecar provenance check | original Camera2 neutral agrees with DNG AsShotNeutral, selected camera/timestamp/frame/raw geometry verified |
| Actual `libaaa.so` / ARM64 seven-frame same-execution comparison | **NOT run — original library and original-frame harness unavailable** |

Reported DNG fixture SHA256 `4a275648d6490ad32c156bedf1abd1d08618e942ca658893d4374ac93e23101a`. The untouched private capture and complete sidecar are **not included**. The tests do not establish colour calibration: e.g., the independent Q16 oracle is a separately implemented check of the newly defined owned mathematics.

### Optional private real-capture commands

```sh
python3 tests/test_frame_stats_python.py --private-dng /private/IMG_20261020_062344.dng --report /private/report.json
python3 tests/validate_private_capture.py --dng /private/IMG_20261020_062344.dng --json /private/IMG_20261020_062344.capture.json --report /private/provenance.json
```

These commands read private files at runtime; never publish those input pixels or full sidecar. The generated reports deliberately avoid pixel arrays and include only verification, geometry and metadata consistency findings. `make check` runs without private inputs.

## What remains before the **lost vendor AWB implementation** can be called reconstructed

1. Retrieve **original** firmware X2D II 100C `1.3.16.2` outside GitHub; verify `libaaa.so` SHA256 `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`. Recover initialized context+config and **same-execution** ARM64 harness/frames. Check exact E2 byte layouts/ABI and 32×32 native binning, brightness, calibrated units and channel ordering.
2. Recover original per-block calibration/AE/classification and scene weighting; test zone-only weighted blocks and the original component traversal/topology. The new owned input adapter is a candidate bridge, not proof it matches firmware stats.
3. Recover scene candidate accumulation numeric equations, optimizer and caller count updates (historical local `9a9f7a1`), history bounded/active correction, atmosphere, post stages through CT/tint and output.
4. Compare original and reconstructed stages in the **same process/execution**, retaining meaningful opaque pointer identity; compare full 920,560-byte context, 1,000-byte persistent REAWB handle, statuses and resulting gain/CT/tint, on seven historical valid/recovery frames plus errors.
5. Rebuild general multiple-eligible-scene loop and earlier full AWB frame lifecycle. Active linked-history REAWB remains future optional coverage unless triggered by the genuine configuration.
6. Only then adapt *legitimately calibrated* phone statistics to the estimator (per physical sensor). Until then never describe this code as producing firmware-equivalent Hasselblad AWB.

## Preservation

- Checkpoint source and test fixtures are original owned code, not vendor source.
- No vendor binaries, protected firmware calibration/LUT data, private photo pixels, capture sidecar, signing keys or generated APKs.
- Commit to `mwilliams455/Hasselblad` branch `recovery/awb-rebuild-20261021`, not `main`, and read back exact files.
- The installed phone baseline remains Native1C, version code 27179; this checkpoint does not generate a new APK.