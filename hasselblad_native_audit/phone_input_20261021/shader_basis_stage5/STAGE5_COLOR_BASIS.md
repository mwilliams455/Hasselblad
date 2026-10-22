# Hasselblad Photon — Stage5 colour-basis CPU reference (22 October 2026)

## Status

**Source-only diagnostic implementation**. Stage4 source-only neutral observer is already verified. Stage5 adds a separate native pixel-level study of the input colour basis for the ordinary full-frame RGGB route, plus an independent Python reference. **No Android app integration, no new APK, no GPU shader parity and no photographic AWB selection.** The installed build stays Domain3 (version 27184). The production Photon render and `main` are unchanged.

## Why this is necessary

The verified Domain3 capture's 1024 RAW-block ratios are much more sensitive to the declared shading basis than the earlier narrow one-dimensional temperature curve suggested. Stage4 avoids manufacturing a neutral and always abstains. Before calibrating neutral acceptance, we must distinguish original, untouched Bayer sensor coordinates from a hypothetical shading-adjusted basis and check the exact source expressions on which Photon renders.

## Source trace

From checked-in Photon source, the ordinary default `PostPipeline` calls `Bayer2Float` before demosaic. Its Java node binds the actual `Parameters.gainMap` as `GL_LINEAR`, `FLOAT_16`, 4-channel `GainMap` plus the current `whitePoint`. The shader `Bayer2Float/tofloat.glsl` uses `texture(GainMap, vec2(xy)*RawInvSize)` for uncropped Bayer, averages Gr and Gb and divides each of R/G/B gains by their RGB arithmetic mean. On a non-RGB-layout Bayer site, it subsequently divides the normalised raw value by the *existing* whitePoint channel before applying site gain. For a cropped input, it has an explicit `GainOffset`/`GainFullInvSize` alternate path; RGB-layout and highlight reconstruction have other branches.

Stage5 implements a **source-expression-aligned CPU sampling model**, not the full GLSL draw. On full, tightly packed, physically proven RGGB Bayer RAW16 only, it:

1. Validates 32×32 RAW block partition, no crop/remosaic/unknown frame, timestamp/exposure/ISO, black/white codes, and bounded 4-channel sensor gain-map geometry with an exact input map length. It never changes the input, and a failed call never modifies the output.
2. Quantises Camera2's 32-bit map coefficients to IEEE binary16 then decodes them, to model the Java `FLOAT_16` upload. Uses GL-style `coord * mapCells / rawSize - 0.5` sampling with endpoint clamping, then bilinear interpolation.
3. Selects site-specific R, mean(G1,G2), B and divides by `mean(R, mean(G1,G2), B)`, exactly as the GLSL **expression**. Applies this hypothetical relative gain to `(RAW - black) / (white - black)` before each CFA site's 1024-block aggregation. The original unshaded RAW remains a distinct `study_basis` mode.
4. Computes site means, Bayer brightness and Q12 R/B ratios for the existing bounded Stage4 observer. Preserves sensor/RAW identity evidence and flags invalid raw blocks. Output has **no white-balance neutral, no render permit and no selected production policy.**

The reference omits division by the pre-existing HAL/Photon whitePoint so we do **not** contaminate an independent AWB observation with the WB we are trying to replace. This is the correct *study intent*, not an assertion that the simulated statistics equal a camera's internal AWB input. It also omits the actual pre-normalized FP16 texture values, shader clamping, highlight reconstruction, exact mobile GPU filtering/rounding, crop, RGB-layout, Quad Bayer and DNG-render/preview branches. No claim of pixel-identical GPU or firmware operation is made. A full shader/device oracle would need GPU readback from the relevant stage, with signed headroom and app render invariance checks.

## Local tests

`tests/verify_stage5_basis.py` loads the Stage4 ABIs from the sibling `neutral_observation` directory, compiles Stage5 at host O0/O2/Clang, and compares every 32×32 block's four site means to an independent numpy float64 + float16 interpolation oracle. The host checks include synthetic nonuniform maps, a solid map with edge cases, **15 rejection/nonmutation cases per compiler**, deterministic replay, and no render-neutral output. The native C sanitizer probe additionally runs under ASan + UBSan.

The private replay requires explicit `--capture --dng --domain-json --private-report --private-replay`, checks capture-DNG hash, sensor/frame binding, original dynamic black/white levels and passes the source-aligned projected blocks through the existing Stage4 `ABSTAIN` observer. It never writes/edits RAW, DNG, JPEG or the app. Private phone-derived counts and user sensor data are retained in the user's private Library; GitHub receives only generic implementation and aggregate test status.

### Source-only build (from repository root)

```sh
python3 hasselblad_native_audit/phone_input_20261021/shader_basis_stage5/tests/verify_stage5_basis.py \
  --out /tmp/STAGE5_PUBLIC_RESULT.json
```

### Deliberately excluded

- Automatic white-balance *selection* or HAL fitting; no scene-based recogniser; no new shipping threshold.
- Any use of X2D vendor calibration on Xiaomi or non-Xiaomi sensors; no vendor shared library.
- Source equivalence for cropped, RGB-layout, pre-binned or HDR processing paths.
- Photograph processing, `Converter.java`, `Parameters.java`, original DNG metadata, or HNCS CCM/tone/gamma/3D-LUT work.

## Next technical boundary

Obtain a controlled GPU-stage observation for the supported Bayer path (or read back a reliably bound intermediate) to compare with Stage5 projection under the same map and light. Only after the pixel-basis and shading state are established should a calibrated, sensor/mode-aware Stage4 policy be developed from independent reference neutral and nonneutral illuminants. The new prospective neutral must replace the old RAW-to-linear whitePoint **once**, with DNG consistency and a proven fallback; it must not be multiplied on top of existing Photon/HAL WB. An already-shaded frame must not be shaded again.

Continue working only on `recovery/awb-rebuild-20261021`; leave `main` and installed Domain3 unchanged.
