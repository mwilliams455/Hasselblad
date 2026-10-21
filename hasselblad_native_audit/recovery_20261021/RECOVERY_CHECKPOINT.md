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
