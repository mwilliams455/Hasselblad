# Hasselblad Photon research recovery checkpoint

## Latest checkpoint: Scene1B RAW capability fix — 21 October 2026

A returned phone capture confirms Scene1 (27182) saved its capture evidence and a hash-matching DNG with proven frame/sensor binding. Its diagnostic sweep was skipped before native execution: the binder treated an out-of-scope `rawBinningFactorUsed` value as a non-Bayer layout. The capture's existing Photon neutral equals the original HAL neutral. The supplied JPEG is resized and has no EXIF, so its file-level pairing is not independently established. Private image/metadata findings are retained outside Git.

Scene1B scopes this flag to cameras advertising both ULTRA_HIGH_RESOLUTION_SENSOR and REMOSAIC_REPROCESSING, as specified by Camera2. Regular RAW cameras use the declared Bayer layout; any out-of-scope flag remains visible in diagnostics. Remosaic without UHR is rejected as inconsistent. UHR+remosaic still requires an explicit false flag, and maximum-resolution mode, app-side binning, crop and other unsupported inputs remain rejected. This changes diagnostics only; no candidate or fallback is applied to the photograph.

The actual app Java/JNI passed 546 host checks across the new and prior capture replays (270 + 276), including 16 capability/flag combinations per replay, 26 rejection cases and 19 native guards per replay. Another 40 offline binding checks passed. The prior capture retains the same policy results. These are host replays, not proof of on-device native execution or photographic calibration.

**APK:** `HasselbladPhoton-Scene1B-27183-debug.apk`, version **0.1-hb-scene1b / 27183**, same package and signing certificate as Scene1/Native1C. SHA256: `a3a407d6f7998ce8816d19ff6049093b3325bd103e1e7fabe1c67dcd86d332e8`. The Android build, manifest, signature, ZIP alignment and packaged fix/JNI call checks pass. All 18 native libraries are byte-identical to Scene1; its existing ARMv7 4KB ELF-alignment limitation is unchanged. `Converter.java` and `Parameters.java` retain their exact hashes. The checked-in counter 27184 is for the next build.

**Next:** install Scene1B over Scene1, obtain one ordinary-light DNG/JPEG/capture JSON with a neutral target, and verify `scene_candidate_diagnostics.status` and its per-policy results on the phone. Dark coloured-light scenes are useful rejection tests but cannot establish neutral-target accuracy. Full phone automatic profile/initialization, calibrated policy selection and HNCS rendering remain open. Main is unchanged. Scene1B has not yet been installed on the phone; earlier no-device-test/Native1C statements below describe historical checkpoints.

See [Scene1B results](../app_scene_integration_20261021/SCENE1B_RESULT.json). Private evidence packet: `Hasselblad_Scene1B_Capture_Check_PRIVATE_20261021.zip`. Android contract: https://developer.android.com/reference/android/hardware/camera2/CaptureResult#SENSOR_RAW_BINNING_FACTOR_USED


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


## Latest research continuation: complete post-processing

The owned scene, history, atmosphere and post stages are now reconstructed and compared. Post-processing passed 10,051 direct checks and seven connected synthetic-frame comparisons (211 total connected checks), with zero mismatches. The complete owned post output now feeds original REAWB in the connected harness. This is synthetic original-code agreement, not real phone calibration, full AWB or active REAWB validation.

Resume from [the current runtime README](../awb_original_runtime_20261021/README.md). Source and safe reports remain on the recovery branch. Private runtime data and the evidence package `Hasselblad_Post_Controller_Evidence_PRIVATE_20261021.zip` remain private. `main` and the installed Native1C application are unchanged; no APK was built or installed for this continuation.


## Completion and passive REAWB continuation — 21 October 2026

The recovery branch now adds owned final result copies, outer completion/recovery, shading temperature and three bounded passive REAWB routes in `hb_completion.c/.h`. Fresh `COMPLETION_RESULT.json`: 7,311 checks, zero mismatches, including 512 copy calls, 1,024 shading calls, 768 passive REAWB calls, 512 suffix calls, 192 stateful completion calls, two original prepared failure paths and six owned-only guard checks. The genuine original scene-40 and post-151 paths skip subsequent processing, restore confirmed state and return outer zero. A successful outer status does not establish a fresh result.

`COMPLETION_PIPELINE_RESULT.json`: 267 comparisons, seven synthetic frames, zero mismatches. Owned scene/history/atmosphere/post/passive REAWB → original debug packing with file output disabled → owned shading/completion. Whole contexts and the passive handle match. `completion_entry.S` is only an ABI adapter into unmodified original suffix code; the outer prefix was not exercised or claimed owned. Shading uses a byte primary label, correcting the older bounded-model assumption. Save-before-enable behavior is implemented only when it does not require linked storage.

