# MAIN CCM: verified coefficient preparation

Target: **Hasselblad X2D II 100C firmware 1.3.16.2**. Audit date: 2026-10-19.

## Result

The global still CCM parameter selects **96 signed coefficients** from an
eight-profile, 768-value source table. The axes are four colour temperatures
and two high-ISO blending banks. The original parameter dispatcher, register
metadata and interpolation caller establish this structure; it is not inferred
solely from the array length.

The portable C helper in [ccm_prepare.c](ccm_prepare.c) reproduces this bounded
coefficient preparation. **162 original-code cases, covering 15,552 scalar
outputs, all match both portable C and an independent Python reference.** The
fixtures include varied signed coefficients, the signed16 endpoints and the
actual exact-hash firmware table. Actual coefficients and output arrays are
temporary inputs to the audit and are not included in this repository.

This recovers a useful state-preparation step. It does not establish the
pixel-level CCM formula, coefficient fraction bits, channel order, clipping,
or a complete photographic colour transform. The helper is research code and
is not connected to the Android app's rendering path.

## Evidence chain

The inputs and bounded function identities are in
[ccm_static_evidence.json](ccm_static_evidence.json). The original library is
`librcam.so`, SHA-256
`3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`.
The exact config and schema are pinned separately in that report.

| Link | Verified evidence |
| --- | --- |
| IQ parameter | `main_ccm.lmtx_fw`: `lerp_1d_lut_reg_idx_v5`, `global_frame`, axes `cc_color_temp` and `color_hiso`, `total=16` |
| Schema dispatch | `calc::lerp_1d_lut_reg_idx_v5` is enum 50; the original relocated dispatch table at VA `0x59c240` points that slot to `_calc_lerp_mx_lut_reg_idx_v5`, VA `0x3b9ea8` |
| Parameter getter | `DIQ_iq_main_ccm_lmtx_fw`, VA `0x33f960`; module getter `DIQ_mod_main_ccm_lmtx_fw`, VA `0x33f9a0` |
| Register metadata | 16 register families, IDs `4126, 4129, …, 4171`, each with six components; scalar mask `0xffff`, shift zero |
| Caller | `_calc_lerp_mx_lut_reg_idx_v5` multiplies group size six by total 16, giving stride 96; it obtains axis dimensions, validates the full extent, then calls `mm_mx_lerp_gap` and `DjiIsp_Reg_Set` for each component |
| Enhanced caller | `_calc_lerp_mx_lut_reg_idx_v5_enh`, VA `0x3c3ad8`, uses the same interpolation leaf |
| Signed representation | `_update_ccm_debug_func`, VA `0x31af98`, requires 96 values and converts the 16-bit register representation to signed values for inspection |

The read-only metadata probe produced 46 bounded records, including the calc
dispatch match, group/parameter descriptors and the absence of additional
non-vreg parameters. Its retained result is
[ccm_metadata_original_execution.json](ccm_metadata_original_execution.json).
The original linker and library initializers run when loading the ELF. The
probe does not call a camera-control function or the CCM configuration wrapper.

The [kernel follow-up](CCM_DRIVER_BOUNDARY.md) independently links the CCM
component to the common mapped postprocessing base plus `0x2c000`. Its
`ccm_set_ig0_config` setup routine sign-extends six signed16 inputs and writes
them repeatedly into 16 groups at register offsets `+0x1cc` through `+0x348`.
The userspace descriptor parents place the corresponding `lmtx_fw` region at
physical addresses `0xf322c1cc` through `0xf322c348`. This matches the same
register region and supports signed coefficient storage. It does not prove
that every userspace update calls this setup routine, or establish the hardware
pixel equation. Two subsequent nine-value driver fields occupy distinct
regions and are not substitutes for the 96-coefficient table.

### The secondary axis has two banks

The four CCT knots in the audited global still mode are **2400, 3050, 5550 and
9100 K**. The high-ISO configuration has four gain/rate records: gains 0, 18,
20 and 42, with rates 0, 0, 0 and 256. Those four records do not mean four
coefficient banks.

`_Calc_GetCoeff`, VA `0x3b42a8`, dispatches `cc_color_temp` and `color_hiso`
through the schema's enum values six and 17. The latter branch selects two
neighbouring gain/rate records and interpolates their rates. At `0x3b52b4` it
resets the resulting coefficient index to zero; at `0x3b52bc` it returns an
axis size of two. `_Calc_GetLerpInfo` multiplies the returned dimensions to
form cumulative products `[4, 8]`. This proves the four-by-two organization
used by the bounded leaf probe.

This gain-to-rate control branch was inspected statically. The native probe
supplies the resulting bank weights explicitly; it does not invent a complete
camera-state object to execute the branch.

### Properties of the actual table

