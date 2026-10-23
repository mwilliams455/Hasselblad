# HasselbladPhoton — Stage 38 original ISP pixel-oracle interface handoff

**Checkpoint:** 23 October 2026 (UK)  
**Camera target:** Hasselblad X2D II 100C, official firmware **1.3.16.2**  
**Working branch:** `recovery/awb-rebuild-20261021`  
**Stage38C verified source commit:** `d8f0ce5f251ffe50fd5dd7fa1f1e8bf3fbe08baa`  
**Production `main`:** `929f523aa02ae5b224be39b9c36cce5975691a10`, unchanged  
**Last signed/phone-tested app:** Stage36 `0.1-hb-dual36`, versionCode **27190**; saved DNG/JPEG still use Photon colour.  
**Firmware archive SHA-256:** `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` (364,814,336 bytes).

## Purpose and established predecessor

This stage did **not** repeat AWB, Camera2 neutral comparison or the six-coefficient register discovery. Stage36 already demonstrated two source-bound original/Photon-neutral Stage24 JNI passes on real Xiaomi RAW. Stages 17/25/27 established original MAIN CCM parameter preparation and the `16 × 6` signed `lmtx_fw` register bank, with repeated static still groups and disabled hue/desaturation/level filters in the audited global still configuration. Stage31's five-bit CCM debug mux had no proven before/after pixel readback. Stages37A/B placed `main_ccm_calc_frame/global/mode` in register/parameter control. Stage37C/C2 did not find a MAIN CCM pixel equation in bundled headers.

Stage38 asked a different question: **Can we find an original camera frame-dump, intermediate-buffer readback or input-test interface from which a genuine X2D II hardware pixel oracle might eventually be built?** The audit uses only exact-firmware ELF data, without executing firmware, touching camera hardware or modifying any image.

## Stage38A — interface candidate discovery (verified)

**CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39913809691 — **SUCCESS**.

Hash-pinned original AArch64 files scanned: `vcam_driver.ko`, `cam_vreg.ko`, `librcam.so`, `libdcam_pp.so`, `libdcam_pp_base.so` and `libduml_hal.so`. The symbol/readonly-string inventory found **61 broadly matched readout names and 5 broadly matched synthetic-input names**. These are *heuristic names*, and include many unrelated operations. No pixel samples or pixel-equation proof followed.

Useful specific original symbols: `pp_dump_frame_to_file_base`, `pp_dump_plane_to_file`, `rcam_dbg_capture`, `rcam_dbg_dump_isp`, `rcam_dbg_enable_segment_switch_isp_dump`, and `_imgsys_set_test_pattern`.

Source: `hasselblad_native_audit/isp_main_stage38/inspect_original_pixel_oracle_surfaces38.py`.

## Stage38B — exact named function callee/caller proof (verified)

**CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39914461814 — **SUCCESS**.

Nineteen selected original functions across `librcam.so`, `libdcam_pp.so`, `libdcam_pp_base.so` and `vcam_driver.ko` had their bounded original AArch64 direct calls and named caller candidates inspected. **No original pixel-memory ABI was established.**

| Original symbol | Original call relationship recovered | Current meaning |
|---|---|---|
| `pp_dump_frame_to_file_base` | Calls `_write_data`, `fopen`, `fclose` | Genuine host frame-to-file writer candidate; input data type/stage not proven |
| `pp_dump_plane_to_file` | Also calls `_write_data`, `fopen`, `fclose` | Plane-to-file helper; not evidence of CCM sample provenance |
| `cap3_fusion17_in_buff_dump` / `cap3_fusion17_out_buff_dump` | Both call `pp_dump_frame_to_file_base` through validated PLT | Fusion-processing buffer dump path, not proven ordinary-still MAIN CCM |
| `rcam_dbg_dump_isp` | Calls `rcam_iq_tuning_dump`, virtual-register handle and tuning-lock APIs | IQ/register-oriented diagnostic, not demonstrated image pixel tap |
| `rcam_dbg_enable_segment_switch_isp_dump` | Calls `rcam_dev_set_segment_switch_reg_dump_enable` | Register-dump control, not verified frame readback |
| `rcam_dbg_capture` | Calls diagnostic reply and `sscanf`/`strncmp` routines | Command parser/ack path; no captured pixel format established |
| `_imgsys_set_test_pattern` | Short setter with mutex calls | Symbol indicates test pattern control, not validated MAIN CCM input injection |

