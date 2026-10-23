# Stage45 — tungsten selection and Android parameter preparation

The owner confirmed tungsten illumination in the room shown by the Stage43
screenshots. Warm wood, skin and textiles are therefore not evidence by themselves
of an incorrect colour transform. The goal remains a specified SDR
Hasselblad/Phocus colour-and-tone reference, with comparable exposure and white
balance. Immediate brand recognition is not a numerical acceptance criterion.

No production capture or Android source changes are made here. The new private
profile works in the existing Stage43 development viewer.

## Original Android preparation now executes

`audit_parameters45.py` extends the guarded Stage41Z ARM64 harness and executes
the complete original `CColorCorrectAllFilter::UpdateParameters` body. It also
executes `CFilmCurveFilter::UpdateParameters` and `CreateLinearCurve` for the
bounded SDR branch. Twenty-four cases cover six temperatures (2400, 2850, 3050,
3200, 4000, 5550 K), film codes 0/1, opposite tint fixtures and scalar gains 1/1.7.

Each colour object is prepared with the original RAW initializer before the
recording factory returns it. Original temperature conversion, matrix/LUT
construction, float conversion, vector writes and film-table preparation execute.
The factory records and checks its arguments; it does not execute the real
allocation/lifecycle. Lens gain reduction is an explicitly supplied scalar and
the destructor is an ownership fixture. These limitations are retained in the
receipt. The library/profile come only from the owner's hash-pinned private APK.

All 24 cases pass:

- The current correction temperature reaches the factory and the corresponding
  profile matrix and LUT. There is no universal fixed 4000 K selection here.
- The emitted first matrix, output matrix, LUT and WB vector agree exactly after
  float32 conversion. The LUT has 105 × 89 texels, with two chroma components
  and two zero components per texel.
- The prepared WB vector is normalized by its largest component. The separate
  scalar incorporates that largest component and the tested source/exposure
  factors. This is parameter evidence, not proof of the consumer's pixel order.
- The separate SDR film filter prepares the selected recovered curve divided
  by 65535, exactly: 1,572,864 checked float entries across the cases. This
  establishes the Android film-table preparation bridge, not final GPU sampling
  or full-render equivalence.
- Sources/profile remain unchanged and all object/allocation guards pass.

Another 48 calls execute `EffectiveFilmCurve`: disabled correction uses the
source film; requested code 4 inherits the source film; enabled model codes 1
and 4 choose film code 7. Other tested requests pass their film code through.
These are numeric routing rules. They do not identify live defaults, establish
UI labels or prove which curve the supplied camera references used.

The live GPU path, lens gain reduction, sensor RAW preparation, complete object
lifecycle and phone temperature calibration are still not validated. Static
inspection also shows that the combined shader's active main body does not use
its declared `uGain` uniform. Do not infer a second WB multiplication from the
existence of the prepared gain vector; its full upstream ownership still needs
tracing. The phone preview retains DNG-owned WB exactly once.

## Curve0 LUT-only sensitivity

`check_tungsten45.py` uses the earlier Stage42 cat DNG, not the newer tungsten-room
RAW. It holds DNG WB, exposure, input/display transforms, shadow processing and
film curve0 fixed, changing only the recovered LUT temperature.

| LUT selection | Mean absolute displayed channel change versus 4000 K | Pixels changing >2 in any channel |
| --- | ---: | ---: |
| 2400 K | 0.1934 | 0.1410% |
| 2850 K | 0.1388 | 0.0627% |
| 3050 K | 0.1146 | 0.0398% |
| 3200 K | 0.0966 | 0.0253% |
| 5550 K | 0.1870 | 0.1247% |

Values are on the displayed 0–255 scale. The 95th percentile is one level for
all alternatives. The maximum at 3050 K is 20 levels, so a small mean does not
mean every pixel is unchanged. The 32 common-D50 neutral controls have identical
displayed RGB for all six selections. They test this fixed transform and are
not measured neutral objects from the room.

All six full-preview vectorized traces match the unchanged C renderer exactly
(14,155,776 channels). Original ARM64 pixel execution matches 512 photographic
samples per temperature (9,216 channels). The original source inputs are unchanged.

This supports only a limited conclusion: LUT temperature alone has a subtle
effect on this available phone image. It neither validates the phone adaptation
nor establishes the actual room illuminant. No calibration matrix is fitted or
transferred from a Hasselblad sensor to the phone.

## Private 3050 K trial

`Stage45_Private_Curve0_3050K.hbc` changes only the temperature field, chroma LUT
and checksum relative to the Stage44 curve0/4000 K profile. The selected 3050 K
is the recovered tungsten LUT anchor, not a measured colour temperature of the
owner's light. Profile size is 412032 bytes; SHA256:

`f8f36fc274328d2a3410eb97c0475cff774e5aff230914872dd0df0eab6b9820`

The existing Stage43 host DNG/Java/JNI test passes with the new profile on the
earlier DNG: all 2,359,296 prepared input channels, output RGB16, display RGB8 and
baseline RGB8 match the reference. This is not a phone-device result.

Import this profile in Stage43 and reopen the same DNG. The report should show
`film_code: 0` and `lut_temperature_manual: 3050`. Importing the Stage44 profile
restores 4000 K. No new APK is needed. This is a reversible diagnostic, not a new
default or a claim of a stronger/more accurate Hasselblad look.

The original tungsten-room DNG is the next useful input for scene-specific work.
It allows fixed-WB/fixed-exposure comparisons and separate input, internal and
display clipping measurements. The existing screenshots cannot locate the TV
highlight clipping in the RAW pipeline. A genuine known-settings Phocus render
is still needed for complete renderer fidelity; the four earlier camera
preview/JPEG pairs are not verified Phocus exports.

## Reproduction and privacy

Use the existing Stage41W–Z/Stage42/Stage44 dependencies, with assertions enabled.
Supply private paths to each script's `--help` options. Run the new profile and
generated private `.hb42` through the existing `Stage43PrivateCheck` Java class.
The original APK, photos, profile arrays, generated `.hbc`/`.hb42`, binaries,
panels and disassembly stay private. Public git contains only independently
written source, this report and aggregate receipts under `evidence/stage45`.
