package com.particlesdevs.photoncamera.hasselblad;

import java.util.Arrays;

/** Source-independent tests of the bounded Stage36 linear delta aggregator. */
public final class Stage36MathSmoke {
    private static int checks;
    private static void must(boolean cond, String label) {
        if (!cond) throw new AssertionError(label);
        checks++;
    }
    private static void near(double a, double b, double tol, String name) {
        must(Math.abs(a - b) <= tol, name);
    }
    private static double[] constant(double r, double g, double b) {
        double[] v = new double[3072];
        for (int i=0;i<1024;i++) {v[i*3] = r;v[i*3+1] = g;v[i*3+2] = b;}
        return v;
    }
    public static void main(String[] args) {
        double[] a = constant(0.3, 0.4, 0.5), b = constant(0.31, 0.38, 0.53);
        HasselbladDualNeutralMath36.Result d = HasselbladDualNeutralMath36.compare(a,b);
        near(d.meanSignedEffectiveMinusOriginal[0], .01, 1e-14, "red signed");
        near(d.meanSignedEffectiveMinusOriginal[1], -.02, 1e-14, "green signed");
        near(d.meanSignedEffectiveMinusOriginal[2], .03, 1e-14, "blue signed");
        near(d.meanAbsoluteDelta[0], .01, 1e-14, "red MAE");
        near(d.meanAbsoluteDelta[1], .02, 1e-14, "green MAE");
        near(d.meanAbsoluteDelta[2], .03, 1e-14, "blue MAE");
        near(d.p95AbsoluteDelta[0], .01, 1e-14, "red P95");
        near(d.p95AbsoluteDelta[1], .02, 1e-14, "green P95");
        near(d.p95AbsoluteDelta[2], .03, 1e-14, "blue P95");
        near(d.overallMeanAbsoluteDelta, .02, 1e-14, "aggregate MAE");
        near(d.overallRmse, Math.sqrt((.01*.01+.02*.02+.03*.03)/3), 1e-14, "aggregate RMSE");
        near(d.overallP95AbsoluteDelta, .03, 1e-14, "aggregate P95");
        near(d.overallMaxAbsoluteDelta, .03, 1e-14, "aggregate max");
        must(d.differencesDetected, "nonzero differences");
        must(d.originalsNegative == 0 && d.effectiveNegative == 0, "negative counters");
        must(d.originalsOverUnity == 0 && d.effectiveOverUnity == 0, "highlight counters");
        double[] c = a.clone();
        HasselbladDualNeutralMath36.Result same = HasselbladDualNeutralMath36.compare(a,c);
        must(!same.differencesDetected, "same values unchanged");
        near(same.overallRmse,0.,0.,"same RMSE");
        near(same.overallP95AbsoluteDelta,0.,0.,"same P95");
        try {HasselbladDualNeutralMath36.compare(a,a); throw new AssertionError("alias accepted");}
        catch(IllegalArgumentException expected){checks++;}
        try {HasselbladDualNeutralMath36.compare(a,new double[300]); throw new AssertionError("short array accepted");}
        catch(IllegalArgumentException expected){checks++;}
        try {HasselbladDualNeutralMath36.compare(null,b); throw new AssertionError("null accepted");}
        catch(IllegalArgumentException expected){checks++;}
        double[] n = a.clone(); n[123] = Double.NaN;
        try {HasselbladDualNeutralMath36.compare(n,b); throw new AssertionError("NaN accepted");}
        catch(IllegalArgumentException expected){checks++;}
        n[123] = Double.POSITIVE_INFINITY;
        try {HasselbladDualNeutralMath36.compare(n,b); throw new AssertionError("Infinity accepted");}
        catch(IllegalArgumentException expected){checks++;}
        n[123] = 1e7;
        try {HasselbladDualNeutralMath36.compare(n,b); throw new AssertionError("huge accepted");}
        catch(IllegalArgumentException expected){checks++;}
        double[] over = constant(-.1,1.2,.5);
        HasselbladDualNeutralMath36.Result out = HasselbladDualNeutralMath36.compare(over,b);
        must(out.originalsNegative == 1024 && out.originalsOverUnity == 1024, "original clip counters");
        must(out.effectiveNegative == 0 && out.effectiveOverUnity == 0,"effective clip counters");
        double[] unique = constant(.1,.2,.3);
        for(int i=0;i<1024;i++)unique[i*3] = i < 973 ? .1 : .5;
        var percentile=HasselbladDualNeutralMath36.compare(constant(.1,.2,.3),unique);
        near(percentile.p95AbsoluteDelta[0],0,0,"per-channel nearest rank 95 pct");
        must(Arrays.equals(a,constant(.3,.4,.5)),"first input unchanged");
        must(Arrays.equals(b,constant(.31,.38,.53)),"second input unchanged");
        System.out.println("{\"schema\":\"hasselblad-stage36-aggregates-synthetic-v1\",\"status\":\"PASS\",\"checks\":"+checks+",\"original_images_used\":false,\"HNCS_equivalence_proven\":false,\"photo_save_changed\":false}");
    }
}
