# Scene1 diagnostic Android integration — 21 October 2026

## Device validation completed — Scene1B, 21 October 2026

A returned Scene1B (27183) capture proves that the corrected binder and native diagnostic sweep execute on the phone. The original DNG matches its recorded SHA-256 and byte length; sensor/frame/timestamp binding passes. Replaying that untouched DNG through the actual app Java/JNI produces exactly the same diagnostic metadata, policy decisions, counts, gains, neutral and temperature values as the phone, excluding elapsed time. All policies report successful native status. The replay also passes 276 Java/JNI checks and 20 offline binding checks.

The original HAL neutral equals the effective Photon neutral. No experimental candidate was applied to the photograph. The supplied JPEG is a resized copy without EXIF, so its file-level pairing is not independently proven. Exact scene-derived values and timing remain in the private validation JSON; they are not phone calibration constants.

This closes the first on-device diagnostic integration check. No new APK is required for this result. The next boundary is phone neutral-locus/acceptance calibration and policy selection before any rendered WB change. Full automatic profile/initialization and HNCS rendering remain open; a single successful capture does not validate other cameras/modes or sustained performance. The earlier statements that Scene1B was not phone-tested describe its build-time checkpoint.

See [device validation result](SCENE1B_DEVICE_RESULT.json). Private evidence: `Hasselblad_Scene1B_Phone_Validation_PRIVATE_20261021.json`. Source build commit: `c078b1c4149aaa8d61914e9121ce10f8888d41d9`.


## Latest checkpoint: Scene1B RAW capability fix — 21 October 2026

A returned phone capture confirms Scene1 (27182) saved its capture evidence and a hash-matching DNG with proven frame/sensor binding. Its diagnostic sweep was skipped before native execution: the binder treated an out-of-scope `rawBinningFactorUsed` value as a non-Bayer layout. The capture's existing Photon neutral equals the original HAL neutral. The supplied JPEG is resized and has no EXIF, so its file-level pairing is not independently established. Private image/metadata findings are retained outside Git.

Scene1B scopes this flag to cameras advertising both ULTRA_HIGH_RESOLUTION_SENSOR and REMOSAIC_REPROCESSING, as specified by Camera2. Regular RAW cameras use the declared Bayer layout; any out-of-scope flag remains visible in diagnostics. Remosaic without UHR is rejected as inconsistent. UHR+remosaic still requires an explicit false flag, and maximum-resolution mode, app-side binning, crop and other unsupported inputs remain rejected. This changes diagnostics only; no candidate or fallback is applied to the photograph.

The actual app Java/JNI passed 546 host checks across the new and prior capture replays (270 + 276), including 16 capability/flag combinations per replay, 26 rejection cases and 19 native guards per replay. Another 40 offline binding checks passed. The prior capture retains the same policy results. These are host replays, not proof of on-device native execution or photographic calibration.

**APK:** `HasselbladPhoton-Scene1B-27183-debug.apk`, version **0.1-hb-scene1b / 27183**, same package and signing certificate as Scene1/Native1C. SHA256: `a3a407d6f7998ce8816d19ff6049093b3325bd103e1e7fabe1c67dcd86d332e8`. The Android build, manifest, signature, ZIP alignment and packaged fix/JNI call checks pass. All 18 native libraries are byte-identical to Scene1; its existing ARMv7 4KB ELF-alignment limitation is unchanged. `Converter.java` and `Parameters.java` retain their exact hashes. The checked-in counter 27184 is for the next build.

**Next:** install Scene1B over Scene1, obtain one ordinary-light DNG/JPEG/capture JSON with a neutral target, and verify `scene_candidate_diagnostics.status` and its per-policy results on the phone. Dark coloured-light scenes are useful rejection tests but cannot establish neutral-target accuracy. Full phone automatic profile/initialization, calibrated policy selection and HNCS rendering remain open. Main is unchanged. Scene1B has not yet been installed on the phone; earlier no-device-test/Native1C statements below describe historical checkpoints.

See [Scene1B results](SCENE1B_RESULT.json). Private evidence packet: `Hasselblad_Scene1B_Capture_Check_PRIVATE_20261021.zip`. Android contract: https://developer.android.com/reference/android/hardware/camera2/CaptureResult#SENSOR_RAW_BINNING_FACTOR_USED

## Historical Scene1 integration

The restored app builds as **0.1-hb-scene1**, application ID
`com.mwilliams.hasselbladphoton`, version code **27182**. The signer matches
Native1C (27179). The APK is a development upgrade candidate; it has not been
installed or camera-tested in this session. `main` remains unchanged.

## What is connected

- Restored Native1C-style original capture metadata, effective Photon export
  metadata, DNG SHA-256/length, `.capture.json` SAF storage and latest-save UI.
  The recovered patch needed its final newline, correct ImageFormat import,
  public Camera2 APIs and Android JSON checked-exception handling corrected.
- Request targets are recorded at the actual `addTarget`/request-build path.
  Stream identities are recorded when each OutputConfiguration is created.
  The delivering ImageReader surface is retained with the ImageFrame. Metadata
  selection requires matching result/request, physical camera ID, frame number
  and RAW timestamp. It does not infer provenance from whichever camera is
  currently open. Weak maps do not retain closed reader/request lifetimes.
- Before Photon fixes metadata or transforms/packs the buffer, a synchronous
  ARM64 JNI call builds the signed RAW grid once and runs the six previously
  verified candidate policies. It borrows the buffer only during that call.
- JSON records original HAL neutral separately, policy settings, candidate or
  rejection, block counts, CT/tint/residual, elapsed time and provenance.
  No-candidate results have null gains/neutral; earlier shots are not reused.
- The development-check screen shows JSON save status and the number of
  settings that yielded a candidate. The existing WB primitive check remains.

## Explicit diagnostic boundary

This is **not** `hb_run_automatic`, full calibrated Hasselblad AWB, or HNCS.
No original firmware/library/calibration payload is bundled. No HAL neutral
selects the candidate. No candidate is applied to pixels or Camera2 metadata.
`Converter.java` and `Parameters.java` retain their prior exact hashes, so the
existing Photon WB/colour route remains intact. No double WB is introduced.

The sweep uses centre tint 0; green-relative Q12 radii 128/256/512/1024/2048/4096;
neighbor factor 2; minimum 16 retained blocks; Bayer arithmetic brightness
0.005..0.9. These are labelled **test settings**, not a shipping calibration.
A wide setting accepting a scene is not evidence of correct white balance.
The retained native filter includes cross-row linear neighbor links.

Current diagnostic input bounds: Android API31+ provenance and ARM64;
one untouched RAW16 frame; full, tightly packed, even Bayer geometry up to
32 MP; original normal-mode pixel array matches delivered dimensions; no
software binning, remosaic pattern, crop, RAW10 packing or fp16 processing;
equal valid per-site black spans exactly representable in Q16; original A/D65
Camera2 calibration/colour matrices. Dynamic black/white are preferred when
present, otherwise original static levels are explicitly labelled. Unsupported
inputs produce a reason and leave normal photo rendering available. Spatial
shading is not applied in these diagnostic statistics.

## Verification

- Android SDK36, build-tools35, JDK17, Gradle8.11.1, NDK27.0.12077973,
  CMake3.22.1: successful 61-task debug build, both existing app ABIs.
- Actual app Java binder plus actual JNI C wrapper on a desktop JVM with
  `-Xcheck:jni`: **219 checks**, including 26 Java rejection cases, 19 JNI
  rejection cases, original saved-RAW results matching the separately verified
  native API, unchanged RAW/metadata, and candidate/empty/candidate recovery.
- Four checks cover the new offline provenance schema and camera-ID rejection.
- APK manifest/app ID/version, retained certificate, signature and 16KB ZIP
  alignment checked. The packaged scene library is ARM64, has 16KB ELF segments
  and only libc/libm/libdl dependencies. Actual packaged DEX checks are in the
  safe result report.
- Original controller/scene algorithm and sanitizer/ARM64 numerical agreement
  remain the earlier bounded evidence; this checkpoint adds app integration.
  Camera callbacks, physical lens switching, SAF save failures, on-device
  runtime/memory and photographic accuracy still require a real phone.

`verify_jni.py` requires private capture JSON/DNG, host cc, JDK and a JSON-Java
JAR (host fixture only, not an app dependency). Its `ImageFrame` shim contains
only fields; it does not simulate Android camera allocation or storage.
The evidence ZIP holds private logs/derived results, not duplicate Git source.

## First device check

1. Install the separately supplied Scene1 APK as an update. Do not uninstall
   Native1C first; the package and signer are preserved.
2. Use PHOTO, one standard RAW frame near 12.5 MP and RAW+JPEG saving. Keep
   granted DCIM access. This build retains the existing single-frame policy.
3. Capture a neutral target in daylight, then under a warm indoor light. Check
   that the matching DNG, JPEG and `.capture.json` are saved. Open Hasselblad
   development check to inspect the save and diagnostic status.
4. Inspect the new `scene_candidate_diagnostics` section. A skipped/no-candidate
   result is meaningful evidence. Share the matching original trio privately
   for calibration; do not treat a broad accepted candidate as ground truth.

Next: device-test capture/storage and candidate provenance, calibrate acceptance
with controlled neutral-target scenes per physical sensor, then implement the
remaining complete phone automatic profile and separately validate a coherent
single-WB photographic rendering path. Full HNCS pixel rendering remains open.
