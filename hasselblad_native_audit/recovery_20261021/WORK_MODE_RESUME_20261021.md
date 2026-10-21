# Hasselblad Photon — Work Mode Resume Checkpoint (public-safe)

## Device validation completed — Scene1B, 21 October 2026

A returned Scene1B (27183) capture proves that the corrected binder and native diagnostic sweep execute on the phone. The original DNG matches its recorded SHA-256 and byte length; sensor/frame/timestamp binding passes. Replaying that untouched DNG through the actual app Java/JNI produces exactly the same diagnostic metadata, policy decisions, counts, gains, neutral and temperature values as the phone, excluding elapsed time. All policies report successful native status. The replay also passes 276 Java/JNI checks and 20 offline binding checks.

The original HAL neutral equals the effective Photon neutral. No experimental candidate was applied to the photograph. The supplied JPEG is a resized copy without EXIF, so its file-level pairing is not independently proven. Exact scene-derived values and timing remain in the private validation JSON; they are not phone calibration constants.

This closes the first on-device diagnostic integration check. No new APK is required for this result. The next boundary is phone neutral-locus/acceptance calibration and policy selection before any rendered WB change. Full automatic profile/initialization and HNCS rendering remain open; a single successful capture does not validate other cameras/modes or sustained performance. The earlier statements that Scene1B was not phone-tested describe its build-time checkpoint.

See [device validation result](../app_scene_integration_20261021/SCENE1B_DEVICE_RESULT.json). Private evidence: `Hasselblad_Scene1B_Phone_Validation_PRIVATE_20261021.json`. Source build commit: `c078b1c4149aaa8d61914e9121ce10f8888d41d9`.


## Latest checkpoint: Scene1B RAW capability fix — 21 October 2026

A returned phone capture confirms Scene1 (27182) saved its capture evidence and a hash-matching DNG with proven frame/sensor binding. Its diagnostic sweep was skipped before native execution: the binder treated an out-of-scope `rawBinningFactorUsed` value as a non-Bayer layout. The capture's existing Photon neutral equals the original HAL neutral. The supplied JPEG is resized and has no EXIF, so its file-level pairing is not independently established. Private image/metadata findings are retained outside Git.

Scene1B scopes this flag to cameras advertising both ULTRA_HIGH_RESOLUTION_SENSOR and REMOSAIC_REPROCESSING, as specified by Camera2. Regular RAW cameras use the declared Bayer layout; any out-of-scope flag remains visible in diagnostics. Remosaic without UHR is rejected as inconsistent. UHR+remosaic still requires an explicit false flag, and maximum-resolution mode, app-side binning, crop and other unsupported inputs remain rejected. This changes diagnostics only; no candidate or fallback is applied to the photograph.

The actual app Java/JNI passed 546 host checks across the new and prior capture replays (270 + 276), including 16 capability/flag combinations per replay, 26 rejection cases and 19 native guards per replay. Another 40 offline binding checks passed. The prior capture retains the same policy results. These are host replays, not proof of on-device native execution or photographic calibration.

**APK:** `HasselbladPhoton-Scene1B-27183-debug.apk`, version **0.1-hb-scene1b / 27183**, same package and signing certificate as Scene1/Native1C. SHA256: `a3a407d6f7998ce8816d19ff6049093b3325bd103e1e7fabe1c67dcd86d332e8`. The Android build, manifest, signature, ZIP alignment and packaged fix/JNI call checks pass. All 18 native libraries are byte-identical to Scene1; its existing ARMv7 4KB ELF-alignment limitation is unchanged. `Converter.java` and `Parameters.java` retain their exact hashes. The checked-in counter 27184 is for the next build.

**Next:** install Scene1B over Scene1, obtain one ordinary-light DNG/JPEG/capture JSON with a neutral target, and verify `scene_candidate_diagnostics.status` and its per-policy results on the phone. Dark coloured-light scenes are useful rejection tests but cannot establish neutral-target accuracy. Full phone automatic profile/initialization, calibrated policy selection and HNCS rendering remain open. Main is unchanged. Scene1B has not yet been installed on the phone; earlier no-device-test/Native1C statements below describe historical checkpoints.

See [Scene1B results](../app_scene_integration_20261021/SCENE1B_RESULT.json). Private evidence packet: `Hasselblad_Scene1B_Capture_Check_PRIVATE_20261021.zip`. Android contract: https://developer.android.com/reference/android/hardware/camera2/CaptureResult#SENSOR_RAW_BINNING_FACTOR_USED


Date: 21 October 2026

## Prior checkpoint: Scene1 diagnostic APK — 21 October 2026

