# Stage64 — bounded directional YCC colour/noise candidate

Stage63 on `experimental/phocus-green63` independently verified **ten** CPU
components, including `GetGreenAtRedFirst`, with exact final RGB16 values in its
bounded original CPU substitution suite. Stage64 begins the remaining
**colour/noise** work by independently reconstructing the executed
`DirectionalColorCorrectionYCC` helper.

**IMPORTANT — Stage64 is a host research *candidate*, not a new verified native
port.** The initial Stage64 run did not have the private Stage60–63 Unicorn,
Capstone and ELF tooling available in the active environment. A *private,
limited interpreter of the extracted ARM64 instruction listing* was used
instead. It is not original ARM64 CPU execution and cannot establish direct
native parity. No source DNG values or original executable bytes are committed.
The Stage58 phone baseline (`0.1-hb-rawprep58` / 27197) remains unchanged.

## What is implemented

`ycc64.c` / `ycc64.h` model one directional YCC helper, not a generic new
smoothing algorithm or a complete colour science pipeline. The bounded input
contract consists of a direction mask, three centre samples (unsigned luma,
two signed chromas), three neighbour planes centred on the same site, an
explicit stride and four independent two-byte output references. It requires
valid neighbouring sample sites, no edge extension, and disjoint output
references. This stage does not infer a CFA or reconstruct the full DNG import.

The candidate preserves the following **execution-derived hypotheses**, with
explicit 32-bit integer narrowing rather than accidental signed overflow:

- Four opposite-neighbour direction pairs with offsets `1`, `stride`,
  `stride-1`, `stride+1`.
- Unsigned absolute luma difference and signed chroma differences, an integer
  reciprocal-six gradient weighting step, and a special equal-gradient branch.
- Direction selection from the low eight bits and a *separate four-bit count*
  encoded in the mask; the stored count is not silently recomputed from bits.
- Signed division and modulo-32-bit accumulation, colour blending using
  fixed-point weights, and a separate final chroma attenuation.
- Initial scalar output copies, with the fourth output reset to zero when
  the centre luma is zero.

This is an explicit *CPU helper candidate*, not the whole `ColorNoise` step or
native `InterpolateRGB` orchestration.

## Checks actually executed in the current workspace

- Independent C11 unit tests pass with GCC warnings as errors and
  undefined-behaviour sanitization, with no fast math or FP contraction.
  They include flat cases, all 256 low mask patterns, zero luma, immutable
  sources and seven fixed synthetic direction/weight witnesses.
- **3,770 cases / 15,080 output codes** match the *private ARM64
  instruction-list interpreter* exactly (zero difference). This covers
  all low mask values, varied packed count fields, multiple strides, signed
  extrema, random samples, zero codes, alternating high/low neighbours.
  An instruction interpreter, however, is not a replacement for direct
  execution against the vendor CPU code and may share a misunderstanding of
  an instruction's semantics.
- Python entrypoints and wrappers passed syntax checks. The original CPU
  runner and eleven-component connected substitution runner have been
  **written, but have not run successfully in this environment**.

Only aggregate evidence in `evidence/stage64` is publicly committed. The
private disassembly, instruction interpreter, original APK, RAW fixtures,
profiles and private input hashes are **not** included.

## Reproduce standalone C candidate

From this source directory:

```sh
gcc -std=c11 -O2 -Wall -Wextra -Werror \
  -fno-fast-math -ffp-contract=off \
  -fsanitize=undefined -fno-sanitize-recover=all \
  ycc64.c test_ycc64.c -o /private/test_ycc64
/private/test_ycc64
python3 -m py_compile portable64.py audit_ycc64.py audit_integration64.py
```

## Required original CPU gates, pending

These runners use the **existing locally supplied private original Phocus
APK**, not a public/Library download or CI binary. They require the existing
Stage60–63 fixture stack, original build identity checks, NumPy, Unicorn,
Capstone, pyelftools, GCC and its sanitizers. They must run with assertions
enabled. Full reproduction requires the two parent Stage62/63 branches from
which Stage64 is based.

```sh
python3 hasselblad_native_audit/phocus_colour_stage64/audit_ycc64.py \
  --apk /private/original.apk --work /private/ycc64 \
  --sanitize --safe-receipt /private/ycc64-original-cpu.json

python3 hasselblad_native_audit/phocus_colour_stage64/audit_integration64.py \
  --apk /private/original.apk --dng /private/retained.dng \
  --work /private/colour-integration64 --sanitize \
  --safe-receipt /private/colour-integration64.json
```

The direct runner declares **3,840** native comparisons (768 mask sweeps plus
3,072 varied-code cases), checking four output codes per case and all source
and output canaries. These are *planned* counts, not achieved results.
The connected runner tries the Stage63 suite: 16 synthetic original/substituted
comparisons, and optionally 16 private-DNG comparisons, with highlights off
and on via the existing Bayer route. The eleven-component label is valid
**only if its native comparisons complete exactly**. The runner deliberately
asserts that this helper was invoked and replaced, and that original replaced
bodies did not execute in the substitute pass. Missing execution is a failed
validation, not permission to declare success.

## Next work

1. Run direct original CPU YCC comparison and fix any differences, including
   output-alias and scalar threshold boundary behaviour.
2. Run connected **eleven-component substitution** and inspect any remaining
   original helper entries. Preserve Stage63 RGB16 parity.
3. Independently reconstruct `ColorNoise` and `InterpolateRGB`, including
   plane ownership, map/threshold decisions, row/stride and alignment rules,
   allocation and status/error behaviour. An isolated small helper does not
   imply the full demosaic is independent.
4. Validate complete host path, JNI and exported device pixels before
   adding an opt-in saved-DNG comparison or preparing a genuinely new APK.
   Full RAW import, cross-sensor colour adaptation, highlight assumptions,
   sharpening, live display and physical matched-reference captures are
   separate unresolved goals.
