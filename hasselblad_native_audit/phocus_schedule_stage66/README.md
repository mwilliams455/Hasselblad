# Stage66 — scalar `InterpolateRGB` scheduling and plane ownership

**Status: independent bounded HOST scheduler and synthetic plane-wiring parity.
Not a complete independent demosaic. No new phone APK.**

This checkpoint continues from the **native-validated Stage63 ten-component
source** and the Stage64 YCC / Stage65 ColorNoise **host-only candidates**.
It isolates the work scheduling and R/G/B/mask plane ownership of the original
scalar gradient interpolator. The actual gradient evaluation, Bayer estimates,
colour/noise mathematics and outer-frame implementation remain separate.
The current phone baseline remains Stage58 `0.1-hb-rawprep58` / 27197. Normal
capture still runs Photon. No scene-specific colour fitting was done.

## Evidence from original private CPU code (not published)

A read-only symbol-specific static audit of the **locally supplied** Phocus 2
ARM64 library confirmed **21 bounded control-flow fingerprints**:

- The scalar `Interpolate` entry writes 0xFFFF to its flags before virtual
  dispatch. The audited constructor initializes optimized-view false and
  its additional strength field to zero. **Actual graph runtime flags still
  require native execution**: setters, virtual dispatch and alternative
  classes are not proved by a static symbol study.
- The scalar `InterpolateRGB` body tests flag bits 0, 1, 3 and 4 for its
  preparation, green, opposite-colour and green-site colour passes.
- For the audited all-enabled scalar route, phase margins are 4, 6 and 8
  working-domain pixels. The sequence includes smoothing/edge rows, scale
  and initial-green maps, an original-to-green plane copy, two colour-CFA
  green estimates per two-by-two cell, opposite-colour estimates at colour
  CFA sites, then fresh masks and red/blue estimates at green CFA sites.
- The original `ColorNoise` entry separately gates its two documented
  branches using bits 5 and 6. The Stage65 positive-strength branch is not
  implemented; no new claim of its absence at every actual call site is made.

The original executable, instruction listings, private input hashes, and
native register/pixel traces remain **outside the repository**. The public
aggregate report `evidence/stage66/STAGE66_STATIC_SCALAR_CALL_CONTRACT.json`
contains only Boolean observations and bounded scope. Static source
inspection is not Unicorn/original ARM64 execution parity.

## Portable C11 code

- `schedule66.h` / `schedule66.c`: deterministic event sequence for the
  supported scalar working-frame route: source-centred smooth/edge row
  preparation, map prepasses, green-plane copy, R/B CFA green sites,
  opposite-colour sites and the two green-CFA mask/colour sites.
- `wiring66.h` / `wiring66.c`: apply source-pixel plane ownership and mask
  branch behavior to user-provided R/G/B/mask buffers. Functions to generate
  green, blue, red, direction masks and R/B pairs are *callbacks*. The code
  **does not invent or replace** their equations or compute original gradients.
- `test_schedule66.c`, `test_wiring66.c`: standalone sanitizer-friendly tests,
  including source immutability, exact CFA coordinates, zero-mask fallbacks,
  low-16-bit signed narrowing, rejected overlapping buffers, unsupported
  configurations and abort behavior.
- `test_schedule66.py`, `test_wiring66.py`: separate NumPy/Python host oracles
  for full ordered event sequences and complete R/G/B/mask plane storage,
  including untouched borders, row padding and helper-independent mock values.
- `audit_native_schedule66.py`: **prepared, not run** boundary observer for
  the Stage63 private original-CPU harness, measuring original and substituted
  helper call counts and refusing to claim native parity on unsupported sizes.

No original executable code, calibration matrices, proprietary LUTs or private
photo pixels are embedded in these source files. They compile without the
vendor binary; the native audit separately requires the user's local private
Phocus APK and the Stage60–63 original-CPU test harness.

### Explicitly supported configuration

- Aligned RGGB input with two-by-two CFA cells at even/even red origins.
- Working-domain width and height each at least 24 and **multiples of 8**;
  stride is at least width. The native **outer alignment scheduler and
  full-frame edge extension are not independently ported**. Do not extrapolate
  the no-padding rule to arbitrary phone capture resolutions.
- Scalar-class flag state 0xFFFF only. Alternative optimized-class/GPU modes,
  crop phases, other flag combinations and graph mutations are rejected.
- Working arrays disjoint, valid full-frame extent, supplied pixel-kernel
  callbacks and valid haloes. The code owns no allocation, no crop and no
  colour-space transformation.
