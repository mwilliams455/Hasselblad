package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.hardware.camera2.*;
import android.hardware.camera2.params.*;
import android.util.Rational;
import android.view.Surface;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.BooleanSupplier;

public final class Stage92Check {
    static int checks,roundtripChannels,cubePixels,adapterCases;
    static final double[] ID={1,0,0,0,1,0,0,0,1},ONE={1,1,1};
    static final float[][] LINEAR={{0,0,1,1},{0,0,1,1},{0,0,1,1}};
    static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
    interface Task {void run()throws Exception;}
    static void reject(Task task)throws Exception{try{task.run();throw new AssertionError("Expected rejection");}catch(IOException expected){checks++;}}
    static void await(BooleanSupplier condition,String label)throws Exception{long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(12);while(!condition.getAsBoolean()&&System.nanoTime()<end)Thread.sleep(3);check(condition.getAsBoolean(),label);}
    static double encode(float[] curve,double x){int i=2;while(i<curve.length-2&&curve[i]<x)i+=2;double t=(x-curve[i-2])/(curve[i]-curve[i-2]);return curve[i-1]+t*(curve[i+1]-curve[i-1]);}
    static float[] srgb(){float[] v=new float[128];for(int i=0;i<64;i++){double y=i/63.;v[2*i]=(float)(y<=.04045?y/12.92:Math.pow((y+.055)/1.055,2.4));v[2*i+1]=(float)y;}return v;}
    static void inverse()throws Exception{
        double[] m={.8,.15,.05,.1,.85,.05,.03,.17,.8},gains={1.8,1.1,1.4};float[] curve=srgb();float[][] curves={curve,curve,curve};Random random=new Random(92);
        for(double boost:new double[]{1,2,4,8})for(double capture:new double[]{.5,1,2}){
            double[] raw=new double[9000],display=new double[raw.length];for(int i=0;i<raw.length;i++)raw[i]=random.nextDouble()*.025;
            for(int i=0;i<raw.length;i+=3)for(int c=0;c<3;c++){double v=0;for(int k=0;k<3;k++)v+=m[3*c+k]*gains[k]*raw[i+k]*boost;display[i+c]=encode(curve,v);}
            short[] reconstructed=HasselbladPreview92.cameraRgb(new HasselbladPreview92.Input(m,gains,curves,ID,ONE,capture/boost,5000),display);
            for(int i=0;i<raw.length;i++){check(Math.abs((reconstructed[i]&65535)-(int)(raw[i]*capture*65535))<=1,"exposure/WB/CCM/tone round trip");roundtripChannels++;}
        }
        reject(()->new HasselbladPreview92.Input(new double[9],ONE,LINEAR,ID,ONE,1,5000));
        reject(()->new HasselbladPreview92.Input(ID,new double[]{0,1,1},LINEAR,ID,ONE,1,5000));
        reject(()->new HasselbladPreview92.Input(ID,ONE,new float[][]{{0,0,.5f,.5f,1,.5f},LINEAR[1],LINEAR[2]},ID,ONE,1,5000));
        reject(()->new HasselbladPreview92.Input(ID,ONE,LINEAR,ID,ONE,Double.NaN,5000));
        reject(()->new HasselbladPreview92.Input(ID,ONE,LINEAR,ID,ONE,.001,5000));
        reject(()->new HasselbladPreview92.Input(ID,ONE,LINEAR,ID,new double[]{-1,1,1},1,5000));
        float[][] copy={{0,0,1,1},{0,0,1,1},{0,0,1,1}};double[] gain={1,1,1};
        HasselbladPreview92.Input immutable=new HasselbladPreview92.Input(ID,gain,copy,ID,ONE,1,5000);gain[0]=99;copy[0][3]=0;
        check((HasselbladPreview92.cameraRgb(immutable,new double[]{.5,.5,.5})[0]&65535)==32767,"immutable input snapshot");
    }
    static void cubes(Path work,HasselbladProfile43 profile,HasselbladTone83 pack)throws Exception{
        for(int film:new int[]{0,1,7})for(double exposure:new double[]{.25,1,2}){
            HasselbladProfile43 selected=film==7?Stage90Check.film(profile,pack,film):HasselbladLook84.select(profile,pack,film);byte[] saved=selected.encoded();
            HasselbladPreview92.Input input=new HasselbladPreview92.Input(ID,new double[]{1.25,1,1.5},LINEAR,ID,ONE,exposure,5000);
            long start=System.nanoTime();byte[] cube=HasselbladPreview92.build(selected,input).texture();
            short[] raw=new short[33*33*33*3];
            for(int g=0;g<33;g++)for(int b=0;b<33;b++)for(int r=0;r<33;r++){
                int i=(g*1089+b*33+r)*3;double[] rgb={r/32./1.25*exposure,g/32.*exposure,b/32./1.5*exposure};
                for(int c=0;c<3;c++)raw[i+c]=(short)(int)(Math.min(1,rgb[c])*65535.);
            }
            short[] colour=HasselbladRenderer42.render(raw,selected.parameters(ID),selected.gridAtTemperature(5000),selected.curve,selected.gridWidth,selected.gridHeight,1);
            int[] jpeg=HasselbladProfile43.srgb16ToArgb(selected.finishRgb16(colour));
            for(int i=0;i<jpeg.length;i++){int rgb=((cube[4*i]&255)<<16)|((cube[4*i+1]&255)<<8)|(cube[4*i+2]&255);check(rgb==(jpeg[i]&0xffffff)&&cube[4*i+3]==(byte)255,"native JPEG and preview cube grid exact");cubePixels++;}
            check(Arrays.equals(saved,selected.encoded()),"profile remains unchanged");
            Files.write(work.resolve("cube-"+film+"-"+exposure+".rgba"),cube);
            System.out.println("Cube "+film+"/"+exposure+" + reference: "+(System.nanoTime()-start)/1e6+" ms");
        }
    }
    static void worker()throws Exception{
        HasselbladPreview92Worker<Integer> worker=new HasselbladPreview92Worker<>();CountDownLatch started=new CountDownLatch(1),release=new CountDownLatch(1);AtomicInteger count=new AtomicInteger(),value=new AtomicInteger(-1);
        worker.offer(()->{started.countDown();release.await();return 0;},(v,e)->{count.incrementAndGet();value.set(v);});check(started.await(2,TimeUnit.SECONDS),"worker starts");
        for(int i=1;i<=1000;i++){final int v=i;worker.offer(()->v,(x,e)->{count.incrementAndGet();value.set(x);});}
        release.countDown();await(()->value.get()==1000,"newest pending frame rendered");check(count.get()==2,"bounded pending queue");
        CountDownLatch started2=new CountDownLatch(1),release2=new CountDownLatch(1);worker.offer(()->{started2.countDown();release2.await();return 1;},(v,e)->value.set(-100));check(started2.await(2,TimeUnit.SECONDS),"invalidation worker starts");
        worker.invalidate();worker.offer(()->2000,(v,e)->value.set(v));release2.countDown();await(()->value.get()==2000,"old session completion discarded");
        CountDownLatch started3=new CountDownLatch(1);worker.offer(()->{started3.countDown();Thread.sleep(60000);return 3;},(v,e)->value.set(-200));check(started3.await(2,TimeUnit.SECONDS),"close worker starts");worker.close();Thread.sleep(20);check(value.get()==2000,"close discards completion");
    }
    static ColorSpaceTransform matrix(double[] m){Rational[] r=new Rational[9];for(int i=0;i<9;i++)r[i]=new Rational((int)Math.round(m[i]*10000),10000);return new ColorSpaceTransform(r);}
    static CameraCharacteristics characteristics(){
        CameraCharacteristics c=new CameraCharacteristics();c.set(CameraCharacteristics.TONEMAP_AVAILABLE_TONE_MAP_MODES,new int[]{0,1});c.set(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS,64);c.set(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT,0);
        c.set(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT1,17);c.set(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2,21);c.set(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL,4095);c.set(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN,new BlackLevelPattern());
        c.set(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM1,matrix(ID));c.set(CameraCharacteristics.SENSOR_CALIBRATION_TRANSFORM2,matrix(ID));c.set(CameraCharacteristics.SENSOR_COLOR_TRANSFORM1,matrix(ID));c.set(CameraCharacteristics.SENSOR_COLOR_TRANSFORM2,matrix(ID));c.set(CameraCharacteristics.SENSOR_FORWARD_MATRIX1,matrix(ID));c.set(CameraCharacteristics.SENSOR_FORWARD_MATRIX2,matrix(ID));return c;
    }
    static TotalCaptureResult result(CaptureRequest request){
        TotalCaptureResult r=new TotalCaptureResult();r.set(CaptureResult.TONEMAP_MODE,request.get(CaptureRequest.TONEMAP_MODE));r.set(CaptureResult.TONEMAP_CURVE,request.get(CaptureRequest.TONEMAP_CURVE));
        r.set(CaptureResult.COLOR_CORRECTION_GAINS,new RggbChannelVector(1.2f,1,1,1.4f));r.set(CaptureResult.COLOR_CORRECTION_TRANSFORM,matrix(new double[]{.8,.15,.05,.1,.85,.05,.03,.17,.8}));r.set(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT,new Rational[]{new Rational(9642,10000),new Rational(1,1),new Rational(8249,10000)});
        r.set(CaptureResult.SENSOR_EXPOSURE_TIME,10000000L);r.set(CaptureResult.SENSOR_TIMESTAMP,1000000000L);r.set(CaptureResult.SENSOR_SENSITIVITY,100);r.set(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST,200);return r;
    }
    static void camera(Path work,HasselbladProfile43 profile,HasselbladTone83 pack)throws Exception{
        Context context=new Context(work.resolve("camera-store").toFile());HasselbladLookStore84.importProfile(context,profile);HasselbladLookStore84.importPack(context,pack);
        CameraManager manager=new CameraManager();manager.cameras.put("logical",characteristics());manager.cameras.put("physical",characteristics());manager.cameras.put("other",characteristics());
        Surface preview=new Surface(),raw=new Surface();CaptureController owner=new CaptureController();
        for(int mode=0;mode<9;mode++){
            adapterCases++;HasselbladPreview89Settings.setEnabled(context,true);
            HasselbladRawStream.record(preview,"logical",mode==1?"physical":null);HasselbladRawStream.record(raw,"logical",mode==1?"physical":mode==2?"other":null);
            HasselbladPreview92Camera camera=new HasselbladPreview92Camera();CaptureRequest.Builder builder=new CaptureRequest.Builder();builder.set(CaptureRequest.TONEMAP_MODE,1);AtomicInteger rebuild=new AtomicInteger();
            CaptureRequest initial=camera.build(context,manager,builder,preview,raw,rebuild::incrementAndGet);
            check(initial.get(CaptureRequest.TONEMAP_MODE)==1,"original tone until profile ready");
            if(mode==2){check(HasselbladPreview92Camera.status().contains("identity differs"),"mismatched stream identity rejected");camera.close();continue;}
            await(()->rebuild.get()>0,"profile async load");CaptureRequest controlled=camera.build(context,manager,builder,preview,raw,rebuild::incrementAndGet);check(controlled.get(CaptureRequest.TONEMAP_MODE)==0,"explicit controlled preview tone");
            TotalCaptureResult result=result(controlled);
            if(mode==1){TotalCaptureResult logical=new TotalCaptureResult();logical.physical.put("physical",result);result=logical;}
            if(mode==3)result.set(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST,null);
            if(mode==4)result.set(CaptureResult.TONEMAP_MODE,1);
            if(mode==5)result.set(CaptureResult.COLOR_CORRECTION_TRANSFORM,matrix(new double[9]));
            if(mode==6)result.set(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID,"physical");
            camera.result(owner,controlled,result,preview);
            if(mode>=3&&mode<=6){
                check(camera.frame(1033000000L)==null,"invalid metadata cannot produce a preview cube");
                CaptureRequest restored=camera.build(context,manager,builder,preview,raw,rebuild::incrementAndGet);check(restored.get(CaptureRequest.TONEMAP_MODE)==1,"restore original HAL tone after unsupported metadata");
            }else{
                await(()->camera.frame(1033000000L)!=null,"preview cube published: "+HasselbladPreview92Camera.status());
                check(camera.frame(999999999L)==null,"future metadata not used");check(camera.frame(2000000001L)==null,"stale preview metadata expires");
                if(mode==7){HasselbladPreview89Settings.setEnabled(context,false);check(camera.frame(1033000000L)==null,"toggle off clears frame synchronously");check(camera.build(context,manager,builder,preview,raw,rebuild::incrementAndGet).get(CaptureRequest.TONEMAP_MODE)==1,"toggle restores original request");}
                if(mode==8){HasselbladLookStore84.select(context,HasselbladLook84.sha256(profile.encoded()),0);check(camera.frame(1033000000L)==null,"curve revision clears stale cube synchronously");}
            }
            camera.close();check(camera.frame(1033000000L)==null,"close invalidates frame");
        }
        PhotonCamera.settings.selectedMode=com.particlesdevs.photoncamera.api.CameraMode.VIDEO;check(!HasselbladPreview92Camera.eligible(),"video excluded");PhotonCamera.settings.selectedMode=com.particlesdevs.photoncamera.api.CameraMode.PHOTO;
    }
    public static void main(String[] args)throws Exception{
        Path work=Paths.get(args[0]);HasselbladProfile43 profile;HasselbladTone83 pack;
        try(InputStream p=Files.newInputStream(work.resolve("synthetic.hbc"));InputStream t=Files.newInputStream(work.resolve("synthetic.hbt"))){profile=HasselbladProfile43.read(p);pack=HasselbladTone83.read(t);}
        inverse();cubes(work,profile,pack);worker();camera(work,profile,pack);
        String receipt="{\"status\":\"PASS_HOST\",\"checks\":"+checks+",\"inverse_roundtrip_channels\":"+roundtripChannels+",\"native_JPEG_cube_grid_pixels_exact\":"+cubePixels+",\"camera_adapter_cases\":"+adapterCases+",\"demosaic_retested\":false,\"saved_JPEG_pipeline_changed\":false}";
        Files.writeString(work.resolve("STAGE92_HOST_VALIDATION.json"),receipt+"\n");System.out.println(receipt);
    }
}
