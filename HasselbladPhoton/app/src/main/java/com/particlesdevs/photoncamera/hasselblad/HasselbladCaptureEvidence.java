package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.graphics.Point;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.LensShadingMap;
import android.hardware.camera2.params.RggbChannelVector;
import android.graphics.ImageFormat;
import android.os.Build;
import android.os.Environment;
import android.util.Rational;
import android.util.Size;

import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import com.particlesdevs.photoncamera.processing.render.Parameters;
import com.particlesdevs.photoncamera.util.Log;
import com.particlesdevs.photoncamera.util.SimpleStorageHelper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Map;

/**
 * Recovery of Native1C's metadata evidence boundary. This is an observational sidecar:
 * it does not write CaptureResult/CameraCharacteristics or change any pixel data.
 * It must run BEFORE Camera2ApiAutoFix.ApplyRes modifies the result, and the DNG
 * checksum must be taken after the DNG writer has finished.
 *
 * Recreated from the preserved Native1C evidence schema; NOT an identical copy
 * of missing unpublished Native1C source. No vendor calibration is bundled.
 */
public final class HasselbladCaptureEvidence {
    private static final String TAG = "HasselbladCaptureEvidence";
    private final JSONObject document = new JSONObject();
    private final JSONObject originalStill = new JSONObject();
    private final JSONObject effective = new JSONObject();
    private final long rawTimestamp;
    private final boolean rawGeometryUsable;
    private final boolean sensorProvenanceMatched;
    private final boolean requiredMetadataPresent;
    private final String pairingStatus;

