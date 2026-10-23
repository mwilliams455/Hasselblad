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

## Stage40B actual original-firmware CI finding (first run)

The verified dual-source run [39919743223](https://github.com/mwilliams455/Hasselblad/actions/runs/39919743223) found **1,617** regular files in each official firmware: **1,368** byte-identical and **249** changed; zero added or removed files. The original **entire IQ configuration** `hb722_config.json` and its schema `config.fbs` are byte-identical. So are the original `libdcam_pp.so`, `libdcam_pp_base.so`, `libdsp_frwk.so`, `libdcam_adj_product.so`, `libalgo_share.so` and `libadj_base.so`. Original `librcam.so`, `vcam_driver.ko`, `cam_vreg.ko`, `libaaa.so`, `libduml_hal.so`, and the four named encrypted DSP firmware images **changed**. This is **not** evidence of changed photographic colour; neither is it enough to transfer function-level proofs automatically from 1.3.16.2 to 1.3.18.1.

The initial first-run diagnostic reported `false` for some individually named gamma subtrees because those names were **absent from global `iq_table.data[0]`**, not because gamma tuning values changed. The entire IQ file was **exactly byte-identical**. Stage40C improves the subtree evaluator to include **all mode-qualified entries in `iq_table.data`**, including the actual still gamma records, and reports `absent_both` explicitly rather than falsely implying different values.

## Stage40C — original function-body identity, not runtime equivalence

The supplemental `fingerprint_colour_functions40c.py` compares the raw **function-body SHA256 digests** of 27 selected original functions across four relevant changed ELFs (`librcam.so`, `vcam_driver.ko`, `libaaa.so`, `libduml_hal.so`). Original `.gnu_debugdata` symbol tables are interpreted as inert metadata under a 64-MiB cap, AArch64 ELF segments and source files are hash-verified against the already inspected old/new manifests, and only counts/digests are reported. Functions include the previously verified CCM profile preparation, MAIN gamma/LUT parameter readers and driver setters, the AWB primitive and the display sampler (which remains a separate non-MAIN reference). Any unlocatable/ambiguous function is *not* promoted to an identity proof.

Even a byte-identical function body does **not** establish byte-identical link relocations, surrounding callers, runtime tables, CPU build state or the photographic ISP pixel equation. Changed binaries require appropriate source-specific native replay before any firmware-equivalence claim can be extended to 1.3.18.1.

Synthetic Stage40C smoke test:

```sh
python3 hasselblad_native_audit/isp_firmware_stage40/fingerprint_colour_functions40c.py --self-test
```

The updated Stage40 CI computes private function summaries for both exactly pinned releases, compares them only after both are extracted, deletes firmware and private indexes, and uploads **only a sanitized function digest report** alongside the existing dual-file summary. No APK is rebuilt by this investigation.