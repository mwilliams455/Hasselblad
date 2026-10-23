# HASSELBLAD PHOTON — STAGE 36 → STAGE 37 COMPREHENSIVE HANDOFF

**Checkpoint date:** 23 October 2026 (UK)  
**Project:** Android PhotonCamera-based port/reconstruction of authentic Hasselblad X2D II 100C image processing and, later, useful autofocus/subject functions  
**Research repository:** https://github.com/mwilliams455/Hasselblad  
**Working branch:** `recovery/awb-rebuild-20261021`  
**Last verified work commit before this handoff:** `dda5d250a29f2716acba8fdf878b0b990f267cba`  
**Production `main`:** `929f523aa02ae5b224be39b9c36cce5975691a10`, **UNCHANGED**  
**Current signed, phone-tested APK:** **Stage 36, versionCode 27190**, versionName `0.1-hb-dual36`  
**Last successful build:** https://github.com/mwilliams455/Hasselblad/actions/runs/39903851434  
**New Stage 36 real-device user outcome:** `PASS_BOUND_REAL_DNG_DUAL_NEUTRAL_LINEAR_TILE`  
**Immediate next work:** **Stage 37 — original-firmware-equivalent Eagle2 MAIN CCM *pixel* arithmetic**, followed by original MAIN gamma and LUT *pixel* semantics. **Do not start another neutral-metadata discovery cycle.**

> **Start-of-next-chat directive:** Resume from this checkpoint, not from the beginning. Stages 6–36 have been researched, implemented and/or validated to the extents stated below. The Android real-RAW diagnostic chain is now demonstrated end-to-end and the original-vs-Photon-neutral difference is quantified on genuine camera data. This still does **not** mean that Hasselblad HNCS colour rendering has been ported: saved JPEGs and normal photo colour remain **Photon**. Prioritise original firmware evidence for the missing MAIN CCM, gamma and LUT pixel computations, without speculative substitutes.

---

## 1. Objective and invariant rules

The goal is **firmware-equivalent Hasselblad colour science**, not a generic Hasselblad-style filter or an unexplained LUT. Original X2D II 100C firmware 1.3.16.2 is the primary evidence; different Hasselblad generations and external Phocus research are independent hypotheses or corroboration, not interchangeable implementations. The native Android app should ultimately render consistent photographic output on the target phone and, where hardware supports it, remain portable beyond the Xiaomi 15 Ultra. The present route is approximately **12 MP first**, with higher-resolution streams later after the core pipeline is reliable. No HDR/stacking should be silently introduced into the default rendering path merely because the X2D II product has HDR-related features.

Longer-term intentions: where evidence and Android capabilities permit, port useful Hasselblad autofocus/face/subject tracking behavior to Photon. Once dependable, these engineering improvements may inform the user's Leica M9/Monochrome apps. **Do not divert Stage 37 from the colour-renderer blocker to AF work.**

**Engineering rules:**

- Original firmware call/parameter parity does **not** prove original photographic pixel parity. Separate each claim.
- No guessed conventional 3×3, 2×3, Q-format, channel interpretation, synthetic 'HNCS' grade, or third-party Phocus LUT may be labeled firmware-equivalent.
- Preserve current user photo/DNG/JPEG behavior while investigation is incomplete. Any future output switch must be opt-in, independently validated and rollback-safe.
- Keep original firmware binaries, tuning payloads, photographs, complete real sidecars, sensor IDs and private calibration arrays out of public GitHub, Actions logs and published artifacts. Only original research source, tests, hashes and sanitized findings belong on the branch.
- Keep `main` unchanged until the user explicitly asks for a production merge. GitHub synchronization has worked on `recovery/awb-rebuild-20261021`.

---

## 2. Verified latest Android artifact and continuity

