package com.particlesdevs.photoncamera.hasselblad;

import java.util.Arrays;

/**
 * Stage36 deterministic comparison of TWO native Stage24 PCS-only outputs.
 * Both images must be the SAME 32x32 camera-linear input tile, processed with
 * the SAME DNG ForwardMatrix/Calibration/AnalogBalance and differing ONLY
 * by the selected neutral. This class knows no Android, DNG, or camera state.
 *
 * Aggregates are scene-linear sRGB numbers (NOT perceptual error, HNCS, or
 * a measurement of a different photographic rendering). No pixels exported.
 */
public final class HasselbladDualNeutralMath36 {
    public static final int TILE_PIXELS = 1024;
    public static final int CHANNELS = 3;
    private static final int SAMPLE_COUNT = TILE_PIXELS * CHANNELS;

    private HasselbladDualNeutralMath36() {}

    public static final class Result {
        public final double[] meanOriginal, meanEffective;
        public final double[] meanSignedEffectiveMinusOriginal;
        public final double[] meanAbsoluteDelta;
        public final double[] maxAbsoluteDelta;
        public final double[] rmseDelta;
        public final double[] p95AbsoluteDelta;
        public final double overallRmse;
        public final double overallMeanAbsoluteDelta;
        public final double overallP95AbsoluteDelta;
        public final double overallMaxAbsoluteDelta;
        public final int originalsNegative, effectiveNegative, originalsOverUnity, effectiveOverUnity;
        public final boolean differencesDetected;

        private Result(double[] mo, double[] me, double[] ms, double[] mad,
                double[] mx, double[] rmse, double[] p95, double overallRms,
                double overallMae, double overallP95, double overallMax,
                int neg0, int neg1, int over0, int over1, boolean changed) {
            meanOriginal = mo;
            meanEffective = me;
            meanSignedEffectiveMinusOriginal = ms;
            meanAbsoluteDelta = mad;
            maxAbsoluteDelta = mx;
            rmseDelta = rmse;
            p95AbsoluteDelta = p95;
            overallRmse = overallRms;
            overallMeanAbsoluteDelta = overallMae;
            overallP95AbsoluteDelta = overallP95;
            overallMaxAbsoluteDelta = overallMax;
            originalsNegative = neg0;
            effectiveNegative = neg1;
            originalsOverUnity = over0;
            effectiveOverUnity = over1;
            differencesDetected = changed;
        }
    }

    private static double p95(double[] sorted) {
        // nearest rank: ceil(0.95*n) - 1, reproducible even for constant arrays
        Arrays.sort(sorted);
        return sorted[(int) Math.ceil(sorted.length * 0.95) - 1];
    }

    public static Result compare(double[] original, double[] effective) {
        if (original == null || effective == null
                || original.length != SAMPLE_COUNT || effective.length != SAMPLE_COUNT
                || original == effective) {
            throw new IllegalArgumentException("Stage36_invalid_tile_shapes_or_alias");
        }
        double[] m0 = new double[3], m1 = new double[3], ms = new double[3];
        double[] mae = new double[3], maximum = new double[3], squares = new double[3];
        double[][] absByChannel = new double[3][TILE_PIXELS];
        double[] absAll = new double[SAMPLE_COUNT];
        int neg0 = 0, neg1 = 0, over0 = 0, over1 = 0;
        double totalAbs = 0., totalSq = 0., totalMax = 0.;
        boolean differences = false;
        for (int i = 0; i < SAMPLE_COUNT; ++i) {
            double a = original[i], b = effective[i];
            if (!Double.isFinite(a) || !Double.isFinite(b)
                    || Math.abs(a) > 1e6 || Math.abs(b) > 1e6) {
                throw new IllegalArgumentException("Stage36_invalid_native_linear_component");
            }
            int ch = i % 3, p = i / 3;
            double d = b - a, ad = Math.abs(d);
            if (ad > 0.) differences = true;
            m0[ch] += a;
            m1[ch] += b;
            ms[ch] += d;
            mae[ch] += ad;
            squares[ch] += d * d;
            maximum[ch] = Math.max(maximum[ch], ad);
            absByChannel[ch][p] = ad;
            absAll[i] = ad;
            totalAbs += ad;
            totalSq += d * d;
            totalMax = Math.max(totalMax, ad);
            if (a < 0) neg0++;
            if (b < 0) neg1++;
            if (a > 1) over0++;
            if (b > 1) over1++;
        }
        double[] rms = new double[3], percentiles = new double[3];
        for (int ch = 0; ch < 3; ch++) {
            m0[ch] /= TILE_PIXELS;
            m1[ch] /= TILE_PIXELS;
            ms[ch] /= TILE_PIXELS;
            mae[ch] /= TILE_PIXELS;
            rms[ch] = Math.sqrt(squares[ch] / TILE_PIXELS);
            percentiles[ch] = p95(absByChannel[ch]);
        }
        return new Result(m0, m1, ms, mae, maximum, rms, percentiles,
                Math.sqrt(totalSq / SAMPLE_COUNT), totalAbs / SAMPLE_COUNT,
                p95(absAll), totalMax, neg0, neg1, over0, over1, differences);
    }
}