Private evidence: `Hasselblad_Completion_Evidence_PRIVATE_20261021.zip`; the exact runtime remains in the separate Android28 complete-runtime packet. Public Git contains owned code and safe reports only. Current resume instructions are in the runtime README. Next work is diagnostic packing/no-file user-dump, surrounding AWB prefix/dispatch and preparation/detection. Active REAWB/linked allocations, authentic camera inputs, phone calibration and full HNCS rendering remain outside this checkpoint. Main and Native1C are unchanged; no APK was built or installed.


## Diagnostics and composed downstream continuation — 21 October 2026

Owned `hb_diagnostics.c/.h` now implements diagnostic carry-forward, two-section byte encoding, full/reduced/coarse statistics packing and no-file user-dump. `DIAGNOSTICS_RESULT.json`: 6,554 checks, zero mismatches. Coverage includes 512 encoding cases, 384 no-file helper calls, 1,024 whole diagnostic calls, 64 arithmetic-boundary packing cases, 256 stateful calls and 24 owned-only guard checks. Workspace is caller-owned, separate and at least 3,076 bytes; lengths A ≤ 510, A+B ≤ 1015; dimensions ≤ 64 with matching sample count. Actual file writes and allocator failure are outside the parity claim.

`DIAGNOSTICS_PIPELINE_RESULT.json`: 302 comparisons, seven synthetic frames, zero mismatches. The connected owned chain now includes scene, history, atmosphere, post, passive REAWB, diagnostic packing, shading and completion. In addition to boundary comparisons, one uninterrupted original controller execution from prepared scene entry `0x471f80` through final cleanup matches the complete owned context, REAWB handle and status on every frame. Original initialization, private tables and surrounding preparation/detection remain external; this is not full AWB or active REAWB validation.

Private evidence: `Hasselblad_Diagnostics_Evidence_PRIVATE_20261021.zip`. Code and safe reports are on the recovery branch. Next: outer entry/scheduling/dispatch and remaining user/ROI/sensor/parsing/detection/face dependencies. Final cleanup and no-file diagnostic packing no longer need reconstruction. Real phone statistics/calibration and HNCS rendering still require separate work. Main and Native1C remain unchanged; no APK was built or installed.


## Controller entry and scheduling continuation — 21 October 2026

Owned `hb_run_entry.c/.h` covers the original controller from entry `0x471a38` to before E-ND white-LUT preparation at `0x471e50`: wrapping counters, initialized/busy guards, fixed-result publication, frame cadence, rate gating and E-ND change flags. An explicit return/prepare action distinguishes a completed early return from a request to continue processing.

`RUN_ENTRY_RESULT.json`: 7,419 checks, zero mismatches against 1,303 full original controller calls. The test restores the same initialized state and substitutes owned entry, followed by the unmodified original remainder on ready cases. There are 853 early returns and 450 remainder executions, 144 numeric scheduling cases, 256 consecutive stateful calls and seven synthetic native frames. Complete context, config, REAWB handle and final status match on every case. The original mid-entry state is not independently captured; this is replacement equivalence with the original remainder, not a wholly owned AWB controller or a combined owned entry/downstream run.

Private evidence: `Hasselblad_Run_Entry_Evidence_PRIVATE_20261021.zip`. Next: E-ND white-LUT/user preparation, statistics-difference checking and remaining dispatch/detection. Existing scene-through-completion ownership remains separately verified. Algorithm agreement supports porting, but finished phone colour still requires real sensor statistics/calibration, coherent one-time WB application, colour-rendering work and physical capture validation. Main and Native1C remain unchanged; no APK was built or installed.


## White-reference preparation continuation — 21 October 2026

Owned `hb_white_lut.c/.h` implements sparse CT/R/B/distance expansion, E-ND white-reference interpolation/selection, exact cache flags and restoration of both baseline tables. `WHITE_LUT_RESULT.json`: 11,302 checks, zero mismatches, including 1,024 expansion calls, 1,280 preparation calls (256 stateful), original statuses 30/33 with partial writes, and 36 owned-only guard checks.

`WHITE_LUT_ENTRY_RESULT.json`: 7,611 checks, zero mismatches against 1,335 full original controller calls. Owned entry plus white-LUT preparation precedes original user/remainder processing at `0x471e64`. There are 853 entry early returns, 32 LUT-error returns and 450 continuations. Seven synthetic native frames include three with E-ND enabled. Complete context, config, REAWB handle and status match. The initial three-point active/eight-point baseline fixture stalled the original downstream search; consistent counts resolve it, and the owned API rejects a mismatch before mutation. This is a fixture correction, not a physical camera result.

