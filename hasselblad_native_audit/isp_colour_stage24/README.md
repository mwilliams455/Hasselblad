# Stage 24 — first executable phone-RAW colour reference renderer

**22 October 2026 · HasselbladPhoton · firmware-equivalence priority · research-only**

## Result

Stage24 is the first full-frame **offline colour-rendering implementation** in this research series. Its native C11 engine composes the previously validated Stage18 **DNG camera-native linear RGB -> XYZ D50** and Stage19 **XYZ D50 -> linear sRGB/Display P3**, and exposes Stage21's research-only planar-LUT pixel sampler as a strictly gated, separately labelled optional hypothesis.

Stage24 is **not a finished HNCS renderer**. It supplies **no original Hasselblad ICC/LUT/pixel-stage data**, no proof of the six-coefficient MAIN CCM pixel operation, no original MAIN gamma pixel evaluation, no original MAIN photographic LUT sampler/working coordinates, and no calibrated Hasselblad AWB. The mere existence of the Stage21 optional path **does not authorize saved-image HNCS output**.

A private full-resolution example was rendered from the existing 4096×3072 Xiaomi phone RGGB DNG in this project. The source frame was SHA-bound to the existing private Stage18 matrix receipt. The image was demosaiced with **OpenCV's diagnostic Bayer implementation**, then a full-frame set of real camera pixels was passed through the Stage24 native C mathematics in **1,024-pixel chunks**. The saved **32-bit float linear RGB TIFF preserves negative and highlight-headroom intermediate values**; a separate JPEG preview uses ordinary sRGB encoding and display-only clipping. The private TIFF/JPEG output, capture metadata and camera matrix are **not** in GitHub.

The private report contains the actual host conversion timing, scene-linear extrema and negative/headroom counts. These are specific to this single personal capture and are not distributed in public repository source. A separate reference-JPEG scalar exposure alignment was also exercised privately; it is a diagnostic comparison to Photon output, **not a proposed HNCS tone curve**.

### Exactly what's verified

1. The DNG metadata has RGGB CFA, matching `ForwardMatrix1/2` and `CameraCalibration1/2`, and `AsShotNeutral` derived from existing phone HAL/Photon. The Stage24 C-built camera->XYZ matrix was checked against the independently generated Stage18 private DNG matrix for this **exact DNG hash**.
2. The native Stage18/19 composition, including D50 Bradford output adaptation, is independently tested against NumPy across random synthetic camera profiles under GCC and Clang. The C path operates on real photo pixels, not only synthetic probes.
3. A 6144-word **synthetic identity 3D LUT** validates the optional Stage21 candidate interface under trilinear and tetrahedral methods. Original Hasselblad LUT data are not embedded. Invalid pixels (outside 0..1 for that candidate), malformed input, source overlap or invalid LUT values abort and preserve outputs. The original MAIN GPU coordinate mapping and interpolation **remain unknown**.
4. All current reports and native receipts explicitly set Hasselblad CCM/gamma/LUT parity and authorised camera photographic rendering to **false**.

### Original DNG limitations explicitly preserved

- The DNG declares an `OpcodeList2` (includes camera RAW processing corrections). Stage24 **does not implement these opcodes**. The command therefore fails unless `--accept-unhandled-dng-opcodes` is explicitly passed. It also does not apply the original phone's lens shading, local denoising, sharpening or Photon demosaic. These differences prevent claims of a high-accuracy colour comparison with the original Photon JPEG.
- The current software demosaic is an explicit OpenCV baseline (RGGB channel orientation checked with unequal synthetic red/green/blue channels), **not original Hasselblad or Photon demosaicing**. The initial implementation refuses unequal per-site black levels rather than guessing corrections. The Stage18 DNG contract rejects differing dual-illuminant forward matrices instead of fabricating an interpolation. Both limitations will matter on additional phone sensors.
- Scene-linear output is neither a display-ready PNG nor an SDR-looking photograph until an ordinary **final output transfer/clip** is chosen. Stage24 separates the encoded preview from unmodified linear TIFF values. It has no Film Curve, gainmap/HDR output or camera exposure policy.
- The camera sensor is Xiaomi, not the Hasselblad X2D II. The original MAIN LUT input working space, X2D-specific sensor calibration and exact pipeline order have not been ported. Stage21's **DISPLAY-based** candidate is not original MAIN proven pixel behaviour. No X2D exposure or colour rendition is claimed.

