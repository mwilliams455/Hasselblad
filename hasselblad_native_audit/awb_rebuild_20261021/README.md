# Hasselblad Photon — AWB lost-source reconstruction checkpoint 01

**Date:** 21 October 2026. **Status:** PARTIAL OWNED SOURCE — **NOT** original firmware equivalent.

This source reimplements the *bounded, independently expressible fragments* of the unpublished 20 October X2D II 100C AWB research that can be specified from the preserved conversation ledger. The exact unpublished implementation was lost, and no verified original ARM64 `libaaa.so`, original-frame harness or seven-frame opaque state inputs are present in this runtime. A successful unit test is **not** evidence of a Hasselblad white-balance estimate.

## Recovered source fragments

| Component | What was actually implemented | What remains unknown / unverified |
| --- | --- | --- |
| `hb_awb_recalib.c/.h` | Existing original-derived Q12 dual-gain function preserved unchanged from the Native1A archived source; safe bounded input policy | No new vendor-ARM64 comparison in this checkpoint; never call it a scene estimator |
| `hb_awb_outer_complete_bounded` | 920,560-byte context, 156-byte live/confirmed/reference copies, `0x174` word clear, exact request byte 1, earlier status and final helper-status layering | Helper ABI and copy-call ordering need direct original confirmation; `final_copy_status` is explicitly caller-supplied |
| `hb_awb_select_supported_scene` / `hb_awb_recover_no_eligible` | Supported illumination 0 / scene 3 sole-eligible entry, scene no-eligible status 40 and confirmed-result restore | Multiple eligible scenes, other illuminations, selector ordering, actual scene-estimator code |
| `hb_awb_shading_select_bounded` | Seven supplied u16 label ratios; maximum with **later** tie winner; exact validity 1; reference-vs-normal CT conditions; read/write recorded addresses | Original ratio field offsets, input validity address, live ABI/types and full shading routine |
| `hb_awb_publication_gates` | Validity byte **nonzero** publishes candidate; exact **1** also copies into history; no accidental erase on later failure | Original candidate/history source/destination lengths/offsets/rounding and downstream gates |
| `hb_awb_prune_small_components` | 32x32 weighted-mask connected-component removal for groups <=3, retaining zone-assigned weighted blocks, explicit 4/8 adjacency argument | Original neighborhood topology, wrap/edge traversal, zone-weight generation, per-block calibration and accumulation |
| `hb_awb_clamp_ct` | Recorded 2000–10000 K result bound | Other output-tail arithmetic, return statuses |

All offsets and constraints are from the preserved [Hasselblad mega handoff, 2026-10-21]. Offsets are little-endian, and the original complete run pointer identity may be meaningful only within the same emulated process. The **original session** historically reported seven-frame state matches; these are not freshly reproduced here.

**Status is not freshness:** an outer return of 0 after an inner scene status 40 or post status 151 can be a restored confirmed result. `fresh_estimate_proven` is deliberately always `0` until proper scene-state evidence is available. Even `HB_AWB_ORIGIN_LIVE_PUBLISHED` does not assert that the live result came from a new scene measurement.

## Execute the locally testable subset

```sh
make check
```

`make check` compiles optimized and ASan/UBSan host C tests and tests 32x32 component filtering against an independently implemented seeded Python BFS oracle under both topologies. This verifies the **new bounded reconstruction's own contract only**.

## Restore the vendor equivalence boundary

Provenance of historical target (hashes are pins, not claims that inputs exist here):

- Hasselblad X2D II 100C firmware `1.3.16.2`, Android 9 / ARM64.
- Official firmware CIM SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.
- `system/lib64/libaaa.so` SHA-256 `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`.
- AWB context 920,560 bytes; configuration 1,502,800 bytes; REAWB handle 1,000 bytes.
- Existing original method address `scene_awb_lib_run` at `0x471a38`; last historical prepared scene boundary preceded scene weighting at `0x4a7d48`.

**Next exact comparison gates:**

1. Retrieve/extract the same original firmware *privately* and verify SHA-256 pins. Rebuild API 28 ARM64/Bionic runtime and original-caller harness from private inputs. Do not copy vendor binaries into GitHub.
2. Reconstruct initialized AWB calibration state and native 32x32 E2 frame statistics with actual original source/ABI offsets; preserve brightness and calibrated units. This is essential before claiming scene weighting fidelity.
3. Run *same-execution* original and owned code on seven authentic fixture frames and synthetic edge fixtures. At each supported stage, compare complete 920,560-byte context, 1,000-byte handle, final inner/outer status and selected neutral. `tests/compare_original_owned.py` checks captured same-execution pairs; it is not the missing original harness.
4. Determine original connected-component topology, exact zone weights, label-ratio source addresses, publication buffer layouts, ref-copy call ordering. Replace explicit unsupported branches only after original-backed evidence.
5. Rebuild candidate accumulation/optimizer → history/active correction → atmosphere → post candidate prep → calibrated CT/tint → publication → dual-sync → light-source → override → smoothing → output tail → passive REAWB → outer completion → scene entry. Sync and read-back after each verified stage.
6. Generalize ordinary scene-controller loop to multiple eligible scenes, then earlier frame lifecycle. Keep active REAWB/spectral optional until the actual firmware configuration proves necessary.

## Preservation policy

This checkpoint contains only owned portable source, synthetic tests, a comparator, and execution reports. It contains **no** original firmware, proprietary calibration/LUT assets, original RAW pixels, private capture sidecars, or APKs. Publish to `mwilliams455/Hasselblad` branch `recovery/awb-rebuild-20261021`; do not advance `main` during reconstruction.