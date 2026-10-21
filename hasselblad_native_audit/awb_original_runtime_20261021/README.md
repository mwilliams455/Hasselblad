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

The initial leaf checkpoint restored execution and recalibration. The following checkpoints restore scene initialization and bounded numerical optimizer comparisons. Still missing: authentic E2 frame preparation, device-specific calibration inputs, historical seven-frame context/REAWB parity, full AWB, HNCS rendering, and phone validation.

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

### Resume here

1. Recreate the verified private runtime from the complete 65-library runtime bundle, or use the pinned extraction script with the original CIM. Run the leaf and `--optimizer` probes above.
2. Restore native E2 input preparation, original sensor calibration injection, per-block classification, weighting/filtering and candidate accumulation using the actual original functions. Do not substitute the Rebuild02/03 synthetic equations for vendor algorithms.
3. Feed those original-prepared candidates through the rebuilt optimizer, restore caller-side count/state updates, and compare the historical seven-frame sequence within one execution, including the passive REAWB handle.
4. Proceed through history, atmosphere, calibrated CT/tint, publication/output and full controller. Only then integrate phone calibration and build an explicitly bounded upgrade APK.

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
