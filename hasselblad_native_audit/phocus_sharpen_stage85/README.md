# Stage85 — recovered bounded CPU sharpening

The independent C reference reproduces the original CPU sharpening row kernel and
its 16-bit filter wrapper on synthetic images. It is not connected to the Android
renderer yet. Stage84, the user's selected curve 1, capture saving, RAW preparation,
demosaic, colour and output implementation remain unchanged. No new APK or phone
test is required for this milestone.

## Recovered route

The original full-resolution SDR graph places sharpening after film/gradation and
before output conversion. Executing the original import and graph builder with an
explicit 64×64 raw-description fixture selects amount 100, radius 1, noise limit 0,
dark limit 10, scale 1 and normalization 1. The sharpening constructor now actually
executes; Stage55 had replaced that constructor with a fixture. Graph ownership,
the other graph objects and preallocated image-buffer ownership remain fixtures.
These settings are not a calibration of Xiaomi or any other phone's optics.

The CPU filter shifts RGB16 right by two bits, sharpens RGB14, then shifts left by
two bits. Sharpening uses integer luminance, separable quantized Gaussian weights,
integer truncation after each pass, a luminance-dependent amount table and a
noise-difference gate. The same signed adjustment is added to every channel before
clipping. Dark protection can produce negative local amounts; treating it as an
ordinary fixed-strength unsharp mask would be incorrect. At extreme requested
strengths the original 32-bit product can wrap; the reference reproduces this
explicitly without invoking C signed-overflow undefined behaviour. This is not a
recommendation to expose those extreme strengths in the camera.

`sharpen85.c` independently generates its tables. No recovered table payload,
profile, vendor binary, disassembly or photograph is included. The bounded API
accepts amount 0–1000, radius 0.5–4, noise/dark limits 0–255, RGB14 input and up to
16,777,216 pixels. It models full-resolution, no-blur, no-local-adjustment SDR only.
Input and output may be identical or disjoint; partial overlap is unsupported.
Amount zero at this row-kernel API is an exact copy; this does not assert that an
entire graph with sharpening disabled performs a 16→14→16-bit round trip.

## Evidence and fixtures

`STAGE85_NATIVE_VALIDATION.json` records exact comparisons with the separately
supplied, hash-pinned original ARM64 library. The audit executes its table
construction, row kernel, native horizontal/first-row extension and the original
16-bit filter wrapper. It covers ramps, impulses, steps, colour edges, random
pixels, shadows, highlights, constant colour, SIMD/tail widths and settings with
3/5/7/9 taps. Input/output/allocation guards and input ownership are checked.

The row harness supplies repeated last rows to drain the kernel. The complete
wrapper comparison uses a four-pixel interior margin. Neither establishes the
original application's outer image boundary policy. Host libm implements external
log/exp calls. The unused blur conversion singleton is a declared fixture; no
verified pixel arithmetic is replaced. No GPU/live-preview equivalence is claimed.

The public host checks cover invalid-input rejection, exact in-place results,
constant preservation and independent partitioning into bands with real neighbour
rows. CI also runs address/undefined-behaviour sanitizers. It does not require
private inputs and does not rerun previous demosaic suites.

```sh
python3 hasselblad_native_audit/phocus_sharpen_stage85/check85.py --work /tmp/hb85
python3 hasselblad_native_audit/phocus_sharpen_stage85/audit85.py \
  --apk /private/original.apk --work /tmp/hb85-private \
  --safe-receipt /tmp/STAGE85_NATIVE_VALIDATION.json
```

The private oracle reuses earlier audit imports and requires numpy, unicorn,
pyelftools, capstone, tifffile, Pillow, opencv-python-headless, rawpy and scipy.
Assertions must remain enabled. GCC is required for the independent C library.

## Next integration gate

Replace the host reference's full-frame luma scratch planes with a bounded row
buffer, expose JNI, and split the existing combined gradation/output step so
sharpening sits between them. Preserve an exact bypass and immutable per-capture
settings. Verify real neighbour rows across 64-row boundaries and final partial
bands, then add a fixed-input off/on saved-DNG comparison. Keep the current camera
look until that comparison and Android execution are verified. Live-preview
matching, resize compensation and arbitrary local adjustments remain separate.
