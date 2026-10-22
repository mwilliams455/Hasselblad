# Stage 30 — DNG Stage2 GainMap correction for the neutral RAW reference

**22 October 2026 · HasselbladPhoton / X2D II firmware-first project**

## Result and scope

This introduces a deliberately **opt-in, offline, non-HNCS** correction for phone DNGs that contain only supported `OpcodeList2` GainMap instructions. It builds on the working Stage24 native colourimetric path, which maps already-demosaiced camera-linear RGB through the DNG ForwardMatrix and XYZ D50 into linear sRGB/P3. Unlike original Stage24, the new branch applies DNG spatial gain maps to normalized RGGB photosites **before** a separate diagnostic float32 bilinear demosaic. The regular Stage24 behavior, native C engine, Android saved JPEG, default viewfinder and Stage26 signed APK 27187 are unchanged.

This is about **removing confounding lens-shading differences** when evaluating phone sensor colour. It is not Hasselblad's six-coefficient MAIN CCM, HNCS, MAIN gamma or MAIN 3D LUT.

## New source

- `src/dng_gainmap30.py`: strict big-endian DNG opcode framing; validates GainMap ID 9 and parameter sizes, rectangle, Bayer row/column pitch, spatial interpolation grid, finite bounded gains and single-plane range-mapped RAW domain. Applies sequential GainMaps via normalized pixel-centre coordinates and edge replication, clipping each affected stage2 sample at unity per the published DNG/SDK behavior. Maintains all four Bayer sites independently. Includes separately labelled float32 Bayer-bilinear demosaic.
- `tests/test_gainmap30.py`: 28 synthetic tests, including exact independent scalar-vs-vector bilinear gain interpolation, four RGGB gain maps, pitch separation, malformed and optional-opcode refusals, out-of-bounds gain rejection, constant-channel demosaic identity, input immutability and no unwarranted SDK/HNCS parity claims.
- `tests/test_stage24_integration30.py`: no-private-image test of the new Stage24 branch and retained standard demosaic interface.
- Stage24 `src/offline_render24.py`: adds `--apply-supported-dng-gainmaps`; refuses other opcode lists, absent GainMaps and unsupported opcode IDs. It cannot be combined with `--accept-unhandled-dng-opcodes`.
- `.github/workflows/hb-stage30-dng-gainmap-reference.yml`: host-only numerical, integration and privacy checks, without downloading any private phone image or original Hasselblad firmware.

## Evidence and limitations

Grounded public specifications and implementations:

- Android DNG opcode builder, including the four Bayer sites and row/column pitch: https://android.googlesource.com/platform/frameworks/av/+/06f46cabd0d52f77520919092b589ce16a282a59/media/img_utils/src/DngUtils.cpp
- Adobe DNG SDK opcode semantics and class definitions: https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_opcodes.h
- Adobe DNG SDK gain-map interpolation and stage2 application semantics: https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_gain_map.cpp
- Adobe DNG SDK stage semantics: https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_negative.h

The parser accepts one `OpcodeList2` whose instructions are **exclusively** supported GainMaps. Even unknown `optional` opcodes are rejected, because silently skipping photographic corrections defeats accurate comparison. Gain maps with unsupported multichannel plane selections, extreme coordinates, malformed grids or out-of-bounds areas also abort. The currently inspected Xiaomi 12 MP phone DNG was recorded with an `OpcodeList2`, but the original image is not included in public tests; do not claim Stage30 has applied it to that frame. A private capture diagnostic reports a lens-shading map, but this is neither the encoded DNG opcode payload nor a pixel oracle.

Algorithmic limitations: independent float32 bilinear interpolation is not claimed bit-exact with Adobe's DNG SDK; no device-specific colour/neutral calibration is inferred; OpenCV interpolation is a diagnostic substitute for Photon/X2D demosaic. The audited Stage24 DNG metadata fast path still requires RGGB, equal black levels and matching dual-illuminant ForwardMatrix/CameraCalibration pairs. There is no support for opcode lists 1 or 3, warp/distortion, other Stage2 opcodes, max-resolution remosaic, or sensor-specific corrections outside the one documented GainMap category. Crop/active-area origins require particular care in any phone-vs-Photon comparison. Strong assertions of DNG fidelity require an independent real-frame DNG SDK/LibRaw reference, and Hasselblad fidelity requires the original ISP pixel oracle.

## Run synthetic checks

```bash
python3 hasselblad_native_audit/isp_dng_stage30/tests/test_gainmap30.py
python3 hasselblad_native_audit/isp_dng_stage30/tests/test_stage24_integration30.py
python3 hasselblad_native_audit/isp_colour_stage24/tests/test_renderer24.py --compiler gcc
```

## Private DNG command

```bash
python3 hasselblad_native_audit/isp_colour_stage24/src/offline_render24.py \
  --dng /private/phone.dng \
  --out-directory /private/hb-stage30-corrected \
  --gamut srgb \
  --apply-supported-dng-gainmaps \
  --linear-tiff
```

**Do not combine** this with `--accept-unhandled-dng-opcodes`. The old explicit unhandled-opcode diagnostic branch remains available for historical comparisons, but does not produce a corrected DNG reference. Original user captures and full-resolution TIFF must remain private, not in GitHub or public Actions.

## Firmware-equivalence gate (unchanged)

Stage17 proved original MAIN CCM coefficient preparation; Stage25 joined its 16×6 signed registers; Stage27 bounded static still group/ISO equalities; Stage28–29 proved B2R→CCM format/callback registration and likely geometry-field provenance. None recovered the hardware six-coefficient pixel equation, Q-scale, selector runtime overrides, RGB order, clipping or rounding. An Eagle2 MAIN-specific hardware specification or isolated before/after-CCM ISP pixel oracle is required before authorising a firmware-colour renderer. **This new DNG correction does not reduce that gate.** The Android default stays Photon and its 27187 synthetic diagnostic is the last device-proven Stage26 check.
