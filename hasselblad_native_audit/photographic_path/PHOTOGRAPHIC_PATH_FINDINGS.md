# X2D II photographic colour path: native execution and remaining pixel contract

## Finding

**Two original X2D II native functions used to prepare photographic colour LUTs now execute successfully outside the camera, including at the actual camera table size with the actual camera data.** The exact `librcam.so` from firmware **1.3.16.2** loaded under its matching Android 9/Bionic runtime in QEMU. Its original `mm_get_coeff` and `mm_mx_lerp_vec_mix2` functions passed twelve bounded synthetic profile tests and ten full-size original-camera profile tests. The tests used the real functions and their original runtime dependencies, with no replacement LUT function or dependency stubs.

This establishes a useful next stage after the separately proven AWB calibration primitive: **selecting and interpolating a camera colour profile for a colour temperature and output gamut**. It does not yet apply that profile to image pixels, run the entire saved-image pipeline, or establish a complete HNCS port.

The more consequential static finding is that the explicitly configured ordinary and enhanced still reprocessing segments **enable `MAIN_CCM`, `MAIN_GAMMA`, and `MAIN_3DLUT`, while bypassing the separately named `MAIN_HNCS` ISP module**. Following the HNCS name alone would target the wrong active block for these segments.

The machine-readable companion is `PHOTOGRAPHIC_PATH_FINDINGS.json`. It contains exact hashes, selected topology declarations, function addresses and calls, profile sizes and hashes, the tested ABI, and remaining uncertainties. Firmware and photographic table payloads are excluded from the report.

## 1. Exact source and parser provenance

The official package is available at:

<https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim>

The URL was obtained from Hasselblad's product firmware API, <https://api.hasselblad.com/products/downloads/173/firmware>. The package was downloaded from that URL and extracted locally as inert data. No update script or camera deployment operation was used.

| Source | SHA256 |
|---|---|
| Official CIM, 364,814,336 bytes | `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` |
| `system/lib64/librcam.so` | `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66` |
| `system/lib64/libdcam_pp.so` | `bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9` |
| `system/etc/iq/hb722_config.json`, 27,277,188 bytes | `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286` |
| `system/etc/iq/config.fbs` | `59ec3b0d019b9e8873f3d005c041b4e3ca1a2b930c503c110c51531f8bd30e40` |
| Original audit parser, `inspect_iq_config.py` | `0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec` |

The JSON companion also pins `libalgo_share.so`, `libadj_base.so`, `libdcam_pp_base.so`, and `libdcam_adj_product.so`. The extracted `system/build.prop` declares Android 9, API 28, and `arm64-v8a`; the probe was compiled for Android API 28 ARM64.

`inspect_iq_config.py` is an original audit tool, not a recovered vendor parser. It tokenizes the supplied FlatBuffers-style configuration and performs recursive descent. It accepts comments, bare keys and enum values, hexadecimal integers, and trailing commas. It rejects duplicate keys, unknown tokens, trailing unparsed data, and any source file that does not match the exact config SHA256. It does not use `eval`, execute configuration text, or run a vendor library. The entire source parsed successfully. The config is therefore inspectable independently of whether a camera service can initialize.

This audit used ELF exports, the embedded compressed `.gnu_debugdata` symbol table, AArch64 direct calls and callers, the supplied configuration/schema, and the bounded native experiment below. Symbol names alone were insufficient to establish photographic relevance or a calling convention.

## 2. Configured saved-still route

The following declarations appear in `topology.modules`:

| Reprocessing segment | Explicit mode mapping | Topology group | Selected enabled modules | `MAIN_HNCS` |
|---|---|---:|---|---|
| `frog_raw_reprocess_2-r2y-still` | `still3` | 2 | `MAIN_WBC`, `MAIN_DEMOSAIC`, `MAIN_PFR`, `MAIN_CCM`, `MAIN_GAMMA`, `MAIN_3DLUT`, `MAIN_R2Y` | Bypassed |
| `frog_raw_reprocess_2-r2y-still_scap3_enh_normal` | `still0` | 2 | Same selected modules | Bypassed |
| `frog_raw_reprocess_2-r2y-still_scap3_enh_hdr` | `still0` | 2 | Same selected modules | Bypassed |

All three mappings are present under each of `TPLG_IMX861BQR_STILL_14BIT`, `TPLG_IMX861BQR_STILL_16BIT`, and `TPLG_IMX861BQR_STILL_14BIT_HS`. Their complete selected module and bypass arrays are preserved in the JSON companion. These are static topology declarations, not a trace of a captured photograph. They do not establish the physical order of every hardware stage or the exact runtime branch selected for every user setting.

`MAIN_HNCS` is a real module with configuration and code. Two other declared recording segments enable it: `common_recording_still_1-raw_writer-ycc-sub_back-data_mux0` and the corresponding `-video` variant. Consequently, the evidence supports bypass in the three named still reprocessing segments; it does not support the broader claim that the firmware never uses this module.

