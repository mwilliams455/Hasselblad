package com.particlesdevs.photoncamera.hasselblad;

import java.io.*;
import java.nio.*;
import java.security.MessageDigest;
import java.util.Arrays;

/** Private curve data and comparison arithmetic. Never writes the active colour profile. */
public final class HasselbladTone83 {
    public static final int VALUES=65536, BYTES=12+3*(4+VALUES*4)+32;
    private static final int[] FILMS={0,1,7};
    private final byte[] encoded;
    private final float[][] curves=new float[3][VALUES];
    private HasselbladTone83(byte[] data)throws Exception {
        if(data.length!=BYTES)throw new IOException("Tone pack length mismatch");
        MessageDigest hash=MessageDigest.getInstance("SHA-256");hash.update(data,0,data.length-32);
        if(!MessageDigest.isEqual(hash.digest(),Arrays.copyOfRange(data,data.length-32,data.length)))
            throw new IOException("Tone pack checksum failed");
        ByteBuffer b=ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic=new byte[8];b.get(magic);
        if(!Arrays.equals(magic,new byte[]{'H','B','8','3','C','R','V','1'})||b.getInt()!=3)
            throw new IOException("Choose the Stage83 .hbt tone pack");
        for(int j=0;j<3;j++) {
            if(b.getInt()!=FILMS[j])throw new IOException("Unsupported tone pack order");
            float previous=-1;
            for(int i=0;i<VALUES;i++) {
                float value=b.getFloat();
                if(!Float.isFinite(value)||value<0||value>65535||value<previous)
                    throw new IOException("Invalid tone curve");
                curves[j][i]=value;previous=value;
            }
        }
        encoded=data;
    }
    public static HasselbladTone83 read(InputStream in)throws Exception {
        if(in==null)throw new IOException("Cannot open tone pack");
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] block=new byte[16384];int n;
        while((n=in.read(block))!=-1) {
            if(out.size()+n>BYTES)throw new IOException("Tone pack too large");out.write(block,0,n);
        }
        return new HasselbladTone83(out.toByteArray());
    }
    public byte[] encoded(){return encoded.clone();}
    public float[] curve(int film)throws IOException {
        for(int i=0;i<FILMS.length;i++)if(FILMS[i]==film)return curves[i].clone();
        throw new IOException("Unsupported film code");
    }
    public void validateProfile(HasselbladProfile43 profile)throws IOException {
        if(!profile.hasAutomaticIlluminant||!profile.hasNativeFinishing)
            throw new IOException("Import your automatic .hbc colour profile first.");
        if(!Arrays.equals(profile.curve,curve(profile.film)))
            throw new IOException("This tone pack does not match the active profile's curve. Keep the profile and use its matching pack.");
    }
    /** RAW intermediate, exactly one requested band; rejects truncation. */
    public static short[] readBand(DataInputStream in,int samples)throws IOException {
        if(samples<=0||samples>64*16384*3)throw new IOException("Invalid RGB band size");
        byte[] bytes=new byte[samples*2];in.readFully(bytes);
        short[] out=new short[samples];ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(out);return out;
    }
    /** Display-code metrics before JPEG compression; endpoints are not sensor clipping. */
    public static final class Stats {
        public long pixels,changedPixels,absoluteDifference,whiteChannelPixels,allWhitePixels,allBlackPixels;
        public int maxDifference;
        public void add(int[] current,int[] baseline) {
            if(current.length!=baseline.length)throw new IllegalArgumentException("Pixel count mismatch");
            for(int i=0;i<current.length;i++) {
                int rgb=current[i]&0xffffff;pixels++;
                if(rgb!=(baseline[i]&0xffffff))changedPixels++;
                boolean white=false;
                for(int shift=0;shift<=16;shift+=8) {
                    int value=(rgb>>shift)&255,d=Math.abs(value-((baseline[i]>>shift)&255));
                    absoluteDifference+=d;maxDifference=Math.max(maxDifference,d);white|=value==255;
                }
                if(white)whiteChannelPixels++;if(rgb==0xffffff)allWhitePixels++;if(rgb==0)allBlackPixels++;
            }
        }
        public double meanAbsoluteDifference(){return pixels==0?0:(double)absoluteDifference/(3*pixels);}
    }
}
