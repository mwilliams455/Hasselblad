# Stage78: exact cached RAW preparation

Stage77 passed the actual phone comparison: the full JPEG, all three previews
and all six exported Bayer/RGB16 sample files were byte-identical to Stage76.
Three RGB16 windows (36,864 codes) also matched the unchanged Stage74 host.
Total before ZIP packaging fell from 21.832s to 9.063s; demosaic 12.042s to
2.880s, colour/bitmap 5.252s to 1.460s. This is one run per version, not a
multi-device benchmark. Preparation/calibration remained 3.371s and became
the largest individual stage.

## Implementation

`readPrepared78` adds an independent fast path alongside the unchanged
Stage75/76 reference methods in `HasselbladDngTileReader`. It accepts exactly
the same strict uncompressed RGGB16 DNG subset and keeps the same validation.

- Cache float32 normalisation for each raw code and CFA black level, using
  the same float64 subtraction/division followed by float32 clamp.
- Cache each gain-map horizontal coordinate; compute vertical coordinates
  once per map/row. Keep the original four-term float64 interpolation order.
- Select applicable maps per row and CFA phase, preserving opcode order,
  rectangle boundaries, per-opcode clipping and float32 stores.
- Read up to 32 rows at once, stopping at strip boundaries and preserving gaps
  and both TIFF byte orders. Decode directly from the bounded byte buffer.
- Retain interruption checks, original read-only source handling, all sample
  counters, the same metadata and final Bayer uint16 quantisation.

Cache memory is bounded by the existing 8192 dimension/64-map limits. Common
four-map input needs approximately 1MB normalisation tables plus axis caches;
equal black levels share a table. No full floating-point RAW frame is created.

The Stage78 screen uses the unchanged Stage77 native demosaic and colour path.
Before rendering it compares 49,152 actual prepared Bayer sites in three regions
against the original Stage75 preparation. This is automatic, not a repeated
manual demosaic test. Exported RGB16 sample windows now straddle a 256-pixel
block boundary; their locations differ from Stage77, so compare each to its
exported Bayer input rather than comparing old/new sample files directly.
The full JPEG and preview images are expected to remain byte-identical for
the same DNG, profile and build environment.

## Validation

- 3,205,134 exact Bayer sites across reference and new fixtures: both byte
orders, padded/multiple strips, odd shapes, single/four fractional black levels,
absent/overlapping/partial/64 gain maps, degenerate grids, coordinate clamps,
very small positive map spacing and intermediate clipping.
- All 12,582,912 Bayer sites in a 4096x3072 fixture match Stage76 exactly.
- Clipping/application counters, source immutability, malformed-input rejection
and cancellation checks pass; existing reader methods are preserved byte for byte.
- Initial local host total: 444.804ms old versus 142.243ms new, about 3.13x. Host
timing is not a phone prediction. CI records its own measurement.

Install `HasselbladPhoton-0.1-hb-prep78-27218.apk` over Stage77. Open
**Saved DNG colour → Stage78 · faster RAW preparation and colour**, select the
same DNG and imported profile, and export `Hasselblad_Stage78_Scene_Comparison.zip`.
The report separates cache planning, row reads, pixel preparation and the
small real-input reference check. Existing Stage76/77 screens remain available.

```bash
python3 hasselblad_native_audit/phocus_prep_stage78/check78.py --work /tmp/hb78 --jni "$JAVA_HOME/include"
python3 hasselblad_native_audit/phocus_prep_stage78/compare78.py /private/scene.zip
```

Normal capture remains Photon in this build. The next integration boundary is
documented in `CAPTURE_INTEGRATION.md`. No physical Hasselblad sensor colour
match or vendor outer-border equivalence is asserted. Keep private photos,
samples, profiles, calibration and identifying metadata off public GitHub.
