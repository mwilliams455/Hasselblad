# Stage43 — direct saved-DNG preview

Adds an opt-in Android preview that reads a user-selected DNG directly. Import a
private `.hbc` colour profile once, then open a standard-resolution DNG. The
screen renders the sampled whole image, can toggle the same-RAW neutral sRGB
baseline, and copies a report with separate copy, RAW preparation, calibration,
core and display timings. This is a preview, not a full-resolution export.
The Stage42 `.hb42` exact-reference test remains available.

The selected DNG supplies its own ForwardMatrix, CameraCalibration,
AnalogBalance and AsShotNeutral. Stage18 maps camera RGB to D50 and owns white
balance; separate core gains are unity. The private profile supplies D50 to the
experimental internal colour basis, chroma map, tone and explicit display
adapter. No X2D sensor matrix is applied to phone samples. The manual LUT
look temperature (4000 K in the supplied private profile) is not phone AWB.

The camera capture and processing paths are unchanged. There is no device-brand
whitelist. The data format determines support. This does not establish full
Phocus, HNCS, demosaic, phone-sensor or camera-ISP equivalence.

## Bounded input branch

Classic TIFF, uncompressed 16-bit single-plane RGGB, up to 16,777,216 RAW pixels,
maximum side 8192, file up to 256 MiB. Single or multiple strips; both TIFF byte
orders. Full active/default crop; orientations 1, 3, 6, 8. One black level or a
2x2 black pattern; scalar/equal white level. ForwardMatrix1 and AsShotNeutral are
required. Unequal dual-illuminant matrices require interpolation and are rejected.
OpcodeList2 may be absent or contain only the tested pitch-2 GainMaps. Unknown
opcodes, OpcodeList1/3, linearization, black deltas, compression, other CFA/crop
layouts and mirrored orientations fail explicitly.

RAW normalization and GainMaps are applied before float32 bilinear demosaic.
Each preview pixel uses full-resolution neighbours, with reflect-101 borders.
Three row buffers avoid storing a full-size RGB frame. Grid sampling is at most
1,048,576 pixels; it is not a filtered final-output downsample. Input values are
clipped/quantized to RGB16 once, as in Stage42. The source URI is read only; the
bounded temporary copy is removed after work. A saved private colour profile is
checksum validated and replaced atomically. Worker cancellation is checked when
copying and on each preview row.

## Evidence

The user supplied `evidence/stage42/STAGE42_USER_DEVICE_RESULT.json`: 786,432
pixels matched the Stage42 host RGB16 exactly, reported core time 16 ms. No phone
model was included in that report. The time covers the Java/JNI call and copies,
not DNG loading or display.

The new Java DNG reader + actual JNI calibration and colour core reproduce all
2,359,296 input channels, final RGB16, displayed RGB8 and neutral baseline RGB8
exactly for the owner's earlier DNG and Stage42 bundle, on the host.
`evidence/stage43/STAGE43_HOST_DNG_CHECK.json` records this local check without
private image bytes, matrices or file hashes. This is not a Stage43 device test.

`make_fixtures43.py` and `Stage43Smoke.java` check full-frame Stage30 reference
pixels for random synthetic RAW, spatially varying GainMaps, different black
levels, both byte orders, strip boundaries, borders, orientations, full and
sampled previews; malformed inputs, invalid calibration/profile and cancellation
are rejected. The suite has 65 checks. The Stage42 core and JNI regressions also
run in the APK workflow. CI has only synthetic inputs.

## Private profile format and creation

Run `prepare_profile43.py --apk OWNER_APK --out PRIVATE_DIR/colour.hbc` locally.
The existing Stage42 loader verifies the exact supplied APK/library/payload.
Never upload the APK, decoded payload, produced profile or photos to public git,
CI or APK assets. Profile data remains a separate owner-imported file.

Little endian: magic `HB43LUT1`; six int32 values (grid width/height, look Kelvin,
model, film, internal-space code); 38 float64 values using Stage42's parameter
layout except the first matrix is D50-to-internal-basis (B*A), not camera-specific;
interleaved grid float64 values; 65,536 float32 curve entries; SHA-256 of all prior
bytes. No photo pixels, source photo hash, WB gains or phone camera matrix are
included. Space code 0 is not named sRGB; the separate display adapter creates
sRGB explicitly. Profile is at most 1.4 MB and must use unity separate WB and
exposure; no automatic exposure matching.

`Stage43PrivateCheck` accepts a DNG, private profile, previous `.hb42` bundle and
receipt output path for a local exact comparison. Do not run it on owner photos
in CI. The native core itself is the unchanged Stage42 implementation.
