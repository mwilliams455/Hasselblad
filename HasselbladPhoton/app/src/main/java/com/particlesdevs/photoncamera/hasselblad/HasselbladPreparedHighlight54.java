package com.particlesdevs.photoncamera.hasselblad;

import java.util.Arrays;

/** Experimental bridge for Stage43 prepared RGB, after gain maps/demosaic/clamp.
 * This does not reconstruct the original Phocus RAW graph or lost RAW headroom.
 * Only the selected DNG's neutral and matrix enter this bridge. */
public final class HasselbladPreparedHighlight54 {
    private HasselbladPreparedHighlight54() {}

    public static final class Plan {
        public final double[] gainRatios,afterMatrix;
        public final boolean analyticEqualGainLimit;
        private Plan(double[] gains,double[] after,boolean limit) {
            gainRatios=gains;afterMatrix=after;analyticEqualGainLimit=limit;
        }
        public short[] reconstruct(short[] preparedRgb16) {
            return HasselbladRenderer42.reconstructHighlights(preparedRgb16,gainRatios,true);
        }
    }

    public static Plan prepare(double[] cameraToD50,double[] neutral) {
        if(cameraToD50==null||cameraToD50.length!=9||neutral==null||neutral.length!=3)
            throw new IllegalArgumentException("Missing DNG highlight calibration");
        double smallest=Double.POSITIVE_INFINITY;
        for(double n:neutral) {
            if(!Double.isFinite(n)||n<=0)throw new IllegalArgumentException("Invalid DNG neutral");
            smallest=Math.min(smallest,n);
        }
        double[] gains=new double[3],after=new double[9];
        for(int c=0;c<3;c++) {
            gains[c]=smallest/neutral[c];
            if(!Double.isFinite(gains[c])||gains[c]<=0)
                throw new IllegalArgumentException("DNG neutral ratios outside supported range");
            for(int r=0;r<3;r++) {
                after[r*3+c]=cameraToD50[r*3+c]/gains[c];
                if(!Double.isFinite(after[r*3+c]))
                    throw new IllegalArgumentException("Invalid DNG highlight transform");
            }
        }
        double[] sorted=gains.clone();Arrays.sort(sorted);
        return new Plan(gains,after,sorted[0]==sorted[1]);
    }
}
