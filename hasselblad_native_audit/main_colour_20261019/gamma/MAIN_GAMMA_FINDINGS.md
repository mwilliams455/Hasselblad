# MAIN gamma: verified knots and register storage

Date: 2026-10-19. Target: Hasselblad X2D II 100C firmware 1.3.16.2.

**The seven division controls now have an original-code oracle: they encode the base-2 logarithm of the interval count in seven input regions. For the configured `[2,2,3,4,5,6,7]`, the resulting 257 positive-domain coordinates are uniformly spaced by 256 from 0 through 65,536.** This conclusion comes from a consumer of the actual `MAIN_GAMMA` register table, with deliberately nonuniform synthetic divisions used to distinguish interval counts from strides.

The companion register investigation confirms that the kernel writes 257 complete 32-bit words to the main gamma table, and identifies the division, negative-table, knee and dither fields. It does **not** establish hardware pixel interpolation, the effective precision of its image output, negative-input handling or the dither algorithm. No photographic curve has been added to Photon; the existing application, APK and earlier reports remain unchanged.

## 1. Saved-still connection and exact inputs

The preceding [photographic path findings](../../photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.md) identify `MAIN_GAMMA` as enabled alongside `MAIN_CCM` and `MAIN_3DLUT` in the declared ordinary and enhanced still reprocessing segments. The ordinary `frog_raw_reprocess_2-r2y-still` segment selects `still3`; the two identified enhanced segments select `still0`. This is a static configuration relationship, not an observed camera capture trace.

This checkpoint uses the same exact local firmware inputs:

| Input | SHA-256 |
|---|---|
| `system/lib64/librcam.so` | `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66` |
| `system/lib/modules/vcam_driver.ko` | `29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e` |
| `system/etc/iq/hb722_config.json` | `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286` |
| `system/etc/iq/config.fbs` | `59ec3b0d019b9e8873f3d005c041b4e3ca1a2b930c503c110c51531f8bd30e40` |

The inert configuration inspection, [main_gamma_config_metadata.json](main_gamma_config_metadata.json), confirms that `still0` through `still4` share one 257-entry positive table. Its compact JSON array SHA-256 is `5c5f69a4087f0aee9ee0068c8687b13e0922dc228550349398a019e468dbfb6f`, and its stored integer range is 0–65,535. All five modes use the division vector above and a nine-entry negative table whose entries are zero. The negative-table scale control is 4. Only hashes and structural metadata are retained; the photographic curve and dither-key values are absent from this package.

The same inspection confirms `enable=1` and `dither_enable=1` for all five modes. Knee is disabled in `still0`–`still3`, including the specifically identified ordinary and enhanced still modes, and enabled in `still4`. A replica of another mode therefore cannot silently assume that knee is always disabled.

## 2. Positive-domain knot semantics

### A MAIN-linked consumer

The relevant consumer is `tmc_v1_0_calc_tmc` in `librcam.so`, at virtual address `0x381bc8`, size 22,816 bytes. It calls `DjiIsp_Reg_GetLut` at `0x384128` with register ID **4266 / `0x10aa`**, verifies the returned count is 257 at `0x384130`, and copies 1,028 bytes. This is the same `normal_gamma_lut` register independently identified by the relocated descriptor probe.

The function then calls `DjiIsp_Reg_Get` for IDs **4221–4227**, storing the seven division controls at stack offsets `0x1364` through `0x137c`. Immediately before knot construction, the original instructions load those values into `W26,W25,W24,W23,W22,W20,W19`. These register reads and loads are checked in the replay script; their surrounding code spans and the entire function are hash recorded. [gamma_knots_original_execution.json](gamma_knots_original_execution.json)

The inline interval **`[0x3866b0, 0x386d28)`** writes the coordinate sequence at `SP+0x144c0`. It is not a separately callable function. The test supplies only the documented live registers, a private stack, and one 16-byte constant read from the pinned ELF. It prohibits execution outside the selected interval and memory accesses outside the bounded constant, saved context word and output region. It stops before later TMC rescaling and resampling logic.

