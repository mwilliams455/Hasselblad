# HasselbladPhoton — Stage 29 original MAIN CCM format-argument handoff

**Date:** 22 October 2026 (UK)  
**Original reference:** Hasselblad X2D II 100C firmware 1.3.16.2  
**Project:** Firmware-first HasselbladPhoton / PhotonCamera; device-neutral Android app, Xiaomi 15 Ultra current physical tester  
**Repository:** <https://github.com/mwilliams455/Hasselblad>  
**Active branch:** `recovery/awb-rebuild-20261021`  
**Verified source commit:** `f7d5846e66020bb7b2c7afa9ea4b66d3bceba6dc`  
**Final Stage29 original-firmware CI:** <https://github.com/mwilliams455/Hasselblad/actions/runs/39837397781> — success  
**CI artifact:** `Hasselblad-Stage29-CCM-Argument-Provenance-Safe` — six sanitized JSON files.

## 1. Do not repeat Stages 24–28

- Stage24 provides a **real-frame offline 12 MP colourimetric reference** from DNG ForwardMatrix/AsShotNeutral through XYZ D50 to linear sRGB/P3. It is not firmware-equivalent HNCS.
- Stage25 joined exact original MAIN CCM parameter names to the Eagle2 hardware register families.
- Stage26 produced signed Android build **27187**, with the user's real-phone synthetic native-JNI check **PASS 11/11, 4.625 ms**. These tests do not validate real-photo colour or full-frame timing; saved JPEG remains Photon.
- Stage27 proved all 16 coefficient groups and the two high-ISO coefficient banks equal for the exact audited *static* global-still CCM profiles. It did **not** reveal the six-coefficient pixel equation or exclude runtime overrides.
- Stage28 proved `b2r_pad_set_fh_fmt` calls `ccm_set_fmt` and then `ccm_set_fn0_config` programs the hardware format register. Format-related calls are not proofs of active pixel stages.

## 2. What Stage29 has now proved or constrained

Stage29 uses the original 3,150,240-byte `system/lib/modules/vcam_driver.ko`, SHA256 `29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e`. The kernel is only statically decoded in an ephemeral CI runner; it is never loaded or executed.

### Stage29A/B — static call argument provenance

Across the named B2R format calls for **WBC, demosaic, CCM and gamma**, the candidate AArch64 `x1` and `x2` call arguments are 32-bit word loads from **the same record pointer**: `[x19 + 0x08]` and `[x19 + 0x0c]`. These are original instruction-operand findings, not inferred from table sizes.

At the CCM callsite (`.text+0x6d598`):

- `.text+0x6d58c`: the 32-bit word at `[x19 + 8]` is loaded into `w1`.
- `.text+0x6d594`: the 32-bit word at `[x19 + 12]` is loaded into `w2`.
- `x0` is derived by a move from `x7`.
- `x3` is clobbered by a previous call in the conservative ABI analysis; do not treat it as a demonstrated CCM input.

The upstream B2R function contains unresolved control-flow edges; the report is a **path-insensitive may-reaching-definition audit**, not a dynamic trace proving all possible argument values. However, the original exact word-load sites and offsets are established.

### Stage29C — B2R record pointer provenance

The original B2R function begins at kernel `.text+0x6d2f0`, spans **912 bytes / 228 instructions**, and binds **incoming `x1` to callee-saved `x19`** at `.text+0x6d314`. No preceding instruction in this bounded entry slice modifies `x1`.

The same original function reads the record at offsets **+4 (once), +8 (11 times), +12 (11 times), +16 (7 times)**. These are *static instruction access counts*, not runtime usage counts.

Public Linux V4L2 userspace format structures have a candidate layout: `v4l2_subdev_format` contains `which` (32-bit), `pad` (32-bit), then an embedded `v4l2_mbus_framefmt` whose initial fields are `width` and `height`; these would appear at offsets +8 and +12. This is a **layout hypothesis only**, not proof that the vendor's input pointer has this type.

Public reference: <https://android.googlesource.com/kernel/common/+/refs/heads/android-mainline/include/uapi/linux/v4l2-subdev.h>.

### Stage29D — original callback-table ownership

The original `.rodata` function-pointer reference at section offset **0x5658** has type `R_AARCH64_ABS64` (257) and targets `b2r_pad_set_fh_fmt`. This entry belongs to the exact original **`b2r_pad_ops`** object, located at `.rodata+0x55a8` and measuring **200 bytes**. Relative entry offset is `0xB0` = **slot index 22** if viewed as 8-byte pointers.

