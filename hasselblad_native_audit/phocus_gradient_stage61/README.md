# Stage61: independent gradient preparation and directional kernels

Stage61 implements **seven native gradient-demosaic components in independent
C11**. Replacing their original CPU bodies inside the Stage60 audit harness
preserves exact final RGB16 output across six synthetic patterns and four
fixed DNG tiles, with and without the highlight/Bayer sequence: **172,032
channels, zero difference**.

The remaining native interpolation and colour/noise operations still execute.
This is an independently checked part of the demosaic, not a complete portable
demosaic or validation of a physical Hasselblad colour match. No scene-specific
parameters were fitted. No app files changed and no APK was built. The current
phone build remains **Stage58, `0.1-hb-rawprep58` / 27197**, with the Stage56
private profile.

## Portable implementation

`gradient_maps61.c` and its header depend only on the C standard library. The
host wrapper `portable61.py` builds and calls that implementation without
loading any vendor binary. The separate original-code audits require the
locally supplied private APK.

| Component | Preserved behavior |
| --- | --- |
| Directional scale maps | Alternating five-sample colour/green ratios, contrast weights, low-value threshold and untouched contrast slots |
| Initial green map | Average of the middle two of four directional scales, original float evaluation order, upper clamp and integer truncation |
| Smoothing row | Integer separable 1–2–1 stencil, division by sixteen, zero border |
| Edge row | Centre-versus-diagonal difference, signed division rounded down, zero border |
| Signed median row | Median of three row medians, copied border |
| Eight directional gradients | Original directional ordering, integer truncation and low-sixteen-bit narrowing |
| Direction mask | Both gradient thresholds, first-gradient fallback, packed selected-direction count and all-directions fallback |

Two negative controls matter for a faithful port. The native median operation
is **not a full nine-value median**: the retained synthetic witness produces 2,
where the full median produces 3. Also, the scale-map contrast test compares a
float result with double `0.05`. Replacing that constant with `0.05f` changes
the branch for the retained five-sample witness. The portable code preserves
both behaviors rather than replacing them with superficially similar filters.

The C contract requires disjoint buffers, valid halos and aligned RGGB cell
origins. It does not extend image edges or discover a sensor's CFA. Float
inputs to the initial-green operation must be finite and nonnegative. Compile
with fast math and FP contraction disabled; the supplied wrapper does this.
Integer narrowing is explicit, including signed wraparound, so it does not
depend on a compiler's out-of-range signed conversion behavior.

## Original-code checks

| Check | Coverage | Result |
| --- | --- | --- |
| Scale and initial-green prepasses | 108 cases, 54,378 CFA cells | Bit exact |
| Ratio/contrast map slots | 435,024 comparisons, including untouched low-value slots | Exact |
| Initial-green scales and codes | 108,756 of each | Exact |
| Three row filters | 135 cases, 5,535 row output codes | Exact |
| Eight-direction calculation | 204 cases, 1,632 codes | Exact |
| Packed direction mask | 1,683 cases | Exact |

The complete prepass output storage, including padding and unwritten sites,
is also compared byte-for-byte: 1,190,592 elements. These are storage checks,
not additional rendered pixels. Inputs cover zero, one, threshold values,
full codes, ramps, seeded random codes, signed extremes and the double/float
comparison boundary. No private calibration values or photograph pixels are
embedded in the C implementation or receipts.

Native scalar and compiler-vector loop execution is measured, rather than
inferred from image width. The initial-green vector loop requires the tested
single two-row cell band; the tested multi-band regions select the scalar
loop. Both match the C implementation. Both loop paths of all three row
filters are also exercised. This does not validate the separate native
optimized gradient class or GPU renderer.

All three suites use GCC 13.3.0 with `-O2 -fno-fast-math -ffp-contract=off`,
warnings treated as errors and undefined-behavior sanitization with recovery
disabled. Source immutability, allocation guards, portable-buffer canaries,
and the original profile guards pass. The Python audit modules compile.
This is host validation; Android execution and performance are not measured.

## Substitution inside the original demosaic

`audit_integration61.py` first runs the original Stage60 gradient reference.
It then skips each of the seven original function bodies at its call boundary,
executes the corresponding independent C function and supplies those outputs
to the remaining original processing. It does not compare an output buffer
with a copy of itself or use original intermediate results as the C outputs.

The twelve synthetic comparisons contain six 64 × 64 fixtures, each with
highlights bypassed and with black subtraction, fast interpolation, highlight
reconstruction and conversion back to Bayer. All **147,456 RGB16 channels**
match. Eight private-DNG comparisons use the four fixed 32 × 32 grid tiles
in both modes; all **24,576 RGB16 channels** match. The resulting values are
before colour/film/display, not sRGB.

The independent substitutions execute 4,528 smoothing calls, 2,224 edge calls,
20 scale-map calls, 20 initial-green calls, 218,240 directional calculations,
100,864 mask calculations and 4,528 median calls. Every component is exercised
in the connected path. These counts include the processing halos; they are
not additional output pixels or a performance benchmark.

The original graph-captured parameters, fixed camera context, noise/lens
service fixture, unity demosaic gains and scalar-class dispatch from Stage60
remain. Synthetic boundaries use its explicit reflect-101 halo. Private DNG
tiles use actual interior neighbours. The DNG bridge still performs Stage58
common-range normalization and gain-map clamps, then quantizes to Bayer
before interpolation. It is **not the Stage58 device RGB16 buffer** or the
original full DNG decoder. Both source DNG and source APK remain unchanged.

## Next implementation boundary

The green-at-red/blue decision, missing red/blue interpolation, pixel-loop
orchestration and the remaining colour/noise output operations still need
independent implementations and original-code comparisons. Native alignment
scheduling, full-frame edges, source-description/DNG import and gain-map
behavior remain separate unresolved boundaries. No complete-gradient parity,
device parity, GPU/live-display equivalence or physical cross-camera colour
accuracy is claimed.

Keep the Stage58 `automatic_dng_preparation` comparison with automatic LUT
selection, native finishing and highlights off as the current controlled
phone baseline. It does not require a new installation for Stage61. Normal
capture continues using Photon. The port should be completed and checked
before replacing the device demosaic; this checkpoint does not justify a
scene-specific look correction or enabling highlights by default.

## Reproduce privately

Run from the repository root with assertions enabled:

```sh
python3 hasselblad_native_audit/phocus_gradient_stage61/audit_maps61.py \
  --apk /private/original.apk --work /private/maps61-work --sanitize \
  --safe-receipt /private/maps61.json

python3 hasselblad_native_audit/phocus_gradient_stage61/audit_kernels61.py \
  --apk /private/original.apk --work /private/kernels61-work --sanitize \
  --safe-receipt /private/kernels61.json

python3 hasselblad_native_audit/phocus_gradient_stage61/audit_integration61.py \
  --apk /private/original.apk --dng /private/input.dng \
  --work /private/integration61-work --sanitize \
  --safe-receipt /private/integration61.json
```

The original-code runners retain Stage60's NumPy, Unicorn, Capstone and ELF
tooling dependencies. The DNG study also needs tifffile; the independent C
build needs GCC and its sanitizer runtime. The original APK, extracted code,
user DNG, private profiles and calibration payloads stay outside git, CI and
APK. Only independent source and aggregate receipts in `evidence/stage61`
are published.
