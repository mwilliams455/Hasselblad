# MAIN colour preparation checkpoint

**2026-10-19 · Hasselblad X2D II 100C firmware 1.3.16.2**

This checkpoint adds verified CCM coefficient preparation, a recovered MAIN
gamma coordinate primitive, the kernel's MAIN table-submission contract, and
a resolved host-to-DSP boundary for the inspected RAW-to-RGB route. These are
concrete additions to the standalone Hasselblad Photon project.

**The Android application remains Native1A. Its photographs still use Photon's
renderer. A complete Hasselblad photographic colour transform is not yet
connected or validated.** The new code lives in the research tree; this
checkpoint does not produce a new APK or claim a new physical-device test.

## What advanced

| Area | New verified result | Evidence |
| --- | --- | --- |
| CCM coefficient preparation | Four CCT knots and two secondary banks select 96 signed coefficients. A portable C implementation matches 15,552 original scalar outputs. | [CCM findings](ccm/CCM_FINDINGS.md) |
| Gamma coordinates | The seven division controls encode interval counts. The configured 257 positive-domain coordinates span 0–65,536 in steps of 256. A portable Python primitive matches all 2,056 tested original coordinates. | [Gamma findings](gamma/MAIN_GAMMA_FINDINGS.md) |
| Gamma register submission | Full execution of the original driver leaf verifies division-field packing and complete 32-bit table writes in four synthetic cases, covering all 199 instructions. | [Gamma driver execution](gamma/gamma_driver_original_execution.json) |
| MAIN 3D LUT submission | The actual kernel setter copies 6,144 LUT words and the separate 33-word pre-gamma table without unpacking or rescaling. All 32 tested control combinations pass. | [MAIN LUT findings](main_lut/MAIN_LUT_FINDINGS.md) |
| CCM hardware-register link | The userspace 16-by-6 coefficient descriptor region matches the kernel CCM block. Its setup path sign-extends six input values into 16 repeated register groups. This is a register contract, not a pixel equation. | [CCM driver boundary](ccm/CCM_DRIVER_BOUNDARY.md) |
| Saved-image dispatch | The inspected RAW-to-RGB branch reaches a DSP function client named `cam_libpp_function_entry`, then the camera's ICC transport. The associated packaged DSP family is encrypted. | [Dispatch findings](dispatch/DISPATCH_FINDINGS.md) |

The executable portable pieces are [ccm_prepare.c](ccm/ccm_prepare.c) with its
[C interface](ccm/ccm_prepare.h), and [gamma_knots.py](gamma/gamma_knots.py).
They contain no camera tuning arrays or firmware instruction bytes. Each
exposes the bounded mathematical operation that has an original-code oracle.

## The colour pipeline has several distinct operations

The preceding [saved-still configuration investigation](../photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.md)
identified separate enabled `MAIN_CCM`, `MAIN_GAMMA` and `MAIN_3DLUT` modules in
the declared ordinary and enhanced still segments. A separately named
`MAIN_HNCS` module is bypassed in those declarations. Module names and topology
declarations are not a live capture trace or a complete hardware stage-order
specification.

The new work makes those distinctions more precise. CCM coefficient selection
depends on colour temperature and a high-ISO blending rate. In this exact
global table the two secondary banks happen to be equal; asymmetric synthetic
fixtures ensure that the tests still exercise bank interpolation. Gamma has
257 positive entries, a separate negative table and dither controls. The
positive curve's stored values range from 0 to 65,535, while the earlier MAIN
LUT profile inspection found 12-bit-sized values in paired lanes. Those
different observations do not establish the conversion between stages.

The MAIN LUT has a 33-entry pre-gamma parameter with 13-bit register fields.
The config under inspection disables it. It therefore supplies no established
explanation for the gamma-to-LUT input conversion in this mode. The prior
[display sampler](../pixel_contract_20261019/PIXEL_CONTRACT_FINDINGS.md) remains
evidence for the display path; sharing a table size is insufficient to assign
its component ordering or trilinear sampling to saved-image MAIN hardware.

## Original-code validation

