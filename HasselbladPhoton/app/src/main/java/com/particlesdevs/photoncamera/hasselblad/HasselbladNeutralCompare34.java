package com.particlesdevs.photoncamera.hasselblad;

/**
 * Bounded, scalar-only Stage34 DNG AsShotNeutral provenance classification.
 * No Android/CaptureResult dependencies; never modifies or saves photographs.
 *
 * Matching means numerical agreement within explicitly disclosed tolerance,
 * not a camera colour accuracy score, HNCS equivalence or DNG SDK parity.
 */
public final class HasselbladNeutralCompare34 {
    private HasselbladNeutralCompare34() { }
    public static final double NEUTRAL_ABSOLUTE_TOLERANCE = 0.00012;
    public static final double MATRIX_ABSOLUTE_TOLERANCE = 0.0005;

    public static final class Comparison {
        public final String classification;
        public final boolean matchesOriginal;
        public final boolean matchesEffective;
        public final boolean originalAndEffectiveDistinct;
        public final double maxAbsDifferenceToOriginal;
        public final double maxAbsDifferenceToEffective;
        public final double maxAbsOriginalVsEffective;

        private Comparison(String value, boolean first, boolean second,
                boolean distinct, double toFirst, double toSecond, double between) {
            classification = value; matchesOriginal = first; matchesEffective = second;
            originalAndEffectiveDistinct = distinct;
            maxAbsDifferenceToOriginal = toFirst;
            maxAbsDifferenceToEffective = toSecond;
            maxAbsOriginalVsEffective = between;
        }
    }

    private static void validVector(double[] values, int n, String label) {
        if (values == null || values.length != n)
            throw new IllegalArgumentException(label + "_length_invalid");
        for (double x : values)
            if (!Double.isFinite(x)) throw new IllegalArgumentException(label + "_nonfinite");
    }

    public static double maxAbsoluteDifference(double[] a, double[] b, int n) {
        validVector(a, n, "first"); validVector(b, n, "second");
        double max = 0;
        for (int i = 0; i < n; i++) max = Math.max(max, Math.abs(a[i] - b[i]));
        return max;
    }

    public static Comparison compareNeutrals(double[] dng, double[] original,
                                             double[] effective) {
        validVector(dng,3,"dng"); validVector(original,3,"original");
        validVector(effective,3,"effective");
        for (int i=0; i<3; i++) {
            if (!(dng[i]>0 && original[i]>0 && effective[i]>0))
                throw new IllegalArgumentException("neutral_component_nonpositive");
        }
        double toOriginal=maxAbsoluteDifference(dng,original,3);
        double toEffective=maxAbsoluteDifference(dng,effective,3);
        double between=maxAbsoluteDifference(original,effective,3);
        boolean mo=toOriginal<=NEUTRAL_ABSOLUTE_TOLERANCE;
        boolean me=toEffective<=NEUTRAL_ABSOLUTE_TOLERANCE;
        String tag=mo && me ? "MATCHES_BOTH_INDISTINGUISHABLE"
                  : mo ? "MATCHES_ORIGINAL_CAMERA2_ONLY"
                  : me ? "MATCHES_PHOTON_EFFECTIVE_ONLY"
                  : "MATCHES_NEITHER";
        return new Comparison(tag,mo,me,
                between>2*NEUTRAL_ABSOLUTE_TOLERANCE,
                toOriginal,toEffective,between);
    }

    /** Comparing an absent DNG profile is not equivalent to identity. */
    public static String compareOptionalMatrix(double[] dng,double[] original,
                                               double[] effective) {
        if (dng == null) return "DNG_TAG_ABSENT";
        if (original == null || effective == null) return "SIDECAR_FIELD_MISSING";
        boolean o=maxAbsoluteDifference(dng,original,9)<=MATRIX_ABSOLUTE_TOLERANCE;
        boolean e=maxAbsoluteDifference(dng,effective,9)<=MATRIX_ABSOLUTE_TOLERANCE;
        return o&&e ? "MATCHES_BOTH" : o ? "MATCHES_ORIGINAL_ONLY"
            : e ? "MATCHES_EFFECTIVE_ONLY" : "MATCHES_NEITHER";
    }
}
