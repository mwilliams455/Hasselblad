# HasselbladPhoton Stage 7 — labelled original-RAW neutral reference evaluation

**Research-only, read-only.** This reference tool does not choose a photographic neutral, apply white balance, or modify Bayer, Photon output, DNG, JPEG, Stage4 native code or X2D firmware routines. It sits *after* the completed 12.6 MP Stage6 Bayer2Float sampled CPU/GPU parity checkpoint. No private sensor profiles or real-camera samples belong in the public repository.

## Purpose and boundaries

- Strictly verify a user-provided DNG against its original `.capture.json` (SHA-256, byte count, single RAW, physical sensor/frame/timestamp, RGGB/crop/pixel mode and unchanged Photon neutral).
- Accept **human-labelled** original sensor-coordinate rectangles: `neutral_reference` (only where explicitly marked `measured_reference_card` and a single light condition), `nonneutral_holdout`, or `unlabelled_scene`.
- Extract four original RGGB Bayer-site values, remove original reported black levels and scale by white level. Independently retain original DNG/static-black and two **hypothetical** lens-shading bases; these do **not** prove RAW's HAL shading state or firmware AWB statistics.
- Report RGB-green-normalized neutral ratios and R/B gains, green-site agreement, usable-cell fractions, and comparator residuals against the **original HAL neutral** and only explicitly marked **uncalibrated** native Stage4 diagnostic candidates. These candidates are never truth targets or selected gains.
- Preserve `calibration_authorized=false`, `render_permitted=false`, `production_wb_unchanged=true`; no fitted radius, AWB confidence threshold, auto-selection policy, output JPEG changes, sensor constants, HNCS or gamma research is implied by this tool.
- Emit a **private** measurement JSON and a minimal **public-safe** status JSON. Do not commit either the user's real DNG/capture/photo, private annotation coordinates, actual ratio evidence or candidate measurements to the public repository.

## Offline prerequisites

Python 3.10+, `numpy`, `tifffile`, `Pillow` (the last only for optional JPEG-to-RAW rectangle mapping). No Android SDK or firmware binary is required for the offline verifier.

```sh
python stage7_labelled_roi.py --self-test
python stage7_jpeg_to_raw_roi.py --self-test
```

No private test photographs are embedded in the tests.

## Capturing usable reference data

A **known spectrally neutral photographic grey card**, not a pale wall or fur, should be clearly visible in a single-RAW 4:3 photo. Capture at least daylight and warm/artificial light conditions with the same card, one without the card or on visibly coloured materials as a false-positive holdout. Avoid saturation, strong shadows across the card, specular patches and uneven lighting. Keep original `.dng`, `.capture.json`, and JPEG (if marking from the JPEG). Record the illumination description and physical lens/mode; do not claim a measured Kelvin value unless independently measured. Repeat across lenses only when the initial sensor path has been controlled. The JSON annotation is a human source declaration, **not** scientific proof that a target or lamp is certified.

### Annotation format

Input `labels.json` (private):

```json
{
  "schema": "hasselblad-stage7-labelled-roi-v1",
  "binding": {
    "dng_sha256": "<from-original-capture-sidecar>",
    "physical_sensor_id": "<from-original-capture-sidecar>",
    "frame_number": "<from-original-capture-sidecar>",
    "sensor_timestamp_ns": "<from-original-capture-sidecar>"
  },
  "regions": [
    {
      "id": "certified_matte_gray_card",
      "role": "neutral_reference",
      "source": "measured_reference_card",
      "reference_target_id": "matte_gray_card_A",
      "illuminant": "daylight",
      "rect_raw_xywh": [1000, 700, 320, 256]
    },
    {
      "id": "coloured_holdout",
      "role": "nonneutral_holdout",
      "source": "human_visual_annotation",
      "illuminant": "unknown",
      "rect_raw_xywh": [1600, 1100, 320, 256]
    }
  ]
}
```

Replace the illustrative coordinates and every binding field; a mismatched hash/frame or too-small/unaligned/out-of-range ROI **fails closed**.

```sh
python stage7_labelled_roi.py \
  --dng original.dng --capture original.capture.json \
  --annotations labels.json \
  --private-report private-stage7-result.json \
  --public-report public-stage7-audit.json
```

