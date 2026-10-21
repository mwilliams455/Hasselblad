# Phone temperature calibration workspace — 21 October 2026

The rebuilt gain/temperature routines now run with the phone's original Camera2 colour and calibration transforms, initialized entirely by owned code. The new workspace does not import vendor context, call the vendor initializer or load `libaaa.so`. Its output is a temperature/gain model, not a scene-selected automatic white balance. The full automatic controller still requires a separate phone profile.

## Implemented boundary

`hb_phone_temperature.c/.h` owns an opaque, read-only temperature workspace. Construction combines each original pair as `calibrationTransform * colorTransform`, sorts the complete anchors by temperature, and supplies those two matrices to the previously verified owned temperature leaves. Interpolation is linear in reciprocal temperature with endpoint clamping. This follows the endpoint-product convention in the public Adobe DNG SDK, including distinct calibration transforms at the two endpoints. Matrix order is significant. The implementation does not use forward matrices, normalize rows for rendering, apply WB or change photographic pixels.

The workspace allocates the existing context/config sizes from zero, populates only the temperature-matrix rows and keeps the automatic initialization marker unset. It is opaque so a caller cannot mistake it for a fully initialized automatic context. E-ND/exposure-dependent calibration is disabled. No scene radii, spectral measurements, spatial corrections, history defaults or exposure scales are fabricated. Each handle occupies about 2.4 MB; it is intended to be created once per validated physical-camera profile, not per block. This is an integration workspace, not a phone performance measurement.

`temperature_binding.py` reuses the strict capture binder and reads matrices exclusively from original sensor characteristics. Android-style rational-to-binary32 conversion is preserved. The verified metadata mapping currently accepts Standard A (17 → 2856 K) and D65 (21 → 6504 K), with distinct anchors. It requires equal Bayer-site black levels for this RAW adapter: then its `(white-black)` normalization is a common scalar and does not change neutral ratios. Unequal site spans and other illuminant mappings reject until their basis is validated. This is a capability restriction, not a device-name whitelist. Exported, dynamic and static black sources remain explicit, and original HAL metadata remain unchanged.

The public 31-row isotemperature table is pinned to the Adobe DNG SDK 1.4 variant, including `u=0.24702` at 325 mired. Some implementations use `0.24792` there. This checkpoint intentionally records the chosen variant; it does not silently mix them or claim an exact spectral/Planck integration. Table facts are public numerical data, not a firmware or device-calibration dump. The existing owned numerical routines are reused without modification.

## Failure behavior

- Invalid/duplicate temperatures, nonfinite or out-of-bound coefficients, and matrices whose interpolation becomes singular reject before a handle is published. The determinant is a cubic along the interpolation segment: endpoints and all interior extrema are checked, including a synthetic case with two very close singularities missed by coarse sampling. Positive determinant >1e-4 and absolute coefficients ≤16 are explicit bounded-profile rules.
- Forward conversion accepts 1667–100000 K and finite tint within ±150, then rejects a channel reaching the owned leaf's 10× gain cap. Unsupported output is never returned as an accepted neutral.
- Inverse conversion accepts nonzero integer gains up to65535 and a channel ratio below10. It verifies finite output and reconstructs the gain ratios at the returned CT/tint. Maximum relative channel/green error must be ≤0.3%; this catches unusable iterative solutions. This is a numerical residual gate, not a photographic confidence score.
- All public output arguments remain unchanged on rejection. Input buffers must be complete, disjoint objects. Successful handles are immutable and support concurrent reads; callers must synchronize destruction.

The 81-point 2000–10000 K zero-tint curve is now generated from the actual phone model, alongside ±25-tint sweeps. These are temperature/gain loci only. No radius has been assigned to turn them into a white-pixel classifier. The original HAL neutral is interpreted as an additional replay input, clearly labelled as the HAL result; it is not presented as a newly estimated scene neutral.

## Fresh verification

`PHONE_TEMPERATURE_RESULT.json` records the exact source/input/binary identities and aggregate results:

- Three real metadata bindings (exported/dynamic/static black) produce the same temperature descriptor while preserving their distinct RAW black choices.
- The actual phone model passes all243 CT/tint samples. Sixteen independent synthetic profiles exercise noncommuting products and differing endpoint calibration transforms.
- 4,131 matrix comparisons against independent NumPy float64 algebra; maximum absolute coefficient difference2.12e-7.
- 4,059 accepted forward comparisons and inverse round trips. Maximum forward error1.05 Q12 units, CT round-trip difference5.08 K and tint difference0.142. An independent XYZ reconstruction agrees within1.75e-5. These quantify numerical behavior, not absolute physical calibration accuracy.
- 72 synthetic samples correctly reject gain clipping, confirmed by the independent oracle. A separate clipping test verifies complete output non-mutation. Swapping full calibration anchors preserves all4,059 accepted gain results exactly.
- 26 native rejection cases per probe run and seven metadata rejection cases pass. Replacing all effective/render-owned colour/calibration fields leaves the original-metadata model unchanged.
- Six exact18,496-byte comparisons across optimized host, ASan/UBSan and Android API28 ARM64/QEMU: the actual phone profile and two synthetic profiles. Each contains243 records, matrix/gain/CT/tint outputs, statuses and a HAL-gain interpretation. No differences.

LeakSanitizer is disabled because this executor denies `/proc` task inspection; address/undefined checks remain enabled and fatal. The initial test harness incorrectly required every synthetic point to fit under10× and initially passed a linker flag to a compile-only Clang invocation. Both harness issues were corrected before the final run. No numerical implementation correction was required. No original-firmware parity or on-device image/performance claim is added by this checkpoint.

## Reproduce

Use Python with NumPy, host `cc`, NDKr27 and the restored API28 Bionic/QEMU runtime:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hasselblad_native_audit/phone_input_20261021/verify_phone_temperature.py \
  --capture /private/IMG_20261020_062344.capture.json \
  --out /private/phone-temperature-check --report /private/phone-temperature-result.json \
  --ndk /tools/android-ndk-r27 --qemu /tools/qemu-aarch64-static \
  --firmware-root /private/extracted
```

Only the owned temperature/user-control/scene-temperature sources are linked with section garbage collection; unrelated routines are discarded. `libaaa.so` is not loaded. Android uses the previously restored Bionic libraries. Final bindings, phone-specific loci, gain interpretation, executables and logs remain private in `Hasselblad_Phone_Temperature_Evidence_PRIVATE_20261021.zip`. Original capture restoration remains `hasselblad.zip`, Library `libfile_20a4cdf4b5b8819198e741fda306316b`.

## Remaining path to the phone

1. Define the bounded phone automatic profile: white/scene acceptance thresholds, sensor-domain ratio scaling, exposure-input semantics, spatial mapping and initial history/recovery state. A matrix-derived locus does not determine these settings. Use the owned controller without importing IMX861 calibration or inventing unavailable spectral channels.
2. Restore Native1C capture-JSON/save-status behavior in the recovered app source, then connect a diagnostic automatic-neutral path with freshness/failure provenance. Preserve the original HAL neutral independently and prove coherent WB application once.
3. Build the signed experimental single-RAW APK with the existing app ID/signer, versionCode>27179 and JSON/DNG/JPEG behavior, then test device output and failure recovery. Validate photographic colour and the remaining HNCS renderer separately.

This checkpoint builds no APK and changes no renderer or installed application. It completes the phone-specific temperature submodel, not all phone calibration or full automatic initialization.

## Public provenance

- [Android CameraCharacteristics](https://developer.android.com/reference/android/hardware/camera2/CameraCharacteristics): original colour/calibration-transform roles and reference illuminants.
- [Adobe DNG SDK colour specification implementation, AOSP](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_color_spec.cpp), blob `57c8b252ff4fabf19af4cd2a0a177ec071e392cd`: endpoint products and reciprocal-temperature interpolation.
- [Adobe DNG SDK temperature table, AOSP](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/android14-prebuilt-test/source/dng_temperature.cpp), blob `47318abb306a231e04140ff57caee2d8a3b77b6c`: public Wyszecki/Stiles table variant and tint convention.
- [Colour implementation documentation](https://colour.readthedocs.io/en/v0.3.13/_modules/colour/temperature/cct.html): explicit alternative325-mired table entry. The implementation here pins the Adobe variant above.