Private evidence: `Hasselblad_White_LUT_Evidence_PRIVATE_20261021.zip`. This advances the current AWB reconstruction/verification phase. Next: user controls/preparation, statistics-difference checking and remaining dispatch/detection. Phone statistics/calibration, app integration, HNCS/pixel rendering and physical image validation remain subsequent work. The owned prefix and separately owned downstream chain are not yet combined. Main and Native1C remain unchanged; no APK was built or installed.


## User calibration preparation continuation — 21 October 2026

Owned `hb_user_prepare.c/.h` reconstructs the base/E-ND/temperature calibration import prefix through before user address `0x4b1624`, plus calibration lookup/manual LUT refresh and a separately tested mode-switch helper. It preserves stable unsigned-key sorting, Q12 wrap/division, exact-1 request handling, group-loop early stop and partial request consumption on statuses 83/84. Research bounds: two base points, two E-ND groups/two points each, one or two ten-ratio temperature rows and at most 15 manual LUT points.

`USER_PREPARE_RESULT.json`: 5,529 checks, zero mismatches; 384 getter, 256 manual-refresh, 256 base-import, 256 mode-helper calls and 512 complete-user replacement comparisons (128 stateful). Includes 24 owned-only guard checks. `USER_PREPARE_ENTRY_RESULT.json`: 8,187 checks, zero mismatches against 1,431 complete original controller calls. Owned entry/LUT/calibration prefix precedes original user remainder `0x4b1624`, then original outer remainder `0x471e78`. There are 853 entry returns, 32 LUT failures, 72 user failures (48 status 83, 24 status 84) and 474 successful continuations. Seven native-format synthetic frames include three E-ND frames and two calibration submissions.

The new outer continuation exposed a missing saved-canary pointer register in the test adapter; the adapter is corrected. `USER_PREPARE_DOWNSTREAM_REGRESSION.json` revalidates the shared adapter and separately owned scene-through-completion chain: 302 checks/seven synthetic frames, zero mismatches. No original function is patched. Full user processing and a combined wholly owned controller are still incomplete.

Private evidence: `Hasselblad_User_Preparation_Evidence_PRIVATE_20261021.zip`. Next: ancillary user requests at `0x4af328`, manual/CT/CT-tint/gain handlers, statistics-difference checking and remaining dispatch/detection. This continues the AWB reconstruction/verification phase; phone calibration/input mapping, application integration and photographic colour rendering/validation remain subsequent work. Main and Native1C remain unchanged; no APK was built or installed.


## E-ND unit-calibration request continuation — 21 October 2026

Owned `hb_user_e_nd.c/.h` replaces helper `0x4af328` and its E-ND point/temperature lookups (`0x4ac718`, `0x4acc10`). It implements profile matching, reference-temperature normalization, exact arithmetic/truncation and original partial-write/disable behavior. Rejected unit requests consume their pending flag and disable correction, but do not abort user processing. Research bounds are two unit profiles/two groups/eight points and eight temperature rows with one to eight points each.

`USER_E_ND_RESULT.json`: 7,446 checks, zero mismatches; 512 row, 512 temperature, 512 unit-request and 320 full-user replacement calls (64 stateful). Includes 21 owned-only guard checks. Across request cases, 175 acceptances and 550 rejections match, including 499 rejected requests with partial table writes.

`USER_E_ND_ENTRY_RESULT.json`: 8,571 checks, zero mismatches against 1,495 complete original controller calls. The owned entry/LUT/calibration/unit prefix reaches original user remainder `0x4b162c`, then original outer remainder `0x471e78`. There are 853 entry returns, 32 LUT errors, 72 earlier calibration errors and 538 continuations, with 26 accepted and 32 rejected unit requests. Seven native-format synthetic frames include three E-ND-enabled frames and two combined calibration/unit submissions. Remaining active unit application still uses original routines; the separate owned downstream chain is not yet combined with this prefix.

Private evidence: `Hasselblad_User_E_ND_Evidence_PRIVATE_20261021.zip`. Next: manual-sample selection, remaining E-ND gain-update helpers and CT/tint/gain controls, statistics-difference checking and dispatch/detection. Phone input mapping/calibration, app integration and photographic rendering/validation remain subsequent boundaries. Main and Native1C remain unchanged; no APK was built or installed.


## Manual white-balance sample continuation — 21 October 2026

