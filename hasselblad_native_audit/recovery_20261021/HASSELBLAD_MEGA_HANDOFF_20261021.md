# Hasselblad Photon — MEGA HANDOFF / RECONSTRUCTION SPECIFICATION

**Prepared:** 21 October 2026  
**Purpose:** Preserve enough of the current ChatGPT conversation, prior handoffs, recovery records, device evidence, firmware identities, AWB reverse-engineering conclusions, build/runtime state, and GitHub state that a fresh session can reconstruct the lost work with minimal rediscovery.

> **Read this first:** This handoff intentionally mixes three classes of information, and they must remain distinct.
>
> 1. **Durably preserved source/evidence** — files that exist in ChatGPT Library or GitHub and can be retrieved again.
> 2. **Conversation-recorded historical conclusions** — technical findings, offsets, state sizes, function behavior, commit hashes, and old verification counts that were produced before the local workspace was lost. These are valuable reconstruction specifications, but are not a substitute for rerunning the implementation against the original firmware.
> 3. **Freshly revalidated recovery results** — build/runtime checks rerun after the workspace loss.
>
> The reconstruction strategy is therefore **chat conclusions → reconstructed code → original-firmware confirmation → immediate GitHub checkpoint**, not “rediscover the entire firmware from zero.”

> **Latest fresh checkpoint — phone scene-candidate bridge:** `phone_input_20261021/hb_phone_scene.c/.h` connects original RAW grids and phone matrices to owned scene weighting/filtering/accumulation/optimization with explicit green-relative gain normalization. This is a diagnostic-only ordinary-candidate route, not the complete automatic controller. Fresh verification:192 cases,196,608 independent block comparisons,101 candidates/91 no-candidate results,16 native guards per probe,15 exact host/sanitizer/ARM64 results. A narrow test policy rejects the saved indoor frame; a broad policy accepts nearly the entire frame, so no shipping profile is selected. See [scene-candidate details](../phone_input_20261021/SCENE_CANDIDATES.md). Next useful step: restore Native1C capture-JSON/save-status behavior and integrate candidate/policy/rejection diagnostics for controlled phone calibration. Full automatic scene/exposure/spatial/history initialization and photographic colour remain open. Private evidence: `Hasselblad_Phone_Scene_Candidate_Evidence_PRIVATE_20261021.zip`. No APK or renderer change.

> **Prior fresh checkpoint — phone temperature model:** `phone_input_20261021/hb_phone_temperature.c/.h` creates an owned temperature-only workspace from original Camera2 `calibrationTransform * colorTransform` anchors and a pinned public isotemperature table. No vendor initializer, private calibration transplant or firmware library is used. Fresh checks:4,131 independent matrix comparisons,4,059 accepted gain/inverse round trips,72 correctly rejected clipped samples,26 native guards per probe,7 metadata guards and six exact host/sanitizer/API28 ARM64 comparisons. Actual phone profile passes all243 CT/tint points. See [temperature model details](../phone_input_20261021/TEMPERATURE_MODEL.md). Full automatic scene/exposure/spatial/history initialization remains open; no automatic selected neutral or APK is claimed. Private evidence: `Hasselblad_Phone_Temperature_Evidence_PRIVATE_20261021.zip`. Next: complete the bounded phone automatic profile, restore Native1C diagnostics and integrate. Main/installed Native1C unchanged.

> **Prior fresh checkpoint — phone RAW input:** `phone_input_20261021/hb_phone_raw.c/.h` derives signed normalized Bayer-block statistics from untouched RAW16, preserving black-level choice, brightness and headroom. Verified on the saved12.6MP Native1C capture using exported/dynamic/static black levels,32 synthetic frames,35,840 independent block comparisons,21 native guards and19 metadata guards. Six Android ARM64/sanitized-host output comparisons match exactly. See [the phone adapter README](../phone_input_20261021/README.md). The automatic controller remains fully composed within its initialized bounded scope (24,219 comparison checks). The phone adapter does not yet initialize/call it: next is phone-specific model/calibration/exposure/spatial mapping, then restored Native1C diagnostics and app integration. Do not transplant IMX861 calibration or fabricate spectral input. Private evidence: `Hasselblad_Phone_RAW_Adapter_Evidence_PRIVATE_20261021.zip`. No APK built or installed; phone colour/HNCS remains unvalidated.

---

## 1. Project mission and hard boundaries

This is the **standalone Hasselblad Photon** project. It is separate from M9, M10-R, Monochrome, Pixel Launcher, and other projects.

The target is a single-frame Android camera path inspired by Hasselblad X2D II 100C firmware, with a firmware-derived AWB decision path, clean RAW-to-linear handling, coherent one-time white-balance application, and eventually a Hasselblad-style photographic colour-rendering path.

Current product policy / user constraints:

- Keep the app standalone first.
- Do not restrict it to Xiaomi. Xiaomi 15 Ultra is the main test device, but the architecture must remain generic.
- Prefer the advertised ordinary RAW stream closest to approximately 12.5 MP.
- Current capture policy: PHOTO, one RAW frame, SDR output.
- No bracketing, stacking, video, maximum-resolution/Quad Bayer path, remosaic, or binning in the first route.
- Preserve original Camera2 metadata separately from any effective processing values.
- Never rewrite source evidence merely to make a comparison pass.
- Do not copy X2D II sensor calibration values into a phone sensor and call that calibration.
- White balance must be applied exactly once with a coherent colour matrix.
- Original Hasselblad firmware, extracted vendor libraries, proprietary LUT/calibration payloads, private photo pixels/full private capture sidecars, Phocus APKs, and generated APKs do **not** belong in GitHub.

The currently installed phone build is **Native1C** and should stay installed until a genuine upgrade is ready.

---

## 2. Current durable source and evidence inventory

### 2.1 ChatGPT Library — important persistent files

These are the known durable file identities at the time of this handoff:

