# Stage41H: declared SBPC route, runtime descriptors, and padded pixel export

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Implementation commit: `9dbfdc56c7664b6f7eeaa4176c51e41a21497ba8`.
Predecessor: `1c2a4d639462540032e908e99a9ccd50b0d83677` (Stage41G).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

## Result

The original stream configuration explicitly connects `liveview_after_sbpc` to output port 0 of `liveview_sbpc`. Its input port 1 is `liveview_sout1`, declared on `EAGLE2_PORT_SOUT1`. This closes the **configuration link**, independently of the rejected camera-service table-adjacency argument in Stage41F. It does not prove that a running camera selected this configuration or bind a camera-service enum to a live buffer.

The linked ordinary preview segment declares `SUB_DEMOSAIC`, `SUB_CC`, `SUB_GAMMA`, and `SUB_YCC`. It does not list `MAIN_CCM`, `MAIN_HNCS`, or `MAIN_3DLUT`. Module membership is not execution order. This source evidence does not establish an isolated MAIN CCM pixel pair; the SBPC path should not be used as that reference.

Two original-code offline tests passed locally. The configured-size NV12 test exports 3,225,600 bytes exactly, including 345,600 bytes of padding. Treating those bytes as tightly packed 1600×1200 NV12 would misinterpret row and plane positions. A separate descriptor test demonstrates that the original forwarding helper overwrites output format and dimensions from its input.

No camera pixels were obtained. There is no production renderer change or APK.

## Original configuration evidence

