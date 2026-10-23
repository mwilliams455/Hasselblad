# Stage 41Y: native RAW matrix composition and ordinary gradation

Phocus's original RAW colour initialization now supplies the matrix composition, generated gradation curve, selected real-profile LUT and shadow settings used by the original CPU pixel routine. The audit replaces Stage 41X's synthetic RGB basis and identity curve. Across 72 controlled configurations, **20,448 synthetic pixel evaluations match the independent calculation exactly: all 61,344 channels**.

The integrated test also resolves an important implementation detail: `ColorNormalCorrectPixels` adds luminance directly to each output channel and uses only the two chroma columns of the reconstruction matrix. Applying that matrix as a generic 3 × 3 multiplication gives different results.

This is a verified colour-processing fragment using explicit per-capture settings. RAW unpacking, input normalization/linearization, demosaic, live Android configuration and complete photographic rendering are still outside the executed path. It does not establish equivalence to the camera's MAIN ISP or validate adaptation to a phone sensor.

## Inputs and reproducibility boundary

The input remains the privately supplied Phocus Android 1.1.0 APK from Stages 41V–X. The audit verifies these hashes:

| Input | SHA-256 |
| --- | --- |
| APK | `5ee52bbb2b7a3fa708628ba251b409a551ae099697668427cf54b523328ccf68` |
| ARM64 `libcrosssdk.so` | `d757237554529f8ab485f88f2c5e5399fbc8d56035c79b8e057b41a40fd055e4` |
| Selected decoded profile | `c2b3d08e0d489eb852610c12a9b985e9d0340a4dd544f5b0b5b7a6a4f3427e95` |

The selected profile is `bohnjuhtuvuvtxyydb56.dat`, version `3.0`, CPID `0x0616`. Stage 41W linked this selection to sensor 22/filter 6 in four X2D II RAWs with `ClosedLoop=false`. That normal configuration is retained here. APK authenticity against an independent manufacturer distribution and the live app's configuration remain unverified.

The harness uses the original profile loader with Stage 41W's Python XML/key-getter facade. It supplies an already-loaded profile cache entry, checks every requested cache ID is `0x0616`, and executes the original selection functions. Cache allocation/file loading is not mistaken for colour arithmetic.

## Matrix construction is now executable

The following original functions execute together with their original matrix helpers:

- `CRawColorParams::GetRawRGB2XYZMatrix`
- `CRawColorCorrection::InitCRawColorCorrection`
- `CRawColorCorrection::GetColorSpaceChangeMatrix`
- `CRawColorCorrection::GetXMLLut`
- `CColorCorrection::SetupCC`

For the tested nonzero-temperature configurations, define:

- `P(T)`: the temperature-specific profile matrix verified in Stage 41X.
- `G`: the diagonal matrix of the three supplied channel gains.
- `A`: the library's fixed conversion preceding the chroma basis.
- `B`: the library's fixed chroma-basis matrix.
- `W`: the transform selected by the numeric working-space code.
- `q`: the scalar selected by the colour-model branch.

The independent matrix calculation is:

```text
stored RAW matrix = P(T) · G
pixel input matrix H = q · B · A · P(T) · G
reconstruction matrix K = W · inverse(B)
```

The audit reads the fixed matrices from the private APK at runtime; it does not embed or publish their values. Original native matrix construction, inversion, multiplication, scalar multiplication and copying execute. Native initialization writes the expected matrices into both the parent RAW object and the correction object.

All six working-space codes 0–5 are tested. Their human-facing UI names are not established by this audit. Code 0 uses the unexpanded LUT and companding code 1; codes 1–5 use the expanded LUT and companding code 2 in the tested path. The independent oracle separately calculates each branch's fixed-matrix composition.

Two colour-model codes are exercised with sensor 22, filter 6 and the final HDR-related boolean false. Code 0 selects the standard LUT and `q=1`; code 1 selects the reproduction LUT, `q=1.7`, and film-curve code 7. These are verified branch behaviours under the stated inputs, not assertions about which UI setting or default the Android app uses.