The source contains 768 little-endian signed 32-bit slots whose values all fit
signed16. Its packed-byte SHA-256 is
`59d1b6c8a291280a8749f5ca190370e5dbff8ce0e6694a7da779ae5488ae641e`.
Each selected profile has 16 equal six-coefficient rows. The second bank's
four profiles are identical to the first bank's four profiles in this exact
configuration. Consequently changing only the supplied high-ISO bank weight
does not change the prepared output for this table. Synthetic fixtures use
different banks so they also test the interpolation that this real-table
symmetry would otherwise conceal.

`enable_lpf`, `enable_hue_mod`, `enable_desaturation` and `enable_level_ctrl`
are zero throughout the audited global still data. These observations apply
to this configuration, not every camera mode or a recorded live register
snapshot. Equal rows and disabled controls are not a basis for inventing a
three-by-three matrix or its RGB interpretation.

## Portable contract and original-code comparison

[ccm_prepare.h](ccm_prepare.h) defines `hb_ccm_prepare`. It accepts exactly 768
source slots and a 96-slot destination, a CCT and an already calculated Q8 bank
weight in the inclusive range 0–256. Source coefficients must fit signed16.
Its statuses are adapter statuses, not vendor return codes. Invalid arguments
or out-of-range source coefficients leave the output untouched. A temporary
96-value result permits input/output aliasing.

CCT is clamped at the ends of the four-knot axis. Within an interval the
fraction is `floor(256 × (CCT − lower_knot) / interval_width)`. For each
component the reconstruction first interpolates CCT within each bank, then
blends the two bank results. Each interpolation uses:

```text
a + floor((b − a) × weight / 256)
```

The floor for negative products is explicit in the portable code. It does
not depend on the implementation-defined right shift of a negative C integer.
Within the accepted signed16/Q8 domain, every product fits the original
routine's signed32 arithmetic. Equivalence is not claimed for arbitrary
signed32 input coefficients, where the original arithmetic can wrap.

The native oracle calls the original `mm_get_coeff` at `0x2bac00` and
`mm_mx_lerp_gap` at `0x2bb138`, through an anchor verified to belong to the
exact loaded ELF. It runs under the matching extracted Android 9 Bionic
runtime and AArch64 QEMU, with no replacement of either vendor routine.

| Fixture | Cases | Scalars compared | Result |
| --- | ---: | ---: | --- |
| Dense signed synthetic profiles | 54 | 5,184 | All match |
| Alternating signed16 minimum/maximum profiles | 54 | 5,184 | All match |
| Actual global still coefficient table | 54 | 5,184 | All match |
| **Total** | **162** | **15,552** | **All match** |

Cases combine nine CCT samples with six secondary weights: exact knots,
below/above-axis inputs, fractional CCT positions, endpoint bank selections
and asymmetric fractional blends. Every native scalar is compared to the
portable C output and the independently implemented Python result. The full
metadata, result hashes and per-case outcomes are in
[ccm_prepare_original_execution.json](ccm_prepare_original_execution.json).

A separate review found no arithmetic, indexing or ABI issue in this bounded
contract. Its [adapter-contract checks](../ccm_independent_review/ccm_adapter_contract_results.json)
passed 20 cases under AddressSanitizer and UndefinedBehaviorSanitizer: rejected
lengths, weights, null arguments and out-of-range coefficients preserve outputs;
extreme signed32 CCT values clamp safely; exact and partial source/output
aliasing work. These are checks of the portable adapter's own contract, separate
from the original-vendor arithmetic comparisons above.

The source is placed in read-only memory between guard pages, with initialized
padding. Inputs and coordinate records are checked after calls. This bounds
the experiment and detects writes; it is not an instrumented proof that no
read touches padding inside the readable page. Child processes have a 15-second
CPU limit, a 20-second wall limit and core dumps disabled. Probe binaries and
all coefficient input/output files are removed with their temporary directory.

## Reproduce

Install `pyelftools` and `capstone`, supply the exact extracted firmware and
an Android API-28 ARM64 NDK compiler, and supply QEMU user-mode separately.
From this directory:

```bash
python3 replay_ccm_probe.py \
  --firmware-root /absolute/path/to/firmware/extracted \
  --clang /absolute/path/to/aarch64-linux-android28-clang \
  --qemu /absolute/path/to/qemu-aarch64-static \
  --output-directory /tmp/hasselblad-ccm-replay
```

The runner emits the three JSON reports and fails on a wrong firmware/schema/
parser identity, unexpected descriptor shape, failed child execution or
any mismatched output. The static inspection can also run alone:

```bash
python3 inspect_ccm.py \
  --firmware-root /absolute/path/to/firmware/extracted \
  --output /tmp/hasselblad-ccm-static.json
```

The next CCM requirement for rendering is its pixel operation: how the six
coefficients are selected and applied to channels, their numerical scale and
the output's range. Coefficient preparation alone does not answer those
questions or calibrate a phone sensor to the X2D II colour pipeline.