- Four per-cell green events have the original important R/G/B ordering:
  red colour site; top and left original-green sites; blue colour site.
  Green masks are computed **afresh** in the final pass, never reused from
  red/blue CFA sites. Zero masks bypass opposite-colour helper callbacks.

The schedule model performs no memory writes by itself. The wiring adapter
writes disjoint output planes, first copying source RAW into the green plane
(including stride padding) and then only touching spatially eligible R/G/B and
mask sites. Callback failure propagates without rollback; it never declares
an image successful. A `NULL` event callback invokes only an O(1) count model
and does not render a full-resolution photograph.

## Actual host validation

- `test_schedule66.c` and `test_wiring66.c` pass C11 GCC with warnings as
  errors, AddressSanitizer and UndefinedBehaviorSanitizer.
- `test_schedule66.py`: **56** synthetic domains, **464,648** exact ordered
  event comparisons; 16 unsupported/invalid-contract cases tested. Separate
  count-only parity checks pass. A theoretical 4096×3072 count-only example
  confirms arithmetic range; it **does not render 12MP pixels**.
- `test_wiring66.py`: **46** synthetic fixtures, **846,208** whole-plane
  storage elements checked exactly against a separate Python reference,
  including zero-mask helper bypass and signed-to-uint16 narrowing.
- Python source compilation and the private static audit pass.

These comparisons are **host-to-host synthetic control-flow and buffer
ownership tests**. They do **not** prove native `InterpolateRGB` execution
parity, the original inline directional gradient equations, final RGB16
matching, Android JNI matching, or physical Hasselblad colour equivalence.
The audit fixture does not contain private photographic RGB pixels.

## Reproduce synthetic checks (no original APK needed)

From the `hasselblad_native_audit/phocus_schedule_stage66` folder:

```sh
gcc -std=c11 -O2 -Wall -Wextra -Werror -fno-fast-math \
  -ffp-contract=off -fsanitize=address,undefined -fno-sanitize-recover=all \
  schedule66.c test_schedule66.c -o /tmp/test_schedule66
ASAN_OPTIONS=detect_leaks=0 /tmp/test_schedule66

gcc -std=c11 -O2 -Wall -Wextra -Werror -fno-fast-math \
  -ffp-contract=off -fsanitize=address,undefined -fno-sanitize-recover=all \
  schedule66.c wiring66.c test_wiring66.c -o /tmp/test_wiring66
ASAN_OPTIONS=detect_leaks=0 /tmp/test_wiring66

python3 test_schedule66.py --work /private/stage66-host \
  --safe-receipt /private/stage66-schedule.json --cases 48
python3 test_wiring66.py --work /private/stage66-host \
  --safe-receipt /private/stage66-wiring.json --cases 40
```

The **native** call-boundary observer is prepared, not executed. When
Unicorn, Capstone, pyelftools and the prior original-CPU harness are available:

```sh
python3 hasselblad_native_audit/phocus_schedule_stage66/audit_native_schedule66.py \
  --apk /private/locally_supplied_phocus.apk \
  --work /private/stage66-native \
  --safe-receipt /private/stage66-native-call-boundaries.json --sanitize
```

## Stage67 / pending validation gates

1. Restore the original-CPU runtime, and execute Stage64 direct YCC and
   Stage64 connected eleven-component replacement tests. **Abort on mismatch**.
2. Run Stage65 direct ColorNoise and graph-flag audits; confirm all actual
   graph flags, positive strength and optimized-view routing. Reject
   unsupported branches rather than silently falling back.
3. Run `audit_native_schedule66.py`; validate native call counts, actual
   geometry/stride, CFA scheduling and masks. This does not substitute the
   main `InterpolateRGB` body or claim full parity.
4. Port the **remaining inline** site-gradient and mask computations and
   complete `InterpolateRGB` independently with Stage61–63 helper calls.
   Then execute original-vs-independent final RGB16 checks in connected
   graph fixtures and held-out DNG tile regions, with highlights on/off.
5. Resolve or explicitly restrict native alignment, full-frame edges,
   CFA phase, construction/error semantics, noised-strength paths and GPU;
   cross-compile for Android and compare **exported device pixels**.
6. Only then consider an explicit saved-DNG experimental renderer and a new
   Android APK. Do not replace normal capture or fit the tungsten-room image.

Stage58 SDR single-frame, ~12MP, all supported phones/lenses, no stacking,
HDR, video or premature physical Hasselblad colour-equivalence claims remain
in force.
