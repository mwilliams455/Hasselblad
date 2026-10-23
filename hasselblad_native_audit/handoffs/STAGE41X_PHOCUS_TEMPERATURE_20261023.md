# Stage 41X: native temperature interpolation and real-profile LUT pixel replay

The original Phocus ARM64 code now executes the selected X2D II profile's temperature interpolation, LUT expansion, correction-object setup and CPU pixel correction. The independent calculation matches all 19,728 output channels in 6,576 synthetic pixel evaluations across 24 configurations. This advances Stage 41V's synthetic LUT tests to the actual profile identified and loaded in Stage 41W.

The result is a verified processing fragment. Pixel tests still supply a synthetic RGB-to-chroma basis, its inverse, identity gradation and explicit neutral/shadow thresholds. The real profile matrix is calculated and stored by native setup, but its composition into the complete RAW pixel transform remains unverified. No full photograph or camera MAIN ISP has been reproduced.

## Inputs and scope

The audit uses the same privately supplied Phocus Android 1.1.0 APK as Stages 41V/W. It verifies the following identities before execution:

| Input | SHA-256 |
| --- | --- |
| Supplied APK | `5ee52bbb2b7a3fa708628ba251b409a551ae099697668427cf54b523328ccf68` |
| ARM64 `libcrosssdk.so` | `d757237554529f8ab485f88f2c5e5399fbc8d56035c79b8e057b41a40fd055e4` |
| Decoded selected profile | `c2b3d08e0d489eb852610c12a9b985e9d0340a4dd544f5b0b5b7a6a4f3427e95` |

The profile is `bohnjuhtuvuvtxyydb56.dat`, version `3.0`, normal CPID `0x0616`. Stage 41W verified the native selector against the sensor/filter metadata from four X2D II RAWs, with the application boolean `ClosedLoop` set to false. The live Android application's setting remains unobserved; this stage does not resolve the alternate closed-loop path. APK authenticity against a manufacturer distribution also remains unverified.

The audit imports Stage 41W's ELF utilities, guarded emulator and private-input decoder. It decrypts only the selected asset in memory, executes the original `DecodeFrom`/`InitializeLUTs`, then runs the new calculations. The original full profile constructor is not executed: its profile flag at object offset `+9` is supplied as `1`, following the previously inspected constructor branch for CPID `0x0616`.

## Temperature operations

Both calculations clamp the requested integer temperature to **2,000–10,000 K**. Interpolation is linear in **Kelvin**, rather than reciprocal temperature. Values outside the outer calibration anchors are extrapolated up to those clamp limits.

| Operation | Below 3,050 K | 3,050–5,550 K | Above 5,550 K |
| --- | --- | --- | --- |
| Matrix | 2,400 K `mlt` to 3,050 K `mt` | 3,050 K `mt` to 5,550 K `mf` | 5,550 K `mf` to 9,100 K `mh` |
| Chroma LUT | 3,050 K tungsten to 5,550 K flash, extrapolated below 3,050 K | Same tungsten/flash pair | 5,550 K flash to 9,100 K high-temperature |

There is no separate low-tungsten chroma LUT in this calculation. Standard and reproduction modes choose their respective three table arrays and use the same temperature rules. The additional loaded matrix `mfd` is not used by the exercised version-3 `CalculateMatrix` path; its role elsewhere is unresolved.

The independent oracle uses `low + (high - low) * fraction`. The native code uses slope/intercept expressions with fused arithmetic, so tiny floating-point differences are expected before integer conversion. A fixed absolute tolerance of `1e-12` was set before the audit; the measured differences are substantially smaller.

All 22 requested temperatures were tested for matrices, and both standard/reproduction modes were tested for LUTs. Cases include negative input, both clamp limits and their neighbours, each calibration anchor and its neighbours, and intermediate values. The two boolean service queries `CPInterpolateLUT` and `CPNoInterpolateLUT` were also tested with both false together and both true together, at 4,000 K and 7,000 K in each mode. These paired configurations produce exactly identical LUTs for this version-3 profile. The test does not establish live app defaults or test every independent combination of the booleans.

## LUT coordinates and expanded borders

Original `Scaled2DLUT::FromCbCrData` creates a **105 × 89 × 2** double table. The two channels represent transformed chroma coordinates, not RGB output samples. For the exercised normal lookup path, the table coordinates are formed from chroma-to-luminance ratios:

```text
x = 32 * (Cb / Y) + 20
y = 32 * (Cr / Y) + 32
```

Lookup clamps to the grid, interpolates bilinearly and divides the two returned values by 32. The division and coordinate scaling are executed by the original lookup helpers in the pixel tests.

`CalculateExpandedLUT` adds 5 columns before and 55 after, and 7 rows before and 12 after. The resulting **165 × 108** grid has bias `(25, 39)`, retaining scale and output divisor 32. Original values occupy columns 5–109 and rows 7–95.

