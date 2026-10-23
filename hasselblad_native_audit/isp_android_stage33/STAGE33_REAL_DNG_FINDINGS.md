# Stage33 — first actual Stage32 DNG / original capture sidecar pair verified

**Date:** 23 October 2026 (UK). **Outcome:** `PASS_RECORDED_DNG_PHYSICAL_FRAME_BINDING`.

The user supplied a new real-file Stage32 on-device report (versionCode 27188) and the corresponding original `.capture.json` saved by the camera app (capture versionCode 27187). A private local cross-check evaluated **19/19 predicates** successfully. **Neither original user file nor original DNG hash, bytes, sensor ID, timestamp, numerical colours, calibration data or filename is committed.** See `STAGE33_REAL_DNG_DEVICE_PASS_20261023.json` for the redacted summary.

## Verified matching records

- The independently opened DNG hash and exact byte size in Stage32 match the `dng.sha256` and `dng.bytes` recorded by `HasselbladCaptureEvidence.finishRawSave`.
- `input_frame_count=1`, original capture evidence usable, no missing required Camera2 calibration fields or recorded unusable reasons, RAW ImageReader request target matched and the selected physical camera result matched the frame.
- Logical/selected frame numbers, original sensor timestamp and delivered RAW timestamp agree.
- Original RAW_SENSOR buffer (format 32) matches DNG 4096×3072 uncropped/unbinned **software copy**, RGGB, 16-bit stride and sufficient input capacity. The Camera2 `rawBinningFactorUsed` sensor-mode flag is separately reported as true; do not conflate that sensor hardware state with the `delivered_raw.binned=false` buffer-copy flag.
- Stage32 successfully applied four supported GainMaps to a bounded real centre neighbourhood and obtained 1024 native Stage24 DNG PCS linear values. No HNCS, original Eagle2 CCM pixel arithmetic or full-frame processing is implied.
- This is **app-recorded capture provenance**, not independent cryptographic camera hardware attestation or DNG SDK pixel equality.

## New original-vs-effective neutral metadata mismatch

The private source sidecar shows a difference in the **blue** component between the unmodified original selected Camera2 still neutral and `effective_photon_export.neutral_used` / `capture_result_after_existing_Photon_fix`. Red and green agree. The change is **about 0.84% relative in that one blue-neutral component** for this capture. A numerical mismatch is confirmed, but it is **not** an HNCS calibration discrepancy or measured JPEG visual error.

Source tracing identifies an existing Photon mutation path:
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/api/Camera2ApiAutoFix.java`: `ApplyRes()` invokes `whitePoint()`, which sets `SENSOR_NEUTRAL_COLOR_POINT` to `CaptureController.mPreviewTemp`.
- `HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/processing/DngCreator.java`: the export configuration invokes `setAsShotNeutral(toDouble(parameters.whitePoint))`.
- `HasselbladCaptureEvidence` deliberately records original Camera2 values before existing Photon normalization and the effective `Parameters.whitePoint` later.

This identifies a concrete source-level route whereby the preview-derived neutral can reach a saved DNG. **The actual DNG's `AsShotNeutral` tag has not been independently read in this verification**, because only the Stage32 summary and its capture sidecar were provided. Verify whether the DNG tag equals original Camera2 or the effective Photon value before claiming the exact stored metadata or changing camera behaviour.

## Engineering next gate

1. Verify the *actual DNG tag* (`AsShotNeutral`, and matching FM/CC/AnalogBalance) against the original selected Camera2 still result and the effective Photon export from the matched sidecar; keep sensitive matrices and photo data private.
2. If it differs, add a separate opt-in **metadata provenance indicator** on the development screen or a private host audit, without silently modifying the saved JPEG/DNG processing path.
3. For firmware-equivalent colour, continue recovery of X2D II MAIN CCM pixel equation, Q scale, gamma and LUT stage semantics. The neutral Stage24 PCS output is only an independent colourimetric reference.
4. Stage32 APK versionCode 27188 remains the phone-tested baseline; **no new APK required by this Stage33 validation**. Main branch stays unchanged.

**Scope:** research receipts only; no raw photo bytes, vendor firmware or original camera identity published. No original photo was edited.
