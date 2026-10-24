# Stage60: native Bayer routing and executable gradient demosaic

Stage60 verifies independent aligned-RGGB fast interpolation and RGB-to-Bayer
selection against original CPU execution. It also runs the original downstream
gradient demosaic, including a connected black-subtraction, fast-interpolation,
highlight, Bayer and gradient-demosaic sequence on synthetic inputs.

The gradient algorithm is now an executable reference, **not an independently
validated portable implementation**. No rendering parameters were fitted to a
photograph. No app source changed and no APK was built. The current phone build
remains **Stage58, `0.1-hb-rawprep58` / 27197**, with the Stage56 private profile.

## Exact bounded interpolation result

The step-one, green-blending-disabled fast branch uses ordinary integer
bilinear interpolation: pair averages truncate after division by two; cross
and diagonal averages truncate after division by four. Measured CFA samples
are preserved. The independent equations are in `reference60.py`.

| Check | Coverage | Result |
| --- | --- | --- |
| Original fast CPU vs independent equations | 27 cases, 23,733 RGB16 channels | Exact |
| Fast RGB returned to the original Bayer sites | 7,911 sites | Exact |
| Black, fast RGB, highlight and Bayer connected | 12 cases, 27,648 highlight channels and 9,216 final Bayer sites | Exact |

Fixtures cover odd/even dimensions, zero/full codes, random codes, ramps,
edges, CFA impulses, two black offsets and all six permutations of three
unequal WB gains. The highlight comparison uses the existing Stage53 portable
C implementation. Original typed image views and pixel bodies execute; buffer
allocation and ownership are controlled host fixtures. Source and profile
immutability and allocation guards pass.

RGB-to-Bayer extraction keeps the channel belonging to each CFA site. The
supported portable domain is **aligned RGGB**. Twenty additional phase/origin
probes inspect 1,980 sites: ten match an ordinary shifted CFA and ten odd
horizontal alignments do not. The receipt preserves the synthetic channel
selection witnesses. The native alignment scheduler was not executed, so this
is neither evidence of a native bug nor permission to generalize this branch
to every sensor layout. Other interpolation steps, the green-blending branch,
and four/six-channel extraction are outside the audit.

## Original gradient CPU reference

`audit_gradient60.py` executes the original `CDemosaicFilter::FilterResult`,
`GGDirInterpolator` and `CGradientInterpolate` pixel bodies. Demosaic parameters
are captured from the original graph constructor in the existing fixed-camera,
noise/lens-disabled fixture, including unity demosaic gains. The graph
constructor and the sequential pixel harness are distinct from running the
original full image scheduler.

The CPU dispatch service selects the scalar gradient class. Compiler-generated
vector instructions still run. Host allocation, the clock and a disabled
performance-log label are mocked; the task queue is null for synchronous
execution. Requested workspace sizes are preserved, including the original
large internal buffers. A 128 MiB host arena accommodates those allocations.

Six 64 × 64 cases exercise a constant neutral, flat CFA colour, ramp, colour
edge, red impulse and seeded random codes. Each direct gradient case is
repeated with different initial memory fill bytes, with identical output.
The constant 10,000 neutral remains exactly 10,000 in all three channels.
Guards, source immutability and original success returns pass.

The same six fixtures also execute the connected highlight-to-Bayer-to-gradient
sequence and a gradient comparison with highlights bypassed: **24 original
gradient invocations**, with 24,576 pixels per comparison set. An explicit
reflect-101 boundary fixture supplies a 32-site gradient halo; it does not
reproduce the native full-frame edge policy.

| Synthetic fixture | Gradient vs integer bilinear: maximum RGB16 difference |
| --- | ---: |
| Neutral | 0 |
| Flat colour | 1 |
| Ramp | 263 |
| Colour edge | 21,994 |
| Red impulse | 49,996 |
| Random codes | 61,503 |

These are differences between algorithms, **not accuracy scores**. Extreme
synthetic patterns are not representative photographic error measurements.
The result demonstrates why a second bilinear pass cannot be described as
the native final demosaic. The connected route also differs from simply
forwarding the highlighted RGB image to colour processing.

## Private DNG tile study

`audit_saved60.py` checks four fixed 32 × 32 interior tiles at a regular 2 × 2
spatial grid, using actual neighbouring sites with a 36-site input halo. Tiles
are not chosen by brightness, colour or a desired result. No parameters are
optimized from the scene, and no photograph pixels are exported.

Input preparation uses Stage58 common-range normalization, 0..1 clipping and
the four DNG GainMaps with an upper clamp after each. For this native mosaic
interface, the values are quantized to Bayer uint16 **before interpolation**.
That differs from Stage58's float-bilinear-then-RGB16 device buffer. This is an
experimental input bridge, not device pixel parity or the original DNG decoder.

All figures below are absolute differences in **linear RGB16 before colour,
film and display**, not sRGB or perceptual colour differences.

| Fixed grid tile | Gradient vs integer bilinear, highlights off: maximum / mean | Highlight → Bayer → gradient vs direct highlight RGB: maximum / mean |
| --- | ---: | ---: |
| Upper left | 1,822 / 217.51 | 939 / 123.02 |
| Upper right | 613 / 55.68 | 323 / 32.01 |
| Lower left | 1,535 / 156.33 | 814 / 83.66 |
| Lower right | 1,263 / 155.93 | 605 / 84.35 |

There are 4,096 pixels per comparison. The report separately retains the
effect of enabling the existing highlight operation with native demosaic.
That operation still uses DNG-derived reciprocal WB ratios and the prepared
encoding ceiling, not measured sensor saturation. Its broad colour changes
are not proof that it should become the phone default. Source DNG and APK
immutability and memory guards pass; their private hashes are not published.

## Implementation decision

Keep Stage58 `automatic_dng_preparation`, with automatic LUT selection, native
finishing and highlights off, as the current controlled device baseline.
There is no new phone installation for Stage60. The exact aligned-RGGB fast
and extraction equations can support a later port, but the downstream gradient
algorithm has not yet been independently implemented or compared on device.

The next implementation gate is an independent gradient implementation checked
against this original-code reference on synthetic cases before any phone
integration. Native phase scheduling and outer-frame handling also need
validation. Original source-description/DNG decode, gain-map handling, GPU
behavior and physical phone-to-Hasselblad colour calibration remain separate
unresolved boundaries. Cross-camera accuracy requires controlled reference
captures and held-out scenes. Normal capture still uses Photon; full Phocus
equivalence and physical Hasselblad colour-match validation remain false.

## Reproduce privately

Run from the repository root, with assertions enabled:

```sh
python3 hasselblad_native_audit/phocus_bayer_stage60/audit_bayer60.py \
  --apk /private/original.apk --work /private/bayer60-work \
  --safe-receipt /private/bayer60.json

python3 hasselblad_native_audit/phocus_bayer_stage60/audit_gradient60.py \
  --apk /private/original.apk --safe-receipt /private/gradient60.json

python3 hasselblad_native_audit/phocus_bayer_stage60/audit_saved60.py \
  --apk /private/original.apk --dng /private/input.dng \
  --safe-receipt /private/tiles60.json
```

These extend the Stage59 bounded ARM64 runner and its existing dependencies:
NumPy, Unicorn, Capstone and ELF tooling, plus GCC for the Stage53 C comparison
and tifffile for the private DNG study. Original APK, extracted code, DNG pixels,
private profiles and calibration values remain outside git, CI and APK.
Only independently authored audit code and aggregate receipts in
`evidence/stage60` are published. This is a host research checkpoint; it does
not establish a new device rendering or performance result.
