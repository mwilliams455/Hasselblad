# HasselbladPhoton Stage 32 — signed real-DNG neutral-centre-tile diagnostic handoff

Date: 22 October 2026 (UK)
Project repository: https://github.com/mwilliams455/Hasselblad
Working branch: `recovery/awb-rebuild-20261021`
**Last tested source commit:** `c9f6a524362a938db149bed6830cf2422946fe78`
**Verified signed CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39848557538 — completed SUCCESS
Production `main`: `929f523aa02ae5b224be39b9c36cce5975691a10`, untouched.

## Why Stage 32 was implemented

Stages 17/25/27/28/29/31 have recovered and verified portions of the X2D II 1.3.16.2 MAIN CCM coefficient preparation, hardware register descriptors, and format/debug wiring. However, the **actual six-signed-coefficient Eagle2 MAIN CCM pixel equation, fixed-point scaling, RGB channel mapping, rounding, clipping, gamma pixel sampling and MAIN 3D-LUT interpolation are NOT yet proven**. Stage 31 also established that the publicly visible CCM debug-mux interface is not a verified RGB pixel oracle.

Stage 30 built and host-tested a strict DNG OpcodeList2 GainMap corrector for the offline neutral reference. Stage 26's Android native JNI passed 11/11 synthetic tests on the phone, but had never processed actual DNG samples. Stage 32 closes the immediate **real-RAW intake and evidence** gap, without substituting guessed HNCS mathematics for original firmware operations.

## Exact implementation

- Android app version `0.1-hb-dng32`, versionCode **27188**, application ID `com.mwilliams.hasselbladphoton`.
- Signed with the **same debug certificate** as the validated Stage 26 APK versionCode 27187. Android can install over it without clearing settings. Signing fingerprint verified in CI.
- Development screen gets a `Stage32: Pick existing DNG for neutral tile test` button, a status line, and `Copy Stage32 DNG diagnostic JSON`. Android's system OpenDocument picker gives access to **only the file chosen by the user**. It does not hook shutter, active capture, preview, photo saving or Camera2 RAW capture.
- Java `HasselbladDngTileReader` uses a strict read-only classic TIFF parser and strip-level seeking. Accepted image domain: little- or big-endian uncompressed **16-bit single-plane RGGB** DNG (IFD0 or a child), 2x2 CFA, 1 or 4 site black-levels, scalar or matching 4-site white levels, simple contiguous uncompressed strip rows. File size capped at **256 MiB**. Compressed/tiled/unknown layouts fail closed.
- A 34×34 centre neighbourhood is read, normalized by embedded DNG black and white levels, optionally corrected by supported GainMap-only OpcodeList2 CFA-site grids, and bilinearly demosaiced to a 32×32 = **1,024 pixel** *diagnostic camera-linear RGB tile*. Both green sites are separately corrected and preserved. Original photosites are not silently re-quantized to 16-bit after shading.
- Exact supported DNG OpcodeList2 rules are intentionally narrower than all legal DNGs: only opcode ID 9, signed/finite gains, bounds and four-class CFA site pitch 2; `OpcodeList1` and `OpcodeList3` are refused, any unknown optional/required opcode is refused. This approximates the documented GainMap stage but does **not** prove Adobe DNG SDK bit-exact parity.
- If the selected DNG includes compatible ForwardMatrix1/2, CameraCalibration1/2, AnalogBalance and AsShotNeutral, the existing Stage 26 JNI processes the 1,024 pixels using Stage 24 DNG ForwardMatrix -> XYZ D50 -> **linear sRGB**. The existing JNI **rejects different dual-illuminant matrices**; Stage 32 preserves those original values and reports an unsupported-profile result instead of lying about interpolation. If ForwardMatrix1/AsShotNeutral are absent, the report confirms RAW tile intake but does not invoke native PCS.
- JSON is a **bounded aggregate report**: input DNG SHA256, size, image shape, recognized opcode state, supported native status, linear channel mean/min/max if successful, and explicit `original_hasselblad_ccm_pixel_proven:false`, `hncs_rendering_performed:false`, `photographic_colour_still_photon:true` and `saved_photo_or_original_dng_modified:false`. No RAW pixels, JPEG preview, user file paths, filenames, camera serials, original calibration matrix values or vendor firmware bytes are exported. Chosen DNG is copied to an app-private temporary cache file for bounded random access, and that copy is deleted after processing.
- Java processor also safely degrades when the optional ARM64 JNI library is unavailable (the camera app itself retains its existing ABI compatibility).

## CI validation and APK