## Files

- `src/hb24_renderer.c` and `.h`: bounded, source-only C composition with `hb24_build` and `hb24_process`. Shared Stage18/19 dependency logic, optional Stage21 LUT hypothesis. Transactional outputs and explicit failure statuses. Maximum chunk: 1024 source camera RGB pixels.
- `src/offline_render24.py`: offline DNG metadata parser, explicit opcode acknowledgement, RGGB demosaic, full native C processing in chunks and private output. Optional 32-bit linear RGB TIFF and display-only sRGB JPEG. Separate alignment JPEG only if paired Photon JPEG is supplied.
- `tests/test_renderer24.py`: independent synthetic NumPy oracle (GCC/Clang), random camera profiles and both output gamuts, buffer guards and a synthetic identity LUT.
- `tests/test_renderer24_sanitized.c`: AddressSanitizer and UndefinedBehaviorSanitizer guards on synthetic input.
- `STAGE24_SYNTHETIC_GCC.json`, `STAGE24_SYNTHETIC_CLANG.json`: public synthetic receipts. Original RAW and private reports are **not included**.
- `.github/workflows/hb-isp-stage24-offline-render.yml`: source and numerical validation. Deliberately never fetches an original user DNG or vendor LUT payload in CI.

## Reproduction

From the repository root:

```bash
python3 hasselblad_native_audit/isp_colour_stage24/tests/test_renderer24.py \
  --compiler gcc --output /tmp/STAGE24_SYNTHETIC_GCC.json
python3 hasselblad_native_audit/isp_colour_stage24/tests/test_renderer24.py \
  --compiler clang --output /tmp/STAGE24_SYNTHETIC_CLANG.json
```

Private DNG only, never as a CI job or a public issue attachment:

```bash
python3 hasselblad_native_audit/isp_colour_stage24/src/offline_render24.py \
  --dng /private/IMG.dng \
  --out-directory /private/hb-stage24 \
  --gamut srgb \
  --accept-unhandled-dng-opcodes \
  --linear-tiff
```

Optional `--reference-jpeg /private/IMG.jpg --match-display-exposure` generates a **different exposure-matched comparison**, not a camera calibration, colour profile or HNCS tone curve. `--verify-private-matrix` checks private Stage18 matrix binding on the exact same source DNG.

**Note:** the `--linear-tiff` output can exceed 150 MB for a 12 MP image because it is uncompressed float32 RGB. This size is deliberate for no-clipping analysis. A phone deployment will need tiling, GPU compute and validated precision/throughput.

## Next firmware-equivalent integration gate

1. **Continue original X2D II MAIN pixel work in parallel:** need actual six-coefficient CCM scale/geometry, gamma input precision, MAIN LUT channel/working space and interpolation, before claiming HNCS. Avoid selecting channel permutation `210` from Stage22's inconclusive gamut comparison.
2. **Android port of the *verified* colourimetric module** as a development-only native option, receiving per-capture RAW and matching Camera2 calibration, without taking over the production JPEG. Preserve RAW/Pho­ton baseline, no new unconditional look.
3. Test native full-frame parity/performance on the Xiaomi 15 Ultra and another device, including LensShadingCorrectionMap or DNG opcodes, correct orientation and differences between 12 MP and max-resolution RAW.
4. Add real Phocus-rendered X2D II targets under controlled lighting to disambiguate original colour stages, not merely measure camera JPEG versus LibRaw.
5. Only then make an **opt-in** *experimental* photographic colour mode, with separate `original_equivalent`, `working_hypothesis` and `empirical` metadata. No unverified colour processing should silently affect saved photos or the Leica ports.

**Production state:** branch `main`, Stage8 APK 27186 and existing Photon still rendering remain unchanged. Source and build outputs exclude original firmware/LUTs, private photos and full matrix receipts.
