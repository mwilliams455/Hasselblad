# Stage 28 — exact Eagle2 MAIN CCM entrypoint wiring

**Firmware-first research — 22 October 2026, X2D II 100C firmware 1.3.16.2**

## Purpose

Stage27 established that the 16 groups and both high-ISO banks of the *static global still MAIN CCM coefficient table* are identical through the already verified Q8 preparation. Stage28 therefore targets the **missing actual six-coefficient pixel arithmetic** instead of rebuilding coefficient preparation or selecting an empirical colour look.

The immediate bounded investigation identifies which exact Eagle2 kernel code and registered callbacks program the CCM block and its input/output format controls. It uses original ELF symbol and relocation records rather than trying to infer function calls from unrelocated AArch64 branch immediates. The input module, previous code-audit receipt and four known functions are hash-/address-pinned.

- Original kernel module: system/lib/modules/vcam_driver.ko, SHA256 29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e
- CCM block: component ID 0x4b, register base at the common mapped PP base +0x2c000
- Verified register writers: ccm_set_fn0_config and ccm_set_ig0_config
- Prior 16 × 6 signed lmtx_fw registers: CCM block offsets 0x1cc through 0x348

## What this audit can establish

The exact-source report inventories CCM-named executable functions, incoming AArch64 CALL26 relocations to the four known functions, non-CALL26 text references, and relocation references from data sections (possible callback-table slots). Any potential callback reference is **only a candidate** until its storage and invocation have been traced. Section-relative locations are not loaded virtual addresses. No userspace/private stack, kernel module or camera hardware is invoked.

The script rejects a changed firmware hash, changed prior driver evidence, missing section/symbol contract, or changed previously verified ccm_set_fmt to ccm_set_fn0_config branch relocation.

## Verified Stage28A/28B original-firmware results

Two independent original-source scripts completed under hosted CI:

- Stage28A: https://github.com/mwilliams455/Hasselblad/actions/runs/39830443284
- Stage28B: https://github.com/mwilliams455/Hasselblad/actions/runs/39831395107

Both runs verified the exact official source package, including the same 3,150,240-byte AArch64 vcam_driver.ko and previous Stage17 driver evidence. All synthetic boundary tests passed. The report is sanitized; original instructions and tuning data are not uploaded.

**New original call edge:** b2r_pad_set_fh_fmt at .text+0x6d598 calls ccm_set_fmt, which in turn calls ccm_set_fn0_config at .text+0x314f0. The old ccm_probe binding to plat_eagle2_probe_components at .text+0x59fbc was also reconfirmed.

**Other format/configuration relationships from the same B2R function** include lsc_set_fmt, wbc_set_fmt, demosaic_set_fmt, pfr_set_format, cac_set_fmt, ccm_set_fmt, gamma_set_fmt, hncs_set_fmt, rltm_set_fmt, rgb_stats_output_config, ae_awb_stats_output_config, yuv_top_set_mux and v4l2_mbus_fmt_2_cfa_pattern. Its exact function size is 912 bytes / 228 decoded instructions. These are *format/control calls*, not evidence of every module's activation, pixel pipeline execution order or a mathematical colour transform. In particular, a call to hncs_set_fmt does not override the separately observed MAIN_HNCS bypass in the three audited still reprocessing topologies.

**The missing CCM IG0 setter reference was investigated further.** ccm_set_ig0_config has no incoming *named* relocation in this kernel module. One source-relative reference to its start offset appears in .altinstructions, relocation type 261. This is kernel alternate-instruction patch metadata, not proof of ordinary runtime invocation. No unrelocated BL to its exact function entry was found by the bounded scan. These observations do **not** prove the IG0 function is unreachable; runtime registration or userland direct register submission remain unexcluded.

The CCM section currently exposes 20 ccm_-prefixed functions, including register format/setup, probes and diagnostic/busy/counter accessors. No recovered original RGB pixel equation emerges from the verified call/relocation evidence.

**Important:** do not expand the symbol B2R into a definite Bayer-to-RGB pixel algorithm solely from its name; the association with downstream format setters is demonstrated, but its precise image-domain contract still needs dataflow evidence.

## What it does NOT establish

Neither an incoming call nor a static function-pointer reference is a pixel oracle. The recovered setters move configuration into hardware registers; they do not multiply RGB samples in userland. The six lmtx_fw values remain **signed16 register data**, not a proven 2×3, affine or constrained 3×3 matrix. No coordinate/working-space/Q-scale, rounding, per-frame overrides, clipping or gamma/LUT handoff is declared proven.

**Do not put an assumed CCM equation into the Android APK based on this audit.** Device build 27187 remains the working Stage26 synthetic neutral-JNI baseline; its 11/11 device test is not a real-photo HNCS equivalence test. Main remains untouched.

## The precise next evidence gate

One of the following is necessary to authorize genuine MAIN CCM pixel code:

1. An authoritative original Eagle2 MAIN CCM hardware/software specification **including the six-coefficient equation**, Q scale, pixel format, stage order and fixed-point rounding, tied to firmware 1.3.16.2; or
2. A controlled original ISP oracle where **before-CCM and after-CCM samples from the same hardware stage** are observable under authenticated fixed coefficient registers, bypassing or otherwise isolating gamma and MAIN LUT. Probe dark, white, neutral grey, independently varied RGB primaries, half-step roundings and both clipping boundaries. Record register image SHA rather than publishing Hasselblad coefficient payloads.

An X2D camera JPEG versus 3FR RAW is a valuable end-to-end evaluator, **not** an isolated CCM oracle because WB, gamma, LUT, tone, demosaic, shading and exposure also differ. An X1D II dump cannot be used as X2D II hardware truth without platform/version-specific equivalence evidence.

## Reproduce (no vendor input)

~~~bash
python3 hasselblad_native_audit/isp_main_stage28/inspect_ccm_entrypoints28.py --self-test
~~~

## Reproduce exact-source probe privately

~~~bash
python3 hasselblad_native_audit/isp_main_stage28/inspect_ccm_entrypoints28.py \
  --module /private/X2DII_extracted/system/lib/modules/vcam_driver.ko \
  --prior hasselblad_native_audit/main_colour_20261019/ccm/ccm_driver_evidence.json \
  --output /private/STAGE28_CCM_ENTRYPOINTS.json
~~~

The workflow retrieves the official firmware transiently, checks its published SHA256, extracts without executing the firmware, runs this probe and publishes only source identities, function names, counts and call-relocation metadata. Vendor instructions, coefficients, image data and original binaries are excluded.