The app integration now builds as **0.1-hb-scene1 / versionCode 27182**, preserving `com.mwilliams.hasselbladphoton` and Native1C's signer. Native1C-style capture JSON, SAF save status and original/effective metadata are restored, and the new bounded scene candidate sweep is connected before Photon modifies the frame. It records six explicit test policies, candidates/rejections and camera/frame provenance, without applying any candidate to rendering. Original HAL neutral remains separate. Stream/request identity comes from actual configuration and request construction, not a later currently-open camera lookup.

Fresh checks: successful 61-task Android build; 219 desktop Java/JNI integration checks (26 Java and 19 JNI guards), plus four offline provenance checks. Original RAW and metadata remain unchanged; candidate/empty/candidate resets pass. APK manifest, signature, Native1C certificate match, 16KB ZIP and all packaged ARM64 native ELF alignments pass; packaged DEX contains the actual capture/diagnostic/JNI/save calls. The scene library imports only libc/libm/libdl. APK: `HasselbladPhoton-Scene1-27182-debug.apk`, SHA256 `ae01c67b4e5ae07649adb98f8f3ac3d6b1d84a71c1858bd23d827151c0917403`.

See [app integration details and device steps](../app_scene_integration_20261021/README.md). Private evidence: `Hasselblad_Scene1_App_Integration_Evidence_PRIVATE_20261021.zip`; APK supplied separately. **The APK has not been installed or camera-tested in this session.** Main and installed Native1C remain unchanged. Next is physical-phone capture/SAF/provenance and controlled neutral-target calibration. Full phone automatic initialization/profile, photographic colour accuracy and full HNCS rendering remain open. Older no-APK entries below describe their historical checkpoints.

## Historical environment recovery scope

Next task: restore **actual Android 9 / API 28 / ARM64 execution** of the original Hasselblad X2D II 100C AWB library and resume original-vs-owned comparisons, rather than adding synthetic approximations.

## Recovered source/evidence, private binaries withheld

The original X2D II 100C firmware 1.3.16.2 was re-extracted and checked against the historical Native1A manifest:

- Original `.cim` SHA-256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`
- Original `libaaa.so` (7,423,736 bytes) SHA-256: `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`
- 3 companion AWB configuration files matched their original hashes.
- 9 direct Android 28 native dependencies were extracted and verified.
- 28 exported AWB functions matched exact name/address/size; 11 internal addresses contain executable code, but the internal stage names are historical labels, not exported names.
- `scene_awb_result_recalib_unit` at `0x4a39a0`: 56-byte unsigned Q12 gain recalibrator; original zero calibration return `89`, valid `0` (static instruction evidence, not runtime equivalence).

**The private binaries are retained outside this public repository.** User-facing Work handoff and binaries are in the user's private ChatGPT Library; use those sources only with authorization and appropriate Library file access. Do not commit binaries, vendor calibration or private image pixels here.

## Current reconstruction

Portable, host-tested scaffolds/source for bounded result recovery, RAW 32x32 statistics, candidate accumulation, explicit-fixture classification, optimizer caller-side updates and seven-frame comparison are in Rebuild01–05. Latest owned Rebuild05 source checkpoint commit: `0aa24fcf26d2a80e31837f4da69893f19f0d609d`.

**Still missing:** original library execution and full exact optimizer/statistics/history/atmosphere/post AWB numerical equivalence. Previous original-code test counts from the 20 October conversation are historical findings, not newly executed tests. The vendor original scene optimizer is a historical internal mapping at `0x4a8c48` (1,452 bytes). Context is 920,560 bytes, configuration is 1,502,800 bytes, passive REAWB handle is 1,000 bytes.

## Mandatory next sequence

1. Confirm access to private AWB bundle and Android 28 runtime dependencies in the user's Library; validate hashes. No proprietary uploads to GitHub.
2. Set up an ARM64 Android API 28 execution/runtime harness for original `libaaa.so`, resolve dependencies and original initialized state.
3. Execute original recalibration helper and compare it against portable code, including error/status/overflow; record genuinely new original execution cases.
4. Rebuild initialized frame/statistics/scene input, original scene optimizer and caller-side count behaviour.
5. Restore same-execution seven-frame original-versus-owned context + REAWB + status comparisons (opaque pointer identity matters).
6. Continue through historical AWB stages using the mega handoff and conversation research ledger as specifications.
7. After each bounded, fresh original-firmware comparison: immediately commit owned source, harness, test definitions, numeric outcomes and safe reports to `recovery/awb-rebuild-20261021`, then read back verified tree/blobs.

Keep `main` unchanged and maintain installed Native1C (version code 27179) until a genuinely better signed APK is validated. Full HNCS photographic colour rendering, phone calibration, and signed/headroom RAW-to-linear insertion remain separate future tasks.