Relevant local code in the pinned `librcam.so` includes:

| Function | ELF virtual address | Size | Observed role |
|---|---:|---:|---|
| `main_3dlut_calc_frame` | `0x39ce88` | 2,148 bytes | Calculates module parameters and submits ISP register/data updates |
| `main_ccm_calc_frame` | `0x39e4b0` | 2,148 bytes | CCM parameter calculation and ISP updates |
| `main_gamma_normal_calc_frame` | `0x3a2df8` | 2,148 bytes | Gamma parameter calculation and ISP updates |
| `_main_hncs_calc_frame` | `0x34c678` | 1,656 bytes | HNCS-named module parameter calculation and ISP updates |
| `post_scap3_calc_3dlut` | `0x2f2d08` | 820 bytes | Still enhancement colour-parameter calculation through the common adjustment dispatcher |
| `post_hdr_calc_3dlut` | `0x301b00` | 820 bytes | HDR colour-parameter calculation through the common adjustment dispatcher |

These entry points expose preparation and submission of ISP data. They are not established `RGB image in → RGB image out` CPU functions. In `libdcam_pp.so`, `raw2rgb_proc` and `hbl_calib_build` dispatch work through `message_trans_arm_proc_pull`; their names do not establish a standalone CPU implementation either. The present evidence locates a host CPU preparation stage feeding platform processing. It does not prove that every photographic operation is hardware-only.

## 3. Actual photographic LUT and tone assets

The main LUT descriptor is `iq_table.module.main_3dlut.lut_data`. Its calculation type is `lerp_lut_mem_3d`, group `global_frame`, with `mem_cfgen = 1` and axes **`[cc_color_temp, color_gamut]`**. The camera declares:

- CCT knots: **2400, 3050, 5550, 9100 K**.
- Gamut selectors: **0 and 1**, named sRGB and P3 in the configuration/schema.
- One global `lut_data` array containing **49,152 32-bit words in total**.

`_Calc_GetLerpInfo` computes cumulative axis products. For these axes, those products are `[4, 8]`. `_Calc_LerpLutMem3d` checks that the source word count equals the axis product multiplied by the destination LUT word count. The consistent configuration/caller contract is therefore **eight profiles, each containing 6,144 words, or 24,576 bytes**. It is not 49,152 words per profile. The per-profile size is derived from the observed array length, declared dimensions, and actual size check; this audit has not captured an ISP register dump containing the destination count.

The native interpolation core treats each 32-bit word as **two signed 16-bit lanes**. In the actual camera asset, both lane ranges are **0–4095**. The first axis varies fastest: `profile_index = cct_index + 4 × gamut_index`. A source profile begins at `profile_index × 6144` words. Packed little-endian hashes for each profile are preserved in the JSON report so subsequent tooling can verify the same interpretation without bundling the tables. The first two CCT profiles are identical within each gamut in this particular package.

Each generated profile consequently contains **12,288 scalar lanes**. This equals `16³ × 3`, which is consistent with a 16×16×16 three-component colour cube. **That is a candidate shape, not proof of an ordinary RGB cube file.** The evidence does not yet identify the component order, position order, bank/swizzle layout, possible padding, sample-coordinate shaper, or spatial interpolation. Two halfwords per word do not by themselves establish RGB triplets or a conventional `.cube` ordering.

Other real photographic assets are present. The normal gamma module has a 257-entry curve shared by `still0` through `still4`, with curve-array JSON SHA256 `5c5f69a4087f0aee9ee0068c8687b13e0922dc228550349398a019e468dbfb6f`. Its `lut_div` parameters are `[2,2,3,4,5,6,7]`; an adapter must recover their coordinate-spacing meaning before treating the curve as uniformly sampled. `main_gamma_common` enables gamma; knee is disabled for the relevant `still0` and `still3` modes, while the quick `still4` mode differs. The main 3D LUT's pre-gamma enable is zero in the global configuration. These facts constrain a later reconstruction, but do not establish the entire input/output transfer domain.

## 4. Proven native ABI and experiment

### Config-to-function connection

The schema assigns `calc::lerp_lut_mem_3d` the value **37**. `rcam_adj_calc_common` at `0x3b3e98` reads a function-pointer table at `0x59c240`. The native probe read slot 37 after the original linker applied relocations and verified that it points to **`_Calc_LerpLutMem3d`, `0x3b8c78`**. This avoids relying on an incomplete offline interpretation of Android packed relocations. The probe reads the wrapper pointer; it does not invoke a wrapper with an invented camera context.