| Item | Library identity / role |
| --- | --- |
| `HasselbladPhoton_Native1A_Source_and_Validation (1).zip` | `libfile_bbf34f3a21748191b5304c7a93f5da1e` — 80,952,170 bytes. Preserved Native1A source/validation baseline. |
| `hasselblad.zip` | `libfile_20a4cdf4b5b8819198e741fda306316b` — Native1C returned capture bundle used for device/metadata validation. |
| `Hasselblad_Photon_Handoff_2026-10-20_AWB_Next.md` | `libfile_e99c176ac93c8191ad579d8a550b696b` — detailed morning Native1C/metadata handoff. |
| `Hasselblad_Recovery_Record_2026-10-20.txt` | `libfile_35dc3fd6e0e081918af857783b959fa1` — 694-line recovery record, source/firmware identities, later checkpoint summary. |
| `Hasselblad_Environment_Checkpoint_2026-10-20.zip` | `libfile_67075bdc1ee88191a63c91a99957d655` — rebuilt environment evidence. |
| `Hasselblad_Conversation_AWB_Research_Ledger_2026-10-21.md` | `libfile_019f30c5f0848191ab6ad940013ed473` — 417-line historical AWB checkpoint ledger extracted from the conversation. |
| `Hasselblad_Metadata_Bridge_Rebuild_2026-10-21.zip` | `libfile_605635aab464819196cb1f841f9418f9` — freshly recreated metadata-bridge checkpoint bundle. SHA-256 of local ZIP: `fbf3c319f6bef2afd1f378ebb1d0dac8aececd03dbe58d89b60f95743d076c8a`. |

Copies of the older handoff also exist in Library. Prefer the identities above.

### 2.2 GitHub repository

Repository: `mwilliams455/Hasselblad`

Published `main` is still:

- commit: `929f523aa02ae5b224be39b9c36cce5975691a10`
- tree: `0ed5c57223c3e37c2e41140a23475c137345ddf1`

`main` has deliberately not been advanced while reconstruction is incomplete.

### 2.3 GitHub write path is working again

The failure that previously blocked synchronization no longer reproduces.

A controlled write test successfully completed:

- blob creation
- `create_tree`
- commit creation
- branch creation
- read-back verification

Temporary test branch:

- `chatgpt-sync-test-20261021-0533`
- test commit: `7603a70608f1beb60445143612db00bef7f71c15`

This test did not modify `main`.

### 2.4 Recovery branches

There are two recovery branches created during this conversation. Treat the second one as the canonical reconstruction branch.

Preliminary notes branch:

- `awb-recovery-20261021`
- known head after environment notes: `6f4e6fd236803aef2830ddb57169f1b89b7ffd47`
- contains `recovery/RECOVERY_STATUS_20261021.md` and `recovery/ENVIRONMENT_REBUILD_20261021.md`

**Canonical reconstruction branch:**

- `recovery/awb-rebuild-20261021`
- baseline recovery commit: `472d5555a8d35994717769c178e9754d7c6fb756`
- conversation research ledger commit: `c4083d9c9fa75050b7ad6280e8ec03170b163ebe`
- ledger blob SHA: `2103ab3a4f5459cab4e1e9a04413d04d14f18efe`

Files already present on the canonical branch:

- `hasselblad_native_audit/recovery_20261021/RECOVERY_CHECKPOINT.md`
- `hasselblad_native_audit/recovery_20261021/RECONSTRUCTION_PLAN.md`
- `hasselblad_native_audit/recovery_20261021/VALIDATION_SUMMARY.json`
- `hasselblad_native_audit/recovery_20261021/CONVERSATION_AWB_RESEARCH_LEDGER.md`

**Rule from now on:** every substantial reconstructed research checkpoint should be committed and synced to `recovery/awb-rebuild-20261021` immediately after fresh verification. No more local-only numerical work.

---

## 3. Application identity and currently validated phone build

Application ID:

`com.mwilliams.hasselbladphoton`

The installed and device-validated build is **Native1C**:

| Item | Value |
| --- | --- |
| Version | `0.1-hb-native1c` |
| Version code | `27179` |
| Previous next source counter | `27180` |
| APK name | `HasselbladPhoton_Native1C_debug.apk` |
| APK size | 70,753,012 bytes |
| APK SHA-256 | `59f54b226d8e5107b9d4a19e860629b84e8464ca0469ea1fd50f4f12e065174e` |
| Signing certificate SHA-256 | `255cb09eaddd26a9cc680786e4985372cf24d0e54bb120fc44d48f3273ff3956` |

Native1C fixed capture JSON storage through the granted Android document-provider folder on API 29+ or existing SAF access. It exposed:

`Settings → Hasselblad development check → Capture JSON`

showing the latest `saved` / `failed` / `skipped` result for the session.

Storage behavior:

- RAW/JSON: `DCIM/HasselbladPhoton/Raw`
- ordinary JPEGs: `DCIM/Camera`
- granted folder must cover primary DCIM
- JSON is a file-manager artifact, not a gallery image

The exact Native1C source commit `f56df58c734b70f6638cd77cd59cdad4bb29cfba` is **not** present in the recovered local Git objects or published GitHub history. Its behavior must be reconstructed from the handoff/conversation when the app source is advanced again.

Do not install a recovered Native1A build over Native1C. The next phone APK should use the same application identity/signing certificate and a version code **greater than 27179**.

---

## 4. Returned Native1C capture — device facts that should not be rediscovered

Persistent input: `hasselblad.zip`, Library `libfile_20a4cdf4b5b8819198e741fda306316b`

ZIP SHA-256:

`a6a7f61d3bff33d43ebdf497673a40e2ae9328776315bb5e3f2b30b9253ddcfc`

Files:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `IMG_20261020_062344.capture.json` | 89,747 | `4b2d29c36fefab63d5ec51d599e21bfdcc1cbfe622767de135e5fabe847b5862` |
| `IMG_20261020_062344.dng` | 25,171,245 | `4a275648d6490ad32c156bedf1abd1d08618e942ca658893d4374ac93e23101a` |
| `IMG_20261020_062344.jpg` | 7,622,718 | `753f2ff16c6b59c69956775f0d62b409471b4999cc34fc77db226abc2200ece6` |

Validated capture facts:

- One 4096×3072 RAW frame.
- 12,582,912 samples.
- `RAW_SENSOR` / format 32.
- row stride 8192, pixel stride 2.
- full copy, no binning.
- RGGB mosaic in a 16-bit container.
- DNG `WhiteLevel` type is TIFF LONG/type 4 with value 1023.
- exported black is 64 per Bayer site.
- original dynamic black is 63.9375 but was not selected for export.
- RAW/still timestamp: `49862904125584` ns.
- frame number: 124.
- opened camera, callback-session camera, and calibration camera are all camera `2`.
- camera `2` is a direct non-logical RAW camera under the recorded capability policy.
- original neutral: `[665/1024, 1, 295/1024]`.
- in this capture the original neutral and post-fix selected neutral are identical.
- DNG sample range: 63–627; none exceeds white.
- ISO 537.
- exposure 0.066654575 s.
- JPEG decodes at 3072×4096.
- the scene is warm indoor light without a known illuminant/colour target; it is not calibration ground truth.
- `calibration_evidence_usable=true` means the metadata is usable for calculation, not that the phone sensor is empirically colour-calibrated.

This one capture is strong evidence for metadata plumbing, not for every lens/device/RAW mode.

---

## 5. Exact Photon metadata bridge — conclusions to preserve

The exact production hashes used for the validated bridge are:

| Source | SHA-256 |
| --- | --- |
| Photon `Converter.java` | `7b80a4532a8623cfe4f41c3c325db6967919bd9e7583eea1cbacd7d9e55be326` |
| Photon `Parameters.java` | `75b09b643dc3e5e7829daebfa8ab74401a31685924abb08bf410674253e7d64c` |
| Owned `camera_linear_adapter.c` | `e8e4279a1f76f6b99b6c731b129b5661821b33d8565290d4e06fc938c2a40e4a` |
| Gson 2.13.2 JAR | `dd0ce1b55a3ed2080cb70f9c655850cda86c206862310009dcb5e5c95265a5e0` |

The bridge executes the unchanged production `Converter.java` through minimal host Android shims and reconstructs the selected original-auto-WB/no-calibration-override path from `Parameters.ReCalcColor`.

Preserve these exact rules:

1. Convert Android rationals using separate float numerator/denominator conversion before division.
2. Preserve row-major matrix storage and `getElement(column,row)` ordering.
3. Normalize **both forward matrices and both colour matrices** with the retained `normalizeFM` calls. Do not “correct” this sequence based on theory.
4. Compute interpolation from the original calibration matrices, normalized colour matrices, and original neutral.
5. The complete native-camera→XYZ-D50 matrix already includes WB; then apply the recorded ProPhoto transforms.
6. Restore exact binary32 values after JSON serialization before comparisons or C handoff.

Validated historical results:

- 57 original input scalars vs effective export: bit-exact, 0 ULP.
- 18 derived export-matrix scalars: bit-exact, 0 ULP.
- real capture interpolation weight: `0.3396311136626453`.
- 10 iterations, converged.
- neutral floor, identity fallback, observed XYZ-sum fallback: none applied.
- 10/10 invalid capture mutations rejected.
- 47/47 unequal synthetic Java checks passed.
- 3/3 CLI checks passed.
- C adapter checks: 15/15 optimized and 15/15 ASan/UBSan.

The synthetic fixture deliberately used unequal/noncommuting calibration/forward/colour pairs to expose skipped normalization, omitted calibration, or mismatched illuminant ordering. Swapping both complete matrix pairs together with their illuminants preserves the final float matrix exactly.

During the current recovery conversation the metadata bridge was recreated again from the preserved source/capture and passed the same principal boundaries. The reconstruction bundle is now durable in Library as:

`Hasselblad_Metadata_Bridge_Rebuild_2026-10-21.zip`

Library ID: `libfile_605635aab464819196cb1f841f9418f9`

Local ZIP SHA-256:

`fbf3c319f6bef2afd1f378ebb1d0dac8aececd03dbe58d89b60f95743d076c8a`

---

## 6. Firmware provenance and known runtime identities

Target firmware:

**Hasselblad X2D II 100C firmware 1.3.16.2**

Original platform/runtime:

- Android 9
- API 28
- ARM64

Pinned original AWB files and recorded SHA-256 identities:

| File | SHA-256 |
| --- | --- |
| `system/lib64/libaaa.so` | `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba` |
| `awb_imx861.bin` | `7fa13044a6c5453b67e4ae11bf8d07828de8e1c02aa915494fe5dad20930d435` |
| `awb/awb_imx861.json` | `df1b47d09ba35062ec61a9c9d9f9a9888b718432890b6453e494f0e5d9e43fea` |
| `awb_config.fbs` | `84ff35c3cf2010b81d29d945ef81a5b87a4d3979b86f13dc814a54812813746e` |

The recovery process also checked the complete firmware extraction against the saved reference across **1,617 files** and both firmware images.

The original vendor files are runtime evidence and must remain outside GitHub.

---

## 7. Known AWB leaf primitive — not a scene estimator

Recovered function:

`scene_awb_result_recalib_unit`

Original address:

`0x4a39a0`

Size:

56 bytes

Behavior in the supported non-overflowing domain:

```text
out = (input << 12) / calibration
```

for two independent unsigned Q12 gain cells, using integer truncation.

Q12 unity = 4096.

The owned adapter rejects zero calibration and overflowing shifts. Those adapter error statuses are not vendor return codes.

Fresh recovery validation re-established:

- 10,000 / 10,000 valid portable-vs-original comparisons.
- nine retained original routine cases passed.
- 14/14 instruction-coverage checks passed.

**Critical boundary:** this helper only recalibrates gains. It does **not** estimate scene illumination and is not itself “Hasselblad AWB.”

Known callers:

- `scene_awb_get_result` call sites `0x465dc8` and `0x465df8`
- `scene_awb_get_recalib_res` call sites `0x474f94`, `0x474fc4`, `0x475000`, `0x475018`

Useful symbol inventory:

| Function | Virtual address | Size |
| --- | --- | ---: |
| `scene_awb_get_result` | `0x465840` | 2744 |
| `scene_awb_get_recalib_res` | `0x474ed0` | 472 |
| `scene_awb_set_calib_info` | `0x473e70` | 440 |
| `scene_awb_lib_init` | `0x46e868` | 5168 |
| `scene_awb_lib_run` | `0x471a38` | 2700 |
| `scene_awb_lib_set_statcfg` | `0x47a1e8` | 392 |
| `scene_awb_stat_calib_proc` | `0x4ad3a0` | 284 |
| `scene_awb_stat_awb_info` | `0x4ad298` | 260 |
| `scene_awb_set_main_spec_sensor_calib_info` | `0x4751d8` | lead only |
| `scene_awb_spec_sensor_param_pass_for_reawb` | `0x4b5d28` | lead only |

