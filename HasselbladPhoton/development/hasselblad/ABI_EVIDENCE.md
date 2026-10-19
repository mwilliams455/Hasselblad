# X2D II AWB calibration primitive: ABI and execution evidence

## Location in the standalone source bundle

This evidence document was copied from the audit's `colour_audit/portable/` directory. Relative script references in its reproduction instructions refer to that original location. In the combined bundle, `HasselbladPhoton/` and `hasselblad_native_audit/` are sibling directories. From this document's directory use:

- `../../../hasselblad_native_audit/colour_audit/prove_awb_recalib_unit.py` for the original-instruction proof.
- `../../../hasselblad_native_audit/colour_audit/portable/verify_against_arm64.py` for the portable-core differential check.
- `../../../hasselblad_native_audit/runtime_probe/results/android_portable_vs_original.json` for the additional comparison through matching Android 9 Bionic under QEMU.

The portable C and header copied into the app remain byte-for-byte unchanged. `verification.json` beside this document records their original differential evidence.

## Result and scope

The original X2D II `scene_awb_result_recalib_unit` function has been executed with deterministic inputs, and a small portable C implementation matches its outputs for valid bounded inputs. This is a two-value Q12 calibration calculation inside the camera's AWB code. It does not run the complete AWB algorithm, supply Hasselblad calibration for a phone sensor, process a photograph, or implement HNCS.

The original function, its callers, and its data accesses establish the ABI below. Pair labels A and B deliberately avoid asserting an upstream structure/channel mapping that has not been recovered here.

## Exact input identity

| Item | Value |
|---|---|
| Camera/firmware | Hasselblad X2D II 100C 1.3.16.2 |
| Official package | [Hasselblad CIM](https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim) |
| Package SHA-256 | `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` |
| Extracted library | `system/lib64/libaaa.so` |
| Library SHA-256 | `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba` |
| Architecture | Little-endian ELF64 AArch64, Android |
| Dynamic symbol | `scene_awb_result_recalib_unit` |
| Symbol virtual address / extent | `0x4a39a0`, 56 bytes / 14 instructions |
| Function-byte SHA-256 | `8540aa5c812999a0d36e4e6256a950a72c7b9a9e501ddc8b41726f1208042779` |

The audit is version-specific. First-generation X2D reports and addresses are not used as proof for this X2D II function. The original firmware and executable bytes are external inputs and are not included in the portable implementation.

## Recovered interface

```c
uint32_t scene_awb_result_recalib_unit(
    uint32_t *gain_a_inout,
    uint32_t *gain_b_inout,
    uint32_t calibration_a,
    uint32_t calibration_b);
```

The two pointers must refer to valid writable 4-byte cells when the divisors are nonzero. The audited adapters use separate private cells. Pointer arguments occupy AArch64 `x0/x1`; unsigned scalar divisors occupy `w2/w3`; the raw status occupies `w0`. The vendor enum's source-level type/name is not known; the recovered 32-bit return representation is sufficient for this ABI.

With either divisor zero, the original returns decimal 89 (`0x59`) before reading or writing either cell. Zero input gains are valid when both divisors are nonzero. With nonzero divisors the original returns 0 and computes independently:

```text
output_a = ((input_a << 12) modulo 2^32) / calibration_a
output_b = ((input_b << 12) modulo 2^32) / calibration_b
```

Division is unsigned integer division and truncates the remainder. Q12 unity is 4096. The portable adapter rejects a divisor of zero, and rejects input gains above 1,048,575 (`UINT32_MAX >> 12`) so that its supported domain cannot encounter the original 32-bit shift overflow. A divisor of 4096 preserves a supported input gain exactly. The supplied calibration values still need independently established meaning before this calculation can be used on a phone camera's gains.

## Evidence from instructions and callers

The entire leaf uses `cbz w2` and `cbz w3` as early guards; two `ldr w` / `str w` pairs access the individual cells; `lsl w,#12` followed by `udiv w` performs each calculation. It has no calls, no stack use, no global loads, no context pointer, and no firmware/device interaction. This property is established by the full 14-instruction disassembly, not by the function's name.

