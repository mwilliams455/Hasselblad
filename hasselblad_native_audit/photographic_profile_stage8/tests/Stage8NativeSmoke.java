import com.particlesdevs.photoncamera.hasselblad.HasselbladProfilePreparationCheck;

/** Plain JDK JNI smoke: no Android API or camera is involved. */
public final class Stage8NativeSmoke {
    public static void main(String[] args) {
        String json=HasselbladProfilePreparationCheck.run();
        System.out.println(json);
        if(!json.contains("\"status\":\"PASS\"") ||
           !json.contains("\"original_native_cases_passed\":12") ||
           !json.contains("\"fullsize_synthetic_cases_passed\":8") ||
           !json.contains("\"photographic_colour_still_photon\":true")) {
            throw new AssertionError("Stage8 host JNI parity or no-render contract failed");
        }
    }
}
