# Exact original X2D II firmware reacquisition and equivalence gate

The recovered original manufacturer URL and hashes below come from the previously saved **Native1A** `hasselblad_native_audit/firmware/firmware_provenance.json` and the 21 October mega handoff. These are historical evidence identifiers, NOT fresh download results.

- Model/version: Hasselblad X2D II 100C, firmware `1.3.16.2`.
- Official CIM: `https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim`
- Package length: `364814336` bytes.
- Expected CIM SHA256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.
- Expected original `system/lib64/libaaa.so` SHA256: `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`.
- Original runtime: Android API 28, ARM64.
- Recorded AWB context size: 920560; config 1502800; passive REAWB handle 1000.

## Recovery

Use `tools/firmware_gate.py` on an authorized network-accessible computer to *download or verify* the package at an external private directory. The script refuses replacing existing files, hashes the exact bytes and removes partial invalid downloads. If the official URL changes, compare official vendor sources and modify the tool deliberately; do NOT bypass pinned checksums.

The preserved Native1A archive contains the original `hasselblad_native_audit/extract_official.py` and `cim_reader.py` which reconstruct system and vendor OTA partitions for **local** inspection, not distribution. Execute those extraction scripts in a private sandbox after official archive verification, verify `libaaa.so` SHA again, then recreate the original ARM64 initialization and seven-frame oracle.

## Revalidation boundaries

1. Every vendor test must disclose the exact original firmware hash, original routine address and input ABI, current test initialisation/configuration, and whether the compared contexts/handles come from the same execution.
2. Comparing a detached capture of an old process is not automatically byte-identical for pointer-bearing context fields; same-execution comparison is preferred.
3. A correct outer return `0` is NOT proof of a new AWB estimate; the vendor may reuse restored confirmed results.
4. Raw phone statistics must be mapped with measured phone calibration, not vendor sensor calibration copied from IMX861.
5. Never check proprietary firmware, extracted `libaaa.so`, calibrations, full DNG/JPEG pixels, private capture sidecars or APKs into the public repository.

Current status: official URL + historical package hashes recovered; **original archive not downloaded here**, `libaaa.so` hash NOT freshly validated, numerical optimizer original comparison NOT executed.