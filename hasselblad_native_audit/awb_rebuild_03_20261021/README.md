# Hasselblad Photon — lost AWB stages checkpoint 03

**21 October 2026** · `AWB_LOST_STAGE_REBUILD_03` · Owned source/harness; **not original-firmware equivalent**

## What was actually implemented here

This is executable source for the boundary *after* Checkpoint 02's RAW -> 1024 4-CFA block bridge and *before* the original scene estimator/optimiser:

1. **Explicit per-block calibration replay (`hb_awb_apply_explicit_calibration`).** The caller supplies four Q16 channel gains and biases and an optional per-block spatial Q16 gain. The portable C11 implementation computes `trunc0(trunc0(site_sum_q16 * channel_gain / 65536) * spatial_gain / 65536) + sample_count * bias_q16` and retains signed negatives. Separate truncation boundaries are intentional *in this owned contract*, not claimed original firmware rounding. Checks reject overflow, invalid coefficients and unknown inputs without modifying the output. No X2D sensor calibration is transplanted.
2. **Evidence-only AE preparation (`hb_awb_prepare_raw_ae_evidence`).** The original RAW black-subtracted block brightness remains separate from calibrated colour channels. Output records signed block/frame raw means, saturated and below-black fractions in integer parts per million, counts and conserved sample totals. It does **not** perform Hasselblad's original AE policy, E2 vendor brightness or exposure recommendation.
3. **Classifier/zone replay interface (`hb_awb_scene_prepare_bounded`).** Only *externally supplied* final weights, classifier acceptance flags and zone overrides are accepted. Classifier-rejected nonzero weight requires explicit zone provenance; unexplained cases are rejected as unsupported. After documented 4- or 8-connectivity component filtering (original topology still unknown), surviving signed calibrated channel sums and **uncalibrated** brightness accumulate. Zone-only survivors remain eligible. Exactly which blocks the original classified, how it calibrated statistics and the original scene/zone weight formula are **not known**.
4. Preserves all Checkpoint 01/02 recovered components and tests. Results are never labelled fresh Hasselblad white balance: `produces_selected_neutral=0` and all `vendor_*_equivalence_proven` flags remain zero.

This checkpoint implements an owned, auditable **replay and integration boundary**, not Hasselblad calibration/AE/classification algorithms. The generic coefficients and scene masks used in the included synthetic and private-DNG tests are test fixtures, not measurements of either sensor's calibration.

## Test evidence newly executed

Run `make check` with GCC C11, Python 3, numpy. Optional: use Clang to build `tests/test_scene_prepare.c` with `src/*.c` at `-O2` and `-fsanitize=address,undefined` separately.

| Test | Fresh result |
|---|---|
| Inherited Rebuild 01 optimized and GCC ASan/UBSan | 33,327 C assertions per configuration |
| Inherited Rebuild 02 optimized and GCC ASan/UBSan | 33,960 C assertions per configuration |
| New Rebuild 03 optimized and GCC ASan/UBSan | **801,012 C assertions per configuration** |
| New Rebuild 03 Clang optimized and Clang ASan/UBSan | **801,012 C assertions per configuration** |
| Independent Python arbitrary-precision Q16/per-cell/zone/BFS replay | **64** complete 1024-block synthetic fixtures |
| Inherited independent NumPy RAW reference | **64** synthetic RAW frames |
| Inherited Python candidate accumulator | **256** fixtures |
| Inherited independent Python component reference | **1,408** fixtures |
| Preserved private Native1C 4096x3072 DNG | **1024/1024** raw blocks independently checked; all 1024 per-block explicit-calibration and replay checks passed |
| Original X2D `libaaa.so` ARM64/state replay | **NOT RUN**: vendor library/initialized original seven-frame harness absent |

The DNG used solely for local testing was pinned by SHA-256 `4a275648d6490ad32c156bedf1abd1d08618e942ca658893d4374ac93e23101a`. It and the unredacted capture sidecar were intentionally **excluded** from the source archive/GitHub. See `evidence/PRIVATE_REPLAY_SUMMARY.json` for a sanitized, aggregate-only status report.

The deterministic arbitrary-precision Python oracle was implemented independently of the production C arithmetic guards and compares the two sequential truncation steps, per-block provenance, filtered weighted colour sums and raw brightness. These checks prove **our own explicit contract**, not the original vendor's numerical behaviour.

### Re-run the private capture (if you have it outside Git)

```sh
python3 tests/test_scene_prepare_python.py \
  --private-dng /private/IMG_20261020_062344.dng \
  --report /private/private_replay_summary.json
```

## Technical blockers before old 20 October AWB research is truly restored

The historical record cites missing checkpoints `8d92116`, `674b571`, `d6c9327`, `fa6a996`, `d7f6c48`, `9a9f7a1`, `0ca6c2f`, `ef32d015` etc. They describe stages, not replacement source. Next milestone needs the genuine firmware 1.3.16.2 original `libaaa.so` with SHA-256 `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`, its calibration/AE E2 ABI, correctly initialized context+config and original ARM64 harness/fixtures, to confirm:

1. Per-block E2 field meaning, scale/rounding/units, Bayer channel ordering and 32×32 binning.
2. Original calibration, AE computation, scene classification and zone weighting, including connected-component neighbourhood rules.
3. Candidate optimizer math and **caller-side count updates** (explicitly recorded in historical research).
4. History/correction, atmosphere, calibrated CT/tint, post stages and outer completion, comparing full 920,560-byte context, 1,000-byte REAWB handle and original statuses in the *same execution*.
5. General multiple-scene iteration, earlier lifecycle, optional active REAWB only if real configuration requires it.
6. Only then bridge to phone sensors using phone-specific calibration and prove one-time WB applied to signed RAW-to-linear rendering.

Preservation target: `mwilliams455/Hasselblad` branch `recovery/awb-rebuild-20261021`. No original firmware binaries, vendor LUT/calibration blobs, protected pixel data, sidecars or APKs in GitHub. Installed Native1C `27179` remains untouched. No new APK is produced by this checkpoint.