| Caller | Call sites | Corroboration |
|---|---|---|
| `scene_awb_get_result` | `0x465dc8`, `0x465df8` | Prepares `x0/x1` as separate 4-byte stack-cell addresses; loads scalar divisors from calibration context; checks `w0` after return; reads the resulting 32-bit cells. |
| `scene_awb_get_recalib_res` | `0x474f94`, `0x474fc4`, `0x475000`, `0x475018` | Applies the routine to calibration fields after named per-unit/e-ND calibration updates; later normalizes WB results using Q12 unity `0x1000`. |

This ties the numerical leaf to AWB calibration. It does not establish the ABI or device requirements of the much larger `scene_awb_lib_run` entry point.

## Independent execution and differential verification

`../prove_awb_recalib_unit.py` requires the exact full-library hash and checks the dynamic symbol address and extent before running any instructions. It maps only the original function, a guarded data page and a private stack, with a sentinel return address and explicit instruction/time bounds. No firmware globals or dependent functions are mapped. Nine cases cover all 14 instructions, including both zero-divisor branches. Only the intended 4-byte cells are accessed; all other data bytes, the stack pointer and callee-saved registers remain unchanged.

`verify_against_arm64.py` compiles `hb_awb_recalib.c` as a host shared library with warnings treated as errors. It compares the compiled C results and the guarded original-callback adapter against actual original ARM64 execution in Unicorn for ten cases. These include independent channel scaling, zero gains, integer truncation, the last inputs that cannot overflow, and large divisors. Four additional cases verify that zero-divisor and overflowing inputs are rejected before the original callback is reached. Missing-original and nonzero-original-status handling are checked separately. The nonzero-status propagation check is explicitly a synthetic adapter failure test, not a claim of original execution.

Separately, `runtime_probe/results/original_awb_recalib.json` records the original `libaaa.so` being loaded through its matching Android 9 Bionic runtime and called under QEMU AArch64. All nine native probe cases pass, including exact status 89 and unchanged buffers for zero divisors. This corroborates that the isolated instruction proof is callable through the real ELF/dynamic-linking interface in that tested runtime.

| Input gains | Calibration | Original ARM64 and portable output |
|---|---|---|
| 4096, 4096 | 4096, 4096 | 4096, 4096 |
| 8192, 12288 | 8192, 6144 | 4096, 8192 |
| 5001, 6001 | 3000, 5000 | 6828, 4916 |
| 4096, 4096 | 2048, 8192 | 8192, 2048 |
| 0, 0 | 4096, 4096 | 0, 0 |
| 1048575, 1048574 | 4096, 4095 | 1048575, 1048830 |

## Adapter behavior

`hb_awb_recalib_portable` performs the recovered arithmetic after guards. `hb_awb_recalib_original` optionally delegates to an already loaded, exact-hash, ABI-verified original. It does no loading or arbitrary symbol casts itself. Native original delegation applies only when the executable architecture matches the original AArch64 ELF; the portable operation may be compiled for other architectures.

The adapters use their own explicitly named status values. Their zero-divisor guard returns `HB_AWB_ZERO_CALIBRATION`, not a fabricated vendor return. `original_status` is meaningful only when `original_called` is true. When the original reports a nonzero status, the adapter preserves that status and withholds partial results; output remains equal to the input.

## Remaining work before photographic use

The Q12 operation is small and useful as a verifiable first recovered computation. Complete photographic use still needs a proven mapping from the phone's RAW/gain metadata into the relevant target units, sensor-specific calibration, frame-pipeline integration, and image comparisons against a defined reference. Full AWB initialization/configuration, spectral-sensor inputs, photographic colour/tone rendering and HNCS remain separate tasks. Successful loading in the matching firmware Bionic runtime does not prove that all vendor dependencies are usable in an ordinary app namespace on a current phone.
