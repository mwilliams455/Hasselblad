# HasselbladPhoton — firmware-first, reusable camera engine
**Decision checkpoint:** 2026-10-22  
**Status:** engineering roadmap, not a completed renderer or autofocus feature  
**Branch:** `recovery/awb-rebuild-20261021`. Do not change `main` or the Stage8 phone baseline without validation.

## Primary priority: reproduce original photographic colour, not only the look

1. **Original X2D II source behaviour is authoritative where it can be demonstrated.** Target the saved-photo MAIN_CCM, MAIN_GAMMA and MAIN_3DLUT chain and white-balance-dependent parameter preparation. Preserve firmware hashes, matched native tests, fixed-point arithmetic, input and output ranges, and stage ordering.
2. **Resolve the actual ISP per-pixel contracts.** Unsolved: six-coefficient CCM meaning/scale/channel choice; MAIN gamma evaluation/dithering/negative input; photographic LUT channel/bank mapping, input shaper, sampling, rounding and clipping. The Stage21 planar sampler is a tested *candidate*, not ISP parity. Stage22's tentative channel label `210` was inconclusive and must **not** be promoted to a hardware mapping.
3. **Port verified math into a portable software ISP.** Reuse Stage8 profile preparation, Stage14 bounded composition, Stage18 phone-camera-to-XYZ D50 and Stage19 output-colour conversions. XYZ is a portable colourimetric adapter, not evidence that the X2D's private working space is XYZ. Preserve headroom until a proven output transfer/tone stage.
4. **Characterize each physical phone sensor and RAW mode.** Original X2D II sensor calibration is not phone calibration. Stage7 neutral-reference WB remains abstaining until controlled calibration supports it. Support DNG matrices, lens shading, physical lens IDs, ≈12MP RAW and high-resolution modes independently. Unsupported modes fall back to Photon.
5. **Use real measurements as validation and fallback.** Stage23 measured one genuine same-frame X2D II ColorChecker RAW/JPEG pair; its LibRaw baseline is not the original ISP and there is no matching default Phocus TIFF or diverse lighting set yet. Measure any fitted approximation separately from original-code parity.
6. **Only then release an opt-in experimental photographic APK.** Preserve original DNG and existing Photon JPEG baseline; prove a saved render and preview parity, highlight headroom, gamut/ICC, performance, lens-switch stability, and graceful fallback. Stage8 build 27186 is the phone-tested baseline. Do not label synthetic-only code as faithful Hasselblad colour.

Keep **Hasselblad colour rendering**, **Film Tone / post-processing**, and **optional HNCS HDR gain-map output** distinct. Do not silently enable exposure stacking. Mark each operation in source and diagnostics as `original_equivalent`, `research_candidate`, `empirical_approximation`, or `fallback`.

## Parallel workstream: subject / face autofocus

**Original camera capability:** The X2D II 100C documents AF-C tracking of people, cats, dogs and vehicles; its XCD system uses 425 PDAF zones and LiDAR-assisted focusing. Sources:
- https://www.hasselblad.com/x-system/x2d-ii-100c/
- https://www.hasselblad.com/x-system/x2d-ii-100c-faq/

**Do not conflate different "face" functions.** The project's `awb_original_runtime_20261021/hb_face.c` reconstructs face-assisted *automatic white-balance statistics*, not a face-detector neural network or focus controller.

