# Stage41O — original gamma_ev selection and knee-gain interpolation

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Starting research commit: `72858ee771909644653ea3c55ecba58c42e3ac67` (Stage41N).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

The original single-axis `gamma_ev` knee-gain preparation path now matches an independently expressed integer implementation. The complete original path passes **357 synthetic cases**, covering axis selection, interpolation, keypoint preparation, Q12 slopes and publication into both virtual and emulated hardware memory. This closes the axis-dependent preparation gap left by Stage41N.

This is table preparation, not a recovered RGB pixel transform. Existing RAW pixel access and the four-pair analysis remain available; no new photographic rendering, fitted parameters or APK is produced here.

## Recovered selection contract

In the pinned `librcam.so`, `_Calc_GetLerpInfo` reads the calculator's axis declaration and calls `_Calc_GetCoeff`. For `calc_axis.gamma_ev` (enum 50), the latter obtains the breakpoint vector from the axis table's FlatBuffer vtable slot `0x5a`. It reads the current signed integer from the runtime state: the state pointer is at runtime offset `0xe8`, and this value is at state offset `0xcc`.

The field name links it to gamma exposure selection. Its physical units, conversion from exposure stops, and actual value for any of the four source captures are **not established** by this read. The denominator 256 below belongs to the interpolation weight; it does not establish the units of `gamma_ev` itself or the knee gain values.

For a nondecreasing signed 32-bit axis with at least two entries:

| Position | Lower-bank index | Integer weight |
| --- | --- | --- |
| Below first breakpoint | 0 | 0 |
| Within a span | First `i` with `axis[i] <= x < axis[i+1]` | Signed quotient described below |
| At or above final breakpoint | `count - 2` | 256 |

At an internal breakpoint, the next span is selected with zero weight. Repeated breakpoints are tested as arithmetic edge cases, not endorsed as valid camera tuning. A single-entry axis returns index zero and weight zero. The low-level coefficient helper also does this for an empty axis; the reconstructed full-preparation interface rejects an empty set of banks.

For an interior span, the original coefficient calculation is:

```text
q = sdiv32(wrap32((x - axis[i]) << 8),
           wrap32(axis[i+1] - axis[i]))
```

Here `wrap32` means signed two's-complement 32-bit wrapping. `sdiv32` truncates toward zero, returns zero on a zero denominator, and reproduces the signed-division overflow case. Valid ordinary spans give a weight in 0–256; deliberately extreme synthetic axis values show that wrapping can yield weights outside that interval. The reconstruction preserves that behavior instead of silently clamping it.

## Exact table interpolation

The complete path calls the original `mm_mx_lerp_vec`. This stage verifies its **single-axis** branch. It blends corresponding entries from adjacent banks using:

```text
delta   = wrap32(upper - lower)
product = wrap32(delta * q)
result  = wrap32(lower + (product >> 8))
```

The right shift is arithmetic. Therefore a negative fractional increment rounds downward, unlike signed division that truncates toward zero. This matters for descending table entries. There is no rounding-to-nearest term, floating-point interpolation or saturation in this operation. With zero weight the original vector helper copies the lower bank without reading the upper bank.

Synthetic examples that distinguish common alternatives:

| Lower | Upper | Weight | Original output | Distinction |
| ---: | ---: | ---: | ---: | --- |
| 10 | 9 | 1 | 9 | Negative increment shifts downward |
| 100 | 200 | 85 | 133 | Quantized Q8 weight |
| 0 | 10,000,000 | 256 | −6,777,216 | 32-bit multiply wraps even at the upper endpoint |

The last example is an arithmetic stress case. It does not imply the real camera's tuning reaches this range. Upper-end selection yields the final bank exactly only when the relevant arithmetic does not overflow; the implementation must not replace this branch with a universal final-bank copy if full 32-bit equivalence is required.

The resulting 32 gain values are then published and used to calculate slopes with the already verified Stage41M signed Q12 arithmetic. Keypoint selection and preparation execute through the original normal-selector, mode-frame path. This stage does not substitute a Python result for any original selector, coefficient, interpolation, slope or register-write function.

## Validation

