# HasselbladPhoton — Stage 30 handoff: real-RAW reference correction and firmware-equivalent colour gate

**Date:** Thursday, 22 October 2026 (UK)  
**Repository:** https://github.com/mwilliams455/Hasselblad  
**Working branch:** `recovery/awb-rebuild-20261021`  
**Verified branch commit:** `6d9eaaa1cb59199d6018b7f49fe610b23ab7f3c3`  
**Hosted CI:** https://github.com/mwilliams455/Hasselblad/actions/runs/39841847642 — **completed / success**  
**Baseline branch `main`:** `929f523aa02ae5b224be39b9c36cce5975691a10` (untouched).  
**Latest device-tested APK:** Stage26 `27187`, user-reported on-device JNI synthetic `11/11 PASS` (4.625 ms for small tests, **not** full-frame). Saved photographic JPEG colour remains Photon.

## 1. What Stage 30 added and verified

The standalone **Stage 24 original DNG ForwardMatrix/AsShotNeutral → XYZ D50 → linear sRGB/Display P3** reference was extended with an **explicit opt-in DNG `OpcodeList2` GainMap correction mode**. This is a device-independent *offline* diagnostic, not Hasselblad's recovered MAIN CCM, HNCS rendering, tone or LUT.

- `hasselblad_native_audit/isp_dng_stage30/src/dng_gainmap30.py` implements original Python code parsing the DNG **big-endian** opcode-list framing and gain-map opcode ID **9** (10 unsigned integers, 4 doubles, one unsigned integer, followed by an NxMx1 float32 gain grid). Values are bounded, checked finite, and applied to the **single-plane, already black/white range-mapped RGGB CFA** before demosaic.
- Four independent Bayer-site rectangles with row and column pitch **2** are supported, as in Android's DNG lens-shading-map encoder. Bilinear interpolation uses normalized image coordinates and edge replication; each corrected sample is capped at 1.0 in the diagnostic Stage2 domain, reflecting published DNG GainMap semantics. **It is not asserted to be byte/bit-exact with the Adobe DNG SDK.**
- `demosaic_linear_rg_reference` is an explicit float32 RGGB-bilinear diagnostic that preserves original red, blue and both green photosite values at their source locations. This prevents an earlier first-pass defect that blended one green photosite class with neighbouring green samples. It is **not Photon's or Hasselblad's demosaic**.
- `hasselblad_native_audit/isp_colour_stage24/src/offline_render24.py` has a new flag **`--apply-supported-dng-gainmaps`**. This flag refuses absent `OpcodeList2`, any `OpcodeList1`/`OpcodeList3`, unsupported opcodes (including unknown optional ones), malformed maps and incompatible `--accept-unhandled-dng-opcodes`. Without the flag, the historical Stage24 behavior remains unchanged and unhandled opcodes still require explicit acknowledgement.
- No original DNG/RAW samples or vendor IQ arrays are in GitHub or CI. The new Python processing is **not connected to Camera2, Stage26 JNI, Android photo saving or the preview**.

### Verification

All hosted checks passed at run `39841847642`:

| Check | Observed status |
| --- | --- |
| GainMap framing, scalar-vs-vector bilinear interpolation, four Bayer site classes, invalid/optional refusals, sample preservation | **28 synthetic checks PASS** |
| Stage24 new opt-in entry point plus previous demosaic method | **PASS** |
| Original Stage24 C native colourimetric numerical parity under GCC | **PASS** |
| Same original Stage24 numerical parity under Clang | **PASS** |
| Public artifact and photo/vendor-asset exclusion | **PASS** |
| Verified full-size private phone DNG actually corrected | **NOT DONE: original file unavailable** |
| Original X2D II MAIN pixel math or HNCS | **NOT PROVEN / NOT ENABLED** |

Public CI evidence ZIP: `Hasselblad-Stage30-GainMap-Verified-Results.zip` (four synthetic numeric receipts, no photographs). The earlier Stage24 workflow was pinned to its verified Stage24 source on manual dispatch only, preventing newer Stage30 path additions from causing misleading historical Stage24-scope CI failures. Stage30 now reruns both native reference tests.

### Synthetic host performance, not phone speed

A **4096 × 3072 (12,582,912-pixel)** synthetic RAW mosaic with four **13 × 17** gain maps was processed locally with the Stage30 Python implementation:

- GainMap corrections: **0.847 s**.
- Float32 diagnostic bilinear demosaic: **1.647 s**.
- Combined measured wall time: **2.495 s**.
- Peak process RSS on that host: approximately **733 MiB**.

This benchmark excludes Stage24 native colour conversion, image export and Android overhead. It is neither the full phone pipeline nor a promise of acceptable in-app performance. It reinforces that future camera integration should **tile/stream**, ideally with native or GPU execution, rather than naively copying the full Python image approach into an APK.

## 2. Why this matters for Hasselblad replication

