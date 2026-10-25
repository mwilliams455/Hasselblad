# Stage70 — original CPU colour/noise reconciliation

**This checkpoint adds actual original ARM64 CPU execution evidence.** The
previous Stages64/65 had instruction-model and host-only checks. Stage70 uses
locally supplied original Phocus APK and Unicorn 2.1.4, Capstone 5.0.9 and
pyelftools 0.33 to compare independent C implementations with original CPU
functions. The proprietary executable, private profile and photograph data
remain **outside** the public repository and CI.

## Verified native results

- Stage64 `DirectionalColorCorrectionYCC`: **3,840 original CPU-to-C calls**,
  **15,360 output codes exact**, 256 low mask selections, strides 3/8/19,
  including noncanonical high packed-mask counts. No differences; guards and
  original profile/APK immutability checked.
- Stage65 bounded `ColorNoise`: **48 direct original CPU-to-C fixtures**,
  **525,840 complete storage elements exact** (including untouched storage),
  **482 actual original YCC helper calls**, 209 distinct low masks and flags
  `0x20`, `0x40`, `0x60`. Only zero extended strength and nonoptimized scalar
  path are supported.
- Actual Stage63 graph observer: flags `0xffff`, `optimized_view=false`,
  `positive_strength=false` on all six recorded calls (three original, three
  substituted). The fixture's native ColorNoise buffers were 128x128;
  directional-YCC entries were exercised in both groups. This is the graph
  *fixture*, not a guarantee for arbitrary device settings.

## Two actual original-CPU mismatches fixed in Stage65

1. **Horizontal luminance clamp contract**: RGB-to-YCC *conversion* writes
   columns `[8, width-8)`, but the separate 3x3 Y clamp **writes** columns
   `[0, width-16)` with row-major scan and *flat contiguous neighbour reads*.
   The prior C code incorrectly clamped the converted-column interval. This
   matters at 17x17 and on random patterns, including row-wrap neighbour
   addressing when x=0. A standalone 17x17 full-range witness asserts the
   native 16383 converted centre code remains unchanged by the clamp.
2. **YCC reference output order**: native ColorNoise passes `outY` in X7,
   then `localC1`, `localC2`, and the auxiliary plane as three stack references
   in that order. Previous C swapped `localC2` and the auxiliary reference,
   producing wrong chroma when directional masks were nonzero. Corrected
   source and a discriminating synthetic output-order regression now pass.

Both corrections were established from native failures, instruction inspection
and rerunning the full original ARM64 audit. An independent Python reference
and the standalone C regression suite also pass again. No colour/tungsten
scene parameters were fitted.

## Reproduction

Requires locally supplied private original Phocus APK and installed Python
emulator stack. The audit imports optional `rawpy` indirectly through older
image comparison modules; it does not call RawPy when running the CPU-only
synthetic paths. If RawPy is unavailable, use a local fail-closed optional
import shim; never return fabricated RAW decoding values.

Run from the repository root, with Python assertions enabled:

```sh
python3 hasselblad_native_audit/phocus_colour_stage64/audit_ycc64.py \
  --apk /private/original.apk --work /private/native64 \
  --safe-receipt /private/native64.json --sanitize
python3 hasselblad_native_audit/phocus_noise_stage65/audit_native65.py \
  --apk /private/original.apk --work /private/native65 \
  --safe-receipt /private/native65.json --sanitize
python3 hasselblad_native_audit/phocus_noise_stage65/audit_graph_flags65.py \
  --apk /private/original.apk --work /private/native-graph \
  --safe-receipt /private/native-graph.json --sanitize
```

The public Stage70 CI checks only the independent C/Python regression sources;
it has no original APK, private DNG or calibration payload and cannot establish
original CPU parity by itself. The public aggregate receipt records the
*already completed local original-CPU runs*.

## Still unresolved

The `InterpolateRGB` pixel-loop output and entire scalar demosaic have **not**
been proven equivalent by Stage70. Stage66–69 schedule/gradient work and
alignment/CFA/halo remain to be checked against original CPU values. Positive
strength, optimized/GPU path, full DNG import, Android/JNI device pixel parity,
physical Hasselblad-to-phone colour adaptation and matched photographic
accuracy are unresolved. Preserve the Stage58 phone build and ordinary Photon
capture until these gates actually pass.
