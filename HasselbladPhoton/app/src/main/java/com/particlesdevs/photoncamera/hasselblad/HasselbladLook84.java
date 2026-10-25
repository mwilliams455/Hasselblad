package com.particlesdevs.photoncamera.hasselblad;

import java.io.*;
import java.nio.*;
import java.security.MessageDigest;
import java.util.*;

/** Select a recovered film table without changing the imported colour/finishing data. */
public final class HasselbladLook84 {
    private HasselbladLook84() {}
    public static String sha256(byte[] bytes)throws Exception {
        StringBuilder out=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))out.append(String.format(Locale.ROOT,"%02x",b&255));
        return out.toString();
    }
    public static String label(int film){return film==0?"Curve 0":film==1?"Curve 1":film==7?"No-film control":"Unknown curve";}
    public static String curveHash(HasselbladProfile43 profile)throws Exception {
        ByteBuffer b=ByteBuffer.allocate(profile.curve.length*4).order(ByteOrder.LITTLE_ENDIAN);
        b.asFloatBuffer().put(profile.curve);return sha256(b.array());
    }
    public static void requireCurrent(HasselbladProfile43 current,String expectedHash)throws Exception {
        if(expectedHash==null||!sha256(current.encoded()).equals(expectedHash))
            throw new IOException("The colour profile changed. Refresh before selecting a curve.");
    }
    public static HasselbladProfile43 select(HasselbladProfile43 current,HasselbladTone83 pack,int film)throws Exception {
        if(film!=0&&film!=1)throw new IOException("Choose curve 0 or curve 1 for camera photos.");
        if(current==null||pack==null)throw new IOException("Import an automatic colour profile and matching tone pack first.");
        pack.validateProfile(current);
        byte[] bytes=current.encoded();ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        b.putInt(24,film);b.position(32+38*8+current.gridWidth*current.gridHeight*2*8);
        for(float v:pack.curve(film))b.putFloat(v);
        MessageDigest hash=MessageDigest.getInstance("SHA-256");hash.update(bytes,0,bytes.length-32);
        System.arraycopy(hash.digest(),0,bytes,bytes.length-32,32);
        HasselbladProfile43 result=HasselbladProfile43.read(new ByteArrayInputStream(bytes));
        pack.validateProfile(result);return result;
    }
}