| Item | Proven value |
|---|---|
| App ID | `com.mwilliams.hasselbladphoton` |
| Latest phone-tested diagnostic | Stage36, versionCode **27190**, versionName `0.1-hb-dual36` |
| Direct APK file | `HasselbladPhoton-Stage36-27190-debug.apk` (previous conversation artifact; not recompiled in this handoff) |
| APK bytes | **70,919,918** |
| APK SHA-256 | `4195998396bde52b3f6604c337797be8f49a38beee714d4e4129afd693e48d29` |
| Verified Stage36 build source | `949d7d935e4897e190bc08d8ce5f7a488534606a` |
| Signed build / tests | https://github.com/mwilliams455/Hasselblad/actions/runs/39903851434 — **SUCCESS** |
| Signature | Same certificate/package identity as Stage34 `27189` and Stage26 `27187`, verified in CI |
| ARM64 native bridge | `libhasselblad_colour_reference_jni.so`, 16 KiB ELF LOAD alignment validated |
| Last working fallback | Stage34 signed APK `27189` (Stage32 `27188`, Stage26 `27187` earlier checkpoints) |
| Actual saved photographic colour | **Photon, unchanged** |
| Original Hasselblad CCM/gamma/LUT photographic parity | **NOT PROVEN** |

**APK execution history:** The user ran Stages 32, 34 and 36 on a physical phone with an existing DNG/sidecar pair and supplied successful JSON. Thus Stage36 is not merely a GitHub build. The Stage36 device test confirms **two native Stage24 reference calls**, not an HNCS photographic rendering or photo-save change.

Stage36 implementation:
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDualNeutralDiagnostic36.java`
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDualNeutralMath36.java`
- `hasselblad_native_audit/isp_android_stage36/tests/Stage36MathSmoke.java`
- `hasselblad_native_audit/isp_android_stage36/tests/Stage36NativeDngSmoke.java`
- `.github/workflows/hb-photon-stage36-dual-neutral.yml`
- Detailed previous implementation handoff: `hasselblad_native_audit/isp_android_stage36/STAGE36_HANDOFF.md`.

CI: **30** new aggregator synthetic checks, **16** end-to-end two-neutral synthetic native tests, earlier **11/11** Stage26 JNI checks, **25** Stage32 parser tests, **32** Stage34 neutral classifier tests, Stage33 binding regression, Stage24 numerical regression, Android compile/signature/package and source-scope guards all passed.

---

## 3. Stage36: actual user RAW observation — VERIFIED

**User-supplied schema:** `hasselblad-stage36-real-dng-dual-neutral-pcs-v1`  
**Result:** `PASS_BOUND_REAL_DNG_DUAL_NEUTRAL_LINEAR_TILE`  
**Input:** real, user-selected saved DNG plus exact corresponding `.capture.json`; the phone independently reverified the DNG checksum and original app-recorded Camera2 physical sensor/frame/timestamp record. **Not independent cryptographic hardware attestation.**

The two Stage24 native calls used:
- Exactly the **same 32 × 32 = 1,024 camera-linear RGB samples**, decoded from the same 4096 × 3072 RGGB RAW DNG.
- The same DNG original ForwardMatrix, CameraCalibration and AnalogBalance data; 4 supported `OpcodeList2` GainMaps applied upstream of diagnostic demosaicing.
- Different neutral only: (a) original selected Camera2 still neutral vs (b) Photon-effective/saved-DNG `AsShotNeutral`.
- Both JNI status **0**. Neither native operation modified the DNG, JPEG, capture, camera HAL or rendered saved image.

### Quantified scene-linear sRGB comparison

| Component | Original Camera2 neutral mean | Photon-effective neutral mean | Mean signed difference: Photon − original | Relative mean difference |
|---|---:|---:|---:|---:|
| Red | 0.02448731115102916 | 0.024485461952629902 | −0.0000018491983992857006 | **−0.007552%** |
| Green | 0.03891678674405634 | 0.03896654009616507 | +0.000049753352108833094 | **+0.127845%** |
| Blue | 0.055915302452831356 | 0.055180848495514204 | −0.0007344539573171799 | **−1.313512%** |

| Metric | Device-reported result |
|---|---:|
| Per-channel RMSE [R, G, B] | [0.00000189024438, 0.00005085770912, 0.00075075636396] |
| Per-channel p95 absolute delta | [0.00000258067075, 0.00006943388046, 0.00102497592852] |
| Per-channel maximum absolute delta | [0.00000281974928, 0.00007586637471, 0.00111993175873] |
| Overall mean absolute delta | **0.00026201883594** |
| Overall RMSE | **0.00043444416505** |
| Overall p95 absolute delta | **0.00090922557894** |
| Overall maximum absolute delta | **0.00111993175873** |
| Negative components | 0 for both passes |
| Greater-than-one components | 0 for both passes |
| Native two calls, combined | **0.089219 ms** for two 1,024-pixel tiles (excluding file read/decode/hash) |
| Total diagnostic duration | **290 ms**, includes repeated DNG reading/hash and binding checks |

