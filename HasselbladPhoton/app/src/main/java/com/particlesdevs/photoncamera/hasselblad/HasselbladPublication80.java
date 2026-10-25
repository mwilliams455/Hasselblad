package com.particlesdevs.photoncamera.hasselblad;

import java.io.*;
import java.nio.file.*;
import java.util.Locale;
import java.util.UUID;

/** Copy a completed private image through a document provider, then rename it. */
public final class HasselbladPublication80 {
    private HasselbladPublication80() {}
    public interface Document {
        OutputStream open() throws IOException;
        long length();
        String name();
        boolean rename(String name);
        boolean delete();
    }
    public interface Store {
        boolean exists(String name);
        Document create(String mime,String name) throws IOException;
    }
    public static void publish(Path source,String name,Store store) throws IOException {
        String lower=name.toLowerCase(Locale.ROOT);
        if(name.isEmpty() || name.contains("/") || name.contains("\\")
                || !(lower.endsWith(".jpg") || lower.endsWith(".dng")))
            throw new IOException("Expected a JPEG or DNG filename");
        boolean jpeg=lower.endsWith(".jpg");
        if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
        long expected=Files.size(source);
        if(expected<=0)throw new IOException("Private image is empty");
        if(store.exists(name))throw new FileAlreadyExistsException(name);
        Document temporary=null;boolean committed=false;Throwable failure=null;
        try {
            temporary=store.create(jpeg?"image/jpeg":"image/x-adobe-dng",
                    "hb80-"+UUID.randomUUID()+(jpeg?".jpg":".dng"));
            if(temporary==null)throw new IOException("Cannot create image through granted folder");
            long copied=0;
            try(InputStream in=Files.newInputStream(source);OutputStream out=temporary.open()) {
                if(out==null)throw new IOException("Cannot open image document");
                byte[] buffer=new byte[65536];int n;
                while((n=in.read(buffer))!=-1) {
                    if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
                    out.write(buffer,0,n);copied+=n;
                }
            }
            if(copied!=expected || temporary.length()!=expected)
                throw new IOException("Image document length differs after copy");
            if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
            if(store.exists(name))throw new FileAlreadyExistsException(name);
            if(!temporary.rename(name))throw new IOException("Cannot rename completed image document");
            // Providers may choose another name; never silently report the wrong path.
            if(!name.equals(temporary.name()))throw new IOException("Provider changed the image filename");
            committed=true;
        }catch(IOException|RuntimeException|Error e){failure=e;throw e;}
        finally {
            if(temporary!=null && !committed) {
                try {if(!temporary.delete())throw new IOException("Cannot remove incomplete image document");}
                catch(IOException|RuntimeException cleanup) {
                    if(failure!=null)failure.addSuppressed(cleanup);else throw cleanup;
                }
            }
        }
    }
}