    private HasselbladCaptureEvidence(int imageCount, ImageFrame frame,
                                       CameraCharacteristics suppliedCharacteristics,
                                       CaptureResult stillResult, CaptureRequest stillRequest) throws Exception {
        rawTimestamp = frame.rawSensorTimestampNs == 0L ? frame.timestamp : frame.rawSensorTimestampNs;
        JSONObject raw = new JSONObject();
        raw.put("sensor_timestamp_ns", Long.toString(rawTimestamp));
        raw.put("format", frame.sourceRawFormat);
        raw.put("delivered_width", frame.sourceRawWidth);
        raw.put("delivered_height", frame.sourceRawHeight);
        raw.put("row_stride_bytes", frame.sourceRowStride);
        raw.put("pixel_stride_bytes", frame.sourcePixelStride);
        raw.put("image_crop_rect", jsonRect(frame.sourceImageCropRect));
        raw.put("copied_width", frame.width);
        raw.put("copied_height", frame.height);
        raw.put("copied_crop_x", frame.cropOriginX);
        raw.put("copied_crop_y", frame.cropOriginY);
        raw.put("copy_offset_bytes", frame.sourceCopyOffsetBytes);
        raw.put("binned", frame.sourceBinned);
        raw.put("original_buffer_capacity_bytes", frame.sourceRawBufferCapacity);

        document.put("schema", "hasselblad-photon-capture-evidence-v1");
        document.put("purpose", "Original still metadata and effective export parameters; no camera colour fit is asserted.");
        document.put("input_frame_count", imageCount);
        document.put("delivered_raw", raw);

        originalStill.put("snapshot_point", "processor_start_before_existing_Photon_fix");
        originalStill.put("camera2_long_values", "decimal strings retain full Camera2 64-bit integer precision");
        JSONObject logical = resultJson(stillResult);
        originalStill.put("logical_still_result", logical);
        originalStill.put("still_request", requestJson(stillRequest));
        originalStill.put("logical_frame_number", stillResult == null ? JSONObject.NULL : Long.toString(stillResult.getFrameNumber()));

        HasselbladRawStream.Identity stream = HasselbladRawStream.lookup(frame.sourceReaderSurface);
        String deviceId = stream == null ? null : stream.deviceId;
        String explicitPhysicalId = stream == null ? null : stream.physicalId;
        CaptureRequest resultRequest = stillResult == null ? null : stillResult.getRequest();
        boolean requestMatches = resultRequest != null && resultRequest.equals(stillRequest);
        boolean targetsRaw = requestMatches && frame.sourceReaderSurface != null
                && HasselbladRawStream.requestTargets(resultRequest, frame.sourceReaderSurface);
        String selectedId = explicitPhysicalId != null ? explicitPhysicalId : deviceId;

        CaptureResult selectedResult = stillResult;
        if (explicitPhysicalId != null && stillResult instanceof TotalCaptureResult
                && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            Map<String, ? extends CaptureResult> physical = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                    ? ((TotalCaptureResult) stillResult).getPhysicalCameraTotalResults()
                    : ((TotalCaptureResult) stillResult).getPhysicalCameraResults();
            selectedResult = physical == null ? null : physical.get(explicitPhysicalId);
        }
        originalStill.put("selected_raw_sensor_result", resultJson(selectedResult));
        originalStill.put("selected_result_frame_number", selectedResult == null ? JSONObject.NULL
                : Long.toString(selectedResult.getFrameNumber()));
        Long resultTimestamp = selectedResult == null ? null : selectedResult.get(CaptureResult.SENSOR_TIMESTAMP);
        pairingStatus = resultTimestamp == null ? "selected_still_timestamp_missing"
                : resultTimestamp.longValue() == rawTimestamp
                    ? "image_timestamp_equals_selected_still_result_timestamp"
                    : "image_timestamp_differs_from_selected_still_result_timestamp";

        JSONObject provenance = new JSONObject();
        provenance.put("configured_output_device_id", jsonNullable(deviceId));
        provenance.put("opened_camera_id", jsonNullable(deviceId));
        provenance.put("explicit_raw_physical_id", jsonNullable(explicitPhysicalId));
        provenance.put("request_targets_recorded_raw_surface", targetsRaw);
        provenance.put("request_target_evidence", "The result request equals the built still request whose recorded addTarget is the delivering ImageReader surface");
        provenance.put("selected_calibration_camera_id", jsonNullable(selectedId));

        CameraCharacteristics selectedCharacteristics = null;
        String characteristicSource = "unavailable";
        try {
            Context context = PhotonCamera.getAppContext();
            if (context != null && selectedId != null) {
                CameraManager manager = (CameraManager) context.getSystemService(Context.CAMERA_SERVICE);
                if (manager != null) {
                    selectedCharacteristics = manager.getCameraCharacteristics(selectedId);
                    characteristicSource = "fresh_CameraManager_query_during_processing";
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Could not query selected camera: " + e.getMessage());
        }
        // Never relabel the processing-supplied characteristics as a fresh query.
        if (selectedCharacteristics == null && explicitPhysicalId == null) {
            selectedCharacteristics = suppliedCharacteristics;
            if (selectedCharacteristics != null) characteristicSource = "processor_supplied_characteristics_fallback";
        }
        provenance.put("characteristics_source", characteristicSource);
        boolean resultCameraMatched = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                && selectedResult != null && selectedId != null
                && selectedId.equals(selectedResult.getCameraId())
                && deviceId != null && stillResult != null && deviceId.equals(stillResult.getCameraId());
        int[] selectedCaps = selectedCharacteristics == null ? null
                : selectedCharacteristics.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES);
        boolean selectedIsLogical = false;
        if (selectedCaps != null) for (int cap : selectedCaps)
            if (cap == CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_LOGICAL_MULTI_CAMERA) selectedIsLogical = true;
        provenance.put("selected_result_camera_id", Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                && selectedResult != null ? selectedResult.getCameraId() : JSONObject.NULL);
        provenance.put("result_camera_id_matched", resultCameraMatched);
        provenance.put("selected_characteristics_are_logical", selectedIsLogical);
        provenance.put("stream_identity_source", "actual_OutputConfiguration_by_delivering_ImageReader_surface");
        boolean frameNumberMatched = selectedResult != null && stillResult != null
                && selectedResult.getFrameNumber() >= 0
                && selectedResult.getFrameNumber() == stillResult.getFrameNumber();
        provenance.put("selected_and_logical_frame_number_matched", frameNumberMatched);
        sensorProvenanceMatched = frameNumberMatched && selectedCaps != null && resultCameraMatched && !selectedIsLogical && deviceId != null && selectedId != null && targetsRaw
                && selectedCharacteristics != null && selectedResult != null
                && "fresh_CameraManager_query_during_processing".equals(characteristicSource);
        provenance.put("sensor_provenance_matched", sensorProvenanceMatched);
        JSONArray unproven = new JSONArray();
        if (!frameNumberMatched) unproven.put("selected_frame_number_not_matched");
        if (!resultCameraMatched) unproven.put("result_camera_id_not_verified_requires_API31");
        if (selectedIsLogical) unproven.put("logical_sensor_without_explicit_physical_binding");
        if (!targetsRaw) unproven.put("still_request_raw_surface_not_verified");
        if (deviceId == null) unproven.put("open_camera_not_available_during_processing");
        if (selectedResult == null) unproven.put("physical_sensor_result_unavailable");
        if (!"fresh_CameraManager_query_during_processing".equals(characteristicSource))
            unproven.put("fresh_sensor_characteristics_unavailable");
        provenance.put("unproven_reasons", unproven);
        originalStill.put("sensor_provenance", provenance);
        JSONObject characteristicsJson = characteristicsJson(selectedCharacteristics);
        originalStill.put("selected_sensor_characteristics", characteristicsJson);

        JSONArray missing = new JSONArray();
        if (selectedResult == null || selectedResult.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT) == null)
            missing.put("android.sensor.neutralColorPoint");
        if (selectedCharacteristics == null || selectedCharacteristics.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL) == null)
            missing.put("android.sensor.info.whiteLevel");
        if (selectedCharacteristics == null || selectedCharacteristics.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1) == null
                || selectedCharacteristics.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2) == null)
            missing.put("android.sensor.forwardMatrix1/2");
        if (selectedCharacteristics == null || selectedCharacteristics.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1) == null
                || selectedCharacteristics.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2) == null)
            missing.put("android.sensor.colorTransform1/2");
        if (selectedCharacteristics == null || selectedCharacteristics.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1) == null
                || selectedCharacteristics.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2) == null)
            missing.put("android.sensor.calibrationTransform1/2");
        originalStill.put("required_metadata_missing_or_invalid", missing);
        originalStill.put("collection_errors", new JSONArray());
        originalStill.put("selected_sensor_timestamp_ns", resultTimestamp == null
                ? JSONObject.NULL : Long.toString(resultTimestamp));
        originalStill.put("logical_frame_number", stillResult == null ? JSONObject.NULL : Long.toString(stillResult.getFrameNumber()));
        requiredMetadataPresent = missing.length() == 0;
        rawGeometryUsable = imageCount == 1 && frame.sourceRawFormat == ImageFormat.RAW_SENSOR
                && !frame.sourceBinned && frame.width > 0 && frame.height > 0
                && frame.sourceRawWidth >= frame.width && frame.sourceRawHeight >= frame.height
                && frame.sourcePixelStride == 2 && frame.sourceRowStride >= frame.sourceRawWidth * 2
                // Only certify the path when the recorded copy offset and origin agree.
                // In particular, a centred 16:9 crop must not be called a full-frame copy.
                && frame.sourceCopyOffsetBytes == (long) frame.cropOriginY * frame.sourceRowStride
                        + (long) frame.cropOriginX * frame.sourcePixelStride
                && (long) frame.cropOriginY + frame.height <= frame.sourceRawHeight
                && (long) frame.cropOriginX + frame.width <= frame.sourceRawWidth
                && frame.sourceRawBufferCapacity >= (long) frame.sourceRowStride
                        * frame.sourceRawHeight;
        document.put("original_still", originalStill);
        document.put("pairing_status", pairingStatus);
        document.put("frame_number", selectedResult == null ? JSONObject.NULL : Long.toString(selectedResult.getFrameNumber()));

        JSONArray unusable = new JSONArray();
        if (!rawGeometryUsable) unusable.put("unsupported_or_unproven_raw_copy_geometry");
        if (!sensorProvenanceMatched) unusable.put("selected_camera_provenance_unproven");
        if (!requiredMetadataPresent) unusable.put("essential_camera2_calibration_metadata_missing");
        if (!"image_timestamp_equals_selected_still_result_timestamp".equals(pairingStatus))
            unusable.put("raw_and_still_timestamp_not_matched");
        boolean usable = unusable.length() == 0;
        document.put("calibration_evidence_usable", usable);
        document.put("calibration_unusable_reasons", unusable);
        document.put("usability_scope", "Timestamp, sensor provenance, supported RAW copy and metadata presence only; not empirical calibration accuracy or pixel colour validation.");
        document.put("pixel_rendering_changed_by_sidecar", false);
        // Cache only the proved original sensor calibration for an opt-in
        // later development-screen check; never run Domain1 in this capture path.
        HasselbladDomainDiagnostics.rememberCapture(document);
        document.put("scene_candidate_diagnostics", HasselbladSceneDiagnostics.run(document, frame));
    }

    /** Must be called before Camera2ApiAutoFix.ApplyRes (from HdrxProcessor.start). */
    public static HasselbladCaptureEvidence begin(ArrayList<ImageFrame> frames,
            CameraCharacteristics characteristics, CaptureResult result, CaptureRequest request) {
        HasselbladSceneDiagnostics.reset();
        HasselbladDomainDiagnostics.clear();
        HasselbladCaptureSaveStatus.started();
        if (frames == null || frames.size() != 1 || frames.get(0) == null) {
            HasselbladCaptureSaveStatus.skipped("Single-frame RAW evidence only; no suitable input frame.");
            return null;
        }
        try {
            return new HasselbladCaptureEvidence(frames.size(), frames.get(0), characteristics, result, request);
        } catch (Exception e) {
            HasselbladCaptureSaveStatus.failed("Metadata snapshot failed: " + e.getMessage(), "");
            Log.e(TAG, "Original metadata snapshot failed: " + Log.getStackTraceString(e));
            return null;
        }
    }

    /**
     * Stage6 ties its GPU samples to an already-saved, checksum-identified
     * DNG, a proven physical sensor, and exactly one unmodified RAW frame.
     * This is read-only. No CaptureResult/RAW value is changed by the probe.
     * The Stage6 result is copied from the dev screen AFTER rendering because
     * the original .capture.json sidecar has already been saved at this point.
     */
    public JSONObject stage6OriginalIdentity() {
        try {
            if (!document.getBoolean("calibration_evidence_usable")
                    || !"image_timestamp_equals_selected_still_result_timestamp"
                    .equals(document.getString("pairing_status")) || !document.has("dng"))
                return null;
            JSONObject original=document.getJSONObject("original_still");
            JSONObject provenance=original.getJSONObject("sensor_provenance");
            if (!provenance.getBoolean("sensor_provenance_matched")
                    || !provenance.getBoolean("result_camera_id_matched")
                    || !provenance.getBoolean("request_targets_recorded_raw_surface")
                    || !provenance.getBoolean("selected_and_logical_frame_number_matched")
                    || provenance.getBoolean("selected_characteristics_are_logical"))
                return null;
            String camera=provenance.getString("selected_calibration_camera_id");
            if (!camera.equals(provenance.getString("selected_result_camera_id")))
                return null;
            String frame=document.getString("frame_number");
            String stamp=original.getString("selected_sensor_timestamp_ns");
            if (!frame.equals(original.getString("selected_result_frame_number"))
                    || !stamp.equals(original.getJSONObject("selected_raw_sensor_result")
                    .getString("android.sensor.timestamp"))
                    || !stamp.equals(document.getJSONObject("delivered_raw")
                    .getString("sensor_timestamp_ns")))
                return null;
            JSONObject raw=document.getJSONObject("delivered_raw");
            if (raw.getInt("delivered_width")!=raw.getInt("copied_width")
                    || raw.getInt("delivered_height")!=raw.getInt("copied_height")
                    || raw.getInt("copy_offset_bytes")!=0 || raw.getBoolean("binned"))
                return null;
            JSONObject dng=document.getJSONObject("dng");
            String hash=dng.getString("sha256");
            if (!hash.matches("[0-9a-f]{64}") || dng.getLong("bytes")<=0)
                return null;
            JSONObject out=new JSONObject();
            out.put("physical_sensor_proven",true);
            out.put("physical_sensor_id",camera);
            out.put("frame_number",frame);
            out.put("sensor_timestamp_ns",stamp);
            out.put("width",raw.getInt("copied_width"));
            out.put("height",raw.getInt("copied_height"));
            out.put("cfa",original.getJSONObject("selected_sensor_characteristics")
                    .getInt("android.sensor.info.colorFilterArrangement"));
            out.put("original_dng_name",dng.getString("name"));
            out.put("original_dng_bytes",dng.getLong("bytes"));
            out.put("original_dng_sha256",hash);
            out.put("original_metadata_binding","image+physical_sensor+frame+timestamp+saved_DNG_hash");
            return out;
        } catch (Exception ignored) {
            return null;
        }
    }

    /** Must be called after FillDynamicParameters but BEFORE processingParameter mutation for render. */
    public void recordEffective(Parameters p, CaptureResult fixedResult) {
        if (p == null) return;
        try {
            JSONObject app = new JSONObject();
            app.put("application_id", "com.mwilliams.hasselbladphoton");
            app.put("version_name", com.particlesdevs.photoncamera.BuildConfig.VERSION_NAME);
            app.put("version_code", com.particlesdevs.photoncamera.BuildConfig.VERSION_CODE);
            effective.put("app", app);
            effective.put("snapshot_point", "after_Photon_FillDynamicParameters_before_RAW_DNG_save");
            effective.put("preview_metadata_substitution_attempted_by_existing_Photon_path", true);
            effective.put("matrix_convention", "Photon row-major float arrays; colour transform getElement(column,row)");
            effective.put("colour_space_warning", "Existing Photon ProPhoto conversion, not Hasselblad HNCS");
            effective.put("camera_id", jsonNullable(p.cameraID));
            effective.put("parameters_logical_id", p.logicalID);
            effective.put("parameters_physical_id", p.physicalID);
            effective.put("iso", p.iso);
            effective.put("exposure_seconds", p.exposureTime);
            effective.put("black_level_raw_counts", jsonFloatArray(p.blackLevel));
            effective.put("white_level_raw_counts", p.whiteLevel);
            effective.put("cfa_pattern", p.cfaPattern);
            effective.put("neutral_used", jsonFloatArray(p.whitePoint));
            effective.put("raw_size", jsonPoint(p.rawSize));
            effective.put("crop_origin", jsonPoint(p.cropOrigin));
            effective.put("full_raw_size", p.fullRawSize == null ? JSONObject.NULL : jsonPoint(p.fullRawSize));
            effective.put("active_sensor_rect", jsonRect(p.sensorPix));
            effective.put("used_dynamic_black_level", p.usedDynamic);
            effective.put("has_lens_shading_map", p.hasGainMap);
            effective.put("lens_shading_map_size", jsonPoint(p.mapSize));
            effective.put("lens_shading_gain_map", p.gainMap == null ? JSONObject.NULL : jsonFloatArray(p.gainMap));
            effective.put("calibration_illuminant_1_field", p.calibrationIlluminant1);
            effective.put("calibration_illuminant_2_field", p.calibrationIlluminant2);
            effective.put("illuminant_field_note", "Photon Parameters native field numbers; compare with original characteristic illuminants");
            effective.put("calibration_transform_1", jsonFloatArray(p.calibrationTransform1));
            effective.put("calibration_transform_2", jsonFloatArray(p.calibrationTransform2));
            effective.put("colour_matrix_1", jsonFloatArray(p.ColorMatrix1));
            effective.put("colour_matrix_2", jsonFloatArray(p.ColorMatrix2));
            effective.put("forward_matrix_1", jsonFloatArray(p.ForwardTransform1));
            effective.put("forward_matrix_2", jsonFloatArray(p.ForwardTransform2));
            effective.put("sensor_to_ProPhoto_field", jsonFloatArray(p.sensorToProPhoto));
            effective.put("ProPhoto_to_sRGB_field", jsonFloatArray(p.proPhotoToSRGB));
            effective.put("sensor_specifics_present", p.sensorSpecifics != null);
            effective.put("sensor_specific_calibration_override_present", p.sensorSpecifics != null && p.sensorSpecifics.CCTExists);
            effective.put("colour_method_setting", PhotonCamera.getSettings().colorMethod);
            effective.put("cct_mode", p.CCT == null ? "unavailable" : p.CCT.correctionMode.toString());
            effective.put("cct_matrix_1", p.CCT == null ? JSONObject.NULL : jsonFloatArray(p.CCT.matrix));
            effective.put("cct_matrix_2", p.CCT == null ? JSONObject.NULL : jsonFloatArray(p.CCT.matrix2));
            effective.put("cct_point_1", p.CCT == null ? JSONObject.NULL : jsonFloatArray(p.CCT.point1));
            effective.put("cct_point_2", p.CCT == null ? JSONObject.NULL : jsonFloatArray(p.CCT.point2));
            effective.put("hsv_profile_present", p.HSVMap != null);
            effective.put("look_profile_present", p.LookMap != null);
            effective.put("capture_result_after_existing_Photon_fix", resultJson(fixedResult));
            effective.put("collection_errors", new JSONArray());
            effective.put("raw_copy_geometry_matches_export", p.rawSize != null
                    && p.rawSize.x == document.getJSONObject("delivered_raw").getInt("copied_width")
                    && p.rawSize.y == document.getJSONObject("delivered_raw").getInt("copied_height"));
            document.put("effective_photon_export", effective);
        } catch (Exception e) {
            HasselbladCaptureSaveStatus.failed("Effective metadata snapshot failed: " + e.getMessage(), "");
            Log.e(TAG, "Effective metadata error: " + Log.getStackTraceString(e));
        }
    }

    /** Write only when a DNG is saved; never pretend success from a file path alone. */
    public void finishRawSave(Path dngPath, boolean dngSaved) {
        if (!dngSaved || dngPath == null) {
            HasselbladCaptureSaveStatus.skipped("DNG was not saved; capture evidence cannot be paired.");
            return;
        }
        String sidecarName = dngPath.getFileName().toString().replaceFirst("(?i)\\.dng$", ".capture.json");
        Path sidecarPath = dngPath.resolveSibling(sidecarName);
        try {
            Context context = PhotonCamera.getAppContext();
            if (context == null) throw new IllegalStateException("application context unavailable");
            // DNG digest/length come from the actual stored file, never from an assumed RAW buffer.
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long size = 0;
            try (InputStream stream = openSavedDng(context, dngPath)) {
                byte[] data = new byte[65536];
                int n;
                while ((n = stream.read(data)) >= 0) {
                    if (n == 0) continue;
                    digest.update(data, 0, n);
                    size += n;
                }
            }
            JSONObject dng = new JSONObject();
            dng.put("name", dngPath.getFileName().toString());
            dng.put("bytes", size);
            dng.put("sha256", toHex(digest.digest()));
            document.put("dng", dng);
            if (!document.has("effective_photon_export"))
                throw new IllegalStateException("effective Photon snapshot not captured");
            byte[] payload = document.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8);
            try (OutputStream stream = openSavedSidecar(context, sidecarPath)) {
                stream.write(payload);
                stream.flush();
            }
            HasselbladCaptureSaveStatus.saved(sidecarName);
        } catch (Exception e) {
            HasselbladCaptureSaveStatus.failed("Capture JSON failed: " + e.getMessage(), sidecarName);
            Log.e(TAG, "Capture JSON storage failed: " + Log.getStackTraceString(e));
        }
    }

    private static InputStream openSavedDng(Context context, Path path) throws Exception {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (!SimpleStorageHelper.hasStorageAccess(context))
                throw new SecurityException("Grant primary DCIM access in Settings");
            return SimpleStorageHelper.openInputStreamByPath(context, pathUnderPrimary(path));
        }
        return Files.newInputStream(path);
    }

    private static OutputStream openSavedSidecar(Context context, Path path) throws Exception {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (!SimpleStorageHelper.hasStorageAccess(context))
                throw new SecurityException("Grant primary DCIM access in Settings");
            OutputStream stream = SimpleStorageHelper.openOutputStreamByAbsPath(path.toString());
            if (stream == null) throw new java.io.IOException("SAF document provider did not create JSON");
            return stream;
        }
        Files.createDirectories(path.getParent());
        return Files.newOutputStream(path);
    }

    private static String pathUnderPrimary(Path path) throws Exception {
        String primary = new File(Environment.getExternalStorageDirectory().getCanonicalPath()).getPath();
        String candidate = path.toFile().getCanonicalPath();
        if (!candidate.startsWith(primary + File.separator))
            throw new SecurityException("DNG is not under primary storage");
        String relative = candidate.substring(primary.length() + 1);
        if (!relative.startsWith("DCIM/")) throw new SecurityException("DNG is outside DCIM");
        return relative;
    }

    private static String toHex(byte[] bytes) {
        StringBuilder b = new StringBuilder(bytes.length * 2);
        for (byte v : bytes) b.append(String.format(java.util.Locale.US, "%02x", v & 255));
        return b.toString();
    }

    private static Object jsonNullable(Object obj) { return obj == null ? JSONObject.NULL : obj; }
    private static JSONArray jsonRect(Rect r) { JSONArray a = new JSONArray();
        if (r != null) {a.put(r.left);a.put(r.top);a.put(r.right);a.put(r.bottom);} return a; }
    private static JSONArray jsonPoint(Point p) { JSONArray a = new JSONArray();
        if (p != null) {a.put(p.x);a.put(p.y);} return a; }
    private static JSONArray jsonSize(Size s) { JSONArray a = new JSONArray();
        if (s != null) {a.put(s.getWidth());a.put(s.getHeight());} return a; }
    private static JSONArray jsonFloatArray(float[] values) { JSONArray a = new JSONArray();
        if (values != null) for (float v : values) a.put(Float.isFinite(v) ? (double)v : JSONObject.NULL);
        return a; }
    private static JSONArray jsonIntArray(int[] values) { JSONArray a = new JSONArray();
        if (values != null) for (int v : values) a.put(v); return a; }
    private static JSONArray jsonRationals(Rational[] items) { JSONArray a = new JSONArray();
        if (items != null) for (Rational v : items) a.put(jsonRational(v)); return a; }
    private static Object jsonRational(Rational r) {if (r == null) return JSONObject.NULL;
        JSONObject v = new JSONObject(); try {v.put("numerator", r.getNumerator()); v.put("denominator", r.getDenominator());}
        catch (Exception ignored) {} return v; }
    private static Object jsonCst(ColorSpaceTransform c) {
        if (c == null) return JSONObject.NULL;
        JSONArray a = new JSONArray(); for(int row=0;row<3;row++) for (int col=0;col<3;col++)
            a.put(jsonRational(c.getElement(col,row))); return a;
    }
    private static Object jsonGains(RggbChannelVector gains) {
        if (gains == null) return JSONObject.NULL;
        return jsonFloatArray(new float[]{gains.getRed(), gains.getGreenEven(),
                gains.getGreenOdd(), gains.getBlue()});
    }
    private static Object jsonMap(LensShadingMap map) {
        if (map == null) return JSONObject.NULL;
        JSONObject json = new JSONObject();
        try {
            json.put("rows", map.getRowCount());
            json.put("columns", map.getColumnCount());
            json.put("layout", "row-major, per-cell RGGB channel order");
            JSONArray gains = new JSONArray();
            for (int row=0;row<map.getRowCount();row++)
                for(int col=0;col<map.getColumnCount();col++)
                    for(int ch=0;ch<4;ch++) gains.put(map.getGainFactor(ch,col,row));
            json.put("gains", gains);
        } catch (Exception ignored) {}
        return json;
    }

    private static JSONObject resultJson(CaptureResult result) throws Exception {
        JSONObject j = new JSONObject();
        if (result == null) return j;
        j.put("android.sensor.timestamp", longOrNull(result.get(CaptureResult.SENSOR_TIMESTAMP)));
        j.put("android.sensor.exposureTime", longOrNull(result.get(CaptureResult.SENSOR_EXPOSURE_TIME)));
        j.put("android.sensor.frameDuration", longOrNull(result.get(CaptureResult.SENSOR_FRAME_DURATION)));
        put(j, "android.sensor.sensitivity", result.get(CaptureResult.SENSOR_SENSITIVITY));
        Object dynBl = result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
        j.put("android.sensor.dynamicBlackLevel", dynBl instanceof float[] ? jsonFloatArray((float[])dynBl) : JSONObject.NULL);
        put(j, "android.sensor.dynamicWhiteLevel", result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL));
        j.put("android.sensor.neutralColorPoint", jsonRationals(result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT)));
        j.put("android.colorCorrection.gains", jsonGains(result.get(CaptureResult.COLOR_CORRECTION_GAINS)));
        j.put("android.colorCorrection.transform", jsonCst(result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)));
        put(j, "android.colorCorrection.mode", result.get(CaptureResult.COLOR_CORRECTION_MODE));
        put(j, "android.control.awbMode", result.get(CaptureResult.CONTROL_AWB_MODE));
        put(j, "android.control.awbState", result.get(CaptureResult.CONTROL_AWB_STATE));
        put(j, "android.control.aeMode", result.get(CaptureResult.CONTROL_AE_MODE));
        put(j, "android.control.aeState", result.get(CaptureResult.CONTROL_AE_STATE));
        put(j, "android.control.aeExposureCompensation", result.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION));
        Object crop = result.get(CaptureResult.SCALER_CROP_REGION);
        j.put("android.scaler.cropRegion", crop instanceof Rect ? jsonRect((Rect)crop) : JSONObject.NULL);
        put(j, "android.shading.mode", result.get(CaptureResult.SHADING_MODE));
        j.put("android.statistics.lensShadingCorrectionMap", jsonMap(result.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP)));
        put(j, "android.lens.aperture", result.get(CaptureResult.LENS_APERTURE));
        put(j, "android.lens.focalLength", result.get(CaptureResult.LENS_FOCAL_LENGTH));
        put(j, "android.lens.focusDistance", result.get(CaptureResult.LENS_FOCUS_DISTANCE));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P)
            put(j, "android.logicalMultiCamera.activePhysicalId", result.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID));
        else put(j, "android.logicalMultiCamera.activePhysicalId", null);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
            put(j, "android.sensor.rawBinningFactorUsed", result.get(CaptureResult.SENSOR_RAW_BINNING_FACTOR_USED));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
            put(j, "android.sensor.pixelMode", result.get(CaptureResult.SENSOR_PIXEL_MODE));
        else put(j, "android.sensor.pixelMode", null);
        return j;
    }

    private static JSONObject requestJson(CaptureRequest request) throws Exception {
        JSONObject j = new JSONObject(); if (request == null) return j;
        j.put("android.sensor.exposureTime", longOrNull(request.get(CaptureRequest.SENSOR_EXPOSURE_TIME)));
        put(j, "android.sensor.sensitivity", request.get(CaptureRequest.SENSOR_SENSITIVITY));
        put(j, "android.control.awbMode", request.get(CaptureRequest.CONTROL_AWB_MODE));
        put(j, "android.control.awbLock", request.get(CaptureRequest.CONTROL_AWB_LOCK));
        j.put("android.colorCorrection.gains", jsonGains(request.get(CaptureRequest.COLOR_CORRECTION_GAINS)));
        j.put("android.colorCorrection.transform", jsonCst(request.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM)));
        put(j, "android.colorCorrection.mode", request.get(CaptureRequest.COLOR_CORRECTION_MODE));
        put(j, "android.control.aeMode", request.get(CaptureRequest.CONTROL_AE_MODE));
        put(j, "android.control.aeExposureCompensation", request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION));
        Rect crop = request.get(CaptureRequest.SCALER_CROP_REGION);
        j.put("android.scaler.cropRegion", crop == null ? JSONObject.NULL : jsonRect(crop));
        put(j, "android.shading.mode", request.get(CaptureRequest.SHADING_MODE));
        put(j, "android.statistics.lensShadingMapMode", request.get(CaptureRequest.STATISTICS_LENS_SHADING_MAP_MODE));
        return j;
    }

    private static JSONObject characteristicsJson(CameraCharacteristics c) throws Exception {
        JSONObject j = new JSONObject(); if(c == null) return j;
        int[] caps = c.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES);
        j.put("android.request.availableCapabilities", caps == null ? JSONObject.NULL : jsonIntArray(caps));
        put(j, "android.sensor.info.colorFilterArrangement", c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT));
        BlackLevelPattern bl = c.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
        JSONArray levels = new JSONArray(); if (bl != null) for(int row=0;row<2;row++) for(int col=0;col<2;col++)
            levels.put(bl.getOffsetForIndex(col,row));
        j.put("android.sensor.blackLevelPattern", bl == null ? JSONObject.NULL : levels);
        put(j, "android.sensor.info.whiteLevel", c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL));
        put(j, "android.sensor.referenceIlluminant1", c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1));
        put(j, "android.sensor.referenceIlluminant2", c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2));
        j.put("android.sensor.calibrationTransform1", jsonCst(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)));
        j.put("android.sensor.calibrationTransform2", jsonCst(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2)));
        j.put("android.sensor.colorTransform1", jsonCst(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)));
        j.put("android.sensor.colorTransform2", jsonCst(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)));
        j.put("android.sensor.forwardMatrix1", jsonCst(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1)));
        j.put("android.sensor.forwardMatrix2", jsonCst(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)));
        j.put("android.sensor.info.activeArraySize", jsonNullableRect(c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)));
        j.put("android.sensor.info.preCorrectionActiveArraySize", jsonNullableRect(c.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE)));
        Size pixels = c.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE);
        j.put("android.sensor.info.pixelArraySize", pixels == null ? JSONObject.NULL : jsonSize(pixels));
        put(j, "android.sensor.info.timestampSource", c.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE));
        return j;
    }
    private static Object jsonNullableRect(Rect r){return r == null ? JSONObject.NULL : jsonRect(r);}
    private static Object longOrNull(Long n){return n == null ? JSONObject.NULL : Long.toString(n);}
    private static void put(JSONObject out,String name,Object value) throws Exception {out.put(name, jsonNullable(value));}
}
