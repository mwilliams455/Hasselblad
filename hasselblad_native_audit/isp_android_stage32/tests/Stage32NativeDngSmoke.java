package com.particlesdevs.photoncamera.hasselblad;

import java.io.File;
import java.util.Arrays;

/** Exact Java->Stage26 native PCS bridge on an actual decoded synthetic DNG tile. */
public final class Stage32NativeDngSmoke {
    public static void main(String[] args)throws Exception {
        System.loadLibrary("hasselblad_colour_reference_jni");
        File root=new File(args[0]);
        var p=HasselbladDngTileReader.read(new File(root,"gains.dng"));
        double[] converted=new double[3072];Arrays.fill(converted,25.);
        int status=HasselbladColourReferenceCheck.nativeLinearTile(
                p.forwardMatrix1,p.forwardMatrix2,p.calibration1,p.calibration2,
                p.analogBalance,p.asShotNeutral,0,p.cameraLinearTile,1024,converted);
        if(status!=0) throw new AssertionError("JNI real synthetic DNG tile failed: "+status);
        double sum=0;for(double x:converted){
            if(!Double.isFinite(x)||x==25.)throw new AssertionError("invalid PCS output");
            sum+=x;
        }
        if(!(sum>100 && sum<10000))throw new AssertionError("implausible PCS aggregate");
        var dual=HasselbladDngTileReader.read(new File(root,"dual_mismatch.dng"));
        double[] untouched=new double[3072];Arrays.fill(untouched,25.);
        int reject=HasselbladColourReferenceCheck.nativeLinearTile(
                dual.forwardMatrix1,dual.forwardMatrix2,dual.calibration1,
                dual.calibration2,dual.analogBalance,dual.asShotNeutral,
                0,dual.cameraLinearTile,1024,untouched);
        if(reject!=3)throw new AssertionError("Dual interpolation should fail closed "+reject);
        for(double x:untouched)if(x!=25.)throw new AssertionError("Native wrote rejected output");
        System.out.println("{\"schema\":\"hasselblad-stage32-host-synthetic-DNG-native-tile-v1\",\"status\":\"PASS\",\"checks\":5,\"tile_pixels\":1024,\"original_photos_used\":false,\"HNCS_pixel_equivalence_proven\":false,\"phone_photo_output_modified\":false}");
    }
}
