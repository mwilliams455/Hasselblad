# Stage12 — Matched-condition MAIN LUT mode audit

**Research-only; no new Hasselblad photographic renderer or mode-dependent LUT switch.** The tested hypothesis is whether normal still, enhanced normal and enhanced HDR choose different photographic `MAIN_3DLUT` tables when colour temperature and output gamut are fixed. This audit **does not execute the original vendor functions**. It tests archived hash-pinned original research and deliberately labels every matched-mode comparison as a **counterfactual prediction**, never as a measured camera output.

## New, bounded conclusions

The inspected 1.3.16.2 IQ configuration contains one 49,152-word `MAIN_3DLUT.lut_data` array, declared `global_frame`, interpolated over `[cc_color_temp, color_gamut]` into a 6,144-word prepared table. The original vendor library's bounded tests for **ten CCT/gamut pairs** previously matched hashes generated independently from that array. There are eight nominal knot profiles but only six unique tables, due to duplicate 2400 K and 3050 K profiles within each gamut.

The original configuration maps:

| Reprocessing path | Mode | MAIN LUT | Gamma | MAIN_HNCS |
| --- | --- | --- | --- | --- |
| `frog_raw_reprocess_2-r2y-still` | still3 | enabled | enabled | bypassed |
| `frog_raw_reprocess_2-r2y-still_scap3_enh_normal` | still0 | enabled | enabled | bypassed |
| `frog_raw_reprocess_2-r2y-still_scap3_enh_hdr` | still0 | enabled | enabled | bypassed |

Both enhanced paths share `still0` in the inspected mapping, and the selected MAIN LUT control flags are enabled for still0–still4. The gamma *curve* is identical across the five modes, but **still4** separately enables knee, so a colour/tone change in another mode is not, by itself, evidence of another photographic LUT.

The prior archived `inspect_pixel_contract.py` inspected **integer arrays with at least 6,144 values whose configuration paths contain `3dlut`, `lut3d`, or `tlut`**. Its six records are one MAIN table, two identical LCDC tables and three identical pyramid tables. No separate `post_hdr` or `post_scap3` table of that size and naming class appears in that **limited scan**. It does **not** rule out smaller parameter arrays, alternate naming, external runtime-loaded LUTs or on-the-fly modifications.

## The mode counterfactual

The audit constructs a *conditional model* for each of the ten archived original `librcam.so` full-camera-data LUT outputs:

> **IF** all three routes actually pass the **same** global source table, exact CCT and output gamut to the verified `_Calc_LerpLutMem3d`/`mm_mx_lerp_vec_mix2` calculation, **THEN** all three receive the same prepared 6,144-word profile hash.

The ten original profile hashes are actual **past original-vendor mathematical outputs for one profile input**, not three separate-mode captures. Their expansion to 30 entries is purely predicted, **not 30 original vendor runs**. A different LUT hash under fixed conditions, if observed via original wrapper/state or hardware traces, would falsify at least one shared-source/parameter assumption and would motivate tracing the override. A same hash would not prove the full rendered images identical because CCM, gamma, tone, postprocessing and DSP may still differ.

The earlier function-call inventory shows:

- `main_3dlut_calc_frame` at `librcam.so:0x39ce88`: two calls to `rcam_adj_calc_common` and two calls to `DjiIsp_Reg_Set`.
- `post_scap3_calc_3dlut` at `0x2f2d08`: two calls to `rcam_adj_calc_common`.
- `post_hdr_calc_3dlut` at `0x301b00`: two calls to `rcam_adj_calc_common`.

**Common dispatcher calls do not identify a common input table or MAIN hardware destination.** The cited `post_*` calls must not be characterized as writing register 2998 without following the argument/control-flow chain. The separately verified MAIN hardware register destination is 2998 / `0xf3208000`; tying those `post_*` callers to that destination is the next evidence gate.

## Reproduction

Run from the exact GitHub recovery branch root:

```bash
python3 hasselblad_native_audit/photographic_mode_stage12/stage12_mode_lut_audit.py --self-test
python3 hasselblad_native_audit/photographic_mode_stage12/stage12_mode_lut_audit.py \
  --output /tmp/STAGE12_MODE_CONDITIONAL_PUBLIC.json
```

This reads seven existing original-source-derived JSON reports from `photographic_path`, `pixel_contract_20261019`, and `main_colour_20261019`, validates their compatible source identities and specific settings, and emits a **small public metadata-only report**. No firmware payload, private phone photographs, original tuning array, APK or proprietary binary are distributed.

## Exact next original-code proof

With the original SHA-pinned `librcam.so` and its Android 9 dependencies available in an authorized runtime:

1. Identify the original parameter descriptor and buffer-source address at both `rcam_adj_calc_common` calls inside `main_3dlut_calc_frame`, `post_scap3_calc_3dlut` and `post_hdr_calc_3dlut` using original AArch64 analysis. Match descriptors against the global `lut_data` IQ getter (`DIQ_iq_main_3dlut_lut_data`) and the MAIN register ID **2998**. Do not synthesize an unvalidated vendor context ABI.
2. Observe the actual selector state and **source table identity** for each path, and whether an enhanced dispatcher uses `_calc_lerp_lut_mem3d_enh` or another parameter type. The unchanged 6,144-word register-copy contract does not establish the *caller* or *source*.
3. Hold **CCT, gamut, source table and calibration constant** while changing one mode. Hash the effective submitted 6,144-word payload in the **actual matched context**. Distinguish an original code-level preparation oracle from physical frame register activation.
4. If mode equality holds, move on to gamma/CCM/postprocessing and scene/AWB inputs instead of inventing a per-scene LUT switch. If it fails, record the controlling condition and branch, then test independent scenes/modes to delimit coverage.

A fresh original-binary test was **not run** for this checkpoint: the Library lists the complete 364,814,336-byte original firmware, but raw-byte materialization of that file was not authorized in this runtime, and the official CDN could not be reached here. This is a source-derived research checkpoint, not a vendor trace or hardware oracle.

## Guardrails

No change to `HasselbladPhoton` source, shaders, RAW, AE, whitePoint, existing Stage8 JNI or JPEG/DNG output. No auto scene LUT switching, HDR/stacking, use of a guessed MAIN/display pixel sampler, vendor file or private capture stored in GitHub. `main` remains untouched.
