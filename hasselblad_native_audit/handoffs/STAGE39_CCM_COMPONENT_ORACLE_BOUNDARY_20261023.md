# HasselbladPhoton — Stage 39 original Eagle2 CCM component/interface checkpoint

**23 October 2026, UK · research only · X2D II 100C firmware 1.3.16.2**

**Working branch:** `recovery/awb-rebuild-20261021`  
**Original-firmware source commit (39B):** `c7fd407587fa8286bd622993f135dca4c56c4b49`  
**Stage39A CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39916749386 — **SUCCESS**  
**Stage39B CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39917308220 — **SUCCESS**  
**Production main:** `929f523aa02ae5b224be39b9c36cce5975691a10`, unchanged  
**Latest phone-tested APK:** Stage36 versionCode `27190`; saved photographic colour remains Photon.

## Exact provenance and purpose

The stage audits **only the original** `system/lib/modules/vcam_driver.ko`, SHA256 `29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e`, extracted transiently from the exact original 364,814,336-byte X2D II 1.3.16.2 firmware, SHA256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.

The narrow question was whether the original MAIN CCM hardware component supplies an explicit frame/buffer/DMA readback endpoint or data-section function-pointer table that could be tied to the previously proven `pp_dump_frame_to_file_base` host file writer (Stage38). The audit does **not** re-check Stage17 coefficient preparation or reuse the Stage36 phone DNG as a claimed Hasselblad output oracle.

Source: `hasselblad_native_audit/isp_main_stage39/inspect_ccm_component_routes39.py`  
Workflow: `.github/workflows/hb-stage39-ccm-component-routes.yml`

## Stage39A verified static evidence

- **20** exact original, defined `ccm_*` functions inventoried (configuration/init/probe/remove, format setter and scalar debug accessors).
- **Zero** names in this set suggest an image-buffer, DMA, frame-file export or per-pixel operator.
- **Zero** multiply-like instruction occurrences in the 20 original functions under this bounded disassembly classification; register loads/stores are present, most extensively in `ccm_set_ig0_config`.
- Direct original control edges agree with previous research: `plat_eagle2_probe_components` calls `ccm_probe`; `b2r_pad_set_fh_fmt` calls `ccm_set_fmt`.
- Five **non-direct-call relocations** targeted four CCM functions. Stage39A treated them as **unresolved**, not as validated buffer callbacks.
- 14/14 synthetic assertions passed; original firmware static analysis and privacy checks passed.

## Stage39B exact relocation-source classification

The new original-firmware report records source sections, offsets and relocation types without exporting instruction bytes, original images or vendor coefficient arrays.

| Source section / offset | Target original symbol | Relocation | Interpretation boundary |
|---|---|---|---|
| `.altinstructions + 0x5afc` | `ccm_set_ig0_config` | **261 / R_AARCH64_PREL32** | ARM64 Linux alternative-instruction metadata reference; **not a demonstrated frame-export callback** |
| `.text + 0x3156c` | `ccm_remove` | **275 / R_AARCH64_ADR_PREL_PG_HI21** | Target address construction in code, not a direct call |
| `.text + 0x31570` | `ccm_remove` | **277 / R_AARCH64_ADD_ABS_LO12_NC** | Low address part for above code reference |
| `.text + 0x46e04` | `ccm_lite_remove` | **275** | Target address construction |
| `.text + 0x46e08` | `ccm_lite_remove` | **277** | Low address part |

Standard Linux ARM64 relocation definitions: https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/elf.h . ARM64 alternative section semantics: https://android.googlesource.com/kernel/common/+/21b594bf4077650611e7973312ce56c71fae9990/arch/arm64/include/asm/alternative.h .

The prior one remaining `ccm_set_ig0_config` reference is thus accounted for within the **alternative-instruction section**, not discovered as a normal image-buffer callback. The paired 275/277 references belong to **remove/teardown-related address references**. The audit does **not** prove every runtime indirect callback target; it merely bounds the scanned original source.

Stage39B synthetic **17/17** assertions and original exact-firmware CI passed.

## Evidence truth table

| Claim | Status |
|---|---|
| Original CCM parameter interpolation and 16×6 signed register bank | **Proven by Stages17/25/27**, not newly re-proven here |
| 20 original CCM driver functions, exact outgoing/incoming static references | **Verified within bounded Stage39** |
| Original CCM-specific named DMA/frame readback or software pixel maths in those 20 functions | **Not found** |
| Previously unexplained noncall relocation identifies a CCM framebuffer callback | **No**: source is `.altinstructions` or remove address construction |
| Hardware datapath is impossible to access by any means | **NOT PROVEN**; undocumented MMIO, unlabelled/indirect code and live interfaces remain outside scope |
| Exact six-coefficient Eagle2 CCM **pixel formula/Q scale/order/rounding/clipping** | **NOT PROVEN** |
| Exact MAIN gamma and MAIN LUT *pixel* interpolation | **NOT PROVEN** |
| Isolated X2D II same-stage input/output CCM pixel oracle | **NOT OBTAINED** |
| Authentic Hasselblad HNCS photographic colour in the Android app | **NOT IMPLEMENTED/VALIDATED** |

## Next gate and engineering decision

**Stop repeated generic searches of the same original CCM control/debug code.** This has now been independently bounded by Stages25/31/37/39. More static setter/callback enumeration alone will not produce a per-pixel transform.

For strictly **firmware-equivalent** colour, a new source of evidence is needed: (a) a MAIN-specific Eagle2 pixel mathematical/hardware specification, (b) an original **same-frame, before-and-after MAIN CCM** pixel oracle from authorized physical hardware with the exact active coefficients and stage controls, or (c) a genuine software implementation specifically of that stage with a verified pixel-buffer ABI. A safe experiment must bind frame/mode/colour temperature, establish numeric RGB domain/bit depth/ordering, isolate gamma/LUT influence, and compare neutral/basis/mixed/near-clip fixtures. The previous public QEMU UI runtime cannot emulate these camera ISP pixels. A DNG/JPEG comparison is only end-to-end and cannot be treated as a CCM oracle.

No original camera device was contacted. Do **not** write ISP registers, enable ADB, install unofficial modifications or run disruptive diagnostics as part of CI. If an authorized owner offers hardware, require explicit informed approval and a verified non-destructive read-only path before designing tests; otherwise stop at the documentary gate.

Until this evidence exists, keep the Stage36 Photon photo-save renderer and production main unchanged. A Phocus-inspired **experimental** mode, if separately desired, must remain explicitly distinguished from verified X2D II firmware pixel parity.
