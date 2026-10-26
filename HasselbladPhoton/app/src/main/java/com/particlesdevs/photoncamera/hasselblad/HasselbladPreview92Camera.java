package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.hardware.camera2.*;
import android.hardware.camera2.params.*;
import android.os.Build;
import android.os.SystemClock;
import android.util.Rational;
import android.view.Surface;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.api.Settings;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector;
import java.io.IOException;
import java.util.Objects;
import java.util.WeakHashMap;

/** Camera2 adapter. Only repeating/focus preview requests are changed; still requests never enter here. */
public final class HasselbladPreview92Camera implements AutoCloseable {
    private static volatile String lastStatus="JPEG colour preview has not started.";
    public static String status(){return lastStatus;}
    private final WeakHashMap<CaptureRequest.Builder,Saved> saved=new WeakHashMap<>();
    private final WeakHashMap<CaptureRequest,Long> requests=new WeakHashMap<>();
    private HasselbladPreview92Worker<Object> worker;
    private Context context;private CameraManager manager;private Runnable rebuild;
    private boolean subscribed,loading,failed,controlled;
    private long epoch,colourEpoch,revision=-1,lastSample;
    private String streamKey,sensorId;
    private CameraCharacteristics characteristics;
    private HasselbladProfile43 profile;
    private Frame frame;
    private final Runnable changed=()->{synchronized(this){invalidate();profile=null;loading=false;failed=false;revision=HasselbladPreview90Changes.revision();}requestRebuild();};
    private static final class Saved {
        final Integer mode;final TonemapCurve curve;
        Saved(CaptureRequest.Builder b){mode=b.get(CaptureRequest.TONEMAP_MODE);curve=b.get(CaptureRequest.TONEMAP_CURVE);}
        void restore(CaptureRequest.Builder b){b.set(CaptureRequest.TONEMAP_MODE,mode);b.set(CaptureRequest.TONEMAP_CURVE,curve);}
    }
    public static final class Frame {
        public final HasselbladPreview92.Cube cube;
        final long timestamp,revision,epoch;
        Frame(HasselbladPreview92.Cube cube,long timestamp,long revision,long epoch){this.cube=cube;this.timestamp=timestamp;this.revision=revision;this.epoch=epoch;}
        public boolean valid(long timestamp,long revision,long epoch){return this.revision==revision&&this.epoch==epoch&&timestamp>=this.timestamp&&timestamp-this.timestamp<=1_000_000_000L;}
    }
    public static boolean eligible(){
        Settings s=PhotonCamera.getSettings();
        return s!=null&&s.selectedMode==CameraMode.PHOTO&&!s.QuadBayer&&!s.heicSave&&!s.aspect169&&(s.rawSaver==0||s.rawSaver==1);
    }
    private void invalidate(){epoch++;colourEpoch++;frame=null;controlled=false;lastSample=0;if(worker!=null)worker.invalidate();}
    private void requestRebuild(){Runnable r; synchronized(this){r=rebuild;}if(r!=null)r.run();}
    private void fail(Throwable e){failed=true;frame=null;lastStatus="JPEG preview unavailable: "+(e.getMessage()==null?e.getClass().getSimpleName():e.getMessage())+". Original camera feed.";}
    public synchronized CaptureRequest build(Context context,CameraManager manager,CaptureRequest.Builder builder,
            Surface preview,Surface raw,Runnable rebuild){
        this.context=context.getApplicationContext();this.manager=manager;this.rebuild=rebuild;
        if(!subscribed){HasselbladPreview90Changes.subscribe(changed);subscribed=true;}
        if(worker==null)worker=new HasselbladPreview92Worker<>();
        Saved original=saved.get(builder);if(original==null){original=new Saved(builder);saved.put(builder,original);}
        try {
            HasselbladRawStream.Identity p=HasselbladRawStream.lookup(preview),r=HasselbladRawStream.lookup(raw);
            String key=p==null?null:p.deviceId+"/"+p.physicalId;
            if(!Objects.equals(key,streamKey)||revision!=HasselbladPreview90Changes.revision()){
                invalidate();streamKey=key;sensorId=null;characteristics=null;profile=null;loading=false;failed=false;revision=HasselbladPreview90Changes.revision();
            }
            controlled=false;
            if(eligible()&&HasselbladPreview89Settings.enabled(context)&&!failed){
                require(p!=null&&r!=null&&p.deviceId.equals(r.deviceId)&&Objects.equals(p.physicalId,r.physicalId),"Preview/RAW sensor identity differs");
                CameraCharacteristics c=manager.getCameraCharacteristics(p.physicalId==null?p.deviceId:p.physicalId);
                int[] modes=c.get(CameraCharacteristics.TONEMAP_AVAILABLE_TONE_MAP_MODES);
                boolean supported=false;if(modes!=null)for(int mode:modes)if(mode==CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE)supported=true;
                require(supported,"Camera has no controllable preview tone curve");
                Integer points=c.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS);require(points!=null&&points>=16,"Insufficient preview tone points");
                if(profile==null&&!loading){
                    loading=true;final long ticket=epoch,rev=revision;final Context app=this.context;
                    lastStatus="Preparing JPEG colour preview…";
                    worker.offer(()->{HasselbladProfile43 value; synchronized(HasselbladLookStore84.class){value=HasselbladLookStore84.read(app);}require(value.hasAutomaticIlluminant&&value.hasNativeFinishing,"Automatic colour profile required");return value;},(value,error)->{
                        synchronized(this){if(ticket!=epoch||rev!=HasselbladPreview90Changes.revision())return;loading=false;if(error!=null)fail(error);else profile=(HasselbladProfile43)value;}
                        requestRebuild();
                    });
                }
                if(profile!=null){
                    float[] curve=new float[Math.min(64,points)*2];
                    for(int i=0;i<curve.length/2;i++){double y=i/(double)(curve.length/2-1);curve[2*i]=(float)(y<=.04045?y/12.92:Math.pow((y+.055)/1.055,2.4));curve[2*i+1]=(float)y;}
                    builder.set(CaptureRequest.TONEMAP_MODE,CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE);
                    builder.set(CaptureRequest.TONEMAP_CURVE,new TonemapCurve(curve,curve,curve));controlled=true;
                }
            }
        }catch(Exception|LinkageError e){fail(e);controlled=false;}
        if(!controlled){original.restore(builder);frame=null;}
        CaptureRequest request=builder.build();if(controlled)requests.put(request,epoch);return request;
    }
    public synchronized Frame frame(long timestamp){
        if(!eligible()||context==null||!HasselbladPreview89Settings.enabled(context)||frame==null||!frame.valid(timestamp,HasselbladPreview90Changes.revision(),epoch))return null;
        return frame;
    }
    public void graphicsFailed(){synchronized(this){fail(new IOException("Preview colour shader/upload failed"));}requestRebuild();}
    public synchronized void result(CaptureController owner,CaptureRequest request,TotalCaptureResult total,Surface preview){
        Long ticket=requests.get(request);if(ticket==null||ticket!=epoch||failed||profile==null||!controlled||!eligible())return;
        try {
            HasselbladRawStream.Identity identity=HasselbladRawStream.lookup(preview);require(identity!=null,"Preview identity missing");
            String id=identity.physicalId;
            if(id==null&&Build.VERSION.SDK_INT>=28)id=total.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID);
            if(id==null)id=identity.deviceId;
            CaptureResult result=total;
            if(!id.equals(identity.deviceId)){
                require(Build.VERSION.SDK_INT>=28,"Physical preview metadata unavailable");
                result=total.getPhysicalCameraResults().get(id);require(result!=null,"Matched physical preview metadata unavailable");
            }
            if(!id.equals(sensorId)){
                // A logical camera can change physical sensors without rebuilding its session.
                frame=null;colourEpoch++;lastSample=0;if(worker!=null)worker.invalidate();sensorId=id;characteristics=manager.getCameraCharacteristics(id);
            }
            long now=SystemClock.elapsedRealtime();if(now-lastSample<200)return;lastSample=now;
            Integer mode=result.get(CaptureResult.TONEMAP_MODE);
            require(mode!=null&&mode==CaptureResult.TONEMAP_MODE_CONTRAST_CURVE,"HAL did not apply the controlled tone curve");
            Integer cfa=characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
            require(cfa!=null&&cfa==CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGGB,"Saved JPEG requires RGGB metadata");
            TonemapCurve tone=result.get(CaptureResult.TONEMAP_CURVE);require(tone!=null,"Returned preview tone curve missing");
            float[][] curves=new float[3][];for(int c=0;c<3;c++){curves[c]=new float[tone.getPointCount(c)*2];tone.copyColorCurve(c,curves[c],0);}
            RggbChannelVector gain=result.get(CaptureResult.COLOR_CORRECTION_GAINS);require(gain!=null,"Returned preview WB gains missing");
            require(Math.abs(gain.getGreenEven()-gain.getGreenOdd())<=.05*Math.max(gain.getGreenEven(),gain.getGreenOdd()),"Unequal green WB gains unsupported");
            double[] gains={gain.getRed(),(gain.getGreenEven()+gain.getGreenOdd())*.5,gain.getBlue()};
            Rational[] n=result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);require(n!=null&&n.length==3,"Preview sensor neutral missing");
            double[] neutral={n[0].doubleValue(),n[1].doubleValue(),n[2].doubleValue()},analog={1,1,1};
            double[] cc1=matrix(characteristics.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1)),cc2=matrix(characteristics.get(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2));
            Number l1=characteristics.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1),l2=characteristics.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);require(l1!=null&&l2!=null,"Preview illuminants missing");
            int kelvin=HasselbladIlluminant56.estimate(matrix(characteristics.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1)),matrix(characteristics.get(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2)),l1.intValue(),l2.intValue(),cc1,cc2,analog,neutral).lutKelvin;
            double[] camera=HasselbladRenderer42.cameraToD50(matrix(characteristics.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX1)),matrix(characteristics.get(CameraCharacteristics.SENSOR_FORWARD_MATRIX2)),cc1,cc2,analog,neutral);
            Long exposure=result.get(CaptureResult.SENSOR_EXPOSURE_TIME),timestamp=result.get(CaptureResult.SENSOR_TIMESTAMP);Integer iso=result.get(CaptureResult.SENSOR_SENSITIVITY),boost=result.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST);
            require(exposure!=null&&exposure>0&&iso!=null&&iso>0&&timestamp!=null&&timestamp>0&&boost!=null&&boost>0,"Preview exposure/RAW boost metadata missing");
            IsoExpoSelector.ExpoPair capture=IsoExpoSelector.GenerateExpoPair(-1,owner);
            double ratio=((double)capture.exposure/exposure)*((double)capture.iso/iso)*100./boost;
            Integer white=result.get(CaptureResult.SENSOR_DYNAMIC_WHITE_LEVEL);if(white==null)white=characteristics.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL);require(white!=null&&white>0,"Preview white level missing");
            float[] black=result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);BlackLevelPattern pattern=characteristics.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN);
            require(black!=null?black.length==4:pattern!=null,"Preview black levels missing");
            double[] levels=new double[4];double max=0;for(int i=0;i<4;i++){levels[i]=black==null?pattern.getOffsetForIndex(i%2,i/2):black[i];require(Double.isFinite(levels[i])&&levels[i]>=0&&levels[i]<white,"Invalid preview black level");max=Math.max(max,levels[i]);}
            double[] normalization={(white-levels[0])/(white-max),(white-(levels[1]+levels[2])*.5)/(white-max),(white-levels[3])/(white-max)};
            HasselbladPreview92.Input input=new HasselbladPreview92.Input(matrix(result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM)),gains,curves,camera,normalization,ratio,kelvin);
            final HasselbladProfile43 selected=profile;final long e=epoch,colour=colourEpoch,rev=revision,stamp=timestamp;final String sensor=sensorId;
            worker.offer(()->HasselbladPreview92.build(selected,input),(value,error)->{
                boolean restore=false;
                synchronized(this){if(e!=epoch||colour!=colourEpoch||rev!=HasselbladPreview90Changes.revision()||!sensor.equals(sensorId)||failed)return;
                    if(error!=null){fail(error);restore=true;}else{frame=new Frame((HasselbladPreview92.Cube)value,stamp,rev,e);lastStatus="JPEG colour preview active: curve "+selected.film+", "+input.kelvin+" K; exposure ratio "+String.format(java.util.Locale.US,"%.3f",ratio)+". Clipping and fine detail can differ.";}}
                if(restore)requestRebuild();
            });
        }catch(Exception|LinkageError e){fail(e);requestRebuild();}
    }
    private static void require(boolean value,String reason)throws IOException{if(!value)throw new IOException(reason);}
    private static double[] matrix(ColorSpaceTransform matrix)throws IOException{
        require(matrix!=null,"Preview colour matrix missing");double[] values=new double[9];for(int r=0;r<3;r++)for(int c=0;c<3;c++)values[3*r+c]=matrix.getElement(c,r).doubleValue();return values;
    }
    @Override public synchronized void close(){
        invalidate();if(subscribed)HasselbladPreview90Changes.unsubscribe(changed);subscribed=false;
        if(worker!=null)worker.close();worker=null;profile=null;loading=false;failed=false;requests.clear();saved.clear();rebuild=null;streamKey=null;sensorId=null;characteristics=null;
    }
}
