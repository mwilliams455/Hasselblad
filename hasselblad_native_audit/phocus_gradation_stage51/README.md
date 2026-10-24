# Stage51: native default post-film gradation

Stage50 identified a separate gradation filter after the film curve. Stage51
executes the original default-setting, curve-generation, CPU pixel and GPU
parameter bodies, then runs the unmodified private gradation fragment shader.
The tests use synthetic inputs; no photograph is used to choose parameters.

## Findings

The native `CImageCorrection` constructor selects SDR tool code 2, working space
0 and film request 4. Stage45 established that film request 4 inherits the source
film; it does not establish which film an actual import supplies.

Default contrast and luminance-user tables are identity at every one of their
131,072 entries. The luminance curve has two control points, so its separate
pixel adjustment is inactive. The three RGB tables are equal and slightly
non-identity. Their endpoint is 65,282, and their largest difference from identity
is 253 out of 65,535. They are monotonic.

The independent reconstruction exactly matches all 196,608 RGB table entries.
This traces to default highlight value 16,383 divided by the native 14-bit
endpoint normalization of 255 × 64, including float intermediates and integer
table indexing. It is a small common-channel endpoint adjustment, not evidence
for a substantial missing contrast curve or a selective colour correction.

A second complete native construction changes working space to 1, temperature
to 6500, tint to 0.003 and film request to 1. All five tables remain byte-exact.
This is a bounded invariance check; it is not a multi-camera calibration claim.

The original CPU pixel body is checked with both version flags over a 17³ RGB
cube plus 513 neutrals (5,426 pixels). Version 0 matches the independent mapping
exactly; version 1 includes native hue recovery and differs by at most one
**16-bit** code. Original GPU table preparation is also checked exactly, including
all 786,432 float values in its three RGBA textures. The original shader is
tested with both version flags and explicit nearest/linear sampler fixtures on
software GLES. See the aggregate receipt for the measured consumer errors and
the synthetic sRGB sensitivity of including the default stage.

## Evidence boundaries

- `CImageCorrection`, `CCalculatedCurves`, `CGradationFilter` and their colour
  arithmetic execute from the hash-pinned owner-supplied APK.
- Host allocation, standard library/math helpers, shared ownership, file-name
  service availability and two logging configuration queries are fixtures.
  All native allocations and bounded objects have checked memory guards.
- CPU in-place buffer ownership is a fixture. The native pixel-address method,
  curve lookup, contrast handling and hue-recovery arithmetic execute.
- The GPU handler, task and texture ownership are recording fixtures. Original
  `CreateCurve` fills the uploaded data; the upload service is intercepted.
  Pixel textures use RGBA16F; curve textures use RGBA32F.
- The final GLES run uses explicit sampler fixtures. Live Android sampler state,
  import-time overrides, phone GPU execution, RAW preparation and final Android
  presentation are not established by this audit.
- No vendor shaders, recovered tables, camera calibration, input hashes or
  photographs are committed or included in the aggregate receipt.

## Reproduce

Use the Python dependencies from Stage49 plus the EGL/GLES libraries required
by Stage50. Assertions must remain enabled.

```sh
python3 hasselblad_native_audit/phocus_gradation_stage51/audit_gradation51.py \
  --apk /private/original-phocus.apk \
  --safe-receipt /private/STAGE51_DEFAULT_GRADATION.json
```

Only the aggregate receipt is intended for public evidence. The independent
`default_curve()` function is limited to the tested unedited SDR defaults; it
does not implement arbitrary user curves or HDR gradation.

## Rendering decision and next boundary

The app renderer is unchanged. This audit records a precise small missing stage
for a future faithful integration. Before applying constructor defaults to all
imports, establish whether the RAW/import setup replaces the endpoint settings.

The next investigation should trace that import setup alongside phone input
adaptation: normalization and gain ownership, the camera-to-colourimetric
mapping, and the representation expected by the verified native core. Evaluate
changes using neutral ramps, colour volumes and controlled illuminant/exposure
cases. Photographic validation should use matched references and held-out scenes.
The tungsten-room photograph must not determine global tuning parameters.
