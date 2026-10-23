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

## Stage40D — differentiate function relocation from operand changes

The validated Stage40C original run [39920704466](https://github.com/mwilliams455/Hasselblad/actions/runs/39920704466) found **12** raw-function-body byte matches, **13** changed and **2** unresolved among the 27 selected original functions. All 10 inspected Eagle2 CCM/gamma/LUT/format driver functions and the original `scene_awb_result_recalib_unit` AWB leaf were byte-identical; the 13 changed original `librcam.so` functions kept their exact original sizes while many had different virtual addresses. The vendor's `mm_get_coeff` CCT leaf was byte-identical even though relocated. The unchanged output profile configuration cannot by itself establish which revised functions retain exactly identical arithmetic.

Stage40D extends the **same bounded original function-body** audit with Capstone AArch64 instruction-shape hashes. Each function is completely decoded; the report retains the total instruction count, arithmetic/loads/stores count, mnemonic-sequence digest, and a second syntax digest that **preserves all registers, memory displacements, immediate numerical constants and shift/extension descriptions**, but normalizes the *target address only* of designated PC-relative branches, ADR/ADRP and literal LDR. Internal branches retain their **relative function offset**. No instruction bytes or disassembly are exported.

A matching normalized syntax digest is **not** an execution/semantic parity proof: especially, an external branch may point to a different callee after the update, the external address is deliberately excluded, and the surrounding helper code/runtime may differ. A changed digest also need not mean changed mathematical output. This audit is a new **triage** for deciding which revised native colour arithmetic needs a full original-code rerun against owned synthetic fixtures, before a new version can claim genuine firmware equivalence.

## Stage40E — original new-firmware CCM arithmetic under QEMU (source-only)

The independent `.github/workflows/hb-stage40e-new-ccm-native-replay.yml` workflow extracts **only** the exact-hash official 1.3.18.1 firmware transiently. It compiles a temporary generated copy of the **already reviewed original owned** C probe `ccm_prepare_probe.c`, changing only the three function-address constants from old version to the independently verified new version and discovering the matching original exported load-bias anchor from `.dynsym`. The original pinned owned C source remains unchanged. The probe invokes exact original `mm_get_coeff` and `mm_mx_lerp_gap` under the new firmware's matching Android Bionic runtime in QEMU user mode. A separate portable C implementation and independently computed Python outputs must match every scalar.

Three bounded fixtures: dense signed synthetic, signed16 endpoint stress, and the same exact-hash original global CCM table (whose entire IQ source is byte-identical across versions), each have 9 CCT points × 6 legal Q8 secondary weights × 96 coefficients. The **maximum possible successful receipt** is **162 original-code cases / 15,552 scalar comparisons**. All original vendor tuning values, synthetic input/output files and temporary compiled probes remain in private transient directories; only source/version IDs, sanitized booleans and aggregate counts may be published. A real ISP pixel transform is not exercised, and this is not a photographic HNCS port.

The owned runner is `replay_new_original_ccm40e.py` and its safe synthetic test is `python3 hasselblad_native_audit/isp_firmware_stage40/replay_new_original_ccm40e.py --self-test`. **Passing this test is only a Python fixture test**, not an original runtime result. The original runtime test requires successful hosted CI and must be reported separately.

## Stage 40F — new-firmware native MAIN LUT profile interpolation

The Stage40E native replay proved original 1.3.18.1 MAIN CCM **coefficient preparation** against our portable C/Python references (162 cases / 15,552 signed scalar outputs). Stage40F performs a separate **original code** arithmetic comparison for `mm_get_coeff` and `mm_mx_lerp_vec_mix2`, now at `0x2bace8` and `0x2bbcf0` in exact new `librcam.so` (SHA-256 `3443f4b6a3c6229325102cf763e433e2b36c76d7ab6650c3fcb9e9e2e821004f`).

The new `replay_new_original_lut40f.py` adapts only address constants in the previously vetted, owned `photographic_path/lut_profile_probe.c` to the new original code after checking new ELF symbol identities. It deliberately **omits the original-`rcam_adj_calc_common` dispatch table assertion** because the new firmware's dispatch table address has not yet independently been verified. This is a leaf-arithmetic-only comparison, not proof of the outer IQ dispatcher, ISP hardware or saved-image pipeline.

The probe first runs the original routines on 12 deterministic seven-word-per-profile asymmetric synthetic inputs and verifies all 168 output lanes against independent Python. It then passes the exact, privately parsed X2D II camera `main_3dlut` profiles (8 × 6,144 words) into the original routine for ten CCT/gamut cases and compares every resulting 16-bit lane against independent Python (10 × 6,144 × 2 = **122,880 original camera profile lanes**). All inputs and outputs remain in a temporary directory. The retained receipt contains only hashes, counts, case names and pass/fail; no vendor table, source photograph, prepared LUT, or vendor instruction bytes.

Official new firmware 1.3.18.1 must match whole-archive SHA-256 `c65970cbc1519f876aa3296411f8bb5075995dabc9479bb8abb635945dad6496` and the old/new **identical** original IQ SHA-256 `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286`. The Android API28 QEMU/NDK source checks are restricted to the exact original vendor `librcam` functions, with no camera control APIs. The workflow `.github/workflows/hb-stage40f-new-lut-native-replay.yml` fails closed for changes and deletes vendor bytes before publishing any artifact. Neither `main` nor the Photon app is modified.

**Important:** `MAIN_3DLUT` profile *preparation* (mixing selected profile words) is not the original Eagle2 MAIN 3D LUT *pixel sampler*. Original packed cube order, input domain, trilinear versus tetrahedral interpolation, fixed-point rounding and their relationship to the original six-coefficient MAIN CCM pixel transform remain unproved. No Hasselblad/HNCS JPEG output is authorized by this stage.