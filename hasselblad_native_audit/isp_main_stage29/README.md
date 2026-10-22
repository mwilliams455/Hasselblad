# Stage 29 — MAIN CCM format-call ABI provenance

**X2D II 100C · firmware 1.3.16.2 · firmware-first / research-only**

Stage28 verified that b2r_pad_set_fh_fmt calls ccm_set_fmt at kernel .text+0x6d598, which calls ccm_set_fn0_config at .text+0x314f0. The original setter packs two fields into the low/high 16 bits of the CCM format register, but their calling-side values and pixel-format meanings remain unproven.

Stage29 performs a bounded forward may-reaching-definition analysis over exact original AArch64 control-flow graphs. For candidate argument registers x0–x3 it reports whether the last writer is unique or path-dependent. Function calls conservatively clobber caller-saved arguments. Unresolved branches prevent a definite source conclusion. It also looks at WBC/demosaic/CCM/gamma/HNCS format call sites for relative provenance, without assuming that each module executes in photography.

This is stronger than finding the nearest writer in an instruction listing, but it does not prove any runtime value, register field semantics, CCM Q format, six-coefficient pixel equation or true Hasselblad colour. The module is pinned to X2D II original vcam_driver.ko SHA256 29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e and verified setter sizes/callsite relocations.

## Reproduction

Synthetic test with no firmware:

    python3 hasselblad_native_audit/isp_main_stage29/inspect_ccm_argflow29.py --self-test

Original-source audit in a private workspace:

    python3 hasselblad_native_audit/isp_main_stage29/inspect_ccm_argflow29.py --module /private/extracted/system/lib/modules/vcam_driver.ko --output /private/STAGE29_CCM_ARGFLOW.json

Only structured writer categories and relative section offsets are retained. Original vendor instructions, IQ tuning, firmware binaries, private DNG/JPEG/TIFF and original pixel data must not be published.

## Next gate

If any writer is unambiguous, follow its source register and memory-producing path, across branch joins, until its format value and provenance can be demonstrated. A verified selector still does not reveal the MAIN CCM pixel arithmetic, which requires a hardware specification or isolated ISP before/after pixel oracle. Do not port a fixed-point convention from a different camera ISP.

The Android Stage26 signed build 27187 remains the proven synthetic-JNI baseline. No Stage29 APK or saved-photo processing changes. Main stays untouched.
