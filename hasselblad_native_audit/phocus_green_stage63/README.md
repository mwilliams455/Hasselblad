# Stage63: independent green estimation at red/blue sites

Stage63 independently implements `GetGreenAtRedFirst` in C11. Together with
Stages61–62, this supplies ten independently implemented demosaic components.
The estimator returns a green code, a packed direction mask and the maximum
gradient. The private original CPU audit compares all three outputs.
Substituting all ten components preserves **187,224 final linear RGB16 values
exactly** across 32 original-versus-substituted demosaic comparisons.

This is a host checkpoint. `InterpolateRGB`, its remaining pixel operations,
`ColorNoise` and `DirectionalColorCorrectionYCC` still execute original code
in the substitution runner. A complete independent demosaic, Android parity
and physical camera colour equivalence have not been established. The device
build remains **Stage58, `0.1-hb-rawprep58` / 27197**, with the Stage56 private
profile. Normal capture continues using Photon; no new APK is built here.

## Independent implementation and contract

`green63.c` and `green63.h` implement the estimator using standard C and
`fmaf`. `portable63.py` builds and loads the implementation without loading
a vendor binary. The separate audit loads the explicitly supplied private
Phocus APK, checks its existing identity contract and resolves the original
function symbol.

The portable interface accepts centre pointers to RAW and three scale maps,
stride, two arrays of eight signed gradients and two explicit threshold
floors. Native object ownership is not exposed through the C interface. The
two floors come from the caller's object state in connected comparisons;
they are not fitted to an image or hardcoded as a camera calibration.

Inputs require valid two-row/two-column halos. Consumed scale samples must be
finite and nonnegative. Unused map cells are not consumed or validated. Output
scalars must be disjoint from each other and all inputs. Native call sites
use separate scalar outputs; the substitution runner checks their separation.
The estimator does not discover a CFA, extend image edges, allocate an image
or reproduce the native constructor.

The original entry's legacy uint16 green-plane pointer is unused by this body:
null and three different mapped pointers produce the same audited outputs.
That observation is specific to this symbol and does not apply to other
gradient operations. RAW and float map pointers remain required.

The implementation preserves:

- Signed gradient thresholds, low-sixteen-bit narrowing and logical shifts.
- Cardinal candidates and bounded diagonal scale estimates.
- Explicit single-precision fused multiply-add for diagonal candidates.
- Saturating signed float-to-int conversion, including large positive values.
- Strict direction comparisons and the no-direction bilinear fallback.
- Modulo-32-bit sum/product arithmetic and signed division toward zero.
- The nearest-cardinal branch, tie ordering, its unchanged-mask zero-distance
  case and its original-count sentinel fallback.

## Direct original CPU checks

**10,783 cases match exactly for all three outputs: 32,349 scalar values.**
Coverage includes all 256 low direction selections through each gradient
input, strides 5/9/23, zero/constant/full/random RAW codes, random finite scale
maps, signed-gradient extremes, five threshold-floor pairs, saturating
conversions, all four nearest-cardinal choices and dedicated edge probes.
Eighteen additional cases cover subnormal scales and finite scales whose
multiplication overflows to positive infinity.
Source buffers, native object state, portable canaries and native allocation
guards are checked. The source APK and decoded private profile remain unchanged.

Native branch probes observe 684 no-direction averages, 9,985 selected-direction
averages, 146 entries into nearest-direction selection and 145 mask replacements.
These counts overlap: a nearest-direction sentinel can enter the averaging
branch. They are execution counts, not disjoint case categories.

The fused arithmetic negative control is deliberately compiled with a separate
multiply/add. On the retained synthetic witness, **native and portable output
50972; unfused output 50971**, with the same direction mask and maximum gradient.
That incorrect test implementation is generated only in the private work
directory; the normal C implementation always uses `fmaf`. The witness and
its exact float32 input bits are recorded in the aggregate receipt. This is
an arithmetic discrimination test, not a visible image-quality claim.

Other retained synthetic branch witnesses demonstrate why generic smoothing
or a simplified mask rewrite would change the original:

