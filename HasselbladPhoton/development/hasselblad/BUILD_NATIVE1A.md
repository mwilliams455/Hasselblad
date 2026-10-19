# Hasselblad Photon Native1A export correction

Native1A is a narrow follow-up to the Native1 checkpoint described in
[BUILD_NATIVE1.md](BUILD_NATIVE1.md). Its application ID, native primitive,
single-frame/SDR capture policy, advertised RAW-size selection, and standalone
storage/configuration isolation are unchanged.

| Item | Native1A |
| --- | --- |
| Application ID | `com.mwilliams.hasselbladphoton` |
| Version name | `0.1-hb-native1a` |
| APK version code | `27176` |
| APK filename | `HasselbladPhoton_Native1A_debug.apk` |
| Native ABIs | `arm64-v8a`, `armeabi-v7a` |

## Why this update exists

The first user phone test of Native1 passed all 14 native checks on ARM64 and
requested/delivered a 4096 × 3072 RAW16 buffer. Its returned DNG contained a
readable uncompressed CFA strip and the expected one-frame capture description.
The recovered Hasselblad WB primitive still has no connection to photographic
rendering; that test confirms only the bounded JNI routine and its guards.

The returned DNG exposed two inherited export defects:

- WhiteLevel tag 50717 used TIFF RATIONAL. The DNG specification requires SHORT
  or LONG. Native1A uses the retained writer's unsigned LONG API and preserves
  the exact integer level, including the existing 65535 linearization-output
  branch. Values that cannot be represented exactly are rejected through the
  existing native-null / Java export-failure path, without rounding.
- Software used `circleimageview.BuildConfig`, producing `PhotonCamera v-1`.
  Native1A imports the application's BuildConfig and writes
  `Hasselblad Photon 0.1-hb-native1a (27176)` for this build. The app's standard
  BuildConfig generation is enabled so these are its own version constants.

No RAW sample arithmetic, demosaic, colour, tone, exposure or lens calibration
has been changed. The four retained native dependency headers remain unchanged.
The user's original files and the earlier Native1 APK are preserved.

## Writer verification

[DNG_EXPORT_CHECK_RESULT.json](DNG_EXPORT_CHECK_RESULT.json) records six cases
compiled from the actual old and new `dngCreator.cpp` with the retained TIFF
writer. Only Android logging is stubbed for host execution. All image samples
are deterministic synthetic data.

The cases cover uncompressed RAW16 at levels 1023 and 65535, existing
JPEG-compressed RAW16 at both levels, direct packed RAW10, and the existing
10-bit linearization branch whose output WhiteLevel is 65535. Each repaired
file contains a single LONG WhiteLevel with the exact expected value. All
encoded strips match Native1 byte-for-byte, as do all other tag payloads apart
from the necessarily relocated strip offset. Uncompressed RAW16 strips equal
the original sample bytes exactly; both 16-bit modes leave their input buffer
unchanged. The 10-bit modes preserve Native1's existing encoding/packing
behavior and remain disabled by this checkpoint's capture policy.

Twelve invalid-level native calls (NaN, positive/negative infinity, a negative
value, a fractional value, and UINT32_MAX + 1, in both 16-bit and 10-bit modes)
return null, set output size to zero, and leave the input unchanged. Four exact
unsigned LONG boundary values pass the representability check. These guards
establish representability; they do not validate physical sensor black/white
calibration.

The fixture lives in `development/hasselblad/dng_export_check/`. From the project
root, with a C++17 compiler and JDK installed, it can be rerun as follows:

```sh
python3 development/hasselblad/dng_export_check/check_dng_export.py \
  --baseline-source ../hasselblad_device_validation_20261019/pair_audit/native1_source_snapshot/app/src/main/cpp/dngCreator.cpp \
  --work-dir /tmp/hasselblad-native1a-dng-fixtures \
  --report /tmp/hasselblad-native1a-dng-fixtures/result.json \
  --java-home /path/to/jdk17
```

The combined source/validation bundle contains the baseline snapshot at that
sibling path. Fixture image files are synthetic; no user image payload is
needed to reproduce this check. Compressed-payload equality tests the scope of
this metadata change, and does not substitute for an independent codec audit.

## Build and next phone check

Native1A uses the same toolchain and development signing key as Native1. Its
higher version code permits an update over the existing standalone installation.
Build/signature/package evidence and the incremental/full source patches are
provided separately with the APK.

The new writer is verified on the host and compiled for both Android ABIs.
Native1A itself still needs the next phone export to confirm the final on-device
DNG metadata. One new DNG is sufficient for that check: inspect WhiteLevel for
LONG/count 1/value 1023 on the previously tested camera, and Software for the
Native1A app/version string. Other cameras may correctly report a different
integer white level. The 14-vector development check remains available and
unchanged.