Owned `hb_user_manual.c/.h` implements manual sample selection, golden CT/amount lookups and all three E-ND gain-update helpers. It preserves selection/validity behavior, wrapped Q12 correction order, low-byte interpolation keys, empty-result handling and the original ignored temperature-conversion status followed by output clamps. Existing owned temperature conversion and gain lookups are reused without original-function callbacks.

`USER_MANUAL_RESULT.json`:3,813 checks, zero mismatches;320 golden leaf calls,480 update calls,224 full-user comparisons (32 stateful), including36 owned-only guard checks. `USER_MANUAL_ENTRY_RESULT.json`:8,955 checks, zero mismatches against1,559 full original controller calls. Includes64 manual fixtures and7 native synthetic frames (3 E-ND-enabled); manual selection persists on frames1..6. Complete context/config/REAWB/status match. Owned prefix now reaches original user remainder0x4b16a8, then outer remainder0x471e78; the separately owned downstream chain is still not joined.

Private evidence: `Hasselblad_User_Manual_Evidence_PRIVATE_20261021.zip`. Research bounds and exact semantics are in the runtime README. Next: connect the already-owned mode helper and reconstruct CT/tint/gain/remaining user controls, statistics-difference checking and dispatch/detection. No new APK; main and Native1C unchanged. Phone calibration/input mapping, app integration and photographic rendering/validation remain subsequent work.


## Temperature/tint/direct-gain controls — 21 October 2026

Owned `hb_user_controls.c/.h` adds inverse temperature/tint conversion, manual-result publication/snapshot/recalibration and CT/CT-tint/direct-gain handlers. Existing mode switching is now connected. Exact request consumption, calibration order, wrapping arithmetic and partial writes on failures are preserved. Mode0 CT/tint indexing is explicitly bounded to0..80; unsupported shapes return the research guard status before that handler's mutation.

`USER_CONTROLS_RESULT.json`:6,073 checks, zero mismatches;384 inverse conversions,576 result-helper calls,592 direct control handlers,248 full-user comparisons (48 stateful),24 owned-only guard checks. Outcomes include original statuses81/89/91/92/157. `USER_CONTROLS_ENTRY_RESULT.json`:9,387 checks, zero mismatches against1,631 full original controller calls, with72 added control fixtures and7 synthetic native frames. All context/config/REAWB/status match. The owned prefix reaches original user remainder0x4b16d4, then outer remainder0x471e78. The separately owned downstream chain is still not joined.

Private evidence: `Hasselblad_User_Controls_Evidence_PRIVATE_20261021.zip`. Detailed semantics and research bounds are in the runtime README. Next: remaining user toggles/bounds/fixed-result requests, statistics-difference and dispatch/detection. No new APK; main and Native1C unchanged. Phone calibration/input mapping, app integration and photographic rendering/validation remain subsequent boundaries.


## Complete bounded user-control stage — 21 October 2026

`hb_user_finish.c/.h` implements final toggle, fixed-result and override requests, and `hb_user_process` composes all owned user stages. It preserves pending-flag consumption, rejection flags, raw record copies, wrapped base scaling, dirty-state synchronization and float/integer boundary behavior. Accepted fixed requests require at most two base calibration points; the preceding modules retain their established research bounds. Original diagnostic logging is excluded.

`USER_FINISH_RESULT.json`:2,553 checks, zero mismatches;64 gain-validity helpers,260 tail calls,328 full-user comparisons (64 stateful),8 owned-only guard checks. `USER_FINISH_ENTRY_RESULT.json`:9,771 checks, zero mismatches against1,695 complete original controller calls;810 user calls,104 user errors,706 outer continuations and zero original user-remainder calls. Includes64 new final-request fixtures and7 native-format synthetic frames. All full context/config/passive-REAWB/status comparisons match. Both runs passed initially; successful output directories retain their actual `*_trial` names in the reports.

Private evidence: `Hasselblad_User_Finish_Evidence_PRIVATE_20261021.zip`. The original outer remainder remains0x471e78, and the separately verified downstream chain is still not joined. Next: statistics-difference, dispatch and remaining ROI/sensor/parsing/detection/face dependencies. No new APK; main and Native1C unchanged. Phone calibration/input mapping, app integration and photographic rendering/validation remain subsequent work.


## Statistics-difference and dispatch gate — 21 October 2026

`hb_stat_difference.c/.h` reconstructs frame-change checking, ROI hold timing, periodic/REAWB refresh and diagnostic counter state. `hb_run_dispatch.c/.h` owns suspension, mode selection, automatic refresh/reuse and scratch clearing after the complete owned user stage. Original missing-handle error behavior and wrapped arithmetic are preserved; zero-count numerical evaluation is guarded before mutation. Logging is excluded.