Source: `hasselblad_native_audit/isp_main_stage38/inspect_original_pixel_oracle_calls38b.py`.

## Stage38C — exact cross-library use of frame exporters (verified)

**CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39914966865 — **SUCCESS**.  
**Source:** `hasselblad_native_audit/isp_main_stage38/inspect_dump_cross_importers38c.py`.

The original validated AArch64 `.plt` ordinals and direct `BL` targets were inspected in three hash-pinned host libraries, without executing them. This is a **direct-call** inventory, not a complete indirect or runtime graph.

| Original importer | Direct calls to `pp_dump_frame_to_file_base` | Direct calls to `pp_dump_buf` |
|---|---:|---:|
| `libdcam_pp.so` | **50** | **8** |
| `libdcam_adj_product.so` | 0 | 0 |
| `librcam.so` | 0 | 0 |

The 50 direct frame-writer calls belong to **26 distinct named caller functions**. They include `cap3_fusion17_in_buff_dump`, `cap3_fusion17_out_buff_dump`, `cap31_hdrgm_input_dump`, `cap31_drc_input_dump`, `cap31_hlrec_input_dump`, `cap31_ltm_input_dump`, `proc_pdaf30`, `proc_rdns_multi_cores`, `rdns`, `rltm_input_dump`, and other fusion, HDR-related, autofocus and denoise paths. Eight direct calls to `pp_dump_buf` are from `convert_pattern_*`, `dma_copy_*` and `mee_*` input/output storage routines.

**No direct `pp_dump_frame_to_file_base` callsite in this bounded inventory is owned by `raw2rgb_proc` or `raw2rgb`.** This does **not** rule out indirect calls, an alternate export helper, DSP-private pixel output, or a hardware-level frame tap. The frame-file helper is real but remains **unconnected to isolated pre-/post-MAIN-CCM pixels** on this evidence.

## Still-open fidelity gates

- Six original Eagle2 `lmtx_fw` coefficients: **pixel equation, Q scale, channel interpretation, rounding/clipping and signed intermediates NOT proven**.
- MAIN gamma and MAIN 3D LUT: **on-pixel application and stage domains NOT proven**. Other stages establish parameter tables and writers, not the hardware sampler.
- Original X2D II CCM before/after same-input oracle: **not obtained**. Stage38 proves file-export functions exist, but not a usable CCM-isolation test.
- Camera mode and software fidelity: static still config cannot prove exact runtime branch or sensor-to-phone matching; Stage36 native reference is not HNCS photographic rendering.

## Most meaningful next investigation

Stage39 should only invest in an avenue with **new evidence that can connect a pixel buffer to the MAIN CCM input/output boundary**, ideally a validated original hardware register/ISP specification or a consented, controlled diagnostic test on compatible X2D II hardware. To be an oracle, it must identify stage-local buffer addresses and format, controlled CCM coefficients, locked/bypassed gamma and LUT, and paired numeric input/output samples. Device-owner authorization is required; do not enable ADB, change original firmware, write registers or run diagnostic camera commands as part of research-only CI.

A public X2D II ADB project suggests that authorized diagnostics on real hardware are possible, but **does not prove a CCM pixel tap**. The published QEMU camera UI emulator does not emulate the camera ISP. External Phocus/HNCS models are independent, generation/domain-specific hypotheses and cannot be quietly substituted for verified firmware maths.

If an original oracle remains inaccessible, explain the blocker instead of creating another guessed 3×3/Q-format 'firmware-equivalent' transform. A separately labelled *experimental* colour option would need its own matching reference renders and user approval before any photographic output changes.

## Source, privacy and rollback

- Audit folder: `hasselblad_native_audit/isp_main_stage38/`.
- CI workflow: `.github/workflows/hb-stage38-original-pixel-oracle-surfaces.yml`.
- Exact original CIM and six primary binaries were hash-verified in ephemeral CI; Stage38C additionally pinned `libdcam_adj_product.so`.
- All tests passed. Published artifacts contain only sanitizer-bounded symbol names, counts and status flags; original firmware binaries, tuning arrays, RAW/JPEG/DNG files and full capture metadata are absent.
- Production `main` was not merged; no APK was built. Stage36 `27190` remains the baseline.