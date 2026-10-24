# Stage62: native red/blue helper boundary instrumentation

**Status: probe infrastructure, not a completed Stage62 interpolation port.**
Stage61's independent seven-kernel substitution remains the control. The
current device APK is still Stage58 (`0.1-hb-rawprep58` / `27197`). No normal
camera capture path, experimental device renderer, or private profile changed.

## Why this checkpoint exists

The next missing original CPU helpers are:

- `CGradientInterpolate::GetBlueAtRed`
- `CGradientInterpolate::GetRedBlueAtGreen`
- followed by `GetGreenAtRedFirst`, pixel-loop orchestration and colour/noise.

The first two helper entries were inspected statically in Stage61, but their
pixel formulas, exact argument meanings, narrowing and aliasing are **not yet
verified by original-code execution**. Do not substitute standard bilinear or
gradient equations and claim native parity. The Stage61 handoff explicitly
identifies diagonal/green weighting and 32/64-bit operations as *hypotheses*.

`helper_trace62.py` adds a **read-only runtime boundary probe** with a separate
public summary and optional local-only private samples. The in-situ
`audit_helpers62.py` executes the same twelve synthetic and optional eight
DNG-tile comparisons as Stage61 with all seven established C kernels
substituted, while observing original calls to the two still-native helpers.
It measures call/return counts and, if enabled, samples original argument
registers, possible pointer neighbourhoods, low-sixteen-bit return and
writable-reference output values. The sampled register interpretation is
*provisional*; testing whether it is correct is part of the investigation.

`fixed_width62.c` provides C11 primitive models for low-bit narrowing,
32-bit wrapped multiplication/addition and AArch64 signed division. The
AArch64 instruction model's divide-by-zero and signed-overflow results follow
the architecture specification; this does **not** establish that those exact
operations occur on the original interpolation path or specify the helper's
zero-denominator fallback. The 65534 comparison is a predicate, deliberately
not an invented saturation formula.

## Locally checked, without vendor code

```sh
python3 -m unittest -v test_helper_trace62.py
gcc -std=c11 -O2 -Wall -Wextra -Werror -fno-fast-math \
  -ffp-contract=off -fsanitize=undefined -fno-sanitize-recover=all \
  fixed_width62.c test_fixed_width62.c -o /tmp/test_fixed_width62
/tmp/test_fixed_width62
python3 -m py_compile helper_trace62.py audit_helpers62.py
```

Five lifecycle tests check return-value capture, two output references,
invalid pointer guesses, nesting, sample limits and the non-sensitive public
summary. The fixed-width test checks wrap, signed narrowing, zero divisors,
signed-overflow and the 65534 threshold. These are **host self-tests** only.

## Required private native run (not done in this environment)

Requires the locally supplied original Phocus APK, optional retained DNG,
Unicorn/ELF dependencies and the parent Stage61/Stage60 repo files. Do not
retrieve the original APK from Library contrary to the retained user
instruction. If the original local APK is unavailable, obtain another local
attachment first.

```sh
python3 hasselblad_native_audit/phocus_gradient_stage62/audit_helpers62.py \
  --apk /private/locally_supplied_phocus.apk \
  --dng /private/retained_input.dng \
  --work /private/stage62-probe-work \
  --safe-receipt /private/stage62-safe-report.json \
  --private-traces --sanitize
```

The `--work` path must be **outside the repository**. Raw pointer/register
values and potential photographic pixel values are written only to
`STAGE62_LOCAL_HELPER_TRACES.private.json` there, with owner-only file mode,
when `--private-traces` is explicitly selected. Never commit it, upload it to
CI or include it in an APK. The public receipt intentionally contains only
counts, flags and previous Stage61 RGB16 parity statistics (not the original
helper return values).

## Next steps after the private run

1. Verify each helper's actual register/stack contract and all call-site
   output aliases. Check which arguments are pointers, strides, masks and
   thresholds before trusting a candidate formula.
2. Build controlled original-helper fixtures for each direction bit and mask
   combination, no selected directions, zero denominators, constant Bayer,
   edges, impulses, seeded random codes, and low/high integer boundaries.
3. Derive and implement both complete independent interpolation helpers in C;
   include the native integer evaluation order, 64-bit products, 32-bit
   narrowing and signed division details established by the probes.
4. Execute direct original-vs-independent comparisons. Extend Stage61's
   **connected substitution harness** to both helpers and retain highlight
   bypass/on plus fixed private-DNG tiles. Prove zero final RGB16 differences.
5. Proceed to `GetGreenAtRedFirst`, full pixel-loop orchestration, colour/noise
   operations, outer-frame/phase validation, JNI parity, and only then a new APK.

There is **no new native helper equivalence claim, physical colour match, or
complete demosaic** at this checkpoint. No device pixel comparison occurred.
