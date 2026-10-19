# Hasselblad Photon Native1 checkpoint

This is the first standalone Photon checkpoint that executes a recovered Hasselblad white-balance calibration primitive through an Android JNI library. The development screen is reached from **Settings → Hasselblad development check**. It executes the native library and compares actual returned values with ten original-routine oracle vectors and four adapter guard cases.

**WB primitive only; photographic rendering not connected.** The app uses a portable reconstruction of the verified routine; it does not package or load the original Hasselblad `libaaa.so`. Photo white balance, colour and tone still use Photon's existing renderer. No Leica project or M9/M10/Monochrome integration is included.

## App and source identity

| Item | Native1 |
| --- | --- |
| Application ID | `com.mwilliams.hasselbladphoton` |
| Launcher label | Hasselblad Photon (Development) |
| Version name | `0.1-hb-native1` |
| Verified APK version code | `27174` |
| Minimum / target / compile SDK | 26 / 35 / 36 |
| Packaged ABIs | `arm64-v8a`, `armeabi-v7a` |
| Upstream source | [eszdman/PhotonCamera at b2eff821a858033515eb2700e7292befecc95225](https://github.com/eszdman/PhotonCamera/tree/b2eff821a858033515eb2700e7292befecc95225) |
| Upstream archive SHA-256 | `26396340dca501c5161bb843331c50eddab5810e6891bf40b5e5565d8fae5cf8` |

The Java namespace remains upstream's `com.particlesdevs.photoncamera`; the installed package, content-provider authorities and gallery launcher alias use the standalone identity. The version counter retains upstream's build-time increment behavior. The checked-in counter after this successful build is `27175`, which is the next build's version code; `app/build.gradle` sets the effective version name.

## Storage and configuration isolation

RAW files are saved under `DCIM/HasselbladPhoton/Raw`. The standalone root also contains its settings backups and `customCCT.txt`; sensor/device configurations and external tuning files use `DCIM/HasselbladPhoton/Tuning`, and logs use `DCIM/HasselbladPhoton/PhotonLog`. Ordinary JPEGs retain the existing `DCIM/Camera` location. The existing folder chooser therefore asks for **primary DCIM**. A grant for a child folder alone does not cover both destinations and is not accepted as the DCIM grant.

`FileManager` defines the dedicated folder name and relative root. `SimpleStorageHelper` checks canonical grant ancestry and always derives the standalone paths from primary DCIM. It does not append the new name inside whichever subfolder happened to be selected. Existing Photon/Leica files are not read, copied or migrated into this instance.

The own-upstream sensor, device and supported-device network configuration URLs are pinned to the same `b2eff821a858033515eb2700e7292befecc95225` source commit through `SupportedDevice.PINNED_SPECIFICS_BASE_URL`. Existing asset/cache loading behavior remains within this app's separate package storage.

## Capture policy for this checkpoint

`HasselbladDevelopmentPolicy` and the corresponding preference getters enforce PHOTO mode with one RAW input frame. Exposure bracketing, multi-frame stacking, unlimited capture, video, Quad Bayer/max-resolution selection, remosaic, binning, Ultra HDR and HEIC output are disabled for this checkpoint. The visible capture picker contains PHOTO only.

The app prefers the **ordinary advertised RAW stream nearest 12.5 megapixels**. It selects an existing Camera2 stream size and never invents a 12 MP mode. A device that only advertises a larger ordinary RAW stream will retain that supported size. The check report records the requested size separately from the latest delivered RAW buffer's actual dimensions, format, strides and timestamp. These fields contain buffer metadata, not image pixels or a colour-calibration result.

The default save mode is **RAW + JPEG** so the first capture preserves a DNG and produces an SDR JPEG through the existing Photon renderer. The user can still select JPEG-only or RAW-only saving. Photon's internal HDRX preference stays enabled because it selects the RAW processing path; exposure bracketing and HDR output remain disabled by the checkpoint policy.

## Native evidence and limits

The source routine is `scene_awb_result_recalib_unit` at virtual address `0x4a39a0`, 56 bytes, from Hasselblad X2D II 100C firmware `1.3.16.2`:

```
libaaa.so SHA-256
7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba

hb_awb_recalib.c SHA-256
99d56c2ed9a72411d64b732100e016d40660bbc3ee75858dfb3de37bdc1fef5e
```

The primitive independently recalibrates two unsigned Q12 gain slots. They are labelled **gain A / gain B** because the complete upstream channel mapping has not been established. Calibration divisors must be nonzero. The portable adapter rejects input gains above `1,048,575`, avoiding the original routine's 32-bit left-shift overflow. A zero gain with a nonzero calibration divisor is valid. Original return value `89` belongs to the zero-divisor path; adapter guard status `1` is the adapter's own status and does not claim the original library ran.

See [ABI_EVIDENCE.md](ABI_EVIDENCE.md) and [verification.json](verification.json). The combined source/research bundle contains the sibling `hasselblad_native_audit` tree with original ARM64 execution scripts, firmware provenance and the Android 9 Bionic/QEMU comparison. The latter compared the same portable C core against the original routine for 10,000 deterministic valid cases with zero mismatches. This establishes agreement for this bounded primitive, not a complete Hasselblad AWB, HNCS or photographic pipeline.

## Source map

Paths below are relative to the project root.

| Responsibility | Source |
| --- | --- |
| Audited portable core and Android JNI bridge | `app/src/main/cpp/hasselblad/hb_awb_recalib.c`, `hb_awb_recalib.h`, `hb_awb_jni.c` |
| Actual native-vector check and Settings screen | `app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladNativeCheck.java`, `HasselbladDevelopmentActivity.java` |
| Single-frame/SDR policy and advertised-size selection | `app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDevelopmentPolicy.java`, `HasselbladRawSizeSelector.java` |
| Standalone file roots and DCIM grant validation | `app/src/main/java/com/particlesdevs/photoncamera/util/FileManager.java`, `SimpleStorageHelper.java` |
| Pinned own-upstream configuration readers | `app/src/main/java/com/particlesdevs/photoncamera/pro/SupportedDevice.java`, `Specific.java`, `SensorSpecifics.java` |
| Host verification entry point | `development/hasselblad/CheckpointVerification.java` |

## Build environment and native dependency retention

The successful build used:

- Temurin JDK `17.0.20.1+1`;
- Gradle `8.11.1`, Android Gradle Plugin `8.10.1`, Kotlin `2.2.0`;
- Android SDK platform 36 revision 2 and build tools `35.0.0`;
- Android NDK `27.0.12077973` and CMake `3.22.1`.

With those tools installed, set `JAVA_HOME` and `ANDROID_HOME` to their installation directories, then build from the project root:

```sh
./gradlew --no-daemon --max-workers=4 :app:assembleDebug
```

`--offline` can be added when the fixed Maven dependencies and tools are already cached. The local verification used the same Gradle version through a tool-directory wrapper that set the environment variables; it did not require source dependency substitutions.

Four headers downloaded by upstream CMake during the stock baseline build are now retained, unchanged, in `app/src/main/cpp/deps`. Their original notices are preserved. CMake verifies their exact SHA-256 values and fails if a header is missing or changed; it no longer downloads from moving branches during a build. [PINNED_NATIVE_HEADERS.json](PINNED_NATIVE_HEADERS.json) records each retained file's hash, byte count and historical source URL. Those origin URLs are provenance, not mutable build inputs.

The final build ran all 60 tasks successfully. A local build-environment issue retained stale generated R-class and executable DEX/package outputs across separate tool environments. The final build checked 980 reviewed source/build-input hashes, removed all generated app outputs except native CXX intermediates, rebuilt in that same process environment, and checked the actual APK for the new isolated paths and pinned URL. No old external root or moving own-upstream config URL remained in the final DEX. No application dependency or source workaround was introduced for the stale-build issue.

## Verification completed

The host check compiled the exact app JNI bridge and portable C core as a host shared library, then called them from the actual Java check class. [HOST_CHECK_RESULT.txt](HOST_CHECK_RESULT.txt) records all fourteen native vectors passing, eight JNI range rejections (`-1` and `UINT32_MAX + 1` in each argument position), and ten RAW-size selection cases. The latter include invalid arrays, reordered sizes, 12 MP candidates, an only-large-size device, tie handling and dimensions requiring 64-bit area arithmetic.

`CheckpointVerification.java` contains the host test entry point. A host run needs JDK 17 and a C11 compiler. Compile `hb_awb_recalib.c` and `hb_awb_jni.c` with `-fPIC -shared -Wall -Wextra -Werror` and the JDK's `include`/platform JNI include directories; compile the test together with `HasselbladNativeCheck.java` and `HasselbladRawSizeSelector.java`; run with the shared-library directory in `java.library.path`.

The Android build compiled both native ABIs and packaged the check activity. The APK signature, package metadata and native ZIP alignment were verified with Android build tools. The app's real camera and UI have not been exercised on a connected Android device in this environment. Host JNI execution and original-routine Bionic/QEMU execution are distinct from a complete app/device test.

## First device check

1. Install `HasselbladPhoton_Native1_debug.apk` and launch **Hasselblad Photon (Development)**. Its package is separate from stock Photon and Leica builds. The version code permits an update over the earlier standalone baseline. When the existing storage prompt appears, select **DCIM**; the app creates its own `HasselbladPhoton` folder below it.
2. Open **Settings → Hasselblad development check**. The expected result is **14/14 native checks passed**, with the device's actual native ABI in the provenance. A native-loading error or mismatch is displayed as a failure, not converted into a pass.
3. Return to PHOTO, take one capture with the default RAW + JPEG saving, and open the development check again. Copy the report to retain the requested and delivered RAW dimensions. Check that the DNG and SDR JPEG were saved; the reported dimensions determine whether that camera exposes the intended approximately 12 MP ordinary RAW mode.

This build is a development checkpoint. The recovered primitive is deliberately confined to the explicit check screen until sensor/channel calibration and the photographic processing interface have been proven.
