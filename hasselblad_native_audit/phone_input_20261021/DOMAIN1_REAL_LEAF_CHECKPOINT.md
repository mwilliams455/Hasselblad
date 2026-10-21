# Hasselblad Phone Domain1 — real native temperature-leaf checkpoint

Date: 21 October 2026  
Repository: `mwilliams455/Hasselblad`  
Branch: `recovery/awb-rebuild-20261021`  
Verified source: `493c567327507859ad8ca982dee32c1ff809400a`  
Prior Domain1 source checkpoint: `dafb555bf9faf12537b9970184fd741b601b404f`  

## New result: host real-leaf integration PASSED

The fixed Domain1 C API now compiles and runs against the actual checked-in,
owned/reconstructed `hb_phone_temperature.c`, `hb_temperature.c`,
`hb_user_controls.c` and `hb_scene_optimizer.c`; no mock temperature leaf is
linked to this test library. The ABI and native contracts are unchanged.

- GitHub Actions workflow: `Phone Domain1 real-leaf verification`, run
  `39669724123`, succeeded. [Run](https://github.com/mwilliams455/Hasselblad/actions/runs/39669724123).
- The workflow compiles both O0 and O2 native shared libraries, then compares
  every Domain1 point against direct calls to the **real** temperature leaf for
  two explicit public-safe synthetic camera profiles.
- 1,458 per-point checks in each optimisation build; all expected statuses,
  reason exclusions, valid gains and point order agree. Both builds give
  identical result records for both synthetic profiles. Seven malformed-grid
  cases and one singular-profile case preserve caller output; each result
  repeats deterministically.
- The earlier isolated ASan+UBSan fixture probe succeeds in the same workflow.
- No original firmware is loaded. No HAL WB estimate is used to select a
  candidate. No render-neutral is written, and no photographic pixels are
  changed.

Public source verifier:
`hasselblad_native_audit/phone_input_20261021/domain_tests/verify_phone_domain_real.py`.
The workflow artifact `hb-domain-real-leaf-host` (retention 7 days) contains
`libphone_domain_real_O0.so`, `libphone_domain_real_O2.so`, and
`PHONE_DOMAIN_REAL_PUBLIC_RESULT.json`. Its native SHA-256 values are in the
machine report. The artifact contains only synthetic tests and native binaries,
not private captures or matrices.

## Private original-metadata check PASSED

The binary artifact was downloaded and loaded locally with the *unmodified*
original sensor metadata from the earlier indoor RAW capture (bound by hash).
The evaluated output for the complete 81-by-9 temperature/tint grid was
compared against all three previously saved private acceptance-audit sweeps.
Both the O0 and O2 binaries independently matched the 2,187 saved native
point statuses, exclusions and representable Q12 gain triples with **zero
mismatches**. The three captures share one tested camera calibration model;
this is one physical profile, not three independent calibrations. Detailed
capture identities and domain breakdowns remain private.

The separate local replay script is
`domain_tests/verify_phone_domain_private.py` (source-only, no embedded sensor
coefficients). It accepts `--capture`, `--acceptance-zip`, `--library`,
`--private-report`, `--public-report`. It never changes the capture JSON or DNG,
never fits the HAL estimate, and never selects a photo-rendering WB candidate.

## Boundaries to preserve

**What this checkpoint proves:** The independent Domain1 coverage interface
operates with the reconstructed *real* temperature implementation in x86 Linux
host testing, and agrees with the saved original-phone-input results.

**It does not prove:** Physical illuminant Kelvin/tint correctness, calibrated
neutral target acceptance, original full automatic-controller invocation on the
phone, Android ARM64 execution of Domain1, new APK compatibility, or photographic
HNCS colour rendering. Scene1B remains installed at version 27183 and continues
to use Photon colour. The main GitHub branch remains unchanged.

The existing fixed-81-point scene acceptance ABI is intentionally unchanged.
The new coverage is informational only; excluding points from this grid is
**not** equivalent to an accepted native scene policy. There is no forced
radius increase, no copying of HAL WB into a model, and no second application
of white balance to RAW/JPEG.

## Next task — bounded phone diagnostic build

Implement an explicit domain-coverage diagnostic entrypoint that operates on
verified original Camera2 calibration metadata, with per-point exclusion
reasons, tested grid and provenance. Prefer generating/cache-once per validated
physical camera profile, not a full 729-point sweep in the synchronous shutter
hot path. Keep a clear `render_applied=false` field and isolate from the
photographic RAW-to-linear pipeline. Confirm API/ABI and app JSON on host before
signed APK release. Package with the existing app ID and signer and a version
code greater than 27183, only after a functioning Android build is verified.

Then collect controlled neutral-target evidence under different light sources
and physical cameras/modes to calibrate an actual AWB policy; later integrate
an accepted neutral once into RAW-to-linear and separately implement/verify
HNCS CCM/tone/gamma/3D-LUT rendering.