| Case | Green output | Packed mask | Preserved behavior |
| --- | ---: | ---: | --- |
| Nearest candidate differs from centre | 5000 | 0x101 | Select north only |
| Nearest candidate equals centre | 5000 | 0x40f | Keep all four cardinal directions |
| Closest-distance sentinel, four selected | 50000 | 0x101 | Divide the selected 200000 candidate by the original count 4 |
| Closest-distance sentinel, five selected | 40000 | 0x101 | Divide by the original count 5 |
| Signed product wraps at an extreme | 60000 | 0x40f | Use the original averaging branch |

These deliberately unusual inputs test arithmetic and control flow. They are
not evidence of their frequency or visual effect in ordinary photographs.

## Connected substitution

`audit_integration63.py` replaces this estimator together with all nine
Stage62 components. It snapshots the required input stencils, runs independent
C, writes the three outputs and skips the original body. Entry instrumentation
checks that no replaced original function executes during substituted runs.
The remaining original gradient functions are explicitly inventoried.

The suite retains Stage62's eight synthetic patterns/rectangles, four fixed
32×32 DNG tiles and four additional 16×24 DNG regions, with highlights bypassed
and with the bounded black/fast-Bayer/highlight/Bayer chain. Additional-grid
regions were held out from Stage61 but are now regression inputs reused from
Stage62. They are from the same photograph, not new independent reference
scenes. No source pixels or profiles are published and no image parameters
are fitted.

All **153,432 synthetic channels**, **24,576 fixed-grid DNG channels** and
**9,216 additional-grid DNG channels** match with zero difference. The suite
executes 32 original and 32 substituted demosaics. No replaced original body
executes in substituted runs. The aggregate receipt records actual component
call counts. Configuration remains the graph-captured fixed
camera context, controlled noise/lens services, unity demosaic gains and
original scalar-class dispatch. Compiler-emitted vector instructions can
still execute within that class. Output is linear RGB16 before main colour,
film and display processing.

Synthetic boundaries use the explicit reflect-101 audit fixture; DNG regions
use real interior neighbours. Native full-frame edge scheduling and CFA phase
remain unresolved. DNG inputs retain Stage58 normalization/gain-map clamps
but quantize before interpolation, so the study is not Stage58 device pixel
parity or a complete original DNG import reconstruction.

Validation uses GCC 13.3.0, C11, `-O2 -Wall -Wextra -Werror`,
`-fno-fast-math -ffp-contract=off`, and undefined-behaviour sanitization with
recovery disabled. Explicit `fmaf` remains fused despite the contraction flag.
The Python modules compile. Emulator timings are not phone benchmarks.

## Next checkpoint

The immediate next task is **independent `InterpolateRGB` orchestration and its
remaining inline pixel arithmetic**. Reuse the ten verified components and
preserve call order, map and plane ownership, halo/stride handling and flags.
Then independently implement `ColorNoise` and the executed
`DirectionalColorCorrectionYCC` route. Constructors, allocation/error handling,
alignment and full-frame boundaries need a declared supported contract.

Only after a complete independent demosaic passes original-reference checks
should it enter host/JNI and exported-device-pixel comparisons, followed by an
explicit saved-DNG option and a new APK. Keep Stage58 automatic DNG preparation,
automatic LUT selection, native finishing and highlights off as the device
baseline. Full RAW/gain-map import, cross-sensor adaptation, highlight inputs,
sharpening, live display and physical matched-reference validation remain
separate boundaries.

## Reproduce privately

Run with assertions enabled from the repository root:

```sh
python3 hasselblad_native_audit/phocus_green_stage63/audit_green63.py \
  --apk /private/original.apk --work /private/green63 --sanitize \
  --safe-receipt /private/green63.json

python3 hasselblad_native_audit/phocus_green_stage63/audit_integration63.py \
  --apk /private/original.apk --dng /private/input.dng \
  --work /private/integration63 --sanitize \
  --safe-receipt /private/integration63.json
```

Use the existing local private APK; do not fetch it from Library. Dependencies
are the Stage60–62 audit stack plus GCC and its sanitizer/runtime math library.
Original executable bytes, disassembly, private LUT/profile/calibration data,
photograph pixels and private input hashes stay outside new public source,
aggregate receipts and APKs.