**Interpretation:** This establishes a **real RAW, same-input numerical sensitivity** of the neutral-reference Stage24 transform. The blue-channel effect dominates and agrees directionally with the earlier single-neutral matrix analysis. The blue **−1.314%** is specific to this tile's *mean linear-sRGB output*, not ΔE, colour accuracy, human-perceived colour difference, original X2D II equivalence, or proof that either neutral is intrinsically correct. One small scene is not population-level camera calibration. Full-frame timing cannot be extrapolated from the two JNI calls or the 290 ms diagnostic.

**Preserved, privacy-safe device receipt:**
`hasselblad_native_audit/isp_android_stage36/STAGE36_REAL_DEVICE_DUAL_NEUTRAL_PASS_20261023.json` — at source commit `dda5d250a29f2716acba8fdf878b0b990f267cba`.

---

## 4. Capture metadata chain and what it proved

### Stage32 — read-only genuine DNG native neutral tile

- User-selected local **4096 × 3072**, stored 16-bit, uncompressed RGGB TIFF/DNG, one RAW strip, strict source bounds and four independently applied `OpcodeList2` CFA GainMaps.
- A **34×34 Bayer neighbourhood** becomes 32×32 demosaiced linear RGB (1,024 pixels) using a separate diagnostic bilinear operator, **not** the Photon or X2D II demosaicer.
- Stage24 DNG ForwardMatrix/neutral → XYZ D50 → **linear sRGB** works through Android JNI, status 0.
- Genuine first and second phone DNG tests passed. No saved photo changed; no full-frame render or SDK-bit-exact GainMap claim.
- Native opt-in app: Stage32 v27188, later included in Stages 34 and 36.

### Stage33 — original capture-frame evidence matched

- The user supplied the original `.capture.json` saved beside the **second** matching phone DNG. Stage32's independently computed DNG SHA-256 and byte count matched the sidecar.
- Original application-recorded physical Camera2 result, RAW ImageReader target, frame number, original sensor timestamp, 4096×3072 RGGB uncropped RAW_SENSOR and essential metadata agreed.
- App-recorded capture provenance **PASS** (19 private local predicates), not independent hardware attestation.
- The original phone **sensor-mode** field `rawBinningFactorUsed=true` is not contradictory to the **software copy** `delivered_raw.binned=false`; distinguish physical sensor acquisition from later copy/cropping.
- The original complete `.capture.json` was user-provided only in the prior conversation. **The actual 25 MB DNG has not been uploaded to the public research repository**. Future offline full-image comparisons require a private original DNG; Stage37 firmware analysis can proceed without one.

### Stage34 — actual saved DNG neutral is **Photon-effective**, not original Camera2

- Real DNG `AsShotNeutral` tag was read directly from bytes after exact DNG/sidecar and physical frame revalidation.
- User report: `PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED`; `DNG_AsShotNeutral_origin=MATCHES_PHOTON_EFFECTIVE_ONLY`.
- Original vs Photon blue neutral difference: **0.0029296875 absolute, ~0.84% relative**. Red and green neutrals agree.
- Actual DNG `ForwardMatrix1/2` and `CameraCalibration1/2` match both original Camera2 and Photon effective records; not a matrix substitution for this frame.
- Source path identified: `Camera2ApiAutoFix.ApplyRes()` → `whitePoint()` sets Camera2 `SENSOR_NEUTRAL_COLOR_POINT` using preview `mPreviewTemp`; `Parameters.ReCalcColor` reads the effective result; `DngCreator.setParameters()` calls `setAsShotNeutral(parameters.whitePoint)`. **The actual tag value was independently proven in Stage34**, not inferred only from function names.
- No output-modification recommendation follows from this alone. Do not automatically overwrite existing DNG neutral or change the default JPEG rendering.

### Stage35 — neutral-only matrix sensitivity reference

