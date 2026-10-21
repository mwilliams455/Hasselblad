# Original ARM64 runtime recovery — 21 October 2026

The original `libaaa.so` now loads and executes through the exact firmware's Android 9 / API 28 Bionic linker under QEMU AArch64. All transitive ELF dependencies were recovered from the full, hash-matched X2D II 100C 1.3.16.2 firmware. No dependency stubs, patched vendor functions, or transplanted phone calibration were used.

## Fresh results

- Earlier five-job Android replay: **5/5 PASS**, including 9 direct original leaf calls and 10,000 original-versus-portable calls.
- Extended same-process leaf comparison: **27,588 original calls, zero failures**.
- Extended cases: 6,561 boundary combinations, 20,000 deterministic random vectors, 1,024 pointer-alias cases, and 3 null-pointer / zero-divisor cases.
- Across those cases: 3,049 zero-divisor returns; 11,753 cases with an overflowing initial 32-bit shift; 12,304 comparisons also matched the unchanged guarded portable implementation in its supported domain. These are overlapping counters, not additional original calls.
- Status 89 returns before touching gain memory when either divisor is zero. Valid calculations truncate the 32-bit shift before unsigned division. Aliased gains receive sequential updates.
- The original first loadable segment starts at virtual address `0x1000`. Bionic's `dladdr().dli_fbase` is the mapped start, so subtracting it alone from a symbol is not its ELF virtual address. The harness accounts for this.
- The complete newly extracted firmware manifest exactly matches the previously preserved manifest, including both system and vendor image hashes.

The two reports contain freshly executed results, not copied historical pass counts. Together these suites made **37,597 original gain-leaf calls**.

## Reproduce

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_recalib.py \
  --firmware-root /private/extracted \
  --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static \
  --output /private/new-results
```

Python requires `pyelftools`. The runner verifies the library, original symbol, Android version, linker, and full DT_NEEDED closure against the saved extraction manifest before compiling and executing. It records exact source/binary hashes and build/run commands. Runtime inputs are private external files; this directory contains only owned code and public-safe reports.

`hb_recalib_exact` is a research comparator, with original wraparound and pointer-alias semantics. It does not replace the production adapter's input guards. The unchanged inherited portable source is read from Rebuild04 because the GitHub Rebuild05 directory contains incremental files, whereas the private Rebuild05 ZIP contains a complete source tree.

## Remaining acceptance boundaries

The bounded automatic controller is now composed entirely from owned implementations: entry guards, scheduling, white-reference LUT, user controls, dispatch, ROI synchronization/processing, statistics, spectral sensor adaptation, semantic parsing, detection, face, scene, history, atmosphere, post-processing, passive REAWB, diagnostics, shading and completion/recovery. Both fresh-estimate and reused-estimate routes match the original controller on the tested inputs. Initialization, native input import and model/calibration supply remain external. Still missing: real camera-frame inputs and device-specific calibration, phone initialization/input adaptation, app integration, the historical seven-frame capture, HNCS rendering and phone validation. Manual/custom bodies, active REAWB and linked storage remain separate backlog. Diagnostic file I/O is intentionally outside the owned no-file scope. These are bounded synthetic comparisons, not exhaustive proof of every input or device behavior.

No APK was built. `main` and the installed Native1C application remain unchanged.

## Original scene initialization checkpoint

The original `_create_scene_awb_lib_manager`, `scene_awb_clear_context`, `awb_cfg_load`, `scene_awb_cfg_init`, and `scene_awb_lib_init` now execute successfully using the unmodified, hash-matched AWB FlatBuffer. All five return zero; the scene initialized marker at context offset `0x170` is 1; 64-byte boundary guards remain intact around the 920,560-byte context. The original config allocation is 1,502,800 bytes.

This restores the original scene configuration/initialization route. It does not prove that device-specific calibration inputs or authentic frame preparation have been recovered. Config/context bytes and vendor logs stay in a private output directory. Context hashes are per-execution audit metadata; they are not cross-process pointer-equivalence claims.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_scene.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/init-check \
  --report /private/init-result.json
```

Fresh initialization result: `evidence/SCENE_INIT_RESULT.json`, recorded at commit `d0bbacece56e914ff44c4459e94cee8de28423cd`. Source hashes in that report refer to that checkpoint; the runner was subsequently extended below.

## Original numerical optimizer reconstruction

`hb_scene_optimizer.c` now reconstructs the numerical body at original virtual address `0x4a8c48`, plus `scene_awb_compute_color_temperature_no_check` at `0x4911a8`. The owned implementation does not call the original optimizer or temperature routine. It reads the original-initialized context tables and receives explicit synthetic candidate inputs.

Fresh final comparison (`evidence/OPTIMIZER_RESULT.json`):

- **920/920 original optimizer calls match**, including status and all **920,560 context bytes** in the same execution.
- **1,024/1,024 direct original temperature-lookup calls match**, including modulo-32-bit distance arithmetic and the zero-result sentinel.
- The **1,502,800-byte original configuration remains unchanged**; parameter records also remain unchanged.
- Optimizer coverage: metric sweep 0–400 (401 cases), 512 deterministic candidate sets across slots 0–3 and counts 0–8, and seven stateful synthetic calls.
- Zero-weight recovery (status 0/no result) and a constructed fallback-only-weight case (status **72**) were covered. There were 126 cases with unchanged complete context.
- Seven synthetic-step statuses: `0, 0, 0, 72, 0, 0, 0`.
- The first run found two mismatches. Both came from putting metric 41 into the lower constant-weight branch. Original instructions enter the ramp at 41, and the corrected run has zero mismatches.

Implemented behaviours include scene eligibility, the valid-candidate gate, count-dependent weight ramp, optional fallback candidate weighting and CT tapering, original 32-bit wrapping sums/products, integer division, calibrated 81-row temperature lookup, result publication, and the optimizer's maximum-metric copy. Caller-side updates visible after the call at `0x4a77a4` remain outside the optimizer. We have not yet run an owned/full-original scene-controller comparison.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_scene.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/optimizer-check \
  --report /private/optimizer-result.json --optimizer
```

**Coverage boundary:** this is genuine execution of the original numerical optimizer against owned code, using synthetic candidate records on authentic original-initialized state. The seven synthetic calls are not the lost seven authentic E2 frames. No passive REAWB handle comparison or complete AWB chain has been recovered yet. The test fixture includes arithmetic edge cases outside normal photographic ranges; a passing edge case does not prove it is physically meaningful.

### Resume here (latest checkpoint)

1. Latest phone work: [phone RAW input adapter](../phone_input_20261021/README.md), verified on the saved12.6MP Native1C capture and Android ARM64. It supplies signed, metadata-bound block statistics. The [phone temperature submodel](../phone_input_20261021/TEMPERATURE_MODEL.md) now initializes owned CT/tint/gain conversion from original Camera2 matrices, with4,059 round trips and exact ARM64 replay. The [phone scene-candidate bridge](../phone_input_20261021/SCENE_CANDIDATES.md) now runs the owned ordinary-candidate kernels on actual RAW under explicit experimental policies:196,608 block checks and15 exact host/sanitizer/ARM64 comparisons. Candidate results are diagnostic-only; no shipping policy is selected. Next: Native1C diagnostic integration. Full automatic scene/exposure/spatial/history initialization remains open. Latest automatic probe remains `--run-entry --automatic-entry`, **24,219 checks, zero mismatches**, against 2,131 full original controller calls. Report: `AUTOMATIC_RESULT.json`. Earlier reports retain their source snapshots.
2. `hb_run_automatic` now joins the complete owned prefix to scene/history/atmosphere/post/passive-REAWB/diagnostics/shading/completion. It ran 2,083 complete automatic calls with zero original numerical callbacks. The broader harness retains 16 original manual/custom continuations. Private evidence: `Hasselblad_Automatic_Composition_Evidence_PRIVATE_20261021.zip`.
3. Next: build the phone initialization/model/calibration mapping, using the completed RAW input adapter, then restore Native1C diagnostics and integrate the automatic single-RAW test APK. Establish available auxiliary spectral inputs without inventing measurements. Do not redo completed controller composition, RAW accumulation or their stages. White-reference counts must still match the baseline count used by statistics search. Read “Automatic composition” below for the API and error contract.
4. Active REAWB and save requests that enter linked storage remain explicit unsupported paths in the passive port. Represent linked state if implementing them; copying the 1,000-byte handle does not clone allocations. The owned debug path rejects actual file-write requests before mutation; unscheduled/exhausted/disabled requests are handled.
5. Recover genuine captured-frame inputs, map Camera2 statistics and inject real per-sensor phone calibration. Continue to a specifically bounded APK only after its relevant integration and stability checks. HNCS rendering remains a separate acceptance boundary.

Keep private runtime/config/dumps out of GitHub. Keep `main` and Native1C unchanged.

## Native E2 preparation checkpoint

The original top-level `awb_lib_init` now succeeds using the exact private config. It creates the 920,560-byte main context, 118,416-byte E2 context and a non-null 1,000-byte REAWB handle through the original initialization path. No hand-patched capability bits are needed.

`hb_stat_prepare.c` reconstructs the main E2 parser with post-processing disabled, scene statistics import (including brightness), input-record preparation, calibration interpolation/application and AE preparation. No owned numeric function calls a vendor numeric function. The original firmware still supplies initialization and private runtime tables.

Fresh original-versus-owned results: **3,138 checks, zero failures**. Every stage compares all 920,560 context bytes in the same process. The parser additionally compares the entire E2 context, output buffers and boundary guards.

- 64 native-format synthetic E2 frames, **65,536 blocks**; 27,097 zero red ratios and 2,800 clipped red ratios. These counts overlap the blocks, not additional tests.
- 64 parser calls, 64 scene imports, 64 input-record preparations, 1,024 calibration-gain calls, 192 block-calibration calls and 64 AE-preparation calls.
- The 1,502,800-byte config and passive 1,000-byte REAWB handle remain byte-identical. Native input buffers are unchanged.
- The parser retains original raw channels and quality, computes gain ratios, and preserves the original difference between averaging the two green values before versus after integer halving. Scene import uses the original 0.3/0.6/0.1 brightness arithmetic.
- Calibration comparisons cover disabled/empty/one/two-point curves, endpoints, interpolation, CT clamping, modulo-32-bit multiplication and saturation. Test calibration curves are explicitly synthetic.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/preparation-check \
  --report /private/preparation-result.json --prepare
```

**Boundary:** native-format inputs are generated test fixtures, not recovered camera frames. E2 post-processing is disabled in the unmodified initialized IMX861 state; enabled post-processing returns an explicit unsupported result in the owned parser. Calibration injection from a real camera, block classification, scene weighting/filtering/accumulation, caller updates and the full historical seven-frame chain remain unverified. The REAWB comparison here checks passive non-mutation only, not REAWB output parity. Secondary import code exists but this checkpoint's native fixtures are main-only. No APK was built.

## Classification, filtering and connected scene checkpoint

`hb_stat_auto` reconstructs the original automatic-statistics routine with E-ND calibration disabled: input preparation, calibration, AE metadata, segmented nearest-CT search, radius acceptance and confidence. It preserves the original search/control-flow and floating-point order. `hb_scene_filter` reconstructs the connected-component filter, including signed 16-bit channel comparisons, linear neighbor indices, groups of at most three being removed, and exact scratch-buffer writes.

The final preparation suite (`evidence/CLASSIFICATION_FILTER_RESULT.json`) passes **3,522 checks with zero mismatches**:

- 64 synthetic native E2 frames / 65,536 blocks, including E2 parameter-version updates with post-processing disabled.
- 96 imports and 96 input-record preparations, including 32 secondary-region cases and full 4,096-block inputs.
- 1,024 direct calibration-gain comparisons, 192 block-calibration comparisons and 64 direct AE comparisons.
- 80 complete automatic-preparation comparisons, including 16 dense 4,096-block fixtures around all 81 original CT rows; 45,303 accepted blocks across these tests.
- 64 direct filter comparisons across four slots, counts through 4,096 and factors through 255; eight zero-factor status-38 cases.
- Every stage's complete 920,560-byte context matches. The original config and passive 1,000-byte REAWB handle remain unchanged.

The extended secondary-region test initially found 28 mismatches: the last field skips a word in the input record. That offset was corrected, and the final run has zero mismatches. The earlier main-only checkpoint remains valid.

### Earlier connected original-prepared scene comparison (historical checkpoint)

`scene_pipeline_compare.c` runs **seven newly generated native-format E2 frames in one execution**. It uses original native decode/import, user/ROI preparation, sensor/parsing/detection/face stages, spectral weighting, candidate weighting and candidate accumulation. Owned automatic preparation is checked against the original at its boundary. Original-prepared candidate records then exercise the owned filter and optimizer inside a reconstructed normal-slot caller.

`evidence/PREPARED_PIPELINE_RESULT.json`: **72 comparisons, zero mismatches**; seven complete scene-controller context/status comparisons; 14 filter calls, 488 removed candidate memberships and seven optimizer calls. All seven scene statuses are zero. Detection naturally activates normal slot 0 in every fixture; no gate bits are manually forced. Normal slot 1 and special slots 2–3 are not activated in this connected test. Special-slot activation returns an explicit unsupported result in the hybrid harness.

The normal caller restores per-slot maximum-metric updates and the final 16-bit aggregate. This is a **hybrid controller**, not a wholly owned AWB implementation: original functions still perform spectral weighting, candidate weighting, calibrated CT/tint and accumulation. The route stops after scene processing; history, atmosphere, final publication and REAWB processing are not exercised. The passive REAWB comparison covers its 1,000-byte handle, not all pointed-to objects.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/pipeline-check \
  --report /private/pipeline-result.json --pipeline