Spectral symbol presence alone does not prove that active spectral input is mandatory for the selected X2D configuration.

---

## 8. State sizes and high-value structural facts from the lost AWB work

The following values are conversation-recorded conclusions from the later local checkpoints. They should be treated as reconstruction targets and revalidated as stages are rebuilt.

- AWB context size: **920,560 bytes**.
- AWB config size: **1,502,800 bytes**.
- REAWB persistent handle size: **1,000 bytes**.
- black-body table: **31 rows / 496 bytes**.
- workspace used by the composed suffix/outer route: **3,196,156 bytes**.
- suffix trace size: **972 bytes**.
- completion trace size: **96 bytes**.
- debug scratch size: **3,076 bytes**.

The project repeatedly used **same-execution byte-for-byte comparison** of original and owned state because the original initialized context can contain opaque process pointers. Cross-process whole-context snapshot identity was not claimed when pointer identity was not meaningful.

---

## 9. Full AWB reconstruction chain from the conversation

This section is the core reconstruction specification. The old source is missing, but the conclusions, expected boundaries, and many verification counts remain.

### 9.1 Metadata bridge / pre-AWB phone evidence

**Recorded local commit:** `9a2b8e6cd9b9ecc8f70ad7a1d20a047ec488d3fc`

Scope:

- validated original Native1C capture metadata through unchanged Photon calculations and the owned linear adapter.
- exact matrix/neutral plumbing, not full scene-AWB.

This commit is not on published GitHub, but the research has now been recreated separately as described above.

### 9.2 Original AWB initialization / calibrated locus

**Recorded checkpoint:** `8d92116`

Historical role:

- original AWB initialization path.
- white locus / normalization / initial calibrated configuration.
- authentic calibration-table setup.

Reconstruction need:

- recover this before depending on any later scene stages.
- treat original config/calibration layout as authoritative; do not invent phone mappings yet.

### 9.3 Offline AWB frame/statistics input

**Recorded checkpoint:** `674b571`

Historical role:

- frame/statistics contract.
- signed RAW reference / offline input preparation.
- responsive original AWB execution with justified inputs.

Reconstruction need:

- establish exact upstream statistics meaning, channel order, units, valid ranges and lifecycle.

### 9.4 Native E2 statistics and original AWB pipeline

**Recorded checkpoint:** `d6c9327`

Historical findings:

- E2 statistics path understood as **32×32 / 1024 blocks**.
- brightness information preserved rather than discarded.
- original AWB pipeline could be exercised from these prepared statistics.

Reconstruction target:

- native statistics manager/parser and generic scene input.

### 9.5 Calibration / regular classification

**Recorded checkpoint:** `fa6a996`

Historical role:

- per-block calibration.
- AE preparation.
- regular classification.

This is the dependency immediately before the later weighting/filtering pipeline.

### 9.6 Scene weighting, filtering and accumulation

**Recorded local commit:** `d7f6c48`

Historical conclusions:

- zone/classifier weighting behavior included zone rules that could assign weight to blocks skipped by the ordinary classifier.
- connected-component filtering removed groups of **three blocks or fewer** while preserving original traversal/edge behavior.
- surviving weighted blocks were accumulated into scene candidates.

Historical verification:

- all 920,560 context bytes matched at 28 comparison points: 21 stage checks + seven complete-chain checks.
- 192 weighting cases.
- 192 filtering cases.
- prepared accumulation comparisons.

Historical path:

`hasselblad_native_audit/awb_scene_20261020/`

### 9.7 Scene candidate optimization

**Recorded local commit:** `9a9f7a1c5105bbad0ed2596d4ee375589355614c`

Historical conclusions:

- scene candidate optimizer reconstructed.
- temperature lookup/conversion reconstructed.
- caller-side count updates after optimizer return are part of the real contract and must not be omitted.

Historical verification:

- 256 successful original-reference optimizer cases.
- 512 temperature conversion cases.
- 34 combined-pipeline checks.
- seven-frame full-context comparison at optimizer/caller boundary.

### 9.8 Bounded history path

**Recorded local commit:** `0ca6c2f24ea82f572a3671a53b46906a8552f96a`

Historical conclusions:

- first history reconstruction covered the authentic route where policies reject before active correction.
- helper work included temperature distance, coordinate remapping, interpolation and zone geometry.

Historical verification:

- 256 history comparisons covering 414 active illumination slots.
- 1,024 synthetic scalar comparisons plus authentic-initialization queries.
- 4,640 zone-geometry comparisons.
- seven complete context comparisons after history and seven at atmosphere entry.

### 9.9 Active history correction / policy selection

**Recorded local commit:** `ef32d015d93f8488956c78cc6b7ac2b9989893d4`

Historical conclusions:

- histogram-support ratios.
- active correction interpolation.
- policy selection and publication.
- combined and measured WB could select different policies.
- exact 32-bit wrap/rounding behavior mattered.

Historical verification:

- 784 whole-function fixtures.
- 846 active illumination slots.
- 732 non-identity publication/selection updates.
- whole 920,560-byte context comparisons.

### 9.10 Atmosphere correction

**Recorded local commit:** `557c549520046180436ac993a23c177a474ab3d3`

Historical conclusions:

- ordinary atmosphere correction.
- label-based correction.
- eND correction for the supported mode-zero route.
- signed comparison and rounding details mattered.

Historical verification:

- 481 successful complete-stage comparisons.
- 623 active illumination slots.
- 560 changed coordinate pairs.
- 3,072 ordinary/eND helper comparisons.
- 1,536 label-helper comparisons.
- seven-frame handoff to post processing.

### 9.11 Post candidate preparation

**Recorded local commit:** `842e61279d7931c82769dcb1df55b7ab5ede3a9f`

Historical conclusions:

- ordinary/special illumination selection.
- temporal caches.
- candidate weighting.
- spectral fusion.
- override handling.
- cache copy lengths are not uniform and must be preserved.
- retained weights and special-illumination fallback order mattered.

