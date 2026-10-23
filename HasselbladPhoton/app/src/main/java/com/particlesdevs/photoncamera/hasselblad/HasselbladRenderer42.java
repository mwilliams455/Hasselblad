package com.particlesdevs.photoncamera.hasselblad;

/** No vendor library is loaded; both configured Android ABIs build this core. */
public final class HasselbladRenderer42 {
    static { System.loadLibrary("hasselblad_renderer42_jni"); }
    private HasselbladRenderer42() {}
    public static native short[] render(short[] input, double[] parameters,
        double[] grid, float[] curve, int gridWidth, int gridHeight, int wbOwner);
}
