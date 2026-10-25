package com.particlesdevs.photoncamera.hasselblad;
/** Experimental diagnostic only: pre-ColorNoise RGGB intermediate buffer.
 * No image/colour profile conversion or normal capture route is changed.
 */
public final class HasselbladPreNoise73 {
    static { System.loadLibrary("hbframe73"); }
    private HasselbladPreNoise73() {}
    /** Returns 0 on success. Four unsigned-16 codes per pixel: R,G,B,mask.
     * Source must already contain a 32px Bayer halo, phase-aligned RGGB;
     * sourceStride is in uint16 elements and input.length>=stride*(height+64).
     */
    public static native int nativeRender(short[] paddedBayer, int width, int height,
        int sourceStride, int cfa, short[] rgbAndMask);
}