The gain vectors `[1, 1, 1]` and `[1.8, 1, 0.7]` are test inputs. Scalar values 1 and 2 are supplied to the parent object's fields `+0x1f8` and `+0x248`, matching their shared scalar input in the inspected filter-construction call. The upstream capture provenance and normalization of these values remain to be traced.

## Zero temperature has a separate meaning

`GetRawRGB2XYZMatrix` does not send a zero temperature argument through the usual clamp/interpolation path. It calls `CXMLLut::GetColorMatrixDNG`, which returns the loaded matrix at profile offset `+0x168`: the decoded `mfd` array.

Native execution verifies this result exactly. Four nonzero-temperature wrapper cases also agree with the independent interpolation calculation. Thus, the previously unresolved `mfd` matrix has a demonstrated use, and a port must preserve this zero-argument branch instead of treating every temperature argument as Kelvin to clamp. The test does not imply that ordinary rendering should use a zero temperature.

## Ordinary curve generation is now verified

The library does not obtain these working curves solely by reading a ready-made 65,536-entry output table. Its original `CGradationManager` constructor and `InitGradationCurves` generate the tables using private constants, supporting curve samples, control points, nonlinear transformations and cubic splines.

Three relevant startup functions were identified through the ELF `.init_array` relocations and executed:

| Local audit label | Native address | Purpose in this audit |
| --- | --- | --- |
| `local_raw_initializer` | `0x34c83f8` | Initialize fixed RAW conversion matrices and supporting data |
| `local_gradation_manager_initializer` | `0x3694960` | Initialize gradation-manager supporting storage |
| `local_gradation_initializer` | `0x36957f8` | Initialize the supporting 1D curve vector |

These labels are names assigned by the audit to original unnamed functions. Their code hashes and ELF initialization-array slots are recorded in the receipt.

The independent oracle uses vectorized formulas, separately solves the natural cubic spline system, and reads the necessary private constants/control points from the APK. It compares all entries of five generated tables:

| Film code | Companding code | Compared entries | Result |
| ---: | ---: | ---: | --- |
| 0 | 1 | 65,536 | All exact |
| 1 | 1 | 65,536 | All exact |
| 1 | 2 | 65,536 | All exact |
| 7 | 1 | 65,536 | All exact |
| 7 | 2 | 65,536 | All exact |

All **327,680 entries** match, and all five tables are finite, monotonic and within the 16-bit output range. The native selection for film code 0 with companding code 2 uses the same generated table as film code 1 with companding code 2; that selection is exercised in the integrated tests.

`GetGradationCurveUpdate` and `ReturnGradationCurve` then choose and copy the appropriate table into `SetupCC` without an identity-curve replacement. The ordinary path is exercised; the HDR branch is not run. Although the ordinary wrapper passes a scalar to `ReturnGradationCurve`, its exercised non-HDR branch selects/copies its table without using that scalar as a curve gain. This does not establish where all exposure scaling occurs in the complete pipeline.

The original Phocus spline and curve-generation instructions execute, but Android's separate math library does not. Imported `pow` calls use host `math.pow`; `powf` uses float inputs and float-rounded host `math.pow`. Their finite-table agreement with the independent oracle is verified here. Bit-exact agreement with every Android libm implementation is not claimed.

## Reconstruction preserves luminance directly

The decisive correction to the earlier simplified model concerns the output matrix. After input transformation, LUT lookup and chroma weighting, this particular CPU routine computes each channel as:

```text
output_i = gradation[clamp_and_truncate(Y + K[i,1] · Cb' + K[i,2] · Cr')]
```

It does **not** multiply `Y` by `K[i,0]`. The routine loads matrix elements 1, 4 and 7 for one chroma column and 2, 5 and 8 for the other, then adds `Y` directly. This is an observed property of `ColorNormalCorrectPixels`, not a general rule for all Phocus processing functions.