```

Private evidence now captures each native frame, parsed data, metadata, E2 state, before/after automatic preparation, before/after original and hybrid scene contexts, and the passive REAWB handle. Same-process pointer identity is retained for byte comparison; these dumps are audit evidence, not cross-process reloadable contexts. Their hashes and source provenance are in the public reports.

**Release boundary remains unchanged:** synthetic tests do not establish camera-image quality, real factory calibration, full owned AWB, historical frame parity or phone validation. No APK was built or installed.

## Candidate weighting and owned normal-scene checkpoint

`hb_scene_candidates.c` reconstructs candidate weighting, candidate accumulation, mode-0 CT/tint, two-dimensional weight curves, normal-slot spectral weighting, and the complete normal-slot scene body. `hb_normal_scene` calls only owned numerical routines. It includes the original per-slot metric updates and final 16-bit aggregate. The original firmware still initializes the private context and tables.

`evidence/CANDIDATES_RESULT.json`: **9,858 checks, zero mismatches**:

- 2,048 interpolation calls and 2,048 mode-0 CT/tint calls, including original arithmetic wraparound and degenerate table geometry.
- 1,024 CT/probability/tint curve calls; 96 weighting and 128 accumulation calls across four slots and eight candidate indices, with low sample counts, zero weights, brightness, semantic weights, polygon overrides, gain remapping and error paths.
- 256 spectral-distribution calls, 256 spectral-ratio calls and 64 complete spectral-state calls, including enabled, disabled, missing-statistics and malformed-knot cases.
- 32 direct normal-controller calls with synthetic normal-slot gates and EV values. These modified gates are test inputs, not evidence that original detection activates slot 1 on camera frames.
- Complete 920,560-byte context comparisons at stateful boundaries; the original config and passive 1,000-byte REAWB handle remain unchanged.

`evidence/OWNED_NORMAL_SCENE_RESULT.json`: **156 comparisons, zero mismatches** on seven generated native E2 frames. Each frame compares the original normal body with an independent `hb_normal_scene` call, including all context bytes and status. All seven statuses are zero. The boundary harness also compares 14 weighting calls, 14 filters, 14 accumulations, seven spectral calls and seven optimizers. Filters remove 488 candidate memberships. Original detection naturally activates only normal slot 0; no detection gate is forced in this connected test.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/candidate-check \
  --report /private/candidates-result.json --candidates

python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/owned-normal-check \
  --report /private/owned-normal-result.json --pipeline
```

Private evidence captures the generated native input and intermediate states plus original, boundary-comparison and standalone-owned scene outputs for each frame. Source, binary and dump hashes are recorded in the reports. Earlier reports describe their own pinned source snapshots and have not been rewritten.

**Scope:** CT modes 1/2 and active special slots 2/3 remain explicitly unsupported. The connected harness still uses original decode/import and surrounding user/ROI/sensor/parsing/detection/face processing; automatic preparation is separately compared with owned code. The enabled spectral route has direct synthetic coverage, not camera-frame validation. History, atmosphere, final publication and REAWB processing are not covered here. No full AWB parity, real calibration recovery, APK build or phone validation is claimed.

## Calibrated temperature modes and scene integration checkpoint

`hb_temperature.c` now reconstructs modes 1/2 and their matrix/xy helpers. Mode 1 normalizes the input channels, selects/interpolates the private calibration matrices, performs the original inverse-matrix iteration and converts xy to temperature/tint using an externally supplied 31-row table. It retains the AE-dependent matrix and gain-remapping paths. Mode 2 selects the calibrated calculation below the first red-gain knot, the existing nearest-table calculation within range, and the original extrapolation above the final knot.

`hb_temperature_compute` is the complete temperature entry point. The older `hb_candidate_temperature` remains the mode-0 primitive. `hb_candidate_accumulate_with_model` and `hb_normal_scene_with_model` connect the complete implementation using an explicit `hb_temperature_model`; wrappers without that model retain mode-0 operation and return unsupported if a required table is unavailable. No original function pointer is accepted. Private tables and calibration are read at runtime, never embedded in the owned source.

`evidence/CALIBRATED_TEMPERATURE_RESULT.json`: **19,362 checks, zero mismatches**:

- 2,048 xy-to-temperature/tint comparisons, 512 matrix-row comparisons and 512 matrix-selection/interpolation comparisons.
- Direct temperature calls: 128 mode-0, 2,048 mode-1, 2,048 mode-2 and 32 invalid-mode cases. Results match bit-for-bit, including error returns and unchanged outputs on errors.
- 32 aliased-output cases and 128 candidate-accumulation comparisons using the alternate models.
- 64 complete normal-scene comparisons with alternate models selected in private config copies; all 64 return zero and match every one of the 920,560 context bytes. Gate and mode selections are explicitly synthetic.
- Zero-channel status 91, singular-matrix status 92, invalid-extrapolation status 93 and invalid-mode status 94 are exercised. Original config and the passive 1,000-byte REAWB handle remain unchanged.

The existing acceptance routes also pass after integration: **9,858 checks** in `TEMPERATURE_CANDIDATES_REGRESSION_RESULT.json` and **156 comparisons / seven generated native frames** in `TEMPERATURE_PIPELINE_REGRESSION_RESULT.json`, all with zero mismatches. Both authentic normal-slot parameter sets still select mode 0; the connected seven-frame run therefore remains mode-0 coverage. The new direct scene tests establish the alternate-mode integration separately.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/temperature-check \
  --report /private/calibrated-temperature-result.json --temperature
```

The private evidence includes the external isotemperature table, initialized runtime dumps, deterministic input/output vectors and representative original/owned scene states. `temperature_vectors.bin` stores 40-byte little-endian records: six uint32 fields (mode, case, red, green, blue, original status), two original float outputs and two owned float outputs. Context pointers are meaningful only within their original execution. Earlier reports retain their historical source hashes.

**Current boundary:** active special slots 2/3 remain unsupported. These tests do not recover real camera frames, phone calibration or photographic image quality. Surrounding controller stages, history, atmosphere, final publication, active REAWB processing and HNCS rendering remain outside this checkpoint. No APK was built or installed; `main` and Native1C remain unchanged.

## Complete scene stage and downstream baseline checkpoint

`hb_scene_controller.c` now reconstructs the special-scene control paths and their spectral and post-optimizer weighting. `hb_scene_process` executes the complete four-slot scene stage using only owned numerical routines, with an explicit external temperature model when required. The normal-only APIs retain their earlier scope; the shared normal prefix is reused without prematurely publishing the final aggregate. This completes `scene_awb_scene_proc`, not the surrounding top-level `scene_awb_lib_run` controller.

The special paths preserve their distinct config offsets, exact-enable gate, empty/no-eligible behavior, error-return ordering, per-slot metric and final 16-bit aggregate. The nested confidence helper selects brackets using scene confidence but interpolates the camera index. That original instruction behavior is retained and directly compared for camera index 0.

`evidence/SCENE_CONTROLLER_RESULT.json`: **15,162 checks, zero mismatches**:

- 4,096 scalar interpolation, 2,048 confidence-curve, 1,024 CT-curve and 128 special-spectral comparisons.
- 256 whole-scene comparisons covering all 16 gate combinations, all four slots and temperature modes 0/1/2. Sixteen use 4,096 blocks; some special scenes use all eight candidate records. 231 return zero; the remaining expected error returns and partially updated contexts also match.
- 16 further calls with the unmodified original configuration and synthetic gate masks. Original special slot 2 is disabled; slot 3's configured filter factor is zero, so activating that path can return status 38. Successful special-path tests use clearly identified private test config copies.
- A 12-call sequence carrying scene state forward: all 12 statuses are zero and every complete context matches.
- Tested returns include 38, 40, 45, 57, 73, 91 and 94. Original config and the passive 1,000-byte REAWB handle remain unchanged.

`evidence/COMPLETE_SCENE_PIPELINE_RESULT.json`: **170 comparisons, zero mismatches** on the seven generated native E2 frames. Each frame independently compares the complete `hb_scene_process` result with the original, including status and all 920,560 context bytes. Original detection still activates normal slot 0 only. `SCENE_TEMPERATURE_REGRESSION_RESULT.json` retains all **19,362** temperature/integration checks with zero mismatches after the normal-prefix refactor.

`evidence/ORIGINAL_DOWNSTREAM_BASELINE_RESULT.json` extends the seven-frame run through the original history, atmosphere, post and REAWB entry points: **28/28 calls return zero**, and the scene boundary still passes **169 comparisons**. The passive REAWB immutability check is intentionally omitted in this execution mode because downstream original code is allowed to process its handle. The reduced comparison count is not a lost scene comparison.

History, atmosphere and post change the main context on six frames; the low-quality sixth frame leaves history/atmosphere unchanged and changes six bytes in post. REAWB changes zero main-context bytes on every fixture. These are original execution baselines, not owned downstream comparisons or proof that active REAWB inference ran. Per-stage changed-byte counts and private dump hashes are recorded in the report; pointed-to REAWB objects are not comprehensively captured.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/controller-check \
  --report /private/scene-controller-result.json --controller

python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/downstream-baseline \
  --report /private/original-downstream-result.json --pipeline --tail-baseline
```

**Current scope:** the four-slot scene stage is owned and verified on these synthetic inputs. Earlier preparation/detection and downstream processing still use original routines in the connected harness. No authentic historical frame recovery, real phone calibration, complete AWB/active REAWB parity, photographic quality or HNCS validation is claimed. No APK was built or installed. `main` and Native1C remain unchanged.

## Owned history processing checkpoint

`hb_history.c` reconstructs `scene_awb_hist_proc` and its temperature-distance, polygon-membership, edge-distance and histogram-zone helpers. It retains the four-slot validity gate, category/confidence selection, EV/CT eligibility, optional gain remapping, distance fallback, histogram/CT/distance interpolation, EV and E-ND correction scaling, weighted category blending, strongest-correction selection, measured-channel selection and all diagnostic/result writes. Numerical work calls only owned functions; original initialization and private calibration tables are still required.

`evidence/HISTORY_RESULT.json`: **30,360 checks, zero mismatches**:

- 4,096 temperature-distance, 4,096 polygon-membership, 4,096 edge-helper, 4,063 polygon-distance and 192 histogram-zone calls. Signed bounds, truncation versus arithmetic shifts, wrapping products, remapping and semantic category selection are exercised.
- 256 direct history comparisons across all four slots; 192 successful calls and matching error returns/partial contexts for invalid category 74, empty distance table 79 and invalid interpolation weights 80. Sixteen cases contain 4,096 blocks.
- 256 additional history comparisons exercise multiple categories, non-neutral correction tables, EV/E-ND ramps, confidence weights, overlapping zones, single-row tables, large products and NaNs. **375 slot outputs change their gains**, so this is not just identity-path coverage.
- 64 further history calls use the unmodified original config with generated context inputs, plus 12 stateful calls. Every comparison includes status and all 920,560 context bytes. Original config and passive REAWB handle remain unchanged.

An early reading suggested that successful interpolation might reset corrections to unity. Non-neutral original-versus-owned tests disproved that reading; the final implementation computes and applies the corrections. No unity-only shortcut remains. The zone-count helper does retain the verified original choice of the larger of its two aggregate measures.

`evidence/HISTORY_PIPELINE_RESULT.json`: **183 comparisons, zero mismatches** on seven generated native E2 frames. The complete owned scene output feeds a history boundary comparison, and the complete owned history output then feeds original atmosphere, post and REAWB calls. All seven history statuses and all 28 original downstream baseline calls are zero. The seven history outputs match byte-for-byte, including the unchanged history state of the low-quality sixth frame. The connected fixtures naturally activate only normal slot 0; all-slot and active-correction coverage comes from the separate generated tests above.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/history-check \
  --report /private/history-result.json --history

python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/history-pipeline \
  --report /private/history-pipeline-result.json --pipeline --history-pipeline
```

The research ABI requires allocated, validated context/config structures and bounded table counts: at most 4,096 blocks, eight history entries per slot, four polygon entries per embedded table, eight distance rows and nonempty EV axes of at most eight entries. This is not an untrusted-input parser. Error parity covers the explicitly exercised malformed category/distance-table cases, not arbitrary invalid pointers or corrupt lengths.

**Next:** reconstruct atmosphere processing at `0x48fed0` from the preserved owned-history outputs, then post-processing at `0x49e4f0`. Surrounding preparation/detection, atmosphere, post and REAWB still use original code in the connected harness. Synthetic agreement does not establish authentic historical-frame recovery, real phone calibration, full AWB, active REAWB, HNCS or photographic quality. No APK was built or installed; `main` and Native1C remain unchanged.


## Owned atmosphere processing checkpoint

`hb_atmosphere.c` reconstructs the four-slot `scene_awb_atmos_proc` stage: the CT/tint eligibility gate, normal and calibrated special-slot temperature routes, exposure/CT/tint gain tables, category-confidence corrections, E-ND-dependent corrections, original wrapping products and context diagnostics. Its helpers retain the two different distance interpolation algorithms: wrapped integer arithmetic in the basic gain tables, and signed floating-point interpolation with negative-output rejection in category tables. The basic EV helper selects brackets with 32-bit knots but uses their low bytes in final interpolation, matching the pinned firmware.

`evidence/ATMOSPHERE_RESULT.json`: **33,946 checks, zero mismatches**:

- 4,096 signed interpolation calls; 2,048 basic EV-row calls; 1,024 each of basic gain, E-ND value and E-ND gain helpers; and 3,072 category distance/CT/EV helper calls.
- 512 complete atmosphere comparisons covering all four slot masks, validity values 0/1/2, temperature modes 0/1/2 and invalid modes, confidence selection, out-of-range tint, correction scaling, NaNs and partially updated error contexts. **363 return zero**; expected returns include 91 (one), 94 (83), 168 (32) and 189 (33).
- **601 slot outputs have changed red or blue gains**, establishing active correction coverage rather than only unchanged outputs.
- 64 calls with the unmodified original config and generated contexts. Slot 2 is explicitly disabled in these fixtures because its original basic atmosphere table is empty; it is exercised with valid synthetic tables in the separate all-slot tests.
- 12 calls carrying atmosphere state forward. Complete context/status comparisons pass; original config and the passive REAWB handle remain unchanged throughout the direct suite.

`evidence/ATMOSPHERE_PIPELINE_RESULT.json`: **197 comparisons, zero mismatches** across seven generated native E2 frames. The owned scene output feeds owned history, then owned atmosphere. History and atmosphere are independently compared with original calls at their same-process input boundaries. The owned atmosphere output then feeds original post-processing and REAWB. All 28 original tail-baseline calls return zero. The seven atmosphere outputs match all 920,560 context bytes, including the inactive low-quality frame; connected original detection still activates only normal slot 0.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/atmosphere-check \
  --report /private/atmosphere-result.json --atmosphere

python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/atmosphere-pipeline \
  --report /private/atmosphere-pipeline-result.json --pipeline --atmosphere-pipeline
```

