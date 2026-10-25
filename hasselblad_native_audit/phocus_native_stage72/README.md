# Stage72 — independently executed scalar pixel-loop parity against Phocus CPU

**Result (25 October 2026): 32 exact original-versus-fully-substituted CPU graph comparisons, 187,224 linear RGB16 output values, maximum difference zero.** This is the first bounded checkpoint where the original `CGradientInterpolate::InterpolateRGB` **and** `ColorNoise` function bodies are skipped in the substituted graph and their pixel work comes from independent C code.

This is **not** a complete original DNG importer, general full-frame demosaic, Android renderer, or physical camera colour match. Normal Hasselblad Photon capture remains unchanged on Stage58, version `0.1-hb-rawprep58` / 27197. No new APK was built.

## What actually ran

The private ARM64 runner `audit_independent72.py` creates the original graph from the locally supplied Phocus APK, obtains the graph's RAW pointer, frame size, stride, flags and constructor-owned thresholds, then runs each test *twice*:

1. The untouched original `InterpolateRGB` and original `ColorNoise` execute normally, producing the original reference RGB16 output.
2. The original `InterpolateRGB` entry is intercepted before any of its body executes. The independent Stage69 C implementation builds red, green, blue and direction-mask planes directly from a fresh copy of the RAW input and newly allocated independent scratch buffers. Those four independently computed planes replace the guest work planes. Original `ColorNoise` is likewise skipped by the existing Stage71 hook and replaced with the corrected independent Stage65 C implementation containing the independent Stage64 directional YCC core. The surrounding original CPU graph still handles object allocation, accessor/crop and output routing. Its returned RGB16 image is compared byte-for-byte with the untouched original reference.

The original reference output is **never** provided as an input to the independent C calculations. Source RAW and private inputs are checked for immutability. The harness also checks that `InterpolateRGB` and `ColorNoise` are absent from the recorded list of original function bodies executed during replacement.

The independent C sources from the existing checkpoint chain are reused unmodified: Stage61 maps/filters/direction masks, Stage62 missing-red/blue helpers, Stage63 green estimator, Stage67/68 inline RAW gradients, Stage66 scheduler/plane wiring, Stage69 composition and the corrected Stage64/65 YCC/colour-noise path. This checkpoint adds the original-CPU *full-loop replacement bridge* and direct final RGB16 parity, rather than fitting photographic appearance or redefining the helpers.

## Original CPU evidence

| Fixture family | Reference/substituted pairs | Exact final RGB16 values | Maximum difference |
| --- | ---: | ---: | ---: |
| Eight synthetic patterns (including two rectangles) | 16 | 153,432 | 0 |
| Four fixed interior DNG tiles | 8 | 24,576 | 0 |
| Four additional interior DNG regions | 8 | 9,216 | 0 |
| **Total** | **32** | **187,224** | **0** |

Each fixture is checked with highlights bypassed and with the previously validated bounded Bayer/highlight/Bayer chain. Additional DNG regions come from the **same** retained photograph, not a separate camera reference or scene. Output values are **linear RGB16 before** the main colour LUT, film/gradation, sRGB finishing and display. No image pixels or private calibration/profile contents appear in the source or public evidence.

Supplemental independent intermediate-plane comparisons on all six classic synthetic patterns matched every R, G, B and direction-mask value inside a margin of eight pixels, amounting to 225,792 RGB16 plane codes and 75,264 packed mask codes. Some native direction-mask sites *outside* that interior retain allocator state and do not match the C zero-initialized scratch; the full working-frame buffers are therefore **not** claimed bit-exact. All final cropped RGB16 images in the declared contract are exact.

## Supported original graph contract

- Aligned RGGB CFA in the audited scalar, non-optimized dispatch.
- `flags = 0xFFFF`, additional noise strength zero, native stride **1024 `uint16_t` elements**.
- Original scale threshold **1.0**, signed edge/raw gradient threshold floors **32/200**, read from the native object (never scene-fitted).
- Explicitly checked native internal **(width, height)** pairs: `(128,128)`, `(96,96)`, `(88,80)` and `(104,88)`.
- The synthetic output rectangle **34×18** provides a bounded original-graph alignment witness: native internal work becomes **104×88**. This observation does not determine the general alignment scheduler, arbitrary offsets, CFA phase or full-frame edge policy.
- The C path owns its own input snapshots and scratch/output planes, and it rejects unsupported configuration and native pointer overlap. The original wrapper still owns allocations, alignment selection, crop, exit/error status and output storage.

This is the native program's own work-domain contract, not a claim that any phone's 12-MP DNG uses the same stride, CFA or input normalization. The source DNG bridge still applies Stage58 common-range normalization and GainMap upper clamps **before** quantizing to Bayer; the Stage58 phone preview originally quantizes after float bilinear interpolation. Do not conflate native tile parity with actual Android buffer parity.

## Reproduction (private host only)

Use the locally supplied original APK and existing retained DNG; do **not** upload proprietary binaries, decoded vendor code, LUTs, calibration matrices, RAW pixels or private file hashes to GitHub or CI.

```sh
PYTHONPATH=/private/offline-emulator-deps python /private/run_private_audit70.py \
  hasselblad_native_audit/phocus_native_stage72/audit_independent72.py \
  --apk /private/original-phocus.apk --dng /private/retained.dng \
  --fixture all --mode both --sanitize \
  --work /private/stage72-work --safe-receipt /private/stage72-native.json
```

`--fixture` may select any synthetic pattern, `dng1`–`dng4`, `held1`–`held4` or `all`. `--mode` accepts `bypass`, `highlight` or `both`. Python assertions must remain enabled. The private execution requires the existing native audit modules, NumPy, tifffile, GCC, Unicorn, Capstone and pyelftools. Local checks also ran the original-CPU bridge with UndefinedBehaviorSanitizer on a neutral scene and two fixed-DNG comparisons.

The public GitHub Actions workflow only syntax-checks the new runner and compiles/tests the canonical independent C components on synthetic data with ASan/UBSan. The **private original CPU** is never executed in GitHub Actions. Consult the actual workflow status rather than assuming CI passed.

## Remaining boundaries — Stage73

1. The original **outer** `GGDirInterpolator`/filter wrapper still runs for graph creation, alignment, edge/crop decisions, output storage and metadata routing. Replace or independently validate those operations for arbitrary dimensions, stride and CFA phase; do not generalize from 128/96/88/104 widths.
2. Build portable JNI/Android support for the *saved-DNG experiment only*, export real phone RGB16 pixel buffers and compare them with host reference output. Avoid overwriting the original phone DNG or changing the stable normal Photon capture route. No new APK is warranted until host/JNI buffer and error-contract validation passes.
3. Finish original DNG import and OpcodeList2 GainMap ordering/clamp contract, sensor-specific colour-basis adaptation and white-balance ownership. Exact interpolation for supplied uint16 Bayer codes does **not** establish cross-sensor Hasselblad colour fidelity.
4. Check highlight input-domain semantics, native sharpening, CPU sRGB finishing, GPU P3/compositor/live-preview consistency and device performance/cancellation on approximately 12 MP single frames. Obtain multiple physical reference scenes before making photographic-colour accuracy claims. Positive noise-strength and optimized/GPU branches are not supported by this checkpoint.

**Result scope:** independently executed original-equivalent **bounded scalar demosaic/colour-noise pixel calculations**, with original surrounding wrapper retained; *not* complete Phocus firmware equivalence or Android rendering parity.
