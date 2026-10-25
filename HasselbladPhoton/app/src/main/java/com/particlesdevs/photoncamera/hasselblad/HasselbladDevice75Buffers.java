package com.particlesdevs.photoncamera.hasselblad;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;

/** Platform-independent bytes and invariant checks, exercised by host JVM and Android. */
public final class HasselbladDevice75Buffers {
    private HasselbladDevice75Buffers() {}
    public static short[] decode(InputStream in,int count)throws IOException {
        if(in==null||count<0||count>65536)throw new IOException("Invalid fixture");
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] block=new byte[4096];int n;
        while((n=in.read(block))!=-1){if(out.size()+n>count*2)throw new IOException("Wrong fixture length");out.write(block,0,n);}
        if(out.size()!=count*2)throw new IOException("Truncated fixture");
        ByteBuffer b=ByteBuffer.wrap(out.toByteArray()).order(ByteOrder.LITTLE_ENDIAN);
        short[] values=new short[count];b.asShortBuffer().get(values);return values;
    }
    public static byte[] encode(short[] values) {
        ByteBuffer b=ByteBuffer.allocate(values.length*2).order(ByteOrder.LITTLE_ENDIAN);
        b.asShortBuffer().put(values);return b.array();
    }
    public static int firstMismatch(short[] a,short[] b) {
        if(a.length!=b.length)return Math.min(a.length,b.length);
        for(int i=0;i<a.length;i++)if(a[i]!=b[i])return i;return -1;
    }
    public static short[] render(short[] bayer,int w,int h) throws IOException {
        if(Thread.currentThread().isInterrupted())throw new IOException("Device test cancelled");
        short[] original=bayer.clone(),output=new short[w*h*3];
        int status=HasselbladFinalRaw74.renderLinearRgb16Native(bayer,w+64,w,h,0,output);
        if(status!=0)throw new IOException("Stage74 native rejection "+status);
        if(!Arrays.equals(original,bayer))throw new IOException("Native input changed");
        if(Thread.currentThread().isInterrupted())throw new IOException("Device test cancelled");
        return output;
    }
    public static void rejectionChecks()throws IOException {
        short[] in=new short[128*128],out=new short[64*64*3];Arrays.fill(out,(short)0x9521);
        int[] status={
            HasselbladFinalRaw74.renderLinearRgb16Native(in,128,64,64,1,out),
            HasselbladFinalRaw74.renderLinearRgb16Native(in,128,65,64,0,out),
            HasselbladFinalRaw74.renderLinearRgb16Native(new short[10],128,64,64,0,out),
            HasselbladFinalRaw74.renderLinearRgb16Native(in,127,64,64,0,out),
            HasselbladFinalRaw74.renderLinearRgb16Native(in,128,64,64,0,in)};
        for(int code:status)if(code==0)throw new IOException("Malformed input accepted");
        for(short v:out)if(v!=(short)0x9521)throw new IOException("Rejected call changed output");
        for(short v:in)if(v!=0)throw new IOException("Rejected call changed input");
    }
}