`STAT_DIFFERENCE_RESULT.json`:2,569 checks, zero mismatches,640 original calls,80 stateful calls,8 owned-only guard checks. `STAT_DIFFERENCE_ENTRY_RESULT.json`:10,841 checks, zero mismatches against1,747 full original controller calls. All six dispatch actions covered:699 suspended returns,31 refreshes,8 reuses,8 manual,8 custom and4 error completions. There are59 original downstream continuations and zero original user remainders. Seven native-format synthetic frames remain covered. Complete context/config/handle/status comparisons match.

Private evidence: `Hasselblad_Stat_Difference_Evidence_PRIVATE_20261021.zip`. Next: ROI sync/processing, remaining sensor/parsing/detection/face dependencies and complete mode bodies, then join the separately verified downstream chain. Exact continuation addresses, semantics and bounds are in the runtime README. No new APK; main and Native1C unchanged. Phone calibration/input mapping, app integration and photographic rendering/validation remain subsequent work.


## Detector ROI processing — 21 October 2026

`hb_roi.c/.h` owns six-format ROI selection, clipping/inset/grid construction, publication and reinitialization. Active non-reset lists are bounded to eight records per type and guarded before mutation. Logging is excluded. Original priority, state transitions, float operation order, zoom error225 and reset semantics are preserved.

`ROI_RESULT.json`:1,549 checks, zero mismatches against512 original calls, including72 stateful calls and12 owned-only guard checks. `ROI_ENTRY_RESULT.json`:11,177 checks, zero mismatches against1,795 full original controller calls. The connected prefix performs87 owned ROI calls,12 ROI error completions and107 downstream original continuations. All six detector types exercise both automatic paths; seven synthetic native E2 frames remain covered. ROI synchronization still uses87 explicit original callbacks. There are zero original user remainders.

Private evidence: `Hasselblad_ROI_Evidence_PRIVATE_20261021.zip`. Next: ROI synchronization/homography/profile calculation, then sensor/parsing/detection/face dependencies and full mode bodies, and joining the separately verified downstream chain. Exact boundaries, guards and semantics are in the runtime README. No new APK; main and Native1C unchanged. Phone calibration/input mapping, app integration and photographic rendering/validation remain subsequent work.


## ROI synchronization — 21 October 2026

`hb_roi_sync.c/.h` owns matrix-based coordinate mapping, profile/default calculation and synchronization/publication. Model names/templates stay caller-supplied and private. Research bounds: three matrix records with names terminating within16 bytes, at most six complete config profiles; shape rejection precedes writes. Original pairwise float extrema, crop saturation, wrapped profile differences and stale publication flags are preserved. Logging is excluded.

`ROI_SYNC_RESULT.json`:1,123 checks, zero mismatches against368 original calls,32 stateful calls and18 owned-only guard checks. `ROI_SYNC_ENTRY_RESULT.json`:11,457 checks, zero mismatches against1,835 full original controller calls. Owned sync/ROI each run127 times; zero original sync/user callbacks. Forty added cases cover refresh/reuse, including eight frames with both ROI stages active. Seven synthetic native frames remain covered. There are147 downstream original continuations; the full controller is not yet owned.

Private evidence: `Hasselblad_ROI_Sync_Evidence_PRIVATE_20261021.zip`. Next: sensor adaptation, parsing, detection and face dependencies, then automatic body composition and joining the already-owned downstream chain. Prioritize automatic single RAW for the first useful bounded APK; map phone inputs/calibration and integrate with the app. Manual/custom and active REAWB/linked-storage work remain explicit backlog rather than automatic-only build prerequisites. No new APK; main and Native1C unchanged. Photographic rendering/HNCS validation remains separate.


## Spectral sensor adaptation — 21 October 2026

`hb_sensor.c/.h` owns bounded ten-channel calibration, spectral reconstruction, smoothing, XYZ/temperature, similarity, classifier probabilities, nested adjustment and parameter blending/carry-forward. All original model/calibration data remain private and caller supplied; the public fixtures are synthetic. Supported shapes: two gain rows, three classes,256 support vectors,15 nodes, two similarity destinations, three adjustment records and1..8 rows at each interpolation level. Unsupported shapes reject before writes; original logging is omitted.

`SENSOR_RESULT.json`:992 checks, zero mismatches against242 original calls,48 stateful calls and26 owned-only guard checks. `SENSOR_ENTRY_RESULT.json`:11,793 checks, zero mismatches against1,883 full original controller calls. Owned sensor runs117 times; zero original sensor/user/synchronization callbacks. There are117 explicit original automatic-statistics calls and195 downstream original continuations. Automatic refresh resumes at parsing (`0x471f50`), reuse at post (`0x472294`). Forty-eight new integrated cases force refresh across both automatic modes and24 sensor scenarios. Existing seven native synthetic frames,52 reuse paths and error completions remain compared.

