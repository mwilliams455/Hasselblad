# Stage71 — original-CPU inline gradients and bounded ColorNoise integration

**This is a private-native validation checkpoint, not a new Android build.**
Stage70 established exact 11-component substitution and corrected two
ColorNoise implementation defects. Stage71 tests the outstanding Stage67/68
inline gradient operands directly against the original ARM64 graph, and adds
independent corrected ColorNoise as the twelfth substituted component.

## Native basis and scope

Private fixture: the locally supplied Phocus APK and existing saved DNG.
Neither is in this repository or any GitHub Actions artifact. The original
ARM64 CPU is executed via Unicorn only on the local private host.

The graph's observed `ColorNoise` context is `flags=0xFFFF`, optimized-view
false, extra noise strength zero, working regions of 128×128 for synthetic
cases and 96×96 for the saved-DNG tiles, both with stride 1024. The 14 required native colour/noise planes are present and mutually
disjoint at this call site. The Stage71 runner rejects any other graph state,
invalid dimensions, null pointers or overlapping spans, rather than silently
processing unsupported modes. It snapshots every plane before independent C
execution, verifies that the read-only planes are unchanged and writes back
only the named mutable planes. It returns immediately to the original caller
without executing the vendor `ColorNoise` body.

Corrected C `noise65.c` from Stage70 is the sole implementation of this
replacement. Its internal directional YCC operation links to the independent
Stage64 C code; therefore the **eleven previously ported components plus
ColorNoise** are independent in the declared bounded call path. YCC no longer
appears as a separate emulated call when its parent `ColorNoise` body is
skipped, which must not be mistaken for missing C processing.

A successful Stage71 comparison **does not mean the complete demosaic has
been independently implemented**. The original `InterpolateRGB` pixel-loop
and additional inline work still execute in the comparison harness.

## Reproduction and controls

Public source location:

- `phocus_native_stage71/audit_colornoise_substitution71.py`
- existing `phocus_inline_stage67/audit_native_inline67.py`
- existing `phocus_coloursite_stage68/audit_native_colour68.py`
- corrected `phocus_noise_stage65/noise65.c` and Stage64 YCC code

Only the original private host may execute the native tests; CI runs synthetic
source tests and syntax checks, **never the original APK or DNG**.

```sh
# Use the existing local private APK/DNG and private runner; never pull private
# binary, profile, photograph, calibration or saved-source hashes into CI.
PYTHONPATH=/private/emulator-wheels python /private/run_private_audit70.py \
  hasselblad_native_audit/phocus_native_stage71/audit_colornoise_substitution71.py \
  --apk /private/original-phocus.apk \
  --dng /private/existing-fixture.dng \
  --work /private/stage71-work \
  --safe-receipt /private/stage71-native.json --fixture all --sanitize
```

The Stage71 runner includes a `--probe-only` mode to verify the actual
pointer/flag/stride ownership without substituting any code. Synthetic
patterns and four interior private DNG tiles may be tested with highlight
reconstruction bypassed and with the bounded Bayer-highlight route.
`--fixture neutral` provides a shorter smoke comparison. Any mismatch fails
without writing a success report.

Host C builds use GCC C11 with warnings as errors, no fast math, and
undefined-behaviour sanitization. Stage64/65 test suites additionally run
under AddressSanitizer in CI. Existing Stage67/68 operand audit runners do
**not** skip the inline SIMD itself: they compare/replace operands at the next
native function boundary, which is a narrower parity claim than a fully
independent pixel loop.

## Executed original-CPU evidence — 25 October 2026

These results were obtained from the locally supplied **original** Phocus
executable and independent C implementations. Each fixture runs both the
original graph and the graph with the declared C substitutions.

| Test | Original-CPU result |
| --- | ---: |
| Stage66 supported scalar scheduling | 6 exact call-boundary cases |
| Stage67 green-site RAW-gradient operands | 426 exact samples; 73,728 final RGB16 channels |
| Stage67 Stage61 signed-edge operands | 426 exact samples |
| Stage68 colour-site RAW-gradient operands | 1,062 exact samples |
| Stage68 signed-edge operands | 1,062 exact samples |
| Stage68 native colour-site DNG/synthetic RGB16 | 172,032 exact channels |
| Stage71 connected native twelve-component comparisons | 20 exact |
| Stage71 final linear RGB16 values | **172,032 exact; maximum difference 0** |
| Stage71 independent `ColorNoise` body calls | 20; original body bypassed |
| Stage71 C directional YCC operations inside ColorNoise | 171,264 |

Stage71 compared six synthetic scenes and four interior DNG tiles with both
highlight modes. The synthetic calls used 128×128 native working frames; DNG
tiles used 96×96; both used 1024-element stride, 0xFFFF flags, optimized view
off and zero extra noise strength. The private APK, photograph and decoded
profiles were not changed and their pixels, hashes and executable material
were not exported. This is a bounded original-CPU check, not a camera-scene
fidelity measurement or a full independent `InterpolateRGB` replacement.

Public aggregate report: `evidence/stage71/STAGE71_NATIVE_PARITY.json`.

## Further work after native parity

1. Reconstruct and independently execute the *entire* original
   `InterpolateRGB` calculation and its preparation/colour-noise scheduling.
   Compare full final RGB16 output with original CPU code that is excluded
   from the independent execution, not merely replaced operands.
2. Determine original alignment and full-frame edge policy; validate native
   halos, stride, CFA phase, constructor configuration, errors and resources.
3. Build Android host/JNI equivalence checks with actual exported pixels;
   the saved-DNG fixture currently quantizes before Bayer interpolation,
   unlike Stage58's float-bilinear preparation and preview.
4. Preserve sensor-specific DNG input-domain calibration, gain-map ordering,
   white-balance ownership, highlight limitations and scene-independent
   physical Hasselblad reference validation as separate open boundaries.
5. Only then add an explicit saved-DNG experimental comparator to a new APK;
   do not change stable Photon normal capture. Stage58 is still the phone
   baseline, `0.1-hb-rawprep58` / version code 27197.

No executable bytes, private decoded profiles, matrices, DNG pixels, user
input hashes, or original instruction listings are committed. Public receipts
contain only aggregate comparisons, counts, feature flags and limitations.