Stage24 originally rendered real 12 MP DNG camera data but ignored `OpcodeList2`, leaving lens-shading variations and per-channel edge falloff confounded with CCM/AWB differences. The Stage30 opt-in route can correct the **supported GainMap-only case** before comparing neutral reference colour to Photon and genuine Hasselblad results. A previously supplied capture diagnostic recorded a lens shading map (17 × 13 sample lattice, four Bayer channels) for the main Xiaomi camera, but **the original DNG opcode bytes and raw photo are not present**, so this specific capture has NOT been re-rendered or proven to match Adobe or Photon.

The correction applies standard DNG numerical operations, **not vendor X2D II HNCS transforms**. It cannot stand in for Hasselblad WB, authentic six-coefficient MAIN CCM pixel math, MAIN gamma interpolation, MAIN 3D LUT sampler, Film Tone, exposure or atmosphere processing.

## 3. Firmware-equivalent blocker and next evidence gate

Prior verified state remains:

- Stage17: original X2D II MAIN CCM parameter interpolation; 16 groups × 6 signed fields; 162 original cases / 15,552 scalars match.
- Stage25: exact `librcam.so` register descriptors map into Eagle2 `vcam_driver.ko` `ccm_set_ig0_config` 96-register destination at block base +0x1CC..+0x348.
- Stage27: all 16 groups and both high-ISO banks of the inspected static still table are identical; group selector cannot change those six source values *for that static table*, although runtime overrides are unexcluded.
- Stage28: register/callback link `b2r_pad_set_fh_fmt` → `ccm_set_fmt` → `ccm_set_fn0_config`; no pixel arithmetic in these CPU-side register writers.
- Stage29: format arguments x1/x2 derive from a shared B2R pointer record offsets +0x08/+0x0C (possibly frame geometry); `b2r_pad_ops` contains `b2r_pad_set_fh_stream` and `b2r_pad_set_fh_fmt` callbacks. No confirmed Q scale, pixel matrix semantics or HNCS.

**The actual next important Stage31 task** is a genuine Eagle2 MAIN CCM pixel oracle or an authoritative ISP specification: source-domain channel order, six signed coefficient meanings, fixed-point scale, rounding, clipping, dynamic profile selector, and stage order relative to gamma/LUT. A QEMU UI-only guest, unrelated ISP matrix headers, or paired JPEG/3FR cannot prove this isolated pixel operation. A possible real-hardware oracle would capture the **same stage's before and after RGB samples** while locking the CCM registers and bypassing other colour stages, with neutral/primary/half-step/near-clip test vectors. No such oracle is currently available here. Avoid assigning a conventional 3×3/2×3 transform from the mere count of six fields.

This stage therefore **did not change or enable** vendor-colour processing on phone, because the necessary mathematical evidence is still missing. Firmware-equivalent remains the primary objective.

## 4. Reproduction

From the checked-out recovery branch:

```sh
python3 hasselblad_native_audit/isp_dng_stage30/tests/test_gainmap30.py
python3 hasselblad_native_audit/isp_dng_stage30/tests/test_stage24_integration30.py
python3 hasselblad_native_audit/isp_colour_stage24/tests/test_renderer24.py --compiler gcc
```

To run the new correction on an **actual private** DNG only once its GainMap-only opcode status is established:

```sh
python3 hasselblad_native_audit/isp_colour_stage24/src/offline_render24.py \
  --dng /private/phone.dng \
  --out-directory /private/hasselblad_stage30 \
  --gamut srgb \
  --apply-supported-dng-gainmaps \
  --linear-tiff
```

Other DNG opcodes or unsupported colour profiles must fail, not silently approximate. Validate orientation/cropping, Bayer sites, physical sensor/frame metadata and correctness against a standard DNG SDK RAW conversion before trusting photographic differences.

## 5. Source links and privacy

- Stage30 source/readme: https://github.com/mwilliams455/Hasselblad/tree/recovery/awb-rebuild-20261021/hasselblad_native_audit/isp_dng_stage30
- Stage24 opt-in offline renderer: https://github.com/mwilliams455/Hasselblad/blob/recovery/awb-rebuild-20261021/hasselblad_native_audit/isp_colour_stage24/src/offline_render24.py
- Stage30 CI: https://github.com/mwilliams455/Hasselblad/actions/runs/39841847642
- Android AOSP DNG GainMap encoder source: https://android.googlesource.com/platform/frameworks/av/+/06f46cabd0d52f77520919092b589ce16a282a59/media/img_utils/src/DngUtils.cpp
- Adobe DNG SDK GainMap source: https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_gain_map.cpp

Never publish original phone DNG/JPEG/TIFF, real lens shading values, private camera matrices, vendor firmware or tuning payloads in this repository, public CI artifacts or public issue/PR text. Research source and synthetic receipts are safe. **Do not modify `main`**. Stage26 signed `27187` stays the last actual Android test baseline; Stage30 generated no new APK.

**Handoff instruction:** Continue with a rigorous Stage31 original Eagle2 MAIN CCM hardware pixel oracle/specification search rather than more B2R format callbacks. In parallel, when a private original phone DNG is available, run the strictly supported Stage30 GainMap correction, confirm crop/geometry, compare against a validated reference, and only then consider a bounded on-device neutral preview diagnostic. Do not claim HNCS or vendor colour science from the neutral bridge.
