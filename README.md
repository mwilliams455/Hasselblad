# Hasselblad Photon

A standalone PhotonCamera development project investigating a firmware-derived
Hasselblad X2D II colour-processing path on Android phones.

**Current checkpoint: Native1A, `0.1-hb-native1a` (reviewed APK version code
27176).** The app contains a verified portable reconstruction of one X2D II
white-balance recalibration primitive, called through JNI by an explicit
development check. **Photographs currently use Photon's renderer. Complete
Hasselblad photographic colour rendering is still under investigation.**

## What is working

- The Native1 phone report passed **14/14 native checks on arm64-v8a**.
- Camera 2 on the tested phone requested and delivered **4096 × 3072 RAW16**.
- The returned DNG contained a complete **12,582,912-sample RGGB mosaic**.
- Native1A fixes the inherited DNG WhiteLevel TIFF type and Software version
  metadata. Six actual production-writer fixtures passed, preserving the image
  payloads; compiled DEX and native packaging were independently inspected.
- The standalone capture policy uses PHOTO, one RAW input frame and SDR output,
  preferring the advertised standard RAW size closest to 12.5 MP. Actual sizes
  and lens access remain device-dependent; this is not a Xiaomi-only build.

Native1A's new DNG writer still needs one fresh phone export to confirm its tags
on the device. The prior phone result applies to Native1 and the unchanged WB
core, not a new physical-device run of Native1A.

## Repository layout

| Directory | Purpose |
| --- | --- |
| [HasselbladPhoton](HasselbladPhoton/) | Complete Android app, Gradle project, native implementation and retained upstream build dependencies |
| [hasselblad_native_audit](hasselblad_native_audit/) | Firmware provenance, extraction/inspection tools and bounded original-code execution evidence |
| [hasselblad_device_validation_20261019](hasselblad_device_validation_20261019/) | Original phone report, capture metadata/integrity audit and Native1A independent review |
| [build_evidence](build_evidence/) | Reviewed build records, signatures, source inventories and full/incremental patches |
| [tools](tools/) | Reproducible repository import tooling |

Open **HasselbladPhoton/** as the Android Studio project. Its nested
`.github/workflows` files are retained upstream source; active workflows for
this repository are in the repository-root `.github/workflows` directory.

## Build and verify

Read [BUILD_NATIVE1A.md](HasselbladPhoton/development/hasselblad/BUILD_NATIVE1A.md)
for the correction and production-writer fixture, and
[BUILD_NATIVE1.md](HasselbladPhoton/development/hasselblad/BUILD_NATIVE1.md) for the
Android build prerequisites and standalone capture/storage policy.

The recorded toolchain is JDK 17, Gradle 8.11.1, Android Gradle Plugin 8.10.1,
Kotlin 2.2.0, Android SDK 36, build-tools 35.0.0, NDK 27.0.12077973 and CMake
3.22.1. A fresh environment needs the normal Gradle/Maven dependency downloads.
The inherited version counter advances during builds; the checked-in counter
is 27177, following the reviewed APK's code 27176. A new build need not recreate
the identical signed APK bytes or version code.

From the app directory, after provisioning the recorded SDK/NDK/CMake:

```sh
./gradlew --no-daemon --max-workers=4 :app:assembleDebug
```

The DNG writer fixture is independently reproducible with a C++17 compiler and
JDK JNI headers. From **HasselbladPhoton/**:

```sh
python3 development/hasselblad/dng_export_check/check_dng_export.py \
  --baseline-source ../hasselblad_device_validation_20261019/pair_audit/native1_source_snapshot/app/src/main/cpp/dngCreator.cpp \
  --work-dir /tmp/hasselblad-native1a-dng-fixtures \
  --report /tmp/hasselblad-native1a-dng-fixtures/result.json \
  --java-home /path/to/jdk17
```

Historical reports retain the paths and timestamps of the environment in which
they were produced. The main build/fixture/research runners accept relocated
inputs; archived independent inspection scripts with fixed historical paths
are evidence utilities, not repository CI entry points.

## Reviewed APK identity

The Native1A APK was supplied separately with the source/validation bundle;
APK and generated build output files are not stored in Git.

| Item | Value |
| --- | --- |
| App | Hasselblad Photon (Development) |
| Application ID | `com.mwilliams.hasselbladphoton` |
| Version | `0.1-hb-native1a` (27176) |
| File | `HasselbladPhoton_Native1A_debug.apk` |
| Size | 70,736,496 bytes |
| SHA-256 | `1db5da91841b632c3a148a556e7efc403493a558f0a2dfadb880421742cb3c70` |

The app uses the existing public Photon development signing fixture. It is a
development checkpoint, not a production-signed release. The complete ARM64
native set passed the recorded static 16 KB checks; an inherited ARMv7
libarchive alignment exception is documented in the independent review.

## Colour-processing research

The inspected X2D II firmware is **1.3.16.2**. Original-code execution proved
the bounded WB primitive and the preparation/interpolation of main colour
profiles for CCT and sRGB/P3. A separate investigation proved a display-format
LUT decoder and trilinear sampler. The MAIN photographic hardware's packing,
input domain and interpolation remain unresolved. A display sampler must not
be presented as a validated saved-image HNCS renderer.

- [WB/original runtime evidence](hasselblad_native_audit/README.md)
- [Main photographic profile preparation](hasselblad_native_audit/photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.md)
- [MAIN hardware descriptor and display sampler boundary](hasselblad_native_audit/pixel_contract_20261019/PIXEL_CONTRACT_FINDINGS.md)
- [Native1A independent review](build_evidence/native1a_native_review.json)

This work remains separate from the M9, M10-R and Monochrome projects.

## Source provenance and initial import

PhotonCamera and remote device/sensor settings are pinned to
[eszdman/PhotonCamera at b2eff821a858033515eb2700e7292befecc95225](https://github.com/eszdman/PhotonCamera/commit/b2eff821a858033515eb2700e7292befecc95225).
The [full source patch](build_evidence/Native1A_full_source.patch) and
[1,092-file source inventory](build_evidence/native1a_source_changes.json)
identify the reviewed standalone source precisely.

The repository's initial import workflow reconstructs the app from that exact
public upstream archive and reviewed patch, checks the complete file set and
SHA-256 values, and adds the app with a normal fast-forward commit. It does not
execute the app, build tools, extracted firmware or vendor camera libraries.
The import is bounded to the frozen checkpoint and will not overwrite a
different existing app tree. Subsequent development uses ordinary Git changes.

The source-bundle manifest and checkpoint notes in `build_evidence/` describe
the original downloadable checkpoint before this repository sync. Its temporary
packaging utility is not a repository build dependency.

## Included material and licences

This repository contains source code, required public Photon build inputs,
synthetic probes, file hashes and derived research/validation reports. Original
Hasselblad firmware, extracted vendor libraries/runtime, proprietary camera
LUT/calibration payloads, user photograph pixels and generated APKs are excluded.
The firmware acquisition instructions let researchers obtain their own input.

Preserve the [Photon GPL-3.0 licence](HasselbladPhoton/LICENSE), embedded third-party
notices and the separate [research notices](hasselblad_native_audit/THIRD_PARTY_NOTICES.md).
The public upstream static libraries/models, Gradle wrapper and development
keystore are required project inputs; they are distinct from extracted camera
firmware. The research tree retains its AGPL-3.0 and MIT notices as documented.

Independent development project; no affiliation with or endorsement by
Hasselblad is claimed.
