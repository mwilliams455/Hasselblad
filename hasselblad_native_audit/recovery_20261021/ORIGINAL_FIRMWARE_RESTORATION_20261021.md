# Hasselblad Photon — verified firmware restoration (2026-10-21)

## Original input / extraction

- User-supplied: `X2DII_100C_v1_3_16_2.cim` (Hasselblad X2D II 100C firmware 1.3.16.2).
- Original input SHA-256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` — **freshly verified**.
- Decrypted OTA SHA-256: `7ccd5df4dab8d098d9895973fb62bcedcaa379f75fb044408a8263ce2d1f9a57` — **freshly verified** against Native1A manifest.
- Reconstructed system image SHA-256: `24aba59a96dfb93485fbf7ab899b3dc6522e203aa39cb810745a72b0115e8c21` — **freshly verified** against Native1A manifest.
- Extracted `etc/VERSION` contains `1.3.16.2`.
- Original read-only CIM reader and OTA transfer reconstruction routines came from the preserved Native1A audit source. Because the historical Python ext4 reader dependency is unavailable in this environment, read-only file extraction used `libext2fs`.

## Exact AWB input files recovered — kept PRIVATE, NOT published

| Original filesystem path | Bytes | SHA-256 |
| --- | ---: | --- |
| `system/lib64/libaaa.so` | 7,423,736 | `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba` |
| `system/etc/aaa/awb_imx861.bin` | 66,728 | `7fa13044a6c5453b67e4ae11bf8d07828de8e1c02aa915494fe5dad20930d435` |
| `system/etc/aaa/awb/awb_imx861.json` | 376,818 | `df1b47d09ba35062ec61a9c9d9f9a9888b718432890b6453e494f0e5d9e43fea` |
| `system/etc/aaa/awb_config.fbs` | 60,371 | `84ff35c3cf2010b81d29d945ef81a5b87a4d3979b86f13dc814a54812813746e` |

All four match the original extraction manifest exactly.

Nine direct `DT_NEEDED` libraries were also extracted and checked against the original manifest: `libduml_util.so`, `libduml_osal.so`, `libdcam_base.so`, `libflow_trace.so`, `libperfetto_c.so`, `libc++.so`, `libc.so`, `libm.so`, `libdl.so`.

## Fresh original ARM64 static evidence

- `libaaa.so` is an ELF64 AArch64 shared object for Android 28.
- **28/28 exported functions** among the 39 historical AWB stage entries match exact function name, virtual address, and size in the actual original `.dynsym`.
- **11/11 historical internal-stage ranges** fall inside original `.text` and contain nonempty instructions; names are NOT exported, so this is a weaker verification of the historical internal mapping, not independent symbol identity.
- At `0x4a39a0`, the original 56-byte `scene_awb_result_recalib_unit` disassembles into two unsigned 32-bit Q12 recalibrations of the form `(input << 12) / calibration` with integer truncation (shift is 32-bit and may wrap).
- Original instruction-level behavior on zero calibration: return **89**, without modifying gains. Valid division path returns **0**. These return codes are those of the vendor routine and not necessarily owned-adapter errors.

## Evidence still missing (do not claim)

- An original Android 28/AArch64 loader/execution harness or equivalent ARM64 emulator with correct dependencies and persistent state.
- Same-execution original-vs-owned seven-frame AWB state equivalence.
- Actual original optimizer / history / atmosphere / post-controller numerical recomparison against reconstruction.
- An APK integrating a freshly proven complete Hasselblad AWB pipeline.

## Safe publication boundary

Commit only documentation, exact hashes, owned test harnesses, and verification summaries to GitHub `recovery/awb-rebuild-20261021`. The original `.cim`, reconstructed `.img`, `libaaa.so`, companion configuration/calibration and other vendor dependencies remain in private user-provided file storage.