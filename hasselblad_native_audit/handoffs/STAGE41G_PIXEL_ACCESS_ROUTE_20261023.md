# Stage 41G — original pixel exporter verified; live camera acquisition still required

23 October 2026 (UK).

We found an original SBPC frame-processing route with diagnostic YUV dumps on
both sides of its processing call, and executed the underlying original ARM64
pixel exporter successfully against synthetic NV12 memory. This establishes an
export mechanism and a tested buffer layout. It does not mean that live camera
pixels or isolated MAIN CCM input/output samples have been acquired.

## Reproducible checkpoint

- Branch: `recovery/awb-rebuild-20261021`.
- Implementation commit: `249466c14f028ddcd4b787f8eeb7f896acae691b`.
- [CI run 39938101861](https://github.com/mwilliams455/Hasselblad/actions/runs/39938101861): completed, success.
- Artifact: `Hasselblad-Stage41G-Original-Pixel-Access-Safe`, ID `12494338540`.
- Original firmware: **1.3.16.2**, full CIM SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.
- Production `main`: `929f523aa02ae5b224be39b9c36cce5975691a10`; unchanged. Phone photographs still use Photon colour. No APK change.

Audit source is in `hasselblad_native_audit/isp_liveview_stage41g/`:
`inspect_pixel_route41g.py` and `pixel_export41g.py`. The workflow downloads and
verifies the exact official firmware, extracts it as data, runs the bounded
source audit and offline emulation, deletes firmware, and publishes only safe
metadata and synthetic-test receipts. No original instruction bytes, raw images,
calibration tables or proprietary disassembly are published.

## The new original frame path

Within the pinned `libdcam_plugins_AIO.so`, the function
`_liveview_sbpc_enqueue_input_frame` contains:

| Original call site | Callee | Established relationship |
|---|---|---|
| `0x35b88` | `_dump_yuv_with_bad_pixel` | Conditional diagnostic dump before the processing call. |
| `0x35b9c` | `_dump_raw_with_bad_pixel` | Separate RAW diagnostic copy/dump path before processing. |
| `0x360ec` | `normal_liveview_sbpc_proc` | Original SBPC processing wrapper. |
| `0x36164` | `_draw_bad_pixel_in_liveview` | Optional debug drawing directly on the live-view frame. |
| `0x36194` | `_dump_yuv_with_bad_pixel` | Conditional diagnostic dump after processing. |

The callback loads its YUV frame carrier from offset `+8` in its frame bundle.
Both YUV dump calls receive that carrier. The processing parameter structure
also receives the RAW/YUV frame pointers at offsets `+0x78` and `+0x80`.
Control-flow analysis finds a path from the first dump through processing to
the second dump without clobbering the frame carrier. This is static evidence,
assuming called functions return; runtime activation of those branches is not
proved.

The dump helpers allocate a new frame, copy the incoming frame, map its memory,
and can call `_draw_normal` before exporting it. They therefore cannot simply
be enabled and treated as pristine pixel references. The separate
`_draw_bad_pixel_in_liveview` path can alter the live preview itself. No such
path was enabled on any device.

The export chain is now resolved through actual original calls:

`_dump_yuv_with_bad_pixel` / `_dump_raw_with_bad_pixel`
→ `cam_dump_frame` (`libdcam_resource_package_util.so`)
→ `dump_frame_to_file` (`libdcam_base.so`)
→ `duss_hal_mem_map` (`libduml_hal.so`)
→ mapped CPU address → `_fwrite_data` → `fwrite`.

For an unaltered capture, the generic exporter is the relevant component; the
bad-pixel diagnostic wrappers and drawing must be avoided. A capture must occur
while the original frame and its backing allocation remain valid.

## Original code execution against synthetic image memory

Unicorn executed the original, hash-verified ARM64 implementations of
`duss_pixel_format_from_str`, `frame_buffer_plane_info_generate`,
`dump_frame_to_file`, `_fwrite_data`, and the HAL mapping dispatcher. No image
read/write algorithm was substituted for those functions. Their imported
platform memory backend, cache operations, logging and stdio were explicitly
simulated. All output was captured in an in-memory sink; no camera, device
driver, DSP or host filesystem exporter was invoked.

The original format resolver identifies `DUSS_PIXFMT_YUV8_SP420_YUV` as enum
**2**. This is the format tested here; it is **not proof that a live SBPC frame
uses enum 2**, nor proof of X Unleashed's exact source attachment.

| Test | Source allocation | Exported bytes | Original return | Result |
|---|---:|---:|---:|---|
| 16×8, tight NV12 | 192 | 192 | 0 | Exact source match |
| 640×480, tight NV12 | 460,800 | 460,800 | 0 | Exact source match |
| 18×10, 64-byte row stride | 960 | 960 | 0 | Exact match including row padding |
| Partial writes, seven bytes per write | 192 | 192 | 0 | Original retry loop completes correctly |
| Memory-map failure | 192 | 0 | −1 | No pixel output |
| File-open failure | 192 | 0 | −1001 | No pixel output |

All six tests leave the synthetic input pixels unchanged. Local and independent
CI JSON results match. The original exporter preserves source row padding; a
viewer must retain stride and plane offsets rather than assuming a tightly
packed width × height × 1.5 file. In the successful tests the original code
requested a cache synchronization for each plane and then unmapped memory;
real hardware cache coherency is not tested by simulated cache operations.

## Tested frame descriptor fields

These are offsets for the pinned original firmware and tested format, not a
portable declaration for all firmware versions or all pixel formats.

| Offset | Meaning supported by source and/or original execution |
|---|---|
| `+0x20` | Memory handle passed to the HAL mapper |
| `+0x28` | Pixel-format enum |
| `+0x38`, `+0x3c` | Width, height |
| `+0x40` | Start of plane descriptors, with 28-byte spacing |
| Plane `+0`, `+4`, `+12` | Row stride, byte offset, plane height |
| Frame `+0xb0` | Plane count |

The HAL mapper obtains a backend mapping function through its device operations
table. Its original dispatch was executed in the test, but that backend was
supplied by the harness with synthetic RAM. This boundary is precisely why the
offline success does not imply access to physical camera memory.

## Separating the MEE and SBPC findings

The initially selected `_calculate_out_result_frame_buffer_info` helper really
does map memory. However, its four result buffers in `_process_on_buffer` are
subsequently copied with maximum accepted lengths of 200, 200, 400 and 400
bytes. They are not full image frames. The genuine SBPC callback above was
found by tracing actual pixel mapping/dump calls in that same pinned plugin;
the two paths remain distinct.

`normal_liveview_sbpc_proc` calls the original `proc_liveview_sbpc`. The latter
uses physical/virtual/shared-memory address helpers and an indirect dispatch.
This work does not execute that processing backend or replace it with an
invented software renderer.

## What remains to obtain actual pixels

1. Supply an actual original frame at the identified callback through a
   nondestructive, owner-authorized camera-side capture mechanism, or obtain
   original captured buffer dumps plus their metadata. Work Mode has no
   physical X2D II connection in this session. Firmware files contain code,
   not a running camera's frame buffers.
2. Record firmware/source hashes, frame identity/timestamp, runtime pixel format,
   dimensions, plane offsets and strides, allocation size, processing/bypass
   state, and whether diagnostic markers were applied. Capture before any
   debug drawing and before buffer reuse; preserve the original image path.
3. Independently establish the stream's relationship to `MAIN_CCM`, gamma and
   the 3D LUT. A pair before/after **SBPC** is not automatically a pair
   immediately before/after **MAIN CCM**, and NV12 is not automatically linear
   RGB.

The camera-service `liveview_after_sbpc` name table, X Unleashed's borrowed NV12
publisher and this AIO source graph have not been joined by an original runtime
buffer trace. Do not claim that link, full HNCS, authentic colour rendering,
actual camera-pixel acquisition or an isolated CCM oracle from Stage 41G.

The useful advance is concrete: the original generic pixel reader is now
exercised, its NV12 memory contract is tested, and an original SBPC frame path
reaches it through the camera's existing dump machinery. No task remains
running after this checkpoint.
