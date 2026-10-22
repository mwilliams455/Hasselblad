# Stage 8 — X2D II photographic LUT **profile preparation**, not pixel rendering

**Date:** 22 October 2026. **Project:** Hasselblad Photon. **Scope:** bounded portable reconstruction and optional Android development-only JNI self-check. The Lightroom/Phocus picture look, HNCS pixel correction, gamma transfer, hardware swizzle, cube interpolation and Hasselblad scene AWB are **not** implemented here.

## Firmware evidence and provenance

Based on the existing `hasselblad_native_audit/photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.md` and `lut_profile_native_execution.json` from the verified X2D II 100C **1.3.16.2** Android 9 runtime. Those original functions ran under QEMU/Bionic in the earlier investigation; the present source is an independently written portable implementation **not** a vendor binary. It verifies against the original native function's 12 recorded **synthetic** outputs, not against a photographic RGB pixel or unpublished vendor table. The original-camera 49,152-word LUT's presence and native profile preparation were verified in the earlier study but the payload bytes are **not included** here.

- Relevant saved-photo configuration `MAIN_CCM`, `MAIN_GAMMA`, `MAIN_3DLUT`; three reviewed still reprocessing segments bypass separately named `MAIN_HNCS`. Configuration evidence does not prove full runtime order.
- Interpolation assets: CCT knots `[2400, 3050, 5550, 9100]`, gamut index `0=sRGB, 1=P3`, *eight* packed profiles each `6,144` uint32 words.
- Each word holds two signed 16-bit scalars. CCT-first index `CCT_index + 4*gamut`. Original helper uses bounded Q8 fractions, first interpolates each lane across CCT, then across gamut with signed-negative products rounded toward negative infinity. `2*6144=12,288` scalars happens to equal `16^3*3`, but per-pixel cube axes/component order are still **unknown**.
- Strict `hb_main_lut_prepare` source size and gamut checks; no allocations, no ambient state, no proprietary LUT arrays, no sensor data or photograph input. On invalid input, neither the caller's output words nor receipt are touched; aliasing input/output is rejected.

## Host validation

```bash
python3 -m pip install --upgrade pip  # not required for this script, standard Python is enough
python3 tests/test_profile_native_fixture.py
```

The validator uses `cc` and the Python stdlib. It reconstructs the exact source generator from the original vendor-function probe, checks 12 previous original output vectors (=84 words), checks 22 full-size **synthetic** 6,144-word profiles (=270,336 16-bit components) against independent Python floor-division arithmetic, and tests bad geometry/gamuts/input alias guard behaviour. No X2D firmware or phone camera frame is read. With the app Java/JNI files in the repo, the workflow also compiles and runs the JNI self-check on a host JDK, then builds a signed Android debug APK.

## Android opt-in development check

`HasselbladProfilePreparationCheck` is a standalone Java class with no Android dependencies, and `hb_photo_profile_jni.c` only bridges bounded synthetic input arrays. The on-device activity has an explicit **Run Stage8 LUT preparation self-test** button; no photo capture, settings change, GPU draw, or WB-selection call. Test is on a background thread; the result can be copied as JSON and records `photographic_colour_still_photon=true`, `hasselblad_wb_selected=false`, `render_applied=false`, `pixel_lut_sampler_implemented=false`.

If the optional ARM64 native library is unavailable on a different ABI, return `NOT_PASSED` and keep Photon rendering working. A successful status is a test of the app process's portable profile generator and JNI, **not** evidence of camera HNCS photographic colour or the original vendor runtime running inside the phone.

## Next scientifically meaningful colour work

1. Obtain exact camera MAIN_3DLUT ISP buffer payload and structure *privately* to map its 12,288 scalar lanes to nodes/components; verify with consumer/format metadata or native ISP readback. Until then, do **not** implement an assumed conventional `.cube` sampler or activate a look.
2. Recover saved-still **MAIN_CCM** and **MAIN_GAMMA** numeric pixel domains and registration (257-point gamma with nonuniform `lut_div`; local pre-gamma disabled) and their order relative to LUT. Do not equate preprocessed profile size with image colour accuracy.
3. Once actual pixel layout is proven, build a synthetic **per-pixel** firmware comparison, define coherent phone sensor-to-input mapping and one-time WB. Use calibrated Stage7 neutral only after controlled grey-card and coloured holdout acceptance. Keep other devices supported, single RAW input, no HDR/stacking, photo only.

**Privacy:** Do not commit a firmware CIM, vendor binaries, copied X2D IQ table or private phone DNG/JSON/ROI results into this public repo. Keep any original camera payload in a private research store.