| Check | Scope | Recorded outcome |
| --- | --- | --- |
| CCM preparation | Original `mm_get_coeff` and `mm_mx_lerp_gap` under the original Android 9 Bionic runtime and AArch64 QEMU; each scalar checked against portable C and independent Python | 162 cases, 15,552 scalar outputs, all match |
| CCM metadata | Bounded reads of the original linker's relocated parameter, dispatch and register records | 46 records, expected 16-by-6 layout and dispatch match |
| Portable CCM adapter contract | Independent ASan/UBSan check of lengths, ranges, output preservation, CCT extremes and buffer aliasing | 20 cases pass; separate from vendor arithmetic tests |
| Gamma coordinate construction | Exact inline instructions from a consumer of MAIN gamma register 4266; private live registers and guarded stack | 8 cases, 2,056 coordinates, all match; 8 adapter guards pass |
| Gamma driver | Complete original `gamma_set_info` instruction body; synthetic RAM replaces MMIO | 4 cases, all 199 instructions covered, register images and guards match |
| Gamma metadata | Original relocated descriptors and exact still-mode config | 34 register records; five selected still modes checked |
| MAIN LUT driver | Complete original `lut_set_lut_info` body; synthetic RAM, enable/shadow/IRQ state variations | 32 cases; 49,152 copied LUT words and 264 pre-gamma words compared; all pass |
| DSP boundary | Static, hash-pinned host relationships and packaged-image inspection | 13 input files, 26 function hashes and 32 direct calls checked; all four encrypted-payload hashes match |

The probes have narrow roles. Running a register writer against ordinary RAM
verifies what the CPU submits; RAM does not simulate the image-processing
hardware's response. Executing a selected instruction slice verifies that
slice with its documented inputs; it does not execute the full TMC algorithm.
The reports identify static relationships, original-code execution, synthetic
fixtures and actual-table tests separately.

All inputs are pinned by hashes. Generated probe binaries and temporary camera
coefficient input/output files are deleted after execution. Per-directory
reports provide reproduction commands, dependencies, input identities, result
hashes and limitations. [CHECKPOINT_MANIFEST.json](CHECKPOINT_MANIFEST.json)
records the retained file set.

Independent reviews of the [CCM implementation](ccm_independent_review/ccm_independent_review.json),
[gamma experiments](independent_reviews/gamma_review.json) and
[MAIN LUT experiments](independent_reviews/main_lut_review.json) found no
blocking issue. The gamma and LUT instruction experiments were independently
replayed with byte-identical result reports.

## Android compatibility and the DSP boundary

Android 9 and AArch64 make the host libraries accessible to these matching
runtime experiments. The inspected `raw2rgb_proc` branch still builds a
request for the camera's DSP framework. It relies on the correct context,
shared buffers, transport driver and server implementation. Loading that
Android library in a phone app alone does not reproduce those resources.

The packaged SS DSP images and auxiliary image are encrypted IMaH v2
containers. The six variants in the precisely pinned public format/tool
source fail the plaintext checksum for every inspected image: 24 tested
combinations, no recovered server implementation. This is a bounded negative
result for that candidate set, not proof that no further legitimate route
exists. The host strings support a CEVA-family attribution; the exact DSP
instruction set and server ABI are not established. Nor has this investigation
established which MAIN colour modules, if any, this particular RPC applies.

The useful implementation path supported by this checkpoint is therefore to
recover and verify portable operations individually, with explicit evidence
for their interfaces. The newly verified ARM arithmetic is progress along
that path even though the complete DSP renderer remains unavailable.

## Requirements before the first validated photographic transform

1. **Recover the CCM pixel equation.** Establish how its six coefficients and
   region selection act on channels, their scale and their clipping behaviour.
   The prepared coefficient table and hardware address map are now known.
2. **Finish the MAIN LUT pixel contract.** Establish component/bank order,
   grid coordinates, input normalization, interpolation and output rounding.
   Kernel submission no longer hides a software unpack or rescale, but the
   hardware operation remains unverified.
3. **Resolve gamma evaluation and stage interfaces.** Positive knot positions
   are recovered. Pixel interpolation, endpoint/sign handling, quantization,
   dither and the conversion into the MAIN LUT still need an oracle.
4. **Define the phone calibration adapter and validate images.** The phone's
   RAW samples, black/white levels, white balance and colour transforms must
   feed the established working colour domain. X2D II sensor-specific tuning
   cannot be assigned directly to unrelated phone RAW values on the basis of
   these coefficient tests.

The image milestone is a deterministic, same-input comparison through the
established stages, followed by a single-frame PHOTO/SDR phone run. The
standalone capture policy continues to target the advertised standard RAW
size nearest 12.5 MP. This research is scoped to the standalone Hasselblad
project; Leica-system integration remains a later task.

## Source and continuity

The starting repository commit is
`336c0425e2ea88d8a04f40e459c5de4760dbf7d9`. The Photon app and pinned upstream
base are described in the [repository README](../../README.md); this
checkpoint does not claim to have rebased to a newer Photon revision.

New original inspection/probe code and mathematical primitives in this
checkpoint are provided under the existing [MIT research licence](../LICENSE-MIT.txt).
Upstream projects and their separate terms remain documented in the
[research notices](../THIRD_PARTY_NOTICES.md). Firmware, proprietary tuning
payloads, user photographs and generated binaries are separate inputs or
artifacts and are absent from this source checkpoint.
