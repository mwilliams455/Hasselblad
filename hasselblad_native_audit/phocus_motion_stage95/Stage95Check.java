package com.particlesdevs.photoncamera.hasselblad;

import com.particlesdevs.photoncamera.api.CameraMode;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.settings.*;
import static com.particlesdevs.photoncamera.hasselblad.Stage94Check.*;

public final class Stage95Check {
    public static void main(String[] args)throws Exception {
        Stage94Check.main(args);int baselineCases=cases;
        for(CameraMode mode:CameraMode.values()) {
            check(HasselbladStillModes95.supports(mode)==(mode==CameraMode.PHOTO||mode==CameraMode.MOTION),"Unsupported mode allowed");
            int saved=mode.ordinal(),allowed=HasselbladStillModes95.allowedOrdinal(saved);
            CameraMode expected=mode==CameraMode.MOTION?mode:CameraMode.PHOTO;
            check(allowed==expected.ordinal(),"Invalid persisted enum mapping");
            check(HasselbladStillModes95.at(HasselbladStillModes95.indexOf(saved))==expected,"Picker index confused with enum ordinal");
            var manager=new SettingsManager();manager.set("global",PreferenceKeys.Key.CAMERA_MODE,saved);
            manager.set("global",PreferenceKeys.Key.KEY_FRAME_COUNT,8);
            HasselbladDevelopmentPolicy.applyPreferences(manager);
            check(manager.getInteger("global",PreferenceKeys.Key.CAMERA_MODE,-1)==expected.ordinal(),"Startup changed supported mode");
            HasselbladDevelopmentPolicy.applyPreferences(manager);
            check(manager.getInteger("global",PreferenceKeys.Key.CAMERA_MODE,-1)==expected.ordinal(),"Repeated startup lost selected mode");
            check(manager.getInteger("global",PreferenceKeys.Key.KEY_FRAME_COUNT,-1)==1,"Motion enabled stacking");
            check(manager.getInteger("global",PreferenceKeys.Key.KEY_BRACKETING_MODE,-1)==0,"Motion enabled bracketing");
            check(Boolean.TRUE.equals(manager.values.get(PreferenceKeys.Key.KEY_HDRX)),"Sensor RAW input lost");
            for(var key:new PreferenceKeys.Key[]{PreferenceKeys.Key.KEY_HDRX_NR,PreferenceKeys.Key.KEY_ULTRAHDR,PreferenceKeys.Key.KEY_QUAD_BAYER,PreferenceKeys.Key.KEY_REMOSAIC,PreferenceKeys.Key.KEY_BINNING,PreferenceKeys.Key.KEY_SAVE_HEIC})
                check(Boolean.FALSE.equals(manager.values.get(key)),"Incompatible option enabled: "+key);
        }
        var defaults=new SettingsManager();HasselbladDevelopmentPolicy.applyPreferences(defaults);
        check(defaults.getInteger("global",PreferenceKeys.Key.CAMERA_MODE,-1)==CameraMode.PHOTO.ordinal(),"First install no longer defaults to Photo");
        for(int invalid:new int[]{-1,6,50,Integer.MIN_VALUE,Integer.MAX_VALUE})
            check(HasselbladStillModes95.allowedOrdinal(invalid)==CameraMode.PHOTO.ordinal(),"Invalid saved value not normalized");
        check(!HasselbladStillModes95.supports(null),"Null mode accepted");
        check(HasselbladStillModes95.at(0)==CameraMode.PHOTO&&HasselbladStillModes95.at(1)==CameraMode.MOTION,"Picker order");
        for(boolean diagnostics:new boolean[]{false,true}) {
            for(int save:new int[]{0,1,2}) {
                Shot s=new Shot("",diagnostics);s.routed(save,CameraMode.MOTION,32,2);
                s.verify(true,save==0?0:1,save==2?0:1);
                check(Test94.renders==(save==2?0:1)&&Test94.writes==1,"Motion skipped Hasselblad renderer");
            }
            for(String fail:new String[]{"profile","invalid_profile","bridge","write","render","linkage","memory","encode","encode_false","exif","save_raw","save_jpeg","snapshot","missing_evidence"}) {
                Shot s=new Shot(fail,diagnostics);s.routed(1,CameraMode.MOTION,32,0);
                s.verify(false,fail.equals("save_jpeg")?1:0,0);
                check(Test94.rawCalls<=1&&Test94.jpegCalls<=1,"Motion retried through another renderer");
            }
            Shot heic=new Shot("",diagnostics);PhotonCamera.settings.heic=true;
            heic.routed(0,CameraMode.MOTION,32,0);heic.verify(false,0,0);
            Shot jpegInput=new Shot("",diagnostics);jpegInput.routed(0,CameraMode.MOTION,256,0);jpegInput.verify(false,0,0);
            Shot cancelled=new Shot("",diagnostics);Thread.currentThread().interrupt();
            try{cancelled.routed(0,CameraMode.MOTION,32,0);}finally{Thread.interrupted();}
            cancelled.verify(false,0,0);
            for(CameraMode mode:new CameraMode[]{CameraMode.NIGHT,CameraMode.VIDEO,CameraMode.RAWVIDEO,CameraMode.UNLIMITED}) {
                Shot s=new Shot("",diagnostics);s.routed(0,mode,32,0);s.verify(false,0,0);
                check(Test94.renders==0,"Other mode entered renderer");
            }
        }
        System.out.println("{\"status\":\"PASS_HASSELBLAD_MOTION\",\"checks\":"+checks+",\"capture_cases\":"+cases+",\"retained_stage94_cases\":"+baselineCases+",\"actual_capture_router_and_mode_policy\":true,\"mode_preferences_and_picker_mapping_checked\":true,\"photon_fallback_permitted\":false,\"motion_uses_fresh_timestamp_matched_RAW\":true,\"legacy_ZSL_enabled\":false,\"native_pixel_kernels_retested\":false,\"device_tested\":false}");
    }
}
