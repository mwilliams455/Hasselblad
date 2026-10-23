package com.particlesdevs.photoncamera.hasselblad;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/**
 * Stage36 strictly on-demand, read-only comparison of ONE physically bound RAW
 * centre tile under two recorded WB neutrals through the SAME Stage26 JNI.
 * It does not touch Camera2 capture, shutter, save paths, preview, or HNCS.
 * Caller supplies the original chosen DNG and matching .capture.json via SAF.
 */
public final class HasselbladDualNeutralDiagnostic36 {
    private HasselbladDualNeutralDiagnostic36() { }
    private static final int MAX_SIDECAR_BYTES = 4 * 1024 * 1024;
    private static final String STAGE32_PASS = "PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY";
    private static final String STAGE34_PASS = "PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED";
    private static final String STAGE36_PASS = "PASS_BOUND_REAL_DNG_DUAL_NEUTRAL_LINEAR_TILE";

    private static final class Rejected extends Exception {
        Rejected(String code) { super(code); }
    }
    private static void require(boolean ok, String code) throws Rejected {
        if (!ok) throw new Rejected(code);
    }
    private static String hex(byte[] digest) {
        StringBuilder b = new StringBuilder(digest.length * 2);
        for (byte value : digest) b.append(String.format(Locale.US, "%02x", value & 255));
        return b.toString();
    }
    private static boolean sameHash(String a,String b) {
        return a != null && b != null && a.matches("[a-f0-9]{64}")
                && b.matches("[a-f0-9]{64}")
                && MessageDigest.isEqual(a.getBytes(StandardCharsets.US_ASCII),
                        b.getBytes(StandardCharsets.US_ASCII));
    }
    private static String safeToken(String message) {
        return message != null && message.matches("[A-Za-z0-9_]{1,98}")
                ? message : "unsupported_input";
    }
    private static JSONArray numericTriple(double[] values) throws Exception {
        require(values != null && values.length == 3, "invalid_aggregate_shape");
        return new JSONArray().put(values[0]).put(values[1]).put(values[2]);
    }
    private static double[] ratios(JSONArray input) throws Exception {
        require(input != null && input.length() == 3, "original_neutral_absent");
        double[] result = new double[3];
        for (int i = 0; i < 3; i++) {
            JSONObject r = input.getJSONObject(i);
            double n = r.getDouble("numerator"), d = r.getDouble("denominator");
            require(Double.isFinite(n) && Double.isFinite(d) && d != 0,
                    "original_neutral_invalid_rational");
            double v = n / d;
            require(Double.isFinite(v) && v > 0, "original_neutral_invalid_value");
            result[i] = v;
        }
        return result;
    }
    private static JSONObject boundedSidecar(ContentResolver resolver, Uri uri) throws Exception {
        try (InputStream source = resolver.openInputStream(uri)) {
            require(source != null, "sidecar_unreadable");
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            byte[] buffer = new byte[16384];
            int n;
            while ((n = source.read(buffer)) != -1) {
                if (n == 0) continue;
                require(n <= MAX_SIDECAR_BYTES - b.size(), "sidecar_exceeds_4MiB");
                b.write(buffer, 0, n);
            }
            require(b.size() > 0, "sidecar_empty");
            return new JSONObject(b.toString(StandardCharsets.UTF_8.name()));
        }
    }
    private static long privateDngCopy(ContentResolver resolver, Uri uri,
                                       File local, MessageDigest sha) throws Exception {
        long bytes = 0;
        try (InputStream source = resolver.openInputStream(uri);
             FileOutputStream dest = new FileOutputStream(local)) {
            require(source != null, "original_dng_unreadable");
            byte[] buffer = new byte[65536];
            int n;
            while ((n = source.read(buffer)) != -1) {
                if (n == 0) continue;
                require(bytes <= HasselbladDngTileReader.MAX_FILE_BYTES - n,
                        "original_dng_exceeds_256MiB");
                sha.update(buffer, 0, n);
                dest.write(buffer, 0, n);
                bytes += n;
            }
        }
        require(bytes > 0, "original_dng_empty");
        return bytes;
    }

