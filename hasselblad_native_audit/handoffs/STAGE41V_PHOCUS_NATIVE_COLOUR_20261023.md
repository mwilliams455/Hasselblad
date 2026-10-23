# Stage 41V: readable Phocus colour code and native pixel replay

The supplied Phocus Android APK contains readable ARM64 colour-processing code and GLSL shaders in `libcrosssdk.so`. One CPU colour operator and its five original arithmetic/lookup helpers executed successfully with synthetic calibration and RGB pixels. This gives the research an executable pixel-processing target while the camera firmware's main processing payload remains encrypted.

This is evidence about this specific supplied APK. It does not establish that Phocus and the X2D II's in-camera MAIN ISP use identical algorithms, profiles, precision or processing order. No complete RAW photograph has been rendered in this stage, and the production renderer has not changed.

## Input identity

| Property | Observed value |
| --- | --- |
| Uploaded filename | `phocus2_v1.1.0_20260914_162851_457_hasselblad_publish_release_signed_guard.apk` |
| APK SHA-256 | `5ee52bbb2b7a3fa708628ba251b409a551ae099697668427cf54b523328ccf68` |
| APK size | 183,221,046 bytes |
| Package | `com.hasselblad.phocus2` |
| Manifest version | `1.1.0`, version code `53` |
| Manifest minimum / target SDK | 29 / 36 |
| ZIP integrity | All 1,580 entries pass CRC checks; no duplicate entry names |
| Native library | `lib/arm64-v8a/libcrosssdk.so`, 82,045,176 bytes |
| Library SHA-256 | `d757237554529f8ab485f88f2c5e5399fbc8d56035c79b8e057b41a40fd055e4` |

Signature schemes v1, v2 and v3 are present. The extracted signing certificate has SHA-256 `4bd427ba30527254192f81031c5d14c11df1fbc9be272286fab52dd2d59df738`. This audit does **not** cryptographically verify the APK signatures or independently match the certificate against a manufacturer distribution. The filename and package name alone do not authenticate the input. Manifest SDK values are installation metadata, not a claim about advertised device support.

The application class is an AppGuard wrapper and the visible DEX exposes only nine classes. That protected Java layer did not prevent inspection or bounded execution of the selected native functions. No protection removal, application installation, camera, account, or rooted device was needed for this stage.

## What is readable

| Component | Address in this library | Evidence / significance |
| --- | --- | --- |
| `RawUtil_getRawBitmapByRect` JNI entry | `0x3285394` | Direct call to `getSRGBDataFromFullSizeProcess`; a native RAW-to-sRGB entry point exists |
| `CColorCorrectFilter::FilterResultGpu` | `0x3325e6c` | Direct calls create colour gradation textures and a CbCr LUT, bind images, and dispatch a compute task |
| `CVectorMethods::ColorNormalCorrectPixels` | `0x350112c` | Actual RGB input/output operator, executed in this audit |
| `Scaled2DLUT::Lookup` / `LookupIndex` | `0x3699640` / `0x3699658` | Original scaled bilinear lookup helpers, executed |
| `CColorCorrection::CalculateGrayWeight` | `0x34ca0d4` | Original neutral/shadow weighting helper, executed |
| `Matrix3x3::operator[]` / multiplication | `0x369ce50` / `0x369bbf4` | Original matrix helpers, executed |

The JNI entry, GPU filter and CPU operator are separate observed portions of the library. A complete entry-to-render call graph has not been established. In particular, the RAW correction wrapper's virtual dispatch has not been resolved to the concrete runtime vector implementation.

Readable shader sources include `color_correct_computeShaderSource`, `colorCorrectAll_fragmentShaderSource`, `gamma_hasselblad_fragmentShaderSource`, and `filmcurve_fragmentShaderSource`. The receipt records their sizes, addresses and hashes, without reproducing source. The GPU colour filter's LUT/gradation preparation and dispatch are statically traced; this stage does not establish the exact shader-pointer argument or execute a GPU shader.

The APK also contains 26 `assets/Colormaps/*.dat` and 59 `assets/GMaps/*.dat` files. Their formats, model associations and use for X2D II have not been established. These filenames are leads, not identified camera profiles.

## Recovered CPU operation

