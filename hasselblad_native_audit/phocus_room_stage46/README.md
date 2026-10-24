# Stage46 — actual tungsten-room DNG

Date: 2026-10-24. The owner supplied the original room DNG after the Stage45
temperature-only trial. This stage renders that file with the three delivered
profiles and locates clipping at successive stages. The source DNG is unchanged.
No APK, production renderer, capture exposure, white balance or default profile
is changed.

## Reproduction checks

The 4096×3072 RGGB DNG produces a 1024×768 development preview (orientation 6,
four GainMaps). Independent NumPy/OpenCV full-frame preparation matches the
existing Stage43 Java streaming preparation exactly: all 2,359,296 RGB16 input
channels. Both find 1,075 below-zero channels and zero above-unity channels at
the preview input, reproducing the owner's Stage43 report counters.

For curve1/4000 K, curve0/4000 K and curve0/3050 K, the portable C output matches
the host Java/JNI output exactly in RGB16 and displayed RGB8. Two vectorized
traces also agree with the C results, including a fourth exposure-adjusted
comparison. The baseline display is exact between the independent path and the
host Java code. This is a host check, not a new phone-device RGB hash receipt.

The supplied DNG is visually the scene in the screenshots. Screenshot resizing
prevents treating screenshot pixels as a bit-exact device output; no such claim
is made. The original Phocus APK is no longer in this runtime's local files.
This stage uses the previously validated private profiles and portable colour
core; it does not claim another original-ARM64 replay on these new pixels.

## LUT temperature is a small change in this scene

All numbers below are mean absolute displayed-channel differences on a 0–255
scale, with the stated other stages fixed:

| Comparison | Mean change | 95th percentile | Pixels changing >2 in any channel |
| --- | ---: | ---: | ---: |
| Curve0: LUT 4000 K → 3050 K | 0.1724 | 1 | 1.0017% |
| Curve0: real 4000 K LUT versus identity LUT | 1.1071 | 4 | 21.8077% |
| Curve0 versus curve1, both 4000 K and unchanged exposure | 25.2918 | 37 | 99.9324% |

These are controlled nonlinear comparisons, not additive fractions of a look.
The LUT is active: on the selected wood patch, the real LUT versus identity
changes channels by 4.345 levels on average. Changing only its temperature
changes that patch by 0.155 levels; the selected skin and blue-wall patches
change by 0.127 and 0.145 respectively. The largest individual temperature-only
channel change is 66, so a small mean must not be read as a per-pixel bound.
No patch is assumed to be a measured colour or neutral target.

## The television clips before and during rendering

Statistics refer to the explicitly drawn TV-interior polygon, excluding most of
the bezel. RAW percentages count CFA sensor samples, not RGB pixels:

- 31.65% of the 255,961 selected RAW CFA samples are already at the DNG white
  limit. By CFA colour: R 3.47%, G1 44.37%, G2 44.23%, B 34.46%.
- GainMap multiplication pushes another 9.64% of the region's CFA samples above
  unity before the existing upper clamp. This is before demosaic and WB.
- Consequently, the old `input_over_unity_channels_clipped: 0` receipt never
  meant the sensor or GainMap path contained no clipped highlights. That counter
  observes the later demosaiced preview input after the GainMap upper clamp.

The upper clip is not an arbitrary LUT adjustment: Adobe's DNG 1.7.1.0
specification, *Opcode List Processing*, printed page 105, specifies the logical
range after each OpcodeList2 operation as 0–1. This audit does not claim SDK
parity; the existing diagnostic path retains negative values until RGB16 input.
[Adobe specification](https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf#page=105).

The next table counts preview RGB pixels in the TV polygon. "Any clipping"
means at least one channel exceeds the stage's upper limit. "Near white" means
all displayed RGB channels are at least 250; it is a diagnostic threshold.

| Render | Any pre-curve internal clipping | Any linear-sRGB output clipping | Displayed near-white pixels |
| --- | ---: | ---: | ---: |
| Neutral baseline | n/a | 83.92% | 0.05% |
| Curve1 / 4000 K | 81.76% | 85.48% | 7.56% |
| Curve0 / 4000 K | 81.76% | 86.79% | 38.31% |
| Curve0 / 3050 K | 81.70% | 86.77% | 38.78% |
| Curve0 / 4000 K, brightness comparison −0.778 EV | 63.40% | 77.89% | 0.00% |

The stages have different domains; their percentages are not additive.
The RAW already contains lost channel information, while the later curve and
display conversion cause additional whitening. Lowering render exposure can
preserve more of the still-available variation but cannot reconstruct the
original values of saturated RAW samples. The blinds, skin, wood and wall
reporting patches have no measured upper clipping in these renders.

## Separate brightness from colour

One global exposure scalar applied before the colour/film transform matches
curve0 to curve1's midtone brightness at −0.77826 EV. It is fitted on alternating
32×32 calibration tiles, excluding near-black or near-clipped baseline samples.
Other tiles remain disjoint for reporting. Median absolute log-luminance error
is 0.05055 stops on calibration samples and 0.05128 on the held tiles. The two
curves still differ in shape; no single exposure can make every tonal region
equal. The blinds, for example, remain about 10 displayed levels apart.

At this matched brightness, mean absolute RGB differences from curve1 are
1.408 levels on the selected skin patch, 1.334 on the blue wall, and 2.741 on
wood. This supports a substantial brightness contribution to the apparent
change. It does not establish Hasselblad colour accuracy. The exposure fit is
scene-specific, used only for this comparison, and is not an automatic exposure
rule or a new recommended default. No hue, saturation, tint or WB fit is used.

The next engineering target should be exposure normalization and explicit
highlight handling, with fixed WB and LUT controls for comparison. Retain the
4000 K trial as the current selection unless further evidence favours a change;
the 3050 K alternative provides no substantial general colour change here.
Full fidelity still requires a known-settings Hasselblad/Phocus reference,
and the phone sensor adaptation remains experimental.

## Artifacts and privacy

`Stage46PrivateDump.java` reuses the existing host Stage43 classes and JNI
library to write private intermediate bytes and PNGs. `analyse_room46.py`
independently prepares the DNG, verifies all supplied profile outputs, computes
stage/region statistics, and builds tagged-sRGB comparison panels.

The original DNG, profile payloads, matrices, per-pixel buffers, private input
ledger, private full analysis, region mean RGB values and photographs remain
outside public git. Public evidence contains aggregate differences and clipping
counts only. The original uploaded file is neither modified nor replaced.

Dependencies are the existing Stage42/44 Python packages and Java 17 host setup.
No original APK is required for this stage. Pass the DNG, private dump directory,
three `.hbc` paths and output paths explicitly; both tools refuse unanticipated
scene dimensions/orientation. Assertions must stay enabled.