Outside that rectangle, the native code continues the nearest boundary value with unit slope in the outward chroma coordinate. An independent equivalent is to select the nearest original grid point, add the horizontal distance to its first component and the vertical distance to its second component. This also describes the corners. Fourteen cases check every expanded component, including the complete border and interior.

## Setup and pixel execution

The original `CColorCorrection::SetupCC` receives the real loaded profile and the selected temperature/mode. It calculates the profile matrix at object offset `+0xf0`, creates the ordinary or expanded LUT at `+0x138`, copies the supplied RGB-basis matrices to `+0x8` and `+0x50`, and copies the supplied gradation array to the owned vector at `+0x188`. The audit verifies these fields before calling the original `ColorNormalCorrectPixels`.

The distinction between the profile matrix at `+0xf0` and the supplied pixel-basis matrices matters: this test does not establish the upstream composition that turns Hasselblad RAW sensor values into the pixel routine's input space. A successful native `SetupCC` call alone does not establish that missing transformation.

Pixel coverage combines three temperatures (3,050, 5,550 and 9,100 K), standard/reproduction mode, ordinary/expanded grid, and neutral/shadow protection off/on: **24 configurations**. Each processes the same 274 triplets: black, white, saturated RGB/CMY endpoints, ten neutral levels and 256 seeded random RGB16 values. Fixtures are explicit:

- The RGB basis and inverse are synthetic, independently invertible matrices retained from the earlier operator audit.
- The gradation table is identity; the actual Phocus film curve is not substituted or claimed.
- Neutral and shadow thresholds are test values, not observed application defaults.
- The correction object starts zeroed and is populated by original `SetupCC`; its complete native constructor and the parent `CRawColorCorrection` constructor are not executed.
- Boolean application queries return false during setup, allowing the explicit expansion argument to control the tested branch.

The native pixel routine and all invoked matrix multiplication, LUT lookup and neutral/shadow weight helpers execute their original ARM64 instructions. No arithmetic or lookup function is replaced by an oracle. The independent pixel oracle consumes the separately calculated real-profile LUT and synthetic test inputs.

## Verification results

| Check | Coverage | Result |
| --- | ---: | --- |
| Matrix interpolation | 22 cases, 198 scalar comparisons | Maximum absolute difference `2.22e-16` |
| Standard/reproduction LUT interpolation | 44 cases, 822,360 scalar comparisons | Maximum absolute difference `1.42e-14` |
| Expanded grid including borders | 14 cases, 498,960 scalar comparisons | Maximum absolute difference `2.84e-14` |
| Paired boolean configuration equivalence | 4 temperature/mode comparisons | Exact |
| Native setup followed by native pixels | 24 cases, 6,576 pixel evaluations, 19,728 channels | All channels exact |
| Guard and immutability checks | Profile object, correction object, allocations, output bounds, pixel inputs | Pass |

A one-code pixel tolerance was fixed before testing; no tested output needed that tolerance. These finite tests are not a guarantee of bit-exact agreement for all inputs or complete photographs.

Twenty-one original native functions execute. The receipt records their symbol names, addresses, lengths and hashes. ELF data/vtable relocations are resolved without loading the library into the host process. Only approved function bodies may execute; unexpected calls and instruction-budget exhaustion fail the audit. Host fixtures provide allocation/free, memory copies/clears, XML key getters and boolean configuration. Freed buffers are retained until each case is checked, then discarded. Object/allocation sentinels and unchanged-profile checks pass.

## Reproduction and saved files

Use Python 3.12 with assertions enabled. Keep the Stage 41W audit at its sibling repository path; this stage imports it. The dependency was introduced by commit `a8cc27269a2a837b54f4b6d4a022d1ad89a17c68`.

```bash
python -m pip install -r hasselblad_native_audit/phocus_stage41x/requirements41x.txt
python hasselblad_native_audit/phocus_stage41x/inspect_phocus_temperature41x.py \
  --apk /absolute/path/to/the/supplied.apk \
  --receipt /absolute/path/to/STAGE41X_PHOCUS_TEMPERATURE_SAFE.json
```

The repository additions contain the audit script, dependency pins, aggregate JSON receipt and this report. No vendor payloads, calibration arrays, shaders, disassembly, crypto tables/keys or photos are included. The script requires the private APK to reproduce the calculations.

## Remaining implementation work

The next target is `CRawColorParams::GetRawRGB2XYZMatrix` and the matrix composition in `CRawColorCorrection::InitCRawColorCorrection`, followed by the ordinary `CGradationManager` film-curve path. Those should establish the input colour space, white-balance/exposure scaling, output working space and actual gradation supplied to `SetupCC`. The parent object's neutral/shadow defaults also need verification.

After those pieces are executable, use an existing X2D II RAW and a controlled Phocus export to validate the complete image path. The absence of a camera no longer blocks profile interpolation or this native CPU fragment, but equivalence to the camera's MAIN ISP remains unproven. Adapting the result to Photon still requires a justified phone-sensor transform; direct reuse of Hasselblad sensor matrices is not a verified solution. Production rendering code and APK builds remain unchanged in Stage 41X.