Historical verification:

- 384 candidate-preparation comparisons.
- 4,608 supporting-helper comparisons.
- seven authentic complete-context candidate-boundary matches.
- seven handoff matches to next AWB stage.

### 9.12 Calibrated CT/tint

**Recorded checkpoint:** `edc1aaf`

Historical conclusions:

- gain→CT/tint conversion.
- calibrated matrix interpolation/inversion.
- eND/remapping paths.
- black-body conversion.
- convergence loop.

Historical verification:

- 512/512 complete CT calculations matched temperature, tint, status, and iteration behavior.
- 5,952 matrix iterations matched.
- 2,560 helper comparisons.
- 30/30 actual CT/tint calls in initialized pipeline.
- ten downstream complete-context comparisons.

### 9.13 Candidate publication / golden gains / history

**Recorded local commit:** `edf4f449183613cec2d5fb39cff73597e3910f01`

Historical conclusions:

- ordered CT/tint publication.
- golden gain scaling.
- candidate/history copies.
- any **nonzero validity byte** allowed publication.
- only exact validity value **1** triggered history copy.
- later errors did not retroactively erase earlier successful publications.

Historical verification:

- 384 prepared publication cases.
- 43 error cases.
- 1,139 golden-gain helper comparisons.
- five complete pipeline state snapshots.

### 9.14 Dual synchronization

**Recorded local commit:** `518b25740e2dde91c3229b65bff3faf9444047a3`

Historical conclusions:

- sync gates.
- sensor CT/tint conversion.
- zone gain adjustment.
- gain blending/clamping.
- red/blue publication.
- outer wrapper could report success after an inner error and partial sensor state could remain.
- authentic five valid reference frames had dual sync disabled by genuine gates.

Historical verification:

- 552 complete calculation/wrapper comparisons.
- 2,624 intermediate helper-call boundaries.
- 1,024 sensor/zone/gain-shift helper comparisons.
- 512 CT/tint→gain comparisons + 26 review edge cases.

### 9.15 Gain validation / light-source selection

**Recorded local commit:** `8037d8861a8283300cc476155d07e295fb5ca1a4`

Historical conclusions:

- six-gain validation.
- auto/manual/clear light-source selection.
- exact score/tie behavior matters.
- manual-label flag interaction matters.
- authentic valid frames actively selected a light source.

Historical verification:

- 384 direct original light-source calls.
- 384 original gain-validation-window executions.
- 256 zone-classification helper comparisons.
- 20 extra edge cases.

### 9.16 Requested-WB override window

**Recorded local commit:** `6904ece665bc052c46935d8310568c45540d890e`

Historical conclusions:

- both requested-WB conversions.
- retain/replace decision.
- gain publication.
- history update.
- override clearing.
- authentic five valid frames skipped override.

Historical verification:

- 192 prepared original-firmware runs.
- 96 skips.
- 34 retain.
- 62 replace.
- optimized/sanitizer + independent reviews.

### 9.17 Smoothing / integer filters

**Recorded local commit:** `4f9a65f237bcdffe4c015a01bf48ea7a42bbda5a`

Historical conclusions:

- smoothing controller.
- two filtered-gain sets.
- persistent transition state.
- integer filter.
- authentic seven-frame sequence reached smoothing on five frames: one initialization + four filtered frames.

Historical verification:

- 768 complete smoothing comparisons.
- 368 integer-filter comparisons.
- five authentic full-pipeline matches at smoothing.

### 9.18 Result CT/tint and gain snapshots

**Recorded local commit:** `7e4a62d95f9c5a6b7b6039c29605a5b84b4660a7`

Historical conclusions:

- four result CT/tint calculations in fixed order.
- raw-gain snapshot.
- later calculation failures preserved earlier writes.

Historical verification:

- 320 complete colour-temperature calls.
- 245 gain-snapshot calls.
- 1,049 calibrated-helper calls.
- five authentic frames reached these stages.

### 9.19 Supported output tail

**Recorded checkpoint:** `2b7b7bc`

Historical conclusions:

- final gain recalibration.
- normalization.
- optional-branch decisions for reference configuration.
- diagnostic publication.
- candidate validation.
- CT clamp to **2000–10000 K**.
- intermediate recalibration error could still result in final successful return after validation.

Historical verification:

- 256 prepared output-tail cases.
- 128 standalone final-validation cases.
- 224 separate original helper calls.
- 33/33 reference-pipeline checks.

### 9.20 Complete supported post controller

**Recorded checkpoint:** `5f2a085`

Historical conclusions:

- composed eight recovered post stages.
- included invalid-candidate recovery.

Historical verification:

- 104 complete original firmware calls.
- full 920,560-byte state + return status.
- eight successive frames carrying persistent state.
- all seven reference frames including two recovery frames.
- 29 owned input/unsupported-feature rejection checks.

### 9.21 Selected-scene estimator suffix

**Recorded checkpoint:** `f717e48`

Historical conclusions:

- composed selected-scene weighting → optimization → history → atmosphere → post.
- preserved cross-stage block-usage counts and handoffs.

Historical verification:

- seven firmware frames matched the entire 920,560-byte state and return status.
- eight completion cases.
- 51 atomic rejection cases.

### 9.22 Passive REAWB continuation

**Recorded local commit:** `96ca17c3a9f81ee559eb66802cba56492dbcfda1`

Historical conclusions:

- three complete **passive** REAWB routes implemented.
- persistent handle is 1,000 bytes.
- disabled REAWB can still save state before checking the enable switch.
- authentic seven-frame controls were recorded as `[0,0,0,1]` and returned success with context/handle unchanged in the passive fixture.
- active linked-history/storage REAWB was **not** implemented.
- handle cloning alone is insufficient for active REAWB because linked storage/history behavior is external to the raw 1,000-byte handle.

Historical verification:

- 96/96 prepared complete original REAWB calls.
- seven-frame comparison across complete context, handle and return status.
- 52/52 integration checks.

### 9.23 Debug, shading, final confirmation and outer recovery

**Recorded local commit:** `328b65f4c811cd81f986f18ea66d41fd6e1b34e9`

Historical scope:

