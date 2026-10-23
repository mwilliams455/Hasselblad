# Stage 38 — original Eagle2 pixel-oracle interface reconnaissance

**Date:** 23 October 2026 (UK)  
**Original source:** Hasselblad X2D II 100C 1.3.16.2, official CMA/CIM SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`  
**Branch:** `recovery/awb-rebuild-20261021` — research only; `main` and Photon saved photographs unchanged.

## Why this is new work

Stage17/25/27 reconstructed **MAIN CCM coefficient preparation** and the 16 × 6 signed register bank, while Stage31 showed that the identified 5-bit CCM debug mux is **not a demonstrated RGB pixel oracle**. Stage37A/B traced three MAIN-named CPU functions into register and parameter updates; Stage37C/C2 did not find a CCM pixel arithmetic contract in bundled headers. Those are all bounded negative results, not exhaustive exclusions of original ISP readback avenues.

Rather than rescan those functions, Stage38 inventories **different, potentially callable interfaces**: any named frame/raw/YUV/RGB/ISP dump, intermediate buffer readback, test pattern, input injection, and B2R/R2Y/V4L2 stream endpoint. Such an interface could make a future *original hardware* before/after CCM pixel experiment possible, provided hardware and an authorized owner were available. The present research cannot interact with a physical camera or assume these interfaces work.

## Exact test

`inspect_original_pixel_oracle_surfaces38.py` verifies and examines the following **six original AArch64 ELF files** (read-only):

- `system/lib/modules/vcam_driver.ko`
- `system/lib/modules/cam_vreg.ko`
- `system/lib64/librcam.so`
- `system/lib64/libdcam_pp.so`
- `system/lib64/libdcam_pp_base.so`
- `system/lib64/libduml_hal.so`

It reads symbol names from `.symtab`, `.dynsym`, and bounded `.gnu_debugdata` mini-debug tables, then counts relevant bounded printable strings in `.rodata`/string sections. Potential capture/injection names are kept distinct from previously identified pure register/transport functions. The report includes **counts and capped ELF symbol names only**, with an explicit flag for missing genuine image-buffer ABI proof. It does **not** dump register values, vendor instruction bytes, original IQ coefficients, firmware file contents, filenames from personal captures, any RGB/RAW data, or full symbol tables.

Local smoke test (no vendor code required):

```sh
python3 hasselblad_native_audit/isp_main_stage38/inspect_original_pixel_oracle_surfaces38.py --self-test
```

For original proof, use the pinned official firmware only in temporary CI:

```sh
python3 hasselblad_native_audit/isp_main_stage38/inspect_original_pixel_oracle_surfaces38.py \
  --firmware-root hasselblad_native_audit/firmware/extracted \
  --output /tmp/STAGE38_ORIGINAL_ISP_ORACLE_SURFACES.json
```

Workflow: `.github/workflows/hb-stage38-original-pixel-oracle-surfaces.yml`. It validates source hashes, performs synthetic tests, downloads/extracts official firmware without ever executing it, inspects the six exact source files, removes the firmware, and uploads **sanitized derived evidence only**.

## Interpretation and next proof gate

The actual output of this tool is a **symbol/entrypoint triage**, *not* a successful live camera dump. Function names and debug strings cannot establish the same stage's before/after RGB values, bypassing gamma and LUT, nor the six-coefficient equation, Q precision, domain, channel order, clipping or rounding. A reliable original pixel oracle requires a compatible physical ISP/hardware test, or a callable exact-original software implementation with verified pixel I/O. If stronger candidate functions appear, a later Stage38B can inspect dataflow/argument shape *on the original exact ELF* before designing any hardware tests.

The previously tested X2D II QEMU DevKit reproduces menus/UI but **not** camera ISP hardware; it is not a pixel oracle. Public X2D II ADB/diagnostic projects establish possible authorized diagnostic access to a real camera, not a working ISP frame-tap protocol or owner permission. No hardware modification or ADB enablement is part of this stage.

**No APK built; Stage36 `27190` remains the last signed and phone-tested diagnostic.**

## Stage38A original-firmware result (23 October 2026)

Original-source GitHub Actions CI https://github.com/mwilliams455/Hasselblad/actions/runs/39913809691 completed **SUCCESS**. Six exact hash-pinned ELF symbol tables were inspected; 61 named functions matched the broad potential-frame-readout heuristic and five the broad synthetic-input heuristic. Those numbers contain false positives (e.g., DMA-buffer export and an unrelated sensor-level test-pattern setter), and are **not** a count of original MAIN CCM pixel oracles. Relevant real original names include `pp_dump_frame_to_file_base`, `pp_dump_plane_to_file`, `rcam_dbg_capture`, `rcam_dbg_dump_isp`, `rcam_dbg_enable_segment_switch_isp_dump`, and `_imgsys_set_test_pattern`. File-output function names suggest a diagnostic frame route but cannot distinguish an actual intermediate image from ancillary configuration metadata.

## Stage38B — named original callsite and buffer-domain triage

`inspect_original_pixel_oracle_calls38b.py` takes **19 exact named original functions** from four hash-pinned ELF files, disassembles only those selected function bodies, resolves PLT imports only if their layout is proven, and inventories direct same-binary BL calls and callers (AArch64 `CALL26` relocations in the original kernel object). It records counts and bounded original symbol names but **no instructions, literals, decoded pixels, vendor colour values, frame buffers, dumped files or hardware changes**. The named upstream callers and downstream I/O/register calls should help distinguish ISP-register-only dumps, sensor test patterns, and actual buffer-to-file helpers.

Stage38B remains **static provenance**: a function calling `fwrite` or named `frame` is not by itself proof of a CCM-before/after pixel oracle. Only independently verified runtime buffer identity, stage provenance, coefficient control and same-pixel sample comparisons can establish that. No live camera operations or APK changes are authorized.

Run `python3 hasselblad_native_audit/isp_main_stage38/inspect_original_pixel_oracle_calls38b.py --self-test`; the updated workflow executes the original on ephemeral hash-pinned firmware and produces a separate sanitized report.