Private evidence: `Hasselblad_Sensor_Evidence_PRIVATE_20261021.zip`. Next: parsing, detection, face, reconcile enabled E-ND automatic statistics, compose automatic body and join the owned downstream chain. Then map real phone statistics/calibration and auxiliary spectral availability, integrate the app, and build the bounded automatic single-RAW APK. Never transplant IMX861 calibration or invent spectral input. Photographic colour/HNCS validation remains separate. No new APK; main and installed Native1C unchanged.


## Parsing and automatic statistics — 21 October 2026

`hb_parsing.c/.h` owns semantic masks,5x5 adjustment, seven-category classification, smoothing and exposure-dependent blending, reusing signed zone geometry. `hb_stat_auto.c` owns complete statistics with E-ND unit/temperature correction, reusing calibration/helpers and the unchanged classification suffix. No original callbacks in either stage; model data stay caller supplied/private.

Fresh comparisons: `PARSING_RESULT.json`484 checks/153 original calls, seven status177 errors, one oversized-grid disable,48 stateful calls,24 guard checks. `STAT_AUTO_RESULT.json`650 checks/209 original calls, unit138/temperature138/both98,48 stateful calls,22 guard checks. `AUTO_PARSING_ENTRY_RESULT.json`12,297 checks/1,955 full original calls. Zero mismatches. Integrated statistics/sensor/parsing189 each, parsing active40/errors4; E-ND unit/temperature13 each. Zero original statistics/sensor/parsing/user/sync callbacks. Downstream267, refresh195/reuse52, seven native synthetic frames,144 scheduling cases,256 stateful entry calls.

Latest mode: `--run-entry --stat-auto-entry`, original detection remainder0x471f60/reuse0x472294. Private evidence: `Hasselblad_Parsing_Auto_Stats_Evidence_PRIVATE_20261021.zip`. Next: detection/face, join owned downstream chain, phone mapping/calibration, app integration and photographic colour/HNCS acceptance. Automatic-statistics E-ND gap is resolved. No APK; main/Native1C unchanged.


## Detection — 21 October 2026

`hb_detect.c/.h` owns region adjustment, confidence smoothing, semantic/spectral blending, outer-zone masks, scheduled detector history, signed category corrections and hysteresis. Original callbacks and model/calibration payloads are absent; data remain private/caller supplied. Shape rejection precedes writes; original status106/131/177/247 partial-write and error behavior is preserved.

`DETECTION_RESULT.json`: 745 checks, zero mismatches; 177 original calls, 64 stateful calls, 36 guard checks. `DETECTION_ENTRY_RESULT.json`: 12,633 checks, zero mismatches against 2,003 full original controller calls; 233 owned detection calls including 40 errors, 237 statistics/sensor/parsing calls each, 295 sync/ROI calls each. Zero original callbacks for those stages or user processing. Added 48 integrated cases; seven native synthetic frames, 144 scheduling cases and 256 stateful calls remain covered. Downstream continuations315; refresh243/reuse52.

Latest mode: `--run-entry --detect-entry`, original face remainder0x471f70, reuse0x472294. Private evidence: `Hasselblad_Detection_Evidence_PRIVATE_20261021.zip`. First direct comparison corrected the semantic maximum rule; invalid controller fixtures were repaired before fresh final runs. Exact bounds, behavior and reproduction instructions are in the runtime README. Next: face, join owned downstream chain, phone mapping/calibration, app integration and photographic colour/HNCS acceptance. No APK; main/Native1C unchanged.


## Face — 21 October 2026

`hb_face.c/.h` owns bounded fractional ROI preparation, face retention, skin-model confidence, candidate rejection, temperature/gain mapping, both face atmosphere corrections, nested confidence/brightness weighting, stability and temporal smoothing/state transitions. Original callbacks and model/calibration payloads are absent; data remain private/caller supplied. Shape rejection precedes mutation; original partial writes, stale values, wrapped arithmetic and errors222/223/225/247 are preserved.

`FACE_RESULT.json`:893 checks, zero mismatches;214 original calls,96 stateful calls,36 guard checks. `FACE_ENTRY_RESULT.json`:12,857 checks, zero mismatches against2,035 full original controller calls;225 owned face calls (32 active, no errors),265 detection calls (40 errors),269 statistics/sensor/parsing each,327 synchronization/ROI each. Zero original callbacks for those stages or user processing. Added32 active integrated face cases. Seven native synthetic frames,144 scheduling cases and256 stateful calls remain covered. Downstream continuations347; refresh275/reuse52.

