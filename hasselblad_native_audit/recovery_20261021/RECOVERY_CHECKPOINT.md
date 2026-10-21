# Hasselblad Photon research recovery checkpoint

**Date:** 2026-10-21  
**Purpose:** Re-establish a durable, verified source/research baseline after loss of unpublished local AWB work.

## Published baseline

- Repository: `mwilliams455/Hasselblad`
- Published parent: `929f523aa02ae5b224be39b9c36cce5975691a10`
- Published parent tree: `0ed5c57223c3e37c2e41140a23475c137345ddf1`
- Restored local source was checked against the complete published tree: 1,257 files.
- The supplied Native1A source archive passed its manifest checks for all 1,206 entries, including 1,092 Android app source files.

This checkpoint does **not** claim that the unpublished Native1C or later AWB source was recovered. Those changes must be reconstructed and revalidated.

## Fresh environment validation

The Android/native research environment was rebuilt from the recorded toolchain:

- JDK 17
- Gradle 8.11.1
- Android SDK 36
- build-tools 35.0.0
- NDK 27.0.12077973
- CMake 3.22.1
- Android API 28 ARM64 original-code comparison runtime

Fresh results after recovery:

- Clean Android debug build completed all 61 tasks.
- Both ARM64 and ARMv7 native targets were built and packaged.
- The retained development signing certificate matches the certificate used by the previously validated Native1C build.
- The portable WB recalibration primitive matched the original ARM64 routine for 10,000/10,000 generated valid comparisons and the retained original routine cases.
- DNG export fixtures and invalid-value guards passed again.

These checks establish that both APK production and original-code comparison are usable again. They do not establish a complete Hasselblad photographic renderer.

## Original firmware inputs

The official X2D II 100C firmware 1.3.16.2 was restored and checked against the recorded extraction identities. The required AWB inputs are available locally for reproducible comparisons, including:

- `libaaa.so` — SHA-256 `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`
- `awb_imx861.bin`
- `awb_imx861.json`
- `awb_config.fbs`

Original firmware binaries and proprietary calibration payloads are intentionally **not** committed to this repository.

## Current application boundary

The published source baseline is Native1A-era source. The previously validated phone installation is Native1C (`0.1-hb-native1c`, version code 27179). Native1C's capture-JSON storage/save-status source changes are not present in this recovered baseline and must be reconstructed before a later phone build supersedes it.

The two central Photon colour calculation files retain the same recorded production identities used by the later Native1C metadata work:

- `Converter.java` SHA-256 `7b80a4532a8623cfe4f41c3c325db6967919bd9e7583eea1cbacd7d9e55be326`
- `Parameters.java` SHA-256 `75b09b643dc3e5e7829daebfa8ab74401a31685924abb08bf410674253e7d64c`

## Publication policy

Reconstructed research will be published as bounded checkpoints only after fresh comparison against the restored original firmware or another explicitly stated evidence boundary.

Do not publish original firmware, extracted vendor libraries/LUT payloads, user photograph pixels/full private sidecars, or generated APKs.

The recovery branch is deliberately separate from `main` while the lost research is being rebuilt.
