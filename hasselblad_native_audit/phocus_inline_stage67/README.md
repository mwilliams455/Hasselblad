# Stage67 — independently reconstructed inline green-site RAW gradients

**Status: PASS bounded original-instruction-listing-model comparisons; original
CPU dynamic/native parity still pending.** This is an independent C11 port of
one previously unported pixel operation, not a complete demosaic or new APK.

Source branch is based on Stage66 (`experimental/phocus-schedule66`), not the
divergent Stage62 research branch. The Stage58 phone APK, Stage56 private
profile, normal Photon capture path and current controlled DNG experiment are
unchanged. No photograph pixels, profile data or scene-specific parameters
are present in this folder.

## What Stage67 establishes

The audited original scalar `InterpolateRGB` loop computes two gradient arrays
at *green* CFA sites. It obtains the first through the separately validated
Stage61 **signed-edge** direction helper. The second is calculated in-line
from **unsigned RAW16** with SIMD arithmetic, and is passed to the original
Stage61 packed direction-mask helper. Substituting the Stage61 signed-edge
algorithm for the second array is wrong: the stencils and code-domain scales
are different.

This stage independently reconstructs the second, unsigned RAW-gradient
operation in `raw_gradient67.c`, with eight directions ordered
`N,E,S,W,NE,SE,SW,NW`. Two original green-site paths use the **same 110-word
ARM64 instruction sequence**; they were independently checked in the private
original APK without publishing instruction words or offsets.

The C version implements each cardinal gradient from two main two-step
absolute differences and four peripheral differences. It preserves two
**separate integer half-sums** before dividing by eight. The diagonals use
four unsigned two-step absolute differences and then divide by eight. All
inputs are ordinary RAW16 codes and no tuning is based on DNG image content.
The synthetic 5×5 regression witness retained in `test_raw_gradient67.c`
produces native-model/C north gradient 1; prematurely merging the half-sums
produces 2. This is an exact integer rounding boundary, not a perceptual
photographic result.

`green_site_mask67.c` composes this new RAW-gradient operation with the
**existing** Stage61 signed-edge gradients and mask helper. It neither
reimplements those proven functions nor uses original executable outputs as
interpolation results. In the full GitHub checkout, compile it with the
canonical `phocus_gradient_stage61/gradient_maps61.c`.

## Completed validations (host, 24 October 2026)

- The private original ARM64 `libcrosssdk.so` was checked byte-for-byte against
  the `lib/arm64-v8a` entry in the locally supplied original Phocus APK. The
  private binary and its hash were not published.
- The two identical original 110-instruction green-site SIMD bodies were
  interpreted using an explicit private ARM64/NEON arithmetic model, with
  nonzero initial-vector poison tests. This does **not** execute original CPU
  instructions under Unicorn/QEMU.
- **5,292** synthetic RAW patches, varied strides 9/17/23/41 and low/high,
  edge, impulse and random codes, tested against **both** original-body listing
  interpretations: **10,584 comparisons / 84,672 exact signed direction codes,
  zero differences**.
- A separately authored Python scalar reference compared **4,800 patches /
  38,400 signed direction codes**, zero differences. Original input storage and
  two output canaries were checked.
- C11 `-Wall -Wextra -Werror` with fast math disabled, AddressSanitizer and
  UndefinedBehaviorSanitizer passed the standalone C regression tests.
- The green-site Stage61+Stage67 mask composition passed **2,000** additional
  synthetic tests with varied threshold floors and strides, under sanitizers.
  In the temporary scratch build, the two canonical Stage61 helper bodies
  were copied only to link the tests. This private copy is **not** committed.

## How to reproduce without original assets

From the repository root:

```sh
dir=hasselblad_native_audit/phocus_inline_stage67

gcc -std=c11 -O2 -Wall -Wextra -Werror -fno-fast-math \
  -ffp-contract=off -fsanitize=address,undefined -fno-sanitize-recover=all \
  "$dir/raw_gradient67.c" "$dir/test_raw_gradient67.c" \
  -o /tmp/hb_test_raw_gradient67
/tmp/hb_test_raw_gradient67

python3 "$dir/test_raw_gradient67.py"

gcc -std=c11 -O2 -Wall -Wextra -Werror -fno-fast-math \
  -ffp-contract=off -fsanitize=undefined -fno-sanitize-recover=all \
  "$dir/raw_gradient67.c" "$dir/green_site_mask67.c" \
  hasselblad_native_audit/phocus_gradient_stage61/gradient_maps61.c \
  "$dir/test_green_site_mask67.c" -lm -o /tmp/hb_test_mask67
/tmp/hb_test_mask67
```

The *prepared, unexecuted* original-CPU boundary audit is
`audit_native_inline67.py`. Once Unicorn 2.x, Capstone 5.x and pyelftools are
available locally, run it against the supplied private APK:

```sh
python3 hasselblad_native_audit/phocus_inline_stage67/audit_native_inline67.py \
  --apk /private/locally_supplied_phocus.apk \
  --work /private/inline67-native-work --sanitize \
  --safe-receipt /private/inline67.json
```

The audit observes the original `GetGradientMask` call operands at both
in-line green-site blocks, compares the original 8-code RAW and signed-edge
gradient operands with independently compiled C, and in substitution mode
**overwrites the original RAW-gradient operand with the independent C
result** before the mask helper. The native inline SIMD instructions have
still executed up to the interception point. The audit must not describe that
as a complete independent pixel loop even if final RGB16 matches.

## Unsupported / next boundary

The separate in-line signed/vector arithmetic feeding `GetGreenAtRedFirst` at
red/blue sites remains original code. So do `InterpolateRGB`'s full orchestration,
remaining pixel operations, original full-frame alignment/outer-frame
scheduling and `ColorNoise` in the connected renderer. Stage64 directional
YCC and Stage65 bounded ColorNoise native parity also remains pending.

Keep the supported scalar, aligned RGGB, even origin, valid 2-cell halo
contract explicit. Original image-edge rules, odd CFA phase, different
capture modes, original CPU full-path parity, Android/JNI device pixels and
physical Hasselblad colour-science equivalence are not established. Do not
push the original Phocus APK, disassemblies, private LUT/profile payloads,
photos, private input hashes or private emulator traces to GitHub or an APK.
