# HasselbladPhoton — Stage 41E → Stage 41F research handoff

**Prepared:** 23 October 2026 (UK)  
**Purpose:** Resume the original X2D II / X Unleashed live-view-source investigation in a new chat without redoing Stages 6–41.  
**Status at handoff:** **Stage 41E CI completed successfully. No task is running in the background.** Stage 41F has **not** been implemented, committed or executed.  
**Priority:** Evidence-based, firmware-equivalent Hasselblad colour processing in the Photon-based Android app, not a generic colour filter.

## 1. Start here — exact continuation instruction

> **Continue HasselbladPhoton from Stage 41E using this handoff. First verify the recovery branch and inspect the saved Stage 41E JSON and audit source. Implement Stage 41F as a narrow, read-only source audit of the `camera-service` table containing `liveview_after_sbpc`: identify the neighboring executable-address relocation targets and their genuine ELF symbol owners/callers, determine whether the table is logging/container metadata or an active frame-producer interface, and report only sanitized metadata. Keep X Unleashed's original live-view NV12 output and the AIO `LiveViewSBPCManager` paths distinct until original dataflow proves a link. Do not assume this is an isolated MAIN CCM pixel oracle, do not modify Photon photo output, do not touch production `main`, and do not repeat completed broad ELF searches.**

The immediate research is **Stage 41F: ownership and use of the relocated `liveview_after_sbpc` label table**, not new CCM coefficient-preparation work. If that route proves to be metadata only, close it honestly and evaluate the separately identified SBPC buffer processing graph, without another generic scan.

## 2. Repository, branch, and build state

