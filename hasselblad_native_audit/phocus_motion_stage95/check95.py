#!/usr/bin/env python3
"""Retain Stage94 routing/failure cases and exercise Motion mode and startup preferences."""
import argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;AUDIT=HERE.parent;ROOT=AUDIT.parent
sys.path.insert(0,str(AUDIT/'phocus_capture_stage94'))
import check94
P=check94.PACKAGE
check94.STUBS.pop(P+'.api.CameraMode')
check94.STUBS.update({
 'androidx/annotation/StringRes.java':'package androidx.annotation;public @interface StringRes {}',
 P+'.R':'public final class R {public static final class string {public static final int mode_unlimited=1,mode_rawvideo=2,mode_motion=3,mode_photo=4,mode_night=5,mode_video=6;}}',
 'android/util/Size.java':'package android.util;public class Size {private final int w,h;public Size(int w,int h){this.w=w;this.h=h;}public int getWidth(){return w;}public int getHeight(){return h;}}',
 P+'.settings.PreferenceKeys':'''public class PreferenceKeys {public static final String SCOPE_GLOBAL="global";public enum Key {KEY_FRAME_COUNT,CAMERA_MODE,KEY_HDRX,KEY_HDRX_NR,KEY_ULTRAHDR,KEY_BRACKETING_MODE,KEY_QUAD_BAYER,KEY_REMOSAIC,KEY_BINNING,KEY_SAVE_HEIC}}''',
 P+'.settings.SettingsManager':'''public class SettingsManager {public final java.util.Map<PreferenceKeys.Key,Object> values=new java.util.HashMap<>();public void set(String s,PreferenceKeys.Key k,Object v){values.put(k,v);}public Integer getInteger(String s,PreferenceKeys.Key k,Integer fallback){return (Integer)values.getOrDefault(k,fallback);}}'''
})
check94.STUBS[P+'.BuildConfig']=check94.STUBS[P+'.BuildConfig'].replace('0.1-hb-capture94','0.1-hb-motion95').replace('27233','27234')
java=ROOT/'HasselbladPhoton/app/src/main/java'/P.replace('.','/')
extra=[java/'api/CameraMode.java',java/'hasselblad/HasselbladDevelopmentPolicy.java',java/'hasselblad/HasselbladRawSizeSelector.java',HERE/'Stage95Check.java']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
 check94.run(p.parse_args().work.resolve(),extra,'Stage95Check','STAGE95_HOST_VALIDATION.json')
