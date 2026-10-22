# Hasselblad Stage 16 — HDR capabilities versus software ISP replication

**Date:** 22 October 2026. Target camera: X2D II 100C, firmware **1.3.16.2**. Development source: `mwilliams455/Hasselblad`, branch `recovery/awb-rebuild-20261021`. Photo build retained: Stage8 `0.1-hb-stage8`, versionCode 27186. **Research only; no camera capture or renderer changed.**

## Question resolved: Hasselblad has real HDR — but what kind?

This distinction emerged after the Stage15 X1D II firmware examination found `hdr.fw`, `hdr2.fw` and `hdr2_stack`-named functions in the older camera. Those are genuine *old-generation* HDR functions, but they cannot be transferred unexamined to X2D II's HNCS HDR feature.

**Manufacturer's source:** [Hasselblad X2D II 100C FAQ](https://www.hasselblad.com/x-system/x2d-ii-100c-faq/) establishes an optional **HNCS HDR** output setting that includes RAW, HDR HEIF and HDR/Ultra HDR JPEG. When enabled, metering is fixed to Smart Metering. In-camera HDR is disabled for continuous capture, focus/exposure bracketing, manual exposure, RAW-only save, and specified flash operation. RAW files can nevertheless be rendered in HDR in Phocus and exported as Ultra HDR JPEG.