- prepared primary AWB path from first selected weighting boundary through actual original outer-controller return.
- debug backup/restoration.
- diagnostic encryption/statistics packing.
- no-file userdump route.
- shading CT selection.
- final shared cleanup / reference override / result confirmation/recovery.

Important original addresses:

- first weighting getter return / composed entry: `0x4a7d48`
- debug entry: `0x494840`
- debug return: `0x495c14`
- diagnostic encryption: `0x495c20`
- encryption return: `0x495d50`
- userdump entry: `0x493c70`
- userdump return: `0x494044`
- shading entry: `0x4664e8`
- shading return: `0x46679c`
- confirmation helper: `0x4a33a0 → 0x4a3404`
- outer `scene_awb_lib_run`: `0x471a38 → 0x471ae4`

Shared-cleanup conclusions:

- always clears context word at offset `0x174`.
- exact reference request byte value `1` at context `0xd338` triggers reference copy to live and confirmation, then request clear.
- prior status nonzero: confirmed result is restored into live result.
- prior status zero: live result is published to confirmed result.
- a later copy-helper status overwrites the prior status; therefore outer can return `0` even after an earlier error.

Recorded 156-byte result copies:

- live→confirmed: `0xb0c48 → 0xb0d80`
- second live→confirmed: `0xb0ce4 → 0xb0e1c`
- reverse confirmed→live uses the inverse pairings.
- reference→live: `0xd3d8 → 0xb0c48` and `0xd3d8 → 0xb0ce4`
- reference→confirmed: `0xd3d8 → 0xb0d80` and `0xd3d8 → 0xb0e1c`

Shading conclusions:

- shading validity must equal **exactly 1**.
- choose the maximum among seven u16 label ratios.
- later label wins ties.
- label 1/4 uses source `0xf008`.
- other labels can also use `0xf008` if primary label at `0xeff8` equals 3 and count at `0xeffc` is at least 60.
- otherwise shading source is `0xb0b6c`.
- shading output stored at `0xb2164`.

Debug/userdump conclusions:

- diagnostic regions are cleared before repacking.
- debug restores backup route and packs diagnostic sections before optional encryption/no-file userdump.
- caller-owned workspace was used safely.
- recorded limits: `A <= 510`, `A+B <= 1015`, dimensions <= 64, record count = width×height.
- actual file-I/O userdump was not ported; no-file route was the supported implementation.

Historical verification:

- five builds passed: owned optimized, owned ASan/UBSan, original ARM64, suffix optimized, suffix ASan/UBSan.
- 80 original debug calls.
- 84 original shading calls.
- 24 original result-copy helper calls.
- 584 getters.
- 80 allocations/frees.
- 80 transitive userdump cases.
- suffix 12 complete cases, 24 guards, 833 checks.
- authentic seven-frame integration: all seven complete context+handle predictions matched after actual outer return.
- 70 integration checks.
- normal seven-frame final statuses all zero.

Critical recovery witness:

- derived from frame 3.
- seed `0xb0c4c = 0` and `0xd47c = 0`.
- post stage produced status **151**.
- later stages were skipped.
- genuine confirmed→live result copy occurred.
- outer ultimately returned **0**.
- owned detached prediction matched complete context+handle within the same execution.

Cross-process context snapshot identity was **not** claimed because initialization can embed opaque pointers. Same-execution comparison was exact across meaningful bytes.

### 9.24 Scene preparation / no-eligible-scene recovery — last local checkpoint

**Recorded local commit:** `aded05ef2f87402c051dd5746e6c58585bffe2b5`

Historical title:

`Own primary AWB scene preparation and no-eligible recovery`

This was the **last known local checkpoint before the workspace disappeared**.

Historical conclusions:

- entry extended earlier than weighting into scene-controller preparation.
- spectral preparation was mapped for the supported configuration.
- normal route selects an eligible scene and enables it before weighting.
- complete **no eligible scene** route reconstructed.
- original no-eligible witness produced scene status **40**.
- later estimator stages were skipped.
- confirmed result was restored.
- outer final status returned **0**.
- supported normal success route remained bounded to **ordinary illumination 0 with scene 3 as the sole eligible scene**.

Historical verification:

- core five builds passed including ASan/UBSan.
- 80 direct original spectral-preparation calls.
- 32 spectral-preparation calls through controller.
- 32 complete no-eligible-scene controller calls.
- normal seven-frame integration: 82 checks.
- all seven frames matched all 920,560 context bytes, all 1,000 handle bytes, and final status from the earlier entry.
- independent core review: 52 checks.
- independent integration review: 40 checks.
- reviewer deliberately introduced four errors — selected-scene flag, spectral-mask byte, return status, handle byte — and all were detected at expected places.
- separate native recovery test: 26 checks.

Recorded limitation of recovery witness:

- live and confirmed result bytes already agreed in the witness, so the restore branch executed without visibly changing those bytes.
- differing-result semantics were already covered by the earlier copy-helper/outer-completion evidence and reconstructed cases.

Historical checkpoint path:

`hasselblad_native_audit/awb_scene_entry_20261020/`

Recorded next target at the time:

**general ordinary scene-controller loop**, reusing the already verified weighting/filtering/accumulation/optimization/finalization machinery; after that, earlier frame preparation/init.

Still unsupported at this point:

- multiple eligible scenes.
- other ordinary scene types / later illumination modes.
- active spectral processing paths outside the supported configuration.
- active linked-history REAWB.

---

## 10. High-level AWB conclusions that should not be forgotten

These are project-level lessons from the long investigation:

- A successful final AWB return does **not** prove a fresh scene estimate was generated. The outer controller can reuse/restore a confirmed result and still return success.
- Therefore phone integration should track **freshness/provenance** of the selected neutral separately from success status.
- Full scene estimator execution was observed even when valid spectral input was absent; missing/invalid spectral data zeroed spectral contribution in the supported tested route rather than necessarily blocking the estimator.
- The tested E2 route uses 32×32 = 1024 blocks and preserves brightness information.
- X2D II sensor calibration is not phone calibration.
- REAWB persistence is separate state; passive behavior is not evidence that the full active linked-storage path is recreated.
- Inactive optional branches should not block a first supported phone route unless the actual camera configuration uses them.
- Original return/status layering must be reproduced exactly; inner failure and final outer success can coexist.
- Exact integer rounding/wrap behavior matters in several stages and should not be replaced by mathematically “cleaner” arithmetic.

