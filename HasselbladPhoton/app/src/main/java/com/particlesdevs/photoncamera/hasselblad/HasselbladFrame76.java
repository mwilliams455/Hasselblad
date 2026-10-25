package com.particlesdevs.photoncamera.hasselblad;
import java.io.IOException;
import java.util.Arrays;
/** Streaming 64-row assembly of the real-neighbour sensor interior. No border synthesis. */
public final class HasselbladFrame76 {
    static {System.loadLibrary("hbframe76");}
    private HasselbladFrame76() {}
    public static native int renderBandNative(short[] preparedRows,int rawWidth,int rowOffset,int rowCount,short[] output);
    public static int width(int raw){if(raw<128||raw>8192)throw new IllegalArgumentException("Unsupported RAW dimensions");return (raw-64)&~1;}
    public static short[] band(short[] prepared,int rawWidth,int rawHeight,int y)throws IOException {
        int w=width(rawWidth),h=width(rawHeight);
        if((long)rawWidth*rawHeight>16777216L||prepared==null||prepared.length!=(long)rawWidth*rawHeight||y<0||y>=h||(y&1)!=0)
            throw new IOException("Invalid sensor-interior band");
        if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
        int rows=Math.min(64,h-y),anchor=Math.min(y,h-64);
        short[] source=Arrays.copyOfRange(prepared,anchor*rawWidth,(anchor+128)*rawWidth);
        short[] out=new short[w*rows*3];
        int code=renderBandNative(source,rawWidth,y-anchor,rows,out);
        if(code!=0)throw new IOException("Scene band rejected: "+code);
        if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
        return out;
    }
    /** Short integration check runs automatically, not a new user test sequence. */
    public static void selfCheck()throws IOException {
        int w=226,h=210;short[] raw=new short[w*h];
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)raw[y*w+x]=(short)((x*331+y*97+(x*y)%1237)&65535);
        for(int by:new int[]{0,64,128}) {
            short[] row=band(raw,w,h,by);int count=Math.min(64,width(h)-by),ay=Math.min(by,width(h)-64);
            for(int x:new int[]{0,64,128}) {
                int ax=Math.min(x,width(w)-64),cols=Math.min(64,width(w)-x);
                short[] input=new short[128*128];
                for(int yy=0;yy<128;yy++)System.arraycopy(raw,(ay+yy)*w+ax,input,yy*128,128);
                short[] expected=HasselbladDevice75Buffers.render(input,64,64);
                for(int yy=0;yy<count;yy++)for(int xx=0;xx<cols;xx++)for(int c=0;c<3;c++)
                    if(row[(yy*width(w)+x+xx)*3+c]!=expected[((yy+by-ay)*64+x-ax+xx)*3+c])throw new IOException("Scene-band integration mismatch");
            }
        }
    }
}