Hash-pinned original firmware 1.3.16.2, archive SHA-256:
`9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.

The audit reads only selected graph/format metadata from `imx861bqr_hb722.sp`, `imx861bqr_hb722.conf`, and the topology declaration in `iq/hb722_config.json`. It also checks bounded functions from original AIO and `libdcam_frwk.so`. Full source hashes are in the JSON receipt. No tuning coefficients, calibration, ELF bytes, or full disassembly are published.

All three declared modes (`still_4x3_16bit`, `still_4x3_14bit`, `still_4x3_14bit_hs`) use `comm_still-template-01` and the same ordinary repeating topology, `TPLG_IMX861BQR_LIVEVIEW_12K_11BIT_60FPS`.

| Stream | Declared connection | Meaning established here |
|---|---|---|
| `liveview_rout0` | ROUT0 → `shadow_liveview_4` | RAW parent branch |
| `liveview_raw_shadow` | `shadow_liveview_4` → SBPC input 0 | RAW-named carrier; actual runtime layout still needed |
| `liveview_sout1` | SOUT1 → SBPC input 1 | Declared NV12 image input |
| `liveview_after_sbpc` | SBPC output 0 → `gdc_calc_liveview` | Named output is explicitly linked in the stream template |
| `liveview_after_gdc_calc` | GDC calculation → `dewarp_liveview` | Downstream geometry path |
| `liveview_after_gdc` | Dewarp → `mctf` | Downstream temporal-processing path |
| `liveview_sout2` / `liveview_mee` | SOUT2 → `shadow_mee` → MEE | Separate MEE branch, not the SOUT1 SBPC image input |

The ordinary repeating topology's selected segment is `common_recording_still_10-sub_back-data_mux0-raw_bin-still`. The selected module-membership checks above belong to this segment only. They do not establish all camera paths, runtime bypass state, hardware ordering, or saved-photo processing.

## Original callback and forwarding contract

Stage41G established the same YUV carrier at SBPC's diagnostic before/after call sites. Stage41H adds:

- AIO `_liveview_sbpc_enqueue_input_frame` calls `normal_liveview_sbpc_proc` at `0x360ec`.
- On its success route, `0x36128` reloads input bundle slot 1; `0x3612c` passes the output-pointer slot at bundle `+0xd8`; `0x36130` calls `cam_stream_filter_eng_process_bypass_v2`.
- The original helper is in `libdcam_frwk.so`, start `0x208d90`, size 2,544 bytes. In the tested common-frame path it retains the input, saves an input-parent pointer at output `+0x390`, shares the memory handle at `+0x20`, and copies format (`+0x28`), dimensions (`+0x38/+0x3c`), frame ID and related descriptor fields. It saves the previous output handle at `+0x3a0`.
- The tested helper leaves the output plane-descriptor area unchanged. The replay prepares that layout separately; it does not test the complete output allocator, queue lifecycle, shadow filter, SBPC callback, or DSP.
- The enqueue callback copies input/output pointer arrays into a result queue; dequeue returns the result descriptor. These arrays and pointers are not image bytes.

The original config declares `RAW16_OPAQUE` on the ROUT0 parent but NV12 on `liveview_raw_shadow`, with a flag preventing inheritance of parent stream parameters. This is a reason to inspect the **runtime descriptor**, not proof that the RAW shadow is actually NV12 or that the camera has a format bug. The RAW replay uses the generic forwarding helper only; it does not execute that shadow filter.

## Synthetic original-code validation

The new replay reuses Stage41G's pinned original pixel exporter and original HAL mapping dispatcher, and additionally executes the original framework forwarding function in ARM64 emulation. Memory backing, mutexes, cache operations and stdio are simulated; unknown imports fail. No physical camera is accessed.

| Test | Verified result |
|---|---|
| Configured SOUT1 NV12, 1600×1200, alignment 256 | Original forwarding retains the input and shares its handle; original exporter returns all 3,225,600 synthetic bytes unchanged |
| RAW16 input with an output initially labelled NV12 | Original format resolver yields RAW enum 10001; original forwarder replaces format/dimensions, preserves parent reference and shared handle; no RAW image pixels are exported |

For the configured NV12 replay:

| Plane | Offset | Stride | Rows | Visible bytes per row |
|---|---:|---:|---:|---:|
| Y | 0 | 1792 | 1200 | 1600 |
| UV | 2150400 | 1792 | 600 | 1600 |

The visible NV12 payload is 2,880,000 bytes; padding adds 345,600 bytes. These numbers describe the tested default geometry, **not every live frame**: the original stream permits variable resolution. The safe capture/import contract must carry actual format, dimensions, offsets, strides and byte lengths. A stream label or nominal file size alone is insufficient.

Synthetic exported SHA-256: `3fa439c31aa5c3b2f9184bbebf707acb1f851ed6b488af9e456fc66e04fdc0e3`.

## Remaining boundary

Work Mode can inspect and process supplied pixel buffers. These checks establish an original reader and a declared stream route, not acquisition of a live camera buffer. Real acquisition still requires a valid running-camera buffer or a captured dump with its runtime layout and provenance. Stage41G's diagnostic wrappers can draw markers; a pristine reference must account for that behavior.

The remaining MAIN CCM question belongs to a verified main/still path. This preview graph and its synthetic exports cannot supply that equation or establish an HNCS renderer for Photon.

## Reproduction and receipts

Scripts: `hasselblad_native_audit/isp_liveview_stage41h/inspect_stream_contract41h.py` and `replay_stream_contract41h.py`.

Workflow: `.github/workflows/hb-stage41h-stream-contract.yml`.
Run: https://github.com/mwilliams455/Hasselblad/actions/runs/39942175299

The workflow checks the production main hash and no Photon diff, downloads and verifies the original archive, runs the bounded audit and two synthetic cases, then removes the firmware before publishing only the two safe JSON receipts. CI completed successfully at the implementation commit, including both original-code replay cases and all three configured modes. Both downloaded JSON receipts were independently compared with the local outputs and match exactly.

Artifact: `Hasselblad-Stage41H-Original-Stream-Contract-Safe`, ID `12496646895`.
ZIP SHA-256: `a7147abb0afc063eb6695d44c8a2ef335a447b01ac23d2496dcb5e51b08dfb48`.
Production main was rechecked after CI and remains at the pinned hash above.