Latest mode: `--run-entry --face-entry`, original scene remainder0x471f80, reuse0x472294. Private evidence: `Hasselblad_Face_Evidence_PRIVATE_20261021.zip`. Exact bounds and reproduction instructions are in the runtime README. Next: compose the automatic prefix with the separately owned downstream chain, then phone mapping/calibration, app integration and photographic colour/HNCS acceptance. Manual/custom and active REAWB/linked storage remain separate backlog. No APK; main/Native1C unchanged.


## Automatic composition — 21 October 2026

`hb_automatic.c/.h` joins the complete bounded automatic prefix to the owned scene/history/atmosphere/post/passive REAWB/diagnostics/shading/completion chain. Refresh and reuse follow distinct original routes. Native recovery retains the underlying status/provenance in a trace; unsupported stages return failure without success completion, leaving prior writes for the caller to discard. Invalid top-level inputs and initial manual/custom modes reject without mutation. Initialization/native import and model/calibration supply remain external.

`AUTOMATIC_RESULT.json`:24,219 checks, zero mismatches;2,131 full original calls,2,083 full owned automatic calls,427 owned suffix calls, zero original automatic numerical callbacks. Broader harness retains16 manual/custom continuations. Added96 consecutive synthetic frames,32 refresh/64 reuse;100 native error recoveries,240 mode-guard checks,33 unsupported/input checks. All context/config/passive-handle comparisons match. Final capture review corrected the snapshot order; evidence was regenerated from an empty output directory against the exact final source, then source/probe/dump hashes and both sets of saved context pairs were verified.

Latest mode: `--run-entry --automatic-entry`. Private evidence: `Hasselblad_Automatic_Composition_Evidence_PRIVATE_20261021.zip`. Full contract, counts and reproduction are in the runtime README. Next: phone initialization/model/calibration/input adaptation, app integration and bounded automatic single-RAW APK. Manual/custom and active REAWB/linked storage remain separate backlog. Phone colour/HNCS acceptance and auxiliary spectral availability remain open. No APK; main/Native1C unchanged.


## Phone RAW input adapter — 21 October 2026

`phone_input_20261021/hb_phone_raw.c/.h` reuses the owned signed Q16 RAW accumulator and adds per-site white/black normalization, preserved negative/headroom values and flagged Q12 ratios. All four Bayer patterns, aligned crops and padded layouts are supported within32MP. `capture_binding.py` binds original metadata to the physical camera/frame and validates the bounded full-copy DNG. Exported/dynamic/static black sources remain explicit; original HAL neutral/matrices stay separate. No vendor E2, exposure scale, spectral measurement or phone calibration is invented.

`PHONE_RAW_RESULT.json`:32 synthetic frames and3 real-capture black interpretations,35,840 independent block comparisons,21 native rejection cases,19 metadata/identity rejection cases. All12,582,912 real samples accounted for;1,024 ratio-valid blocks per interpretation. Six complete139,296-byte outputs match across host ASan/UBSan and API28 ARM64. LeakSanitizer cannot inspect executor `/proc`; address/undefined checks remain active. Final source hashes recorded. No numeric implementation mismatch; initial oracle/case assumptions were corrected.

Private evidence: `Hasselblad_Phone_RAW_Adapter_Evidence_PRIVATE_20261021.zip`. The original capture and metadata bridge remain in their existing private restore packets. Next: phone-specific initialization/model/calibration, exposure and spatial mapping before calling the composed automatic controller; then restore Native1C diagnostics and integrate the test APK. Current app plumbing remains Native1A-era; no downgrade APK. No APK built/installed; main/Native1C and rendering unchanged.


## Phone temperature model — 21 October 2026

`phone_input_20261021/hb_phone_temperature.c/.h` owns a temperature-only workspace built from original Camera2 matrix products and public isotemperature data, with reciprocal-temperature interpolation. Original HAL and render-owned metadata remain separate. Automatic initialization markers remain unset; no vendor initializer, vendor library or device calibration transplant is used. `temperature_binding.py` validates original sensor provenance, A/D65 anchors and equal site-normalization spans. Coefficient/determinant, CT/tint, gain-cap and inverse-residual guards reject unusable models/results without publishing output.

`PHONE_TEMPERATURE_RESULT.json`:4,131 independent matrix comparisons,4,059 accepted gain/inverse round trips across the actual phone and16 synthetic profiles,72 oracle-confirmed clipped samples,26 native guards per probe plus an explicit cap/non-mutation check and7 metadata guards. Actual phone profile passes all243 CT/tint points. Six18,496-byte outputs match exactly across optimized host, ASan/UBSan and API28 ARM64. Maximum round-trip temperature difference5.08 K is numerical self-consistency, not photographic accuracy. The public table variant is explicitly pinned; no original-firmware parity claim is added. LeakSanitizer remains unavailable; address/undefined checks pass.

