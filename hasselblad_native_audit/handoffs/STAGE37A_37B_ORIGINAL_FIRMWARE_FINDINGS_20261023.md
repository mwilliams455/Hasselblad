# HasselbladPhoton — Stage37A/37B exact original firmware result

**Date:** 2026-10-23 (UK)  
**Scope:** X2D II 100C official firmware **1.3.16.2**, ARM MAIN CCM **candidate ownership**, not photographic pixel rendering.  
**Recovery branch:** `recovery/awb-rebuild-20261021`  
**Authoritative CI runs:** [37A original static audit](https://github.com/mwilliams455/Hasselblad/actions/runs/39908604001) **success**; [37A + 37B original callsite audit](https://github.com/mwilliams455/Hasselblad/actions/runs/39909210812) **success**.  
**Exact Stage37B source commit:** `2b96e20a6f812da7e69e0a7817fcbedbdf54f1e9`  
**Main:** No merge or change. **Last user-tested APK** remains Stage36 `27190`, and saved photographic colour remains Photon.

## Source and output controls

The Stage37A script `hasselblad_native_audit/isp_main_stage37/inspect_main_ccm_cpu37.py`, Stage37B script `inspect_main_ccm_calls37b.py` and workflow `.github/workflows/hb-stage37-cpu-main-ccm.yml` have exact-source SHA-256 guards for original AArch64 binaries. Both runs downloaded and verified the 364,814,336-byte official firmware archive with SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`, ran only static original-code inspection and synthetic tests, and deleted original firmware before publishing a sanitized JSON artifact. Neither run executed camera firmware, exported vendor coefficients/instructions, read user images, or changed the Android camera renderer. Stage37A synthetic **14/14** and Stage37B synthetic **10/10** passed.

## Stage37A — bounded original ARM function triage

| Original component | Named function candidates in bounded scope | Examined | Unresolved named arithmetic leads |
|---|---:|---:|---|
| `system/lib64/librcam.so` | 77 | 60 (cap) | **3** |
| `system/lib64/libdcam_pp.so` | 7 | 7 | **0** |
| `system/lib64/libdcam_pp_base.so` | 3 | 3 | **0** |
| `system/lib/modules/vcam_driver.ko` | 23 | 23 | **0** |

The three unresolved candidate names in the original `librcam.so` were `main_ccm_calc_frame`, `main_ccm_calc_global` and `main_ccm_calc_mode`. The heuristic asked only whether a selected named function contains arithmetic multiplication plus memory reads/writes. It did **not** establish that those instructions consume photo RGB or output corrected pixels. Searches are bounded by symbol names, function sizes, selected files, and a 60-function inspection cap; unknown indirect, stripped, DSP or hardware routines remain unexcluded.

## Stage37B — actual original AArch64 direct-call provenance

Original static ARM64 `BL` callsites for the three routines were resolved against the exact symbol tables, with PLT imports recorded only under their verified ordinal layout. Every function had **9 direct calls**.

| Resolved call target | `main_ccm_calc_frame` | `main_ccm_calc_global` | `main_ccm_calc_mode` |
|---|---:|---:|---:|
| `DjiIsp_Reg_Set` | 2 | 2 | 2 |
| `rcam_adj_calc_common` | 2 | 2 | 2 |
| `DjiIsp_ValidateDataNodeByAttr` | 3 | 4 | 4 |
| Stack-check fail PLT | 1 | 1 | 1 |
| `assert_handler_noarg` | 1 | 0 | 0 |

**Interpretation:** These three source-named MAIN CCM routines demonstrably reference register submission, node validation and an adjustment-calculation common path. That strongly supports **configuration/control-plane** ownership, not a newly discovered photographic pixel transform. The static source call list does not by itself prove how every argument is typed or exclude indirect/image-processing paths; no camera pixel-buffer ABI or original same-stage input/output oracle was recovered.

## Pixel-equation truth table

| Technical claim | Status after Stage37B |
|---|---|
| Exact firmware provenance and validated ARM candidate scan | **PROVEN** within the bounded analysis |
| Calls from 3 MAIN CCM functions to `DjiIsp_Reg_Set`, node validation and `rcam_adj_calc_common` | **PROVEN direct-call relationships** |
| Three named routines are likely parameter/control code | **Strongly indicated**, not a complete buffer-ABI proof |
| Six signed `lmtx_fw` entries per 16 groups and original coefficient preparation | **Previously proven** in Stages17/25/27 |
| Eagle2 MAIN CCM **per-pixel** six-coefficient equation, channel order, Q scale, rounding, clipping, group selector | **NOT PROVEN** |
| Original MAIN gamma interpolation and LUT per-pixel sampler/domain | **NOT PROVEN** |
| Isolated original ISP before/after CCM pixel oracle | **NOT AVAILABLE** in current evidence |
| Authentically matched Hasselblad photographic colour/HNCS on Android | **NOT PROVEN** |
| Stage36 source-bound real DNG linear reference comparison | **Previously device-verified**, **not HNCS** |

## Next meaningful gate

Do **not** repeat another broad search of `main_ccm_calc_*` or the known CCM setter/debug accessors without new evidence. Their direct named call relationships now point toward IQ parameter/control preparation, not an isolated original RGB pixel operator. For actual firmware-equivalent Android colour, seek one of:

1. A **MAIN-specific Eagle2/YUV-PP hardware register-and-pixel mathematical specification** for `lmtx_fw`.
2. An **original X2D II hardware or software pixel oracle**, measuring identical before/after MAIN CCM pixels with gamma/LUT disabled or locked and the six coefficients controlled.
3. A newly discovered, genuinely **callable software implementation of the same exact original stage**, with source/provenance and sample-domain ABI resolved.

If those routes remain unavailable, document the hard evidence boundary; do not label a guessed 3×3, fixed-point shift or independent Phocus colour model firmware-equivalent. A separate, honestly labelled experimental Phocus or colourimetric mode could be built later, but no production photo swap or new APK follows from Stage37A/B alone.