### Recovered formula

For division `d` in a region from `L` to `U`, the original code calculates:

\[
n=2^d,\qquad s=\left\lfloor\frac{U-L+\lfloor n/2\rfloor}{n}\right\rfloor.
\]

It emits the interior coordinates `L + j*s` for `j=1..n-1`, then writes `U` explicitly. The whole sequence begins at zero. The seven region boundaries are 0, 1,024, 2,048, 4,096, 8,192, 16,384, 32,768 and 65,536.

| Region | Lower boundary | Upper boundary | Configured division | Interval count | Coordinate step |
|---|---:|---:|---:|---:|---:|
| 0 | 0 | 1,024 | 2 | 4 | 256 |
| 1 | 1,024 | 2,048 | 2 | 4 | 256 |
| 2 | 2,048 | 4,096 | 3 | 8 | 256 |
| 3 | 4,096 | 8,192 | 4 | 16 | 256 |
| 4 | 8,192 | 16,384 | 5 | 32 | 256 |
| 5 | 16,384 | 32,768 | 6 | 64 | 256 |
| 6 | 32,768 | 65,536 | 7 | 128 | 256 |

The counts sum to 256 intervals, producing 257 coordinates. Uniform spacing is a consequence of these particular division values; it is not a general property of the encoding.

The owned implementation [gamma_knots.py](gamma_knots.py) exposes only this mathematical primitive. Its guarded interface accepts seven integer divisions in the range 0–7 whose powers of two sum to 256. Those restrictions are intentionally narrower than the physical four-bit fields. It neither reads a photographic LUT nor evaluates gamma on a pixel.

### Original-instruction validation

Eight cases compared every original output coordinate against the mathematical primitive: the actual vector, reversed and asymmetric permutations, and several different region-count partitions. **All 2,056 coordinate comparisons passed.** The asymmetric cases produce genuinely nonuniform sequences, so a uniform-grid shortcut would fail the check. Surrounding stack bytes remain unchanged, no unexpected reads occur, and eight invalid-input cases are rejected by the portable interface. The output records case parameters and coordinate hashes, not original photographic samples. [gamma_knots_original_execution.json](gamma_knots_original_execution.json)

This result establishes the positive-domain knot positions used by this MAIN-linked host consumer. A boundary coordinate of 65,536 is not, by itself, proof that the hardware accepts a pixel code of 65,536 or how it clips at the endpoint.

## 3. Register and kernel boundary

The native metadata probe reads the original linker-relocated descriptors under the matching Android/Bionic runtime and QEMU. Its C code invokes no camera processing routine; loading `librcam.so` executes its normal initializers. It reports 34 bounded records, including 30 parameter-field records, and resolves each IQ getter to its corresponding MAIN gamma module getter. The record also hashes the 93 files in the inspected runtime's transitive `DT_NEEDED` closure. [main_gamma_register_metadata.json](main_gamma_register_metadata.json)

Selected fields are:

| Field | Register ID(s) | Virtual-register offset | Storage |
|---|---|---|---|
| Gamma enable | 4207 | `0x22004` | Bit 0 |
| Knee enable | 4208 | `0x22004` | Bit 1 |
| Dither enable | 4209 | `0x22004` | Bit 2 |
| Seven positive division controls | 4221–4227 | `0x2201c` | Seven 4-bit fields at shifts 0,4,8,12,16,20,24 |
| Negative-table scale control | 4228 | `0x2201c` | 4-bit field at shift 28 |
| Positive gamma table | 4266 | `0x22080` | 257 words; physical address `0xf322e800` |
| Negative gamma table | 4267 | `0x22500` | 9 words; physical address `0xf322f000` |
| Knee clip | 4211 | `0x22008` | 12-bit field |
| Three knee Y coefficients | 4213,4215,4217 | `0x2200c`–`0x22014` | 10-bit fields |
| Knee blend control | 4219 | `0x22018` | 8-bit field |

