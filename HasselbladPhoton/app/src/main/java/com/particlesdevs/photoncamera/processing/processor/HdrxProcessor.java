package com.particlesdevs.photoncamera.processing.processor;

import com.particlesdevs.photoncamera.hasselblad.HasselbladStillModes95;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.ParseExif;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.control.GyroBurst;
import com.particlesdevs.photoncamera.hasselblad.HasselbladCapture79;
import com.particlesdevs.photoncamera.hasselblad.HasselbladCaptureEvidence;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import com.particlesdevs.photoncamera.processing.ProcessingEventsListener;
import com.particlesdevs.photoncamera.processing.encoder.ImageFormatConfig;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;

/** Retains the capture-controller interface; all still rendering belongs to Hasselblad. */
public final class HdrxProcessor extends ProcessorBase {
    private ArrayList<ImageFrame> frames;
    private int imageFormat,saveRAW;
    private CameraMode cameraMode;

    public HdrxProcessor(ProcessingEventsListener events) {super(events);}
    public void configure(int unusedAlignment,int saveRAW,CameraMode mode) {
        this.saveRAW=saveRAW;cameraMode=mode;
    }
    public void start(Path dngFile,Path imageFile,ParseExif.ExifData exif,
            ArrayList<GyroBurst> unusedGyro,ArrayList<ImageFrame> frames,HashMap<Long,Double> unusedExposures,
            int format,int rotation,CameraCharacteristics characteristics,CaptureResult result,
            CaptureRequest request,ProcessingCallback callback) {
        this.dngFile=dngFile;this.imageFile=imageFile;exifData=exif;this.frames=frames;
        imageFormat=format;cameraRotation=rotation;this.characteristics=characteristics;
        captureResult=result;captureRequest=request;this.callback=callback;
        Run();
    }
    public void Run() {
        var context=PhotonCamera.getAppContext();
        HasselbladCaptureEvidence evidence;int saveMode;
        try {
            if(!HasselbladStillModes95.supports(cameraMode) || imageFormat!=CaptureController.RAW_FORMAT)
                throw new IOException("Hasselblad photos require Photo or Motion mode and a sensor RAW stream");
            evidence=HasselbladCaptureEvidence.begin(frames,characteristics,captureResult,captureRequest);
            saveMode=ImageFormatConfig.resolve(saveRAW,PhotonCamera.getSettings().isHeicSave());
        } catch(Exception|LinkageError|OutOfMemoryError e) {
            String reason=e instanceof OutOfMemoryError?"Not enough memory":e.getMessage();
            HasselbladCapture79.reject94(context,frames,reason==null?e.getClass().getSimpleName():reason,
                    callback,processingEventsListener);
            return;
        }
        HasselbladCapture79.handle(context,frames,evidence,cameraRotation,saveMode,
                dngFile,imageFile,exifData,callback,processingEventsListener);
    }
}
