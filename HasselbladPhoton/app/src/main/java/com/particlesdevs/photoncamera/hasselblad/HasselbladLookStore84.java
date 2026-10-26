package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.util.Arrays;

/** Serialize profile changes with capture snapshots; persist the actual .hbc, not a second setting. */
public final class HasselbladLookStore84 {
    private HasselbladLookStore84() {}
    private static AtomicFile profileFile(Context c){return new AtomicFile(new File(c.getFilesDir(),"stage43-colour.hbc"));}
    private static AtomicFile packFile(Context c){return new AtomicFile(new File(c.getFilesDir(),"stage83-tones.hbt"));}
    public static synchronized HasselbladProfile43 read(Context c)throws Exception {
        try(InputStream in=profileFile(c).openRead()){return HasselbladProfile43.read(in);}
    }
    public static synchronized HasselbladTone83 readPack(Context c)throws Exception {
        try(InputStream in=packFile(c).openRead()){return HasselbladTone83.read(in);}
    }
    private static void write(AtomicFile file,byte[] bytes)throws Exception {
        if(Thread.currentThread().isInterrupted())throw new IOException("Profile update cancelled");
        FileOutputStream out=null;
        try{out=file.startWrite();out.write(bytes);file.finishWrite(out);}
        catch(Exception e){if(out!=null)file.failWrite(out);throw e;}
        try(InputStream in=file.openRead()) {
            ByteArrayOutputStream readback=new ByteArrayOutputStream();byte[] block=new byte[16384];int n;
            while((n=in.read(block))!=-1)readback.write(block,0,n);
            if(!Arrays.equals(bytes,readback.toByteArray()))throw new IOException("Profile storage verification failed. Refresh to check the active profile.");
        } finally {
            // A completed write can change the file even if verification then fails.
            // Invalidate first; a subsequent load validates the actual stored data.
            HasselbladPreview90Changes.changed();
        }
    }
    public static synchronized void importProfile(Context c,HasselbladProfile43 profile)throws Exception {
        write(profileFile(c),profile.encoded());
    }
    public static synchronized void importPack(Context c,HasselbladTone83 pack)throws Exception {
        pack.validateProfile(read(c));write(packFile(c),pack.encoded());
    }
    public static synchronized HasselbladProfile43 select(Context c,String expectedHash,int film)throws Exception {
        HasselbladProfile43 current=read(c);HasselbladLook84.requireCurrent(current,expectedHash);
        HasselbladProfile43 selected=HasselbladLook84.select(current,readPack(c),film);
        if(!Arrays.equals(current.encoded(),selected.encoded()))write(profileFile(c),selected.encoded());
        return read(c);
    }
}
