package com.particlesdevs.photoncamera.hasselblad;

import java.io.*;
import java.nio.file.*;

/** Publish only a completely copied file. Never overwrite an existing photograph. */
public final class HasselbladCaptureFiles79 {
    private HasselbladCaptureFiles79() {}
    public static void publish(Path source,Path destination) throws IOException {
        Path temporary=Files.createTempFile(destination.toAbsolutePath().getParent(),"hb79-",".tmp");
        try {
            try(InputStream in=Files.newInputStream(source);OutputStream out=Files.newOutputStream(temporary)) {
                byte[] buffer=new byte[65536];int n;
                while((n=in.read(buffer))!=-1) {
                    if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
                    out.write(buffer,0,n);
                }
            }
            if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
            Files.move(temporary,destination); // no REPLACE_EXISTING
        } finally {Files.deleteIfExists(temporary);}
    }
}