The wrapper obtains interpolation information and an ISP LUT destination, checks the source/destination sizes, then calls `mm_mx_lerp_vec_mix2` at `0x3b8d20`. It subsequently calls `DjiAdj_Calc_LutMemCopy`. The separate enhanced wrapper `_calc_lerp_lut_mem3d_enh`, at `0x3c3948`, calls the same core at `0x3c39b8` with an explicit destination descriptor. Both callers support the six-argument layout below.

### Bounded contract

The following signature describes the audited calling convention. The declarations are research descriptions, not vendor source:

```c
struct coefficient {
    uint32_t index;
    int32_t fraction_q8;
};

uint32_t *mm_mx_lerp_vec_mix2(
    const uint32_t *profiles,
    uint32_t words_per_profile,
    const struct coefficient *coeff,
    const uint32_t *cumulative_axis_products,
    uint32_t dimensions,
    uint32_t *destination);
```

The tested domain is two dimensions with four and two knots, strictly bounded indices and fractions, nonoverlapping owned arrays, eight source profiles, and a destination with one profile's capacity. The synthetic fixture uses seven words per profile; the real-camera fixture uses **6,144 words per profile**. The return value is `destination + words_per_profile`. The original wrapper supports more dimensions, but the present experiment does not validate that broader domain.

For each signed halfword, the core performs the first-axis interpolation, then the second-axis interpolation, using:

`lerp(a,b,f) = a + floor((b−a) × f / 256)`.

The arithmetic shift in the original AArch64 code rounds negative products downward. Results are repacked by retaining each lane's low 16 bits. The harness reference implements signed floor division explicitly instead of depending on a host compiler's signed right shift. With signed-16 input lanes and fractions in `[0,256]`, the intermediate products fit in signed 32-bit arithmetic.

`mm_get_coeff`, at `0x2bac00`, takes an ascending `int32` axis, a count, and an `int32` coordinate. It returns a 64-bit value whose low 32 bits are the interval index and high 32 bits are the Q8 fraction. For the audited positive CCT axis, the interior fraction is `floor(256 × (value−axis[i]) / (axis[i+1]−axis[i]))`. Below the first knot it returns `(0,0)`; at or above the last knot it returns `(count−2,256)`. These endpoints keep both adjacent profiles in bounds. The actual coefficient-generation caller uses the declared CCT axis, and reduces the runtime gamut selection to zero or one before selecting the gamut coefficient.

Both functions are local symbols recovered from `.gnu_debugdata`, not dynamic exports. The harness resolves the defined export `dcam_isp_vreg_get_type`, verifies its library identity using `dladdr`, and uses exact same-ELF address differences. It does not assume a zero first load-segment address. The Python runner refuses any other library SHA256 and verifies all three symbol addresses and sizes before execution.

| Original function | Address / size | Original function-byte SHA256 |
|---|---|---|
| `mm_get_coeff` | `0x2bac00` / 160 bytes | `68754a8d484850dc37a03dedd36b17fa309f3f76fcdc7c2f21472400e6a192bf` |
| `mm_mx_lerp_vec_mix2` | `0x2bbc08` / 1,784 bytes | `2082f0f9f3db305022bee2e479adf4da94855ff049105a1b8fc816e12256c1cf` |

### Result and practical limits

All **12 synthetic cases passed**, with process exit **0** and empty stderr. The fixture contains eight synthetic profiles of seven words each, with asymmetric positive and negative halfword values. It exercises both gamut endpoints, CCT values below/at/above the bounds, internal knots, and fractional CCT interpolation. Every output word matched the independent reference. The source array and destination guard words remained unchanged outside the intended outputs, and each returned pointer matched the destination end. This synthetic experiment is preserved separately in `lut_profile_native_execution.json`.

A second bounded experiment then passed the **full original 49,152-word camera LUT** to the same original functions and generated **ten 6,144-word profiles**. This closes the validation gap between the small fixture and the actual profile size. The selected CCTs were **2400, 4300, 5550, 7001, and 9100 K**, each tested with **both sRGB and P3**. They include the endpoint/interior knots and two fractional intervals.

All **122,880 output lanes** in that experiment matched the C reference. An independent Python calculation also matched every byte of every generated profile. All source-integrity checks, destination guards, coefficient checks, and returned pointers passed. The process exited **0** with empty stderr. Knot-output hashes matched the corresponding original profile hashes; fractional outputs have separately recorded hashes.

The exact packed input SHA256 was `0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911`. `lut_profile_real_asset_execution.json` records that hash, the config hash, sizes, output hashes, coefficients, and validation outcomes. It contains **no camera LUT or generated profile payload bytes**. The runner used temporary files to transfer the original table and generated outputs, hashed and compared them, and deleted those files before writing the retained result. No profile was applied to an image pixel.

The original runtime supplies the real `memset` and stack-guard handling used by the interpolation helper. Successful execution under matching firmware Bionic is a separate result from loading this library inside a normal modern-phone application namespace. It also does not measure camera capture performance or establish a safe arbitrary-input API.

