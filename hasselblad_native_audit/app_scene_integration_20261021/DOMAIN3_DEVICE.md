# Domain3 phone diagnostic: on-device validation checkpoint (22 October 2026)

## Verified scope

Domain3 (0.1-hb-domain3 / 27184) ran the on-demand `hasselblad-phone-domain1-on-demand-v1` temperature/tint coverage on an actual Android device, reporting `completed` with the original physical-camera calibration snapshot. This is **the on-device diagnostic**, not the complete Hasselblad automatic white-balance controller and not an HNCS photographic renderer.

The nine-tint by 81-temperature grid reported 729 test points: 707 representable, 19 rejected by the temperature converter, three outside the connected scene signed-gain domain, and zero adjacent duplicates. This matches the earlier recovered phone profile. A separate offline replay of the uploaded DNG's embedded colour/calibration matrices through the actual owned host library reproduced all **729 point values, statuses and exclusion reasons**, with zero mismatches. This gives an independent DNG-to-native model check, not a strict proof that the DNG pixels are the same frame as the development-screen report.

One original, uncompressed, Bayer RAW DNG was inspected: 4096×3072, one frame, RGGB. All 1,024 32×32 block statistics were valid for this particular pale-surface scene, with no black/white clipping. The owned inverse temperature leaf completed for all 1,024 block gains. The JPEG is a resized, untagged copy. Neither photographic WB nor the original Scene1B six-policy capture path was changed by Domain3.

## Research interpretation and safeguards

The phone's large positive model tint for the pale surface is reproducible across this and an earlier neutral-looking capture. This remains **a model-coordinate reading**, not a measured source Kelvin/tint value. The actual lamp spectrum and surface reflectance are unknown. Existing independent numerical/original-metadata checks already ruled out the previously suspected colour-matrix transpose/transport error within the tested model, but physical calibration remains unresolved.

Distance to the representable two-dimensional grid is much smaller than distance to the old zero-tint curve. However, expanding classification to that grid without an independently justified neutral/scene policy risks admitting coloured content. In earlier, incompletely controlled indoor evidence, many blocks also lie close to the two-dimensional grid. Do **not** turn a broad radius, a near-grid match, a HAL neutral or a low inverse residual into a default shipping white-balance choice.

The DNG's stored camera ID, software version and calibration agree with the diagnostic, but the matching original `.capture.json` with DNG SHA-256 and frame/timestamp binding was **not supplied**. Therefore `strict_dng_frame_pairing_proven=false`; the supplied resized JPEG also lacks independent file-level pairing proof. This does not undo the on-device Domain3 result.

## Next work — do not repeat Domain3

1. Close exact DNG↔frame evidence with the matching capture sidecar when available. The original Android provenance and unchanged RAW mode need to be retained; do not replace unknown values with inferred metadata.
2. Research a bounded, separate scene-neutral eligibility/acceptance model using spatial, exposure and multi-illumination checks. Preserve Domain1's explicit valid/excluded mask and the Scene1B 81-point ABI. A continuous temperature interpretation or nearest-grid count alone is insufficient to pick white pixels.
3. Verify candidate stability on controlled neutral targets under multiple documented illuminants, and across physical cameras/modes. Do not transplant X2D sensor constants or fit to Photon/HAL output.
4. Finish the supported phone automatic-controller profile and insert an accepted neutral into RAW-to-linear **exactly once** (avoiding double WB). Independently continue Hasselblad HNCS CCM, tone/gamma, 3D-LUT and saved-photo validation.

This checkpoint changes no native algorithm, APK or photographic rendering. Original photograph pixels, full per-point values and capture-derived colour measurements remain in private evidence, not the public Git repository.

Reproduction script: `audit_domain3_device.py` (requires NumPy, tifffile, Pillow, the previously verified real-leaf host shared object, one private Domain3 JSON and matching DNG). Public aggregate result: `DOMAIN3_DEVICE_RESULT.json`.
