package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.media.Image;
import com.particlesdevs.photoncamera.api.*;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.processing.*;
import com.particlesdevs.photoncamera.processing.processor.*;
import java.nio.file.*;
import java.util.*;

public final class Stage94Check {
    static int checks,cases;static Path work;
    static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
    static final class Events implements ProcessingEventsListener,ProcessorBase.ProcessingCallback {
        int started,failed,finished,errors,saved;boolean callbackThrows;
        public void onStarted(){started++;if(callbackThrows)throw new IllegalStateException("UI fixture");}
        public void onFailed(){failed++;if(callbackThrows)throw new IllegalStateException("UI fixture");}
        public void onFinished(){finished++;if(callbackThrows)throw new IllegalStateException("UI fixture");}
        public void onProcessingStarted(String s){}public void onProcessingChanged(Object o){}
        public void onProcessingFinished(Object o){}
        public void onProcessingError(Object o){errors++;check(o.toString().startsWith("Hasselblad capture failed:"),"Missing visible failure");}
        public void notifyImageSavedStatus(boolean s,Path p){check(s&&Files.isRegularFile(p),"Incorrect save notification");saved++;}
    }
    static final class Shot {
        final Path dir;final Context context;final Events events=new Events();
        ArrayList<ImageFrame> frames=new ArrayList<>(List.of(new ImageFrame()));
        Shot(String failure,boolean diagnostics)throws Exception {
            dir=work.resolve("case-"+(cases++));Files.createDirectories(dir);
            context=new Context(dir.resolve("cache").toFile());Test94.reset(failure,diagnostics);
            HasselbladDiagnostics86.setEnabled(context,diagnostics);PhotonCamera.context=context;PhotonCamera.settings.heic=false;
        }
        void handle(int mode,HasselbladCaptureEvidence evidence){
            HasselbladCapture79.handle(context,frames,evidence,0,mode,dir.resolve("photo.dng"),dir.resolve("photo"),new ParseExif.ExifData(),events,events);
        }
        void routed(int mode,CameraMode camera,int format,int alignment) {
            var processor=new HdrxProcessor(events);processor.configure(alignment,mode,camera);
            processor.start(dir.resolve("photo.dng"),dir.resolve("photo"),new ParseExif.ExifData(),null,frames,null,format,0,null,null,null,events);
        }
        String status(){return HasselbladCapture79.lastStatus94(context);}
        void verify(boolean success,int raw,int jpeg)throws Exception {
            check(events.failed==(success?0:1)&&events.finished==(success?1:0),"Wrong terminal callback: "+Test94.fail);
            check(events.errors==(success?0:1),"Failure not surfaced");
            check(events.saved==raw+jpeg,"Wrong publication notifications");
            check(Files.exists(dir.resolve("photo.dng"))==(raw==1),"Unexpected RAW");
            check(Files.exists(dir.resolve("photo.jpg"))==(jpeg==1),"Unexpected JPEG");
            if(frames!=null)for(ImageFrame frame:frames)if(frame!=null)check(frame.closes==1,"Frame not closed exactly once");
            try(var files=Files.list(context.getCacheDir().toPath())){check(files.noneMatch(p->p.getFileName().toString().startsWith("hb82-shot-")),"Temporary RAW/JPEG leaked");}
            check(!status().contains("Photon"),"Substitute renderer reported");
            check(status().contains("0.1-hb-capture94"),"Missing result build");
            if(!Test94.diagnostics)check(!Files.exists(context.getCacheDir().toPath().resolve("hb82-latest")),"Diagnostics retained when off");
            else check(Files.readString(context.getCacheDir().toPath().resolve("hb82-latest/report.json")).contains("photon_colour_applied=false"),"Renderer requirement missing from report");
            check(success?!status().contains("failed"):(status().contains("failed")||status().contains("cancelled")),"Incorrect visible result");
        }
    }
    public static void main(String[] args)throws Exception {
        work=Path.of(args[0]);
        for(boolean diagnostics:new boolean[]{false,true}) {
            for(int mode:new int[]{0,1,2}) {
                Shot s=new Shot("",diagnostics);s.routed(mode,CameraMode.PHOTO,32,2);
                s.verify(true,mode==0?0:1,mode==2?0:1);
                check(Test94.renders==(mode==2?0:1)&&Test94.writes==1,"Capture skipped Hasselblad or rendered RAW-only");
                check(mode==2?s.status().contains("original RAW saved"):s.status().contains("Hasselblad · Curve 1"),"Wrong renderer label");
                HasselbladCapture79.clearDiagnostics86(s.context);
                check(s.status().contains("Build:"),"Clearing diagnostics erased capture outcome");
            }
            for(String fail:new String[]{"profile","invalid_profile","bridge","write","render","linkage","memory","encode","encode_false","exif","save_raw","save_jpeg","snapshot","missing_evidence"}) {
                Shot s=new Shot(fail,diagnostics);s.routed(1,CameraMode.PHOTO,32,0);
                s.verify(false,fail.equals("save_jpeg")?1:0,0);
                if(fail.equals("save_jpeg"))check(s.status().contains("Original RAW saved"),"Partial save hidden");
                check(Test94.rawCalls<=1&&Test94.jpegCalls<=1,"Save retried through another path");
            }
            for(int invalid:new int[]{0,1,2,3,4}) {
                Shot s=new Shot("",diagnostics);
                if(invalid==0)s.frames=null;
                if(invalid==1)s.frames.clear();
                if(invalid==2)s.frames.add(new ImageFrame());
                if(invalid==3)s.frames.set(0,null);
                s.handle(0,invalid==4?null:new HasselbladCaptureEvidence());s.verify(false,0,0);
                check(Test94.writes==0&&Test94.renders==0,"Invalid capture reached writer");
            }
            for(int invalid:new int[]{0,1,2}) {
                Shot s=new Shot("",diagnostics);
                if(invalid==2)PhotonCamera.settings.heic=true;
                s.routed(0,invalid==0?CameraMode.UNLIMITED:CameraMode.PHOTO,invalid==1?256:32,0);
                s.verify(false,0,0);check(Test94.renders==0,"Unsupported mode rendered");
            }
            Shot cancelled=new Shot("",diagnostics);Thread.currentThread().interrupt();
            try{cancelled.routed(0,CameraMode.PHOTO,32,0);}finally{Thread.interrupted();}
            cancelled.verify(false,0,0);check(cancelled.status().contains("cancelled"),"Cancellation hidden");
            Shot ui=new Shot("bridge",diagnostics);ui.events.callbackThrows=true;ui.routed(0,CameraMode.PHOTO,32,0);ui.verify(false,0,0);
            Shot cleanup=new Shot("",diagnostics);cleanup.frames.get(0).closeThrows=true;cleanup.frames.add(new ImageFrame());
            cleanup.handle(0,new HasselbladCaptureEvidence());cleanup.verify(false,0,0);
            for(boolean jpeg:new boolean[]{true,false}) {
                Shot s=new Shot("",diagnostics);Image image=new Image();
                DefaultSaver saver=jpeg?new JPEGSaver(s.events):new YUVSaver(s.events);saver.addImage(image);
                check(image.closes==1&&!saver.bufferLock&&s.events.errors==1,"Processed stream rejection leaked image or locked capture");
                check(s.status().contains("failed")&&Test94.renders==0&&Test94.jpegCalls==0,"Processed camera stream substituted for renderer");
            }
            Shot recovered=new Shot("",diagnostics);recovered.routed(0,CameraMode.PHOTO,32,0);recovered.verify(true,0,1);
        }
        System.out.println("{\"status\":\"PASS_HASSELBLAD_ONLY\",\"checks\":"+checks+",\"capture_cases\":"+cases+",\"actual_capture_orchestrator_and_router\":true,\"injected_failure_and_cleanup_checks\":true,\"native_pixel_kernels_retested\":false,\"device_tested\":false}");
    }
}
