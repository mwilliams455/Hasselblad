package com.particlesdevs.photoncamera.hasselblad;

/** Deterministic, dependency-free bounds for one optional GPU observation.
 * No image processing, colour calibration, or threshold fitting lives here. */
public final class HasselbladStage6Contract {
    public static final int GRID = 4;
    public static final int PATCH = 8;
    public static final int PATCH_COUNT = GRID * GRID;
    public static final int SAMPLES = PATCH_COUNT * PATCH * PATCH;
    public static final int MAX_PIXELS = 32000000;

    private HasselbladStage6Contract() { }

    public static boolean supported(int width, int height, int cfa,
                                    int sourceFrames, boolean cropped,
                                    boolean processed, boolean bayerRgb,
                                    float[] whitePoint) {
        if (width < 64 || height < 64 || width > 16384 || height > 16384
                || (long)width * height > MAX_PIXELS
                || (width & 1) != 0 || (height & 1) != 0
                || cfa != 0 || sourceFrames != 1 || cropped || processed
                || !bayerRgb || whitePoint == null || whitePoint.length != 3)
            return false;
        for (float v : whitePoint)
            if (!Float.isFinite(v) || v <= 0f || v > 8f) return false;
        return true;
    }

    /** All patches are 2-pixel-aligned, inside the texture and in FB order.
     * Coordinates use the GPU frame-buffer origin (bottom left). RAW file
     * row orientation is intentionally not inferred from these coordinates.
     */
    public static int[] patchRect(int width, int height, int index) {
        if (index < 0 || index >= PATCH_COUNT || width < 64 || height < 64 ||
                (width & 1) != 0 || (height & 1) != 0)
            throw new IllegalArgumentException("Invalid Stage6 patch geometry");
        int gx = index % GRID;
        int gy = index / GRID;
        int cx = (int)(((long)(2 * gx + 1) * width) / (2 * GRID));
        int cy = (int)(((long)(2 * gy + 1) * height) / (2 * GRID));
        int x = Math.max(0, Math.min(width - PATCH, (cx - PATCH / 2) & ~1));
        int y = Math.max(0, Math.min(height - PATCH, (cy - PATCH / 2) & ~1));
        return new int[]{x, y, PATCH, PATCH};
    }
}