1. Inventory Camera2 capabilities **for each physical phone camera**: `CONTROL_AF_AVAILABLE_MODES`, `CONTROL_MAX_REGIONS_AF`, `STATISTICS_INFO_AVAILABLE_FACE_DETECT_MODES`, `STATISTICS_INFO_MAX_FACE_COUNT`, minimum focus distance, zoom/crop and distortion modes. No assumption that Xiaomi 15 Ultra characteristics apply to other devices.
2. If supported, consume `CaptureResult.STATISTICS_FACES`. If absent/unreliable, consider a separately validated, licensed **on-device** face/subject detector. People/face first; animals/vehicles and eye landmarks only if independently supported. Never upload viewfinder frames to an external inference service.
3. Build a reusable *observation → subject selection → temporal tracking → Camera2 AF-region controller*, with subject ID continuity, hysteresis, confidence/timeout, measured latency, lost-target fallback and correct sensor-array↔viewfinder mapping under orientation, mirroring, distortion, zoom and physical lens switches.
4. Route control to the phone HAL's PDAF/CDAF/AF-C, **not to Hasselblad's LiDAR or XCD lens motors**. The existing Photon `control/TouchFocus.java` already handles AF regions, focus state and tap-trigger sequencing, but it sometimes switches continuous-mode touch focus to AUTO to handle strict HALs. Do **not** repeat its CANCEL→START sequence for each subject-tracking frame; use throttled region updates and independent state transitions. Respect manual focus, tap priority, AE-L, burst/RAW capture, video modes and unsupported/fixed-focus hardware.
5. Validate stationary and moving people, multiple subjects, disappear/reappear, low light, zoom/lens switching, AF convergence, false positives and capability-zero devices before surfacing the experimental mode. Any proprietary model or algorithm taken from firmware requires separate original-provenance and compatibility evidence; do not claim it is already ported.

Android Camera2 references:
- https://developer.android.com/reference/android/hardware/camera2/CaptureRequest#CONTROL_AF_REGIONS
- https://developer.android.com/reference/android/hardware/camera2/CaptureRequest#STATISTICS_FACE_DETECT_MODE
- https://developer.android.com/reference/android/hardware/camera2/CaptureResult#STATISTICS_FACES

## Reusable engine for Hasselblad, Leica M9 and Monochrome

| Module | Responsibilities | Reuse policy |
|---|---|---|
| `CameraDeviceAdapter` | Camera2 capabilities, RAW/preview stream, physical ID, crop/orientation, AF/AE requests and feedback | Shared with per-device adapters |
| `SubjectEngine` / `FocusController` | Detection, target selection, temporal tracking, AF regions, lock and fallback | Shared once validated on phones |
| `MeteringExposureController` | Exposure geometry, optional subject weighting, preview/capture state | Shared math/control where compatible |
| `SensorColourAdapter` | Per-sensor RAW levels, neutral, shading, DNG matrix to PCS | Shared plumbing; separate calibrations |
| `PhotoColourPipeline` | Original-equivalent colour processing + mode-specific output | **Never share Hasselblad LUTs with Leica by default** |
| `EvidenceHarness` | Native math oracles, private matched photos, public aggregate reports, device regression tests | Shared |

Future Leica M9/Monochrome implementations may adopt stable focus/tracking and capture reliability improvements, **while retaining distinct Leica colour/monochrome rendering and their intentional manual-focus-style controls**. An AF feature added to an M9-look app is an app capability, not a claim that the actual historical Leica M9 had that autofocus system.

## Sequencing and release gates

1. **Firmware-equivalent colour remains the critical path:** MAIN ISP pixel domain + CCM/gamma/LUT, cross-checked against real X2D II photographs and eventual default Phocus TIFF references.
2. **AF foundation in parallel:** a capability-reporting and subject-tracker host test can proceed without destabilizing the saved renderer.
3. **Next colour test APK:** signed upgrade with versionCode above 27186, opt-in experimental path, unchanged DNG, existing Photon mode, reproducible sidecar and measured preview/still parity. Do not issue before usable real pixel rendering exists.
4. **Experimental subject-AF integration** after Camera2 capability evidence and temporal tracking tests; never let detection overrun the repeating capture request or override AF locks.
5. **Cross-project port** only after the shared controller passes Hasselblad tests on more than one physical phone camera and robust unsupported-device fallback is verified.

## Proof boundary

A routine is *firmware-equivalent* only when matched against a known original operation on a specified input domain. Even bit-exact colour operators **cannot guarantee identical results on every phone** without calibrating sensor spectral response, WB, lens data, working-space conversion and subsequent tone/output processing. Proprietary X2D II PDAF/LiDAR hardware or model weights are not directly reusable on generic Android devices. Reproduce supported **observable behaviour** using the available HAL, and label unknowns honestly.

Do not publish extracted Hasselblad firmware binaries, tuning values/3D LUT arrays, machine-learning weights, private phone DNGs, user faces or private calibration files on public GitHub.
