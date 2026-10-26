# Stage88 — reuse finishing lookup tables

Stage87 remains the feature baseline: curve/profile selection, optional sharpening,
diagnostics and save modes are unchanged. This build removes repeated table setup
from the existing finishing stage. It does not tune colours, add denoising or change
the live viewfinder. No re-import or new setting is required.

## Change

The old JNI constructed the 65,536-entry default gradation table for every band.
Stage55 output also rebuilt its 65,536-entry power-decoding table on every call.
A typical 4032×3008 photo has 47 bands.

`finish88.c` computes the original gradation table once with `pthread_once`, then
calls the unchanged `hb55_gradate`. A mutex protects one output-decode cache entry,
keyed by the exact validated exponent. Each call copies that table into its own
existing scratch allocation and releases the mutex before processing pixels.
Changing the exponent rebuilds the entry. Matrices are read afresh on every call;
they are not cached. Different profiles and concurrent calls therefore cannot
reuse a wrong matrix or a partially replaced decode table.

The cache retains 393,216 bytes (384 KiB) of numerical lookup tables, plus small
synchronization/key fields. It stores no images, profile payload or camera metadata.
It has no Java/native handle lifetime, per-capture ownership or unbounded growth.
Concurrent renders with different exponents can lose the performance advantage
by replacing the single entry repeatedly, but retain the same output.

The Stage55 reference is kept unchanged. The cached output loop preserves its
operation order, float/double stores, matrix multiplication, transfer function and
rounding. No fast-math or approximate gamma lookup is introduced. RAW preparation,
demosaic, colour/LUT, sharpening and publication code remain pinned.

## Validation and measured limits

```sh
python3 hasselblad_native_audit/phocus_finish_stage88/check88.py --work /tmp/hb88 --sanitizers
python3 hasselblad_native_audit/phocus_capture_stage87/check87.py --work /tmp/hb88-integration
```

- 57 numeric comparisons, 11,206,656 RGB16 channels, maximum difference zero.
  Inputs cover every uint16 code, permuted channels and random colour; output
  exponents are 0.25, 1, 1.8, 2.2, 3 and 8, with identity and mixed-sign matrices.
  Exact in-place operation and rejected invalid parameters are checked.
- A separate executable starts four threads against cold caches, then compares
  160 concurrent renders with differing exponents/matrices against Stage55.
- One gradation build and one decode build for 47 same-exponent calls are verified.
- The actual Java/JNI capture integration checks pass with sharpening off/on,
  diagnostics off/on, partial bands, cancellation and failed sinks. RAW and
  demosaic remain explicit adapters; the old demosaic suite is not rerun.
- CI runs address/undefined-behaviour sanitizers with leak detection. Local
  sanitizer checking passes with leak detection disabled because this container
  prevents LeakSanitizer from inspecting `/proc`; CI supplies the full leak check.

The retained local benchmark alternates five uncached/cached runs of the finishing
stage only, using a synthetic 4032×3008-equivalent workload. Its medians were
2,818.26 ms uncached and 2,472.80 ms cached (12.26% lower). These are host results,
not Android latency or an end-to-end shutter claim. CI also records its own timing;
speed is not used as a pass/fail threshold.

Stage86's saved-DNG sharpening phone comparison is preserved evidence. Stage87
normal-camera sharpening and this optimization still await a phone capture; no
new device validation is claimed by this build. Take one ordinary JPEG with the
chosen sharpening setting, confirm it saves/opens, and send the original JPEG.
Keep diagnostics off for normal use; enable them only if timing or a failure needs
investigation. No new DNG comparison is required.
