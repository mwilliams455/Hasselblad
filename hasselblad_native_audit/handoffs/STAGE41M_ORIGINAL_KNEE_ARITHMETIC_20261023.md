# Stage41M — original knee arithmetic and MAIN/SUB separation

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Starting research commit: `d206498276e847bea6a859a4c70ac1fd1f25bddd` (Stage41L).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

This stage reconstructs two original table-preparation operations and checks them against the original AArch64 instructions with synthetic inputs. All 26,705 compared entries match exactly. It also verifies the MAIN gamma dispatcher and separates the configured SUB preview fusion path from MAIN gain/saturation knee preparation.

This is stronger evidence for those bounded operations than a fitted image curve. It is not a recovered RGB pixel renderer, a full camera-pipeline execution, or proof of which tuning bank produced the four supplied captures. No new image-quality improvement or Android change is claimed.

## Findings and validation

| Operation | Original execution scope | Result |
| --- | --- | --- |
| MAIN gamma selection | Entire dispatcher; selected callbacks intercepted | Five synthetic flag combinations choose the expected callback sequence |
| Gain/saturation slope preparation | Contiguous arithmetic block inside `_calc_knee_data` | 261 cases, 8,458 entries, exact agreement |
| SUB knee/gamma table fusion | Entire `adj_plat_calc_knee_fusion`; external knee-map lookup supplies synthetic values | 71 cases, 18,247 entries, exact agreement |
| Named gamma-EV and excess-knee-gain hooks | Entire two-instruction functions | Both return zero and perform no work in this build |

Six standalone tests also pass, covering slope fractions, signed arithmetic edge cases, input bounds, identity/half-gain/clamped fusion, float32 operation order and unsigned output saturation. Validation runs locally, not on public CI.

## The original MAIN slope preparation

`calc_knee_data` is schema calculator ID 84. The original calculator dispatch table maps it to `_calc_knee_data` at `0x3bf218`. The active calculation type declared for both `main_gamma_normal.knee_gain` and `main_gamma_normal.knee_saturation` is `calc_knee_data`. The schema comment explicitly identifies this calculator as preparing gain, gain slope, saturation and saturation slope.

The original slope loop at `[0x3bf500, 0x3bf55c)` computes, for consecutive table values and keypoints:

`slope[i] = SDIV32(wrap32((value[i+1] - value[i]) << 12), wrap32(keypoint[i+1] - keypoint[i]))`

The final slope entry is zero for the tested contract of at least two entries. The 12-bit shift establishes a 4096 slope scale. Intermediate differences and shifts are 32-bit operations; division truncates toward zero. The replay includes descending values, non-integral slopes, shifted-numerator overflow, equal keypoints and signed division overflow. Equal keypoints reproduce the processor's zero-divisor result; this does not assert that repeated keypoints are valid camera tuning.

The complete `_calc_knee_data` function also performs table selection/interpolation, calls keypoint preparation and publishes lookup data. Those surrounding dependencies were inspected statically but are not included in the slope-block execution claim. No per-pixel keypoint selection, clipping, slope interpolation or RGB mixing equation is inferred from the table-preparation loop alone.

## Runtime gamma branch selection

The complete original `main_gamma_calc_frame` dispatcher runs against synthetic context objects and the original callback-pointer tables. It always calls the common callback first. It then selects:

| Synthetic mode flag | Synthetic lowlight flag | Next callback |
| --- | --- | --- |
| Zero | Zero | Normal |
| Zero | Nonzero | Lowlight |
| Nonzero | Either | EI |

The mode flag is loaded from context-state offset `0x18`; the lowlight-selector byte is at context offset `0x3440`. Names follow the selected callback symbols. This establishes routing and precedence, not the threshold or upstream algorithm that sets those flags. The synthetic test checks argument forwarding to each callback. Callback bodies are intercepted rather than executed.

We still do not know those runtime flags for the four supplied RAW/JPEG pairs. ISO alone must not be used to label a capture's active bank.

## SUB fusion is distinct from MAIN preparation

The original configuration assigns `knee_fusion` to `sub_gamma_normal.r_lut`, `.g_lut` and `.b_lut`. Their lookup axis is `gamma_simulation_ev`, with `gamma_dgain` as a dependency. Its `knee_lut` is separately interpolated along `gamma_ev`. By contrast, MAIN normal gamma tables are declared as simple memory LUTs, with separate gain and saturation knee data.

