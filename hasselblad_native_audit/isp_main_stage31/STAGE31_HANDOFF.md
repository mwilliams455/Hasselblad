# HasselbladPhoton — Stage 31 engineering checkpoint

**Date:** 22 October 2026 (Europe/London)  
**Project:** Firmware-first colour reconstruction of Hasselblad X2D II 100C in PhotonCamera/Android  
**Working branch:** `recovery/awb-rebuild-20261021`  
**Original source firmware:** X2D II 100C, 1.3.16.2 (full package and driver SHA-256 pinned)  
**Validated Stage 31 CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39845352893 — **success**  
**Stage 31 test commit:** `0d34d96a703c7feb69868436beea9590f408b7ad`  
**Last device-tested APK:** Stage 26 `0.1-hb-neutral26`, versionCode `27187`, 11/11 synthetic JNI checks passed on Android. **Actual photographic JPEG colour remains Photon**.  
**`main` remained unchanged** at `929f523aa02ae5b224be39b9c36cce5975691a10`.

## 1. Work performed in Stage 31

The strongest firmware-first route after Stage 29 was to examine whether Eagle2's CCM hardware debug interface can provide an isolated **before-/after-CCM pixel oracle**. Stage 31 added two source-only, original-firmware-hash-pinned audits and an ephemeral-firmware CI workflow. Both scripts reject unexpected firmware and export no original instructions, vendor IQ tables, camera images or firmware binaries.

### 31A/31B — inspect actual CCM debug-interface functions

Files:

- `hasselblad_native_audit/isp_main_stage31/inspect_ccm_debug31.py`
- `.github/workflows/hb-stage31-ccm-debug-oracle.yml`

The exact `system/lib/modules/vcam_driver.ko` source SHA-256 is:
`29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e`.

Audited **14 original functions** (12 CCM debug accessors/setters plus two CCM format functions), decoding **90 original AArch64 instructions** in aggregate:

- `ccm_get_dbg_info_by_mux`: **3 instructions**, one 32-bit register-relative read.
- `ccm_set_dbg_mux`: **7 instructions**, a 32-bit read/modify/write.
- Busy/size/error/shadow-ID/counter debug getters: **3–4 instructions each**, a single 32-bit scalar read and no pixel/vector loops in the checked functions.
- `ccm_set_fmt`: 20 instructions; `ccm_set_fn0_config`: 23 instructions; original routine sizes preserved.

The bit-mask arithmetic in the original debug-mux setter **clears bits 0..4** of its destination (`0xffffffe0`), **masks selector input to five bits** (`0x1f`) and combines it into the register. This proves a **0–31, 32-selection control field**. It does **not** establish what those selectors mean, what they return, or whether any selects original input/output RGB samples. The getter returns one 32-bit scalar, not a stream of decoded photo pixels in the inspected CPU routine.

The returned memory operands are relative to CPU address registers; their individual offsets are **not automatically physically mapped MMIO addresses**. No hardware was read or operated.

### 31C — callsite/callback reference search

File: `hasselblad_native_audit/isp_main_stage31/inspect_ccm_debug_callers31c.py`.

The exact kernel `.text` disassembly examined **138,644 AArch64 instructions**, with a scan of ELF relocation records and potential direct local branches. It found **zero direct named CALL26/JUMP26 callsites, zero section-plus-addend text references, zero data-section function-pointer references, and zero unrelocated direct `BL` candidates** to **either** `ccm_set_dbg_mux` or `ccm_get_dbg_info_by_mux` in this same original `vcam_driver.ko` file.

This bounds our currently available evidence. It does **not** prove unreachable code or exclude a loader, userland, indirect call, other firmware component, or unobserved hardware debug mechanism. It certainly does **not** prove a CCM pixel equation. The debug mux is therefore **not currently a credible substitute** for an actual isolated ISP pixel oracle.

The final Stage 31 original-source CI and all tests are **green**: https://github.com/mwilliams455/Hasselblad/actions/runs/39845352893. The retained artifact is `Hasselblad-Stage31-CCM-Debug-Oracle-Safe`; four JSON reports (31A/31B + 31C original and synthetic) contain metadata only.

## 2. Existing hardware facts still proven (Stages 17–30)

- Original MAIN CCM coefficient preparation matches 162 original-code cases / 15,552 scalar comparisons. Four CCT anchors in this **X2D II 1.3.16.2** static tuning are 2400, 3050, 5550 and 9100 K.
- The 16 groups of six signed `lmtx_fw` coefficients map to the **CCM hardware register block** at offsets +0x1cc..+0x348; all groups and both high-ISO banks are equal in the audited static still table. Runtime updates remain unexcluded.
- Original Stage25 register descriptor names show that the neighbouring nine-value arrays +0x34c and +0x370 are **`level_ctrl_lut` and `level_ctrl_inv_lut`**, *not a proved 3×3 CCM*.
- Stage28/29 reconstructed control edges and frame-format register sources, not a pixel equation: `b2r_pad_set_fh_fmt` -> `ccm_set_fmt` -> `ccm_set_fn0_config`; B2R record offsets +8/+12 plausibly relate to frame geometry but are not formally typed.
- Stage24 provides the true DNG ForwardMatrix / camera neutral -> XYZ D50 -> sRGB/P3 **linear neutral colourimetric reference**. Stage30 added opt-in DNG OpcodeList2 GainMap corrections, validated in 28 synthetic cases and host numerical tests under GCC/Clang. There is **still no validated original phone DNG containing the supported opcodes** in our working environment.

