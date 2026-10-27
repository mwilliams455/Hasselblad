# Stage99: bounded correction for coherent edge chroma

Stage97 leaves purple tree/sky fringes. This experimental build adds a local colour correction over its unchanged source-camera RGB. It reduces the fringe in the two private RAW replays; it does **not** establish that the problem is solved or that preview matches output on a phone.

The new stream caches at most three Stage97 bands, supplies a real 15-pixel halo across band boundaries, and releases the cache on completion/failure. Image borders repeat the nearest rendered pixel. The original prepared RAW supplies censor flags including outside the rendered interior. It never falls back to a different renderer.

A 31x31 local RGB/brightness regression proposes chroma. Apply only when RGB channels all correlate positively with brightness, explained RGB variance is high (smooth gate .90 to .98), and 3x3 contrast is high (smooth gate .20 to .50). Opposing channel slopes protect genuine colour boundaries. Bound each normalized chroma coordinate change by .06. Preserve `(R/nR + 2G + B/nB)/4` before quantization. Reject changes producing clipping. Skip zero-valued centre RGB or prepared RAW, and any 65535 RGB/prepared RAW within 15 pixels. Zero-valued neighbours alone do not suppress a supported correction. No hue is singled out.

This is a new adaptation, **not** a recovered Phocus primitive or a proven reconstruction of its original input graph. The original demosaic, native colour-noise stage, RAW preparation, camera matrix, LUT/profile, curve, gradation, sharpening and preview are unchanged. Photo/Motion retain a fresh timestamp-matched single RAW. Original DNG capture and RAW-only publication are unchanged.

## Verification

From repository root, run `python hasselblad_native_audit/phocus_fringe_stage99/pins99.py`, then `python hasselblad_native_audit/phocus_fringe_stage99/check99.py --work /tmp/hb99-check`. Requires Java17, GCC, NumPy/SciPy and JNI headers (`--jni` if needed).

Includes existing Stage97 native/JNI/1152-fixture checks, Photo/Motion and publication/failure cases, new ASan/UBSan tests, whole-image versus streamed bands/tails over 12 dimensions with 1/4 workers, and independent float64 reference comparison for every new fixture. New suite: 1728 line/edge fixtures plus 324 multicolour, woven, purple-texture and dense-branch holdouts. Material regression means RGB RMSE exceeds Stage97 by >5% plus .0001 normalized units. This limit is retained, not relaxed. Fixtures cannot prove real-world colour fidelity.

Local container ptrace can prevent LeakSanitizer; set `ASAN_OPTIONS=detect_leaks=0` only there. CI runs normal leak detection. Android CI verifies both ARM ABIs, 16K ELF alignment, existing certificate, version and private-asset exclusions.

## Phone validation

Install over Stage97 with the same profile/settings. Confirm `0.1-hb-fringe99` / 27237. Compare tree/sky captures in Photo and Motion. Keep matching DNGs and diagnostics; check fine red/blue/purple detail and natural sunset colours as well as branches. Residual fringe, phone runtime/memory and preview/output agreement remain unverified. Do not describe this experimental APK as a completed image-quality fix.