The research ABI requires validated, allocated structures and nonempty nested axes. Basic tables have up to eight EV rows, fifteen CT rows per EV row and eight distance rows per CT row. Category confidence records use the original fixed layout. An enabled empty basic atmosphere table, or a selected E-ND value with no EV rows, returns `HB_PREP_UNSUPPORTED`: the original consumes unspecified stack outputs in those cases. Direct empty top-level helper calls retain their original no-write success behavior. This explicit boundary is not a claim of parity for arbitrary malformed lengths or uninitialized data.

### Relationship to colour rendering and the next boundary

Atmosphere processing directly scales scene red/blue WB gains using exposure, CT/tint and category evidence. Post-processing blends/selects the candidate results, recalibrates and normalizes gains, applies optional colour-mode gain adjustments, performs dual-camera synchronization and publishes AWB state. These stages influence the renderer through its WB inputs. They do not establish the complete HNCS pixel-rendering pipeline, tone reproduction or output colour transforms.

Inspection of the original `scene_awb_color_mode_proc` (`0x4667a8`) shows that its final operation scales the red/blue gain fields at context offsets `0xb0c4c` and `0xb0c54`. Its feature-enable flag is zero in this original config, so the connected baseline does not validate an active colour-mode adjustment. At this atmosphere checkpoint this was only a source-trace finding; the post-result checkpoint below adds an owned implementation and active synthetic comparisons.

**Next implementation:** `scene_awb_post_proc` at `0x49e4f0` (9,320 bytes), using each saved `frame_XX_after_atmosphere_owned.bin` as its audited boundary. Rebuild its blending and publication helpers, `scene_awb_result_normalise_all`, `scene_awb_compute_result_ct`, golden-gain/E-ND/unit recalibration, `scene_awb_color_mode_proc`, CT/tint-to-gain conversion and dual-sync dependencies. Original post outputs are already captured. REAWB and the surrounding user/ROI/sensor/parsing/detection/face route still require owned implementations or explicitly bounded integration.

No historical camera frames, real phone calibration, full AWB/active REAWB parity, photographic quality or HNCS validation is established. No APK was built or installed; `main` and Native1C remain unchanged.


## Post-result helpers and mode-2 checkpoint

`hb_post_results.c` implements nine post-processing primitives: the two-normal-result blend, golden-gain conversion, final CT/tint calculation, golden snapshots, E-ND temperature and unit recalibration, camera recalibration, normalization, and colour-mode gain adjustment. `hb_post_finalize` composes the seven final-result helpers in the original order with matching early exits. `hb_post_mode2` owns the complete mode-2 branch, including diagnostic publication and final validation. This does **not** yet own the normal-mode `scene_awb_post_proc` controller.

Original arithmetic details are preserved: 32-bit wrapping gain products and calibration shifts, 64-bit normalization products, the blend's double reciprocal rounded to float, and golden-conversion pointer write order. Normalization updates records sequentially, so a later zero channel can leave earlier records changed. The outer mode-2 branch returns its final validation status even when a helper failed; owned unsupported boundaries remain explicit. Final CT reuses the previously verified calibrated-temperature implementation with the private model supplied by the caller.

Colour mode clamps the configuration's mapping count to 22, chooses one of two mapped tables and its mode-dependent subtable, then scales final red/blue gains. Endpoint correction values are loaded as 16-bit integers; interpolated values use full 32-bit words and signed float-to-integer conversion. Both behavior and diagnostic writes are compared. Its flag remains disabled in the unmodified original config, so active adjustment coverage comes from synthetic tables.

`evidence/POST_RESULTS_RESULT.json`: **15,271 checks, zero mismatches**:

- 4,096 golden-conversion calls, including wrapping multiplication, zero divisors, null outputs and aliased output pointers.
- 512 normal-result blend calls, including wrapping weight sums and status 132; 1,280 snapshot/recalibration/normalization calls with complete context comparisons.
- 512 colour-mode calls covering both mappings and subtables, 1–10 CT entries, endpoints/interpolation, high correction bits, disabled processing, count clamping and status 191. **444 calls change red or blue gains**. Configuration mutations are compared separately.
- 192 result-CT calls: 159 successes, 11 singular-matrix returns (92) and 22 zero-channel returns (95), including partial diagnostic writes.
- 256 composed finalizer calls: 171 successes, 11 returns of 89, 32 of 95, 31 of 133 and 11 of 191. Context and configuration match at every exit.
- 256 complete mode-2 post calls: 192 successes and 64 final-validation returns of 151; 16 stateful finalizer calls; explicit unsupported-input guards. The original config and passive REAWB handle remain unchanged.

`evidence/POST_RESULTS_PIPELINE_RESULT.json`: **227 comparisons, zero mismatches** on seven generated native E2 frames. Owned scene/history/atmosphere still feed **original post and original REAWB**. A separate replay restores the original post's pre-calibration channel snapshots, compares the original final-helper sequence with `hb_post_finalize`, then restores the actual original post output before REAWB. This is a reconstructed snapshot boundary, not interception of a live pre-finalizer call and not a wholly owned post controller.

- All seven final-helper replays match complete contexts and statuses against the original helper sequence.
- The persistent post gain/CT records match the original full post output on all seven frames. On six fresh results, the entire replay context also matches that full post output.
- On the rejected sixth frame, original post retains the previous gains and leaves cleared CT/tint diagnostics. Deliberately replaying the finalizer repopulates those diagnostics, so this fixture is checked as a separate fallback: its original diagnostic bytes remain zero, gain records match, and original post state is restored before continuing.
- All 28 original history/atmosphere/post/REAWB calls return zero. No active REAWB output claim is made.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/post-results \
  --report /private/post-results.json --post-results

python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/post-results-pipeline \
  --report /private/post-results-pipeline.json --pipeline --post-results-pipeline
```

Research contract: initialized context/config, valid private temperature model, bounded ordered tables, and disjoint normal-blend input/output records. An active empty colour axis or mapping outside the two supported tables returns `HB_PREP_UNSUPPORTED`; arbitrary corrupt pointers/lengths are not supported. Other post modes are rejected by `hb_post_mode2` before modification. The general normal/special blending controller, temporal smoothing/publication, CT/tint override conversion and dual-sync dependencies remain to be integrated and compared.

Next resume at `scene_awb_post_proc` with the newly captured `frame_XX_after_atmosphere_owned.bin` input and original post output. The normal blend primitive is ready; publication at `0x4a0d80` and mode/category selection at `0x4a0958` are disassembled privately for continuation. Keep fresh-result and retained-result paths distinct. These AWB gains influence colour rendering, while HNCS/pixel rendering, real phone calibration and photographic quality remain unvalidated. No APK was built or installed; `main` and Native1C remain unchanged.


## Complete post-controller checkpoint

`hb_post_process` now reconstructs `scene_awb_post_proc` across its normal, mode-2 and preset branches using owned numerical functions. It covers normal-result blending and history decay, both special slots, nested merge weights, face/override blending, retained-result recovery, category assignment, dual-sensor synchronization, manual CT/tint gain conversion, ISO/tint gain correction, temporal smoothing and final result publication. `hb_post_validate` exposes the previously compared outer validator for both mode-2 and general post.

The implementation preserves the original 32-bit wrapping arithmetic, signed smoothing divisions, float/double conversion order, partial writes, and final-validation return semantics. Two unusual original behaviors are preserved: the category score's threshold selection and the ISO correction's repeated evaluation of the lower EV row. The owned controller never calls a vendor numerical routine. The original library supplies initialization and private calibration/model tables only; the harness separately invokes original routines as comparison oracles.

### Fresh comparison evidence

`evidence/POST_CONTROLLER_RESULT.json`: **10,051 checks, zero mismatches**.

- 512 inverse CT/tint-to-gain cases, including zero CT and extreme scale inputs.
- 256 smoothing primitive cases with complete state/output comparisons; 128 cases each for special gate, nested merge weights and ISO/tint tables.
- 384 category calls and 384 publication calls, comparing all 920,560 context bytes.
- 256 cases each for sensor tint transformation, sensor conversion, synchronization-zone selection, gain shifting and complete sync calculation; all 256 complete sync calls change state and match.
- 1,024 complete post calls across modes 0–11 and optional feature fixtures: 998 return zero, 26 return final-validation status 151. There are 50 cleared manual requests, five applied retained-result manual overrides, and 45 calls with colour-mode correction enabled.
- 288 consecutive post calls preserve history and smoothing state; the fast-smoothing timer is checked through expiry. Two owned-only unsupported-input guards are included in the total and are not original-equivalence cases.

`evidence/POST_CONTROLLER_PIPELINE_RESULT.json`: **211 comparisons, zero mismatches**, seven synthetic native E2 frames. Owned scene/history/atmosphere outputs feed the complete owned post controller. All seven post outputs match the original in all 920,560 context bytes, and owned post state continues into original REAWB. All 28 original tail comparison/baseline calls return zero. The sixth, rejected frame retains its prior gains and leaves fresh-result diagnostics cleared; no finalizer replay is substituted for this comparison.

The research ABI requires initialized contexts, valid pointers, bounded ordered tables and the explicit private temperature model. Unsupported malformed/empty table inputs are rejected where the original may abort or consume unspecified outputs; this is not an untrusted-input production adapter. Active colour-mode mapping retains the two-table scope of the preceding helper checkpoint. Tests do not exhaust every configuration combination, validate physical multi-camera synchronization, or establish real photographic quality.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/post \
  --report /private/post-result.json --post
# Connected owned scene/history/atmosphere/post:
# use --pipeline --post-pipeline and a separate output/report path.
```

Post-processing supplies white-balance gains and related state to colour rendering. Full HNCS pixel rendering, active REAWB, a wholly owned AWB controller, phone calibration and device validation remain separate work. No APK was built or installed; `main` and Native1C remain unchanged.


## Completion, shading and passive REAWB checkpoint

`hb_completion.c/.h` supersedes the earlier unverified bounded completion model for these initialized-context paths. The four 156-byte result-copy helpers, outer cleanup/recovery, final shading-temperature selector and three passive REAWB routes now execute owned code without original callbacks.

Fresh direct evidence: `evidence/COMPLETION_RESULT.json`, **7,311 checks, zero mismatches**:

- 512 result-copy calls, covering publication, restoration and reference copies to both live and confirmed pairs.
- 1,024 shading calls: validity must equal 1; the later label wins equal ratios; labels 1/4 select reference CT. Other labels select reference CT only when the **byte** at `0xeff8` is 3 and the count is at least 60. Nonzero upper bytes are tested explicitly. This corrects the field-width assumption in the older historical bounded model.
- 768 passive REAWB calls, 256 per route: processing disabled, nonzero mode, and mode zero with the active-run flag not equal to 1. Compare all 920,560 context bytes and all 1,000 handle bytes. Includes 192 save-before-enable cases that do not enter linked storage, packed-confidence truncation, diagnostic validity and counter wrap.
- 512 prepared completion-suffix calls across preceding statuses 0, 40, 151 and `UINT32_MAX`; reference request bytes 0, 1, 2 and 255; plus 192 stateful completion calls.
- Two **actual original-controller failure paths**, entered immediately before scene or post: scene returns 40 or post returns 151, the original controller skips subsequent stages, restores confirmed results and returns zero. Owned stage-plus-completion outputs match the complete context and unchanged REAWB handle.
- Six owned-only guard checks are included in the total; they verify explicit unsupported status and unchanged buffers for active REAWB and linked-save requests. They are not original-equivalence claims. One additional check confirms original configuration immutability.

`completion_entry.S` is a test-only AArch64 ABI adapter. It creates the saved-register/TLS-canary frame expected by the original controller and enters its unmodified code at completion (`0x4722b0`), scene (`0x471f80`) or post (`0x471fb0`). It does not patch functions, inject return statuses into the two failure witnesses, or exercise the omitted outer prefix. Plain suffix cases supply the preceding status explicitly. On valid initialized contexts, the final copy helper's zero status replaces the earlier error. A zero outer status therefore does not establish a fresh estimate.

Fresh connected evidence: `evidence/COMPLETION_PIPELINE_RESULT.json`, **267 comparisons, seven synthetic native E2 frames, zero mismatches**. Owned scene/history/atmosphere/post/passive REAWB feed the original debug packer, then owned shading and completion. Every new stage is compared against its original from the same input. Debug file output is disabled and checked before execution. The rejected sixth frame still retains gains without fresh CT/tint diagnostics. The full 920,560-byte context matches after final completion on all seven frames.

Reproduce using the standard private firmware/NDK/QEMU arguments to `run_full.py`, selecting `--completion` for direct checks or `--pipeline --completion-pipeline` for the connected chain. The latter implies full post, atmosphere and history replacement. `--post` and `--pipeline --post-pipeline` remain available for their earlier boundaries.

Passive scope: save flag exactly 1 runs before the enable check. Packed confidence above 122 requires linked storage even when processing is disabled and returns owned `HB_PREP_UNSUPPORTED` without mutation. Mode-zero active processing is also unsupported. Disabled processing with no linked save, nonzero modes and inactive mode-zero runs are implemented. This is not an active REAWB claim.

Next: own diagnostic packing/no-file user-dump, then outer prefix/dispatch and surrounding preparation/detection. The private packet preserves their disassembly plus stage-boundary dumps; the complete runtime archive remains separate. Full AWB, authentic-frame recovery, phone calibration and HNCS/pixel rendering remain unvalidated. No APK was built or installed.


## Diagnostic packing and composed downstream checkpoint

`hb_diagnostics.c/.h` replaces original `scene_awb_debug_proc` for bounded initialized contexts with no file output. It owns the full state transformation: clearing packet regions, saving fresh diagnostics, restoring the previous diagnostic block on rejection while retaining 37 selected current fields, packing and encoding two metadata sections, full statistics, reduced statistics and coarse statistics, and no-file user-dump state updates. Original log messages and file output are not reproduced. The encoding is the firmware's byte-feedback transform, not a claim of secure encryption.

Fresh direct evidence: `evidence/DIAGNOSTICS_RESULT.json`, **6,554 checks, zero mismatches**:

- 512 metadata-encoding context comparisons, with owned supported-status checks. The original helper's unspecified return value is not compared.
- 384 no-file user-dump calls, including disabled/non-1 flags, exhausted counts, zero periods, unscheduled requests and counter wrapping. Actual scheduled writes return owned unsupported without mutation and are not executed in the original tests.
- 1,024 complete diagnostic calls: 340 fresh backup, 172 retained backup and 512 mode-2-or-higher cases. Includes 384 grids over 1,024 samples, 320 odd-dimension cases, empty grids and 64×64 maximum grids. Every call compares all 920,560 context bytes and checks workspace canaries.
- 64 dedicated packing cases around rounding/saturation boundaries and wrapped 32-bit sums; both 2×2 and 4×4 coarse reduction are exercised.
- 256 consecutive diagnostic calls carrying fresh/rejected/non-1-valid state forward. Two checks also establish configuration and REAWB-handle immutability.
- 24 owned-only guard checks are included in the total, not original-equivalence claims: metadata bounds, dimensions/count mismatch, short workspace and actual scheduled file output all return unsupported with context/workspace unchanged.

The research contract requires metadata lengths A ≤ 510 and A+B ≤ 1015, width/height ≤ 64, and sample count equal to width×height. The caller supplies a separate 3,076-byte workspace. The original allocates this temporary buffer; allocator failure is outside the parity claim. Original malformed-length behavior writes before its late check, so those inputs are deliberately rejected rather than treated as supported cases.

Fresh connected evidence: `evidence/DIAGNOSTICS_PIPELINE_RESULT.json`, **302 comparisons, seven synthetic native E2 frames, zero mismatches**. Owned scene/history/atmosphere/post/passive REAWB/diagnostics/shading/completion are connected. Each boundary is independently compared to the original. Additionally, restore the pre-scene context and handle, enter the unmodified original controller at `0x471f80`, and let it run all stages through its own cleanup and return. All seven full contexts, REAWB handles and statuses match the composed owned path. This prepared suffix does not exercise the omitted controller entry/dispatch or preparation/detection prefix.

The rejected sixth frame preserves the already verified retained-gain behavior and cleared fresh-result diagnostics through the new owned debug stage. `completion_entry.S` remains test scaffolding only. All old commands are retained; `--diagnostics-pipeline` implies `--completion-pipeline` and its earlier stage replacements. Public reports include source/header/compiler/runtime/probe and private-dump hashes. Raw state, logs and original disassembly remain private.

Next: outer controller entry, scheduling and dispatch, then remaining preparation/detection dependencies. Full AWB, active REAWB, authentic camera-frame recovery, phone calibration and HNCS/pixel rendering remain unvalidated. No APK was built or installed.


## Controller entry and scheduling checkpoint

`hb_run_entry.c/.h` owns the outer entry from `scene_awb_lib_run` (`0x471a38`) through the boundary immediately before E-ND white-LUT preparation at `0x471e50`. It implements the wrapping entry counter, initialized/busy guards, fixed-result gains/CT/tint publication to live/combined/confirmed/manual records, warm-up counter, frame-skip cadence, rate limiting and E-ND feature/change flags. It makes no firmware calls. Fixed-result and scheduling returns bypass shared completion, preserving pending reference requests as the original does.

`hb_run_entry` returns its research-operation status separately from `hb_run_entry_result`. `HB_RUN_RETURN` supplies an original final status; `HB_RUN_PREPARE` means processing must continue, not that AWB has completed or produced a fresh estimate. Null arguments return unsupported. This is an initialized-allocation research ABI, not a production phone adapter.

Fresh evidence: `evidence/RUN_ENTRY_RESULT.json`, **7,419 checks, zero mismatches**, from **1,303 actual full original controller calls**:

- 896 base cases covering initialized/busy flags, fixed-result publication, cadence, rate gating and ready paths. Fixed gains preserve wrapping products, unsigned tint conversion, untouched record fields and all seven result destinations.
- 144 scheduling numeric-boundary cases, including timestamp clamping, equality, negative/zero/NaN/infinite durations and saturated unsigned conversion.
- 256 consecutive calls carrying cadence and other controller state forward.
- Seven synthetic native E2 frames through full original dispatch, including a rejected frame.
- Outcome counts: 128 uninitialized, 128 busy, 128 fixed-result, 320 cadence-skip, 149 rate-skip and 450 ready. Thus 853 owned early returns and 450 owned-entry/original-remainder executions. Complete context (920,560 bytes), config (1,502,800 bytes), REAWB handle (1,000 bytes) and final status match for every case.

The harness saves initialized state, calls the actual full original controller, restores that state, runs owned entry, then either returns its early result or enters the unmodified original remainder at `0x471e50` using the existing test-only ABI adapter. This validates replacement behavior with the original remainder. It does not independently capture an original mid-entry boundary, combine entry with the owned downstream chain, or establish full-controller ownership. Original initialization, private tables and remaining preparation/detection still participate.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/run-entry \
  --report /private/run-entry-result.json --run-entry
```

**Meaning for colour and a phone port:** these results support faithful AWB software behavior for the tested inputs and state. Atmosphere and post-processing influence colour through the white-balance gains they supply. They do not establish matching finished photographs: a phone still needs correctly mapped statistics, its own sensor/lens calibration, coherent one-time WB application with its colour matrices, separate HNCS/pixel-rendering work and physical capture comparisons across lighting conditions. Passing synthetic comparisons is a foundation for that integration, not a guarantee of photographic equivalence.

Next: E-ND white-LUT and user preparation, statistics-difference checking, remaining dispatch and detection dependencies. Their original disassembly is preserved privately. Active REAWB/linked storage remains outside the passive scope. No APK was built or installed; main and Native1C remain unchanged.


## White-reference LUT preparation checkpoint

`hb_white_lut.c/.h` reconstructs sparse white-reference expansion (`0x4ab960`) and `scene_awb_stat_e_nd_white_lut_proc` (`0x4ab5f0`) without firmware callbacks. Expansion creates the 81-row reference curve and its sparse-point indices, preserving wrapped fixed-point slope arithmetic, truncating signed division, repeated CT indices, first/last extrapolation, radius flooring and partial writes before statuses 30/33. The original two-point path does not extrapolate above its last point. Zero/one-point inputs clear the first index without filling the table.

Preparation implements the exact enable/change/cache gates, baseline restoration of both reference tables, active E-ND axis selection and floating-point blending of all four point fields. Active processing updates the first table only. Above-all-axis values select the **first** table in the original; this behavior is preserved. The scalar implementation preserves separate multiply/add rounding, with floating-point contraction disabled.

Fresh `WHITE_LUT_RESULT.json`: **11,302 checks, zero mismatches**:

- 1,024 direct expansion calls across counts 0–15, endpoints, off-grid CTs, equal/decreasing indices, wrapping gains and positive/negative slopes. Compare status, complete context, complete output with canaries, and immutable input points.
- 1,024 preparation calls across gate flags, empty tables, baseline restoration, endpoints/interiors, above-range inputs, NaN/infinite input values and synthetic gain extremes.
- 256 consecutive preparation calls carrying table/cache state across enabled and disabled transitions. Preparation calls total 1,280; compare all context bytes and config immutability on every call.
- Across expansion/preparation: 201 original status-30 and 66 status-33 returns; 386 successful active table changes and 122 successful baseline restorations.
- 36 owned-only guard checks are included, not original-equivalence cases. They cover unsafe counts/CTs, inconsistent active/baseline or interpolation counts, and a nonfinite interpolation endpoint. Original configuration and REAWB-handle immutability are checked separately.

Fresh `WHITE_LUT_ENTRY_RESULT.json`: **7,611 checks, zero mismatches**, from **1,335 full original controller calls**. Restore the same input and replace both entry and white-LUT preparation; continue with the unmodified original user-processing remainder at `0x471e64`. There are 853 entry early returns, 32 white-LUT failure returns and 450 original-remainder executions. Every call compares full context/config/REAWB handle and final status. The suite retains 144 scheduling boundary cases, 256 stateful calls and seven synthetic native E2 frames; three native frames enable E-ND with consistent synthetic reference tables. The 32 LUT failures verify partial writes and direct return without running user processing or shared completion. This still does not combine the owned prefix with the separately owned downstream chain.

### Fixture issue found and resolved

The first connected active-E-ND fixture supplied three reference points while leaving the baseline count at eight. The downstream statistics search consumes that baseline count, so the shorter active update left stale segment indices. The unmodified full original controller failed to finish the fourth synthetic frame; a native-only reproduction did the same. This was an inconsistent synthetic fixture, not an owned/original numerical mismatch. Keeping the E-ND point count equal to the baseline count makes the complete connected suite pass. The owned preparation API now rejects that mismatch before mutation. The earlier logs/probe witness remain private; they are not successful evidence or real-camera failures.

### Research contract and meaning for porting

Context/config allocations must already be initialized. Sparse tables have at most 15 points; for count ≥2, CTs must lie within 2000–10000. Inputs and output/scratch regions must be disjoint. Selected interpolated axes are finite and ordered, and selected point counts agree with each other and the baseline count. Unsupported inputs return `0xfffffffe` before mutation; original errors 30/33 retain their original partial-write behavior. These are bounded research APIs, not an untrusted-input camera adapter. Active E-ND white-reference preparation is verified here; this is not a claim that all E-ND calibration/history/atmosphere branches are owned.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/white-lut \
  --report /private/white-lut-result.json --white-lut
# For connected entry plus LUT, use separate output/report paths and:
# --run-entry --white-lut-entry
```

| Project work | Current position |
| --- | --- |
| Recovery and original-code comparison runtime | Working and verified |
| AWB reconstruction and verification | Current phase: major numerical/downstream stages, entry and white-reference preparation are owned; remaining user/control/detection connections are next |
| Phone statistics, sensor calibration and app integration | Still required before a representative phone trial |
| HNCS/pixel colour rendering | Separate unfinished work, beyond white-balance gains |
| Physical capture validation and release build | Follows the relevant integration work; no new APK in this checkpoint |

The immediate next boundary is `scene_awb_user_proc`, followed by statistics-difference checking and remaining dispatch/detection. Keep the generic-phone architecture and approximately 12.5 MP single-RAW route. Main and Native1C remain unchanged.


## User calibration preparation checkpoint

`hb_user_prepare.c/.h` owns the import prefix of `scene_awb_user_proc`, from `0x4b09c0` to the boundary before `0x4b1624`. The owned code has no original-firmware callbacks. It consumes base calibration requests, imports E-ND calibration groups, sorts reference keys stably as unsigned integers, computes wrapped Q12 ratios and publishes temperature-correction rows. Original statuses 83/84 preserve request consumption and any preceding successful stage writes. An E-ND group without an exact-1 request stops the group loop, leaving later group requests pending; baseline calibration is disabled only when all requested groups finish.

The module also owns the calibration gain getter, manual LUT refresh and the mode-request helper. The getter's upper endpoint writes CT 10000 into context even when the requested CT is below 10000; this is distinct from the existing statistics calibration helper. Manual refresh preserves zero-divisor AArch64 division behavior and wrapped shifts. The mode helper retains the previous mode when no change occurs and refreshes three pending flags from exact-1 enable flags. It is directly compared; the connected remainder still executes the original mode helper.

`USER_PREPARE_RESULT.json`: **5,529 checks, zero mismatches**:

- 384 calibration-getter calls, including endpoints, interiors, large unsigned values and aliased red/blue outputs with canaries.
- 256 manual-LUT calls and 256 base-import calls, comparing complete context and configuration immutability.
- 256 mode-helper calls comparing complete context; the original helper has no defined return-status contract.
- 512 complete original user-processing comparisons: 384 independent cases and 128 stateful calls. Restore the input, run the owned prefix, and on success continue the unmodified original user routine at `0x4b1624` through `user_entry.S`.
- The user remainder runs 345 times. Across direct base-import and complete-user comparisons, 161 original status-83 and 48 status-84 returns match. Prefix state changes include 209 base imports, 297 E-ND group imports and 242 temperature imports; these are overlapping activity counters.
- 24 owned-only unsupported-shape checks are included, separately from original equivalence. The original configuration is retained unchanged.

`USER_PREPARE_ENTRY_RESULT.json`: **8,187 checks, zero mismatches**, against **1,431 actual full original controller calls**. The replacement path uses owned entry → white LUT → user calibration prefix → original user remainder → original outer remainder. All 920,560 context bytes, 1,502,800 config bytes, 1,000 REAWB-handle bytes and final status match. There are 853 entry early returns, 32 LUT-error returns, 546 user-prefix executions, 72 user-error returns (48 status 83; 24 status 84) and 474 successful continuations. Coverage retains 144 scheduling boundaries, 256 stateful calls and seven native-format synthetic frames, three with E-ND enabled; two frames submit calibration requests. Ninety-six added controller fixtures cover calibration requests and error routing.

The test-only outer adapter now initializes the saved-canary pointer register for the new `0x471e78` continuation. Its immediate mode-2 return uses that register before another original call can initialize it. The first connected trial failed in this adapter; correcting the register setup makes the complete suite pass. The failed probe/logs are private diagnostic evidence, not a firmware algorithm failure. The existing owned scene → history → atmosphere → post → passive REAWB → diagnostics → shading → completion comparison was rerun after this shared-adapter change: `USER_PREPARE_DOWNSTREAM_REGRESSION.json`, **302 comparisons, seven synthetic frames, zero mismatches**. It is still a separate path from the new prefix.

### Bounded user-preparation contract

Use already initialized context/config allocations and distinct context/config storage. Base calibration supports at most two points; E-ND supports at most two groups with two points each; temperature imports support one or two rows, each containing ten ratios. The temperature count uses its low byte, matching the original. Zero temperature rows are rejected because the original sorting path underflows its loop bound. Manual LUTs support at most 15 points, a research limit rather than a proved full struct capacity. Getter outputs are valid uint32 pointers; they may alias each other and are external to context/config. Shape guards return `0xfffffffe` before prefix mutation; supported original validation failures retain partial state changes. This is not a production untrusted-input API.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/user-prepare \
  --report /private/user-prepare-result.json --user-prepare
