package com.particlesdevs.photoncamera.hasselblad;

/** Fixed outputs come from the recorded execution of the original ARM64 routine. */
public final class HasselbladNativeCheck {
    public static final String SCOPE =
            "WB primitive only; photographic rendering not connected";

    private static final String[] NAMES = {
            "Q12 unity", "Independent gain scales", "Fractional truncation",
            "Half and double calibration", "Zero gains", "Bounded gains",
            "One least-significant bit", "Asymmetric fraction",
            "Last inputs before shift overflow", "Large unsigned calibration",
            "Guard: zero calibration A", "Guard: zero calibration B",
            "Guard: gain A shift overflow", "Guard: gain B shift overflow"
    };

    /* gain A, gain B, calibration A, calibration B, expected adapter status,
       expected output A, expected output B. No photograph calibration is inferred. */
    private static final long[][] VECTORS = {
            {4096, 4096, 4096, 4096, 0, 4096, 4096},
            {8192, 12288, 8192, 6144, 0, 4096, 8192},
            {5001, 6001, 3000, 5000, 0, 6828, 4916},
            {4096, 4096, 2048, 8192, 0, 8192, 2048},
            {0, 0, 4096, 4096, 0, 0, 0},
            {65535, 65535, 4096, 8192, 0, 65535, 32767},
            {1, 2, 4096, 4096, 0, 1, 2},
            {12345, 23456, 7000, 3333, 0, 7223, 28825},
            {1048575, 1048574, 4096, 4095, 0, 1048575, 1048830},
            {65535, 4096, 4294967295L, 16777216, 0, 0, 1},
            {4096, 4096, 0, 4096, 1, 4096, 4096},
            {4096, 4096, 4096, 0, 1, 4096, 4096},
            {1048576, 4096, 4096, 4096, 2, 1048576, 4096},
            {4096, 4294967295L, 4096, 4096, 2, 4096, 4294967295L}
    };

    private HasselbladNativeCheck() { }

    public static native long[] nativeRecalibrate(long gainA, long gainB,
                                                  long calibrationA, long calibrationB);
    private static native String nativeProvenance();

    /** Runs the actual JNI bridge each time; no cached or fabricated PASS state. */
    public static Report run() {
        StringBuilder details = new StringBuilder();
        int passed = 0;
        String provenance = "Native library not loaded";
        try {
            System.loadLibrary("hasselblad_wb_jni");
            provenance = nativeProvenance();
            for (int i = 0; i < VECTORS.length; i++) {
                long[] vector = VECTORS[i];
                long[] actual = nativeRecalibrate(vector[0], vector[1], vector[2], vector[3]);
                boolean match = actual != null && actual.length == 5
                        && actual[0] == vector[4] && actual[1] == 0 && actual[2] == 0
                        && actual[3] == vector[5] && actual[4] == vector[6];
                if (match) passed++;
                details.append(match ? "PASS  " : "FAIL  ").append(NAMES[i]).append('\n')
                        .append("Gain A/B: ").append(vector[0]).append(" / ").append(vector[1]).append('\n')
                        .append("Calibration A/B: ").append(vector[2]).append(" / ").append(vector[3]).append('\n')
                        .append("Expected output: ").append(vector[5]).append(" / ").append(vector[6]).append('\n');
                if (actual != null && actual.length == 5) {
                    details.append("Actual output: ").append(actual[3]).append(" / ").append(actual[4])
                            .append("; adapter status ").append(actual[0]).append('\n');
                } else {
                    details.append("Invalid JNI response\n");
                }
                details.append('\n');
            }
        } catch (LinkageError | RuntimeException failure) {
            details.append("Native check could not finish: ")
                    .append(failure.getClass().getSimpleName()).append(": ")
                    .append(failure.getMessage()).append('\n');
        }
        return new Report(passed, VECTORS.length, provenance, details.toString());
    }

    public static final class Report {
        public final int passed;
        public final int total;
        public final String provenance;
        public final String details;

        private Report(int passed, int total, String provenance, String details) {
            this.passed = passed;
            this.total = total;
            this.provenance = provenance;
            this.details = details;
        }

        public boolean allPassed() { return passed == total; }

        public String summary() {
            return (allPassed() ? "PASS" : "NOT PASSED") + " — " + passed + "/" + total
                    + " native checks passed";
        }

        public String asText() {
            return summary() + "\n" + SCOPE + "\n\n" + provenance
                    + "\n\n10 original-routine output vectors and 4 adapter guard cases.\n"
                    + "Adapter status 1 rejects a zero divisor; status 2 rejects shift overflow.\n"
                    + "These are adapter statuses, not vendor return codes.\n\n" + details;
        }
    }
}
