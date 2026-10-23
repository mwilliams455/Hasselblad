# Stage 41 — X Unleashed Eagle2 live-view bridge to original X2D II firmware

**Research only, 23 October 2026.** Target: the original, hash-pinned X2D II 100C 1.3.16.2 firmware, whose extracted `kheaders.ko` matches the camera-specific kernel source identity published by `scanfsec/hasselblad-x-unleashed`. This checkpoint does **not** change Photon, upload user photographs, install anything onto an X2D II or derive a MAIN CCM pixel equation.

## External source provenance

Reviewed independent public project [scanfsec/hasselblad-x-unleashed](https://github.com/scanfsec/hasselblad-x-unleashed) at commit [`dd798e5e51a8bebc333ce7026c7fa700a0feb96c`](https://github.com/scanfsec/hasselblad-x-unleashed/commit/dd798e5e51a8bebc333ce7026c7fa700a0feb96c). Original source snippets are **not** committed here.

| Published source | Git blob SHA1 | Evidentiary role |
| --- | --- | --- |
| `hasselblad_monitor/uvc-gadget/eagle2_v4l2_abi.h` | `91b13ce7a02aeab247305be91aac25c492d4de6c` | Author's vendor V4L2 buffer ABI adapter; nonstandard 96-byte `v4l2_buffer`, 344-byte format request |
| `hasselblad_monitor/uvc-gadget/liveview_bridge.c` | `1f3a63664ca140199e5cdeb84de1ed09a7b0f1f0` | Existing CPU-accessible frame pointer -> writer-managed shared memory |
| `hasselblad_monitor/uvc-gadget/liveview_frame.h` | `91b9a8996194d461512418b89bf5ed29f6b800ac` | Bounds-checked NV12 sampling/downsampling -> 640 × 480 YUYV, 8-bit output |
| `hasselblad_monitor/uvc-gadget/test_liveview.c` | `e81178c4b5d88a51b2d0dd3d114d7c3996c94c13` | Published synthetic frame bounds, NV12 stride, frame counter and consistent-copy checks |
| `hasselblad_monitor/uvc-gadget/test_eagle2_abi.c` | `6b4b03aae24f40f887ff76f403289912e7a858fa` | Published synthetic mock-ioctl ABI tests |

These are tests **of the independent project source**, not executions of the original Hasselblad camera code. The camera-side UVC gadget subtree has a GPL-2.0 license file; do not copy its implementation into an MIT-only Photon module. The upstream source includes no published code establishing precisely where or how the `liveview_after_sbpc` publisher hook is installed in the original camera. Its [kernel-runtime research notes](https://github.com/scanfsec/hasselblad-x-unleashed/blob/main/hasselblad_monitor/kernel_runtime/README.txt) claim a camera-side post-SBPC source, but that description alone is not proof of pixels immediately before or after MAIN CCM.

**No on-camera installation is attempted.** The project's own kernel-runtime notes record risks in USB reconnection and experimental kernel hooks. Run only the publicly published **host synthetic tests**, pinned by Git object ID, inside CI with no device.

## Exact original-firmware work

`inspect_original_liveview41.py` checks a known source identity: original full CIM SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`, `system/etc/VERSION=1.3.16.2` and original `system/lib/modules/kheaders.ko` SHA-256 `b7cbbd598da206e828b96d8103650f790ef7508bd0e1835ab3485c04aad9621b`. Six previously validated original camera ELFs are checked against exact hashes before analysis.

The bounded read-only scan enumerates native ELFs in five original system/vendor directories, searches for **literal** `liveview_after_sbpc`, `sbpc`, `liveview`, `v4l2`, and `nv12`, and looks for matching defined function symbol names (including original `.gnu_debugdata` when available). It retains only path names, SHA256 identities, boolean string-presence flags and bounded public ELF symbol names. It does not inspect or export image pixels, private tuning arrays, vendor instruction bytes or runtime addresses. Missing a literal **does not mean a private hook does not exist**: an analyst-assigned nickname, stripped symbols or indirect callbacks can evade the scan. Finding NV12 or V4L2 does not show the function is used in the MAIN CCM processing chain.

Run the local host-only selftest:

```sh
python3 hasselblad_native_audit/isp_liveview_stage41/inspect_original_liveview41.py --self-test
```

For exact firmware CI, see `.github/workflows/hb-stage41-x-unleashed-liveview.yml`. It fails closed on changed inputs, deletes the original official camera firmware and third-party source files, and uploads **only sanitized JSON**.

## What would count as a genuine CCM pixel oracle?

A verified original-camera same-frame **pair of RGB buffers** immediately before and immediately after the `MAIN_CCM` hardware component, with known bit depth, channel order, numerical normalization, six signed active coefficients, group selector, gamma and LUT controls/bypass, frame/mode/CCT binding, and an independent numerical comparison (neutral, channel basis, mixed colours, clipping). The present published external hook gives a postprocessed NV12 live view, downsampled and quantized to YUYV, so it **cannot be relabelled as a direct CCM oracle**.

Stage40E/F verified the new original 1.3.18.1 *parameter preparation* functions, not the original per-pixel CCM or LUT arithmetic. Stage36 APK `27190` remains the phone-tested capture baseline with Photon photo rendering. Production `main` is untouched.

## Stage41B — from original literal to native function provenance

Stage41A original-firmware CI [39929388253](https://github.com/mwilliams455/Hasselblad/actions/runs/39929388253) **passed**. It found the literal `liveview_after_sbpc` in the original `system/bin/camera-service`, with **733** native ELF files examined and **83** related liveview/SBPC/V4L2/NV12 matches. The identical `kheaders.ko` proves a common original kernel-header identity with the X Unleashed test device. The two exact-Git-blob upstream C synthetic test programs also **passed**. This is a real original-firmware named lead, not yet a proven pipeline tap.

`inspect_original_liveview_xrefs41b.py` now hash-pins the **exact original** `camera-service` ELF at SHA256 `51b9e02f8bfebf388be8dfa163c8e512bee19aeb8ae37a6712727ccc6f26a52d` and `system/lib64/camera/plugins/libdcam_plugins_AIO.so` at SHA256 `1924f9aca6d5f4f92ff482f6a864579d303a890fcef3427053f35d9b00bd4135`. It classifies the original string's ELF section, bounded AArch64 `ADR` / `ADRP + ADD` code references where present, and original named `LiveViewSBPCManager`/DSP handler/processing callbacks and their direct callees. The classification explicitly distinguishes original **symbol metadata**, a **string referenced by code**, and a **proven ISP output buffer** (which remains absent). This is read-only disassembly over exact pinned ELF functions, never original vendor code execution, capture, firmware patching or arbitrary memory reading. The output excludes original byte sequences and any personal data.

**Limitations:** ELF PC-relative reference detection is deliberately bounded and incomplete; a zero result does not prove no runtime references. A matching static function/call does not prove any frame's colour domain, ISP stage timing, or the relationship between SBPC and MAIN CCM. An actual same-frame before/after CCM measurement requires an authorised original hardware oracle, not a Qt symbol name or a postprocessed NV12 sample.