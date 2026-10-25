package com.particlesdevs.photoncamera.hasselblad;

/** Bounded experimental C/JNI internal-linear-RGB16 research entry point.
 *  PREPARED RGGB Bayer with explicit 32px halo. NOT a full DNG decoder,
 *  Phocus display-colour profile, Android camera capture path, or JPEG.
 *  The caller MUST use the supported Stage73 measurement-based tile sizes.
 */
public final class HasselbladFinalRaw74 {
    static { System.loadLibrary("hbfinal74"); }
    private HasselbladFinalRaw74() {}
    /** On success, output contains interleaved linear RGB16 code values.
     *  Java short[] carries *unsigned* uint16 bit patterns. On any error the
     *  caller's output array is unchanged. Returns zero on success.
     */
    public static native int renderLinearRgb16Native(short[] preparedBayerWithHalo,
        int inputStride, int outputWidth, int outputHeight, int cfa, short[] resultRgb16);
}
