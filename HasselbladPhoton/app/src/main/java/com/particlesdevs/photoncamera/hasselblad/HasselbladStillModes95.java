package com.particlesdevs.photoncamera.hasselblad;

import com.particlesdevs.photoncamera.api.CameraMode;

/** Supported still modes and explicit picker mapping; enum ordinals are persisted, not UI indices. */
public final class HasselbladStillModes95 {
    private HasselbladStillModes95() {}
    public static boolean supports(CameraMode mode) {
        return mode==CameraMode.PHOTO || mode==CameraMode.MOTION;
    }
    public static int allowedOrdinal(int saved) {
        return saved==CameraMode.MOTION.ordinal()?saved:CameraMode.PHOTO.ordinal();
    }
    public static CameraMode at(int pickerIndex) {
        return pickerIndex==1?CameraMode.MOTION:CameraMode.PHOTO;
    }
    public static int indexOf(int savedOrdinal) {
        return savedOrdinal==CameraMode.MOTION.ordinal()?1:0;
    }
}
