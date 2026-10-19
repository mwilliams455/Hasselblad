import com.particlesdevs.photoncamera.hasselblad.HasselbladNativeCheck;
import com.particlesdevs.photoncamera.hasselblad.HasselbladRawSizeSelector;

/** Host checks for the real Java/JNI bridge and advertised-RAW selection policy. */
public final class CheckpointVerification {
    private static int checks;

    private static void expect(boolean condition, String message) {
        checks++;
        if (!condition) throw new AssertionError(message);
    }

    private static void expectRejected(long gainA, long gainB, long calibrationA, long calibrationB) {
        boolean rejected = false;
        try {
            HasselbladNativeCheck.nativeRecalibrate(gainA, gainB, calibrationA, calibrationB);
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        expect(rejected, "JNI must reject a value outside the unsigned 32-bit contract");
    }

    public static void main(String[] args) {
        HasselbladNativeCheck.Report report = HasselbladNativeCheck.run();
        expect(report.allPassed() && report.total == 14, report.asText());
        expect(report.provenance.contains("portable C reconstruction"), "Portable execution provenance missing");
        expectRejected(-1, 4096, 4096, 4096);
        expectRejected(4096, -1, 4096, 4096);
        expectRejected(4096, 4096, -1, 4096);
        expectRejected(4096, 4096, 4096, -1);
        expectRejected(4294967296L, 4096, 4096, 4096);
        expectRejected(4096, 4294967296L, 4096, 4096);
        expectRejected(4096, 4096, 4294967296L, 4096);
        expectRejected(4096, 4096, 4096, 4294967296L);

        expect(HasselbladRawSizeSelector.chooseIndex(
                new int[][]{{8192, 6144}, {4032, 3024}, {1920, 1080}}) == 1,
                "12 MP advertised RAW should be preferred over 50 MP");
        expect(HasselbladRawSizeSelector.chooseIndex(
                new int[][]{{4032, 3024}, {1920, 1080}, {8192, 6144}}) == 0,
                "Advertised size order must not change the selected size");
        expect(HasselbladRawSizeSelector.chooseIndex(
                new int[][]{{4096, 3072}, {4080, 3060}}) == 1,
                "Select the size nearest 12.5 MP, without forcing dimensions");
        expect(HasselbladRawSizeSelector.chooseIndex(new int[][]{{8000, 6000}}) == 0,
                "A camera exposing only a larger standard stream must retain that real size");
        expect(HasselbladRawSizeSelector.chooseIndex(
                new int[][]{null, {0, 3000}, {-1, 3000}, {4000}, {4000, 3000}}) == 4,
                "Malformed candidates must be ignored");
        expect(HasselbladRawSizeSelector.chooseIndex(new int[][]{null, {0, 3000}}) == -1,
                "No valid candidate must not fabricate a stream");
        expect(HasselbladRawSizeSelector.chooseIndex(new int[0][]) == -1,
                "Empty advertised sizes must have no selection");
        expect(HasselbladRawSizeSelector.chooseIndex(null) == -1,
                "Missing advertised sizes must have no selection");
        expect(HasselbladRawSizeSelector.chooseIndex(
                new int[][]{{100000, 100000}, {4000, 3000}}) == 1,
                "Pixel-area arithmetic must not overflow a 32-bit int");
        expect(HasselbladRawSizeSelector.chooseIndex(
                new int[][]{{5200, 2500}, {4800, 2500}}) == 1,
                "An equal-distance tie should select the smaller real stream");
        System.out.println(report.asText());
        System.out.println("HOST VERIFICATION PASS: " + checks + " assertions, including 14 native vectors, 8 JNI range checks and 10 RAW-selection cases.");
        System.out.println("This is a host JVM/JNI check, not Android device or camera validation.");
    }
}
