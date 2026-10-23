# HasselbladPhoton Stage37C2 — exact firmware kernel-header contract audit

**Date:** 2026-10-23 UK  
**Target:** X2D II 100C official firmware 1.3.16.2, not newer revisions  
**Executed source commit:** `ab5d49a36aeee42c9f0be8c996558f15f19ae944`  
**Validated original-firmware CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39911084313 (**SUCCESS**)  
**Previous Stage37C source commit:** `519489f676824f786d9aae092d42fa9ee3608b66`; CI https://github.com/mwilliams455/Hasselblad/actions/runs/39910561921 (**SUCCESS**)  
**Source/tool:** `hasselblad_native_audit/isp_main_stage37/inspect_ccm_header37c.py`; firmware transient, source-only repository.  
**Phone baseline:** Stage36 signed APK `27190`; *normal photos still use Photon*, no renderer changed.

## Exact proven observations

- Official X2D II 1.3.16.2 CIM validated against its pinned SHA256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` and extracted only in CI.
- `system/lib/modules/kheaders.ko` validated at SHA256 `b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b`. It contains **one valid XZ/tar kernel-header archive**: **9,329** members, **7,740** bounded textual files, **30,049,604** examined text bytes.
- Six archived files contained text matching **Eagle2**, with no *same-file* bounded standalone CCM or YUV-PP term, and no strict `lmtx_fw`, `ccm_set_ig0_config`, `yuv_pp_ccm` or `level_ctrl_inv_lut` hits. The paths were:
  - `./include/dji/mach-eagle2/include/mach/regs/regs-noc.h` — system interconnect/NoC name
  - `./include/dt-bindings/clock/eagle.h` — clock binding name
  - `./include/dt-bindings/reset-controller/eagle2-resets.h` — reset-controller name
  - `./include/dt-bindings/scmi/pd-eagle2.h` — power-domain name
  - `./include/generated/autoconf.h` — kernel generated config
  - `./include/misc/tzasc_cfg.h` — security-controller name
- In `system` and `vendor` extracted paths, **335** bounded text files and **4,827,873** bytes were examined. Only **one** contained `main_ccm`: `system/etc/iq/hb722_ads6401_config.json`. There were **no strict CCM equation anchors** and three files with text matching Eagle2: `system/etc/ac_config.json`, `system/etc/blackbox.json`, `system/etc/et_product_whitelist.json`.
- The scan explicitly skipped four files larger than its 2 MiB limit: `system/etc/iq/hb722_config.json`, `vendor/model/nnf/model/nnpd_depth.json`, `vendor/model/nnf/model/person_detection.json`, `vendor/model/nnf/model/skin_mask.json`. In particular, **the primary IQ file was omitted from this new scan**; Stages17/25/27 already separately investigated its MAIN CCM preparation. The absence of `lmtx_fw` in this run is **not** evidence that the string is absent from the original IQ file.
- The ADS6401 identifier has a credible *depth sensor* association, not a proven alternate photo colour ISP: Adaps Photonics lists ADS6401 as a spot SPAD/dToF sensor family. Source: https://adapsphotonics.com/en/product-55669-206546.html . The config filename alone does **not** establish an active depth-sensor model, actual X2D II hardware installation or RGB colour-calibration pipeline.

## Engineering interpretation and closed route

The embedded Linux header archive yielded no original MAIN CCM coefficient-to-pixel mathematical contract or before/after ISP sample. No exact Eagle2 RGB pixel register-field bit mapping, fixed-point scale, sign interpretation at the multiplier, clipping/rounding, domain or 16-group selector was recovered. Matching platform/header names, common firmware packaging, and an unrelated dToF-named IQ file are not sufficient to infer a colour operator.

**Stage37A/37B remain in force:** MAIN-named `librcam` ARM routines make direct calls to parameter/node checks and `DjiIsp_Reg_Set`, strongly supporting a control-plane role. Prior Stage17/25/27 coefficient preparation, Stage24/36 real Android DNG linear reference, and stage-specific gamma/LUT table copy contracts remain verified *within their scopes*. None proves photographic HNCS.

Do not perform a new generic scan of the same header names. The next original-equivalence gate must come from a **MAIN-specific hardware mathematical reference**, controlled before/after ISP CCM samples on actual compatible hardware, or independently validated callable software implementation of the *same stage*. QEMU UI emulation does not substitute for an ISP pixel oracle (see https://github.com/derrickyau9/Hasselblad-X2D-II-QEMU-DevKit/blob/main/docs/VERIFICATION.md).

## Safety and software status

This audit read inert firmware bytes in temporary CI, verified source identities, ran synthetic tests, deleted original firmware before artifact upload, and published only sanitized counts/path names. No original source contents, firmware binary, numeric private tuning array, user photo, full capture sidecar, or private camera identifier was uploaded. `main` and the Android saved-image processing are unchanged. **No new APK is justified by Stage37C2 alone**.
