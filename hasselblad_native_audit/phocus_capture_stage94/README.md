# Stage94: require Hasselblad rendering for photos

The new phone recording displays `Last saved photo: Curve 1`, which the Stage93 UI emits only for a `HASSELBLAD_SHUTTER_RENDERED` receipt. It does not show a Photon fallback for that reported capture. The remaining brightness/preview differences therefore cannot be attributed to a fallback from this recording alone. The user explicitly requires the Hasselblad renderer, without automatic Photon substitution.

The old integration returned false on a pre-publication error and allowed the ordinary processor to run Photon's RAW/colour pipeline. Stage94 removes that entire pipeline from the ordinary processor. It now calls only Hasselblad or reports a terminal rejection. The capture handler returns no fallback flag: missing metadata/profile, native rendering errors, encoding errors, cancellation and publication failures all report failure and release the input frames. Unsupported processed camera JPEG/YUV inputs are rejected; disabled multi-frame/video modes cannot enter the retained legacy processors. RAW-only remains an original sensor DNG without colour rendering.

A successful capture shows `Last saved photo: Hasselblad · Curve …`. A failed capture shows its reason and whether a RAW or JPEG was actually saved, including partial RAW+JPEG saves. This small status is retained in preferences even with diagnostics off, and identifies its build. Diagnostic comparisons, pixel samples and report JSON remain opt-in. Existing diagnostic reports from older builds are not presented as new captures.

Photon-derived camera acquisition, application UI and storage infrastructure remain in the codebase. They are not an alternate still renderer. This change does not replace the phone's live camera stream with a full RAW preview or change the established preview correction math.

## Validation

`python3 hasselblad_native_audit/phocus_capture_stage94/check94.py --work /tmp/hb94-tests`

The JVM harness compiles the actual production capture handler, processor router, JPEG/YUV rejection adapters, diagnostic preference and output-mode mapper. Android UI/storage primitives, native rendering and the unchanged DNG bridge are test doubles, with injected errors at each boundary. It exercises JPEG, RAW+JPEG, RAW-only, diagnostic on/off, missing metadata, invalid profiles, native-linkage errors, memory failure, encoding failures, partial publication, cancellation, callback errors, cleanup errors and a subsequent successful shot. It checks exactly one terminal callback, visible status, single publication, and frame/temporary-file cleanup. Native pixel kernels are not re-tested because they are pinned unchanged from Stage93.

`python3 hasselblad_native_audit/phocus_capture_stage94/pins94.py`

Pins prohibit unrelated changes and verify that no Photon rendering call remains in the ordinary processor. GitHub CI builds both ARM ABIs, checks 16 KB ELF load alignment, signing identity, version and source assets. These checks are not a phone test or proof of exact preview/output equality.

## Phone check

Install over Stage93, retain the imported profile and selected curve, and take a fresh Photo capture. Settings should identify Hasselblad and the new build in the last-capture status even with diagnostics off. If capture fails, its displayed reason is the next issue to fix; no Photon JPEG should be substituted. Compare a fresh saved photo with the live preview to assess the remaining preview difference.