# Separate output/report paths for controller integration:
# --run-entry --user-prepare-entry
# Shared-adapter downstream regression:
# --pipeline --diagnostics-pipeline
```

We remain in AWB reconstruction and original-code verification. The full user stage, outer dispatch/preparation and detection connections remain incomplete. Active REAWB/linked storage, genuine captured frames, phone calibration/integration and HNCS photographic rendering remain separate boundaries. No new APK was built or installed; main and Native1C are unchanged.


## E-ND unit-calibration request checkpoint

`hb_user_e_nd.c/.h` owns the request helper at `0x4af328`, temperature-dependent calibration lookup at `0x4acc10` and its per-row lookup at `0x4ac718`. The module calls only owned code. It selects a unit profile by ID, checks requested group/point keys against the profile, clamps the integer-decoded request temperature to 20–30, and calculates relative correction against the reference profile's temperature. Temperature rows use signed 16-bit keys; E-ND point keys and stored gains are unsigned 16-bit. Endpoint selection, interpolation, uint32 multiply/shift wrap, integer truncation and uint16 output truncation match the original. The first E-ND point must have key 1 and receives unity gains.

The original request helper's return register has no defined status contract and its caller ignores it. The owned API returns zero for supported processing, including rejected requests. An exact-1 pending request is consumed. A failed profile/key/count/gain check clears calibration validity and activation, preserving any already-written group count, keys or gains. A valid request sets validity and enables the correction when the E-ND enable byte is any nonzero value. Non-1 pending flags leave everything untouched. This behavior is distinct from earlier imports whose errors 83/84 abort user processing.

`USER_E_ND_RESULT.json`: **7,446 checks, zero mismatches**:

- 512 original per-row lookups and 512 two-dimensional temperature lookups, with endpoint/interior queries, signed and unordered keys, duplicate keys, aliased outputs, output canaries, NaN/infinities and zero-temperature-table unity fallback.
- 512 direct unit-request calls comparing the complete context/config/REAWB handle; compare owned supported-status zero, not the original helper's unspecified return register.
- 320 complete original user comparisons: 256 independent cases and 64 stateful calls. Restore the same input, run owned calibration imports and the unit helper, then enter original user remainder `0x4b162c` through the existing test-only ABI adapter. All 320 remainder calls finish with matching status and state.
- Across direct/complete-user request cases: 175 accepted and 550 rejected exact-1 requests; 499 rejected requests leave partial table writes. These counters overlap with the call totals. Requests missing a profile, mismatched counts/keys, zero effective channels, truncated-zero outputs and consumed-request repeats are covered.
- 21 owned-only shape-guard checks are included separately from original equivalence, including verification that a later unsupported request is rejected before earlier calibration imports mutate state.

`USER_E_ND_ENTRY_RESULT.json`: **8,571 checks, zero mismatches**, against **1,495 complete original controller calls**. The replacement path is owned entry → white LUT → calibration imports → unit request → original remaining user processing → original outer remainder. Complete context, config, REAWB handle and status match. There are 853 entry early returns, 32 LUT errors, 610 user-prefix calls, 72 earlier calibration errors (48 status 83, 24 status 84) and 538 continuations. New unit requests yield 26 acceptances and 32 rejections; rejected unit requests continue processing instead of becoming new outer errors.

The connected suite adds 64 unit-request fixtures and retains 144 scheduling boundaries, 256 stateful calls and seven native-format synthetic E2 frames. Three native frames enable E-ND, and two submit both earlier calibration imports and unit requests. Active unit-gain application later in the controller still uses the original routines; this checkpoint owns request preparation and the temperature-lookup dependency, not all E-ND statistics/history/atmosphere paths. No original function is patched. Owned intermediate boundary dumps are diagnostic snapshots; original mid-boundary state is not independently captured.

### E-ND request research contract

Use already initialized, separate context/config allocations. Temperature tables support at most eight rows, each with 1–8 points in a 52-byte row; the point-count byte ignores the following byte, matching the original. Unit lookup supports at most two 116-byte profiles, two groups per matching request, and at most eight points per matching group. These are explicit bounded research limits. Mismatched counts may be rejected by the original validation path before any corresponding array access; unsupported shapes that would reach an unsafe loop return `0xfffffffe` before mutation. Zero point count is supported in unit groups, but not temperature rows. Outputs must be valid uint32 storage outside the inputs and may alias each other. These APIs are not an untrusted-input production adapter.

```sh
python3 hasselblad_native_audit/awb_original_runtime_20261021/run_full.py \
  --firmware-root /private/extracted --ndk /tools/android-ndk-r27 \
  --qemu /tools/qemu-aarch64-static --private-output /private/user-e-nd \
  --report /private/user-e-nd-result.json --user-e-nd
