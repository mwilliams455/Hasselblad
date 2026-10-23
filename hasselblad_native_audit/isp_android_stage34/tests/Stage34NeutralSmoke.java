package com.particlesdevs.photoncamera.hasselblad;

/** Compiled with standard JDK. All fixtures synthetic, no private photo data. */
public final class Stage34NeutralSmoke {
    private static int checks=0;
    private static void ok(boolean value){if(!value)throw new AssertionError("stage34_check_"+checks);checks++;}
    private static void error(Runnable task){
        try {task.run();throw new AssertionError("expected_stage34_validation_exception");}
        catch(IllegalArgumentException expected){checks++;}
    }
    public static void main(String[] args) {
        double[] raw={.50,1,.30}, effective={.50,1,.303},
                 dngEffective={.50,1,.303}, dngOriginal={.50,1,.30};
        HasselbladNeutralCompare34.Comparison c=HasselbladNeutralCompare34.compareNeutrals(dngEffective,raw,effective);
        ok(c.matchesEffective);ok(!c.matchesOriginal);ok(c.originalAndEffectiveDistinct);
        ok("MATCHES_PHOTON_EFFECTIVE_ONLY".equals(c.classification));
        ok(Math.abs(c.maxAbsDifferenceToOriginal-.003)<1e-10);
        c=HasselbladNeutralCompare34.compareNeutrals(dngOriginal,raw,effective);
        ok(c.matchesOriginal);ok(!c.matchesEffective);
        ok("MATCHES_ORIGINAL_CAMERA2_ONLY".equals(c.classification));
        c=HasselbladNeutralCompare34.compareNeutrals(new double[]{.50,1,.307},raw,effective);
        ok("MATCHES_NEITHER".equals(c.classification));
        c=HasselbladNeutralCompare34.compareNeutrals(raw,raw,raw);
        ok("MATCHES_BOTH_INDISTINGUISHABLE".equals(c.classification));
        ok(!c.originalAndEffectiveDistinct);
        c=HasselbladNeutralCompare34.compareNeutrals(new double[]{.50,1,.300119},raw,effective);
        ok(c.matchesOriginal);ok(!c.matchesEffective);
        c=HasselbladNeutralCompare34.compareNeutrals(new double[]{.50,1,.3028809},raw,effective);
        ok(c.matchesEffective);ok(!c.matchesOriginal);
        c=HasselbladNeutralCompare34.compareNeutrals(new double[]{.50,1,.3015},raw,effective);
        ok("MATCHES_NEITHER".equals(c.classification));
        error(()->HasselbladNeutralCompare34.compareNeutrals(null,raw,effective));
        error(()->HasselbladNeutralCompare34.compareNeutrals(new double[2],raw,effective));
        error(()->HasselbladNeutralCompare34.compareNeutrals(new double[]{.5,0,.3},raw,effective));
        error(()->HasselbladNeutralCompare34.compareNeutrals(new double[]{Double.NaN,1,.3},raw,effective));
        error(()->HasselbladNeutralCompare34.compareNeutrals(new double[]{.5,1,Double.POSITIVE_INFINITY},raw,effective));
        error(()->HasselbladNeutralCompare34.compareNeutrals(new double[]{.5,1,-.3},raw,effective));
        double[] m={1,0,0,0,1,0,0,0,1},t=m.clone(),u=m.clone();
        ok("MATCHES_BOTH".equals(HasselbladNeutralCompare34.compareOptionalMatrix(m,t,u)));
        t[0]+=.02;
        ok("MATCHES_EFFECTIVE_ONLY".equals(HasselbladNeutralCompare34.compareOptionalMatrix(m,t,u)));
        u[2]+=.02;
        ok("MATCHES_NEITHER".equals(HasselbladNeutralCompare34.compareOptionalMatrix(m,t,u)));
        t=m.clone();
        ok("MATCHES_ORIGINAL_ONLY".equals(HasselbladNeutralCompare34.compareOptionalMatrix(m,t,u)));
        ok("DNG_TAG_ABSENT".equals(HasselbladNeutralCompare34.compareOptionalMatrix(null,t,u)));
        ok("SIDECAR_FIELD_MISSING".equals(HasselbladNeutralCompare34.compareOptionalMatrix(m,null,u)));
        error(()->HasselbladNeutralCompare34.maxAbsoluteDifference(m,new double[3],9));
        error(()->HasselbladNeutralCompare34.maxAbsoluteDifference(new double[]{Double.NaN,1,0},new double[]{1,1,1},3));
        ok(HasselbladNeutralCompare34.MATRIX_ABSOLUTE_TOLERANCE < .001);
        ok(HasselbladNeutralCompare34.NEUTRAL_ABSOLUTE_TOLERANCE < .0002);
        System.out.println("{\"schema\":\"hasselblad-stage34-WB-provenance-synthetic-v1\",\"status\":\"PASS\",\"checks\":"+checks+
             ",\"input_is_synthetic\":true,\"real_DNG_metadata_verified\":false,\"saved_photo_renderer_unchanged\":true,\"HNCS_equivalence_proven\":false}");
    }
}
