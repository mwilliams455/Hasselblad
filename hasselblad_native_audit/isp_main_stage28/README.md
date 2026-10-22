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