- Source: `hasselblad_native_audit/isp_android_stage35/neutral_sensitivity35.py` (eight synthetic checks; final CI https://github.com/mwilliams455/Hasselblad/actions/runs/39901621203 SUCCESS).
- Under original Stage18 single-profile algebra and identity AnalogBalance *assumption*, Photon-effective vs original reduces the Stage24 camera-to-PCS **blue input-column weighting ~0.831%**; overall matrix Frobenius relative change ~0.781%. Does **not** measure scene colour fidelity or HNCS.
- Stage36 later obtained the actual per-pixel aggregate difference, so **do not repeat a Stage35-only theoretical cycle**. Both are complete within their scopes.

---

## 5. Original X2D II 100C firmware research: proven and unresolved

**Pinned exact original firmware:** X2D II 100C **1.3.16.2**, official archive SHA-256:
`9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.

Official source:
`https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim`

Original files of interest (hash pins):
- `system/lib/modules/vcam_driver.ko`: `29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e`
- `system/lib64/librcam.so`: `3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66`
- `system/etc/iq/hb722_config.json`: `2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286`
- `system/lib64/libdcam_pp.so`: `bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9`

Firmware must be fetched, hash-checked and extracted **transiently** for CI; original binaries, numeric proprietary tuning records and images are **not committed or uploaded as public artifacts**. Existing extraction tool: `hasselblad_native_audit/extract_official.py`.

### Status by critical earlier stage

| Stage(s) | Verified or bounded finding | What is still **not** established |
|---|---|---|
| Original AWB reconstruction / Native1 | Portable JNI arithmetic and original-binary routine tests for a bounded AWB primitive | Calibrated end-to-end Hasselblad auto-WB controller |
| 8 | Original profile preparation/native synthetic comparison on a 6,144-word profile | True on-pixel 3D LUT interpolation or photographic output |
| 16 | Firmware and official product contain HDR-named modes/functions | Universal stacking requirement, active HDR still route, or post-HDR HNCS parity |
| 17 | MAIN CCM original CCT/profile interpolation: **162 cases / 15,552 scalar comparisons**, all match. CCT static knots **2400, 3050, 5550, 9100 K** | Actual ISP pixel equation |
| 19/24/26 | DNG colourimetric Stage18/19/24 reference (ForwardMatrix → XYZ D50 → linear sRGB/P3) through real Android JNI | Hasselblad MAIN CCM/HNCS photographic renderer |
| 21 | Bounded **hypothetical** MAIN-LUT sampler testing only | Original vendor pixel sampler or validated LUT domain/order |
| 25 | `DIQ_iq_main_ccm_lmtx_fw` descriptor connects to CCM driver register family. **16 groups × 6 signed coefficients**, 96 outputs/registers in +0x1CC..+0x348. Neighbouring 9-value arrays are level-control LUTs, **not a proven 3×3 CCM** | Meanings/Q format of the six pixel coefficients |
| 27 | Audited **static still** CCM groups identical across all 16 groups and both high-ISO banks | Any dynamic runtime changes or pixel-domain group selector |
| 28/29 | Original B2R path `b2r_pad_set_fh_fmt → ccm_set_fmt → ccm_set_fn0_config`; format arguments derived from shared record offsets +8/+12, plausibly frame dimensions; original callback table identified | Pixel equation, confirmed format-record struct type, stage order as executed in actual still render |
| 30 | Opt-in DNG `OpcodeList2` GainMap-only correction and float-linear RGGB diagnostic; **28 synthetic checks**, Stage24 regressions | Adobe SDK pixel parity or original Hasselblad lens/colour processing |
| 31 | Original CCM debug setter is **five-bit mux, selectors 0–31**; 12 status/debug functions inspected; **138,644 instructions** scanned for callers; no direct callsite/relocation within original driver for debug mux accessors | Any isolated before/after original CCM pixel oracle. The mux is **not established** as one |
| 32–36 | Genuine saved phone RAW/metadata intake, physically bound source, saved DNG WB provenance, same-source two-neutral reference comparison: **user on-device PASS** | Full-frame production renderer, accurate camera/scene colour calibration, genuine HNCS |

Detailed earlier checkpoints: `hasselblad_native_audit/isp_main_stage31/STAGE31_HANDOFF.md`, `hasselblad_native_audit/isp_dng_stage30/STAGE30_HANDOFF.md`, `hasselblad_native_audit/isp_main_stage29/STAGE29_FINDINGS.md`, and Stage25 README/source. Stage31 verified CI: https://github.com/mwilliams455/Hasselblad/actions/runs/39845352893.

### Important negative boundaries

1. The original **Eagle2 MAIN CCM six-coefficient per-pixel transform** is still unknown: representation, fixed-point Q scale, RGB channel mapping, precision, rounding, clipping and group activation.
2. Original **MAIN gamma interpolation** and **MAIN 3D LUT pixel sampling** are likewise unproven, although parameter preparation and parts of register wiring are recovered.
3. A firmware CPU register setter, matching coefficient preparation, similar coefficients to a neutral-preserving matrix, or a classic 3×3 formula on a different ISP **is not proof** of original X2D II pixel arithmetic.
4. A paired phone DNG and saved Photon JPG cannot isolate Hasselblad's missing ISP stage. The verified Stage24 JNI maps DNG metadata to linear sRGB; it is **not** HNCS and has no vendor colour LUT.
5. The third-party Phocus 4.0.1 **X2D 100C** WB-dependent 2D CbCr ColorCorrect work (`fishvivfish/HNCS-Lightroom`) is **independent cross-generation research**, not evidence the X2D II's 16×6 MAIN CCM uses the same pixel structure. Phocus LUTs/V-Log-to-display LUTs are domain-specific and not safe drop-in camera pixels.

---

## 6. STAGE 37 — EXACT ORDER OF WORK

**First priority: firmware-equivalent colour rendering, not another WB diagnostic APK.**

### 37A. Find authoritative original per-pixel MAIN CCM contract

Start from **existing verified** original firmware extraction and static audits; do not repeat generic searches already ruled out:

- Inspect `hasselblad_native_audit/isp_main_stage25/inspect_main_ccm_contract25.py`, original Stage17 CCM preparation/oracle checks and Stage27–29 original-driver findings. These pin the descriptor identity, 96 register destinations and corresponding library/driver call edges.
- Search the **exact firmware generation** for a CPU/CEVA/DSP fallback, hardware emulation, software offload, machine-readable device register field description, debug patterns, test/calibration image vectors or a genuine MAIN CCM input/output stage. Focus on hardware-facing call relationships in `vcam_driver.ko`, `librcam.so`, `libdcam_pp.so` and relevant available vendor components. Disambiguate MAIN CCM from SUB/POST CCM, ProRes/DNG matrix metadata and unrelated 3×3 RGB transforms.
- Recover or independently prove the original **six coefficient meanings** and signedness, **Q fractional-bit scale**, **input/output channel ordering and range**, **rounding/overflow/clipping**, **profile/region selection**, and **stage placement relative to WB, gamma and 3D LUT**. Record which properties are **proved**, **only suggested** or **unavailable**.
- If static CPU code only prepares/register-writes, say that explicitly; **do not** manufacture pixel semantics. The Stage31 five-bit debug mux had **no proven pixel readback** and **no direct caller in that driver**; move away from it unless independent new evidence appears.

**Deliverable:** New source-controlled, hash-pinned `Stage37` audit with synthetic tests, exact-source CI receipt and a concise truth table of proven vs unsupported pixel semantics, with sanitized outputs only. A mere extended inventory of the same callback getters is insufficient progress.

### 37B. Obtain an isolated original ISP pixel oracle (if a real avenue exists)

Best evidence: the **same X2D II MAIN ISP stage**'s before/after colour pixels from hardware or original callable processing code with coefficients and surrounding stage controls locked. Include neutral, primary, mixed, half-step, negative/signed intermediate (if supported), near-clip and boundary vectors; vary one register/group at a time and compare bit-exact or bounded numeric outputs. Distinguish stage-local pixels from end-to-end photographic JPG processing. If no original hardware/software contract or oracle is available, **do not claim it is validated**.

**Deliverable when supported:** A standalone owned C/arm64 primitive for the *proven* transform, tested against an original routine or original hardware oracle before enabling any Android photographic pixel path. Never infer a conventional 3×3/2×3/Q-shift from 16×6 alone.

### 37C. Then tackle original MAIN gamma and LUT pixel semantics

- Identify the exact still-photo MAIN gamma and 3D LUT stage mapping, register/block memory layout, node order, interpolation/fixed-point precision, clipping and colour-domain expectations.
- Reuse existing bounded original LUT **preparation** research but keep it separate from per-pixel **application** proof.
- Only after the CCM/gamma/LUT operations are individually grounded, implement a controlled JNI/GPU diagnostic that takes source-bound RAW data and reports well-defined numeric parity. Image output should remain diagnostic and opt-in at first; preserve normal Photon processing until user approves a validated swap.

### 37D. Independent real-image comparator (secondary, not a substitute)

Stage36 gives trustworthy physical source-frame binding and a functioning 1,024-pixel neutral-reference path. A later **bounded tile-streamed full-frame reference** can compare a trusted DNG SDK conversion and available Hasselblad/Phocus reference render across skin, tungsten, daylight, shadows and colours, with ICC-aware colour-space/transfer-function matching. Do not treat its diagnostic bilinear demosaic or GainMap interpretation as Adobe SDK exact. Avoid full-frame Python intermediate heaps (~733 MiB previously measured on host). The user's real DNG has **not** been copied into the public source project; obtain it privately only if truly needed. This path helps calibrate/validate photographs but **cannot by itself reveal** the isolated original ISP CCM equation.

### 37E. Deferred work (not next)

- Decide whether to offer an explicit original-Camera2-neutral **DNG metadata** option only after ground-truth image-colour tests. The Stage36 magnitude alone does **not** justify changing Photon defaults.
- Higher-resolution (50 MP) camera streams after the 12 MP first-pass is mature.
- Original Hasselblad subject/face AF/tracking research and prospective safe sharing with Leica M9/Monochrome.
- HDR details only with original pipeline evidence and explicit product-mode objectives; do not enable default stacking by assumption.

---

## 7. Source, build and next-chat navigation

- GitHub working branch: https://github.com/mwilliams455/Hasselblad/tree/recovery/awb-rebuild-20261021
- Stage36 code/readme/receipts: https://github.com/mwilliams455/Hasselblad/tree/recovery/awb-rebuild-20261021/hasselblad_native_audit/isp_android_stage36
- Stage36 signed build: https://github.com/mwilliams455/Hasselblad/actions/runs/39903851434
- Stage34 actual neutral provenance: `hasselblad_native_audit/isp_android_stage34/STAGE34_REAL_DEVICE_WB_PROVENANCE_PASS_20261023.json`
- Stage35 numerical sensitivity: `hasselblad_native_audit/isp_android_stage35/neutral_sensitivity35.py`
- Stage31 exact original CCM debug gate: `hasselblad_native_audit/isp_main_stage31/STAGE31_HANDOFF.md`; CI https://github.com/mwilliams455/Hasselblad/actions/runs/39845352893
- Stage30 GainMap reference: `hasselblad_native_audit/isp_dng_stage30/STAGE30_HANDOFF.md`; CI https://github.com/mwilliams455/Hasselblad/actions/runs/39841847642
- Stage25 hardware register mappings: `hasselblad_native_audit/isp_main_stage25/README.md`
- Stage17 original coefficient preparation: `hasselblad_native_audit/main_colour_20261019/ccm/README.md` (check path/tree if navigating)

**If GitHub connector tools work, reuse exact current recovery branch refs and commit source files there; avoid changing `main`.** On container environments without original source/firmware, use original-firmware fetch and extraction in an ephemeral CI runner with hard-coded SHA-256 checks, then upload **only sanitized proof reports**. CI output should not include full firmware or original vendor matrices/coefficients.

**Do not ask for a new DNG or new Stage36 JSON as the first action:** the real device Stage36 comparison is **already complete**. The next user message saying **“Continue”** means **begin Stage37 original ISP colour arithmetic research/implementation**. If user wants to continue an optional camera test, use the verified `27190` APK without assuming a new build exists.

### Final evidence boundary

- **PROVEN:** real phone DNG read, GainMaps supported, same physically bound RAW tile, Stage24 PCS native processing twice, exact actual `AsShotNeutral` origin, statistically measurable output difference, signing and rollback identity, unchanged Photon saves.
- **NOT PROVEN:** which neutral is more colour-accurate; actual Hasselblad/HNCS photographic image colour; original Eagle2 per-pixel CCM (or MAIN gamma/LUT) formula; Adobe SDK bit-exact GainMap/demosaic/profile interpolation; full-frame native rendering and performance; original Hasselblad face AF.

**Working principle:** Evidence-first colour reconstruction is the goal. Carry forward the verified Stage36 device facts while advancing the missing original firmware pixel operations, not the already-completed neutral diagnostics.
