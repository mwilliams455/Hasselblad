# Stage41P — trace actual pixel-operation leads after table preparation

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Starting commit: `55b03a52c87d1b239cbad83e4834beb867448294`.
Production `main`: `929f523aa02ae5b224be39b9c36cce5975691a10`.

**The exact photographic MAIN CCM pixel equation is still not recovered.** This investigation followed consumers and a packaged Eagle2 simulation lead rather than adding another table-preparation test. The simulation's constructed callback chain reaches an SS DSP function client; its remote pixel body is not present in the inspected host functions. Its parameter layout also describes a nine-coefficient SUB CCM, not the six-coefficient-per-group photographic MAIN CCM contract.

This is a bounded negative finding, not pixel parity or a claim that recovery is impossible. Actual RAW samples and rendered reference images remain accessible. The missing evidence is the transformation between individual MAIN stages and their active state, not access to image pixels in general.

## 1. Exact original register-reader trace

The audit finds every immediate AArch64 `B`/`BL` reference in the pinned `librcam.so` `.text` section to the known `DjiIsp_Reg_Get` entry. It independently checks each encoded target with Capstone and resolves its containing original function. There are **90 call sites in 10 functions**:

| Consumer | Call sites | Relevant scope |
| --- | ---: | --- |
| `dcam_isp_vreg_get_reg` | 1 | Generic register access wrapper |
| `_segment_pre_calc_autoknee` | 1 | Autoknee control |
| `adj_hiso_shift_pygen_level` | 1 | High-ISO/pyramid control |
| `main_blc_update_reg` | 1 | Black-level register update |
| `_update_rltm_debug_func` | 2 | RLTM debugging |
| `_update_ccm_debug_func` | 3 | CCM debugging, already bounded by prior work |
| `_update_gamma_debug_func` | 1 | Gamma debugging |
| `adj_plat_calc_mctf_denoise_strength` | 17 | Denoise parameter control |
| `tmc_v1_0_calc_tmc` | 8 | Tone-control table computation |
| `calc_blc_hob_adpt` | 55 | Black-level adaptation |

This does not demonstrate a new RGB CCM evaluator. In particular, numeric constants within the CCM register-ID range are not automatically register accesses: the TMC function also uses numbers in that range as arithmetic constants. The audit does not classify such coincidences as CCM reads.

The scope is explicitly **direct calls to this getter**. It does not exclude indirect calls, code reading a virtual-register buffer directly, unlabelled functions, other binaries, DSP instructions or hardware. It cannot support the stronger claim that no software model exists anywhere.

## 2. The Eagle2 simulation lead resolves to DSP transport

The packaged `system/etc/ppt` test definitions include `e2_subp_sim`, `gamma` and `gamma_reverse` recipes. Each explicitly selects `PP_PLATFORM_DSP_FRWK`. They contain parameter descriptions and CRC/model-version fields, but the four referenced input files are absent by basename from the inspected extracted firmware tree. No matched per-pixel input/output fixture was recovered from these recipes. A CRC or model-version identifier is not a pixel evaluator.

The `e2_subp_sim` parameters contain BPC, white balance, demosaic, CCM, gamma and YCC sections. The CCM matrix has **nine** entries, and gamma has 257 positive and nine negative entries. The table lengths alone do not establish that its gamma is the photographic MAIN gamma implementation. The SUB CCM must not be substituted for MAIN's six-value family without a separate equivalence proof.

The original host initialization and process routines give a more concrete result than the simulation name:

1. `e2_subp_sim_init` calls `pp_create_platform_ctx`.
2. The latter reaches `_create_platform_ctx_base`, which creates a DSP framework device context.
3. `pp_create_dsp_frwk_dev_ctx` installs named callbacks into that context.
4. `proc_e2_subp_sim` uses those callback offsets for buffer translation, processing, an optional wait and result retrieval.
5. Its constructed processing callback reaches `pp_call_ss_function_client`, which calls `ss_dsp_function_client_call`.

| Device callback offset | Constructor-installed target | Caller site in `proc_e2_subp_sim` |
| --- | --- | --- |
| `+0x10` | `_pp_dsp_frwk_buf_trans` | `0xa86a8` |
| `+0x28` | `_pp_dsp_frwk_process` | `0xa8938` |
| `+0x30` | `_pp_dsp_frwk_wait` | `0xa8bc0` |
| `+0x40` | `_pp_dsp_frwk_pull_buf` | `0xa8cb0` |

The processing chain is `_pp_dsp_frwk_process` → `_pp_dsp_frwk_sl_process` → `pp_call_ss_function_client` → imported `ss_dsp_function_client_call`. The independent audit verifies the direct call sites and resolves the four callback address constructions from the original constructor. These are static relationships, not an observed live capture or proof of every possible runtime override.

This establishes why calling the host wrapper in an emulator would not by itself produce the model's pixels: the wrapper submits work through a remote DSP client. Stubbing that remote call with an assumed matrix would test the stub, not recover the missing implementation. No original wrapper was run, no hardware was contacted, and no claim is made that the remote code has been decrypted or emulated.

