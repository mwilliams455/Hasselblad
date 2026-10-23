package com.particlesdevs.photoncamera.hasselblad;

import java.io.File;
import java.util.Arrays;

/** Synthetic DNG GainMap->CFA demosaic->TWO genuine Stage24 JNI tile passes. */
public final class Stage36NativeDngSmoke {
    private static int checks;
    private static void require(boolean ok, String label) {
        if (!ok) throw new AssertionError(label);
        checks++;
    }
    private static double[] sentinel() {
        double[] x = new double[3072];Arrays.fill(x,77.);return x;
    }
    public static void main(String[] args) throws Exception {
        System.loadLibrary("hasselblad_colour_reference_jni");
        File root = new File(args[0]);
        var dng = HasselbladDngTileReader.read(new File(root,"gains.dng"));
        require(dng.gainMapCount == 4, "4 synthetic GainMaps");
        require(dng.cameraLinearTile.length == 3072, "1024 linear camera pixels");
        require(dng.forwardMatrix1 != null, "synthetic ForwardMatrix");
        double[] originalNeutral = {.62,1.,.349609375};
        double[] effectiveNeutral = {.62,1.,.3525390625};
        double[] original = sentinel();
        double[] effective = sentinel();
        int status0 = HasselbladColourReferenceCheck.nativeLinearTile(
                dng.forwardMatrix1,dng.forwardMatrix2,dng.calibration1,
                dng.calibration2,dng.analogBalance,originalNeutral,
                0,dng.cameraLinearTile,1024,original);
        int status1 = HasselbladColourReferenceCheck.nativeLinearTile(
                dng.forwardMatrix1,dng.forwardMatrix2,dng.calibration1,
                dng.calibration2,dng.analogBalance,effectiveNeutral,
                0,dng.cameraLinearTile,1024,effective);
        require(status0==0, "native original neutral accepted");
        require(status1==0, "native Photon neutral accepted");
        require(original[0]!=77 && effective[0]!=77, "native writes new data");
        var diff=HasselbladDualNeutralMath36.compare(original,effective);
        require(diff.differencesDetected,"different native PCS tiles");
        require(diff.overallRmse>0.000001,"measurable native delta");
        require(Double.isFinite(diff.overallMeanAbsoluteDelta),"finite native delta");
        require(diff.originalsNegative==0&&diff.effectiveNegative==0,"synthetic positive");
        require(diff.originalsOverUnity>0 || diff.effectiveOverUnity>0,"Stage24 preserves over-range linear output");
        double[] repeat = sentinel();
        int statusRepeat = HasselbladColourReferenceCheck.nativeLinearTile(
                dng.forwardMatrix1,dng.forwardMatrix2,dng.calibration1,
                dng.calibration2,dng.analogBalance,effectiveNeutral,
                0,dng.cameraLinearTile,1024,repeat);
        require(statusRepeat==0&&Arrays.equals(repeat,effective),"native deterministic repeat");
        var zero=HasselbladDualNeutralMath36.compare(effective,repeat);
        require(zero.overallMaxAbsoluteDelta==0,"identical neutral yields zero difference");
        var mismatched=HasselbladDngTileReader.read(new File(root,"dual_mismatch.dng"));
        double[] untouched = sentinel();
        int reject=HasselbladColourReferenceCheck.nativeLinearTile(
                mismatched.forwardMatrix1,mismatched.forwardMatrix2,
                mismatched.calibration1,mismatched.calibration2,
                mismatched.analogBalance,effectiveNeutral,0,
                mismatched.cameraLinearTile,1024,untouched);
        require(reject==3,"dual profile invalid result rejected");
        for(double x:untouched)if(x!=77.)throw new AssertionError("rejected tile modified");
        checks++;
        require(Arrays.equals(dng.cameraLinearTile,
                HasselbladDngTileReader.read(new File(root,"gains.dng")).cameraLinearTile),
                "input DNG tile unmodified");
        System.out.println("{\"schema\":\"hasselblad-stage36-host-native-two-neutral-DNG-v1\",\"status\":\"PASS\",\"checks\":"
            + checks + ",\"actual_original_photos_used\":false,\"tile_pixels\":1024,\"same_DNG_raw_input_for_both_native_calls\":true,\"stage24_PCS_only\":true,\"colour_error_or_deltaE_measured\":false,\"HNCS_equivalence_proven\":false,\"saved_photo_renderer_modified\":false}");
    }
}
