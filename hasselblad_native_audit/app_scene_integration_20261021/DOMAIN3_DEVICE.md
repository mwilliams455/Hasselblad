# Domain3 phone diagnostic: on-device validation checkpoint (22 October 2026)

## Verified scope

Domain3 (0.1-hb-domain3 / 27184) ran the on-demand `hasselblad-phone-domain1-on-demand-v1` temperature/tint coverage on an actual Android device, reporting `completed` with the original physical-camera calibration snapshot. This is **the on-device diagnostic**, not the complete Hasselblad automatic white-balance controller and not an HNCS photographic renderer.

The nine-tint by 81-temperature grid reported 729 test points: 707 representable, 19 rejected by the temperature converter, three outside the connected scene signed-gain domain, and zero adjacent duplicates. This matches the earlier recovered phone profile. A separate offline replay of the uploaded DNG's embedded colour/calibration matrices through the actual owned host library reproduced all **729 point values, statuses and exclusion reasons**, with zero mismatches. The independently supplied original capture sidecar now binds that hash-matching DNG to the same physical camera, frame and timestamp as the development-screen report. Model consistency and original capture identity are separate checks, both now passed.

One original, uncompressed, Bayer RAW DNG was inspected: 4096×3072, one frame, RGGB. All 1,024 32×32 block statistics were valid for this particular pale-surface scene, with no black/white clipping. The owned inverse temperature leaf completed for all 1,024 block gains. The JPEG is a resized, untagged copy. Neither photographic WB nor the original Scene1B six-policy capture path was changed by Domain3.

## Research interpretation and safeguards

The phone's large positive model tint for the pale surface is reproducible across this and an earlier neutral-looking capture. This remains **a model-coordinate reading**, not a measured source Kelvin/tint value. The actual lamp spectrum and surface reflectance are unknown. Existing independent numerical/original-metadata checks already ruled out the previously suspected colour-matrix transpose/transport error within the tested model, but physical calibration remains unresolved.

Distance to the representable two-dimensional grid is much smaller than distance to the old zero-tint curve. However, expanding classification to that grid without an independently justified neutral/scene policy risks admitting coloured content. In earlier, incompletely controlled indoor evidence, many blocks also lie close to the two-dimensional grid. Do **not** turn a broad radius, a near-grid match, a HAL neutral or a low inverse residual into a default shipping white-balance choice.

The matching `IMG_20261022_053840.capture.json` was subsequently supplied. Its recorded DNG byte length and SHA-256 match the original DNG exactly; the capture evidence binds physical camera 2, frame 225 and original sensor timestamp to the Domain3 diagnostic. `strict_dng_frame_pairing_proven=true` for this capture. The resized JPEG remains without independent file-level pairing proof.

## Sidecar and shading follow-up (22 October 2026)

The new, separately supplied original capture sidecar was checked by `verify_domain3_pairing_and_shading.py` against the original DNG bytes and separate Domain3 JSON, not inferred from the filename. All asserted frame, sensor timestamp, physical camera and RAW geometry records agree; the DNG file SHA-256 and byte count match precisely. The sensor is the same verified Camera2 physical sensor used for the app diagnostic.

All 59 colour-calibration/white-point entries in the DNG and original Camera2 record are **numerically equal**. Of those, 47 rational entries are encoded with exactly identical numerator/denominator pairs; the remaining 12 are zero-valued CameraCalibration off-diagonal entries serialised in the DNG with `0/16777216` rather than Camera2's `0/1`. These are mathematically identical and do **not** indicate changed camera calibration. The original HAL neutral, DNG AsShotNeutral and effective Photon neutral agree exactly.

The original Camera2 13×17×4 lens shading map matches the effective Photon map element-for-element. The Scene1B candidate diagnostic explicitly does **not** apply shading, even though Photon records an available map. A separate hypothetical pre-statistics bilinear application reduces both colour-ratio medians and narrows their spatial spread, but the model's positive tint remains substantial. No photo pixels, Camera2 metadata, processing code or diagnostic policy were modified. This is a **sensitivity test**, not proof whether the delivered DNG or renderer has already been shade-corrected; never apply the map twice.

The temperature/tint inverse is still a **model coordinate** and not a measured light spectrum or certified white target. Do not fit acceptance policy to these same observations or the HAL solution; uncontrolled coloured scenes can also fall near the 2D lattice. All photo-derived values and private sensor calibration remain outside public GitHub. The supplementary public result is `DOMAIN3_PAIR_SHADING_RESULT.json`.

## Next work — do not repeat Domain3

1. **Completed:** exact DNG↔original frame association using the supplied sidecar. Original Camera2 sensor provenance and unchanged RAW geometry are verified and retained privately. Do not repeat this investigation.
2. Research a bounded, separate scene-neutral eligibility/acceptance model using spatial, exposure and multi-illumination checks. Preserve Domain1's explicit valid/excluded mask and the Scene1B 81-point ABI. A continuous temperature interpretation or nearest-grid count alone is insufficient to pick white pixels.
3. Verify candidate stability on controlled neutral targets under multiple documented illuminants, and across physical cameras/modes. Do not transplant X2D sensor constants or fit to Photon/HAL output.
4. Finish the supported phone automatic-controller profile and insert an accepted neutral into RAW-to-linear **exactly once** (avoiding double WB). Independently continue Hasselblad HNCS CCM, tone/gamma, 3D-LUT and saved-photo validation.

This checkpoint changes no native algorithm, APK or photographic rendering. Original photograph pixels, full per-point values and capture-derived colour measurements remain in private evidence, not the public Git repository.

Reproduction script: `audit_domain3_device.py` (requires NumPy, tifffile, Pillow, the previously verified real-leaf host shared object, one private Domain3 JSON and matching DNG). Public aggregate result: `DOMAIN3_DEVICE_RESULT.json`.
