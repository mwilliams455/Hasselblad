# Stage73: bounded original-graph alignment and a real host/JNI tile ABI

Stage72 independently substitutes the scalar Phocus `InterpolateRGB` and
zero-strength `ColorNoise` within the original CPU graph: 32 paired cases and
187,224 exact final linear RGB16 codes. Stage73 adds **new original-CPU geometry
fixtures** and a standalone **pre-ColorNoise** portable tile interface callable
from ordinary C and real Java/JNI. The phone remains at Stage58; this directory
is not an APK and does not change normal Photon capture.

## Observed outer-graph domain

The original-CPU graph was executed with irregular synthetic RGGB outputs.
It rounded its working dimensions to a multiple of eight after adding a 32px
halo on each side. The native `InterpolateRGB` RAW input matched the caller's
explicit padded Bayer source at every overlapping site, and it retained a
stride of 1,024 uint16 elements and flags `0xffff`.

| Output (width×height) | Native work (width×height) | Test scope |
| --- | --- | --- |
| 9×11 | 80×80 | Original native graph and independent full-loop parity |
| 12×15 | 80×80 | Original native graph and independent full-loop parity |
| 18×34 | 88×104 | Original native geometry only |
| 23×31 | 88×96 | Original native graph and independent full-loop parity |
| 33×35 | 104×104 | Original native graph and independent full-loop parity |
| 24×16, 34×18 | 88×80, 104×88 | Stage72 full-loop parity |
| 32×32, 64×64 | 96×96, 128×128 | Stage72 full-loop parity |

The four new full original-versus-independent CPU comparisons contain **6,441
exact final RGB16 codes with zero differences**. The original pixel-processing
bodies were bypassed in each substituted run. Together with Stage72's separate
187,224 original-CPU codes, the bounded accumulated comparison count is
193,665 codes across 36 distinct fixture/mode pairs. The new rectangle
comparisons used highlight bypass; Stage72 retained both highlight modes.

A separate direct original-CPU **pre-ColorNoise plane** comparison checked
12×15 and 23×31 output crops, returning **3,572 exact R/G/B/mask codes**
with no differences from the independent `hb73_render_pre_noise` API. This is
not Android/JNI device parity: the original Phocus CPU and portable C both ran
locally, while JNI was exercised separately in a host JVM.

**Do not generalize this measured alignment rule to unrestricted full-frame,
other CFA phases or GPU/optimized dispatch.** The native surplus work cells
outside the caller's original padded input were *not* equal to normal
reflect-101, edge-replicated or zero-padded extensions. Their ownership and
relevance outside the cropped ROI remain unresolved. In particular this
checkpoint does not claim bit-exact complete native work-buffer equivalence.

## New C interface

`frame73.h` and `frame73.c` expose `hb73_plan` and `hb73_render_pre_noise`.
The input is *already prepared* RGGB Bayer uint16 with a caller-provided
32px halo, not a DNG importer. The C implementation allocates separate
scratch and output planes, copies the source respecting its row stride, calls
**the canonical independently reconstructed Stage61–69 scalar helper code**,
and returns interleaved R,G,B,packed-direction codes at the crop. No fitting,
private profile, interpolation shortcut, sensor matrix or vendor binary is
included. The API only permits the bounded original CPU modes and measured
shapes above, and returns detailed negative errors for bad input, unsupported
configuration, allocation failure or interpolation failure.

The extra alignment tail is intentionally diagnostic and has an explicit fill
argument; it is *not* described as recovered original firmware padding.
Across 36 synthetic fixtures, each rendered with two different tail values,
the returned cropped outputs were byte-for-byte unchanged. That supports
reliance on the 32px caller-owned halo for those fixtures; it does not prove
all Bayer edge-extension rules or arbitrary-sensor/full-frame parity.

Caller output is untouched on errors. Source/output aliasing, unsupported
CFA/flags/thresholds, incorrect capacities, nontrivial input strides and
output canaries are tested. The pre-noise result is a diagnostic intermediate,
**not yet the final 16-bit/SDR Hasselblad image**: the original graph's YCC
conversion, post-noise RGB output, colour LUT, film/gradation and display are
not reproduced by this one interface.

## Real host JVM/JNI test

`jni_bridge73.c` implements a Java `short[]` boundary. The counterpart Java
class `HasselbladPreNoise73` uses the same package as the HasselbladPhoton
Android project, but is **not added to the installed app**. A host JVM calls
the compiled JNI library; it checks exact neutral-scene RGB16 values, output
guards, source immutability, invalid CFA/size rejection, and source/output
array alias rejection. Java shorts preserve the unsigned raw 16-bit bit
patterns. This is a host JNI smoke test, not Android/NDK execution.

From the repository root, with GCC and JDK available:

```sh
hasselblad_native_audit/phocus_frame_stage73/run_host73.sh /tmp/hb73-test
```

The script compiles all actual Stage61–69 source dependencies under
AddressSanitizer and UndefinedBehaviorSanitizer and runs 36 C fixtures. It
also builds the JNI shared library and runs a standalone Java class using the
real JNI entry point. The CI workflow exercises the same public tests,
**without the proprietary Phocus APK, any DNG, photographs or calibration**.

## Remaining gates before APK

1. Test more outer-region rectangles, source offsets, CFA phases, alignment
   tails and native cropping; add only measured shapes, not inferred ones.
2. Independently reconstruct the original YCC-to-final-RGB output and any
   still-native outer-frame allocation/scheduling/crop/error behaviour.
3. Add an Android NDK integration and verify JNI buffers byte-for-byte on an
   actual phone; this host JVM test alone is not Android/device parity.
4. Resolve Stage58 float-bilinear/late-quantization versus native pre-Bayer
   uint16 quantization, DNG OpcodeList2 GainMaps, site blacks, clipping,
   AsShotNeutral/colour matrices and lens/sensor adaptation.
5. Preserve Stage58 normal capture, the original DNG, and the private profile.
   Device APK integration must first be an **explicit saved-DNG comparison**;
   12MP full-frame tiling, throughput, cancellation and preview consistency
   remain separate milestones.

Only synthetic host source and aggregate original-CPU evidence are public.
Private executable, disassembly, RAW pixels, profile/matrix data and private
input hashes must never be included in GitHub, CI, ZIP or an APK.