Private evidence: `Hasselblad_Phone_Temperature_Evidence_PRIVATE_20261021.zip`. See `phone_input_20261021/TEMPERATURE_MODEL.md` for bounds, provenance and reproduction. Next: full bounded phone automatic profile (scene radii/thresholds, ratio/exposure/spatial mappings, history and recovery initialization), then Native1C diagnostic restoration and app integration. Temperature loci have no fabricated classification radius. HAL neutral interpretation is not a new AWB estimate. No APK built/installed, rendering change or phone-colour/HNCS acceptance claim.


## Phone scene-candidate bridge — 21 October 2026

`phone_input_20261021/hb_phone_scene.c/.h` connects original phone RAW grids and the owned temperature workspace to a bounded ordinary-candidate path. It converts model gains to green=4096, exhaustively classifies the81-point locus, and calls unchanged owned weighting, connected filtering, accumulation and optimizer leaves. Final CT/tint is checked by the phone calibration model. Handles require an explicit experimental policy; no default is selected. Working state is fresh per frame, the full-automatic marker remains unset, and no HAL neutral, firmware initializer, vendor config or spectral/exposure input is used. No-candidate frames clear output; candidates are diagnostic-only.

`PHONE_SCENE_RESULT.json`:192 cases over two actual black-level interpretations and30 synthetic RAW frames;196,608 independent block comparisons;101 candidates and91 no-candidate results;486 normalization checks;16 native guards per probe plus a model rejection. Fifteen24,636-byte results match exactly across optimized host, ASan/UBSan and API28 ARM64/QEMU. Input/metadata are unchanged, candidate→empty→candidate replay is verified. The first build's hex-token spacing and the Python oracle's16-bit sum were corrected before final verification.

At centre tint0 the actual capture yields no classified blocks for test radii128..2048, while4096 admits nearly the whole frame. This is policy sensitivity, not ground-truth calibration. Private sweep/trace data remain in `Hasselblad_Phone_Scene_Candidate_Evidence_PRIVATE_20261021.zip`. See `SCENE_CANDIDATES.md` for bounds, original linear-neighbour filter behavior and reproduction.

Next useful APK work: restore Native1C capture-JSON/save-status behavior and integrate the bounded diagnostic candidate plus explicit policy/failure provenance, preserving original HAL metadata and existing photographic WB ownership. This can collect controlled calibration evidence before the entire automatic phone profile is complete. Full automatic scene/exposure/spatial/history initialization and photographic/HNCS validation remain open. No APK built/installed; no renderer change or production AWB claim.


## Prior checkpoint: Scene1 diagnostic APK — 21 October 2026

The app integration now builds as **0.1-hb-scene1 / versionCode 27182**, preserving `com.mwilliams.hasselbladphoton` and Native1C's signer. Native1C-style capture JSON, SAF save status and original/effective metadata are restored, and the new bounded scene candidate sweep is connected before Photon modifies the frame. It records six explicit test policies, candidates/rejections and camera/frame provenance, without applying any candidate to rendering. Original HAL neutral remains separate. Stream/request identity comes from actual configuration and request construction, not a later currently-open camera lookup.

Fresh checks: successful 61-task Android build; 219 desktop Java/JNI integration checks (26 Java and 19 JNI guards), plus four offline provenance checks. Original RAW and metadata remain unchanged; candidate/empty/candidate resets pass. APK manifest, signature, Native1C certificate match, 16KB ZIP and all packaged ARM64 native ELF alignments pass; packaged DEX contains the actual capture/diagnostic/JNI/save calls. The scene library imports only libc/libm/libdl. APK: `HasselbladPhoton-Scene1-27182-debug.apk`, SHA256 `ae01c67b4e5ae07649adb98f8f3ac3d6b1d84a71c1858bd23d827151c0917403`.

See [app integration details and device steps](../app_scene_integration_20261021/README.md). Private evidence: `Hasselblad_Scene1_App_Integration_Evidence_PRIVATE_20261021.zip`; APK supplied separately. **The APK has not been installed or camera-tested in this session.** Main and installed Native1C remain unchanged. Next is physical-phone capture/SAF/provenance and controlled neutral-target calibration. Full phone automatic initialization/profile, photographic colour accuracy and full HNCS rendering remain open. Older no-APK entries below describe their historical checkpoints.
