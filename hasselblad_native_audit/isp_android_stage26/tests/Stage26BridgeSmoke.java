import com.particlesdevs.photoncamera.hasselblad.HasselbladColourReferenceCheck;

/** Host Java/JNI integration probe, no Android framework or camera data. */
public final class Stage26BridgeSmoke {
    public static void main(String[] args) {
        String report = HasselbladColourReferenceCheck.run();
        System.out.println(report);
        if (!report.contains("\"status\":\"PASS\"")
                || !report.contains("\"tests_passed\":11")
                || !report.contains("\"input_is_synthetic\":true")
                || !report.contains("\"photographic_render_authorized\":false")
                || !report.contains("\"saved_photo_colour_still_photon\":true")
                || !report.contains("\"main_lut_hypothesis_invoked\":false")) {
            throw new AssertionError("Stage26 JNI bridge failed synthetic checks");
        }
    }
}