### Unsolved, do not extrapolate

The actual per-pixel meaning, scale, channel order, rounding, clipping and stage domain of the six signed `lmtx_fw` coefficients remain unknown. MAIN gamma per-pixel interpolation and 3D LUT sampler/domain are also unproven. No equivalent original X2D II pixel output oracle has been recorded. Stages 24/26/30 do not apply verified photographic HNCS on Android.

## 3. New independent HNCS corroboration (research lead, NOT original X2D II ISP proof)

Two 2026 public research sources provide useful context:

1. Independent reporting quotes **Hasselblad engineering, 19 August 2026**, stating that HNCS is applied to every Phocus RAW rendering as an internal stage strongly linked to white-balance parameters, while vignette/tone adjustments are separate. Source: https://blog.tonalphoto.com/what-hncs-actually-is/ (independent journalist reproducing engineering correspondence; not an official SDK specification).
2. The Apache-2.0 source project `fishvivfish/HNCS-Lightroom` describes a recovered **Phocus 4.0.1 X2D 100C Standard** colour stage. Its indexed `ColorCorrect` anchors are **3100, 5550, 9100 K**, and camera matrix anchors **2400, 3100, 5550, 9100 K**. Its disclosed evaluator has an RGB -> luminance/chroma matrix stage, a 2D CbCr correction texture dependent on brightness/colour and WB, then an output matrix. The **actual recovered numerical colour records are deliberately not distributed**. That target model is **NOT** the X2D II firmware's original MAIN CCM hardware representation. Sources: https://github.com/fishvivfish/HNCS-Lightroom/blob/main/docs/ALGORITHM.md and https://github.com/fishvivfish/HNCS-Lightroom/blob/main/hncs_core/phocus401_wb.py.
3. `shenmintao/V-Log-Alchemy` publishes explicitly daylight-baked X2D Phocus-derived V-Log LUTs using a documented RGB/D50 colour-space chain, film curve and display encoding. This is a camera-space/domain-specific display rendering, not an interchangeable original X2D II hardware pixel operation or a WB-general phone camera profile. Source: https://github.com/shenmintao/V-Log-Alchemy/blob/main/Luts/Hasselblad/README.md.

**Strict boundary:** Neither the Phocus 4.0.1 X2D model, Sony camera Lightroom profile nor these LUTs should be copied into the X2D II firmware-equivalent phone renderer as validated X2D II colour. Keep external model comparisons separate until exact camera mode, input/output colour space and original-pixel validation are established. Do not import proprietary recovered numeric datasets without licensing/provenance review.

## 4. Engineering decision / next work

The firmware-debug-register route does **not currently produce** the missing hardware pixel oracle. Avoid spending more iterations on callback getters without independent new evidence. The most valuable next engineering route toward a usable APK is:

1. Implement an **opt-in, real capture-bound RAW neutral reference diagnostic** in Android, connecting the Stage26 JNI native matrix reference and Stage30 verified DNG GainMap-only processing through bounded tiles. Bind physical sensor ID, frame/timestamp, saved original DNG SHA256, actual black/white levels, as-shot neutral, CFA and crop metadata. The original RAW must never be replaced, and Photon remains default saved-photo renderer.
2. First test end-to-end on a **genuine user phone DNG** with supported OpcodeList2; fail closed for other DNG opcodes, unknown crop/geometry, missing matrices, duplicate metadata or unproven shading. Report numerical sampling errors before image comparison. No hardware-specific precomputed arrays or vendor-looking LUT guess.
3. Parallel firmware-first research should now seek an **authoritative Eagle2/YUV-PP CCM register math description** or actual original ISP camera hardware **before-/after-CCM image samples** under locked registers with gamma/LUT isolated. Only this permits a firmware-equivalent 6-coefficient C primitive and equivalence tests. Do not treat 2D Phocus chroma maps, external 3x3/Q-format examples, or a paired RAW+JPEG as an isolated CCM pixel oracle.
4. For a separate, clearly labelled *Phocus experimental target*, first establish the X2D 100C versus X2D II camera/HNCS equivalence using matching original RAW renders and documented colour spaces, then validate before implementing optional mobile colour mode. This must not displace the firmware-first path.

## 5. Safety and continuity

All Stage31 code and results are committed only to the recovery branch. `main` and Android saved-photo colour are unchanged. No new APK was built, and no background deployment is pending. Current installed Stage26 `27187` remains the phone baseline. All screenshots, original private RAW/JPEG/TIFF, original firmware/ELFs, extracted vendor LUTs, confidential capture metadata and original IQ coefficient payloads must remain outside the public repository/CI artifacts.

**Continuation instruction:** Do **not** reconstruct or retest Stages 6–31. The next practical implementation checkpoint should be opt-in, tile-bounded native/Android real-DNG diagnostic integration with strict provenance and an original-data rollback. Seek genuine Eagle2 CCM oracle/spec evidence in parallel. No claim of X2D II photographic HNCS or a working colour port is justified yet.
