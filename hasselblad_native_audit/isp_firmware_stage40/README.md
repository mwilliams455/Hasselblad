# Stage40 — 2026-10-22 official X2D II firmware colour-source comparison

**Research only — no Android saved-photo renderer changes.** Target is an exact, hash-pinned, side-by-side byte and profile-structure comparison of **X2D II 100C firmware 1.3.16.2** (the provenance of Stages6–39) against the newly released **1.3.18.1** (22 October 2026). The public release note reports an improvement to the touch display in low light, **not a colour-science change**.

## Identity and provenance

| Version | Official CIM bytes | SHA-256 | Verification |
| --- | ---: | --- | --- |
| 1.3.16.2 | 364,814,336 | `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` | Stage6–39 original-source checksum |
| 1.3.18.1 | 365,283,840 | `c65970cbc1519f876aa3296411f8bb5075995dabc9479bb8abb635945dad6496` | New official CDN response, Stage40A CI `39919059958`, success |

Official downloads are under `https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/<version>/X2DII_100C_v<version_underscored>.cim`. Both packages are inert, private temporary inputs in CI. No firmware file, extracted binary, private tuning table, sensor calibration, or image is committed or published.

## Stage40B new experiment

The workflow `.github/workflows/hb-stage40-colour-asset-delta.yml` downloads **both exact archives** and checks size **and SHA-256 before any parsing**. The `extract_exact40.py` script reuses the trusted original CIM reader, full OTA extent verifier, and regular-file ExtFS extractor, verifies camera product and exact `/system/etc/VERSION`, and never executes original vendor code.

The old and new firmwares are extracted and summarized **sequentially** to minimize temporary disk space. `compare_colour40.py` generates temporary private per-file digest indexes plus hashes of **only selected inert IQ subtrees** (main CCM, main gamma, main 3DLUT, HNCS, WBC, camera/topology). Its final artifact contains only selected source digests, equality flags and aggregate file-change counts, never any proprietary numeric vectors. The manifest and original extraction are deleted before final publication.

A successful byte-identity check on original `librcam.so`, `vcam_driver.ko` and IQ subtrees means **the file-level material underlying earlier audits is unchanged** between releases. It **does not** imply active runtime identity, automatic photographic parity, original CCM pixel semantics, or compatibility of a different future device. When hashes differ, **the earlier version's proofs cannot silently be transferred** to the modified file. All claims remain exact-source scoped.

## Run

Synthetic regression (no firmwares):

```sh
python3 hasselblad_native_audit/isp_firmware_stage40/compare_colour40.py --self-test
```

Original dual-firmware CI is triggered by source changes on `recovery/awb-rebuild-20261021` or `workflow_dispatch` and publishes only `STAGE40_DUAL_ORIGINAL_COLOUR_COMPARISON_SAFE.json` plus a synthetic receipt. Both original archives and all extracted copies remain outside public source, logs and artifacts.

## Persistent limits

Stage36 (`versionCode 27190`) is still the latest signed, user-tested APK. All saved photos remain Photon. The actual X2D II Eagle2 six-coefficient **per-pixel CCM formula**, MAIN gamma hardware sampler, MAIN 3DLUT domain/interpolation and photographic HNCS parity remain unproven. Finding identical files in new firmware neither changes those limits nor justifies a production photo-renderer swap. The recovering next useful target, assuming image-pipeline hashes match, remains original pixel semantics from new evidence (hardware specification or true stage-isolated oracle), not another white-balance diagnostic.