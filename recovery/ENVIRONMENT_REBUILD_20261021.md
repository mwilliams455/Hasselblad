# Environment rebuild — 2026-10-21

The Android build and original-firmware comparison environments were reconstructed from the preserved Native1A source and pinned research inputs.

## Fresh checks

- Android Gradle build: PASS, 61/61 tasks
- ARM64 native target: PASS
- ARMv7 native target: PASS
- Original Android runtime loading jobs: 3/3 PASS
- Original WB routine cases: 9/9 PASS
- Portable C vs original ARM64 recalibration: 10,000/10,000 PASS
- Original routine instruction coverage: 14/14
- DNG serialization fixture: 6/6 PASS
- Invalid DNG-level guards: 12/12 rejected as expected
- Representable DNG boundaries: 4/4 accepted
- Signing certificate SHA-256: `255cb09eaddd26a9cc680786e4985372cf24d0e54bb120fc44d48f3273ff3956`

## Toolchain

- JDK 17
- Gradle 8.11.1
- Android Gradle Plugin 8.10.1
- Kotlin 2.2.0
- Android platform 36
- Build tools 35.0.0
- NDK 27.0.12077973
- CMake 3.22.1

The diagnostic build produced from the restored source is Native1A/version code 27177. It is intentionally not a phone upgrade over the installed Native1C/version code 27179.

## Release boundary

Before issuing the next phone APK, restore and validate the Native1C-style capture-evidence workflow: exact RAW/still-result pairing, original Camera2 metadata preservation, capture JSON storage through the granted document-provider path, and visible saved/failed/skipped status.

Full Hasselblad scene AWB remains a separate reconstruction milestone. Passing the small Q12 helper does not establish a scene estimator.
