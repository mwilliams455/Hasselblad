# Phone RAW input adapter — 21 October 2026

**Latest addition:** [Phone temperature calibration workspace](TEMPERATURE_MODEL.md) now initializes the owned gain/CT/tint routines from original Camera2 matrices and a pinned public isotemperature table. It passes4,131 matrix-oracle comparisons,4,059 gain/inverse round trips and six exact host/sanitizer/ARM64 comparisons. This completes the temperature submodel; full automatic scene/exposure/spatial initialization remains open. The RAW results below are unchanged.

The owned phone adapter now derives a 32×32 Bayer-block grid from untouched single-frame RAW16 samples. It runs against the saved Native1C phone capture and on Android API28 ARM64 under QEMU, with identical outputs to the optimized host implementation. It does **not** yet initialize or call the automatic estimator: a phone-specific estimator profile and calibration mapping remain required.

## What is implemented

`hb_phone_raw_build` reuses the retained `awb_rebuild_04_20261021` RAW statistics accumulator. That accumulator's signed Q16 sums and sample counts remain exact. The new layer normalizes each Bayer site's mean by its own `(white - black)` span, preserves negative values and highlight headroom, and calculates finite positive green/red and green/blue ratios in Q12. A separate flag marks nonpositive, saturated or out-of-range blocks; unusable ratios are zero. The signed sums/means are retained even for rejected blocks. All four Bayer layouts, padded rows/pixels and aligned crops are supported within the existing 32MP bound. A block is rejected conservatively if any sample reaches white; this is an explicit phone policy, not a recovered vendor quality rule.

The mean brightness is the arithmetic Bayer mean, not CIE Y or the original exposure-input scale. The adapter does not infer exposure values, fabricate spectral channels, transplant sensor calibration, apply WB, demosaic, apply lens shading or clip photographic pixels. It does not serialize E2 records. The caller must supply the declared untouched RAW16 buffer; a flag cannot independently prove processing history. Output is unchanged on rejected calls. Input/output buffers must not overlap.

`capture_binding.py` checks single-frame identity, RAW format/copy layout, physical-camera provenance, paired timestamps and frame number, explicit black-level source, Bayer phase, original matrix presence and DNG identity. It supports this captured full-copy/uncompressed layout; unknown crops, logical-camera routing without explicit physical binding, non-Bayer modes and maximum-resolution mapping reject. The native accumulator's crop/stride support is wider than this deliberately bounded offline DNG reader. Original camera metadata are retained separately from derived processing fields. DNG OpcodeList2 remains metadata and is not applied.

Choose `exported`, `dynamic` or `static` black levels explicitly. The recorded capture exported64 but reports dynamic63.9375; both were exercised independently. None is silently substituted. Camera2 describes per-frame dynamic black/white levels separately from static characteristics; Bayer arrangement describes the sensor's top-left2×2 reading order. Sources: [CaptureResult](https://developer.android.com/reference/android/hardware/camera2/CaptureResult), [CameraCharacteristics](https://developer.android.com/reference/android/hardware/camera2/CameraCharacteristics).

## Fresh verification

- **32 synthetic frames**, covering all four CFA patterns, per-site/fractional black, padded/non-square layouts, nonuniform block partitions, aligned crops, negative values, saturated samples and extreme ratios.
- **Three interpretations of the real 4096×3072 capture**, using exported, dynamic and static black levels. Each accounts for all **12,582,912 samples** and yields1,024 ratio-valid blocks. A valid ratio is not an estimated scene neutral.
- **35,840 independent block comparisons** against a NumPy slicing oracle. Exact raw sums/counts/extrema/flags/ratios and normalized means match; arithmetic brightness is compared with a small floating-point tolerance because Python's compensated sum differs from C's ordered sum.
- **21 native rejection cases**, with complete output non-mutation, and **19 metadata/identity rejection cases**. Original input bytes and metadata remain unchanged.
- **Six exact 139,296-byte cross-runtime comparisons**: exported/dynamic real capture plus a padded cropped BGGR fixture through ASan/UBSan and Android ARM64. No mismatches. LeakSanitizer is disabled because this executor denies `/proc` task inspection; address/undefined checks remain enabled and fatal.

The first verification attempts exposed an oracle summation-order assumption and a test case that described a valid crop; those tests were corrected. LeakSanitizer's executor restriction was then recorded explicitly. The final report is from the exact final source. No numeric implementation correction was needed. Timings in the report include the Python oracle and are not phone performance measurements.

## Reproduce

Use Python with NumPy/Pillow, host `cc`, NDKr27 and the existing API28 Bionic/QEMU runtime:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 hasselblad_native_audit/phone_input_20261021/verify_phone_raw.py \
  --capture /private/IMG_20261020_062344.capture.json \
  --dng /private/IMG_20261020_062344.dng \
  --out /private/phone-raw-check --report /private/phone-raw-result.json \
  --ndk /tools/android-ndk-r27 --qemu /tools/qemu-aarch64-static \
  --firmware-root /private/extracted
```

The native adapter/probe does not load `libaaa.so`; the Android replay uses only the restored Bionic runtime. Its C dependencies are the retained RAW accumulator and stage-helper source. The standalone TIFF reader is reused from `hasselblad_device_validation_20261019/raw_audit/audit_dng.py`. Source, input and binary hashes are in `PHONE_RAW_RESULT.json`. Derived grids, original metadata, executable probes and logs are private in `Hasselblad_Phone_RAW_Adapter_Evidence_PRIVATE_20261021.zip`. The original capture remains `hasselblad.zip`, Library `libfile_20a4cdf4b5b8819198e741fda306316b`, SHA256 `a6a7f61d3bff33d43ebdf497673a40e2ae9328776315bb5e3f2b30b9253ddcfc`.

## Next boundary

The [temperature submodel](TEMPERATURE_MODEL.md) is now constructed from original Camera2 matrices. Complete the remaining phone-specific automatic initialization/profile: scene acceptance, exposure scale, spatial mapping and history/recovery defaults. Those are not determined by the matrix-derived locus. Define their mappings explicitly before feeding these ratios into the estimator. The metadata bridge already preserves matrix/WB ownership; retain original HAL neutral separately from any selected neutral and apply WB once. Missing auxiliary spectral measurements stay unavailable.

Then restore Native1C capture-JSON/save-status behavior in the recovered app source and connect the bounded path for a useful test APK. The current source is still Native1A-era app plumbing; do not deliver it as an upgrade. Preserve application ID/signing, versionCode>27179, JSON/DNG/JPEG and the single-RAW/no-stacking policy. This checkpoint changes no photographic rendering, builds no APK and leaves main/installed Native1C unchanged.
