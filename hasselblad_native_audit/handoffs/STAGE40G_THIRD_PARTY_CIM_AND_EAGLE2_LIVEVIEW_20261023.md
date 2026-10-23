# HasselbladPhoton — Stage 40G: independent CIM extractor and original X2D II live-view interface research

**Date:** 2026-10-23 (UK)  
**Scope:** Source comparison only, no vendor firmware copied, no device modified, no Photon saved-photo renderer change  
**Working branch:** `recovery/awb-rebuild-20261021`  
**Production baseline:** `main` remains separately protected. Latest verified phone APK remains Stage36 `27190` (Photon photo colour).

## User-provided third-party sources

1. [YuHaoyua/hasselblad-cim-firmware-extractor](https://github.com/YuHaoyua/hasselblad-cim-firmware-extractor), examined at public `main` commit `768664267cb44621c3c12595ee9cc538020b1b94`. README blob `fc010bc137f33b117ed20f6f5fd48d6c33b3e3cf`; extraction script blob `35469a59ee6357de7bfe90dbbafe03d248e3b7e9`. Repository declares MIT.
2. [scanfsec/hasselblad-x-unleashed](https://github.com/scanfsec/hasselblad-x-unleashed), examined at public `main` commit `dd798e5e51a8bebc333ce7026c7fa700a0feb96c`. Principal references: [English README](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/README.en.md), [Eagle2 V4L2 ABI](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/uvc-gadget/eagle2_v4l2_abi.h) blob `91b13ce7a02aeab247305be91aac25c492d4de6c`, [frame publisher](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/uvc-gadget/liveview_bridge.c) blob `1f3a63664ca140199e5cdeb84de1ed09a7b0f1f0`, [frame conversion](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/uvc-gadget/liveview_frame.h) blob `91b9a8996194d461512418b89bf5ed29f6b800ac`, [camera kernel guard README](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/kernel_runtime/README.txt) blob `92e077695f40b64fd6a1218449a1924945eb4fcb`.

### What is already decrypted in *our* research

- `hasselblad_native_audit/cim_reader.py` in our recovery branch already contains the same AES-128-CBC key value and 4,096-byte chunk-reset operation as the independent extractor. The first-party research script uses known plaintext to determine the package IV. The newly identified extractor instead describes an independent timestamp-derived IV and an MD5-plus-salt component integrity check. **Do not copy the decryption key or component contents into source reports.**
- Our `extract_official.py` has already successfully extracted exact-hash X2D II 100C 1.3.16.2 and, by Stage40, 1.3.18.1, including the Android ARM system libraries, main IQ tuning and vendor partition, in ephemeral CI. Original full CIM hashes are independently pinned. The outer CIM encryption is **not** the remaining CCM mathematical obstacle.
- The independent extractor is useful as a secondary verification route. Its source includes a no-table-match fallback and logs `HASH MISMATCH` without always refusing extraction; therefore treat its outputs as **untrusted until full exact-hash and per-component validation**. Its README description of MD5 verification alone is not grounds for overriding the existing pinned extractor.

### Separate *inner* encrypted DSP and hardware block

- Stage main-colour dispatch inspection traced a real `libdcam_pp.so` RAW-to-RGB host route to the DSP call `cam_libpp_function_entry` through Linux ICC transport. Packaged `ss_dsp0.fw`, `ss_dsp1.fw`, `ss_dsp2.fw` and `ask_dsp.img` are **separately encrypted IMaH v2 / TBIE** containers. Neither provided third-party repository discloses a validated decryption or original stage-local colour pixel oracle for these images.
- The original Eagle2 **MAIN CCM** is a hardware register-programmed component. The descriptor/register copy proof for `lmtx_fw` (16×6 signed entries) still does **not** specify channel mapping, fractional-bit Q scale, clipping or pixel rounding. The CCM may operate in the camera hardware even if the separate `raw2rgb` DSP payload is decrypted. Do not conflate the two processing units.

### New X Unleashed evidence of accessible camera frames

- The modified camera's `kheaders.ko` SHA256 in `kernel_runtime/README.txt` is `b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b`, **identical** to the exact kernel-header module hash in our X2D II 1.3.16.2 Stage37 / older MAIN LUT audit. This is strong *firmware-generation matching evidence*; it is not proof that a specific runtime buffer is immediately before/after MAIN CCM.
- `eagle2_v4l2_abi.h` documents a vendor `v4l2_buffer` size of **96 bytes** instead of standard 64-bit host size **88**, due to an additional eight-byte timestamp at offset 40. The code adjusts `VIDIOC_QUERYBUF`, `QBUF`, `DQBUF` ioctl request sizes and the `G_FMT`/`S_FMT` format-struct size **344**. A separate host-side test `test_eagle2_abi.c` asserts the request numbers and field offsets. These are the authors' claims and source tests, **not a newly executed original X2D II kernel audit by us**.
- `liveview_bridge.c` takes an already CPU-accessible **NV12 YUV frame** from an original consumer (caller maintains ownership), receives width/height/stride/UV offset/frame ID, bounds-checks and publishes **640×480 YUYV 8-bit** through shared memory with a sequence protocol. It explicitly does not acquire the camera buffer, hold ownership, or write camera image pixels. The camera-side `kernel_runtime/README.txt` describes the source as `liveview_after_sbpc`. This shows a credible **postprocessing/live-view output reference** avenue, not a proven RAW/linear RGB or isolated CCM tap. Downsampling, YUV conversion, output quantization and the undocumented point within processing prevent substituting this for bit-exact CCM maths.
- X Unleashed documents native runtime experimentation on the camera (including UVC/USB issues and timed factory restoration), not an ordinary phone Camera2 mechanism. Its English README describes direct video recording as **in progress**, even while mentioning in-camera MP4 production. It says some exploit/deployment methods are withheld. **Do not attempt unattended camera patching, root injection, kernel modules or ISP register writes.**
- The camera-side UVC gadget subtree includes a GPL-2.0 license file; the repository root does not advertise a single explicit license. Do not copy camera-side source into the Photon APK without component-by-component licensing review. Independently reimplement compatibility adapters only after validated technical need.

## Priority and limits

| Avenue | New relevance | Does it solve the missing CCM equation? |
|---|---|---|
| Second CIM extractor | Independent decryption/integrity verification for current and historic packages | **No** — same outer layer already open |
| X Unleashed camera-specific V4L2 ABI | New original-camera frame transport/interface evidence | **No** — not MAIN CCM pixel semantics |
| X Unleashed NV12 live-view bridge | Possible full-pipeline *output* evidence for visual/colour comparisons, with hardware owner's approval | **No** — postprocessing, lossy 8-bit 640×480 |
| Original hardware tap *before and after MAIN CCM*, under locked gamma/LUT/settings | If available, could finally discriminate six-coefficient equations, fixed point, channel order | **Yes, if actually isolated and numerically verified** |
| Decrypting separate encrypted DSP images | Could reveal raw2rgb/DSP processing logic if done lawfully with a valid original-code oracle | **Not necessarily** — MAIN CCM is a separate hardware block |

**Recommended next path:** Keep original firmware-equivalent colour as priority. Use the V4L2 and live-view research to design a **non-destructive, read-only, hardware-owner-approved** evidence request/experiment. Required evidence: original frame identity, location before/after exact MAIN CCM block, 12/14/16-bit RGB format, input/output range, actual six coefficients/Q scale, gamma and LUT locked/bypassed, and neutral/primaries/mixed/edge fixture pairs. Only if that cannot be obtained should the 640×480 postprocessed YUV stream be used as a secondary *photographic look* comparator (not hardware equivalence). No new Android renderer, APK, or production merge follows from this source comparison alone.