| Check | Cases | Result |
| --- | ---: | --- |
| Complete original `mm_get_coeff` | 4,343 | Exact index and weight |
| Complete original scalar `mm_lerp` | 515 | Exact output word |
| Complete original `mm_mx_lerp_vec`, single axis | 126 | 4,242 exact output words |
| Complete original `_calc_knee_data` with `gamma_ev` | 357 | 34,272 exact table words per memory view |
| Focused reconstruction unit tests | 8 | Passed |

The complete preparation check compares keypoints, gains and slopes in both virtual and emulated hardware memory. It also checks that input banks, the breakpoint vector, supplied state value, surrounding guard words and unrelated knee tables remain unchanged. The source file hash is checked before and after execution.

Every complete case enters `_Calc_GetCoeff`, `mm_get_coeff`, `mm_mx_lerp_vec`, `adj_calc_knee_kpx_data`, the original calculator dispatch and the original LUT-write chain. Only libc `memset` is intercepted with its ordinary bounded stack-fill semantics. No physical camera or MMIO is accessed. Execution is limited to selected original functions and a finite instruction budget; unexpected calls fail.

The receipt records original function identities/hashes, call counts, runtime versions and aggregate results. The source arrays and state are synthetic. It contains no photographs, RAW arrays, original executable bytes, disassembly or vendor tuning arrays.

## Preserve earlier gamma findings and scope

The earlier [MAIN gamma findings](../main_colour_20261019/gamma/MAIN_GAMMA_FINDINGS.md) already verified the positive-coordinate construction used by a MAIN-linked host consumer, with 2,056 original-coordinate comparisons. For the audited static still configuration, its coordinates are uniformly spaced from 0 through 65,536 in steps of 256. The region/division rule also supports nonuniform grids, and those synthetic configurations were checked earlier.

Consequently, Stage41N's broad statement that the gamma input grid remained unresolved was incomplete. **Positive coordinate construction is already verified.** What remains unresolved is the hardware's pixel interface, interpolation, negative-domain behavior, clipping, output quantization and dither. Host coordinate construction does not independently settle those operations or prove the register state of a particular capture.

The same earlier investigation established that the statically mapped ordinary/enhanced still profiles have **knee disabled**. A separate audited still profile enables it. Running knee-table preparation successfully does not prove that hardware applies those tables to a photograph; preparation can occur independently of a stage's enable bit. This stage therefore makes no claim that knee interpolation explains the four pairs' visible highlight differences.

The remaining photographic blockers include the MAIN CCM six-coefficient pixel equation, actual gain/saturation interpretation when knee is enabled, hardware gamma sampling/quantization, the MAIN 3D-LUT sampling contract and capture-specific state. The four RAW/JPEG pairs remain an empirical output reference, not isolated before/after samples for those stages. Firmware analyzed here is 1.3.16.2; the four source captures report 1.1.6.3.

The next investigation should preserve the verified coordinate builder and static knee-enable facts, then focus on a narrow original pixel-operation or active-state lead. Another generic knot or register-layout audit would repeat completed work. Lowlight/EI selection, multidimensional interpolation and the dependency-override branch are outside this stage's tested contract.

## Files and reproduction

- `isp_knee_stage41o/gamma_axis_math41o.py`: independent integer selection and interpolation.
- `isp_knee_stage41o/replay_gamma_axis41o.py`: original-instruction replay using the Stage41M/N harnesses.
- `isp_knee_stage41o/test_gamma_axis41o.py`: rounding, overflow, boundary and interface checks.
- `evidence/stage41o/STAGE41O_GAMMA_AXIS_REPLAY_SAFE.json`: aggregate receipt.

From the repository root, with dependencies from `isp_knee_stage41m/requirements41m.txt` and a private firmware extraction:

```sh
python -m unittest discover -s hasselblad_native_audit/isp_knee_stage41o -p test_gamma_axis41o.py -v
python hasselblad_native_audit/isp_knee_stage41o/replay_gamma_axis41o.py --library PRIVATE_FIRMWARE/system/lib64/librcam.so --output RESULTS/STAGE41O_GAMMA_AXIS_REPLAY_SAFE.json
```

Required source SHA256: `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`. Retain the existing Stage41M and Stage41N directories beside this stage. No firmware download, public CI upload or real-device execution is part of these commands.
