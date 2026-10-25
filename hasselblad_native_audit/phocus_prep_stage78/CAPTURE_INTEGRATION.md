# Normal-capture integration boundary after Stage78

The inspected source already forces development PHOTO capture to one RAW input
and disables bracketing, stacking, remosaic, binning and maximum-resolution modes
through `HasselbladDevelopmentPolicy`. This does not by itself select the new
renderer; `HdrxProcessor.ApplyHdrX` still saves RAW then runs Photon PostPipeline.

The key paths are under `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/`:

- `processing/SaverImplementation.getFrame`: records delivered dimensions,
  row/pixel strides, crop and timestamp; may create a digitally cropped buffer.
- `processing/processor/HdrxProcessor.start`: snapshots still metadata with
  `HasselbladCaptureEvidence.begin` before `Camera2ApiAutoFix.ApplyRes` modifies it.
- `HdrxProcessor.ApplyHdrX`: owns the uint16 sensor-count `output` after the
  single-frame selection, saves a DNG if requested, then normalises that buffer
  to fp16 before Photon PostPipeline. The new renderer needs the sensor-count
  input and its matching preparation metadata before this fp16 conversion.
- `hasselblad/HasselbladRawStream` and `HasselbladCaptureEvidence`: existing
  timestamp/request/surface/physical-camera provenance checks should supply
  capture identity. Do not infer it from a mutable current-camera setting.

The next implementation should extract a headless scene renderer from the
Stage78 Activity, returning an automatic-colour bitmap plus a small receipt.
UI controls, comparison previews and ZIP generation should be optional consumers.

For a first shutter integration, a completed private DNG staging file can bridge
to the exact decoder that has already been checked. It must use the same still
metadata and source pixel domain, honour RAW/JPEG output choices, handle cleanup,
and measure temporary encode/read costs. No Photon colour pass should be applied
after the new renderer's sRGB output. DNG staging is an implementation option,
not a reason to require a publicly saved RAW when the user selects JPEG only.

A direct in-memory RAW adapter can follow once its prepared Bayer values agree
with the DNG route for the same capture. It must account for actual row padding,
pixel stride, CFA phase, crop, white/black levels, lens-shading map coordinate
conventions and original still neutral/matrices. Camera2 shading data must not
be assumed numerically interchangeable with serialized DNG GainMap opcodes.

The first device test should compare a single shutter JPEG with rendering that
capture's saved DNG through Stage78, then check orientation, save modes, queue
ownership, cancellation and lens switching. The current crop32 contract remains;
larger RAW modes and alternative CFA layouts require their own adapters.

No capture/processing implementation is changed by Stage78. This document records
the concrete source boundary and next work, not a completed camera integration.
