package com.particlesdevs.photoncamera.hasselblad;

/** No vendor library is loaded; both configured Android ABIs build this core. */
public final class HasselbladRenderer42 {
    static { System.loadLibrary("hasselblad_renderer42_jni"); }
    private HasselbladRenderer42() {}
    public static native short[] render(short[] input, double[] parameters,
        double[] grid, float[] curve, int gridWidth, int gridHeight, int wbOwner);
    public static native double[] cameraToD50(double[] fm1,double[] fm2,double[] cc1,
        double[] cc2,double[] analog,double[] neutral);
    public static native double[] xyzToSrgb();
    /** CPU reconstruction on the reader's already clipped prepared RGB16.
     * Equal lower gains require explicit permission for the Stage53 limit. */
    public static native short[] reconstructHighlights(short[] input,double[] gainRatios,
        boolean allowEqualGainLimit);
}