## 5. Precise remaining work before saved pixels

Preparing a full-size profile from the exact main LUT asset with the original native helper is now demonstrated. The next operation is to establish how the camera samples that prepared profile for a pixel. The unsolved contract comprises:

1. **Table layout:** assign the 12,288 lanes to spatial nodes and output components, including any bank interleave or swizzle. Confirm or reject the 16³ three-component interpretation using the ISP LUT descriptor/consumer, not the count alone.
2. **Input coordinates and stage domain:** establish the LUT's input range, grid knot positions, component order, and relationship to the CCM and gamma stages. The 0–4095 stored values and disabled local pre-gamma constrain this question without answering it.
3. **Spatial interpolation:** recover the pixel sampler's interpolation method, fixed-point precision, rounding, clipping, and endpoint behavior. The proven routine interpolates between complete profiles as illumination/gamut changes; it does not interpolate a pixel within a colour cube.
4. **Sensor adaptation:** establish how Photon sensor-linear values and its calibration/WB metadata map into the colour coordinates expected by the X2D II stages. Executing a correct profile generator does not make a phone sensor respond like the camera sensor.
5. **Phone execution:** verify an appropriate native or equivalent audited adapter in the standalone Photon process on the target Android device. The matching-runtime proof is complete; ordinary app compatibility and a complete image transform are separate gates.

The first inspection target for the pixel contract is the consumer/format metadata behind `DjiIsp_Reg_GetLut` and `DjiAdj_Calc_LutMemCopy` for `MAIN_3DLUT`, followed by the corresponding platform image-processing stage. The saved-still CCM/gamma descriptors supply companion constraints. A software pixel sampler should be implemented only once that contract has evidence; otherwise it would introduce an assumed look despite using a real camera profile.

Two tempting leads were excluded. `GetGammaLut` and `GetDegammaLut` in `libdcam_pp.so` are called by `elldn_nn_config_gamma`, reached from `call_nndns` immediately after neural denoiser acquisition. The embedded path is `hardware/dji/common/camera/libpp_proxy/pp_proxy/nn_proxy/elldn/elldn_nn.c`. Their location in this path supports neural-denoise normalization, not a proven photographic rendering curve. Display `lcdc_3dlut*` handlers are likewise distinct from the identified saved-still `main_3dlut` configuration.

## 6. Reproduction and packaging

The native experiment needs an extracted exact-hash firmware root containing `system/bin/linker64` and `system/lib64`, QEMU AArch64 user mode, an Android NDK API-28 ARM64 compiler, and Python with `pyelftools`. The runner hashes the library, relevant function bytes, original linker/libc, QEMU executable, harness source and built probe. It records the exact build/run commands, sets a 20-second wall timeout and 15-second CPU limit, and disables core dumps.

Run with local paths to those supplied materials:

```bash
python replay_lut_probe.py \
  --firmware-root /absolute/path/to/extracted \
  --qemu /absolute/path/to/qemu-aarch64-static \
  --clang /absolute/path/to/aarch64-linux-android28-clang \
  --output /absolute/path/to/lut_profile_native_execution.json
```

To run the separate full-size original-camera validation, supply the exact config explicitly and use a separate result file:

```bash
python replay_lut_probe.py \
  --firmware-root /absolute/path/to/extracted \
  --qemu /absolute/path/to/qemu-aarch64-static \
  --clang /absolute/path/to/aarch64-linux-android28-clang \
  --config /absolute/path/to/extracted/system/etc/iq/hb722_config.json \
  --output /absolute/path/to/lut_profile_real_asset_execution.json
```

The observed runs used NDK `27.0.12077973` and the extracted Android 9 runtime. Their exact commands and hashes are in their respective result JSON files. The runner compiles `lut_profile_probe.c` next to the chosen result file; it neither downloads firmware nor copies vendor bytes into an application. The optional config mode imports the adjacent original `inspect_iq_config.py` tool and enforces both the config SHA256 and the packed LUT SHA256 before execution.

To repeat the inert config inspection:

```bash
python inspect_iq_config.py \
  --source /absolute/path/to/extracted/system/etc/iq/hb722_config.json \
  --output /absolute/path/to/iq_config_summary.json
```

For the source/research bundle, include this report, `PHOTOGRAPHIC_PATH_FINDINGS.json`, `lut_profile_native_execution.json`, `lut_profile_real_asset_execution.json`, `librcam_load_result.json`, `adj_dispatch_table.json`, `lut_profile_probe.c`, `replay_lut_probe.py`, `inspect_iq_config.py`, and the original analysis helper `inspect_paths.py`. The detailed local disassembly outputs, the expanded config summary, extracted firmware, original config arrays, and probe executables are unnecessary for the source bundle; the supplied tools can recreate the local inspection and bounded probes from the user-supplied package.
