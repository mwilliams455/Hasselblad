# What remains AFTER the lost 20 October AWB reconstruction is fully restored

This is genuinely new work, **not** repetition of the historical AWB recovery. Keep Native1C intact until a safer, validated update exists.

## Priority 1 — complete ordinary AWB scene coverage

1. Generalize the verified ordinary illumination 0 / scene 3 sole-eligible controller to multiple eligible scenes and the additional original scene types actually reached in the saved firmware configuration. Reproduce iteration order, selection and failure/status layering.
2. Recover the earlier frame/statistics lifecycle leading into scene preparation, including any stateful frame-to-frame operation not covered by the selected suffix. Preserve original E2 32x32/1024-block statistics meaning and brightness.
3. Consider active REAWB history/storage and additional spectral/illumination branches only if real configuration/device evidence proves the branch relevant; passive REAWB alone is insufficient.

## Priority 2 — phone-to-Hasselblad AWB input mapping

4. Convert one ordinary ~12.5 MP Camera2 RAW frame and valid exposure/crop/black/white metadata into estimator statistics and calibrated units for each physical camera. Do not reuse X2D II IMX861 calibration as phone calibration. Identify missing measurable inputs and fallback paths.
5. Produce one selected neutral for each capture with original HAL neutral kept unchanged and explicit `fresh / restored / manual / fallback / unavailable` provenance. A final return of 0 is not proof of fresh AWB.

## Priority 3 — the clean linear photographic insertion point

6. Implement an independent signed, unclipped, headroom-preserving RAW-to-linear route, across RAW normalization, optional lens correction and demosaic; prove the actual buffer values with basis/readback checks.
7. Recalculate the coherent camera-to-XYZ transform for the chosen neutral and apply white balance **once**. Keep previous divisors/spatial corrections explicit; do not reuse the ordinary `captureDemosaicLinear` point without auditing ABLC/highlight processing.
8. Test identical RAW offline with original neutral vs reconstructed selected neutral, then prove preview and saved still use consistent state on the phone.

## Priority 4 — actual Hasselblad saved-photo colour (HNCS)

9. Resolve MAIN per-pixel CCM input domain/numeric ordering, gamma evaluation and clipping/rounding, MAIN 3D LUT component layout, interpolation and final composition order. Display-LUT sampler alone does NOT establish the MAIN photographic output.
10. Implement the bounded saved-photo renderer, compare against firmware-derived reference outputs on controlled pixel probes, then photographs. Keep pure AWB, camera calibration and HNCS rendering evidence separate.

## Priority 5 — product validation and rollout

11. Return an experimental build as soon as selected-neutral logging/provenance is trustworthy, even before full HNCS. Requires package identity/signing match, version code >27179, and no regression in captured DNG/JPEG/JSON.
12. Validate multiple physical cameras/lenses, exposure/WB stability, preview-versus-still consistency, sensor crop/RAW modes, grey/skin/foliage/neutrals, and mixed tungsten/daylight sources.
13. Validate failure states, performance/memory/save queue behavior, and no additional HDR/stacking/video/Quad Bayer pathways; then move reviewed checkpoints from recovery branch to main for release.

**Highest-value work immediately after recovery**: general ordinary scene loop and early lifecycle, followed by phone calibration/statistics mapping. These unlock meaningful firmware-derived AWB on the phone; photographic colour parity still requires HNCS.