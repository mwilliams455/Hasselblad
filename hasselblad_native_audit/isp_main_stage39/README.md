# Stage 39 — original X2D II CCM component routing and pixel-oracle feasibility

**23 October 2026 · X2D II 100C 1.3.16.2 · firmware-first research · read-only**

## Why this is a different investigation

Stage36 established genuine physically bound phone DNG native colourimetric reference; not HNCS. Stage17/25/27 independently established X2D II MAIN CCM coefficient preparation and a 16 × six-signed-coefficient hardware register family; the per-pixel operator remains **unknown**. Stages31/37 established configuration/debug getters, not isolated pixels. Stage38 found a real original frame-to-file exporter, but its original direct callers lie in various processing functions, and none of the direct-call inventory identified ordinary `raw2rgb` or a before/after MAIN CCM stage.

Stage39 tests a **different, falsifiable hardware interface question**: Does the original Eagle2 CCM component itself publish a callback, frame-buffer getter, DMA endpoint or readback path that could connect a separately established original buffer exporter to this *specific* hardware block? A mere debug function or register setter is not sufficient.

## 39A: exact original driver relocation and function inventory

`inspect_ccm_component_routes39.py` verifies the exact original firmware's `system/lib/modules/vcam_driver.ko` SHA256, treats its ET_REL symbol and relocation sections as inert inputs, audits defined original `ccm_*` functions and exact relocations referencing them, and records bounded static call and instruction-class summaries. It distinguishes `R_AARCH64_CALL26`/`R_AARCH64_JUMP26` from data-section callback pointers. It identifies named CCM routines suggesting buffers or frame outputs as **candidates**, never as a proven pixel stage. No live capture, hardware access, vendor code execution or device-modification command occurs.

A report can show which functions are reachable from `.rodata` callback tables and which only feed register configuration. Function names, relocation pointers and the absence of a `ccm`-named buffer helper are **not** proof that no unlabelled/indirect/hardware path exists. The stage's actual outcome must be interpreted within that bound. In particular, the previously discovered debug mux's five-bit selector has not been established as a before/after pixel sample.

## Reproduction

With Python 3.12+, `pyelftools>=0.31,<1`, `capstone>=5,<6`:

```bash
python3 hasselblad_native_audit/isp_main_stage39/inspect_ccm_component_routes39.py --self-test
python3 hasselblad_native_audit/isp_main_stage39/inspect_ccm_component_routes39.py \
  --module hasselblad_native_audit/firmware/extracted/system/lib/modules/vcam_driver.ko \
  --output /tmp/STAGE39_ORIGINAL_CCM_COMPONENT_ROUTES.json
```

`.github/workflows/hb-stage39-ccm-component-routes.yml` verifies the official firmware archive **size 364,814,336** and SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`, extracts transiently with the pre-existing inert extractor, runs synthetic and original audits, deletes original inputs before artifact publishing, and uploads only a sanitized JSON report. It guards the Android app and `main` from changes. Original ELFs, instruction sequences, firmware tables, images, captured physical device identifiers and calibration values are never published.

## Classification gates

- **Proven**: exact name, symbol boundaries, original relocation or decoded instruction class, when original CI passes.
- **Candidate**: callback or function name suggesting frame access; caller and stage dataflow must be independently proven.
- **Not proven**: CCM-input and CCM-output samples, pixel-bit arithmetic and rounding, six-coefficient Q format, channel order or pixel group selection, MAIN gamma/LUT pixel domain, colorimetric faithfulness/HNCS.

The signed phone-tested Stage36 `27190` is unchanged. The recovery branch is independent of production `main`, which must remain `929f523aa02ae5b224be39b9c36cce5975691a10` unless the user approves a merge.