These virtual-register offsets describe the library's data representation. They are not interchangeable with byte offsets from a mapped physical gamma register base. The native metadata independently retains the physical addresses for the table records.

The separate kernel function **`gamma_set_info`**, `.text+0x31a50`, size 796 bytes, contains no external call or relocation. Its full original body was executed in Unicorn with owned RAM standing in for the parameter object and MMIO. Four cases cover every one of its **199 instructions**, including disable, enabled knee-off, enabled knee-on, and nonboolean enable values. The exact final register image, all guard bytes, the read-only parameter memory, stack, preserved registers and zero return value matched. [gamma_driver_original_execution.json](gamma_driver_original_execution.json)

When enabled, the function masks the eight division bytes into register offset `+0x1c`, copies 257 input words from parameter offset `+0x1c` to register offset `+0x800`, and copies nine words from parameter offset `+0x420` to register offset `+0x1000`. Five additional 32-word knee tables follow. The tests use asymmetric synthetic 32-bit data, including nonzero high bits: the table words are copied unchanged. Therefore this routine is a storage/copy boundary, not a software implementation of 16-bit clipping or gamma interpolation. The physical address `0xf322e800` is consistent with register offset `+0x800` relative to a gamma base at `0xf322e000`; the RAM execution itself does not establish or exercise a physical mapping.

## 4. Remaining precision and pixel questions

The evidence currently supports these distinct facts:

- The positive table occupies 257 32-bit storage words; the particular configured values lie in 0–65,535.
- The recovered positive-domain coordinate builder covers 0–65,536 with a boundary point at the upper end.
- The declared still profiles enable gamma dither, and the relocated metadata has separate dither seed and channel-key fields.
- A nine-word negative table and a four-bit negative scale control exist; the audited still table is zero.

Those facts do not establish the hardware image interface's input precision, sign convention, effective output precision, interpolation order, rounding, saturation or dither-state evolution. Nor does the all-zero negative table establish how negative input coordinates map onto its nine entries. A bit-exact photographic stage needs evidence for those operations and its relationship to the upstream CCM and downstream MAIN 3D LUT.

Later instructions in the TMC function perform rescaling/resampling, but they are outside the executed slice and are not presented as a hardware gamma oracle. Neural-denoiser gamma helpers and display gamma paths remain excluded for the reasons documented in the earlier photographic path and pixel contract reports.

## 5. Reproduction and retained material

The scripts read only a privately supplied firmware extraction. Use Python with `pyelftools`, `capstone` and `unicorn`; the execution records pin the versions used for the instruction tests. The native descriptor replay additionally requires an Android AArch64 NDK compiler and QEMU AArch64 user emulator. Its recorded compiler is NDK r27 / Android API 28; runtime files come from the pinned Android 9 firmware.

From the repository root, substitute local paths for the four uppercase placeholders:

```sh
python3 hasselblad_native_audit/main_colour_20261019/gamma/inspect_main_gamma_config.py --firmware-root FIRMWARE_ROOT --output RESULTS/main_gamma_config_metadata.json
python3 hasselblad_native_audit/main_colour_20261019/gamma/verify_gamma_knots.py --firmware-root FIRMWARE_ROOT --output RESULTS/gamma_knots_original_execution.json
python3 hasselblad_native_audit/main_colour_20261019/gamma/verify_gamma_driver.py --firmware-root FIRMWARE_ROOT --output RESULTS/gamma_driver_original_execution.json
python3 hasselblad_native_audit/main_colour_20261019/gamma/replay_main_gamma_metadata.py --firmware-root FIRMWARE_ROOT --clang ANDROID28_CLANG --qemu QEMU_AARCH64 --output RESULTS/main_gamma_register_metadata.json
```

Compiled probes live in temporary directories and are deleted after replay. The package contains owned inspection/test code, the narrow knot primitive, metadata/results and this report. It contains no original firmware, executable instruction bytes, disassembly, photographic LUT arrays, dither-key payloads or user photos.
