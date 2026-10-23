# Stage 41Z: white-balance inputs, optional linearization and Android caller mapping

Date: 2026-10-23, Europe/London. Research branch only.

The recovered colour stage is close enough to begin an experimental Android renderer port. This stage verifies its white-balance conversion, optional linearization arithmetic and part of the Android parameter preparation. It does not produce an APK or a complete photographic render.

The practical correction is that `CalculateLinearization` is not the RAW decoder. It rescales pre-existing channel calibration tables. Its application is skipped when the parent RAW colour object has no closed-loop calibration object. It should not be treated as a universal blocker to processing saved RAW pixels.

## Executed evidence

The audit executes 26 original ARM64 functions from the same privately supplied, hash-pinned Phocus Android APK used in Stages 41V–Y. Original white-balance matrix construction, temperature/tint conversion, scalar preparation and table arithmetic execute. The independent NumPy calculations are comparators, not replacements for those functions.

| Check | Coverage | Result |
| --- | ---: | --- |
| White-balance converter construction | Both `CCNC` settings | Forward and inverse matrices agree within `1e-12` |
| Temperature/tint → gains | 60 cases | Maximum absolute difference `2.76e-12`, within `1e-10` |
| Gains → temperature/tint | 68 primary cases and 68 common-scale repeats | Integer temperatures exact; tint agrees within `1e-12` against the bounded comparator |
| Existing X2D II RAW metadata | Four files × two `CCNC` settings | Eight conversion cases pass; source files unchanged |
| Full channel linearization tables | Three tables × four gains × 65,536 entries | **786,432 of 786,432 entries exact** |
| Linearization application | 512 RGB triplets × four gains × two calibration-pointer states | **12,288 of 12,288 channels exact** |
| Android source-gain/scalar helpers | Six configurations, three source branches | Independent calculations agree within `1e-10` |
| Android SDR creation argument routing | Eight configurations | Factory arguments and subsequent linearization scalar exact |
| Android direct call edges | Five sites | Branch destination and PLT symbol verified |
| Input/profile immutability and memory guards | All executed cases | Pass |

The four RAWs contribute TIFF `AsShotNeutral` metadata, converted to reciprocal gain triplets. This tests real metadata values through the native converter. It does **not** prove that those values exactly equal the live app's prepared filter arguments, and it does not process their image pixels. Capture identifiers, gain values and calculated capture temperatures/tints are absent from the public receipt.

## White-balance conversion uses a distinct calibration basis

For sensor 22 and filter 6, the converter constructor obtains the neutralized matrix from the already-loaded CPID `0x0616` profile. With the debug-manager boolean `CCNC=false`, its forward matrix is:

```text
M = decoded_mf × diagonal(decoded_vf)
```

The constructor obtains this through original matrix inversions. Its stored forward matrix agrees with the independent expression, and its stored inverse agrees with `inverse(M)`. With `CCNC=true`, the tested path uses identity matrices. The live app's debug setting is not observed; both branches are deliberately covered. The acronym is not expanded or assigned an unverified UI meaning.

`GainToTempAndTint` divides the minimum supplied gain by each channel's gain, applies the forward matrix, converts the resulting chromaticity to an `u,v` representation, and searches a private temperature-locus table. `TempAndTintToGain` interpolates that table, applies tint, transforms through the inverse matrix and normalizes the resulting gains. The audit reads the table privately from the APK; it does not publish it.

The tested conversion branch uses unquantized temperature/tint. The boolean-enabled UI quantization branch is not executed. No host math-library substitutes are needed for the white-balance arithmetic in this stage; its division, square-root and multiply/add operations execute as ARM64 instructions.

### Preserve the observed tint interpolation detail

In the gain-to-temperature routine, the weights used for the interpolated direction vector are reversed relative to the weights used for the interpolated locus point. Replacing this with conventional interpolation failed the comparison. The independent comparator now preserves the observed operation.

This also creates a small tint discontinuity at certain temperature-locus segment boundaries. Scaling a gain triplet by a common factor can change the selected adjacent segment through floating-point rounding. Three of the 68 common-scale checks changed tint by more than `1e-12`; the maximum change was `2.7951e-5` in the routine's internal tint units. All integer temperatures remained unchanged.

The audit therefore does not claim exact scale invariance or exact round trips. For inputs within `2e-14` of an isotherm, its comparator admits the two adjacent segment results; elsewhere it admits only the selected result. Thirty-six primary cases, deliberately including temperature-locus anchors, meet this boundary condition. Against the admissible comparator, the maximum primary tint difference is `1.09e-16`. This boundary treatment and its threshold are explicit in the source and receipt.

## Linearization is optional channel-table processing

The parent `CRawColorCorrection::CalculateLinearization(double)` delegates to the correction object. The scalar-only routine first requires all three source tables to contain exactly 65,536 unsigned 16-bit entries. With missing tables it returns without modifying the correction object; this no-op path is executed and verified.

For positive scalar gain `g`, source channel table `L_c` and input index `i`, the tested operation is:

```text
j = truncate(min(i / g, 65535))
L'_c[i] = truncate(min(L_c[j] × g, 65535))
```

Three intentionally distinct, independently generated fixtures test identity, nonlinear and clipped behaviour. Gains `0.5`, `1`, `1.7` and `4` exercise both ends of the index/output clamps. The output vectors have reserved capacity, so this run verifies arithmetic and writes without exercising vector-capacity growth. All source tables remain unchanged.

