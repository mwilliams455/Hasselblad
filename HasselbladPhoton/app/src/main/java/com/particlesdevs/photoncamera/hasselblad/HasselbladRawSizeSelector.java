package com.particlesdevs.photoncamera.hasselblad;

/** Chooses only among advertised dimensions. This never manufactures a RAW mode. */
public final class HasselbladRawSizeSelector {
    private static final long INITIAL_RAW_PIXELS = 12500000L;

    private HasselbladRawSizeSelector() { }

    public static int chooseIndex(int[][] dimensions) {
        if (dimensions == null) return -1;
        int chosen = -1;
        long bestDifference = Long.MAX_VALUE;
        long chosenPixels = Long.MAX_VALUE;
        for (int i = 0; i < dimensions.length; i++) {
            int[] size = dimensions[i];
            if (size == null || size.length < 2 || size[0] <= 0 || size[1] <= 0) continue;
            long pixels = (long) size[0] * size[1];
            long difference = Math.abs(pixels - INITIAL_RAW_PIXELS);
            if (difference < bestDifference
                    || (difference == bestDifference && pixels < chosenPixels)) {
                chosen = i;
                bestDifference = difference;
                chosenPixels = pixels;
            }
        }
        return chosen;
    }
}
