# Stage62: independent missing-colour interpolation

Stage62 implements `GetBlueAtRed` and `GetRedBlueAtGreen` in independent C11.
The two helpers supply missing red/blue values using green-weighted neighbour
pairs. They extend the seven independently checked Stage61 components.
Substituting all nine components inside the original bounded CPU demosaic
preserves **187,224 final RGB16 channels exactly**, across 32 comparisons.

This is a bounded host implementation checkpoint. Green estimation at red/blue
sites, the pixel-loop orchestration and colour/noise output work still execute
original code in the substitution harness. The phone build remains **Stage58,
`0.1-hb-rawprep58` / 27197**, with the Stage56 private profile. No APK is built
and normal capture continues using Photon.

[Stage63](../phocus_green_stage63/README.md) independently ports
`GetGreenAtRedFirst` and extends the connected check to ten components. The
results below remain the historical Stage62 checkpoint.

## Independent implementation

`interpolation62.c` and `interpolation62.h` use only standard C types and
integer operations. `portable62.py` builds and loads them without a vendor
binary. The separate private audit loads the explicitly supplied local Phocus
APK, verifies its existing identity contract and resolves the original symbols.

Both functions take image pointers directly; neither has an implicit object
argument. `GetBlueAtRed` uses four diagonal neighbours. The red/blue-at-green
helper uses four cardinal neighbours and computes two output planes. Weights
are based on the absolute difference from the centre green code, divided by
four with integer truncation, then incremented by one. The low eight direction
bits select weighted pairs. Zero-denominator pairs are omitted. If no usable
direction remains, the four colour neighbours are averaged.

The port preserves 64-bit products, modulo-32-bit accumulation, signed division
toward zero, the signed upper comparison with 65534, and final low-sixteen-bit
storage. It explicitly defines signed wrap conversion rather than relying on
undefined overflow or implementation-defined out-of-range signed conversion.
The two synthetic witnesses below prevent an apparently reasonable saturation
rewrite from silently changing the original behaviour.

| Synthetic input | Native and portable signed result | Stored code | Ordinary saturation would give |
| --- | ---: | ---: | ---: |
| Centre green 65535, neighbours green 1 / colour 65535, mask 1 | -131071 | 1 | 65534 |
| Centre green 32768, neighbours green 1 / colour 65535, mask 3 | -32768 | 32768 | 65534 |

These are deliberately extreme arithmetic probes, not claims about visible
photograph artefacts or their frequency. In the second case the individual
ratios remain positive signed values; their sum crosses the signed boundary.

The caller supplies valid one-row/one-column halos and stride in uint16
elements. The helpers do not select a CFA or extend image edges. Higher mask
bits are ignored. Red/blue output references may alias the input planes, as
they do in the original caller. All required inputs are sampled before either
write; the second output is written before the first. Shared output addresses
therefore retain the first plane's result.

## Direct original CPU validation

`audit_interpolation62.py` compares **21,822 blue-at-red register results** and
**22,062 red/blue-at-green calls**, or **65,946 stored output codes**, exactly.
It covers all 256 low direction masks for 27 patterns at each of three strides
(3, 8 and 19), additional seeded random 32-bit masks, and 300 alias cases.
Fixtures include constants, colour edges, impulses, low/high boundaries,
zero and partial-zero denominators, random codes, and overflow witnesses.

Every source and destination storage element is checked, including row padding
and unwritten output sentinels. Only declared aliased output addresses may
change. Portable canaries, native allocation guards and private profile/source
immutability are checked. GCC 13.3.0 builds with warnings as errors, no fast math,
FP contraction disabled and undefined-behaviour sanitization without recovery.
The Python modules compile. No Android/compiler-cross-target result is claimed.

## Connected demosaic validation

`audit_integration62.py` replaces the two new function bodies together with all
seven Stage61 components. Each substituted call obtains its outputs from the
independent C code. Original helper outputs are not used as replacement values.
Entry instrumentation checks that none of the nine replaced original bodies
execute during the substituted run, and counts actual native plane aliases.

The suite retains the six 64×64 synthetic patterns and four fixed 32×32 DNG
tiles from Stage61, each with highlights bypassed and with the bounded
black/fast-Bayer/highlight/Bayer sequence. It adds random 16×24 and 18×34
synthetic rectangles and four 16×24 interior DNG tiles at previously unused
grid locations. These additional tiles are held out from the Stage61 tile set,
but come from the same photograph; they are not independent physical reference
scenes. No scene-specific parameters are fitted.

All **153,432 synthetic channels**, **24,576 original-grid DNG channels** and
**9,216 additional-grid DNG channels** match with zero difference. The suite
runs 32 original and 32 substituted demosaic invocations. None of the nine
replaced original function bodies execute in substituted runs. The aggregate
execution receipt also inventories the original functions that still execute.
The graph-captured
fixed-camera parameters, controlled noise/lens services, unity demosaic gains
and scalar-class dispatch remain from Stage60. Compiler vector instructions
may still run within that class. Values are linear RGB16 before the main
colour LUT, film curve and display output, not sRGB accuracy measurements.

Synthetic boundaries use the explicit reflect-101 audit halo. DNG tiles use
actual interior neighbours. The DNG bridge retains Stage58 common-range
normalization and gain-map clamps, then quantizes before interpolation. Stage58
on the phone instead quantizes after its float bilinear interpolation. This
study therefore does not establish device pixel parity, native full-frame
edge handling or the original complete DNG importer.

## Next implementation boundary

1. Independently implement and execute-check `GetGreenAtRedFirst`, preserving
   its float scale calculations, direction thresholds, output references and
   integer narrowing. Unlike these two new helpers, that entry reads object
   state. Do not infer its ABI from these image-pointer-only entries.
2. Port `InterpolateRGB` and the remaining pixel-loop operations, then
   `ColorNoise` and the actually executed `DirectionalColorCorrectionYCC`
   route. Use the execution inventory rather than counting helpers as proof
   of complete demosaic coverage.
3. Validate a complete independent path with no original executable pixel
   operations. Resolve or explicitly restrict alignment, CFA phase, dimensions,
   halos, full-frame edges, parameters, allocation and error handling.
4. Add host/JNI and exported-device-pixel comparisons before introducing an
   explicit saved-DNG demosaic option and a genuinely new APK.

The wider RAW import/gain-map contract, cross-sensor colour basis, highlight
adaptation, sharpening and live-display path remain separate tasks. Numerical
parity here does not establish a physical phone-to-Hasselblad colour match.
Keep Stage58 automatic DNG preparation, automatic LUT selection and native
finishing with highlights off as the controlled device baseline.

## Reproduce privately

Run with Python assertions enabled from the repository root:

```sh
python3 hasselblad_native_audit/phocus_interpolation_stage62/audit_interpolation62.py \
  --apk /private/original.apk --work /private/helpers62 --sanitize \
  --safe-receipt /private/helpers62.json

python3 hasselblad_native_audit/phocus_interpolation_stage62/audit_integration62.py \
  --apk /private/original.apk --dng /private/input.dng \
  --work /private/integration62 --sanitize \
  --safe-receipt /private/integration62.json
```

Dependencies are the Stage60/61 private-runner stack (NumPy, Unicorn,
Capstone, ELF tooling and tifffile), GCC and its sanitizer runtime. Emulation
time is not a phone performance benchmark. Source APK, extracted executable,
profile/calibration payloads, photograph pixels and private input hashes remain
outside new public source, evidence and APKs. Only independent code, synthetic
witnesses and aggregate receipts are published.
