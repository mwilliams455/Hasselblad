# Stage92: JPEG colour and exposure preview

Stage89/90 applied a relative neutral tone curve over an already rendered HAL viewfinder. It did not remove the camera's brightening, colour transform, white balance or post-RAW boost, so it could not represent the saved JPEG. The user's recording shows the live scene substantially brighter than the saved image. That observation identifies a mismatch, not a measured universal exposure offset.

Stage92 replaces that live path in ordinary RAW-backed Photo mode. The camera preview requests a controlled sRGB contrast curve. Returned per-frame tone curves are inverted, followed by the returned colour matrix and WB gains. The result is adjusted for reported post-RAW boost, predicted still/preview exposure energy, and the RAW black-level normalization convention. The reconstructed camera RGB passes through the existing camera-to-D50 bridge, automatic illuminant LUT, selected film curve, native gradation and output/sRGB finishing used by saved JPEGs. No fixed brightness offset or scene-fitted calibration is used.

The GPU samples a 33³ RGB cube with explicit high-precision trilinear interpolation (avoiding reduced-precision hardware filtering), rebuilt at most five times a second on one background worker. There is one running calculation and one replaceable pending calculation. Sharp preview and blurred UI regions use the same frame snapshot. This is still a reconstruction of a processed, quantized preview: HAL clipping, gamut clipping, spatial processing, rapidly changing exposure/WB and preview resolution can prevent an exact match. JPEG sharpening remains a saved-image operation.

## Camera ownership and fallback

- Preview and RAW output configurations must identify the same device/physical stream. Physical results and characteristics must match the active preview sensor; no logical metadata is silently substituted for a missing physical result.
- The returned tone mode must actually be CONTRAST_CURVE, and all required colour/exposure/neutral metadata must be present and valid. Unsupported or singular metadata restores the original camera tone configuration and original viewfinder; the misleading relative Stage89 treatment is not retained as a fallback.
- Profile/curve/preference changes invalidate the old cube immediately. Session close cancels work and unsubscribes. Logical sensor changes reject previous-sensor work, including an A→B→A sequence. Future metadata is not applied to an older SurfaceTexture frame; cubes expire after one second of sensor time.
- The camera's previous tone mode/curve are saved per builder and restored when disabled, unsupported, or outside ordinary Photo mode. Still requests, the saved RAW/JPEG pipeline and exposure-selection implementation are unchanged. Preview prediction calls the existing no-recording exposure selection branch (`step=-1`); it does not insert exposure pairs or alter still requests.
- Settings show the last camera preview status and fallback reason. Optional capture evidence records `preview92_status`. No private profile, tone pack, RAW, photograph, vendor library or keys are bundled.

## Validation

Run `python3 hasselblad_native_audit/phocus_preview_stage92/check92.py --work /tmp/hb92-tests` with a JDK and Mesa EGL/GLES available. For a runtime-only Java installation, supply `--jni-include` with JNI headers. The driver first checks the existing profile/store revision behaviour, then compiles the production inverse/cube/worker/Camera2 adapter unchanged. Android API doubles provide deterministic metadata, rather than simulating a real HAL.

Coverage includes non-diagonal colour matrices, WB, 1×/2×/4×/8× post-RAW boost, different still exposure ratios, invalid metadata, immutable snapshots, exact cube-grid parity with native saved-JPEG rendering, bounded work under 1,000 queued updates, cancellation and invalidation, physical-sensor provenance, preference/curve invalidation and stale/future frame gating. Mesa compiles the production OES shaders and fallback shaders. A 2D camera-texture adapter checks enabled RGB interpolation and disabled sharp/blur equivalence, plus colour treatment before blur. Source pins enforce the saved-photo boundary. These are host/build results, not proof of a match on the user's phone.

## Phone check

Install over Stage91, retaining the existing private automatic profile and tone pack. Enable **Preview JPEG colour and exposure** in the Hasselblad look settings. In Photo mode, compare the same stationary scene before the shutter and in the saved JPEG. Check both curves 0 and 1, then a darker and brighter scene, a lens change and a return from the gallery. Settings report the last camera status: it should say **JPEG colour preview active**. If the camera cannot support reconstruction, the reason appears there and the original feed remains usable. No diagnostic ZIP is required to try the fix.

Primary Camera2 contract: https://developer.android.com/reference/android/hardware/camera2/CaptureResult (TONEMAP_MODE, TONEMAP_CURVE, COLOR_CORRECTION_TRANSFORM, COLOR_CORRECTION_GAINS, CONTROL_POST_RAW_SENSITIVITY_BOOST).