Stage 41V/X used a synthetic reconstruction matrix whose first column was exactly unity, so their tests could not distinguish this operation from a complete matrix multiplication. Those test results remain valid for their fixtures. Stage 41Y supersedes the general interpretation: using a complete matrix multiplication in the first integrated case produced 549 differing channels out of 852, with maximum difference 186. Using the directly observed luminance-preserving reconstruction made that case, and then the entire suite, exact.

This is a concrete implementation requirement for a future port: retain this operation's neutral-axis behaviour instead of replacing it with an apparently equivalent generic matrix multiply.

## Native shadow and neutral settings

The audit no longer inserts Stage 41X's synthetic shadow coefficients. Original `InitCRawColorCorrection` computes them, and the independent oracle verifies the generated coefficients before pixel execution. For the two tested colour-model branches and filter 6, both neutral thresholds are zero. The ordinary code-0 branch generates a scalar-dependent shadow curve; the tested code-1 branch produces unity shadow weighting. These observations are conditional on the selected sensor/filter/model and supplied scalar values.

The pixel suite includes very low unequal RGB triplets, neutral levels around the shadow region, saturated endpoints and seeded random values. The actual original gray/shadow-weight helper runs for these inputs.

## Integrated validation

The suite combines three temperature/requested-film pairs (2,400 K/code 0, 4,000 K/code 1 and 9,100 K/code 7), two gain configurations, two colour-model codes and six working-space codes. That gives **72 configurations**, each processing the same 284 synthetic RGB16 triplets.

| Check | Result |
| --- | --- |
| Input-matrix composition | Maximum absolute scalar difference `6.66e-16` |
| Reconstruction-matrix composition | Maximum absolute scalar difference `5.55e-16` |
| Five generated curve tables | 327,680 of 327,680 entries exact |
| Curve selected into each correction object | Exact in all 72 cases |
| Native pixel output | 61,344 of 61,344 channels exact across 20,448 evaluations |
| Profile/input immutability and object/allocation/output guards | Pass |

Forty-nine original native functions execute, including the three initialization functions. The receipt records names/labels, addresses, sizes and hashes. Native matrix, spline, profile interpolation, lookup, shadow and pixel functions are not replaced by the independent oracle.

Execution is guarded at basic-block boundaries against an explicit function allowlist and a per-call instruction budget. The host allocator verifies guards before freeing/reusing buffers, which is necessary because curve generation repeatedly constructs splines. Single-thread mutex operations and process-exit destructor registration are host fixtures. The full Android app is not started.

Absolute tolerances of `1e-12` for double calculations and one code for curve/pixel comparisons were fixed before the integrated run. No curve or pixel comparison required the one-code tolerance. This finite coverage does not prove bit-exact equivalence for all possible inputs.

## Reproduction

Use Python 3.12 with assertions enabled and retain the sibling Stage 41W/X audit directories. The dependencies are present at research commit `e83eba0d1eaa44b780814b3d2b41d1db4185ea15`.

```bash
python -m pip install -r hasselblad_native_audit/phocus_stage41y/requirements41y.txt
python hasselblad_native_audit/phocus_stage41y/inspect_phocus_pipeline41y.py \
  --apk /absolute/path/to/the/supplied.apk \
  --receipt /absolute/path/to/STAGE41Y_PHOCUS_PIPELINE_SAFE.json
```

The public additions contain only the audit source, dependency pins, aggregate receipt and this report. Vendor binaries, calibration arrays, generated curve arrays, shader source, disassembly, cryptographic material and photographs remain excluded.

## Next target

Trace and execute `CalculateLinearization` and the gain-to-temperature/tint path used by the parent filter. Establish how black level, white level, capture gains, exposure and demosaiced RGB are prepared for the now-verified colour fragment. Numeric working-space and colour-model codes also need to be bound to the actual application/capture settings.

Then process an existing X2D II RAW through the verified preparation path and compare a complete render against a controlled Phocus export. Phone adaptation still requires a justified phone-sensor-to-working-space conversion. No production renderer or APK build changed in this stage.
