# Stage41N — MAIN gamma register layout and original preparation/write path

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Starting research commit: `25aa1b75cdbf113c2db13868f2749deb6ad8562d` (Stage41M).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

The MAIN gamma configuration is now connected to its original register descriptors and memory destinations. Its knee has 32 entries per table. Normal, lowlight and EI tuning variants all feed the same register IDs; their selection does not imply three separate hardware register layouts. Original-code replay verifies that table words, including negative slope bit patterns, survive the write path unchanged.

The complete original no-axis knee-preparation path also passes 64 synthetic cases, including original keypoint selection, lookup preparation, slope calculation and publication. This closes more of the software preparation boundary. It does not recover the ISP's RGB pixel equation, the runtime bank for the four real captures, or the axis-dependent gain interpolation used by the normal configuration.

## Recovered field-to-register contract

The analysis connects each named configuration accessor to its record in `.data.rel.ro`, reads the referenced register IDs, then decodes their original 16-byte descriptors. The descriptor base is resolved through the original driver's pointer. These are structural records, not tuning-value arrays.

| MAIN normal field | Register ID(s) | Descriptor contract |
| --- | --- | --- |
| `gamma_lut` | `0x10aa` | 257 32-bit entries |
| `gamma_minus_lut` | `0x10ab` | 9 32-bit entries |
| `knee_kpx` | `0x10ac` | 32 32-bit entries |
| `knee_gain` | `0x10ad`, `0x10ae` | 32 values and 32 slopes |
| `knee_saturation` | `0x10af`, `0x10b0` | 32 values and 32 slopes |
| `knee_clip` | `0x1073` | 12-bit field |
| `knee_y_coef` | `0x1075`, `0x1077`, `0x1079` | Three 10-bit fields |
| `knee_blend_max_det_rate` | `0x107b` | 8-bit field |
| `lut_div` | `0x107d` through `0x1083` | Seven 4-bit fields in one word |
| `lut_div_minus_scale` | `0x1084` | Remaining 4-bit field in that word |

Common enable, knee-enable and dither-enable controls occupy separate bits in one control word. The receipt also records their masks and the dither seed/key bindings.

Register widths do not establish the numerical scale or physical meaning of their inputs. In particular, the 12-bit clip field is not proof of a 12-bit RAW input, and the 10-bit coefficient fields do not by themselves prove a denominator of 1024. The seven gamma division fields mean that the 257-entry table must not be assumed to use a uniform input grid without further evidence.

All corresponding normal, lowlight and EI field bindings resolve to identical register descriptors. This establishes shared destinations for different tuning variants; it does not establish which values were active during a real capture or rule out buffering elsewhere in the ISP.

## Original write chain and numeric behavior

The replay executes the original `DjiIsp_Reg_GetLut`, handle-to-buffer lookup, descriptor lookup, `DjiAdj_Calc_LutMemCopy` and address-resolution functions. Its destination is synthetic emulator memory representing the register/LUT memory; no physical hardware is accessed. This copy chain has no substituted function bodies.

The original implementation copies 32-bit words without rescaling, saturating or changing signed slope bit patterns. Its 64-bit and 128-bit access options copy the same bits in larger chunks. The schema calls these `io32`, `io64` and `io128`; they are distinct from `mem_cfgen`, which selects a memory configuration method. Wide copies are tested only at compatible table lengths. The 257-entry and 9-entry tables use the compatible 32-bit path in these tests.

The copy function performs the hardware-memory copy only when its supplied commit-mode argument equals one. Synthetic mode values zero and two leave that destination untouched. This is a function-level branch result, not an interpretation of all camera operating modes.

Scalar writes use a masked shift and preserve unrelated bits in the shared register word. Oversized values lose bits outside the mask; they are not clamped to the field's maximum. Reads return the masked, shifted unsigned field. This behavior matters when implementing an equivalent parameter loader, but does not describe how the ISP later interprets the fields.

## Complete preparation replay

Stage41M executed the original slope arithmetic block. This stage additionally executes the entire `_calc_knee_data` path for synthetic no-axis input, including:

1. The original table-type and length checks and copy into virtual register memory.
2. The original `adj_calc_knee_kpx_data` selector using synthetic normal-mode flags and a synthetic mode-frame keypoint bank.
3. The original calculator dispatch and simple-LUT preparation for those keypoints.
4. The original signed Q12 slope loop, followed by the original write chain.

Only libc `memset` is intercepted and supplied with its ordinary zero-fill behavior. All configuration objects and values are synthetic, including the minimal FlatBuffer structures used by the original selectors. No original firmware tuning values are copied into the public code or receipt.

For both gain and saturation register pairs, the independent expected output is the input values, the input keypoints and the Stage41M reconstructed signed slopes. Each case checks the full 32-entry tables in both virtual and synthetic hardware memory. It also verifies that source values, surrounding guards and the unrelated knee tables remain unchanged.

The tested no-axis branch corresponds to the generic calculator's direct-table case. The real normal gain declaration uses `gamma_ev`; its axis-dependent lookup/interpolation is **not covered** by this full-path claim. The configured normal saturation declaration has no axis, but synthetic successful execution is still not evidence of the capture's active tuning values. Lowlight/EI runtime keypoint selection and invalid configuration paths remain untested here.

## Validation results

| Check | Cases | Compared output |
| --- | ---: | --- |
| Original LUT-copy chain | 80 | 3,368 table words; all bit-exact |
| Copy disabled by supplied commit mode | 14 | Destination unchanged |
| Original scalar set/get chain | 598 | Exact masked writes/readback, with hardware mirror enabled and disabled |
| Complete no-axis knee preparation | 64 | 6,144 table words per memory view; both views match |

Firmware SHA256 remains `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`. The harness checks it before and after execution. Selected function hashes are recorded in the receipt. All execution is bounded to explicitly selected original functions and the declared `memset` interception; unexpected execution or an exhausted instruction budget fails the run.

The original source RAWs, Stage41J caches and Stage41L comparison are not modified. No Android source or APK changes. Validation is local and uses synthetic inputs; no source photographs or firmware payloads enter public CI.

## What remains at the hardware boundary

This route ends with values written to the ISP's memory layout. The inspected register-set and LUT-copy routines do not implement RGB processing. A narrow check of the gamma-export/metadata and post-capture gamma-configuration helpers also found copying or configuration dispatch, not a recovered pixel equation. That observation is scoped to these inspected routines, not a claim that no software model exists anywhere in the firmware.

Still unresolved: the MAIN pixel input scale; keypoint interpretation and lookup interpolation; gain and saturation numeric units; luminance/max-channel blend; clip behavior; gamma division-grid interpretation; rounding; and the order relative to MAIN CCM and other colour blocks. The four real RAW pairs provide end-to-end image checks, not these hidden intermediate values. The capture firmware 1.1.6.3 also differs from the inspected 1.3.16.2 firmware.

Next work should seek an executable pixel model or controlled stage output for the MAIN gamma block, and independently close the `gamma_ev`-dependent table selection. If candidate RGB equations are fitted against the four RAWs, label them empirical and retain the saturated-red, skin, shirt/background and highlight checks. Do not replace the unresolved pixel equation with the now-verified register-writing code or infer an image-quality gain from synthetic preparation tests.

## Reproduction

The script uses the adjacent Stage41M harness and dependency pins; it requires only locally held original `librcam.so`.

```bash
python -m pip install -r hasselblad_native_audit/isp_knee_stage41m/requirements41m.txt

OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
python hasselblad_native_audit/isp_knee_stage41n/replay_main_gamma41n.py \
  --library /private/original-firmware/extracted/system/lib64/librcam.so \
  --output /private/STAGE41N_MAIN_GAMMA_REGISTERS_SAFE.json
```

Public files contain original analysis code, structural register facts, selected firmware hashes and aggregate synthetic results. Vendor bytes, disassembly, tuning arrays, photographs, capture identifiers and fitted rendering parameters remain excluded.
