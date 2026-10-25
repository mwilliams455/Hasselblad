# Stage86 — optional capture diagnostics and Android sharpening comparison

Install the APK as an update. Existing colour profiles, tone packs, curve selection
and Save mode are preserved. Normal camera JPEG rendering remains Stage84; recovered
sharpening is available only in the explicit saved-DNG comparison.

## Ordinary photos

In **Settings → Hasselblad rendering**, **Capture diagnostics** defaults off,
including after upgrade from Stage84. Leave it off for ordinary shooting. In camera
settings choose **Save → JPEG** for JPEG-only output, or keep RAW + JPEG if desired.
Disabling diagnostics does not override that choice or delete existing photographs.

With diagnostics off, new captures do not write `.capture.json` sidecars, retain a
private comparison JPEG/report/sample set, collect scene candidate probes or run
the repeated prepared-RAW reference probe. Required sensor provenance, matched
still metadata, RAW validation, colour and publication checks remain enabled.
The renderer still uses a private temporary DNG internally and deletes its staging
folder after capture. This build does not remove that processing step.

The switch is recorded at capture start; disabling also prevents later sidecar/
comparison retention by an already-running capture. Toggling diagnostics off clears
the old private last-capture comparison cache, not public files. Explicit saved-DNG
experiments continue to create their own requested comparisons regardless of this
switch. A diagnostic export requires diagnostics enabled and a new photo.

## Sharpening comparison

1. Open **Settings → Hasselblad rendering → Compare sharpening on a saved DNG**.
2. Choose an existing standard-resolution DNG. The current imported profile and
   curve are used for both views. No extra tone pack is needed.
3. Switch between **Sharpening off** and **Recovered CPU sharpening**. Save a view
   or export **Hasselblad_Stage86_Sharpening_Comparison.zip** for inspection.

RAW preparation, demosaic, colour/film and default gradation run once. Their shared
RGB16 intermediate feeds both views; output conversion and JPEG encoding are the
same. The recovered path applies original CPU defaults (amount 100, radius 1,
noise limit 0, dark limit 10) between gradation and sRGB output, including the
original 16→14→16-bit precision transition. It does not sharpen Bayer input,
change exposure/WB or apply Photon sharpening. Normal capture remains unchanged
until comparison/device evidence supports enabling it.

A delayed band stream supplies real rows across 64-row boundaries and partial
final bands. Only one pending band and a preceding row are retained in Java;
JNI operates on at most 66 rows. No full-resolution RGB sharpening buffer is
allocated. The Stage85 C kernel is reused byte-for-byte. Image edges use repeated
edge rows/columns, an explicit policy whose parity with the original application's
outer boundary remains unverified.

The comparison ZIP contains exactly two full-resolution JPEGs, two oriented
preview PNGs and one report. The copied DNG, shared gradation pixels and baseline
ARGB intermediate are removed before export. No private profile or calibration
is bundled. One full-size Bitmap is reused for the two JPEGs. Cancelling or closing
the activity clears its private work; comparisons do not publish camera photos.
The live viewfinder still does not show the Hasselblad look.

## Validation

`check86.py` compiles the actual Java stream and Android JNI source on the host,
then compares their 16-bit output against the Stage85 full-frame reference with
independent 1/7/63/64-row partitions. Cases include 4032-pixel width, heights around
64/128 boundaries, input ownership, callback order, bad sizes, incomplete streams,
cancellation, failed sinks and closed streams. The finishing split must exactly
match the existing combined finishing method; optional private profiles are read
locally for the same check.

The actual diagnostics preference and renderer branch run against explicit JVM
adapters. These prove default-off, failed-setting-write handling, skipped reference
probes/samples and unchanged adapter output. Android storage/UI operation still
requires a phone check; the adapters do not claim to emulate it.

```sh
python3 hasselblad_native_audit/phocus_sharpen_stage86/check86.py --work /tmp/hb86
```

Requires Java 17/JNI headers, GCC and numpy. Use `--jni-include` if headers are
elsewhere. CI builds both Android ABIs, verifies the existing signing identity,
16 KiB native alignment, source/version receipts and absence of private payloads.
Old demosaic/native-oracle suites are not rerun; their validated sources are pinned.

Phone check: take one ordinary JPEG with diagnostics off and confirm no new capture
JSON or DNG is saved in JPEG mode. For sharpening, reuse an existing DNG and inspect
fine edges/shadows plus the exported pair. No new demosaic comparison is required.