| Item | Exact checkpoint |
|---|---|
| Repository | [`mwilliams455/Hasselblad`](https://github.com/mwilliams455/Hasselblad) |
| **Active research branch** | `recovery/awb-rebuild-20261021` |
| **Verified Stage 41E audit-source commit** | `3f96b125361ad600b27590d93455b45fb69846c9` (prior to adding this handoff) |
| **Verified production `main` HEAD** | `929f523aa02ae5b224be39b9c36cce5975691a10` — unchanged |
| Last verified phone APK | Stage 36 debug signed `HasselbladPhoton-Stage36-27190-debug.apk`, versionCode `27190`, versionName `0.1-hb-dual36` |
| APK SHA-256 | `4195998396bde52b3f6604c337797be8f49a38beee714d4e4129afd693e48d29` |
| App ID | `com.mwilliams.hasselbladphoton` |
| Stage 36 build | [Run 39903851434 — success](https://github.com/mwilliams455/Hasselblad/actions/runs/39903851434) |
| Android physical test device | Xiaomi 15 Ultra, 4096×3072 standard RAW capture; app should remain cross-device, not Xiaomi-only |
| Production image colour | **Still Photon**. Authentic Hasselblad HNCS/photo colour not yet enabled or proven. |

**Important:** Do not claim a new APK or a verified HNCS renderer was made in Stages 37–41. Those stages were source-only research and CI. The user prefers firmware equivalence, darker photographic rendering and single-frame capture, without silent HDR/stacking. Leica M9/Monochrome feature sharing is later, after Hasselblad functionality is proven.

## 3. Exact Stage 41E result — the active lead

**CI:** [Stage 41E run 39932390658 — completed, success](https://github.com/mwilliams455/Hasselblad/actions/runs/39932390658). Original-firmware extraction was transient; no camera was accessed. The final safe artifact was named `Hasselblad-Stage41-XUnleashed-Original-Liveview-Safe` (artifact ID `12492097569`). Its `STAGE41E_ORIGINAL_SBPC_POINTER_SAFE.json` is the authoritative machine-readable result.

**Primary original source:** X2D II firmware **1.3.16.2** — `system/bin/camera-service`, SHA-256 `51b9e02f8bfebf388be8dfa163c8e512bee19aeb8ae37a6712727ccc6f26a52d`.

| Confirmed property | Actual recorded finding |
|---|---|
| Exact literal | `liveview_after_sbpc` |
| Literal location | `.rodata`, ELF VA `0x6c3d63`, file section offset `0x26513` |
| Relocated pointer slot | `.data.rel.ro`, ELF VA `0x8cd170` (section offset `0x12e90`) |
| Relocation type | AArch64 `R_AARCH64_RELATIVE` = **1027**, in `.rela.dyn` |
| Neighboring pointer relocations | Relative offsets `−64` to `+24` in eight-byte steps target `.rodata`; offsets `+32`, `+40`, `+48`, `+56`, `+64` target `.text` (all type 1027 in this bounded window) |
| ELF object symbol enclosing exact pointer | **None established**; recorded `matched_named_containing_objects=[]` |
| Bounded code-site candidates | **One**: `DCAMContainer::print(bool)` (`_ZNK13DCAMContainer5printEb`), instruction site `0x304178` |
| Crucial limitation on that candidate | It references an address **32 bytes from** the relocated string pointer, **not the exact slot**; `exact_pointer_slot_access=false` |
| Instruction search coverage | `1,485,599` original AArch64 instructions |
| Running frame source or hook installation verified? | **No** |
| Original stage position / pixel format verified by this pointer? | **No** |
| Isolated pre-/post-MAIN CCM RGB pixels obtained? | **No** |

**Interpretation:** The mixture of `.rodata` string pointers and adjacent `.text` pointers is consistent with some sort of table or registration object, but **its concrete type and consumer are unknown**. Treat `DCAMContainer::print` as a **nearby reference candidate, not the owner**. Neither the existence of the string nor this relocation proves that X Unleashed has supplied a usable `camera-service` pixel hook, that the source is after CCM, or that it has a legal public deployment mechanism. Do not infer that all adjacent code pointers belong to the same high-level object without resolving its extents and actual references.

**Targeted next action:** Map each +32..+64 `.text` relocation destination to exact functions in the pinned ELF (use `.dynsym`, `.symtab`, bounded `.gnu_debugdata` and section coordinates as applicable); group the data-pointer window by relocation, alignment, pointer target sections and candidate object boundaries; trace consumers through direct and data-pointer address references. Preserve uncertainty where owners remain stripped/indirect. No vendor source bytes or full disassembly should enter public artifacts.

## 4. Stage 41A–D evidence already proved — do not repeat

### Stage 41A: external source and original firmware link

- [CI run 39929388253 — success](https://github.com/mwilliams455/Hasselblad/actions/runs/39929388253) verified two **pinned, unmodified** host-only tests from the third-party X Unleashed project: `test_liveview.c` and `test_eagle2_abi.c`. The first original-firmware CI attempt [39929168169](https://github.com/mwilliams455/Hasselblad/actions/runs/39929168169) failed solely because a filename was outside the audit's safe-path character allowlist; this was fixed by counting/skipping unsafe names, and the rerun passed.
- The firmware scan covered **733 original AArch64 ELF files**; **83** had related SBPC/live-view labels; the exact `liveview_after_sbpc` literal was found in **`system/bin/camera-service`**.
- The X Unleashed project documents its camera-side source as `liveview_after_sbpc`, but its public publisher is supplied a buffer by an external, original consumer. The complete camera-side installation/hook path is not published.

### Stage 41B: original call-graph triage

- [CI run 39930378914 — success](https://github.com/mwilliams455/Hasselblad/actions/runs/39930378914).
- Original `camera-service` SHA pinned as above; `libdcam_plugins_AIO.so` source path `system/lib64/camera/plugins/libdcam_plugins_AIO.so`, SHA-256 `1924f9aca6d5f4f92ff482f6a864579d303a890fcef3427053f35d9b00bd4135`.
- A bounded scan of `camera-service` direct AArch64 `ADR` / `ADRP`+`ADD` references to the exact literal found **zero**; this did not exclude data-section relocation references, confirmed in Stage 41D.
- `libdcam_plugins_AIO.so` contains `LiveViewSBPCManager` names and the **verified direct edge** `_liveview_mee_on_buffer → _process_on_buffer`. Stage 41B initially had unresolved external callees, improved by Stage 41C.

### Stage 41C: original SBPC buffer processing

- [CI run 39931031784 — success](https://github.com/mwilliams455/Hasselblad/actions/runs/39931031784).
- PLT import mapping and original code identities were verified for 11 selected `libdcam_plugins_AIO.so` functions.
- Original `_process_on_buffer` has **9,516 bytes / 2,379 AArch64 instructions / 251 direct calls** in the bounded report, and calls named functions including `mee_proc`, `cam_filter_simulate_hw_exec`, `frame_buffer_alloc_vmem_by_heap_id`, plus `memcpy` and queue/buffer operations.
- `LiveViewSBPCManager` has `requestDspHandler`, `releaseDspHandler`, `registerContainerCmd`, `updateLiveviewSBPCMode`, `onSwitchSegmentSuccess` and calibration-related functions. Its DSP handler/container relationship is genuine, but its relationship to the `camera-service` named label and the `MEE`-labelled buffer callback is **not proven**.
- No input format, original buffer bytes, active stage placement or pre/post CCM sample pair was obtained.

### Stage 41D: relocated table evidence

- [CI run 39931765896 — success](https://github.com/mwilliams455/Hasselblad/actions/runs/39931765896).
- The exact literal resides in `.rodata`, with one `R_AARCH64_RELATIVE` relocation from the pointer at `.data.rel.ro + 0x12e90` (VA `0x8cd170`). Earlier absence of a direct instruction reference was therefore *not* proof of an unused label.
- The bounded structured stage-token search found only `liveview_after_sbpc` among the matching labels. It did not find a recognized `liveview_before_sbpc` or specifically MAIN-CCM-labelled sibling.
- These are source relationships only, not a live capture trace.

### Audit code / workflow paths

All on branch `recovery/awb-rebuild-20261021`:

- `hasselblad_native_audit/isp_liveview_stage41/inspect_original_liveview41.py`
- `hasselblad_native_audit/isp_liveview_stage41/inspect_original_liveview_xrefs41b.py`
- `hasselblad_native_audit/isp_liveview_stage41/inspect_original_sbpc_processing41c.py`
- `hasselblad_native_audit/isp_liveview_stage41/inspect_original_sbpc_labels41d.py`
- `hasselblad_native_audit/isp_liveview_stage41/inspect_original_sbpc_pointer41e.py`
- `hasselblad_native_audit/isp_liveview_stage41/README.md`
- `.github/workflows/hb-stage41-x-unleashed-liveview.yml`

**Last original CI evidence ZIP:** [Stage 41E GitHub Actions run 39932390658](https://github.com/mwilliams455/Hasselblad/actions/runs/39932390658) → artifact ID `12492097569`, file `STAGE41E_ORIGINAL_SBPC_POINTER_SAFE.json` inside the safe ZIP. Also includes 41A–41D audit JSON and upstream test receipts. **Fetch the artifact anew if it is no longer present in the new chat**; local sandbox links must be reverified, never invented.

## 5. User-provided third-party sources, verified boundaries

**[YuHaoyua/hasselblad-cim-firmware-extractor](https://github.com/YuHaoyua/hasselblad-cim-firmware-extractor)**, public `main` commit `768664267cb44621c3c12595ee9cc538020b1b94`. Uses AES-128-CBC with 4,096-byte chunk resets to decrypt the **outer CIM container**, compatible in key/chunk behavior with our already-working `hasselblad_native_audit/cim_reader.py`. Adds independent timestamp-derived IV and MD5+salt checks. It **does not** decrypt the separately encrypted DSP payloads. Repo lists MIT. Its extraction fallback/hash-mismatch behavior warrants independent checks; do not replace validated extractor solely on its README.

**[scanfsec/hasselblad-x-unleashed](https://github.com/scanfsec/hasselblad-x-unleashed)**, pinned public `main` commit `dd798e5e51a8bebc333ce7026c7fa700a0feb96c`.

- `hasselblad_monitor/uvc-gadget/eagle2_v4l2_abi.h` documents an Eagle2 modified V4L2 `v4l2_buffer` ABI: **96 bytes** versus the standard 64-bit host **88 bytes**, with extra timestamp at offset `+40`; selected ioctl request sizes must be adjusted. Both the published mock V4L2 test and the published live-view test passed in pinned host-only CI.
- `liveview_bridge.c` and `liveview_frame.h` accept a borrowed **NV12 YUV input** with source width/height, stride, UV offset and frame ID, convert/downsample to **640×480 8-bit YUYV** and publish a sequence-guarded shared-memory frame for a UVC monitor. The bridge **does not acquire or retain the original camera buffer**. This is a plausible postprocessing/live-view **output reference**, not an isolated linear CCM result.
- The repository's kernel-runtime documentation quotes original `kheaders.ko` SHA-256 `b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b`, an exact match for our earlier X2D II 1.3.16.2 firmware extraction. This establishes generation-level technical relevance, not a full active-pipeline proof.
- The root does not expose a uniform license; camera-side `uvc-gadget/LICENSE` says GPL-2.0. **Do not copy its code into our Photon APK without reviewing licensing.** The project states deployment/exploit details may be withheld. **No unattended root, ADB enabling, kernel module loading or camera patching.**

Prior combined assessment is in `hasselblad_native_audit/handoffs/STAGE40G_THIRD_PARTY_CIM_AND_EAGLE2_LIVEVIEW_20261023.md` (recovery branch commit `b953a88681b22077d9e6c5d944a78415fbe033ad`).

## 6. Original Hasselblad colour-science work worth preserving

**Target:** firmware-*equivalent* Hasselblad colour, preserving true camera processing where it can be proven, while adapting input calibration properly for phone sensors. Do not guess the Eagle2 hardware maths, a CCM 3×3, a fixed-point shift or a 3D LUT swizzle and call them original-equivalent.

| Work | Verified | Still blocked |
|---|---|---|
| Stage 17 / 25 / 27 MAIN CCM | Original `lmtx_fw` consists of **16 groups × 6 signed coefficients**; 4 CCT knots at **2400/3050/5550/9100 K**, two high-ISO banks. Prepared result is 96 coefficients. The actual original static still groups and banks are equal, so group selection need not be the *first* question for that restricted table. | **Hardware six-coefficient pixel equation, input channel mapping/Q scale/rounding/clipping, dynamic overrides.** |
| 19 Oct original CCM arithmetic | Portable C `hb_ccm_prepare` matched **162 native cases / 15,552 signed scalar outputs**, including original tuned profiles. | Coefficient selection ≠ applying to pixels. |
| Stage 25 / 31 / 39 driver & debug | Register bank matches at CCM physical block `0xf322c000`, 96-word region `+0x1cc..+0x348`; separate adjacent nine-value arrays are level-control LUTs, **not 3×3 matrices**. Stage 39 found no CCM frame-export callback in 20 named functions; `.altinstructions` reference was not an image callback. | No MAIN CCM before/after pixel oracle. |
| MAIN gamma | 257 positive entries and seven division controls `[2,2,3,4,5,6,7]` with verified knot positions **0..65536 step 256**, **2,056 original coordinate comparisons**. Original driver table writer independently tested. | Pixel gamma interpolation, negative-domain behavior, dither/quantization and stage interface. |
| MAIN 3D LUT | 8 camera source profiles × **6,144 32-bit words**, 2 × signed16 lanes per word; CCT/gamut preparation verified under original code. Original driver submits 6,144 words without reordering. | Actual MAIN input transfer domain, RGB bank/grid order, interpolation and rounding. Original **display** 16³ decoder/trilinear sampler is not evidence for photographic MAIN. |
| Named still topology | Declared ordinary/enhanced still paths enable `MAIN_CCM`, `MAIN_GAMMA`, `MAIN_3DLUT`, while the separately named `MAIN_HNCS` is bypassed **for those mapped segments**. | A static topology is not an end-to-end live capture trace or proof that HNCS never operates elsewhere. |
| DSP layer | Host original `raw2rgb_proc` routes through `cam_libpp_function_entry` and camera's Linux ICC/DSP transport; packaged SS DSP firmware encrypted as IMaH-v2/TBIE. | Decrypting the outer CIM does **not** decrypt the DSP or reveal Eagle2 hardware pixel equation. |
| Stages 24–36 phone DNG | Stage 36 **genuine, source-bound 4,096×3,072 DNG**; original Camera2 neutral versus Photon-effective neutral native double call passes `PASS_BOUND_REAL_DNG_DUAL_NEUTRAL_LINEAR_TILE`. Same 1,024 RAW tile, measured linear-sRGB reference differences, original RAW and saved photographs unchanged. | This is **not** HNCS, not AWB calibration and not a full-frame Hasselblad renderer. |

### New firmware cross-check, Stage 40

X2D II 100C **1.3.18.1** released 22 October 2026 and independently hash-pinned: official CIM **365,283,840 bytes**, SHA-256 `c65970cbc1519f876aa3296411f8bb5075995dabc9479bb8abb635945dad6496`; old **1.3.16.2** is 364,814,336 bytes, SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.

- Stage 40B/C: **1,617 files** each; **1,368 identical, 249 changed**. Entire original `hb722_config.json` and colour tuning, still CCM, gamma, LUT, camera topology, original RAW-to-RGB *host* `libdcam_pp.so` were unchanged; `librcam.so`, `vcam_driver.ko`, `libaaa.so` and encrypted DSP images had changed full-file hashes.
- Stage 40D: Among selected original functions, 12 byte-identical, 13 byte-changed, 2 unresolved; **all 25 resolvable function mnemonic sequences identical**, 15 normalized operand shapes matching.
- Stage 40E new-firmware original native CCM preparation: **162 cases / 15,552 scalar comparisons passed** under matching Android/QEMU, not a pixel transform; [CI 39922831961](https://github.com/mwilliams455/Hasselblad/actions/runs/39922831961).
- Stage 40F new-firmware native MAIN LUT profile *preparation*: **22 cases** (12 synthetic + 10 original camera profiles), including 122,880 lanes in ten real profile cases; [CI 39923834306](https://github.com/mwilliams455/Hasselblad/actions/runs/39923834306). **Not** the original MAIN LUT pixel sampler.

**Do not transfer Stage 41E literal addresses or symbols to firmware 1.3.18.1 without a new exact-hash analysis.** Stage 41 original-source proof is for **1.3.16.2** only.

## 7. Stage 38 prior frame-dump evidence — distinct from X Unleashed

The original software exposes `pp_dump_frame_to_file_base` in `libdcam_pp_base.so`; Stage 38C counted **50 direct calls** to that exporter from **26 named functions** in `libdcam_pp.so`, notably fusion/HDR/denoising paths. No direct exporter call was demonstrated in the bounded ordinary `raw2rgb` caller list or `librcam.so`. The exporter uses file IO, but **this alone does not reveal a MAIN CCM input/output pixel tap**. Do not confuse it with the new `camera-service` SBPC label or AIO plugin's MEE buffer callback.

Original combined handoff: `hasselblad_native_audit/handoffs/STAGE38_ORIGINAL_ISP_PIXEL_ORACLE_INTERFACES_20261023.md`.

## 8. Actionable Stage 41F sequence and acceptance gates

1. **Reconfirm identity and availability.** Stage 41E source commit `3f96b125361ad600b27590d93455b45fb69846c9` (before handoff commits); production main `929f523aa02ae5b224be39b9c36cce5975691a10`. Read Stage41E script/results first. All original artifact links should be fetched from GitHub, not inferred from old sandbox references.
2. **Narrow relocation-table/object audit.** Within exact-hash `camera-service`, safely resolve `.data.rel.ro` addresses `0x8cd170 + {32,40,48,56,64}` to named `.text` functions or explicitly classify as unnamed; record function size/class, symbol owner, outgoing calls and original reverse references. Preserve source hash and section offsets, no raw original bytes.
3. **Check object semantics, not just adjacency.** Determine whether `.data.rel.ro` slot `0x8cd170` is part of a Qt metadata array, a `DCAMContainer` descriptor, a vtable-like structure, a printer/logging table or a live processing registry. Trace verified *consumer* of the exact slot and compare against the sole prior nearby candidate `_ZNK13DCAMContainer5printEb` whose address use was **+32**, not exact. Stop if evidence cannot resolve it.
4. **Keep distinct paths apart.** `camera-service` named label, `libdcam_plugins_AIO.so:LiveViewSBPCManager` DSP handler, `_liveview_mee_on_buffer → _process_on_buffer`, Stage38 frame-file exporter and X Unleashed's borrowed NV12 publisher are **five separate pieces** until a verified original call/pointer/buffer graph links them.
5. **Pixel-oracle qualification.** Even a real live-view output would be only an output reference. An authentic CCM oracle needs same-frame numeric RGB samples *immediately before and after* hardware MAIN CCM, validated bit depth/black-white normalization/channel order, active six coefficients and gamma/LUT state, and neutral/basis/mixed/near-clip inputs. If not available, say so and do not declare parity.
6. **Safe CI and deliverables.** Add a source-only Stage41F audit (or Stage42 if filename scheme requires), synthetic tests and CI that transiently downloads exact 1.3.16.2, checks SHA-256, extracts as inert data, deletes firmware before artifact upload, and emits sanitized JSON with exact symbol/relocation provenance. Never commit source ELF, DSP, original tuning, images, private data or arbitrary vendor code. Do not modify `HasselbladPhoton`, production main or saved photographs. If no new source evidence appears, document a negative finding instead of repeating broad scans.
7. **External-camera experiments require explicit informed consent.** Do not modify a real X2D II, load kernel modules, enable privileged debugging, overwrite firmware or trigger invasive tracing based on this handoff. Owner-approved and nondestructive *read-only* output reference collection can be considered separately once the pipeline stage is independently identified.

## 9. Exact links for the new chat

- [Stage 41E successful CI and evidence artifact](https://github.com/mwilliams455/Hasselblad/actions/runs/39932390658)
- [Stage 41D successful CI](https://github.com/mwilliams455/Hasselblad/actions/runs/39931765896)
- [Stage 41C successful CI](https://github.com/mwilliams455/Hasselblad/actions/runs/39931031784)
- [Stage 41B successful CI](https://github.com/mwilliams455/Hasselblad/actions/runs/39930378914)
- [Stage 41A successful CI](https://github.com/mwilliams455/Hasselblad/actions/runs/39929388253)
- [Stage 40G external source comparison](https://github.com/mwilliams455/Hasselblad/blob/recovery/awb-rebuild-20261021/hasselblad_native_audit/handoffs/STAGE40G_THIRD_PARTY_CIM_AND_EAGLE2_LIVEVIEW_20261023.md)
- [Independent CIM extractor](https://github.com/YuHaoyua/hasselblad-cim-firmware-extractor)
- [X Unleashed source/research](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/README.en.md)
- [Eagle2 V4L2 buffer ABI](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/uvc-gadget/eagle2_v4l2_abi.h)
- [X Unleashed NV12 live-view bridge](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/uvc-gadget/liveview_bridge.c)
- [Stage 41 audit source directory](https://github.com/mwilliams455/Hasselblad/tree/recovery/awb-rebuild-20261021/hasselblad_native_audit/isp_liveview_stage41)

**Last sentence for the new investigator:** The next task is **to resolve the original camera-service relocated stage-name table and its +32…+64 executable pointers**, and distinguish metadata from actual frame production. Stage41E is complete and green; there is no ongoing asynchronous work. The exact Eagle2 MAIN CCM pixel mathematics remain unproven and the phone still saves Photon-rendered photos.