`CRawColorCorrection::ApplyLinearization` returns immediately when the parent calibration pointer is null. For a non-null pointer, `CLNoLinearization=false`, and no per-pixel gain map, it applies the three prepared tables to RGB16 samples in place. Both pointer states are executed. The non-null pointer is a gate fixture; this path does not dereference a manufacturer's calibration object. The per-pixel float-gain-map branch and the overload accepting an additional channel-gain vector remain unexecuted.

This evidence concerns closed-loop channel correction. Black-level subtraction, sensor unpacking, demosaic and other RAW preparation are separate operations.

## Android parameter preparation now has a concrete entry point

The inspected Android path calls `CColorCorrectAllFilter::UpdateParameters`, which calls `ColorCorrectionAllFilter::CreateColorCorrection`. This is a more relevant Android integration lead than relying only on the older `CColorCorrectFilter` constructor inspected previously.

The audit verifies these original direct-call relationships:

| Call site | Target |
| --- | --- |
| `0x34bb618` | `CColorCorrectAllFilter::UpdateParameters` |
| `0x34c0dbc` | `ColorCorrectionAllFilter::CreateColorCorrection` |
| `0x34c0e8c` | `CColorTempConversion::TempAndTintToGain` |
| `0x3279f94` | `CRawColorCorrection::NewRawColorCorrection` |
| `0x3279fb4` | `CRawColorCorrection::CalculateLinearization` |

The original source-gain helper and scalar helper execute with controlled descriptions/settings. They cover current temperature/tint, alternate temperature/tint, and capture-gain fallback when the selected temperature is zero. They agree with independent calculations.

The original `CreateColorCorrection` also executes. Its factory call is intercepted to record arguments and return the harness's existing RAW object; the factory and full RAW/correction constructors are **not** executed in this stage. The subsequent original linearization call executes its empty-table path. These tests establish caller routing, not a complete object lifecycle or rendered result.

For the tested SDR configurations:

- The selected correction temperature is passed as the factory's first double argument.
- The factory's next two scalar double arguments are both `1` and its HDR-related boolean is false.
- A separate enabled gain setting supplies `CalculateLinearization`; otherwise that scalar is `1`.
- Enabled settings select the requested model and working-space codes. Model code 1 selects film code 7. Disabled settings select model/space code 0 and the source film code.
- The calibration pointer is null in these cases.

Static inspection of `UpdateParameters` separately shows temperature/tint-derived gains being prepared into a gain vector, alongside the correction object's matrices and LUT. The corresponding complete update/GPU function is not executed here. Consequently, copying those white-balance gains into Stage 41Y's parent-object matrix-gain fixture without tracing their consumer would risk applying gain twice.

Stage 41Y remains valid for its explicit matrix-gain and scalar fixtures. Its older-constructor scalar linkage should not be generalized to this combined Android path: the tested ordinary creation call supplies unity scalars and handles other gain preparation separately.

## What this means for the next APK

An experimental colour-preview APK is a reasonable next implementation target. It can build on the original-profile selection, matrix/LUT interpolation, gradation and CPU pixel evidence already established in Stages 41W–Y, plus the input-preparation evidence here. An X2D II purchase or MAIN firmware decryption is not required to start that port.

The immediate implementation work is to port the verified colour fragment behind an explicit development path, define its normalized RGB input and separate white-balance/exposure inputs, and compare one saved RAW render before connecting the phone capture path. Phone sensor data still needs the phone's own calibration into the appropriate colour domain; X2D II sensor coefficients must not be applied directly to phone samples as though the sensors were interchangeable.

The target should be a single-frame SDR colour preview with a comparison path. A complete render and phone-domain validation are still outstanding. The existing Photon production renderer is unchanged, and no new APK is claimed by this checkpoint. A CPU-fragment replay does not establish complete Android GPU equivalence or camera MAIN ISP equivalence.

## Reproduction and retained material

Run with Python 3.12 and assertions enabled. Retain the sibling Stage 41W, 41X and 41Y audit directories from research commit `482bb958a307567ab4540434434d6e302f90823f`.

```bash
python -m pip install -r hasselblad_native_audit/phocus_stage41z/requirements41z.txt
python hasselblad_native_audit/phocus_stage41z/inspect_phocus_input41z.py \
  --apk /absolute/path/to/the/supplied.apk \
  --raw /absolute/path/to/first.3fr \
  --raw /absolute/path/to/second.3fr \
  --raw /absolute/path/to/third.3fr \
  --raw /absolute/path/to/fourth.3fr \
  --receipt /absolute/path/to/STAGE41Z_PHOCUS_INPUT_SAFE.json
```

The `--raw` inputs are optional; omitting them skips only capture-metadata cases. The final script is checked in the repository's sibling-directory layout. APK/library/profile hashes are verified against the Stage 41W–Y pins. Every supplied RAW and the APK are rechecked for immutability.

Only the independently written audit, dependency pins, aggregate receipt and this report are retained in the research repository. Vendor binaries, decoded profiles, calibration/curve arrays, temperature tables, disassembly, shaders, cryptographic material and photographs remain private. The harness retains the original allowlist, bounded execution and guarded allocation model; only an explicit list of additional functions is enabled.