### Converting upright JPEG rectangles (orientation 6 only)

A separate optional mapper supports a full-frame, uncropped DNG with TIFF Orientation=`6` and JPEG with the same 90° clockwise rotated aspect ratio. It cannot prove exact JPEG/DNG pixel alignment after ISP geometric or lens corrections. Use the JPEG's **actual pixel dimensions**, not a chat thumbnail size.

`jpeg_regions.json` (private):

```json
{
  "schema": "hasselblad-stage7-jpeg-region-spec-v1",
  "regions": [{
    "id": "reference_card_daylight",
    "role": "neutral_reference",
    "source": "measured_reference_card",
    "reference_target_id": "matte_gray_card_A",
    "illuminant": "daylight",
    "rect_jpeg_xywh": [200, 100, 150, 120]
  }]
}
```

```sh
python stage7_jpeg_to_raw_roi.py \
  --dng original.dng --jpeg saved-preview.jpg \
  --capture original.capture.json --spec jpeg_regions.json \
  --output bound-labels.json
```

## Exit criteria for choosing a new phone WB

A region's near match to a Stage4 temperature/tint candidate **does not authorize selection**, even if its green-site split is tiny. Stage7 will require independently grounded reference targets under multiple lights, explicitly coloured holdouts, supported provenance and mode/lens breakdown, shading-basis resolution, exposure robustness and failure/abstention conditions before a future development-only Hasselblad WB A/B can be enabled. White balance and HNCS CCM/tone/LUT remain separate stages.

## Stage 7B: cross-capture evidence (new)

After obtaining individually verified private Stage7 ROI reports, run the
`stage7_cross_capture.py` aggregator. Each **neutral reference** ROI must now
carry a user-declared stable `reference_target_id` (e.g. the same physical grey
card under two lighting conditions). The ID is a study label, not proof the card
has been spectrally characterized. Holdout and unlabelled ROIs must not carry a
card ID. The ROI evaluator binds an opaque SHA-256 of the physical camera's
calibration matrices/metadata plus exposure time and ISO to each private report.
The SHA is only a consistency test, not an individual camera identification
that should be published.

Create a **private** study manifest alongside the private report files:

```json
{
  "schema": "hasselblad-stage7b-study-manifest-v1",
  "reports": [
    { "id": "daylight_01",
      "path": "daylight_01.private.json",
      "binding": {
        "dng_sha256": "<exact DNG hash from original capture>",
        "physical_sensor_id": "<physical camera>",
        "frame_number": "<frame number>",
        "sensor_timestamp_ns": "<sensor timestamp>"
      }
    }
  ]
}
```

`id` values must be unique. Paths must be relative to the manifest directory,
inside that directory, without `..` traversal. Repeat for all reference and
holdout captures; reuse the **same reference_target_id** only for shots of the
same physical card, and independently label `daylight` or `warm_artificial` in
each ROI. The study analysis never edits images and cannot infer Kelvin or
spectral neutrality from these self-reported labels.

```sh
python stage7_labelled_roi.py --self-test
python stage7_jpeg_to_raw_roi.py --self-test
python stage7_cross_capture.py --self-test
python stage7_cross_capture.py \
  --manifest PRIVATE_study_manifest.json \
  --private-report PRIVATE_study_result.json \
  --public-report PUBLIC_study_audit.json
```

The tool never pools different camera-profile hashes, physical cameras, Bayer
geometries or reported RAW-binning states; it never pools different reference
cards. Repeated ROIs from a single photograph are collapsed into **one frame**
when computing within-light repeatability. All lens-shading hypotheses remain
separate. It calculates descriptive medians, median absolute deviations in
R/G and B/G log2 stops and HAL/Stage4 residuals, plus coloured-holdout ratio
collisions. The default `0.125` stop holdout collision radius is **research
only**, not a validated acceptance threshold.

The *minimum exploratory coverage* marker requires two independent captures
of **the same card** under daylight and two under warm artificial lighting,
plus a coloured holdout for that camera profile. This is a completeness
checkpoint only: it never establishes light temperature, true spectral
neutrality, a firmware controller, a calibrated AWB policy, HNCS or permission
to change a photographic white point. No original RAW/JPEG or private study
report belongs in this public repository.
