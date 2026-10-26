# Stage93: keep fractional black-level captures on the Hasselblad path

The Stage92 phone recording showed `JPEG colour preview active: curve 1, 5000 K; exposure ratio 1.000` and a last-capture message starting `Last capture routed to Photon: Existing DNG writer requires`. That prefix uniquely matches the bridge's integer-only original black-level guard. The supplied resized JPEG has no EXIF, so the recording is evidence of a recent fallback, not a provenance guarantee for every attached photo. No brightness offset was fitted to the images.

The preview was allowed to reconstruct fractional black levels, while the saved-photo bridge rejected them and returned to Photon. Stage93 corrects this mismatch at the capture boundary. Original finite fractional `SENSOR_DYNAMIC_BLACK_LEVEL` values now travel through a dedicated Java/JNI writer API into DNG BlackLevel RATIONAL entries, in the original RGGB order. The existing RAW reader already supports rational black levels and uses them in its per-site subtraction and common white-minus-maximum-black normalization.

The TIFF writer's rational setter also incorrectly required BlackLevel count to equal SamplesPerPixel. A 2×2 Bayer repeat needs four black levels with SamplesPerPixel=1. The setter now accepts repeat-sized counts and checks that conversion preserves each original value exactly. Invalid or unrepresentable values are rejected instead of silently rounded.

Integer black levels continue through the existing SHORT-tag path. The precise API is restricted to original unbinned, uncompressed 16-bit sensor RAW. Other compressed/binned Photon modes retain their existing integer API and behaviour. The preview correction, exposure selection, colour/LUT/film/finishing/sharpening kernels, RAW reader, and save publication are unchanged. This build addresses the observed capture fallback; it does not claim that every residual phone preview difference has been eliminated.

## Validation

`python3 hasselblad_native_audit/phocus_preview_stage93/check93.py --work /tmp/hb93-tests`

The test compiles the actual production Java Camera2-to-DNG bridge, Java DNG wrapper, JNI C++ writer and RAW reader. Only Android metadata, logging and unused framework dependencies are doubles. It writes integral, fractional, unequal-channel, zero and near-white black levels, plus fixed-seed randomized Camera2 float values. An independent TIFF parser checks the tag type/count/rationals, CFA repeat size, SamplesPerPixel, WhiteLevel and untouched RAW values. The production reader is checked against the fractional normalization formula at every site. Tests cover padded rows, buffer immutability, invalid Java/JNI inputs, closed writers and rejection of unsupported sample-domain transformations.

A separately compiled Stage92 native writer produces deterministic legacy uncompressed, compressed, binned and 10-bit files; each must be byte-identical to the new writer's corresponding legacy output. The Stage79 metadata/allocator spy is retained and updated to expect exact fractional transport. No demosaic or colour reconstruction work is repeated. Tests contain no user photographs or private profiles.

## Phone acceptance

Install over Stage92, retaining the selected automatic profile and curve. Take a fresh ordinary Photo capture with JPEG or RAW+JPEG enabled. The last-capture report should identify Hasselblad output rather than the previous integer-black-level Photon fallback. Compare that newly saved image with the live preview. Existing photos are unchanged.

References:

- Android CaptureResult `SENSOR_DYNAMIC_BLACK_LEVEL`: https://developer.android.com/reference/android/hardware/camera2/CaptureResult#SENSOR_DYNAMIC_BLACK_LEVEL
- Adobe DNG 1.7.1, BlackLevel and BlackLevelRepeatDim: https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf
