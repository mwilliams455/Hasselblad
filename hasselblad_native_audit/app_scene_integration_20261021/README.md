# Scene1 diagnostic Android integration — 21 October 2026

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
