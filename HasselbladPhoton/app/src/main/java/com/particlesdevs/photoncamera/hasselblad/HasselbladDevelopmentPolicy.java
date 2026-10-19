package com.particlesdevs.photoncamera.hasselblad;

import android.util.Size;

import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.settings.PreferenceKeys;
import com.particlesdevs.photoncamera.settings.SettingsManager;

import java.util.Locale;

/** Capture limits for this standalone development checkpoint, not a camera look. */
public final class HasselbladDevelopmentPolicy {
    private static volatile String requestedRawMode = "RAW stream has not been configured yet.";
    private static volatile String deliveredRawMode = "No RAW frame has been delivered during this app session.";

    private HasselbladDevelopmentPolicy() { }

    public static boolean isEnabled() { return true; }

    public static void applyPreferences(SettingsManager manager) {
        if (!isEnabled()) return;
        String scope = PreferenceKeys.SCOPE_GLOBAL;
        manager.set(scope, PreferenceKeys.Key.KEY_FRAME_COUNT, 1);
        manager.set(scope, PreferenceKeys.Key.CAMERA_MODE, CameraMode.PHOTO.ordinal());
        // In Photon, HDRX selects RAW input. It does not itself enable HDR output.
        manager.set(scope, PreferenceKeys.Key.KEY_HDRX, true);
        manager.set(scope, PreferenceKeys.Key.KEY_HDRX_NR, false);
        manager.set(scope, PreferenceKeys.Key.KEY_ULTRAHDR, false);
        manager.set(scope, PreferenceKeys.Key.KEY_BRACKETING_MODE, 0);
        manager.set(scope, PreferenceKeys.Key.KEY_QUAD_BAYER, false);
        manager.set(scope, PreferenceKeys.Key.KEY_REMOSAIC, false);
        manager.set(scope, PreferenceKeys.Key.KEY_BINNING, false);
        manager.set(scope, PreferenceKeys.Key.KEY_SAVE_HEIC, false);
    }

    /** Selects an advertised standard RAW size, never a fabricated 12 MP mode. */
    public static Size chooseInitialRawSize(Size[] advertised) {
        if (advertised == null) return null;
        int[][] dimensions = new int[advertised.length][];
        for (int i = 0; i < advertised.length; i++) {
            if (advertised[i] != null) {
                dimensions[i] = new int[]{advertised[i].getWidth(), advertised[i].getHeight()};
            }
        }
        int chosen = HasselbladRawSizeSelector.chooseIndex(dimensions);
        return chosen >= 0 ? advertised[chosen] : null;
    }

    public static void recordRequestedRawSize(Size size, String physicalId) {
        requestedRawMode = String.format(Locale.US,
                "Requested standard RAW: %d × %d (%.2f MP), camera %s. Actual delivered data still needs device validation.",
                size.getWidth(), size.getHeight(),
                (long) size.getWidth() * size.getHeight() / 1000000.0, physicalId);
    }

    public static void recordDeliveredRawImage(int width, int height, int format,
                                              int rowStride, int pixelStride, long timestamp) {
        deliveredRawMode = String.format(Locale.US,
                "Latest delivered RAW: %d × %d (%.2f MP), format %d, row stride %d, pixel stride %d, sensor timestamp %d ns. These are buffer facts, not colour-calibration validation.",
                width, height, (long) width * height / 1000000.0,
                format, rowStride, pixelStride, timestamp);
    }

    public static String captureSummary() {
        return "Development capture: PHOTO, one RAW input frame, SDR output. "
                + "Bracketing, stacking, video and maximum-resolution modes are disabled. "
                + "The standard advertised RAW stream nearest 12.5 MP is preferred.\n\n"
                + requestedRawMode + "\n\n" + deliveredRawMode;
    }
}
