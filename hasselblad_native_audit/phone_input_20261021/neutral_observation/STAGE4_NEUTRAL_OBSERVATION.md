# Hasselblad Photon Stage4 — bounded scene-neutral evidence, no WB selection

**Checkpoint:** 22 October 2026. Source-only native phone-adaptation research. **No new APK, no new original-firmware parity, no photographic render change.** The installed Domain3 build 27184 is still the right phone build. Do not repeat the validated firmware reconstruction, Domain1 coverage, Domain3 grid, DNG-to-frame identity or original Camera2-to-DNG metadata comparisons.

## Why a separate observation layer

The real Domain3 capture established exact temperature/tint *representability*, not a neutral-object classifier. A 2D locus can be close to both a pale subject and other coloured objects. Thus nearest-point distance, a low native inverse residual, a uniform patch, a wide radius, and the HAL neutral cannot be treated as sufficient proof that an illuminant was identified. The Stage4 ABI deliberately contains no result field for photographic WB gain and always publishes `render_permitted=0`, `calibrated_policy=0` and an abstention decision.

## What has been implemented

`neutral_observation/src/hb_phone_neutral_observation.c/.h` is an owned C11, allocation-bounded **diagnostic adaptation**, NOT an exact Hasselblad X2D `E2` layout or an invented vendor AWB stage. It consumes an explicit `hb_ns_domain` and 32×32 RAW-statistic records from a separately verified, same-frame phone adapter. It doesn't load `libaaa.so` or include device/vendor constants. No sensor matrices, private RAW data, shading maps, user image pixel data, or HAL solutions are compiled into the source.

- The independent Domain1 valid/excluded mask is enforced; clipped/signed/duplicate knots never become neighbours or nearest points. Every valid lattice gain is green-normalized Q12 and within the signed scene-gain range.
- Caller-proved physical frame, original single-RAW provenance, nonzero timestamp, exposure time, ISO, and a declared **unshaded versus hypothetical pre-statistics shading basis** are required. Caller must enforce profile-to-physical-camera identity, RAW geometry and metadata before calling. The native model does not invent or verify such identity itself.
- Every 32×32 block is checked against the RAW adapter's reported flags, finite and internally consistent original R/Gr/Gb/B normalized site means and Q12 gain truncation, an explicitly experimental brightness interval, a green-site disagreement check, and the positive signed-16-bit gain comparison range.
- Classification is an **exhaustive nearest valid 2D grid-point observation** with an explicit experimental search radius, never an implicit selection policy.
- Spatial evidence uses true bounded **8-neighbour 32×32 coordinates**, tests neighbour colour-ratio difference, tracks distinct components and their largest support, and reports quadrant coverage and grid-tint edge proximity. It does **not** silently preserve the older recovered linear-neighbour row-wrap behaviour; it is separate adaptation code.
- Outcomes distinguish `ABSTAIN_NO_CANDIDATE_SUPPORT` from `ABSTAIN_UNCALIBRATED`. Even when all 1,024 blocks are near a valid grid point and belong to a uniform component, the algorithm never promotes a neutral into the photo path.
- No temporal history, lens shading application, exposure-based gain correction, semantic detector, certified illuminant/reflectance prior, fallback or actual automatic controller initialization is claimed. Values are diagnostic observations, not image colour.

Every output is unchanged on invalid API input. Successful calls carry explicit empty/new block records with no stale previous candidate. The companion typed `hb_phone_neutral_binding.c/.h` converts the unchanged existing `hb_phone_raw_grid` and `hb_phone_domain_result` into these structures, but only with explicit source frame, physical sensor, original metadata and shading-basis provenance. Its original input/output structs are not modified. This is a host-side typed bridge, NOT an app JNI integration. Do not run this per block, and do not add a new expensive full sweep to the shutter path.

## Test and evidence boundaries

