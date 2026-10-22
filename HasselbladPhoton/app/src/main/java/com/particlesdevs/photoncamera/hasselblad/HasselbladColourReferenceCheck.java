package com.particlesdevs.photoncamera.hasselblad;

import java.util.Arrays;
import java.util.Locale;

/**
 * Stage26 bounded Android JNI smoke check of the Stage24 neutral colourimetric
 * engine. Development screen only. Does not load RAW, read camera metadata,
 * set white balance, alter Photon processing or save photographs.
 *
 * Native input is ALREADY demosaiced, black-corrected camera-linear RGB; the
 * caller must separately prove DNG calibration/opcodes/frame provenance before
 * using this API with actual photographs. Native output is *linear* sRGB/P3,
 * not a display-encoded JPEG or Hasselblad/HNCS colour transform.
 */
public final class HasselbladColourReferenceCheck {
    private HasselbladColourReferenceCheck() { }

    private static native int nativeLinearTile(
            double[] forwardMatrix1, double[] forwardMatrix2,
            double[] cameraCalibration1, double[] cameraCalibration2,
            double[] analogBalance, double[] asShotNeutral,
            int outputGamut, double[] cameraLinearRGB, int pixels,
            double[] outputLinearRGB);

    private static final double[] D50_IDENTITY_FM = {
            .9642, 0, 0, 0, 1, 0, 0, 0, .8249
    };
    private static final double[] IDENTITY = {
            1, 0, 0, 0, 1, 0, 0, 0, 1
    };
    private static final double[] UNITY = {1, 1, 1};
    private static final int JNI_BAD_INPUT = 100;
    private static final int UNSUPPORTED_DUAL_PROFILE = 3;
    private static final int EXPECTED_TESTS = 11;

    private static int invoke(double[] fm1, double[] fm2, double[] cc1, double[] cc2,
                              double[] neutral, int gamut, double[] in,
                              int pixels, double[] out) {
        return nativeLinearTile(fm1, fm2, cc1, cc2, UNITY, neutral, gamut, in, pixels, out);
    }
    private static double[] sentinel(int n) {
        double[] x = new double[n];
        Arrays.fill(x, 37.0);
        return x;
    }
    private static boolean nearAll(double[] values, double expected, double tolerance) {
        for (double v : values) {
            if (!Double.isFinite(v) || Math.abs(v - expected) > tolerance) return false;
        }
        return true;
    }
    private static boolean untouched(double[] values) {
        return nearAll(values, 37.0, 0.0);
    }

    /** Synthetic arithmetic only. Never called from the shutter or photo path. */
    public static String run() {
        int passed = 0;
        String failure = "";
        long started = System.nanoTime();
        try {
            System.loadLibrary("hasselblad_colour_reference_jni");
            // D50-neutral white should map to D65-neutral linear sRGB.
            double[] white = sentinel(3);
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, UNITY, 1, white) == 0 && nearAll(white, 1, 0.0004)) passed++;
            double[] whiteP3 = sentinel(3);
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 1, UNITY, 1, whiteP3) == 0 && nearAll(whiteP3, 1, 0.0004)) passed++;

            // Prove unclipped negative and above-one scene-linear components.
            double[] negative = sentinel(3);
            double[] negativeSource = {-0.20, -0.20, -0.20};
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, negativeSource, 1, negative) == 0
                    && nearAll(negative, -0.20, 0.0004)) passed++;
            double[] bright = sentinel(3);
            double[] brightSource = {1.40, 1.40, 1.40};
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, brightSource, 1, bright) == 0
                    && nearAll(bright, 1.40, 0.0006)) passed++;

            // A mixed 1024-pixel buffer exercises the native tiling boundary.
            double[] input = new double[1024 * 3];
            for (int i = 0; i < input.length; i++) input[i] = (i % 41) / 23.0 - .35;
            double[] tile = sentinel(input.length);
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, input, 1024, tile) == 0
                    && Double.isFinite(tile[0])
                    && Double.isFinite(tile[tile.length - 1])
                    && !untouched(tile)) passed++;

            double[] mismatched = D50_IDENTITY_FM.clone();
            mismatched[0] += .01;
            double[] reject = sentinel(3);
            if (invoke(D50_IDENTITY_FM, mismatched, IDENTITY, IDENTITY,
                    UNITY, 0, UNITY, 1, reject) == UNSUPPORTED_DUAL_PROFILE
                    && untouched(reject)) passed++;

            reject = sentinel(3);
            double[] mismatchCC = IDENTITY.clone();
            mismatchCC[4] = 1.01;
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, mismatchCC,
                    UNITY, 0, UNITY, 1, reject) == UNSUPPORTED_DUAL_PROFILE
                    && untouched(reject)) passed++;

            reject = sentinel(3);
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 2, UNITY, 1, reject) == JNI_BAD_INPUT
                    && untouched(reject)) passed++;

            reject = sentinel(3);
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, new double[]{Double.NaN, 1, 1}, 1, reject) != 0
                    && untouched(reject)) passed++;

            double[] aliased = {1, 1, 1};
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, aliased, 1, aliased) == JNI_BAD_INPUT
                    && nearAll(aliased, 1, 0)) passed++;

            reject = sentinel(3);
            if (invoke(D50_IDENTITY_FM, D50_IDENTITY_FM, IDENTITY, IDENTITY,
                    UNITY, 0, UNITY, 1025, reject) == JNI_BAD_INPUT
                    && untouched(reject)) passed++;
        } catch (Throwable e) {
            failure = e.getClass().getSimpleName();
        }
        boolean ok = passed == EXPECTED_TESTS && failure.isEmpty();
        return "{\"schema\":\"hasselblad-stage26-neutral-jni-synthetic-v1\","
                + "\"status\":\"" + (ok ? "PASS" : "NOT_PASSED") + "\","
                + "\"tests_passed\":" + passed + ","
                + "\"tests_total\":" + EXPECTED_TESTS + ","
                + "\"elapsed_ms\":" + String.format(Locale.US, "%.3f", (System.nanoTime() - started) / 1e6) + ","
                + "\"exception_type\":\"" + failure + "\","
                + "\"input_is_synthetic\":true,"
                + "\"output_linear_light\":true,"
                + "\"hncs_pixel_equivalence_proven\":false,"
                + "\"main_lut_hypothesis_invoked\":false,"
                + "\"photographic_render_authorized\":false,"
                + "\"saved_photo_colour_still_photon\":true}";
    }
}