---

## 11. Clean RAW-to-linear work — required for a valid phone integration

The retained Photon equation for interpolated calibration `C`, normalized forward matrix `F`, original neutral `n`, and reference neutral `r = inverse(C) * n` is:

```text
M = F * diag(max(r) / r) * inverse(C)
```

`M` already includes WB.

Native camera RGB:

```text
XYZ = M * RGB
```

If RGB was previously divided by an explicitly known divisor `d`:

```text
XYZ = M * diag(d) * RGB_divided
```

The prior divisor `d` need not be identical to the neutral used to compute the new matrix. Do not apply WB twice.

Why the normal Photon route is not yet a proven clean insertion point:

- `rawF16.normalizeSample` clamps normalized RAW to `[0,1]` and stores half floats.
- Bayer2Float divides by a neutral.
- Bayer2Float applies relative chromatic lens shading.
- Bayer2Float can reconstruct highlights or clamp.
- AMaZE final shader floors negative RGB.
- ABLC applies scene-dependent black/gain correction and a floor.
- ordinary `captureDemosaicLinear` is after ABLC.
- later adaptive exposure, colour, tone and look operations add additional history.

Required phone-side research/integration:

- build a separate path preserving signed values and highlight headroom from RAW normalization through demosaic.
- explicitly declare any previous WB divisor and lens/spatial correction.
- verify real matrix layout and GPU/buffer content with basis/readback checks.
- do not certify a buffer as clean merely because a variable is called “linear” or a tone toggle is off.

The owned adapter historically rejected unknown processing history, clipping, highlight reconstruction, adaptive black/exposure, previous colour/tone/look, etc. History is partly a caller declaration; values alone cannot prove that the route is clean.

---

## 12. What is genuinely new research after AWB reconstruction

Most of the AWB chain is now a **reconstruction problem**, because this conversation preserves the conclusions. The truly unresolved research areas are smaller and clearer.

### 12.1 General ordinary scene-controller loop

Last local checkpoint only supported the successful path where ordinary illumination `0` had scene `3` as the sole eligible scene.

Still needed:

- multiple eligible ordinary scenes.
- exact iteration/selection semantics across them.
- other scene types / later ordinary illumination paths actually relevant to firmware configuration.
- earlier frame preparation and complete lifecycle before scene-entry.

### 12.2 Active REAWB

Passive REAWB is well specified by the conversation.

Still unresolved:

- active linked-history/storage route.
- exact external persistence semantics beyond the 1,000-byte handle.

This may be optional for the first phone route if authentic configuration does not engage it, but it remains incomplete firmware coverage.

### 12.3 Phone sensor calibration and estimator-input mapping

Need to define, per physical phone camera:

- how Camera2 RAW/statistics map into the estimator’s expected calibrated quantities.
- which per-unit calibration values can be measured/derived legitimately.
- whether spectral inputs are optional/zeroed or need a phone-side substitute for a particular mode.
- exact selected-neutral provenance/fallback logging.

Do not substitute X2D IMX861 calibration into another sensor.

### 12.4 Hasselblad photographic rendering / HNCS path

Substantial research remains after AWB.

Already recovered/proved historically:

- MAIN CCM coefficient preparation.
- gamma-coordinate primitive.
- MAIN LUT/gamma register-write behavior.
- a separate display-format LUT decoder/trilinear sampler.

Still unresolved for the saved-photo MAIN path:

- exact per-pixel input domain / conversion into the photographic hardware.
- exact CCM per-pixel equation and numeric order.
- gamma evaluation, clipping and rounding/conversion details.
- MAIN 3D LUT component layout.
- exact LUT interpolation/rounding behavior.
- end-to-end composition/order of matrix, gamma and LUT for saved images.

The display sampler is **not** proof of the photographic HNCS renderer.

Phocus Android `libcrosssdk.so`/colour-LUT exports remain a software lead, not proved equivalence to the X2D saved-photo pipeline.

### 12.5 Android photographic integration/validation

After the numerical path is ready:

- prove actual Android insertion point.
- prove preview and still use the intended selected WB state.
- prove one-time WB.
- validate physical-camera/lens-specific metadata/calibration handling.
- compare identical RAW offline first.
- then validate saved photographs.

---

## 13. Current build environment / fresh recovery status

A clean Android build environment was reconstructed and used successfully during recovery.

Recorded toolchain:

- JDK 17
- Gradle 8.11.1
- Android Gradle Plugin 8.10.1
- Kotlin 2.2.0
- Android SDK 36
- build-tools 35.0.0
- NDK 27.0.12077973
- CMake 3.22.1

Fresh recovery results:

- Android debug build: all **61** build tasks completed.
- ARM64 target built and packaged.
- ARMv7 target built and packaged.
- signing certificate matches the validated Native1C certificate.
- original Android runtime loading worked.
- 10,000/10,000 portable-vs-original WB recalibration comparisons passed.
- DNG writer checks passed again, including serialization and invalid-value guards.

The clean rebuilt APK was still Native1A-era source/version code 27177 and was intentionally **not** installed because Native1C 27179 remains the better phone baseline.

Environment-local convenience paths may disappear after a reset. The durable environment record is in Library as `Hasselblad_Environment_Checkpoint_2026-10-20.zip`.

---

## 14. GitHub publication strategy from now on

Canonical branch:

`recovery/awb-rebuild-20261021`

Workflow for every reconstructed numerical stage:

1. Read this handoff + conversation ledger first.
2. Reconstruct the stage from the recorded algorithm/ABI conclusions.
3. Use the restored original firmware only to answer remaining ambiguities and to verify equivalence.
4. Run optimized + sanitizer checks where meaningful.
5. Run original ARM64 comparison.
6. Record exact firmware/source hashes used.
7. Save source, test harness, findings and execution summary.
8. Commit locally.
9. Immediately publish the complete bounded checkpoint to `recovery/awb-rebuild-20261021`.
10. Read the GitHub version back and verify its commit/tree/blob identities.
11. Only then continue to the next stage.

