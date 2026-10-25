package com.particlesdevs.photoncamera.hasselblad;

import java.io.IOException;
import java.nio.ByteBuffer;

/** Checks the observed uncropped RAW16 copy and removes only row padding. */
public final class HasselbladRawLayout79 {
    private HasselbladRawLayout79() {}
    public static void validate(int w,int h,int row,int pixel,int copiedW,int copiedH,
            long sourceCapacity,long copyCapacity,int copyOffset,int cropX,int cropY,
            boolean transformed,boolean fullImageCrop) throws IOException {
        if(w<128 || h<128 || w>8192 || h>8192 || (long)w*h>16777216)
            throw new IOException("Standard RAW dimensions required (up to 16 MP)");
        long required=(long)(h-1)*row+2L*w;
        if(pixel!=2 || row<2*w || (row&1)!=0 || copiedW!=row/2 || copiedH!=h
                || sourceCapacity<required || copyCapacity<required || copyOffset!=0
                || cropX!=0 || cropY!=0 || transformed || !fullImageCrop)
            throw new IOException("Uncropped RAW16 buffer required; turn off digital zoom and 16:9 crop");
    }
    /** Caller owns and frees dst. Neither source bytes nor position/limit are changed. */
    public static void copy(ByteBuffer source,ByteBuffer dst,int w,int h,int row) throws IOException {
        long required=(long)(h-1)*row+2L*w;
        if(w<=0 || h<=0 || row<2L*w || required>source.capacity() || (long)w*h*2>dst.capacity()
                || source==dst || dst.isReadOnly()) throw new IOException("Invalid RAW copy buffers");
        ByteBuffer in=source.duplicate(), out=dst.duplicate(); in.clear(); out.clear();
        for(int y=0;y<h;y++) {
            if(Thread.currentThread().isInterrupted()) throw new IOException("Capture cancelled");
            in.limit(source.capacity()); in.position(y*row); in.limit(y*row+w*2); out.put(in);
        }
    }
    public static int orientation(int degrees) throws IOException {
        switch(degrees) {case 0:return 1;case 90:return 6;case 180:return 3;case 270:return 8;
            default:throw new IOException("Unsupported capture rotation");}
    }
}
