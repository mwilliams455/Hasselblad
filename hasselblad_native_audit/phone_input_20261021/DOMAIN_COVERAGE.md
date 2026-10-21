# Phone temperature/tint diagnostic coverage — 21 October 2026

**Status:** Source-only research checkpoint. The installed Scene1B APK is unchanged and Photon still renders the photographs. This is not a working shipping automatic white-balance profile or a finished HNCS renderer.

## Motivation

The Scene1B phone scene-candidate policy tests 81 samples on a *single tint curve* and rejects the entire curve if any sampled gain is outside its signed 16-bit comparison domain. The latest acceptance audit confirms that a zero-tint sweep is not a two-dimensional temperature/tint calibration and that widening the radius does not establish the correct neutral. Camera2 colour-transform ordering, DNG metadata transport and the declared temperature model's numerical oracle have already been checked. Do not repeat those audits without a relevant code change.

## New bounded API

`hb_phone_domain.h/.c` adds `hb_phone_domain_evaluate`, separate from the existing `hb_phone_scene_create` ABI. Callers supply an explicit integer Kelvin/tint grid containing at most 81 x 9 points. Every requested point is returned, with exact temperature-leaf status and one clear classification:

- Representable (normalised Q12 gain with green=4096, signed scene range).
- Temperature converter clipped.
- Scene signed-gain rejection.
- Adjacent duplicate Q12 knot.

Rejected points have zero published gain values, not silently clipped or accepted values. Unexpected model errors fail the complete call without modifying the output. There is no default policy, HAL WB fit, lens-shading change, semantic classifier, radius adjustment, or render action. Representability is a mathematical statement only: **it is not neutral detection or colour accuracy.**

Generate the grid once per validated physical-camera metadata profile, never per block or on the shutter hot path. Preserve the original 81-point scene ABI until any replacement is explicitly designed and validated.

## Verification

Focused native source tests use `domain_tests/mock_temperature.c` to simulate well-defined clipping, signed rejection, duplicate knots and failure cases; the real temperature leaf is not replaced in the app. The sanitizer smoke probe is `domain_tests/phone_domain_probe.c`.

```sh
cc -std=c11 -O1 -g -Wall -Wextra -Werror -fno-omit-frame-pointer \
  -fsanitize=address,undefined \
  -Ihasselblad_native_audit/phone_input_20261021 \
  hasselblad_native_audit/phone_input_20261021/hb_phone_domain.c \
  hasselblad_native_audit/phone_input_20261021/domain_tests/mock_temperature.c \
  hasselblad_native_audit/phone_input_20261021/domain_tests/phone_domain_probe.c \
  -o /private/phone_domain_probe_asan
ASAN_OPTIONS=detect_leaks=1 /private/phone_domain_probe_asan
```

At this checkpoint, O0 and O2 host runs both passed 729 synthetic point checks, seven invalid-grid cases, nine output-nonmutation cases and deterministic replay. A **private** saved-temperature fixture replay checked 2,187 individual points across three original captures. The isolated ASan/UBSan smoke probe also passed. These verify the coverage representation against known leaf outputs; they do *not* constitute a new real-leaf-linked host/ARM64 run or phone-device benchmark. Full optional Python verifier, run logs and private fixture report are retained separately, never alongside original photo pixels or camera calibration on public GitHub.

## Next boundary

1. Link the new coverage code with the *actual owned* phone temperature implementation in the host and Android ARM64 harness. Compare every reported point against the saved private audit and test unexpected statuses.
2. Add provenance-labelled coverage JSON in a future signed diagnostic APK with `render_applied=false`, keeping sensor/camera/mode metadata binding exact.
3. Use controlled neutral targets in different illumination and modes to calibrate an actual scene policy; never force an answer by widening radii, skipping invalid points in the old ABI or reusing the HAL result as a fitted target.
4. Complete the supported automatic phone profile, integrate an accepted WB neutral **once** into RAW-to-linear, and separately validate Hasselblad HNCS CCM, tone/gamma and 3D-LUT photographic rendering.

The recovery branch is the only intended destination for this work. Keep `main` and the Scene1B 27183 APK unchanged until a meaningful bounded upgrade is device-validated.