Do not wait for another giant end-of-day synchronization.

Do not modify `main` until the reconstructed chain is coherent enough for review.

---

## 15. Reconstruction priority — fastest path back to productive development

The most efficient order is not to redo reverse engineering in historical order unless a dependency is actually missing.

### Phase A — restore the minimum dependable foundation

- Native1A/published source baseline.
- Native1C capture JSON/save-status source behavior.
- metadata bridge (already recreated in Library).
- firmware runtime + original comparison harness.
- AWB init/calibration/E2/statistics/classification dependencies.

### Phase B — reconstruct the already-solved AWB suffix from this handoff

Rebuild in dependency order using historical conclusions as a specification:

weighting/filtering → optimizer → history → active history correction → atmosphere → candidate prep → CT/tint → publication/golden gains → dual sync → gain validation/light-source → override → smoothing → result snapshots → output tail → post controller → estimator suffix → passive REAWB → outer completion → scene-entry/no-eligible recovery.

Do not rediscover these stages from scratch unless a specific implementation detail is missing.

### Phase C — genuinely new estimator research

- general ordinary scene loop.
- earlier frame prep/lifecycle.
- active optional paths only if actual config requires them.

### Phase D — phone path

- per-phone calibrated estimator input.
- signed/headroom clean RAW-to-linear path.
- selected-neutral provenance/fallback.
- coherent one-time WB/matrix integration.

### Phase E — HNCS photographic renderer

- per-pixel MAIN CCM.
- gamma numeric contract.
- MAIN LUT component layout/interpolation/rounding.
- end-to-end saved-image composition.

### Phase F — phone photographic validation

- identical RAW offline.
- Android preview/still consistency.
- multi-physical-camera/lens behavior.
- real photographs against Hasselblad reference expectations.

---

## 16. Next APK boundary

The next phone APK should **not** merely be a Native1A rebuild.

Minimum conditions for a useful upgrade over installed Native1C:

- application ID unchanged: `com.mwilliams.hasselbladphoton`.
- signing certificate unchanged.
- version code > 27179.
- capture JSON storage/save-status behavior restored or superseded without regression.
- original Camera2 metadata preserved separately from effective processing data.
- at least one genuinely new, bounded and validated research capability added.

It is acceptable for the next APK to be explicitly experimental. It does **not** need the entire HNCS renderer completed before device testing resumes.

A sensible early experimental build could expose/log a reconstructed selected neutral and provenance while still keeping photographic rendering on the existing Photon path, provided the UI/logging clearly states the boundary and the selected neutral is not silently double-applied.

---

## 17. Things the next session should NOT waste time on

- Do not ask whether `f56df58` or `aded05ef` exists on GitHub; they do not.
- Do not assume the old local Git objects can be restored from commit hashes alone.
- Do not treat the recovery record/ledger as executable proof.
- Do not redo the 10,000-case Q12 primitive investigation unless the primitive changes.
- Do not use the X2D sensor calibration as phone calibration.
- Do not call unity calibration “Hasselblad AWB.”
- Do not apply a second WB after using a matrix that already contains WB.
- Do not claim the display LUT sampler is the saved-photo HNCS renderer.
- Do not claim successful outer status proves a fresh scene estimate.
- Do not publish firmware/vendor libraries/private capture pixels/APKs into Git.
- Do not let reconstructed research remain only in a transient workspace.
- Do not downgrade the phone from Native1C merely to test that an older baseline builds.

---

## 18. Recommended resume prompt for a fresh chat/session

```text
Continue the standalone Hasselblad Photon project from the MEGA HANDOFF dated 2026-10-21. Treat the handoff and the GitHub file hasselblad_native_audit/recovery_20261021/CONVERSATION_AWB_RESEARCH_LEDGER.md as the reconstruction specification for the lost AWB work. The canonical GitHub reconstruction branch is recovery/awb-rebuild-20261021; remote main remains 929f523 and should stay unchanged during reconstruction.

Do not rediscover already-recorded AWB conclusions from scratch. Reconstruct each lost stage from the recorded algorithms, state sizes, offsets, call ordering, branch behavior and historical test boundaries, then rerun the rebuilt code against the restored X2D II 100C 1.3.16.2 original firmware. Immediately sync each verified checkpoint — source, test harness, findings and execution summary — to the recovery branch and read it back before continuing.

Preserve Native1C as the installed phone baseline (0.1-hb-native1c, version code 27179). Do not send or install a Native1A downgrade. Restore Native1C capture-JSON/save-status behavior before the next useful phone APK. A future APK must retain com.mwilliams.hasselbladphoton, the same signing certificate, and use a version code above 27179.

The last historical AWB checkpoint before workspace loss was aded05ef2f87402c051dd5746e6c58585bffe2b5: primary scene preparation and no-eligible recovery. It supported ordinary illumination 0 with scene 3 as the sole eligible scene, and the next genuine estimator target is the general ordinary scene-controller loop followed by earlier frame preparation/init. Active REAWB and broader spectral/illumination routes remain optional/unresolved unless the authentic configuration needs them.

After the AWB chain is reconstructed, the major new research is phone sensor calibration/input mapping, a signed/headroom-preserving RAW-to-linear path with one-time WB, and the unresolved saved-photo Hasselblad per-pixel CCM/gamma/3D-LUT renderer. Keep HNCS photographic rendering claims separate from the already-proved metadata bridge and small Q12 recalibration primitive.
```

---

## 19. Final state summary

What is safe to say now:

- The project source baseline is durable.
- The Native1C capture evidence is durable.
- The environment can be rebuilt.
- GitHub write/sync is working again.
- The conversation now has a durable ledger in both Library and GitHub.
- The exact old AWB source is missing, but the **technical conclusions are extensively preserved in this conversation**.
- Therefore most of the old AWB work should be approached as **reconstruction from a detailed specification**, not full rediscovery.
- The canonical safety mechanism is immediate per-checkpoint GitHub synchronization.
- The genuinely new research after reconstruction is the general scene loop/lifecycle, phone sensor input/calibration, clean RAW-to-linear integration, and the remaining Hasselblad photographic per-pixel renderer.

This handoff is intentionally redundant. Redundancy is preferable to losing another day of reverse-engineering conclusions.
