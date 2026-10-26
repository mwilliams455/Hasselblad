package com.particlesdevs.photoncamera.processing;

import android.media.Image;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.hasselblad.HasselbladCapture79;

/** A processed camera stream cannot substitute for Hasselblad sensor-RAW rendering. */
public final class YUVSaver extends DefaultSaver {
    public YUVSaver(ProcessingEventsListener events) {super(events);}
    @Override public void addImage(Image image) {
        try {HasselbladCapture79.reject94(PhotonCamera.getAppContext(),null,
                "Hasselblad rendering requires sensor RAW; received YUV input",
                processingCallback,processingEventsListener);}
        finally {image.close();bufferLock=false;}
    }
}
