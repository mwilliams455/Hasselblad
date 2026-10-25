package com.particlesdevs.photoncamera.hasselblad;
import java.io.IOException;
import java.util.Arrays;
/** Streaming 64-row assembly of the real-neighbour sensor interior. No border synthesis. */
public final class HasselbladFrame77 {
    static {System.loadLibrary("hbframe77");}
    private HasselbladFrame77() {}
    public static native int renderBandNative(short[] preparedRows,int rawWidth,int rowOffset,int rowCount,int workers,short[] output);
    public static int width(int raw){if(raw<128||raw>8192)throw new IllegalArgumentException("Unsupported RAW dimensions");return (raw-64)&~1;}
    public static short[] band(short[] prepared,int rawWidth,int rawHeight,int y,int workers)throws IOException {
        int w=width(rawWidth),h=width(rawHeight);
        if((long)rawWidth*rawHeight>16777216L||prepared==null||prepared.length!=(long)rawWidth*rawHeight||y<0||y>=h||(y&1)!=0)
            throw new IOException("Invalid sensor-interior band");
        if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
        int rows=Math.min(64,h-y),anchor=Math.min(y,h-64);
        short[] source=Arrays.copyOfRange(prepared,anchor*rawWidth,(anchor+128)*rawWidth);
        short[] out=new short[w*rows*3];
        int code=renderBandNative(source,rawWidth,y-anchor,rows,workers,out);
        if(code!=0)throw new IOException("Scene band rejected: "+code);
        if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
        return out;
    }
    /** Quick on-device scheduling check; unchanged Stage76 is the reference. */
    public static void selfCheck(int workers)throws IOException {
        int w=642,h=194;short[] raw=new short[w*h];
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)raw[y*w+x]=(short)((x*331+y*97+(x*y)%1237)&65535);
        for(int by:new int[]{0,64,128})
            if(!Arrays.equals(band(raw,w,h,by,workers),HasselbladFrame76.band(raw,w,h,by)))
                throw new IOException("Stage77 scheduling differs from Stage76");
    }
}
