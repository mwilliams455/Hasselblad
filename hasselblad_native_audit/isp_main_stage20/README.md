# Stage 20 — Original X2D II MAIN/LCDC LUT spatial-layout forensics

22 October 2026, HasselbladPhoton, research only. Follow-on to validated Stage 19 sensor→D50 PCS→standard output primaries. **No saved-photo renderer is enabled.**

## Question

The original X2D II 100C firmware 1.3.16.2 MAIN LUT parameter preparation is validated for eight 6144-word profiles; the original display-library pixel sampler is independently verified on synthetic data. **The shared size does not establish that the MAIN and LCDC use the same packing or spatial interpolation.** This stage asks whether the original camera LUT values are *consistent* with a candidate layout, and whether an explicitly named display model is plausible on an original LCDC table.

## New audited source

`src/main_lut_spatial_audit.py` reads only the hash-pinned original `system/etc/iq/hb722_config.json`, through our original strict inert parser, and checks source hashes before evaluating eight profiles of MAIN and two identically hashed LCDC blocks. It never invokes a vendor function and **does not export numeric LUT values, model node outputs, or image pixels**.

For each input, it tests 72 possible layout permutations: two memory organizations (three 2048-word planar banks or per-node interleaving), six RGB axis orders, and six output component-bank orders. It computes a *conditional* heuristic for each candidate from the real vendor data: normalized difference from an RGB identity lattice, average nearest-neighbour smoothness and curvature, and mean diagonal/off-diagonal differences. Best lower score means only "more consistent with a smooth, approximately identity 3D RGB transform". Not a pixel-hardware oracle. This heuristic is particularly invalid for an intentionally strong, non-identity artistic look.

**Critical mathematical limitation**: jointly relabelling all RGB axes and output components can yield tied scores even with a well-behaved true model. These are observationally equivalent under our symmetric metric. The script explicitly exposes the tied equivalence class and **does not claim to recover canonical RGB axis or bank names**. Even a uniquely best spatial family cannot prove ISP interpolation, scale, knots, CCM→gamma order or clipping.

## Positive and negative controls

The `--self-test` mode uses owned, asymmetric synthetic smooth RGB cubes packed into both planar and interleaved layouts, different axis orders, output-bank permutations. It recovers the correct **memory organization** while allowing tied axis/component relabellings; also checks a degenerate constant LUT and rejects wrong shapes/dtypes. The synthetic test is self-contained and runs in seconds with NumPy. Real original values exist only transiently in the GitHub Actions runner.

The original reference physical packing is described in Stage9's `hb_display_lut16.c`: planar memory axes RGB, two B-adjacent 12-bit output values per word and three 2048-word banks. That layout was proven only for a `libduml_hal.so` display sampler, not X2D MAIN.

## Reproduction

```
python hasselblad_native_audit/isp_main_stage20/src/main_lut_spatial_audit.py --self-test
python hasselblad_native_audit/isp_main_stage20/src/main_lut_spatial_audit.py \
  --original-root /absolute/path/to/exact/firmware/extracted \
  --output /tmp/HB20_PUBLIC_SPATIAL_SCORES.json
```

Use the original hash-verified X2D II 1.3.16.2 firmware, otherwise the audit refuses execution. GitHub Actions `.github/workflows/hb-stage20-main-lut-structure.yml` downloads the official firmware only into an ephemeral runner, verifies the entire 364,814,336-byte file SHA-256, calls our pinned extractor, runs synthetic tests and publishes **only derived candidate aggregate numerical scores and hashes**, never firmware or photographic pixels.

## Decision gate

This is a **ranking**, not evidence of per-pixel hardware behaviour. A candidate survives only as a proposed format for controlled ISP tests. Even if the display model ranks first on MAIN, `MAIN_pixel_layout_proven=false`, `MAIN_pixel_sampler_proven=false`, `render_applied=false` remain fixed. No standalone photo colour transform, Android opt-in switch or new APK can be justified solely by these results.

Next: seek a MAIN-linked sampler/register bitfield definition or bounded hardware output oracle with an asymmetric test table. In parallel, validate an explicitly *empirical* Phocus-like output using genuine paired RAW+Phocus SDR renders and physical reference targets, with scene-level holdouts. Keep film tone and HDR gain-map output separate from WB-dependent colour.

No proprietary code, tune bytes, original photographs, captured hashes, camera-specific matrices or IMaH firmware in public GitHub. Original user RAW and ROI reports remain private in the project Library.