| Configuration field | Declared calculator | Declared axis |
| --- | --- | --- |
| MAIN normal gamma LUT | `simple_lut_mem` | None |
| MAIN normal knee gain | `calc_knee_data` | `gamma_ev` |
| MAIN normal knee saturation | `calc_knee_data` | None |
| MAIN lowlight knee gain | `calc_knee_data` | `knee_axis_many` |
| MAIN lowlight knee saturation | `calc_knee_data` | `knee_axis_few` |
| MAIN EI gamma LUT | `index_1d_lut_mem` | `user_ei` |
| SUB normal R/G/B LUTs | `knee_fusion` | `gamma_simulation_ev` |

The full declaration mapping, including groups and dependencies, is in the evidence receipt. Registration membership does not by itself prove hardware execution order. The earlier Stage41H preview-topology findings remain relevant; they do not identify the embedded still preview as that liveview stream.

For SUB fusion, schema calculator ID 186 dispatches to `_calc_knee_fusion`, which calls the replayed platform helper. The helper requires 257 entries. For each synthetic knee-map value `k` and unsigned context scalar `g`, it computes the lookup position using separately rounded float32 operations equivalent in real arithmetic to `g*k/1024`. It clamps both neighboring indices to 256, linearly interpolates signed source values, and converts the result to unsigned integer with truncation/saturation. The scalar's upstream ownership and exposure units remain unproven.

The original helper executes with only `memset` and the external knee-map lookup intercepted. The latter writes a synthetic 257-entry map. No original tuning arrays are used or exported. The replay checks exact outputs and output-buffer sentinels. The reconstruction exposes only the explicitly bounded gain/map/source domain documented in `knee_math41m.py`.

Precision matters: a synthetic interpolation with gain 677, map value 99 and neighboring source values 37,392 and −31,519 produces 6,234 in the original float32 operation order. A float64 rewrite truncates to 6,233. Both the reconstruction test and original-code replay preserve the original result.

## Two misleading function names resolved

`adj_plat_calc_gamma_lut_compensate_ev` and `adj_plat_calc_knee_gain_over_isp_max` each consist of a zero return in this exact build. Their full functions execute in the harness and leave synthetic memory unchanged. The configuration also contains no occurrences of the gamma-compensation calculator type names, although the generic calculator dispatch includes them.

This closes those specific hooks as sources of missing arithmetic. It does not imply that exposure compensation or gain limits are absent elsewhere in the pipeline. MAIN normal knee gain explicitly depends on `gamma_ev`.

## Effect on the four-RAW work

Stage41L's smooth empirical curve remains the retained offline comparison candidate. Its rejected neutral-axis gamut contraction is not reinstated. The separate original gain and saturation controls now provide a more concrete reconstruction target, but their existence does not prove the camera's pixel mixing or explain every saturated-red difference.

No RAW, cache, reference encoding, exposure fit or comparison image is changed in this stage. There is no new APK. The extracted firmware is 1.3.16.2; the supplied RAW capture firmware is 1.1.6.3, so exact cross-version rendering claims remain inappropriate.

The next bounded task is to trace the MAIN hardware register layout and application of its gain/saturation tables: input units, keypoint interpretation, clipping, luminance weighting and channel mixing. Then connect the correct runtime bank before testing the reconstructed pixel operation against the real RAW regions. The MAIN CCM group selection, scaling and rounding also remain open; the available RAWs establish input access but cannot expose every hidden intermediate stage.

## Reproduce and preserve

The source library is pinned to SHA256 `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`. Config/schema hashes and selected original function hashes are in the receipt. The harness maps the original library at zero load bias solely for bounded emulation, intercepts declared dependencies and fails on unexpected code execution. It does not load Android libraries, contact hardware or emulate the camera service.

```bash
python -m pip install -r hasselblad_native_audit/isp_knee_stage41m/requirements41m.txt

python hasselblad_native_audit/isp_knee_stage41m/replay_knee41m.py \
  --library /private/original-firmware/extracted/system/lib64/librcam.so \
  --config /private/original-firmware/extracted/system/etc/iq/hb722_config.json \
  --schema /private/original-firmware/extracted/system/etc/iq/config.fbs \
  --output /private/STAGE41M_ORIGINAL_KNEE_REPLAY_SAFE.json

python hasselblad_native_audit/isp_knee_stage41m/test_knee_math41m.py
```

The public commit contains original analysis/reconstruction source, dependency pins, this report and the aggregate evidence receipt. It excludes vendor executable bytes, disassembly, tuning arrays, source photographs, camera identifiers, capture metadata/calibration arrays and fitted rendering parameters. Private exploratory disassembly is reproducible from the pinned firmware and is not a public artifact.
