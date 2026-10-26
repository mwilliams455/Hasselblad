package com.particlesdevs.photoncamera.hasselblad;
import java.io.IOException;
import java.util.Arrays;
public final class Frame96Check {
    private static void require(boolean b){if(!b)throw new AssertionError();}
    public static void main(String[] args)throws Exception {
        int w=642,h=194;short[] raw=new short[w*h];
        for(int i=0;i<raw.length;i++)raw[i]=(short)(i*197+(i/w)*331);
        for(int y:new int[]{0,64,128}) {
            require(Arrays.equals(HasselbladFrame77.band(raw,w,h,y,1),HasselbladFrame96.band(raw,w,h,y,4,new double[]{1,1,1})));
            require(Arrays.equals(HasselbladFrame96.band(raw,w,h,y,1,new double[]{.315,1,.678}),HasselbladFrame96.band(raw,w,h,y,4,new double[]{.63,2,1.356})));
        }
        for(double[] bad:new double[][]{null,{}, {1,1}, {0,1,1}, {Double.NaN,1,1}, {1,Double.POSITIVE_INFINITY,1}, {1,1,0}, {32,1,1}}) {
            try{HasselbladFrame96.band(raw,w,h,0,1,bad);throw new AssertionError();}catch(IOException expected){}
        }
        Thread.currentThread().interrupt();
        try{HasselbladFrame96.band(raw,w,h,0,1,new double[]{1,1,1});throw new AssertionError();}catch(IOException expected){}finally{Thread.interrupted();}
        short[] in=new short[w*128],out=new short[(w-64)*64*3];Arrays.fill(out,(short)123);
        require(HasselbladFrame96.renderBandNative(in,w,0,64,1,out,Double.NaN,1)==-2);
        for(short p:out)require(p==123);
        require(HasselbladFrame96.renderBandNative(in,w,0,64,1,in,1,1)==-1);
        System.out.println("PASS production Java/JNI bands, tail anchoring, neutral scaling, cancellation and invalid input");
    }
}