An immediately preceding `.rodata+0x5650` section-plus-addend relocation resolves to the original function **`b2r_pad_set_fh_stream`**. This is direct original-symbol evidence of neighbouring FH stream/format handlers in a B2R pad-ops record.

A matching V4L2-like field layout is plausible, but **neither the `b2r_pad_ops` object name nor its callback neighbours formally proves that the incoming record is `struct v4l2_subdev_format`**. Do not force a standard V4L2 callback index/type onto this custom table, whose format callback is at index 22.

### Important inference / negative result

The two shared call arguments may be **frame geometry** rather than a numerical pixel/colour encoding selector. Their 32-bit source fields and the prior two-halfword CCM format-register submission support investigation of that distinction, but neither dimensions nor bit depth has yet been conclusively identified as the original field semantics.

**The six signed MAIN CCM coefficients are a separate register family (`lmtx_fw`) and their actual per-pixel arithmetic, Q scale, RGB order, clipping and rounding remain unknown.** Formatting callbacks are not the colour transformation itself.

## 3. Repository files / validation

- `hasselblad_native_audit/isp_main_stage29/inspect_ccm_argflow29.py`
- `hasselblad_native_audit/isp_main_stage29/inspect_b2r_record29c.py`
- `hasselblad_native_audit/isp_main_stage29/inspect_b2r_callback29d.py`
- `hasselblad_native_audit/isp_main_stage29/README.md`
- `.github/workflows/hb-stage29-ccm-argflow.yml`
- Hosted successful exact-source CI: <https://github.com/mwilliams455/Hasselblad/actions/runs/39837397781>

The final CI reports passed all synthetic CFG/record/callback boundary tests, retrieved/hash-verified the exact firmware transiently, inspected the original ELF, verified required function pointers and privacy guards, deleted firmware before upload and published **only derived metadata**. Its artifact contains Stage29, 29C and 29D original reports and synthetic receipts. No original instructions, coefficient arrays, LUTs or user photos are published.

## 4. Stage30 work — do this next

1. **Do not keep treating B2R frame-format callbacks as a route to pixel equations.** If resolving their original field type, pursue exact callback/input structure evidence, but keep this bounded; current result suggests these may be image dimensions rather than colour math.
2. **Prioritise the Eagle2 MAIN CCM pixel operation**: authoritative hardware/register/ISP description for the 16 × six-coefficient `lmtx_fw` block, or a same-input original ISP **before/after-CCM** oracle with gamma/LUT bypass and controlled numeric fixed-point tests. Do not assert a constrained 3×3 or 2×3 formula from coefficient count alone.
3. In parallel, continue a rigorous *non-HNCS* Stage24 real-RAW reference adapter: DNG OpcodeList2, lens shading and sensor calibration/input-domain validation, with provenance-bound physical sensor/frame capture and a separately opt-in Neutral/Lab diagnostic. Keep Photon saved JPEG the default.
4. After **genuine original pixel maths** is recovered, implement standalone C primitive, synthetic/original-oracle differential tests and host/arm64 CI; only then add firmware-stage toggles to the Android colour renderer. Subject/face AF remains a later shared module for Hasselblad and Leica apps.

## 5. Production, privacy and continuity

- Do not alter `main`; last confirmed production baseline is commit `929f523aa02ae5b224be39b9c36cce5975691a10`.
- Keep working on recovery branch until explicitly validated for merge.
- Current installed Stage26 build `27187` is the signed on-device **synthetic** diagnostic baseline; Stage8 `27186` remains rollback. **Stage29 creates no APK.**
- Never commit or upload original Hasselblad firmware, IQ payloads, private DNG/JPEG/TIFF, original camera matrices or confidential capture identifiers in public GitHub or Actions artifacts.
- Stage29 does NOT claim firmware-equivalent HNCS, validated real-phone photographic colour, calibrated AWB, subject autofocus, or a completed MAIN CCM pixel equation.

**Next-chat instruction:** Resume from Stage29 final original-firmware CI on the recovery branch. Do not reconstruct Stages 6–29. Direct Stage30 toward the real Eagle2 six-coefficient CCM pixel equation/hardware oracle, with real-phone neutral DNG correction work as a parallel safe option; never substitute assumed standard ISP Q formats or an arbitrary Hasselblad-like LUT for proven firmware maths.
