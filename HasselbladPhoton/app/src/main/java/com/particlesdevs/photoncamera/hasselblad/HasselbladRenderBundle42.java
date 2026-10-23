package com.particlesdevs.photoncamera.hasselblad;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.util.Arrays;

/** Bounded, checksum-protected private preview import. Never writes a source RAW.
 * Contains prepared camera RGB, the explicit calibration, and a same-RAW baseline.
 * This is an experimental offline rendering input, not a general DNG decoder.
 */
public final class HasselbladRenderBundle42 {
    public static final int MAX_PIXELS=1048576, MAX_BYTES=16000000;
    public final int width,height,gridWidth,gridHeight,wbOwner,orientation;
    public final int temperature,model,film,space;
    public final double[] parameters=new double[38], grid;
    public final float[] curve=new float[65536];
    public final short[] input;
    public final int[] baseline;
    public final byte[] expected=new byte[32];
    private HasselbladRenderBundle42(byte[] data) throws Exception {
        if (data.length<400) throw new IOException("Incomplete preview file");
        MessageDigest sha=MessageDigest.getInstance("SHA-256");
        sha.update(data,0,data.length-32);
        if (!MessageDigest.isEqual(sha.digest(),Arrays.copyOfRange(data,data.length-32,data.length)))
            throw new IOException("Preview checksum failed");
        ByteBuffer b=ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic=new byte[8];b.get(magic);
        if (!Arrays.equals(magic,new byte[]{'H','B','4','2','R','A','W','1'}))
            throw new IOException("Choose a Stage42 .hb42 preview file");
        width=b.getInt();height=b.getInt();gridWidth=b.getInt();gridHeight=b.getInt();
        wbOwner=b.getInt();orientation=b.getInt();temperature=b.getInt();model=b.getInt();
        film=b.getInt();space=b.getInt();
        long n=(long)width*height, g=(long)gridWidth*gridHeight*2;
        if (width<1 || height<1 || width>2048 || height>2048 || n>MAX_PIXELS ||
            gridWidth<2 || gridWidth>256 || gridHeight<2 || gridHeight>256 ||
            wbOwner<0 || wbOwner>2 || (orientation!=1 && orientation!=6) ||
            temperature<2000 || temperature>10000 || model<0 || model>1 ||
            (film!=0 && film!=1 && film!=7) || space!=0)
            throw new IOException("Unsupported preview dimensions or configuration");
        long expectedLength=8+40+38*8+g*8+65536*4+64+n*9+32;
        if (expectedLength!=data.length) throw new IOException("Preview length mismatch");
        for (int i=0;i<38;i++) {
            parameters[i]=b.getDouble();
            if (!Double.isFinite(parameters[i]) || Math.abs(parameters[i])>1e6)
                throw new IOException("Invalid preview parameter");
        }
        if (parameters[37]<=0 || parameters[37]>8) throw new IOException("Invalid display transfer");
        grid=new double[(int)g];for(int i=0;i<grid.length;i++)grid[i]=b.getDouble();
        for(int i=0;i<curve.length;i++)curve[i]=b.getFloat();
        b.position(b.position()+32); // Private source SHA; do not export it in public reports.
        b.get(expected);
        input=new short[(int)n*3];for(int i=0;i<input.length;i++)input[i]=b.getShort();
        baseline=new int[(int)n];
        for(int i=0;i<baseline.length;i++)baseline[i]=0xff000000|
            ((b.get()&255)<<16)|((b.get()&255)<<8)|(b.get()&255);
    }
    public static HasselbladRenderBundle42 read(InputStream in) throws Exception {
        if(in==null)throw new IOException("Cannot open preview file");
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] chunk=new byte[65536];
        int count,total=0;
        while((count=in.read(chunk))!=-1) {
            total+=count;if(total>MAX_BYTES)throw new IOException("Preview file is too large");
            bytes.write(chunk,0,count);
        }
        return new HasselbladRenderBundle42(bytes.toByteArray());
    }
    public boolean matches(short[] rendered) throws Exception {
        if(rendered.length!=input.length)return false;
        MessageDigest sha=MessageDigest.getInstance("SHA-256");byte[] block=new byte[8192];
        int at=0;
        for(short x:rendered) {
            block[at++]=(byte)x;block[at++]=(byte)(x>>>8);
            if(at==block.length){sha.update(block);at=0;}
        }
        sha.update(block,0,at);return MessageDigest.isEqual(sha.digest(),expected);
    }
    public int[] display(short[] rendered) {
        if(rendered.length!=input.length)throw new IllegalArgumentException("Wrong RGB length");
        int[] output=new int[baseline.length];double[] decode=new double[65536];
        for(int i=0;i<decode.length;i++)decode[i]=Math.pow(i/65536.0,parameters[37]);
        for(int i=0;i<output.length;i++) {
            double r=decode[rendered[3*i]&65535],g=decode[rendered[3*i+1]&65535],
                blue=decode[rendered[3*i+2]&65535];
            int packed=0xff000000;
            for(int c=0;c<3;c++) {
                int k=28+3*c;
                double v=parameters[k]*r+parameters[k+1]*g+parameters[k+2]*blue;
                v=Math.max(0,Math.min(1,v));
                v=v<=.0031308 ? 12.92*v : 1.055*Math.pow(v,1/2.4)-.055;
                packed|=((int)Math.floor(v*255+.5))<<(16-8*c);
            }
            output[i]=packed;
        }
        return output;
    }
}
