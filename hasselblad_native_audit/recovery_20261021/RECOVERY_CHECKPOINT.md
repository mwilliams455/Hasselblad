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
