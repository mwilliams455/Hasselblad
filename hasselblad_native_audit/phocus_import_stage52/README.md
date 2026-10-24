# Stage52: native import defaults and upstream white balance

Stage52 closes the import-default question left by Stage51 and traces white
balance into the single-shot RAW graph. All tests use synthetic inputs. No
photograph supplies a fitted coefficient or a target colour.

## Findings

The original Android `configureImageCorrection` resets correction defaults and
selects tool version 4. With the supplied mode flag false (the tested SDR route),
the three shadow/highlight
endpoint pairs remain 0/16383. All five complete post-import gradation tables
match the Stage51 independent reconstruction exactly: 327,680 unsigned 16-bit
entries. Thus the small default RGB endpoint adjustment survives this import
path; import does not reveal an additional substantial default contrast curve.

Import derives temperature and tint from the source camera gains through the
original camera-specific conversion, then quantizes them. The Kelvin grid is
50 K from 2000 to 8000, 100 K to 10000, 1000 K to 20000, and 5000 K to 50000.
Tint uses steps of 1/3000 and clamps to +/-0.05 in the native internal units.
The native conversion and independent arithmetic agree in 171 synthetic cases,
including 57 groups tested at gain scales 0.125, 1 and 3.7. Temperature and tint
results are exact; prepared channel gains differ by at most 1.14e-13.
Four further synthetic cases verify both tint clamps.

The original complete `UpdateProcessParams` executes with a null RAW file and
image-description pointer, empty clarify map and explicitly disabled blue-corner
correction. In that bounded route, it converts the imported temperature/tint
back into the process gains. It copies the enabled exposure scalar and selects
model 0, source film 1, working space 0 and SDR tool 4. Twenty-four additional
cases verify the three metadata-presence gates: exposure uses 2^EV only when
present; the two integer adjustment fields otherwise reset to zero. These are
native raw-description fields, not a claim that arbitrary DNG tags map to them.

The original `AddSingleshotRawFilters` body executes in 24 explicit fixtures:
three illuminants, two tints, two source-gain scales and two exposure settings.
The recorded sequence is:

1. Orientation
2. Fast Bayer interpolation
3. Scalar highlight reconstruction
4. Conversion back to Bayer
5. Demosaicing

Highlight reconstruction receives process gains normalized by their maximum.
The subsequent demosaic constructor receives unity channel gains. Recorded
gain arguments match independent normalization exactly. This resolves the
upstream destination of WB gains in the tested branch; the colour shader's
unused `uGain` uniform is not evidence that WB is absent from this RAW graph.

## Highlight diagnostic

The original scalar highlight-reconstruction constructor and `Convert` body
also execute separately over a 9-cubed colour volume plus a 257-step equal-channel
ramp: 986 pixels for each of three deliberately synthetic gain ratios. A second
run scales each gain ratio by 3.7; output changes by at most 4.45e-16.

This is not merely a channel multiplier. With gains (1.8, 1, 1.4), for example,
the native conversion of equal-channel sensor white is neutral (1, 1, 1).
Simple maximum-normalized WB would yield (1, 0.5556, 0.7778). Across the three
test sets, maximum differences from that simple baseline are 0.4444 to 0.5455
in the **linear sensor domain**. Those are sensitivity differences, not errors
against a reference, displayed-image differences, or a measure of resemblance
to Hasselblad photography. Exposure and downstream colour/film stages are not
included in this diagnostic.

The native highlight method has not yet been independently reconstructed or
compared with its GPU implementation. Its difference from a simpler operation
identifies a concrete missing boundary to investigate, without inventing a
scene-dependent tone or colour adjustment.

## Evidence boundaries and fixtures

- Original code comes from the separately supplied private APK. Its bytes and
  the decoded calibration object/arrays remain unchanged. No input hashes,
  vendor shader source, recovered tables, camera matrices or photographs appear
  in the public receipt or source.
- The private profile cache supplies one already decoded CCD22/IR6 profile.
  Tests establish its arithmetic, not calibration across phone sensors.
- Native allocation guards and source/correction immutability checks remain
  enabled. Host allocation, libm, configuration, file-name availability and
  shared ownership are inherited fixtures. `exp2` uses host libm.
- The RAW graph explicitly enables `nonr`, disables lens, moire and green-green
  correction, supplies black standard deviation 1 and unit source scalar
  fields, and uses a 32x32 crop and 65535 truncation levels.
- `EmplaceFilter` records constructor arguments and returns empty shared
  pointers. Graph ownership is a fixture; the demosaic constructor executes,
  but its pixel body and the other spatial pixel filters do not. The separate
  scalar highlight diagnostic executes original pixel arithmetic.
- These are bounded host emulations, not live Android graph, RAW decoding,
  demosaicing or GPU tests. The app renderer and private profiles are unchanged;
  no APK is built.

## Reproduce

Use the Python dependencies from Stage51, keeping assertions enabled. This
audit does not create an EGL context or execute a shader.

```sh
python3 hasselblad_native_audit/phocus_import_stage52/audit_import52.py \
  --apk /private/original-phocus.apk \
  --safe-receipt /private/STAGE52_NATIVE_IMPORT_WB.json
```

Only the aggregate receipt is intended for public evidence.

## Rendering decision and next boundary

Keep the verified LUT/film core and the current phone renderer unchanged.
Independently reconstruct and validate the native highlight operation, including
its GPU route and its relationship to downstream exposure scaling. Establish
the phone sensor/input domain before integrating it. Applying the private
camera's temperature conversion or highlight math directly to an already
adapted phone RGB buffer would not be justified by this audit.

Any eventual change must pass neutral ramps, colour volumes, illuminant and
exposure tests, followed by matched references and held-out photographic scenes.
The tungsten-room photograph must not determine global tuning.
