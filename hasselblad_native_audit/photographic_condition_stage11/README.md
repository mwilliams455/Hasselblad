# Stage 11: X2D II condition-dependent photographic colour selection audit

**Research checkpoint, 22 October 2026 — no new APK, no photographic pixels changed.**

This is a cross-report audit of earlier **original firmware** results. It tests the proposal that the X2D II may use different LUTs based on conditions. The appropriate distinctions are (1) different source tables for different **processing blocks**, (2) selecting/interpolating within the **photographic MAIN table** by known per-frame parameters, and (3) selecting entirely different photographic tables on **unproved scene/ISO/HDR conditions**. These are not interchangeable.

## Known X2D II firmware findings

- `MAIN_3DLUT.lut_data` is a *global-frame* LUT preparation parameter with axes **`cc_color_temp`** (2400, 3050, 5550, 9100 K) and **`color_gamut`** (0/sRGB, 1/P3). Original `librcam.so` profile functions were previously executed against 10 full-size camera data cases. The portable Stage8 math subsequently ran successfully in the real Android development diagnostic. None of these tests exposed a MAIN RGB pixel-output oracle.
- The original IQ data have **eight indexed MAIN profiles but six distinct profile payloads**: the 2400 and 3050 profiles are byte-identical *within either gamut bank*. Thus in the bounded verified two-axis interpolation, 2400–3050 K yields the same LUT within each gamut despite different fractions. The sRGB and P3 banks are different at the recorded knots.
- The IQ configuration separately contains **one MAIN source array** (49,152 words), **two identical LCDC arrays** (49,152 words each), and **three identical PYRA arrays** (30,720 words each). Their three **family hashes are different**, and no LCDC/PYRA 6,144-word chunk matched a MAIN source profile. This establishes distinct **assets associated with different blocks**; it does not establish using LCDC or pyramid assets *instead of* MAIN in a photographed scene.
- `MAIN_3DLUT` is enabled for all five examined still modes. `still0` through `still4` have an identical **positive MAIN gamma curve**; `still4` changes `knee_en` from 0 to 1. Different picture tonality could therefore arise without a new positive gamma table.
- `MAIN_CCM.lmtx_fw` has a separate high-ISO blending axis (`color_hiso`) that was demonstrated for **coefficient preparation**, but the two resulting source banks are **identical in this exact global configuration**. Moving only that weight does not alter that CCM table; other ISO effects and runtime settings remain outside the proof.
- Normal, enhanced normal, and enhanced HDR reprocessing segments all declare `MAIN_CCM`, `MAIN_GAMMA`, `MAIN_3DLUT` enabled and `MAIN_HNCS` bypassed. `post_scap3_calc_3dlut` and `post_hdr_calc_3dlut` call the common adjustment dispatcher, but that *does not yet prove* they choose distinct MAIN LUT values, an alternative artistic LUT bank, or that the segment is taken in a live capture.

These findings **support condition-dependent profile preparation** and *separate family assets*, but **do not yet prove scene-category, atmosphere, skin, foliage, HDR or ISO-driven switching between unrelated MAIN photographic LUT tables**. Avoid inventing a selector or production Lightroom/phone look from this report.

## Reproduce without firmware, original camera LUT, private photographs, or app

From the repository root:

```bash
python3 hasselblad_native_audit/photographic_condition_stage11/condition_audit.py --self-test
python3 hasselblad_native_audit/photographic_condition_stage11/condition_audit.py \
  --output /tmp/stage11-condition-evidence.json
```

The audit consumes **only existing public source-derived reports** and archived original native-execution output hashes from:

- `photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.json`
- `pixel_contract_20261019/asset_format_relationship.json`
- `main_colour_20261019/gamma/main_gamma_config_metadata.json`
- `main_colour_20261019/ccm/ccm_static_evidence.json`
- `main_colour_20261019/main_lut/main_lut_static_evidence.json`

It checks original configuration identity, profile count and order, paired-knot equality, gamut independence, 10 native output-hash receipts, mode-level gamma controls, exact-mode enable flags and the distinct families. It emits bounded **selector receipts**, not camera colour samples. The scenario CCT is a caller-supplied research parameter; no X2D or phone AWB output is implied.

## Most valuable next **new** proof

Inspect a **MAIN-linked** *runtime selector witness* that includes the actual original reprocessing segment, global colour-temperature controller value, gamut, LUT input source identifier/hash, and submitted/active register-table hash (MAIN register 2998, memory 0xf3208000). Compare two frames/camera settings where only *one named condition* changes while holding others constant. The witness must identify the **photographic MAIN** block, not LCDC/display or pyramid blocks. A real camera live register/ISP trace or a proven original MAIN selector-path execution is needed to claim actual routing, as opposed to merely calculating hypothetical outputs from the static config.

For photo **pixel parity**, additionally prove input RGB coordinate domain after CCM/gamma, layout, interpolation, output range and rounding. Stage9's display format is just an alternative hypothesis, and Stage10 already provides a discriminator for it.

### Change boundaries

- No vendor firmware, source tuning arrays, captured photographs, original tables or proprietary bytes checked in.
- No phone colour, white balance, RAW, Bayer shader, DNG, JPEG, runtime camera JNI or APK changes.
- No extra phone test needed to rerun Stage8; the real 12/12 + 8/8 phone result was already provided.
- `main` stays unchanged; research belongs to `recovery/awb-rebuild-20261021`.
