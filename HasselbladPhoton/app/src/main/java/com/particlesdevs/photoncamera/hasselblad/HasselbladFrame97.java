package com.particlesdevs.photoncamera.hasselblad;
import java.io.IOException;
import java.util.Arrays;
/** Phocus demosaic with neutral adaptation and bounded local chroma correction. */
public final class HasselbladFrame97 {
    static {System.loadLibrary("hbframe97");}
    private HasselbladFrame97() {}
    public static native int renderBandNative(short[] preparedRows,int rawWidth,int rowOffset,int rowCount,int workers,short[] output,double redNeutral,double blueNeutral);
    public static int width(int raw){if(raw<128||raw>8192)throw new IllegalArgumentException("Unsupported RAW dimensions");return (raw-64)&~1;}
    public static short[] band(short[] prepared,int rawWidth,int rawHeight,int y,int workers,double[] neutral)throws IOException {
        if(neutral==null||neutral.length!=3)throw new IOException("Missing RAW neutral for chroma correction");
        for(double value:neutral)if(!Double.isFinite(value)||value<=0)
            throw new IOException("Invalid RAW neutral for chroma correction");
        int w=width(rawWidth),h=width(rawHeight);
        if((long)rawWidth*rawHeight>16777216L||prepared==null||prepared.length!=(long)rawWidth*rawHeight||y<0||y>=h||(y&1)!=0)
            throw new IOException("Invalid sensor-interior band");
        if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
        int rows=Math.min(64,h-y),anchor=Math.min(y,h-64);
        short[] source=Arrays.copyOfRange(prepared,anchor*rawWidth,(anchor+128)*rawWidth);
        short[] out=new short[w*rows*3];
        int code=renderBandNative(source,rawWidth,y-anchor,rows,workers,out,neutral[0]/neutral[1],neutral[2]/neutral[1]);
        if(code!=0)throw new IOException("Scene band rejected: "+code);
        if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
        return out;
    }
}