# For controller integration, use separate output/report paths and:
# --run-entry --user-e-nd-entry
```

This advances AWB preparation and original-code verification. Remaining manual/user controls and dispatch/detection connections come next. Phone-specific calibration, Camera2 input mapping, coherent one-time WB integration and finished-image HNCS rendering/validation remain separate work. Main and Native1C remain unchanged; no APK was built or installed.


## Manual sample selection and E-ND application checkpoint

`hb_user_manual.c/.h` replaces manual-sample processing beginning at original `0x4b162c` through the branch to mode requests at `0x4b16a8`. Its numerical code contains no original-function callbacks. It reuses owned calibration lookup, E-ND row/temperature lookup and `hb_temperature_calibrated`, with the caller supplying the private isotemperature table. It also implements golden CT/amount lookup and temperature, unit and golden E-ND update helpers (`0x4ac250`, `0x4ac390`, `0x4aca10`, `0x4ac870`, `0x4ac510`). Unit and temperature point getters share original address `0x4ac718`.

Behavior preserved: nonzero sample count forces recomputation; otherwise only pending-byte value1 recomputes. No request/no samples clears the valid byte. Selected uint16 indices beyond the statistics count are skipped, as are samples with zero red, blue or validity fields. Duplicated indices count repeatedly. Base calibration precedes golden, unit and temperature corrections, each using wrapped uint32 multiplication then Q12 shift. Sums also wrap before unsigned averaging. Empty selection clears validity but retains previous result values. A successful selection writes mean R/B, CT, tint and validity; the original ignores temperature-conversion errors, leaving initially zero outputs to clamp to CT2000/tint0. Finite outputs clamp to CT2000..10000 and tint-99..99. No conversion error is promoted into a new user-stage failure.

Preserved key-width details: unit selection uses low16 CT and uint16 row keys, but interpolation reads each selected key as a BYTE. Golden amount selection reads uint32 keys and interpolation again reads their low bytes. Temperature rows use signed16 keys. Temperature/unit/golden updates publish their original cache fields. A zero-row temperature lookup is supported by the earlier getter, but the active temperature update requires a nonempty table; the owned updater rejects zero rows before mutation.

Research bounds: initialized distinct context/config allocations, <=64 selected indices, <=1024 statistics; base calibration <=2 points; temperature1..8 rows with1..8 points; unit1..2 rows with1..8 points; golden1..2 profiles with1..8 amounts and1..2 CT points. Each API preflights its own relevant shapes before mutation. Earlier imports in the composed prefix can already have mutated context when manual preflight runs; this is not a transactional whole-prefix API. The prior calibrated-temperature model contract remains required. These are bounded research interfaces, not production parsers or claims of exhaustive device coverage.

`USER_MANUAL_RESULT.json`: **3,813 checks, zero mismatches**. 320 golden leaf calls,480 E-ND update calls,224 whole-user replacement comparisons including32 stateful calls;127 selections publish results and97 clear validity.36 included checks exercise owned-only shape guards. Getter outputs/canaries and input immutability are compared; update/user comparisons cover all920560 context bytes,1502800 config bytes,1000 REAWB bytes and status. Coverage includes endpoints, nonfinite amount/temperature inputs, byte-key truncation, zero channels, wrapped products, duplicate/out-of-range indices, inactive non-1 flags, singular conversion matrices and output aliasing.261 private binary dumps and53 saved original/owned context pairs.

`USER_MANUAL_ENTRY_RESULT.json`: **8,955 checks, zero mismatches** against **1,559 complete original controller calls**. 853 entry returns,32 LUT errors,674 user-prefix executions,72 earlier calibration errors and602 original remainder continuations. Includes64 added manual fixtures,144 scheduling boundary cases,256 stateful entry calls and7 native-format synthetic frames,3 with E-ND enabled. A four-index selection is submitted at frame1 and refreshed at frame4; its persistent count exercises manual selection on frames1..6.303 private binary dumps and45 saved context pairs. Original user remainder starts at`0x4b16a8`, outer remainder at`0x471e78`. The unchanged test adapter reconstructs the original stack/register/TLS frame; no original code is patched. Owned intermediate snapshots are not independent original-boundary captures.

No numerical mismatch was observed. An initial build caught C tokenization of a hexadecimal literal immediately followed by `+`; spacing was corrected before execution. Unchanged downstream implementations and completion adapter did not require another downstream regression. Full user processing, a wholly owned controller, authentic camera statistics, phone calibration and HNCS/pixel rendering remain outside this checkpoint. No APK was built or installed; main and Native1C are unchanged.

Reproduce using standard `run_full.py` runtime arguments with `--user-manual`, or `--run-entry --user-manual-entry`, and separate private output/report paths. Private inputs/logs/disassembly/dumps remain outside GitHub; owned source and safe reports are on the recovery branch.


## Temperature, tint and direct-gain control checkpoint

`hb_user_controls.c/.h` owns the inverse converter `scene_awb_ct_tint_to_gain` (`0x4917b0`), manual result publication/snapshot/four recalibrations (`0x4a3610`, `0x4a38f0`, `0x4a39d8`, `0x4a3cc0`, `0x4a3bc8`, `0x4a3ad0`), CT/CT-tint/direct-gain handlers (`0x4adc68`, `0x4ae3a8`, `0x4aeb40`) and their ordered caller sequence. Existing owned mode switching, matrix lookup, calibrated temperature conversion, golden gain scaling, base calibration and E-ND updates are reused. No owned numerical function calls original code.

The inverse converter receives the private31x4 isotemperature table through the existing model. It selects reciprocal-temperature rows, reconstructs the tint-offset chromaticity with the original mixture of float/double operations, applies the calibrated matrix, normalizes each gain to the largest channel and caps low/overlarge channels at10 before scaling and saturating uint32 conversion. NaN/infinity cases and output alias order are preserved. Inputs/outputs must be outside each other's storage; output pointers may alias each other. The existing initialized temperature/matrix-table contract applies.

Manual-result publication writes two raw triples, two scaled triples, duplicated CT/tint fields, a mapped uint16 label and flag, then copies the entire156-byte record including otherwise untouched fields. Snapshot copies two24-byte raw blocks into golden-history fields. Recalibration divides four R/B pairs after a wrapped32-bit left shift by12; zero R/B divisors return89 before those gain writes. Publication/helper label is bounded0..8 in the owned research API. Input triples must be separate from context.

CT-only request byte0xb14c4 must equal1; desired uint32 CT is0xb14c8. Consume the request, clamp CT2000..10000 and select mode at config0x18. Mode0 takes R/B from context0xd68/0xd6c with16-byte stride and floor((CT-2000)/100), computes tint from those gains, scales via existing golden conversion, but publishes the requested/clamped CT. Mode1 reads cached tint at0x1278 with8-byte stride and invokes the inverse converter at4096 and config0x80 scales. Other modes return157 after request consumption.

CT/tint request byte0xb14cc, desired CT0xb14d0, float tint0xb14d4, config mode0x1c. It does not clamp CT. Mode0 uses the same indexed gain table and computed tint, ignoring the submitted tint; mode1 uses the submitted CT/tint directly. The bounded mode0 contract permits indices0..80 (CT2000..10099); out-of-range indexing is rejected before consumption instead of invoking unsafe original access. Unsupported shapes are research guards, not original validation statuses.

Both CT routes publish the manual record, set calibration CT, update base calibration, snapshot raw gains, then run enabled exact1 E-ND temperature/unit/golden updates and corresponding recalibrations, followed by base recalibration. Success sets byte0xc534. Original statuses retain consumed requests and all earlier writes, including publication before later status89. Direct-gain request byte0xb14d8 has R/G/B at0xb14dc/e0/e4: consume then reject any zero channel with81; otherwise compute CT/tint, scale, publish and set0xc534. It does not run the CT-route recalibration sequence. Status91/92 from calibrated conversion propagates. `hb_user_controls` calls mode switch, CT, CT/tint, gain in that order, stopping on error.

Shape limits inherit base<=2, temperature1..8x1..8, unit1..2x1..8 and golden1..2x1..8x1..2. Each handler validates relevant shapes before its own mutation; earlier handlers/imports/mode updates may already have mutated state. This is not an atomic whole-prefix API. Initialized fixed lookup arrays and valid private model/calibration allocations are prerequisites.

`USER_CONTROLS_RESULT.json`: **6,073 checks, zero mismatches**.384 inverse conversions,576 manual-result helper calls,592 direct control-handler calls and248 whole-user comparisons (48 stateful);24 included owned-only guard checks. Handler/user outcomes include72 status81,87 status89,40 status91,63 status92 and78 status157 returns. Coverage includes successful populated lookup tables, request flags other than1, CT endpoints/rounding, zero/wrapped/scaled gains, NaN/infinite tint, aliased converter outputs and canaries, preserved untouched result fields, singular matrices, and24 targeted CT/user comparisons forcing base/temperature/unit/golden recalibration failures.333 private dumps,76 exact saved context pairs,28 verified source/header hashes.

`USER_CONTROLS_ENTRY_RESULT.json`: **9,387 checks, zero mismatches** against **1,631 complete original controller calls**.853 entry returns,32 LUT failures,746 user-prefix calls,104 user failures (including the prior48 status83 and24 status84),642 original user/outer continuations.72 added control fixtures;144 scheduling cases;256 stateful entry calls;7 native-format synthetic frames,3 E-ND-enabled. Native frames2/4/6 submit CT, CT/tint and direct-gain requests.359 private dumps,53 exact saved context pairs,33 source/header hashes. Whole context/config/REAWB/status match. Original user remainder now starts0x4b16d4; the existing stack/register/TLS adapter's code is unchanged. The original firmware is unpatched; intermediate owned snapshots are not independent original-boundary captures.

The first passing trial exposed a coverage gap: original initialization leaves the manual gain table empty. Final fixtures explicitly populate that table and cover both success and error propagation. Every numerical comparison passed; no algorithm mismatch was found. Shared downstream numerical code and completion adapter are unchanged, so no redundant downstream regression was run. Full user processing and the wholly owned controller remain unfinished, as do authentic phone inputs/calibration, app integration and HNCS photographic rendering/validation. No APK built or installed; main and Native1C unchanged.

Reproduce with standard runtime arguments plus `--user-controls`, or `--run-entry --user-controls-entry`, and separate private output/report paths. Source and safe reports are on the recovery branch; private tables, original logs, context dumps and disassembly stay outside GitHub.


## Complete user-control stage — 21 October 2026

`hb_user_finish.c/.h` implements the final numerical requests in `scene_awb_user_proc` from `0x4b16d4`: two exact-1 pending toggles, fixed-result validation/publication, persistent toggle synchronization and the bounded override request. `hb_user_process` composes owned calibration imports, unit requests, manual samples, mode/CT/tint/gain controls and this final stage. The complete user stage now has no original numerical callbacks within the documented research bounds; diagnostic logging is excluded. No original user remainder is executed by the owned path in the complete-stage controller mode. The outer original continuation remains `0x471e78`.

Fresh evidence:

- `USER_FINISH_RESULT.json`: **2,553 checks, zero mismatches**. 64 gain-record helper calls, 260 original-tail comparisons and 328 complete-user comparisons, including 64 stateful calls. 254 fixed requests accepted / 129 rejected; 250 overrides accepted / 133 rejected; 190 earlier user errors preserve unprocessed final requests. Eight owned-only shape-guard checks are included. All 920,560 context bytes, 1,502,800 config bytes, 1,000 passive REAWB bytes and defined statuses are compared on each tail/full-user call.
- `USER_FINISH_ENTRY_RESULT.json`: **9,771 checks, zero mismatches**, against **1,695 complete original controller calls**. 853 entry returns, 32 LUT failures, 810 full-user calls, 104 user failures and 706 original outer continuations. **Zero original user-remainder calls**. Includes 64 new final-request fixtures, 144 scheduling cases, 256 stateful calls and seven native-format synthetic frames (three E-ND enabled). Frames1 and5 submit fixed/override requests; frame2 rejects a fixed request to release the override. Earlier CT/tint/gain and calibration submissions remain covered.
- Both suites passed on their first execution. Existing numerical modules, firmware and entry adapters were unchanged. Unchanged downstream stages were not rerun. Reports retain the actual `*_trial` output-directory names from those successful executions; these are the accepted checkpoint evidence.

Request semantics:

- Exact-1 pending bytes `0xb1f84` and `0xb14f0` are consumed and their payload bytes copied unchanged to `0x190` and `0xf028`. Other pending values do nothing.
- Fixed request `0xb1cf8` is consumed. Both unsigned CT fields must be in2000..10000, and each of two records must contain six nonzero uint32 gain words. The standalone validity helper returns246 for valid /247 for invalid; it imposes no maximum gain. Rejection clears `0xd338` and preserves old result records. Acceptance sets that flag, copies156 bytes to both `0xd33c` and `0xd3d8`, updates CT/base calibration, and multiplies the eight R/B fields in the first copy by the corresponding base calibration using wrapped32-bit multiplication then right shift12. The second copy remains uncalibrated. Zero and overflowing calibration products preserve original arithmetic.
- Persistent byte `0xb1ff6` is synchronized to `0x42d3`; a change sets dirty flag `0x42d2`. Equal values leave that flag unchanged.
- Override pending byte `0xb1ff8` is consumed. Unsigned count must be<=1024; float CT must be zero or2000..10000; all twelve uint16 weights must be<=256. As in the original comparison instructions, NaN is accepted and infinities rejected. Rejection clears `0xd324` and preserves old output fields. Acceptance sets that flag and copies count/CT/opaque payload to `0xc5a0`, `0xc6d4`, `0xc6e4`. The opaque32-bit payload is not validated; the twelve weights are validated but not copied here. Final-request validation failures return0 and communicate rejection through validity flags.

`hb_user_finish` rejects an accepted fixed request with more than two base calibration points before any tail mutation. Invalid fixed requests do not require that table and retain the native rejection path even with an oversized count. The complete wrapper preserves the earlier modules' bounds and stops on their first error; earlier stages may already have mutated context. This is not a production arbitrary-input contract or exhaustive coverage of every possible state.

Reproduce with `run_full.py --user-finish`, or `--run-entry --user-finish-entry`, plus the established firmware/NDKr27/QEMU/private-output/report arguments. The private packet is `Hasselblad_User_Finish_Evidence_PRIVATE_20261021.zip`; owned source and safe reports are in GitHub, with original binary data and disassembly kept private.

Next: statistics-difference checking (`0x4aacb8`), then mode dispatch and remaining ROI/sensor/parsing/detection/face dependencies. Join this owned entry/user path to the separately verified scene-through-completion chain. Phone input mapping/calibration, integration and photographic colour/HNCS validation remain subsequent boundaries. Main and Native1C are unchanged; no APK was built or installed.


## Statistics-difference and dispatch gate — 21 October 2026

`hb_stat_difference.c/.h` owns the numerical `scene_awb_stat_diff_chk` stage (`0x4aacb8`), including diagnostic-counter advancement, REAWB flag inspection, ROI hold timing, periodic refresh, wrapped R/B differences and update/reuse state. `hb_run_dispatch.c/.h` connects it after the complete owned user stage and owns outer suspension, mode selection, automatic refresh/reuse selection and the refresh scratch clears. No owned function calls original firmware. Diagnostic logging is excluded; its context counter is preserved.

Fresh evidence:

- `STAT_DIFFERENCE_RESULT.json`: **2,569 checks, zero mismatches**, against640 original calls. 388 refresh /252 reuse results; eight missing-handle/disabled returns;132 diagnostic-counter changes;80 stateful calls; eight owned-only guard checks. Cases include all12 ROI positions, signed timer endpoints and a complete30-call hold/release sequence, period0/1/2/3/255, exact threshold boundaries, uint32 wrap/INT32_MIN, NaN/infinite frame rates, diagnostic counter overflow, and absent REAWB handles. All920560 context,1502800 config and1000 handle bytes plus status compare exactly per call.
- `STAT_DIFFERENCE_ENTRY_RESULT.json`: **10,841 checks, zero mismatches**, against **1,747 complete original controller calls**. 853 entry returns,32 LUT failures,862 user calls and104 user failures. The owned dispatch handles699 suspended returns,31 automatic refreshes,8 automatic reuses,8 manual selections,8 custom selections and4 error completions. Only59 downstream original continuations remain in this suite; there are zero original user-remainder calls. Existing144 scheduling cases,256 stateful entry calls and7 synthetic native E2 frames remain covered. 52 additional cases check dispatch on initialized/imported state, including four missing-handle errors through original outer recovery.
- Direct and initial integrated runs passed on first execution. The integrated suite was then extended to cover the new error-completion route; the final run also passed. Original firmware, previously owned numerical modules and ABI adapters were unchanged. The separately owned downstream chain was not redundantly rerun.

Exact semantics and bounds:

- Context sample count must be<=1024 and ROI count<=12. Zero samples are supported whenever a bypass/force/hold/periodic route avoids division. Reaching numerical difference with zero samples returns `HB_PREP_UNSUPPORTED` before mutation; the original fatal path is deliberately not invoked. Other shape guards also precede writes in the direct stage. The dispatch wrapper sets the busy marker before calling this stage, so a research guard there retains that earlier write.
- A nonzero diagnostic uint16 period at `0xb6962` advances the uint32 counter at `0xb6964`, including overflow. Diagnostic log output and sampled logging calculations are excluded.
- With an available handle, exact switch byte1 at handle+`0x1c` and mode byte0 at+`0x20` force refresh. The handle is read only; this does not implement active REAWB processing. Either disabled configuration byte at `0x1531a8`/`0x1531ac` also forces refresh. A missing handle combined with disabled checking returns `UINT32_MAX`, matching the original; other supported routes return0.
- Any nonzero ROI flag at `0x98f48+32*i` sets active byte`0xef3c` and signed16 hold timer`0xef3e` to30. Without an ROI, decrementing the timer to a nonnegative value keeps activity set. An expired timer is retained; byte`0xdb60` or word`0xeeac` can restart it at30. Otherwise the active byte clears.
- An active hold forces refresh. Otherwise unsigned frame counter`0x9c1a0` modulo config byte`0x1531ad` equal to1 forces refresh. For period0, the original ARM division produces quotient0, leaving the frame counter as the remainder.
- Difference sums the wrapped signed-absolute R/B deltas between current records at`0x84f48` (stride20) and previous records at`0xf450` (stride40), wraps the sum to uint32, divides by sample count and compares to threshold`0x1531b0`. At/below threshold, refresh byte`0xd328` clears while history byte`0xd329` remains unchanged. Above threshold, the old refresh byte moves into history; refresh clears only when frame rate`0x9c1a4`>=30 and prior history equals1. NaN follows the below-threshold-rate branch, consistent with the original floating-point condition.
- Dispatch returns immediately when context`0xb2020` equals2. Otherwise it sets busy word`0x174` to2. Mode`0x194` below2 uses the difference gate; a nonzero refresh or force byte`0xd32a` clears diagnostic scratch`0xa8510` length`0x34c` and prior-statistics scratch`0xf450` length`0x75af8`, then selects refresh. Mode2 selects the manual body; larger unsigned values select the custom body. Those bodies remain external.

The comparison adapter resumes original code at these explicit boundaries:

| Owned dispatch action | Original remainder |
| --- | --- |
| Automatic refresh, after scratch clearing | `0x471f10` |
| Automatic reuse | `0x472274` |
| Manual mode | `0x471ff0` |
| Custom mode | `0x472100` |
| Error completion/recovery | `0x4722b0` |
| Suspended | No remainder |

Reproduce with `run_full.py --stat-difference`, or `--run-entry --stat-difference-entry`, plus established firmware/NDKr27/QEMU/private-output/report arguments. The private packet is `Hasselblad_Stat_Difference_Evidence_PRIVATE_20261021.zip`; owned source and safe reports are in GitHub. These remain bounded synthetic comparisons, not exhaustive arbitrary-state or phone-colour validation.

Next: ROI synchronization/processing (`0x551920`/`0x4c02f0`, including sync calculation/reinitialization), remaining sensor (`0x4b60b0`), parsing (`0x4960c8`), detection (`0x497d18`) and face (`0x4ba158`) processing; then finish mode bodies and connect the separately verified scene-through-completion chain. The existing owned automatic-statistics preparation is reusable. Phone input mapping/calibration, integration and photographic colour/HNCS validation remain subsequent work. No APK was built or installed; main and Native1C remain unchanged.


## Detector ROI processing — 21 October 2026

`hb_roi.c/.h` owns the numerical `scene_awb_roi_proc` (`0x4c02f0`) and ROI reinitialization (`0x4bfeb8`). It processes six ordered detector formats, selects a usable rectangle, constructs eight sampling rectangles, and publishes the resulting ROI to the configured destination. The implementation has no original callbacks. Logging is excluded.

Fresh evidence:

- `ROI_RESULT.json`: **1,549 checks, zero mismatches**, against **512 original calls**. This includes eight direct reinitializations, twelve invalid-zoom errors, 72 stateful calls, and twelve owned-only guard checks. Each comparison covers status, all 920,560 context bytes and all 1,502,800 configuration bytes. All six detector types produce selected regions. Coverage includes priority among enabled types, empty/pending/stale input, confidence and size thresholds, tied areas, boundary and invalid rectangles, integer zoom steps, timestamp wrap, NaN/infinite frame rates and inset values, reset/disable flags, and both publication destinations.
- `ROI_ENTRY_RESULT.json`: **11,177 checks, zero mismatches**, against **1,795 full original controller calls**. The connected replacement calls owned ROI processing 87 times, including twelve error completions. Dispatch covers 699 suspended returns, 55 automatic refreshes, 32 automatic reuses, eight manual selections, eight custom selections and four statistics-difference error completions. There are 107 original downstream continuations, 87 explicit original ROI-sync callbacks, and zero original user remainders. The added 48 cases cross all six detector types with both automatic paths, empty/stale input, reset, eight-record lists and zoom errors. Existing seven synthetic native E2 frames, 144 scheduling cases and 256 stateful entry calls remain covered.
- Both implementations passed their first comparison runs. The integrated fixture routing was then adjusted to exercise each detector type through both refresh and reuse, and the final run also passed. Previously owned numerical modules and ABI adapters were unchanged. No unrelated downstream retesting was needed.

Exact behavior and research bounds:

- Processing requires exact enable byte1 at context `0xd900`; exact reset byte1 at `0xd901` invokes reinitialization. Other enable values bypass processing. Active non-reset calls reject any of the six detector counts above eight with `HB_PREP_UNSUPPORTED` before mutation. This is a deliberate bounded research ABI, not a claim about the original maximum list capacities. Disabled/reset calls bypass these shape guards. The caller supplies initialized context/configuration buffers of the documented sizes.
- Enabled detector configurations are visited in their original order. A recent higher-priority input can stop later processing even without a pending record. Age uses wrapped uint32 frame subtraction divided in float32 by the frame rate. The original ordered/unordered floating-point branch behavior is preserved.
- Zoom below10000 returns225. The scale uses unsigned integer division by10000 before conversion to float32. Candidate confidence and scaled size must exceed their thresholds. Selection uses maximum clipped overlap area with an earliest-record tie; selected confidence publication and pending/state flag changes are retained even if no usable geometry results.
- Three detector formats store center coordinates; their centers are converted to top-left coordinates with the original zero clamp. Valid geometry is inset and divided into eight samples. The first format retains the regular bottom-row positions; the other five shift the two bottom samples by half a cell. Floating-point operation order, including double intermediates for inset centering, is retained.
- Each processed type publishes a164-byte ROI structure through the common staging region. Configuration route word1 selects `0xef54`; other values select `0xb2054`. Pending, prior-frame, activity and publication flags are updated as in the original. Reinitialization clears all six pending words and ROI output structures, the two destinations and common staging structure, resets the request byte and sets the publication flags.

The test adapter explicitly invokes original `scene_awb_sync_roi_proc` (`0x551920`) before the owned ROI stage. Synchronization and its homography/profile calculation are **not owned yet**. The automatic original continuations now start after ROI processing:

| Path | Original remainder |
| --- | --- |
| Automatic refresh | `0x471f30` — automatic statistics |
| Automatic reuse | `0x472294` — post processing |
| Manual mode | `0x471ff0` |
| Custom mode | `0x472100` |
| Error completion/recovery | `0x4722b0` |
| Suspended | No remainder |

Reproduce with `run_full.py --roi`, or `--run-entry --roi-entry`, plus the established firmware/NDKr27/QEMU/private-output/report arguments. The latter implies the owned statistics-difference/dispatch, complete user and white-LUT prefix. Private evidence is `Hasselblad_ROI_Evidence_PRIVATE_20261021.zip`; owned source and safe reports remain in GitHub. The evidence is bounded and synthetic; it does not validate arbitrary device state or photographic colour.

Next: own ROI synchronization (`scene_awb_sync_roi_proc`, `scene_awb_sync_roi_calc` at `0x551570`, and matrix helper at `0x551088`), then remaining sensor (`0x4b60b0`), parsing (`0x4960c8`), detection (`0x497d18`) and face (`0x4ba158`) processing. Complete the mode bodies and connect the separately verified scene/history/atmosphere/post/completion chain. Existing automatic-statistics preparation is reusable. Phone input/calibration, app integration and photographic colour/HNCS validation remain subsequent work. No APK was built or installed; main and Native1C remain unchanged.


## ROI synchronization — 21 October 2026

`hb_roi_sync.c/.h` owns matrix-based coordinate mapping (`scene_awb_sync_roi_calc_use_h_matrix`, `0x551088`), profile/default calculation (`scene_awb_sync_roi_calc`, `0x551570`) and synchronization/publication (`scene_awb_sync_roi_proc`, `0x551920`). The connected prefix now uses owned synchronization followed by the previously owned detector ROI stage. There is no original ROI-sync callback in `--roi-sync-entry`. Original automatic mode remainders still begin at `0x471f30` and `0x472294`.

Fresh evidence:

- `ROI_SYNC_RESULT.json`: **1,123 checks, zero mismatches**, against368 original calls:112 matrix,112 calculation and144 synchronization calls. Thirty matrix rejections,32 stateful calls and18 owned-only guard checks. Status and every context/configuration byte compare exactly. Cases cover all three matrix-record positions, reversed/equal sensor names, unknown IDs and target masking, zero/odd/extreme dimensions, crop saturation, negative/sheared/translated transforms, NaN/infinity, threshold equality, fixed-layout mode, all six profile positions, missing/duplicate profiles, wrapped rectangle differences, stale publication flags and disabled states. An additional48 deterministic finite transforms per entry point exercise arithmetic beyond the boundary fixtures.
- `ROI_SYNC_ENTRY_RESULT.json`: **11,457 checks, zero mismatches**, against **1,835 full original controller calls**. Owned synchronization and detector ROI processing each execute127 times, with **zero original synchronization callbacks** and twelve ROI error completions. Dispatch covers699 suspended returns,75 automatic refreshes,52 automatic reuses, eight manual selections, eight custom selections and four difference-error completions. There are147 downstream original continuations and zero original user remainders. Forty added cases cover both automatic paths; eight activate synchronization and detector ROI in the same frame to verify priority and publication interactions. Existing seven synthetic native E2 frames,144 scheduling cases and256 stateful entry calls remain covered.
- The direct and integrated suites passed on first execution. Integration was then extended with the eight simultaneous-activity cases and passed again. Prior owned numerical modules and ABI adapters were unchanged; no unrelated stage was retested.

Model and exact behavior:

- `hb_roi_sync_model` is caller-supplied: three sensor names, eight normalized endpoint templates, eight fixed rectangles and eight fallback rectangles. The test harness reads the private original name/template data from the initialized oracle; no original table payload or callback is embedded in the implementation. This is a research model interface, not phone calibration. The original three-ID mapping is retained for IDs12,15,19; unsupported IDs return matrix failure, allowing the profile/default path.
- Matrix lookup picks the first of three records containing both source and target names. The target uses the low six bits of the config uint16. Input/output/record dimensions must be nonzero; absolute first matrix coefficient below1e-5 rejects. A strictly higher configured mode threshold selects the fixed rectangles. Otherwise the first six matrix coefficients transform the original pairs of corners, with pairwise numeric min/max, normalized endpoints, output crop subtraction and width/height subtraction. This deliberately preserves the original operation order and pairwise extrema rather than substituting a general homography implementation. No perspective divide is added.
- Crop offsets subtract separately halved unsigned dimensions in float32, saturate to uint32, then convert back to float32. IEEE unordered behavior, float rounding, signed zero and wrapped integer profile differences are preserved; compilation disables floating-point contraction.
- Calculation tries the matrix route, then the first matching profile. A successful matrix/profile writes eight active flags and sets `0xda50` and uint16`0xd9a8` to1. Default calculation writes inactive fallback rectangles without clearing those preexisting flags. Processing publishes config enable to `0xd9ac`, clears `0xd9a8`, and runs calculation only for exact config enable1 with gate byte`0x990dc` zero. If publication byte`0xda50` equals1 afterward, it copies164 bytes from `0xd9b0` to `0xb2054`, clears that byte and sets `0xb20f4`/`0xb2050` to1. This includes the original stale-flag fallback behavior.
- Research guards require all matrix/model names to terminate within16 bytes. Calculation and active processing require profile count<=6, the number of complete136-byte records fitting the established1,502,800-byte config buffer. Unsupported shapes return `HB_PREP_UNSUPPORTED` before writes. Disabled processing needs no model and retains its original bookkeeping writes. Matrix failure returns `UINT32_MAX` without mutation. Logging is excluded.

Reproduce with `run_full.py --roi-sync`, or `--run-entry --roi-sync-entry`, using the established private firmware/NDKr27/QEMU/output/report arguments. Private evidence: `Hasselblad_ROI_Sync_Evidence_PRIVATE_20261021.zip`. Owned source and safe reports are in GitHub. These are bounded synthetic comparisons; full AWB, phone colour and HNCS rendering are not validated by these tests.

### Route to the first useful APK

Prioritize the automatic, approximately12.5MP single-RAW path, preserving the generic device architecture. Next implement remaining sensor adaptation (`0x4b60b0`), parsing (`0x4960c8`), detection (`0x497d18`) and face (`0x4ba158`) dependencies and compose the automatic body. Reuse existing automatic-statistics preparation and the separately verified scene/history/atmosphere/post/passive-REAWB/diagnostics/shading/completion chain. Then connect phone statistics/calibration, integrate with the app and build a bounded test APK. Keep unsupported modes explicit; manual/custom bodies and active REAWB/linked storage remain tracked but are not automatically prerequisites for an automatic-only test build. Diagnostic file I/O remains excluded.

Actual phone testing and photographic colour/HNCS acceptance are still required. Never transplant IMX861 calibration into the phone. Keep HAL metadata separate, WB applied once and colour matrices coherent. No APK was built or installed in this checkpoint; main and Native1C remain unchanged.


## Spectral sensor adaptation — 21 October 2026

`hb_sensor.c/.h` owns the bounded numerical sensor stage (`scene_awb_spec_sensor_proc`, `0x4b60b0`), ten-channel calibration gain interpolation (`0x4b4fc8`) and parameter carry-forward (`0x4b5d28`). The implementation has no original callbacks and embeds no original calibration, spectral or classifier tables. The initialized research context and configuration supply those data. This firmware stage consumes an auxiliary spectral measurement; owning its calculations does not establish that an equivalent measurement exists on a phone.

Fresh evidence:

- `SENSOR_RESULT.json`: **992 checks, zero mismatches** against242 original calls:49 calibration helper calls (including null output),48 parameter-pass calls and145 processing calls. Forty-eight calls form a changing-input sequence;26 additional checks verify owned shape guards and no mutation on rejection. Status, gains and every context/configuration byte compare exactly.
- Active coverage includes zero/one/two calibration rows, endpoint/interior/reversed thresholds, calibration requests and invalid normalization, stale/absent/out-of-range readings, zero and NaN frame rates, validity counters, two-stage smoothing and wrapped arithmetic,401-channel spectral reconstruction, zero spectral/template norms, both similarity slots, all class counts0..3, sparse feature matching, sigmoid and multiclass coupling, nested adjustment and result blending. Thirty-five varied classifier/adjustment cases include256 support vectors with15 nodes and adjustment tables at the eight-row bound. Caller-supplied data are synthetic in these fixtures. The initialized original configuration is also compared once unchanged.
- `SENSOR_ENTRY_RESULT.json`: **11,793 checks, zero mismatches**, against **1,883 complete original controller calls**. Owned sensor processing executes117 times with its enable set, using zero original sensor callbacks. Forty-eight new cases force automatic refresh across both automatic modes and24 sensor scenarios. Synchronization/ROI processing each execute175 times; twelve ROI errors still take normal completion. Dispatch covers699 suspended returns,123 refreshes,52 reuses, eight manual selections, eight custom selections and four difference-error completions. Seven synthetic native E2 frames,144 scheduling cases and256 stateful entry calls remain covered.
- Original automatic-statistics processing is an explicit117-call dependency immediately before owned sensor processing. Its enabled E-ND routes must be reconciled with the earlier bounded owned statistics implementation before full composition. The automatic refresh continuation now starts at parsing (`0x471f50`); reuse remains at post (`0x472294`). There are195 original downstream continuations and zero original user or synchronization callbacks. This is not a wholly owned controller yet.

Behavior and supported shape:

The stage handles calibration requests, validity and dropout weighting, ten-channel correction/normalization, two-stage integer smoothing,401 spectral estimates, XYZ/chromaticity and bounded temperature, spectral similarity, an RBF classifier with pair probabilities and multiclass coupling, three-level adjustment interpolation, and eleven downstream blend parameters. It preserves the original integer wrapping, saturating ARM float conversions, float/double operation order, stale-field behavior, sparse-vector early stop and sequential blending. The calibration parameter-copy overlap is preserved. The second ratio uses the first smoothed channel as its numerator; the first comparison caught an incorrect numerator and the corrected implementation matches. Logging is excluded.

Shape checks run before writes: up to two calibration rows, three classes,256 support vectors,15 nodes per support vector, class score spans inside256 slots, two similarity destinations, and three adjustment records with1..8 rows at each of the three levels. Unsupported shapes return `HB_PREP_UNSUPPORTED`. A null calibration output retains original status171. Disabled sensor processing returns zero without requiring active classifier tables. These are research ABI bounds against initialized buffers of920,560 context bytes and1,502,800 configuration bytes, not production phone input validation.

Reproduce with `run_full.py --sensor` or `--run-entry --sensor-entry`, using the established private firmware/NDKr27/QEMU/output/report arguments. Compile with floating-point contraction disabled. Never load pointer-bearing context snapshots into another process; initialize and clone in the same process. Safe source and reports are in the recovery branch; original material and raw evidence stay private in `Hasselblad_Sensor_Evidence_PRIVATE_20261021.zip`.

### Next work

Continue with parsing (`0x4960c8`), detection (`0x497d18`) and face processing (`0x4ba158`), reconcile automatic-statistics E-ND handling, then join the automatic body to the separately verified scene/history/atmosphere/post/passive-REAWB/diagnostics/shading/completion chain. For the automatic single-RAW phone build, explicitly map which auxiliary spectral inputs are actually available and define the supported absent-input route. Do not invent spectral measurements or transplant IMX861 calibration. Real phone statistics/calibration, app integration and photographic colour/HNCS acceptance remain ahead. Manual/custom bodies and active REAWB/linked storage remain tracked separately from automatic-only build prerequisites. No APK was built or installed; main and Native1C remain unchanged.


## Parsing and automatic statistics — 21 October 2026

Two remaining dependencies are now owned and connected: semantic parsing (`scene_awb_parsing_proc`,0x4960c8) and complete automatic statistics (`scene_awb_stat_auto_proc`,0x4ad6c0), including enabled E-ND unit and temperature correction. The automatic refresh path resumes the original controller at detection,0x471f60. Reuse still resumes at post,0x472294.

Fresh evidence:

- `PARSING_RESULT.json`: **484 checks, zero mismatches**, against153 original parsing calls. Forty-eight stateful calls, seven original empty-table status177 results, one oversized-grid disable and24 owned guard checks. Status and every context/config byte match. Coverage includes copy/adjustment paths, zero/one/1024-cell grids, stale masks and category counts, first-category tie priority, clipped5x5 neighborhoods, selected empty tables, one/eight-row curves, remapping with zero divisors, NaN/infinite exposure/parameters and wrapped smoothing/blending. Sixty-four varied grids and weight patterns supplement targeted cases.
- `STAT_AUTO_RESULT.json`: **650 checks, zero mismatches**, against209 original automatic-statistics calls. Unit correction enabled138 times, temperature correction138 times, both98 times; counters overlap. Forty-eight stateful calls and22 guard checks. Cases cover0..1024 statistics,0..8 ROIs, nonbinary enables, ordered correction stages, calibration gains, saturated/wrapped products, inactive ROIs, stale fields, varying E-ND amounts/temperatures, NaN/infinity and spectral normalization. Added model fixtures are synthetic.
- `AUTO_PARSING_ENTRY_RESULT.json`: **12,297 checks, zero mismatches**, against **1,955 full original controller calls**. Owned statistics, sensor and parsing each execute189 times; parsing is active40 times with four error completions. **Zero original statistics/sensor/parsing/synchronization/user callbacks** in the owned prefix. Unit and temperature correction each execute13 times. Synchronization/ROI execute247 times each, with twelve ROI errors. Dispatch:699 suspended,195 refresh,52 reuse, eight manual, eight custom, four difference errors. Seven synthetic native E2 frames (three with E-ND),144 scheduling cases and256 stateful entry calls remain covered. Forty added parsing cases and32 E-ND/statistics cases exercise both automatic modes. There are267 original downstream continuations; the whole controller is not yet owned.
- All three comparisons matched on their first completed execution. Build warnings were fixed before execution. Final captures use exact final source hashes; an incomplete capture run caused by temporary disk exhaustion was discarded and regenerated after removing reproducible development captures.

`hb_parsing.c/.h` reuses owned signed zone geometry in `hb_history.c`. It generates six zone masks, optionally remaps gains, computes5x5 neighborhood densities, applies density/weight interpolation, selects one of seven categories, normalizes/smooths category counts, interpolates exposure-dependent blend parameters and accumulates downstream results. It preserves skipped/stale fields, first-category ties, uint16 accumulation, wrapped signed smoothing and partial writes before status177. Configuration is writable because the original clears its enable byte when wrapped width×height exceeds1024. No original tables or callbacks are embedded; logging is omitted.

Active parsing bounds: dimensions/count<=1024, unwrapped grid area<=1024, four zones per adjusted category, up to eight density/weight rows and1..8 exposure rows. Empty selected density/weight tables retain original status177; excessive shapes reject before numerical writes with `HB_PREP_UNSUPPORTED`. Disabled parsing and original oversized-grid disabling retain their behavior.

`hb_stat_auto.c` composes owned statistics import, calibration, E-ND update helpers, AE information and temperature classification. Unit correction precedes temperature correction; each affects all statistics and only active ROIs. Wrapped32-bit gain products with a nonzero upper nibble saturate to65535; otherwise they shift right12. Disabled corrections publish unity gains. `hb_stat_prepare.c` exposes the unchanged numerical classification suffix as `hb_stat_auto_classify`; its earlier bounded `hb_stat_auto` entry retains its E-ND restrictions.

Complete statistics bounds:1024 samples, eight ROIs, two active calibration rows,1..15 nondecreasing LUT segment indices within0..80, existing E-ND table bounds, and1024 auxiliary spectral samples when enabled. Guards precede writes. Initialized research buffers remain920,560 context and1,502,800 config bytes; these are not production phone metadata contracts.

Reproduce direct modes with `--parsing` and `--stat-auto`; latest integrated mode is `--run-entry --stat-auto-entry`, implying the earlier sensor/ROI/user/LUT replacements. `--parsing-entry` remains an older comparison option with explicit original statistics. Use established private firmware/NDKr27/QEMU arguments, floating-point contraction disabled, and same-process initialized clones. Never restore live pointer dumps across processes.

Private evidence: `Hasselblad_Parsing_Auto_Stats_Evidence_PRIVATE_20261021.zip`. Source/safe reports are on the recovery branch; original configuration/table payloads remain private.

### Next work

Implement detection0x497d18 and face0x4ba158, then join the automatic body to the separately verified scene/history/atmosphere/post/passive-REAWB/diagnostics/shading/completion chain. The automatic-statistics E-ND gap is resolved. Then map real phone statistics/calibration and available auxiliary spectral inputs, integrate the app and build the bounded automatic single-RAW APK. Do not invent spectral measurements or transplant IMX861 calibration. Phone colour/HNCS acceptance needs actual captures. Manual/custom and active REAWB/linked storage remain tracked separately from automatic-only prerequisites. No APK was built/installed; main and Native1C are unchanged.


## Detection — 21 October 2026

`hb_detect.c/.h` owns the complete bounded detection stage originally at `0x497d18`, including its internal semantic mixing helper at `0x49a930`, outer-zone helper and multi-point interpolation. It reuses owned temperature lookup and signed zone geometry; it contains no original model/calibration tables or numeric callbacks.

- Region adjustment copies diagnostic input, checks five configured colour classes against zones, fades near-zone confidence, evaluates nested count/weight curves, preserves skipped outputs and derives the residual class. Empty selected curves return **106** after the original partial writes.
- Six temporal smoothers retain the original fixed-point intermediate precision, signed wraparound and truncation. Category coefficients accumulate into existing fields before normalization.
- Spectral and semantic blending retains the original fixed-point products, 16-bit normalization totals, zero-total fallbacks and conditional diagnostic copies. Empty semantic blending tables return **177**.
- Outer-zone masks retain semantic filtering and sequential float sampling when a grid dimension exceeds 32; output remains at most 32×32. This port bounds the underlying source grid to 1,024 cells.
- Two configurable detectors preserve independent cadence, exposure/temperature gates, positive/negative zone evidence, optional spectral curves, alternate thresholds, the 15-sample ring, publication and maximum-magnitude signed category adjustments. A rolling sum above 3,840 clears its history and returns **131**.
- Four-category hysteresis retains accumulated/stale flags, delayed category changes, previous/current state, lock/unlock counters and the final confidence curve. Its empty curve returns **247**.

Research bounds are checked before process mutation: 1,024 statistics and grid cells, four adjustment zones per set, eight nested table rows/points, one outer detector with eight zones, two scheduled detector records/IDs, 15 history entries, four/seven bounded correction destinations, and valid hysteresis category 0–3. The standalone curve API additionally rejects nonfinite queries before writes; full detection feeds it finite converted queries. Zero-count original error semantics are retained. These are pinned research layouts; initialization and model/calibration data are still external. Logging is omitted.

`DETECTION_RESULT.json`: **745 checks, zero mismatches**, against **177 original calls**, including 64 stateful calls, two status106 errors, one each of status131/177/247, and 36 owned-only guard checks. Synthetic cases exercise one/eight-point tables, 1,024-cell grids, non-square sampling, gain remapping, signed/overflow arithmetic, nonfinite blend coefficients/exposure and cold/warm state.

`DETECTION_ENTRY_RESULT.json`: **12,633 checks, zero mismatches** against **2,003 full original controller calls**. The prefix executes 233 owned detection calls, including 40 error completions; 237 statistics/sensor/parsing calls each; and 295 sync/ROI calls each. There are zero original detection/statistics/sensor/parsing/user/sync callbacks in the owned prefix. The 48 added integration fixtures cover both automatic modes; earlier seven native-format synthetic frames, 144 scheduling cases, 256 stateful entry calls, 52 reuse paths and error handling remain covered. Full context/config/passive-REAWB/status comparisons match. There are 315 original downstream continuations; original face and later mode bodies remain explicit dependencies.

The first direct run exposed the category-three semantic confidence rule: it chooses the larger of the two zone confidences, not the smaller. That was corrected before the successful runs. The first expanded controller fixture set enabled parsing without initializing its required synthetic tables and changed geometry independently of the prepared frame. That invalid test setup was replaced with valid parsing tables and preserved frame geometry; the failed development captures were discarded. A later capture run hit the inherited 20-second CPU cap; detection-entry now has a bounded 40-second CPU/60-second wall allowance. No cases were removed. Final reports were generated from fresh empty output directories and their exact source/probe/dump hashes were verified.

Reproduce with `run_full.py --detect` or `--run-entry --detect-entry` and the established firmware/NDK/QEMU arguments. The latter implies all earlier owned prefix modes and resumes at **face0x471f70** after refresh; reuse remains **post0x472294**, error completion **0x4722b0**. Private evidence: `Hasselblad_Detection_Evidence_PRIVATE_20261021.zip`.

Next: face processing, join the owned automatic prefix to scene/history/atmosphere/post/passive REAWB/diagnostics/shading/completion, then map real phone inputs/calibration and integrate the bounded automatic single-RAW APK. Manual/custom bodies and active REAWB/linked storage remain explicit backlog. Phone colour/HNCS acceptance and auxiliary spectral availability remain separate. No APK was built or installed; main and Native1C are unchanged.


## Face — 21 October 2026

`hb_face.c/.h` owns the bounded face controller originally at `0x4ba158`, including fractional ROI averaging, face retention/expiry, skin-model confidence, candidate rejection, iterative temperature/gain mapping, two atmosphere corrections, nested confidence curves, movement/colour stability, temporal state transitions and fixed-point smoothing. It reuses owned numerical helpers and contains no original callbacks or calibration/model payloads. Logging is omitted.

The implementation preserves float operation order, wrapped integer products, signed/unsigned comparisons, partial writes on error, stale inactive records, diagnostic copies and the original seven-state controller. A zero-length face atmosphere table leaves zero-initialized gain outputs, matching this caller's original behavior. This is distinct from callers with unspecified local outputs. Error returns222/223 cover missing source/block dimensions,225 covers invalid zoom, and247 covers empty active multi-point curves.

Research bounds are checked before stage mutation: eight face/retained ROIs, two models with at most16 sorted indices into81 rows,1,024 statistics/grid cells, finite exposure/hold/rectangle values, eight multi-point knots, eight atmosphere EV rows with15 temperature rows and eight tint rows,15 confidence rows/knots, and four brightness mixture rows with15 exposure/brightness knots. Public helper entry points require those validated table shapes. The caller still supplies initialized temperature and model tables; these guards are not a production phone-input adapter.

- `FACE_RESULT.json`: **893 checks, zero mismatches**,214 original calls,96 stateful calls,36 owned-only guard checks. Original errors222/223/225 once each and247 four times. Cases include disabled/reset paths, empty/retained faces, fractional/clipped/empty rectangles, bypass inputs, changing model segments, nonzero atmosphere correction, nested confidence/brightness tables and temporal states.
- `FACE_ENTRY_RESULT.json`: **12,857 checks, zero mismatches**,2,035 full original controller calls. The owned prefix executes225 face calls,32 active, with zero face errors or original face callbacks. Detection265 (40 errors); statistics/sensor/parsing269 each; synchronization/ROI327 each (12 ROI errors). All earlier native/scheduling/stateful coverage remains: seven synthetic E2 frames,144 scheduling cases,256 stateful calls. There are347 explicit original downstream continuations; automatic refresh275/reuse52. Manual/custom remain original continuations.

Reproduce with the established private runtime arguments and either `--face` or `--run-entry --face-entry`. The latter implies the entire detection prefix and resumes original scene at `0x471f80`; reuse still resumes original post at `0x472294`. It uses the existing40-second CPU/60-second wall limits. Comparisons clone initialized state in the same process and compare every context byte, status and immutable config. Never replay pointer-bearing dumps in another process.

Private evidence is saved as `Hasselblad_Face_Evidence_PRIVATE_20261021.zip`; owned code, safe reports and this handoff remain on GitHub. The first implementation passed the direct comparisons; broader nonzero/nested fixtures and guard cases also passed. Final reports were rerun against the exact final source. Passing synthetic comparisons are bounded evidence, not photographic colour/HNCS acceptance. The automatic prefix and separately verified downstream chain still need composition, followed by actual phone statistics/calibration mapping and app integration. No APK was built or installed; main and Native1C remain unchanged.


## Automatic composition — 21 October 2026

`hb_automatic.c/.h` exposes `hb_run_automatic`, an owned composition of the full bounded automatic controller for modes 0/1. No original numerical callbacks or model/calibration payloads are embedded. The caller supplies an initialized 920,560-byte context, 1,502,800-byte config, optional passive 1,000-byte REAWB handle, temperature/ROI models and at least `HB_DEBUG_WORKSPACE_BYTES` of diagnostic workspace. Existing stage table bounds and initialized-ABI preconditions still apply. Initialization, native statistics import and phone calibration remain external; this API is not yet a standalone phone implementation.

The refresh route runs entry/LUT/user/dispatch/synchronization/ROI/statistics/sensor/parsing/detection/face/scene/history/atmosphere/post/passive REAWB/debug/shading/completion. Reuse runs the same prefix through ROI, then post/debug/completion; it skips REAWB and shading as the original does. Early entry/LUT/user and suspended-dispatch returns retain their original behavior. `hb_automatic_tail` provides the refresh, reuse and error composition boundary, with an initialized caller-supplied trace.

`hb_automatic_trace` records executed stages, entry/dispatch results, failure stage/status and completion provenance. Original downstream errors can restore confirmed gains and return zero; callers must inspect the trace to distinguish recovery from a newly calculated result. `HB_PREP_UNSUPPORTED` never goes through success completion. If encountered after earlier stages, their writes remain: discard/reinitialize that working state. Invalid top-level inputs and initial manual/custom modes reject before touching context/config/handle/trace. Manual/custom requests arising later from user controls also reject, preserving prior writes. Active REAWB and actual diagnostic file I/O remain unsupported.

`AUTOMATIC_RESULT.json`: **24,219 checks, zero mismatches**, against **2,131 complete original controller calls**. The independent full owned API runs **2,083 automatic calls**, comparing status, all context/config bytes, passive REAWB state and entry reason. The piecewise comparison uses **427 owned suffix calls**; its only original continuations are 16 manual/custom cases. Automatic numerical callbacks: zero. Mode guards contribute 240 checks; explicit unsupported/input guards contribute 33. There are 100 native error recoveries and 384 early nonzero returns, including fixed-result statuses that are not necessarily errors.

The new **96 consecutive imported synthetic E2 frames** exercise both automatic modes, changing exposure/model rows and E-ND settings, with **32 refreshes and 64 reused results**. Original native setters/parser import provision those fixtures before comparison; the automatic calculation itself is fully owned. Existing seven synthetic native frames, 144 scheduling cases and 256 stateful entry calls remain covered. Stage counts: synchronization/ROI423 each, statistics/sensor/parsing301 each, detection297, face/scene257 each, history/atmosphere217 each, post/debug327 each, passive REAWB/shading217 each and completion427. Error recoveries comprise dispatch4, ROI12, parsing4, detection40 and scene40.

Reproduce with the established private firmware/NDKr27/QEMU arguments and `run_full.py --run-entry --automatic-entry`. It implies the entire owned face prefix and uses the existing 40-second CPU/60-second wall limits. API28, C11, O2, `-ffp-contract=off`, 16,384-byte maximum ELF page size. Initialize and clone state within the same process; never restore pointer-bearing dumps into another process.

Final capture review corrected the save order so the piecewise result is preserved before the independent full API resets working state. The final run was regenerated into an empty output directory against the exact final source; every retained capture postdates compilation of that probe. Final source/probe/dump hashes and saved original/owned context pairs are verified before checkpointing. Private evidence: `Hasselblad_Automatic_Composition_Evidence_PRIVATE_20261021.zip`. Source and safe reports remain on GitHub.

Next: map actual Camera2/raw inputs and available auxiliary spectral information; implement phone context/model initialization and inject real per-sensor calibration; connect the bounded automatic API to the app and run integration/stability checks for the first single-RAW APK. Never invent spectral measurements or transplant IMX861 calibration. Preserve the one-time white-balance/coherent-matrix rendering policy. Matching this initialized synthetic controller does not establish real-phone colour or HNCS rendering. No APK was built or installed; main and Native1C remain unchanged.