- Real captured RAW: four diagnostic-radius replays using the *unchanged* original verified capture, a 729-point Domain3 grid, and a second Python/NumPy nearest-knot and spatial-component oracle; **4,096 independent block comparisons**. This was a local **host** test, not an Android phone invocation of Stage4.
- **14** malformed native input cases assert complete output non-mutation. **Six** synthetic abstention/rejection scenarios cover a uniform perfectly-lattice-matched coloured target, two uniform distinct synthetic illumination zones, green-site mismatch, signed-gain exclusion, zero valid RAW blocks and row-wrap-connectedness rejection. A separate AddressSanitizer/UndefinedBehaviourSanitizer C probe passes. The new typed RAW/Domain1 bridge has its own standalone positive/rejection/non-mutation C probe, compiled against the **actual** repository headers.
- Tests use explicitly experimental radius values, neighbour radius, brightness range and green-site threshold. **No radius, support count or experimental threshold has been selected as a shipping default**. The real scene and the earlier incomplete indoor and coloured-light captures show why a near-locus score is not a reliable neutral label.
- A private *hypothetical* shading-map replay (original map, bilinear sensor positions before block averaging) reports significantly different boundary neighbourhood and narrow-radius support. This is basis sensitivity only, not a claim the sensor has already supplied corrected RAW or that the photographic renderer needs another correction. Never double-apply shading.
- User photographs, original full Camera2 calibration and scene-specific diagnostics remain in the private evidence bundle/Library. Only owned code, generic tests and public aggregate counts/source hashes belong on GitHub.

## Reproduce synthetic checks

```sh
cc -std=c11 -O1 -g -Wall -Wextra -Werror -Wno-misleading-indentation \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  -Ihasselblad_native_audit/phone_input_20261021/neutral_observation/src \
  hasselblad_native_audit/phone_input_20261021/neutral_observation/src/hb_phone_neutral_observation.c \
  hasselblad_native_audit/phone_input_20261021/neutral_observation/tests/neutral_probe.c \
  -lm -o /private/neutral_probe_sanitized
ASAN_OPTIONS=detect_leaks=1 /private/neutral_probe_sanitized
```

Bridge test (requires real GitHub RAW and Domain1 headers):

```sh
cc -std=c11 -O1 -g -Wall -Wextra -Werror -Wno-misleading-indentation \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  -Ihasselblad_native_audit/phone_input_20261021/neutral_observation/src \
  hasselblad_native_audit/phone_input_20261021/neutral_observation/src/hb_phone_neutral_observation.c \
  hasselblad_native_audit/phone_input_20261021/neutral_observation/src/hb_phone_neutral_binding.c \
  hasselblad_native_audit/phone_input_20261021/neutral_observation/tests/neutral_binding_probe.c \
  -lm -o /private/neutral_binding_probe
ASAN_OPTIONS=detect_leaks=1 /private/neutral_binding_probe
```

Private host RAW replay uses the exact hash-bound capture JSON, DNG and Domain1 JSON, plus `verify_phone_neutral_observation.py` with an independently implemented NumPy oracle. Do not include the original inputs in public test fixtures. Public aggregate: `neutral_observation/STAGE4_PUBLIC_RESULT.json`. The original firmware reconstruction and full controller parity are prior checkpoints; this verifies **new phone adaptation code only**.

## Next decision boundary

1. Verify the real RAW-to-Stage4 adapter and new native ABI with controlled on-phone diagnostics, without capturing additional full 729-point grids or touching the photograph. Preserve sensor, frame and shading-basis provenance.
2. Establish controlled neutral and non-neutral reference scenes under **multiple independently documented illuminants**, repeated exposures and rear physical cameras/modes. Do not fit a policy to this single pale surface, earlier tungsten door or Photon/HAL output. Compare results in both original and declared hypothetical shading bases to resolve spatial calibration semantics.
3. Select bounded camera/mode-specific neutral eligibility and *abstention* policies only after hold-out false-positive tests. Then supply a validated phone automatic-controller profile (initialization, history/recovery, auxiliary-absent spectral route, exposure and spatial mappings). Do not transplant X2D sensor constants.
4. Separately integrate a validated neutral into coherent RAW-to-linear **exactly once**, then continue HNCS CCM/tone/gamma/3D-LUT and photographic comparisons. No HDR or stacking; retain generic device architecture and ordinary single RAW.

The recovery branch is `recovery/awb-rebuild-20261021`. Keep `main` unchanged. No new APK is justified solely by a non-rendering host research test.