The selected normal-colour routine accepts packed 16-bit RGB triples and a correction object. Its observed operations are:

1. Transform RGB into a luminance/chroma representation using a 3×3 matrix.
2. For positive luminance, divide both chroma coordinates by luminance and perform a scaled, bounded bilinear lookup in a two-component 2D table.
3. Calculate a weight from the input's distance from neutral, with optional shadow desaturation.
4. Reconstruct RGB using the original luminance and weighted, corrected chroma.
5. Clamp reconstructed components to the 16-bit range, truncate to table indices, read a float gradation table, and convert the result to 16-bit output.

Nonpositive luminance follows the black-output branch. This control-flow interpretation is specific to the CPU routine. The shader paths have different numeric representations and were not shown to be equivalent at black or at rounding boundaries.

The execution fixture supplies its own reversible matrices, 9×9 chroma grids, weighting thresholds, and an identity output gradation table. These are deliberately synthetic and do not represent Hasselblad calibration. In particular, the replay does not validate a genuine camera gradation curve or the full range of possible correction-object settings.

## Native execution and verification

The harness reads the original instruction bytes directly from the hash-pinned APK. Unicorn executes the colour operator and all five helper bodies. Calls through the procedure linkage table are redirected to those original bodies; no arithmetic or lookup helper is replaced by a Python answer.

The independent NumPy calculation uses the inferred operation and the same synthetic inputs. There are 274 RGB triplets: black, basis/secondary colours, white, ten neutral ramp values, and 256 seeded random samples. They are reused across three synthetic maps and two protection configurations, giving **1,644 pixel evaluations and 4,932 channel comparisons**.

| Synthetic map | Protection | Pixels | Exact channels / 822 | Largest absolute difference |
| --- | --- | ---: | ---: | ---: |
| Identity | Off | 274 | 821 | 1 |
| Identity | Gray and shadow | 274 | 822 | 0 |
| Chroma mix | Off | 274 | 820 | 1 |
| Chroma mix | Gray and shadow | 274 | 820 | 1 |
| Curved | Off | 274 | 822 | 0 |
| Curved | Gray and shadow | 274 | 822 | 0 |

**4,927 channels match exactly; five differ by one unsigned 16-bit code value.** A one-code tolerance was fixed before replay to allow floating-point evaluation-order effects at truncation boundaries. This result is not a bit-exact equivalence claim, nor proof of the cause of each difference.

Every case reaches the expected return address within its instruction budget. Black produces zero, 32-byte guards before and after the output remain unchanged, and the input pixels, correction object, LUT and gradation table remain unchanged. Unexpected code execution raises an error. The original APK hash is checked before and after the audit.

Static checks validate the library's PLT slot structure and relocation targets, independently calculate direct branch destinations, and check selected call edges against disassembly. Shader pointers are resolved through ELF relocations. These checks support the recorded native evidence; they do not prove the behaviour of unexecuted functions.

## Reproduction

Use Python 3.12 and the original private APK. Run without Python's `-O` option: the audit intentionally uses assertions for verification.

```bash
python -m pip install -r hasselblad_native_audit/phocus_stage41v/requirements41v.txt
python hasselblad_native_audit/phocus_stage41v/inspect_phocus41v.py \
  --apk /absolute/path/to/the/supplied.apk \
  --receipt /absolute/path/to/STAGE41V_PHOCUS_NATIVE_COLOUR_SAFE.json
```

The accompanying receipt contains input/library hashes, native-library inventory, selected function hashes and call edges, shader hashes, and synthetic replay aggregates. The repository additions contain our audit code and derived findings only. APKs, native payloads, shader source, disassembly, calibration arrays and photographs are not included.

## Next research target

Trace how Phocus selects and constructs the correction object: identify the readers of the colour-map assets, determine how camera model and RAW metadata select a profile, and establish which matrices, chroma tables and gradation curves are used for X2D II. Then extend native replay with that verified configuration and compare a complete render of an existing RAW against a controlled Phocus export.

The existing encrypted camera firmware remains a separate source of evidence. This discovery provides a practical route to understand Phocus colour operations without first decrypting that firmware. Matching the X2D II camera JPEG and adapting the result to another sensor each require additional validation.