GitHub Actions run `39848557538` finished SUCCESS with:

1. Guard against any changes to actual camera capture, processing, shaders, or Stage 26 colour JNI native implementation.
2. Host Java synthetic uncompressed DNG fixtures (plain, GainMap, big-endian, wrong CFA, invalid strip bounds, unknown opcode, mismatched dual profile): **25 checks PASS**.
3. Existing Stage26 host-JNI self-test unchanged and PASS.
4. Synthetic real DNG-tile data fed through the native Stage24 C/JNI engine; **5 checks PASS**, including deliberate dual-profile rejection without output-buffer mutation.
5. Stage24 native mathematical numerical regression under GCC PASS.
6. Android SDK/NDK/CMake build PASS; signature fingerprint and application identity match previous signed Stage26, arm64 shared native library LOAD alignment 16 KiB PASS, build version 27188 PASS.

GitHub Actions artifact: `HasselbladPhoton-Stage32-27188` (id `12455564215`), includes the signed APK and machine-readable reports; artifact expires 5 November 2026.

- Direct signed APK: `HasselbladPhoton-Stage32-27188-debug.apk`
- Direct APK size: **70,902,926 bytes**
- Direct APK SHA-256: `44445b42180e27198fbee2f8ef575968cd568e4925fd0ba7027c2b53b3d67728`
- GitHub Actions full artifact ZIP: `HasselbladPhoton-Stage32-27188.zip`
- Signing identity unchanged from Stage 26, package `com.mwilliams.hasselbladphoton`.

Stage 26's old CI workflow was frozen at source SHA `6c8c687609cf92f2ca3b0256728b5b2000d3ec1b` and is manual-dispatch only; Stage 32 owns new Android upgrade builds. The earlier Stage 8/24 signed baselines remain preserved. The production `main` branch remains untouched.

## What the user should test on Android

1. Install APK versionCode **27188** over current Stage 26 `27187`, without uninstalling or clearing data.
2. Confirm normal RAW+JPEG camera capture and gallery still behave exactly as before; saved JPEG colour **should remain Photon**.
3. Open the Hasselblad **Development** screen. Press **Stage32: Pick existing DNG for neutral tile test**. Select one original .dng exported by the app (not a screenshot/JPEG).
4. Press **Copy Stage32 DNG diagnostic JSON** and send that text for analysis. This reveals what the actual DNG supports, including format/strips, GainMaps, and native calibration compatibility, without uploading the photo itself.
5. Possible results include `PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY` (actual file decoded and native PCS tile processed), `RAW_TILE_PASS_NATIVE_PROFILE_UNSUPPORTED` (e.g. dual-illuminant matrices need SDK-specific interpolation), `RAW_TILE_PASS_PCS_METADATA_UNAVAILABLE` (required DNG colour tags absent), `RAW_TILE_PASS_ARM64_NATIVE_UNAVAILABLE`, or `UNSUPPORTED_REAL_DNG` with a bounded reason. These are expected diagnostic classifications, not a camera malfunction.

**Not yet tested:** Stage 32 import from the user's specific real phone DNG, DNG SDK numeric parity, full-frame native speed/quality, calibrated Hasselblad AWB, actual X2D II MAIN CCM/gamma/LUT rendering. Host compilation and signed APK availability are not equivalent to an on-device report.

## Next engineering priority (Stage 33)

Use the Stage32 **actual phone DNG JSON** to decide the next concrete code change: support the observed TIFF strips/opcode form if needed, resolve legitimately different ForwardMatrix1/2 using a verified DNG SDK interpolation model rather than discarding one, and introduce a bounded real-image test that can be compared numerically with a trusted neutral reference. Only then expand tiling/streaming beyond the centre 1,024 pixels.

In parallel, keep the original X2D II firmware-first hard gate: obtain a trustworthy **Eagle2 CCM pixel equation or isolated same-stage original hardware before/after RGB oracle**. The third-party Phocus 4.0.1 X2D 100C 2D CbCr ColorCorrect reproduction can serve as independent rendering research only, not evidence that X2D II MAIN CCM shares its data layout or arithmetic. Do **not** invent a 2×3 or constrained 3×3 transform from the six-coefficient count. Future firmware-equivalent pixel code, face tracking and AF remain separate from this neutral intake stage.

**Handoff directive:** Resume at versionCode 27188 on the recovery branch, do not reconstruct Stages 6–32, and do not modify `main` or saved photograph colours. First analyse the actual Stage32 on-device DNG JSON. If it fails closed, fix only the proven incompatibility and rerun CI. Preserve signed rollback and public/private data boundaries.