## 3. Two apparent arithmetic leads have different roles

`_ColorMatrix_Func` and its `DjiMetadata_ProresRaw_GetCcmByCct` callee contain real floating-point matrix arithmetic. The inspected caller takes two nine-value metadata matrices, converts their numeric representation, and obtains a CCT-dependent nine-value result. It does not turn the photographic MAIN six-coefficient group into an RGB operator. A metadata matrix interpolation is not a demonstrated input-pixel/output-pixel operation.

`tmc_v1_0_calc_tmc` reads the MAIN positive gamma table, knee keypoints/gain and division controls. Its positive-coordinate construction was already verified in the 19 October gamma work. The later inspected code rescales coordinates and resamples a curve before writing a 257-entry gamma table. Those original operations inform tone-table computation, but do not establish the hardware's per-pixel interpolation, negative handling or dither. This stage does not publish another table operation as a recovered pixel renderer.

## 4. Current pixel contract: known and missing

| Operation | Established evidence | Still needed for faithful pixel rendering |
| --- | --- | --- |
| MAIN CCM | CCT-dependent preparation; 16 groups of six signed coefficients; register destinations | Meaning/order/scale of six coefficients; RGB equation; group selection where relevant; clipping and rounding |
| MAIN gamma | 257-entry positive table; MAIN-linked coordinate construction; table writes | Hardware interpolation, signed input behavior, negative table mapping, output precision and dither |
| MAIN knee | Gain-table exposure interpolation, Q12 slope preparation and writes | Pixel luma/gain/saturation equations when enabled; runtime activation |
| MAIN 3D LUT | Profile preparation and packed-word submission | Channel/grid packing, input domain, pixel interpolation and rounding |

The earlier static ordinary/enhanced still mappings have knee disabled. The earlier positive gamma coordinate result remains valid. Neither should be reopened as unknown merely because the remaining pixel stages are unresolved.

The four real RAW/JPEG pairs span the whole processing chain, with intermediate values and active registers unobserved. They support measured comparisons and an explicitly empirical renderer. They do not uniquely attribute a difference to CCM versus gamma, the 3D LUT, local processing or reference encoding, and cannot on their own validate an exact hidden-stage equation. The existing offline empirical results remain separate from firmware-equivalence claims.

## 5. What evidence would move the exact-pixel investigation forward

The next useful evidence must be one of these concrete sources:

- A MAIN-specific Eagle2 mathematical implementation/specification tied to the existing six-coefficient and register contract.
- A genuine software model with a verified pixel-buffer interface and an independently established link to photographic MAIN.
- Same-frame numeric RGB samples immediately before and after an isolated MAIN stage, accompanied by active coefficients, enable states, mode, channel order, numeric range and rounding/clipping controls.

For the last route, start with black, neutral ramps, single-channel and two-channel basis patches, mixed colours and near-clipping samples. It must distinguish six-coefficient ordering and scaling, not merely look plausible on a photograph. Existing RAW/JPEG pairs and a complete live-view NV12 frame are not substitutes for those isolated stage samples. This document specifies the missing evidence; it does not authorize device modification or claim that a suitable physical capture interface has been found.

Stop repeating CCM setter/debug inventories, generic header searches and table-preparation replay as substitutes for this evidence. Without a new implementation/specification or isolated samples, exact MAIN parity remains blocked. A measured photographic approximation is a separate, testable development path and should retain that label.

## Validation and retained files

`isp_pixel_stage41p/inspect_pixel_consumers41p.py` performs the static source audit. `evidence/stage41p/STAGE41P_PIXEL_CONSUMER_AUDIT_SAFE.json` records source/function hashes, the 90 direct getter references, four resolved simulation callbacks, seven verified direct edges and structural test metadata. Six synthetic branch-decoder cases pass. Sixteen selected original function bodies are inspected; no original pixel-operation execution or pixel equivalence test was performed.

The source files are the same SHA-pinned 1.3.16.2 inputs used in prior research. The receipt and source contain no original executable bytes, disassembly, tuning arrays, photographs, RAW arrays, fitted coefficients or private capture calibration. Firmware 1.3.16.2 still differs from the four captures' reported 1.1.6.3. No Android rendering code or APK changes.

Run from the repository root, retaining the earlier sibling audit directories:

```sh
python hasselblad_native_audit/isp_pixel_stage41p/inspect_pixel_consumers41p.py --self-test
python hasselblad_native_audit/isp_pixel_stage41p/inspect_pixel_consumers41p.py --firmware-root PRIVATE_FIRMWARE_ROOT --output RESULTS/STAGE41P_PIXEL_CONSUMER_AUDIT_SAFE.json
```

Install `isp_pixel_stage41p/requirements41p.txt` for the existing Stage41M requirements plus `capstone==5.0.9`. This audit reuses symbol/ELF helpers from `isp_knee_stage41m`, `isp_knee_stage41n` and `isp_liveview_stage41`.