    public static String compare(Context context, Uri dngUri, Uri sidecarUri,
                                 String previousStage32Json, String previousStage34Json) {
        JSONObject report = new JSONObject();
        File temporary = null;
        String status = "NOT_PROVEN";
        long started = System.nanoTime();
        try {
            report.put("schema", "hasselblad-stage36-real-dng-dual-neutral-pcs-v1");
            report.put("source", "explicitly_selected_existing_DNG_and_capture_sidecar");
            report.put("input_is_synthetic", false);
            report.put("same_RAW_tile_and_DNG_matrices_for_both_native_calls", false);
            report.put("saved_photographs_and_original_DNG_unchanged", true);
            report.put("user_pixel_values_exported", false);
            report.put("private_file_hash_neutrals_matrices_camera_IDs_exported", false);
            report.put("native_stage", "Stage24_ForwardMatrix_D50_linear_sRGB_only");
            report.put("photographic_colour_still_photon", true);
            report.put("Hasselblad_MAIN_CCM_pixel_equivalence_proven", false);
            report.put("HNCS_pixel_rendering_performed", false);
            report.put("DNG_sdk_opcode2_bit_exact_proven", false);
            report.put("full_frame_render_performed", false);
            report.put("colour_error_or_deltaE_measured", false);
            report.put("not_a_camera_AWB_calibration", true);
            require(context != null && dngUri != null && sidecarUri != null
                    && previousStage32Json != null && previousStage34Json != null,
                    "missing_explicit_DNG_sidecar_or_receipts");
            JSONObject stage32 = new JSONObject(previousStage32Json);
            JSONObject previous34 = new JSONObject(previousStage34Json);
            require("hasselblad-stage32-real-dng-centre-tile-v1".equals(stage32.optString("schema"))
                    && STAGE32_PASS.equals(stage32.optString("status"))
                    && !stage32.optBoolean("input_is_synthetic", true)
                    && stage32.optInt("native_stage24_status_code", -1) == 0,
                    "previous_real_DNG_stage32_not_passed");
            require("hasselblad-stage34-dng-AsShotNeutral-provenance-v1".equals(previous34.optString("schema"))
                    && STAGE34_PASS.equals(previous34.optString("status"))
                    && previous34.optBoolean("DNG_digest_matches_Stage32_and_capture_sidecar", false)
                    && previous34.optBoolean("recorded_physical_sensor_frame_and_timestamp_bound", false),
                    "previous_stage34_record_binding_not_passed");

            ContentResolver resolver = context.getContentResolver();
            // Reverify the selected documents, not just a prior in-memory status.
            // The existing Stage34 method independently performs the physical,
            // frame, TIFF and original/effective neutral checks, deleting its copy.
            JSONObject fresh34 = new JSONObject(HasselbladDngWbProvenance34.verify(
                    context, dngUri, sidecarUri, previousStage32Json));
            require(STAGE34_PASS.equals(fresh34.optString("status"))
                    && fresh34.optBoolean("temporary_file_deleted", false)
                    && fresh34.optBoolean("DNG_AsShotNeutral_directly_read", false)
                    && fresh34.optBoolean("recorded_physical_sensor_frame_and_timestamp_bound", false),
                    "current_stage34_record_binding_not_passed");
            require(fresh34.optBoolean("DNG_neutral_matches_effective_Photon", false)
                    && fresh34.optBoolean("original_and_effective_neutrals_distinct", false)
                    && "MATCHES_PHOTON_EFFECTIVE_ONLY".equals(
                        fresh34.optString("DNG_AsShotNeutral_origin")),
                    "DNG_not_distinct_Photon_effective_neutral");
            for (String name : new String[] {"ForwardMatrix1_match", "ForwardMatrix2_match",
                    "CameraCalibration1_match", "CameraCalibration2_match"}) {
                require("MATCHES_BOTH".equals(fresh34.optString(name)),
                        "DNG_original_and_effective_profile_not_identical");
            }
            report.put("recorded_original_capture_physical_sensor_frame_bound", true);
            report.put("DNG_neutral_origin", "MATCHES_PHOTON_EFFECTIVE_ONLY");
            report.put("DNG_original_and_effective_profile_matrices_agree", true);

            temporary = File.createTempFile("hb36-readonly-", ".dng", context.getCacheDir());
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            long count = privateDngCopy(resolver, dngUri, temporary, sha);
            String digest = hex(sha.digest());
            require(sameHash(digest, stage32.optString("source_dng_sha256"))
                    && count == stage32.optLong("source_dng_bytes", -1),
                    "DNG_changed_since_Stage32");
            JSONObject sidecar = boundedSidecar(resolver, sidecarUri);
            JSONObject dngIdentity = sidecar.getJSONObject("dng");
            require(sameHash(digest, dngIdentity.getString("sha256"))
                    && count == dngIdentity.getLong("bytes"),
                    "DNG_changed_since_capture_record");
            HasselbladDngTileReader.ReadResult raw = HasselbladDngTileReader.read(temporary);
            require(raw.hasPcsInput() && raw.cameraLinearTile != null
                    && raw.cameraLinearTile.length == 3072,
                    "DNG_native_linear_tile_unavailable");
            JSONArray dims = stage32.getJSONArray("raw_dimensions");
            require(dims.length() == 2 && raw.width == dims.getInt(0)
                    && raw.height == dims.getInt(1) && raw.gainMapCount == 4,
                    "RAW_dimensions_or_gainmap_count_changed");
            double[] originalNeutral = ratios(sidecar.getJSONObject("original_still")
                    .getJSONObject("selected_raw_sensor_result")
                    .getJSONArray("android.sensor.neutralColorPoint"));
            double[] effectiveNeutral = raw.asShotNeutral;
            HasselbladNeutralCompare34.Comparison classified =
                    HasselbladNeutralCompare34.compareNeutrals(
                            effectiveNeutral, originalNeutral, effectiveNeutral);
            require(classified.originalAndEffectiveDistinct
                    && !classified.matchesOriginal && classified.matchesEffective,
                    "dual_neutrals_not_independently_distinct");

            System.loadLibrary("hasselblad_colour_reference_jni");
            double[] nativeOriginal = new double[3072], nativeEffective = new double[3072];
            long tNative = System.nanoTime();
            int originalStatus = HasselbladColourReferenceCheck.nativeLinearTile(
                    raw.forwardMatrix1, raw.forwardMatrix2,
                    raw.calibration1, raw.calibration2, raw.analogBalance,
                    originalNeutral, 0, raw.cameraLinearTile, 1024, nativeOriginal);
            int photonStatus = HasselbladColourReferenceCheck.nativeLinearTile(
                    raw.forwardMatrix1, raw.forwardMatrix2,
                    raw.calibration1, raw.calibration2, raw.analogBalance,
                    effectiveNeutral, 0, raw.cameraLinearTile, 1024, nativeEffective);
            double nativeElapsedMs = (System.nanoTime() - tNative) / 1e6;
            report.put("original_Camera2_neutral_native_status", originalStatus);
            report.put("Photon_effective_neutral_native_status", photonStatus);
            require(originalStatus == 0 && photonStatus == 0,
                    "native_Stage24_profile_or_tile_not_supported");

            HasselbladDualNeutralMath36.Result result =
                    HasselbladDualNeutralMath36.compare(nativeOriginal, nativeEffective);
            report.put("linear_RGB_mean_original_Camera2", numericTriple(result.meanOriginal));
            report.put("linear_RGB_mean_Photon_effective", numericTriple(result.meanEffective));
            report.put("linear_RGB_mean_signed_Photon_minus_original", numericTriple(
                    result.meanSignedEffectiveMinusOriginal));
            report.put("linear_RGB_mean_absolute_delta", numericTriple(result.meanAbsoluteDelta));
            report.put("linear_RGB_RMSE_per_channel", numericTriple(result.rmseDelta));
            report.put("linear_RGB_p95_absolute_delta_per_channel", numericTriple(result.p95AbsoluteDelta));
            report.put("linear_RGB_max_absolute_delta_per_channel", numericTriple(result.maxAbsoluteDelta));
            report.put("linear_RGB_RMSE_overall", result.overallRmse);
            report.put("linear_RGB_mean_absolute_delta_overall", result.overallMeanAbsoluteDelta);
            report.put("linear_RGB_p95_absolute_delta_overall", result.overallP95AbsoluteDelta);
            report.put("linear_RGB_max_absolute_delta_overall", result.overallMaxAbsoluteDelta);
            report.put("original_negative_components", result.originalsNegative);
            report.put("effective_negative_components", result.effectiveNegative);
            report.put("original_over_unity_components", result.originalsOverUnity);
            report.put("effective_over_unity_components", result.effectiveOverUnity);
            report.put("linear_reference_differences_detected_in_tile", result.differencesDetected);
            report.put("original_Camera2_vs_Photon_neutral_max_abs_delta",
                    classified.maxAbsOriginalVsEffective);
            report.put("tile_width", 32);
            report.put("tile_height", 32);
            report.put("native_tile_pixels_per_pass", 1024);
            report.put("native_reference_passes", 2);
            report.put("native_two_passes_elapsed_ms", nativeElapsedMs);
            report.put("native_two_pass_timing_excludes_DNG_decode_and_hash", true);
            report.put("same_RAW_tile_and_DNG_matrices_for_both_native_calls", true);
            report.put("numeric_metrics_are_scene_linear_sRGB_not_DeltaE", true);
            report.put("original_DNG_hash_reverified_but_not_exported", true);
            status = STAGE36_PASS;
        } catch (Rejected e) {
            try { report.put("reason", safeToken(e.getMessage())); } catch (Exception ignored) { }
        } catch (HasselbladDngTileReader.Unsupported e) {
            try { report.put("reason", "DNG_" + safeToken(e.code)); } catch (Exception ignored) { }
        } catch (Throwable e) {
            try { report.put("reason", "unsupported_" + safeToken(e.getClass().getSimpleName())); }
            catch (Exception ignored) { }
        } finally {
            boolean erased = temporary == null || temporary.delete();
            if (!erased) status = "NOT_PROVEN";
            try { report.put("temporary_file_deleted", erased); } catch (Exception ignored) { }
        }
        try {
            report.put("status", status);
            report.put("elapsed_ms", Math.round((System.nanoTime() - started) / 1e6));
        } catch (Exception ignored) { }
        return report.toString();
    }
}
