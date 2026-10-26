package com.particlesdevs.photoncamera.hasselblad;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.BlackLevelPattern;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.LensShadingMap;
import android.os.Build;
import android.util.Rational;
import com.particlesdevs.photoncamera.BuildConfig;
import com.particlesdevs.photoncamera.processing.DngCreator;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import com.particlesdevs.photoncamera.util.Allocator;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Original still metadata -> the existing DNG writer. No Parameters/preview substitutions. */
public final class HasselbladDngBridge79 implements AutoCloseable {
    private DngCreator writer;
    private final ImageFrame frame;
    public final int width,height,orientation;
    public final int iso;
    public final long exposureNs;
    public final Float aperture, focalLength;

    private static double[] matrix(ColorSpaceTransform m) throws IOException {
        if(m==null) throw new IOException("Required original colour matrix missing");
        double[] out=new double[9];
        for(int y=0;y<3;y++) for(int x=0;x<3;x++) {
            double v=m.getElement(x,y).doubleValue();
            if(!Double.isFinite(v)) throw new IOException("Invalid original colour matrix");
            out[y*3+x]=v;
        }
        return out;
    }
    private static void require(boolean ok,String reason) throws IOException {if(!ok)throw new IOException(reason);}
    public HasselbladDngBridge79(ImageFrame f,CameraCharacteristics c,CaptureResult r,int rotation) throws Exception {
        frame=f; width=f.sourceRawWidth; height=f.sourceRawHeight; orientation=HasselbladRawLayout79.orientation(rotation);
        require(f.buffer!=null && f.sourceRawFormat==ImageFormat.RAW_SENSOR,"Unmodified RAW_SENSOR required");
        Rect crop=f.sourceImageCropRect;
        HasselbladRawLayout79.validate(width,height,f.sourceRowStride,f.sourcePixelStride,f.width,f.height,
                f.sourceRawBufferCapacity,f.buffer.capacity(),f.sourceCopyOffsetBytes,f.cropOriginX,f.cropOriginY,
                f.sourceBinned || f.fp16 || f.packedBits!=0,
                crop!=null && crop.left==0 && crop.top==0 && crop.right==width && crop.bottom==height);
        Integer cfa=c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        require(cfa!=null && cfa==CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGGB,"Stage79 requires RGGB RAW");
        // The existing GainMap writer has zero normalized origin. Restrict this bridge
        // to a full active rectangle; do not guess a transform for offsets/scaled modes.
        for(Rect active:new Rect[]{c.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE),
                c.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE)})
            require(active!=null && active.left==0 && active.top==0 && active.right==width && active.bottom==height,
                    "Original sensor active rectangle must match the delivered RAW dimensions");
        Integer white=r.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL);
        if(white==null) white=c.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);
        require(white!=null && white>0 && white<=65535,"Invalid original white level");
        float[] dynamic=r.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
        BlackLevelPattern pattern=c.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
        require(dynamic!=null?dynamic.length==4:pattern!=null,"Original black levels missing");
        double[] exactBlack=new double[4];
        short[] black=new short[4];boolean fractionalBlack=false;
        for(int i=0;i<4;i++) {
            double v=dynamic!=null?dynamic[i]:pattern.getOffsetForIndex(i%2,i/2);
            require(Double.isFinite(v)&&v>=0&&v<white,"Invalid original black level");
            exactBlack[i]=v;fractionalBlack|=v!=Math.rint(v);
            black[i]=(short)(int)v;
        }
        Rational[] n=r.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
        require(n!=null && n.length==3,"Original still neutral missing");
        double[] neutral=new double[3];
        for(int i=0;i<3;i++){neutral[i]=n[i].doubleValue();require(Double.isFinite(neutral[i])&&neutral[i]>0,"Invalid still neutral");}
        LensShadingMap lens=r.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP);
        require(lens!=null && lens.getColumnCount()>0 && lens.getRowCount()>0
                && (long)lens.getColumnCount()*lens.getRowCount()<=1048576,"Original still shading map missing or too large");
        float[] gains=new float[lens.getGainFactorCount()]; lens.copyGainFactors(gains,0);
        for(float v:gains) require(Float.isFinite(v)&&v>0&&v<=32,"Invalid still shading gain");
        Integer i=r.get(CaptureResult.SENSOR_SENSITIVITY);Long e=r.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        require(i!=null && i>0 && i<=65535 && e!=null && e>0,"Original exposure metadata missing");
        iso=i; exposureNs=e; aperture=r.get(CaptureResult.LENS_APERTURE);focalLength=r.get(CaptureResult.LENS_FOCAL_LENGTH);
        Number light1=c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1);
        Number light2=c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);
        require(light1!=null && light2!=null,"Original reference illuminants missing");
        try {
            writer=new DngCreator(); writer.setCompression(false);writer.setBinning(false);writer.setBitsPerSample(16);
            writer.setWhiteLevel(white);
            if(fractionalBlack)writer.setBlackLevelPrecise93(exactBlack);else writer.setBlackLevel(black);
            writer.setCFAPattern(0);writer.setOrientation(rotation/90);
            writer.setColorMatrix1(matrix(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)));
            writer.setColorMatrix2(matrix(c.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)));
            writer.setForwardMatrix1(matrix(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1)));
            writer.setForwardMatrix2(matrix(c.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)));
            writer.setCameraCalibration1(matrix(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)));
            writer.setCameraCalibration2(matrix(c.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2)));
            writer.setCalibrationIlluminant1((short)light1.intValue());writer.setCalibrationIlluminant2((short)light2.intValue());
            writer.setAsShotNeutral(neutral);writer.setAnalogBalance(new double[]{1,1,1});
            writer.setGainMap(gains,0,0,width,height,lens.getColumnCount(),lens.getRowCount());
            writer.setIso((short)iso);writer.setExposureTime(exposureNs/1e9);
            if(aperture!=null)writer.setAperture(aperture);if(focalLength!=null)writer.setFocalLength(focalLength);
            writer.setMake(Build.MANUFACTURER);writer.setModel(Build.MODEL);
            writer.setUniqueCameraModel(Build.MANUFACTURER+" "+Build.MODEL);
            writer.setDateTime(new SimpleDateFormat("yyyy:MM:dd HH:mm:ss",Locale.US).format(new Date()));
            writer.setSoftware("Hasselblad Photon "+BuildConfig.VERSION_NAME);
            writer.setDescription("Stage79 original matched still metadata; sensor RAW counts");
        } catch(Exception|LinkageError|OutOfMemoryError error) {close();throw error;}
    }
    public void write(File destination) throws IOException {
        ByteBuffer packed=null;
        try {
            if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
            ByteBuffer source=frame.buffer.duplicate();source.clear();
            if(frame.sourceRowStride!=width*2) {
                packed=Allocator.allocate(width*height*2);
                if(packed==null)throw new IOException("Cannot allocate packed RAW buffer");
                HasselbladRawLayout79.copy(source,packed,width,height,frame.sourceRowStride);source=packed;
            }
            source.limit(width*height*2);source.position(0);
            try(FileOutputStream out=new FileOutputStream(destination)) {writer.writeBuffer(out,source,width,height);}
            if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
        } finally {if(packed!=null)Allocator.free(packed);}
    }
    @Override public void close(){if(writer!=null){writer.close();writer=null;}}
}
