# Stage 37A — exact X2D II ARM-side MAIN CCM computation triage

**23 October 2026 | research-only | firmware-first**

## Problem

Stage 36 established a physically capture-bound genuine phone DNG, with two successful native Stage24 neutral reference calls and measurable per-pixel differences. This is not Hasselblad photographic rendering. Stage17/25/27/29 established original X2D II 1.3.16.2 MAIN CCM coefficient *preparation* and a 16 × 6 signed-register layout, not the hardware's per-pixel arithmetic. Stage31 ruled out a demonstrated before/after pixel oracle from the bounded debug-mux functions. The prior saved-still dispatch audit found that `libdcam_pp.so:raw2rgb_proc` constructs a DSP operation and that the remote `cam_libpp_function_entry` has not been recovered from encrypted DSP images.

## This targeted experiment

The new `inspect_main_ccm_cpu37.py` examines **four SHA-256-pinned ARM ELF binaries** extracted transiently from the same official X2D II 1.3.16.2 firmware. It enumerates and bounds symbols likely to contain MAIN CCM arithmetic or a direct RAW-to-RGB fallback, including `.gnu_debugdata` where present. It disassembles only selected named functions and reports **aggregate instruction-class counts** (loads/stores, multiply, vector multiply, calls, backward branches). Prior-validated parameter getters, MMIO register setters and DSP request/copy/transport functions are marked with their known scopes. Unexpected named colour arithmetic is flagged **for manual review**, never silently promoted to a camera pixel transform.

This is a targeted test of the **named ARM software fallback** hypothesis. A negative finding would only bound these four ELFs, named candidates, size cap and heuristic. An unlabelled or indirect ARM routine, hardware RTL, DSP code or another firmware component could still contain the operation. An apparent multiply in a named routine could be a table index or coefficient preparation, not pixel maths.

## Evidence test

```bash
python3 hasselblad_native_audit/isp_main_stage37/inspect_main_ccm_cpu37.py --self-test
python3 hasselblad_native_audit/isp_main_stage37/inspect_main_ccm_cpu37.py \
    --firmware-root hasselblad_native_audit/firmware/extracted \
    --output /tmp/STAGE37_CPU_MAIN_CCM.json
```

The workflow `.github/workflows/hb-stage37-cpu-main-ccm.yml` downloads the official archive with exact 364,814,336-byte and SHA-256 identity checks, extracts it transiently, runs the 14-case synthetic test and original static inspection, verifies that no vendor pixel or matrix output was exported, deletes firmware, and publishes only the bounded JSON research report. The script never loads or executes vendor libraries.

## Decision gate

A candidate with named colour semantics and multiply/memory operations may justify targeted ABI and per-pixel dataflow proof in **Stage37B**. Merely detecting a name, scalar multiplication or SIMD is *not* parity evidence. No firmware-verified six-coefficient pixel equation, Q scale, channel order, rounding, clipping, group selector, MAIN gamma or 3D LUT sampler is claimed by Stage37A. Neither Stage24 nor any diagnostic in this repo is established to be HNCS.

**Safety:** Do not publish original ELF/firmware bytes, original vendor tuning values, original DNGs, private capture metadata or photographs. Do not change `main`, saved JPEG/DNG colour, Photon capture or Android app code. No new APK is supplied by this stage.