**Independent review, updated July 2026:** [DPReview](https://www.dpreview.com/reviews/hasselblad-x2d-ii-100c-in-depth-review/) observes HDR HEIF or Ultra HDR JPEG **by default**, P3 gamut, and a **lower-resolution gain map embedded with the JPEG** for SDR-compatible display. The reviewer reports Hasselblad described the transfer using a linear response with highlight roll-off, rather than HLG/PQ; the reviewer also observed HDR mode adjusting exposure strategy for highlight headroom. Their 1/4-resolution example is a *sample artifact*, not a universal format requirement.

**Interpretation:** X2D II end-to-end HNCS HDR is fundamentally a **single-photo HDR colour, exposure and display/output workflow**. It does *not require us to implement multiframe exposure stacking* to reproduce a plausible HDR image from one original sensor capture. The exact original camera capture count and internal pixel computations for every HDR mode are **not proved** merely by the documentation or available ELF symbols. Do not confuse older `hdr2_stack` DSP stages, enhanced HDR reprocessing names, and the public HNCS HDR output feature.

## Verified separate original firmware processing evidence

- Stage13: the original X2D II IQ topology has `frog_raw_reprocess_2-r2y-still` (still3), `..._scap3_enh_normal` (still0) and `..._scap3_enh_hdr` (still0), each statically enabling `MAIN_CCM`, `MAIN_GAMMA`, `MAIN_3DLUT` in the three examined reprocess segments.
- Stage13: `post_hdr_calc_3dlut` and `post_scap3_calc_3dlut` each call the common adjustment dispatcher, but the archived call inventory does not prove which effective LUT bytes reach the MAIN 3D LUT register on a real camera.
- Stage14: the software-ISP research harness composes proven LUT/CCM **parameter preparation** and gamma coordinates with a **DISPLAY-only** LUT pixel sampler hypothesis. It must refuse production photographic pixel rendering. No HNCS HDR/photo pixel operation is derived from it.
- Stage15: older X1D II `libmod_x1dm2.so` exposes model-specific CCM tuning descriptors, while older HDR/HDR2 CEVA firmware is packaged separately. Those are not a proven X2D II ISP pixel equation.
- Stage16's new original-firmware script compares X2D II HDR/RAW and CCM function names, static saved-still route metadata, and MAIN source selection axes. It never invokes a camera library and never outputs firmware code bytes or private tables.

## Proposed port architecture (design decision, not implementation)

Keep the original 12 MP single-frame RAW and current SDR output as the reference. Add a **future explicit opt-in HDR-output variant**, not a capture-fusion change:

1. Preserve sensor RAW, original metadata binding, high-precision linear values, negative noise/headroom, and one-time calibrated WB. No HDR/stacking in Stage6/Stage8 baseline.
2. Prove or empirically fit Hasselblad camera colour and tone transforms. Carry scene-linear highlight information through the verified CCM, gamma and MAIN LUT stages, or leave the HDR branch disabled.
3. Build a normal SDR-compatible base image, plus a separately calibrated higher-headroom target rendition. Derive and validate a brightness gain map and metadata from the **same** photographic frame. Confirm backward-compatible SDR decoding and HDR colour on compatible displays. Do not treat a generic gain-map boost as HNCS parity.
4. Target Android `ImageFormat.JPEG_R` (API 34+) and `android.graphics.Gainmap` for a suitable codec path. Android HEIC_ULTRAHDR exists on API 36+, but is not required in the first A/B. Codecs and device support must be checked before enabling output; standard JPEG/RAW continues to work on all supported phones.
5. Respect original-device evidence: HDR enabled influences Smart Metering. Before changing Photon AE, record side-by-side exposure/headroom policy, do not silently brighten existing output or apply multi-frame stacking, and preserve no-HDR default for our current dev build.
6. Test both variants on exactly the same RAW capture. Report colour-space primaries, SDR fallback, gain-map dimensions, gain metadata, clipping/oversaturation, and preview correspondence. Manual exposure is a separate explicit testing case.

## Source of evidence versus inference

| Claim | Classification |
|---|---|
| X2D II supports HNCS HDR JPG/HEIF and optional mode | Official Hasselblad product documentation |
| HDR automatically fixes Smart Metering, disabled in bracketing/manual/RAW-only capture | Official Hasselblad FAQ |
| HDR HEIF/JPEG by default, JPEG gain map, P3 output, exposure shift/headroom | Published independent camera review; not original-code validation |
| X2D II firmware contains separate HDR reprocessing names/paths | Exact-hash original firmware structural evidence, *not execution* |
| Every X2D II HDR photo uses multi-frame stacking | **Not demonstrated** |
| The HDR ISP function named `post_hdr_calc_3dlut` itself constructs JPEG gainmaps | **Not demonstrated** |
| X2D II MAIN CCM's 16 × 6 register coefficients have a proven pixel equation | **Not demonstrated** |
| An optional single-RAW gain-map HDR port is feasible in Android | Platform API evidence and architecture proposal, not built/tested |

## Reproduce Stage16 original-firmware inspection

After obtaining and verifying *exact* X2DII firmware in a temporary workspace (same method as Stage13):

```bash
python3 hasselblad_native_audit/isp_hdr_stage16/inspect_hdr_ccm.py --self-test
python3 hasselblad_native_audit/isp_hdr_stage16/inspect_hdr_ccm.py \
  --repo . \
  --firmware-root hasselblad_native_audit/firmware/extracted \
  --output /tmp/STAGE16_ORIGINAL_HDR_CCM_RECEIPT.json
```

CI workflow `.github/workflows/hb-isp-stage16-hdr-ccm.yml` builds no APK, runs no original firmware instructions, and exports **metadata only**. Original tuning arrays, extracted binaries and RAW/JPG samples remain outside public GitHub.

## Next research priorities

1. **Recover MAIN CCM's pixel equation:** investigate signed 16×6 register lanes and the 9+9 separate fields. Need genuine hardware or original-function input/output oracle for channel order, normalization, region selection and fixed-point rounding; do not invent a 3×3 transform.
2. Recover gamma and MAIN 3D LUT **pixel** contracts, including pixel shaper and output clipping.
3. Compare **HNCS HDR output** with matched X2D II SDR/HDR JPEG+RAW examples and gainmap metadata, rather than guessing vendor tone curves.
4. When colour and tone are verified, develop a reversible, opt-in, **single-frame HDR** A/B on phone. User retains RAW/JPEG controls, no stacked captures unless independently required and separately authorized.

No change has been made to `main`, current APK or photographic output in this checkpoint.
