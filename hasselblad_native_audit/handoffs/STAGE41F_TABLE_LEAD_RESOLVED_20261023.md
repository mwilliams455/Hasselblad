# Stage 41F — stream-name and metadata-table lead resolved

23 October 2026 (UK). Stage 41F is complete; no background investigation remains running.

The Stage 41E adjacency lead does not establish a frame producer. The original
`camera-service` contains an indexed stream-name lookup near a separate metadata
printing callback table. The earlier +/-64-byte reference window missed the
relevant lookup base, which is 80 bytes before the label pointer.

## Verified source and result

- Research branch: `recovery/awb-rebuild-20261021`.
- Audit implementation commit: `e1d161ab07b372e923a42bbe7fa96a2a6806d7f0`.
- [Original-firmware CI run 39935641556](https://github.com/mwilliams455/Hasselblad/actions/runs/39935641556): completed successfully.
- Artifact: `Hasselblad-Stage41F-Original-Table-Safe`, ID `12494015528`.
- Original firmware: 1.3.16.2; archive SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.
- Original `system/bin/camera-service` SHA-256: `51b9e02f8bfebf388be8dfa163c8e512bee19aeb8ae37a6712727ccc6f26a52d`.
- Production main remains `929f523aa02ae5b224be39b9c36cce5975691a10`; no phone renderer changes or APK build.

## Concrete findings

| Address / relationship | Original source evidence | Meaning |
|---|---|---|
| `0x8cd170` | Existing RELATIVE relocation to `liveview_after_sbpc` at `0x6c3d63` reconfirmed | A real static name pointer remains established. |
| `0x8cd120`, 80 bytes before the slot | `DCAMUtil::toStreamProfileString(HblmTypes::E_DCAMStream)` forms this base at `0x3034a0`, then loads an eight-byte element with an indexed `ldr` at `0x3034a4` | The relevant lead is a stream-name lookup. The label slot is index 10 relative to this base; the corresponding raw enum value and a runtime invocation have not been proved. |
| `0x8cd080`, 240 bytes before the slot | The `E_StreamGroup` overload uses a different indexed lookup base | The contiguous run of 34 rodata pointers must not be treated as one proven high-level object. |
| `0x8cd190`, 32 bytes after the slot | `DCAMContainer::print(bool)` forms this address at `0x304178` and reads callback pointers; it calls `dcam_enum_container_inner` | Stage 41E's nearby reference is genuine, but concerns the neighboring metadata callback table. It is not an exact label-slot access. |

All five specified executable pointers resolve to exact function entries:

| Offset from label slot | Target | Resolved function |
|---|---|---|
| +32 | `0x304248` | `metadataStringCb` |
| +40 | `0x3043a8` | `metadataUInt8Cb` |
| +48 | `0x304610` | `metadataUInt16Cb` |
| +56 | `0x304878` | `metadataInt16Cb` |
| +64 | `0x304ae0` | `metadataUInt32Cb` |

These callbacks call `logDcamMetadataTag`, Qt message/debug logging and text
stream functions. Their bounded, fully decoded bodies have no indirect control
transfers. Exact mangled names, source symbol tables, sizes, code hashes and
direct callees are preserved in `STAGE41F_ORIGINAL_TABLE_SAFE.json`.

Eight original direct calls to `DCAMContainer::print` were identified, from
reprocessing, metadata-setting and captured-image handling functions. These
callers do not turn the printer into a pixel-export interface. No containing
named STT_OBJECT was established, including after checking compressed debug
symbols. Mapping symbols and indexed consumers support separation of the
adjacent tables, without inventing C++ object extents.

## Corrected audit defect

Stage 41E's ADRP tracker retains stale values when the same X/W register is
overwritten, replaced by another ADRP, or crosses a call/branch boundary. A
synthetic instruction fixture reproduced a false reference after an overwrite.
The Stage 41F tracer invalidates written registers, handles W/X aliases and
stops address propagation across calls and branches. All 12 regression checks
passed locally and in CI.

This defect is distinct from the real-firmware finding: the specific Stage 41E
printer reference at `0x304178` survived the corrected analysis. Its misleading
proximity, and the lookup base outside the original window, explain this lead;
the stale-register defect did not invalidate that particular original reference.

The new targeted pass examined only the pinned camera-service table range and
selected function targets, decoding 128-byte windows from 11 matching PC-relative
seeds. It did not repeat the 733-ELF inventory or the prior full disassembly sweep.
Indirect and cross-basic-block references are explicitly incomplete. No original
code was executed, and all firmware was deleted before artifact publication.

## Research decision and next concrete target

Close the adjacent executable-pointer route as a proposed active frame-producer
interface. This is a source-level resolution of that lead, not proof that the
named stream never carries pixels elsewhere and not a contradiction of X
Unleashed's unpublished external buffer supplier.

The next bounded investigation should use the separately verified AIO plugin
edge `_liveview_mee_on_buffer -> _process_on_buffer`. Stage 41C already shows four
calls to `_calculate_out_result_frame_buffer_info`, four buffer allocations,
`mee_proc`, `cam_filter_simulate_hw_exec`, and reference-frame queue operations.
Inspect that specific helper and its argument/return-field use at those call
sites to identify buffer dimensions, format/domain and ownership. Establish any
link to `LiveViewSBPCManager` and the named stream independently. Do not repeat
the name search or assume that the callback delivers isolated MAIN CCM pixels.

The six-coefficient MAIN CCM pixel equation, active stage order and same-frame
before/after numeric samples remain unproved. Production photographs still use
Photon colour. No new APK was needed for this source-only result.
