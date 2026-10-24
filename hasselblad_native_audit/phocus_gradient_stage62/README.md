# Stage62: independent red/blue interpolation helpers (host checkpoint)

**Status: TWO HELPER IMPLEMENTATIONS, INSTRUCTION-LEVEL PARITY ON SYNTHETIC INPUTS.**
The remaining original green interpolation, pixel-loop orchestration and
colour/noise operations have **not** been ported. Stage58
(`0.1-hb-rawprep58` / `27197`) is still the current phone build; no APK or
normal capture path was changed.

## Progress relative to Stage61

Stage61 supplied seven independently checked C11 gradient components and a
connected original-CPU substitution harness. Stage62 adds:

- `interpolate62.h` and `interpolate62.c`: independent C11 implementations of
  `GetBlueAtRed` and `GetRedBlueAtGreen` for the bounded original CPU helper
  entry-point contracts. The first returns its original 32-bit W0 result;
  callers may narrow to 16 bits. The second produces two `uint16_t` outputs.
- `test_interpolate62.c`: host-only synthetic constant-colour, fallback,
  clipping, all-256-mask and output-alias tests with UB sanitization.
- `audit_substitution62.py`: **prepared but unexecuted** nine-kernel connected
  comparison. It extends the Stage61 substitution runner with just the two
  new C helper bodies. It snapshots source stencils before writing guest
  output references and respects the native write order.
- The previous Stage62 read-only helper boundary instrumentation and fixed-
  width arithmetic probes remain available on this branch.

## Reconstructed helper behaviour

Both routines weight candidate colour neighbours according to a green-plane
absolute-difference estimate `1 + (abs(center_green - neighbour_green) >> 2)`.
Each eligible direction contributes a *ratio of integer weighted sums*
multiplied by centre green. The packed direction mask determines which
candidates are active. A zero green denominator disables that candidate;
when none remains, the original function falls back to an unweighted average
of four diagonal samples (blue-at-red) or four cardinal samples (red/blue at
green).

The port preserves the actual paired neighbour selection, repeated direction
paths, widening for integer products and unsigned division, 32-bit narrowing
and summation, signed division for averaging, final signed comparison against
65,534 and the two-reference write order. It does not apply any phone-specific
colour correction, white balance, sharpening or scene fitting.

The two helper contracts require valid one-site halos and sensible positive
strides. In the connected harness, the 3×3 host stencils are copies of the
native helper's actual neighbourhood, not a changed interpolation scheme.
The routines do not themselves solve source Bayer phase, full-frame boundaries,
noise reduction, or the later colour pipeline.

## Validation performed on 24 October 2026

The locally supplied original Phocus APK was used **privately** to extract and
decode the two AArch64 helper bodies. A purpose-built interpreter executed the
extracted *instruction listings* with synthetic guest registers and memory.
This is **not** original CPU execution under Unicorn, QEMU or device hardware;
interpretation defects could cause correlated errors. The original executable
instructions and the private interpreter remain outside GitHub.

Results (no private photographs, profile values or file hashes exported):

| Comparison scope | Helper evaluations | Differences |
| --- | ---: | ---: |
| Eight base synthetic patterns × all 256 masks, both helpers | 4,096 | 0 |
| 500 additional seeded random masks, both helpers | 1,000 | 0 |
| Four strides × eight extreme-pattern fixtures, including aliasing | 2,624 | 0 |
| **Combined** | **7,720** | **0** |

Input patterns include zeros, 65,535, constant RGB, checkerboards, gradients,
impulses, random 16-bit codes, near-zero green denominators, packed masks with
upper count bits and overlapping output/source addresses. For the first
helper, all 32 returned bits were compared. For the second helper, both final
16-bit output references were compared. These were *helper* comparisons, not
7,720 complete rendered pixels. GCC C11 strict-warning and undefined-behaviour
sanitization self-tests passed; the preceding Stage62 probe tests also passed.

**Claims not yet established:** Direct execution of these two original helpers
in the Stage61 Unicorn runner, nine-kernel connected final RGB16 parity, real
DNG tile parity for the two substitutions, Android JNI parity, full independent
Phocus demosaic, or physical Hasselblad-vs-phone colour matching.

## How to run the next native completion gate

Run from the repository root with the locally supplied **private** original
APK. Its bytes must not be committed, sent to CI or packed into an APK. A
private DNG is optional but required for the retained DNG tile comparisons.

```sh
python3 hasselblad_native_audit/phocus_gradient_stage62/audit_substitution62.py \
  --apk /private/locally_supplied_phocus.apk \
  --dng /private/retained_image.dng \
  --work /private/stage62-native-work \
  --safe-receipt /private/stage62-native-aggregate.json --sanitize
```

The work path must be outside the Git repository. The script first executes
original demosaic operations and then replaces *nine* helpers (seven from
Stage61 and the two Stage62 C routines) in the same bounded CPU graph. It
compares final linear RGB16 on Stage61 synthetic fixtures, both highlight
modes, and four fixed DNG tiles when supplied. This run is **pending**, not a
result of the earlier instruction-level comparisons.

The independently runnable synthetic C self-test is:

```sh
gcc -std=c11 -O2 -Wall -Wextra -Werror -fno-fast-math \
  -ffp-contract=off -fsanitize=undefined -fno-sanitize-recover=all \
  interpolate62.c test_interpolate62.c -o /tmp/test_interpolate62
/tmp/test_interpolate62
```

## Next implementation

After executing the direct native helper and nine-kernel connected checks,
reconstruct and execute-check `GetGreenAtRedFirst`, then port the pixel-loop
and remaining colour/noise operations. Keep the Stage58 saved-DNG baseline
and normal Photon captures unchanged until host, JNI and device pixel-parity
checks justify an actual Android integration. Native graph scope is still the
fixed-camera, aligned-RGGB, noise/lens-disabled fixture, not all camera modes.
