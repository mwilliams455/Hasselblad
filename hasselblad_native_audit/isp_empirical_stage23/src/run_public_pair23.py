#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Ephemeral, chart-only, in-camera JPEG vs LibRaw comparison of one X2D II pair.

Requires rawpy/opencv-contrib/Pillow/exiftool. No pixel data or metadata that
could expose a photographer is exported. The full-size originals remain local
and must never be uploaded or committed.
"""
from __future__ import annotations
import argparse, datetime, json, math, subprocess, sys
from pathlib import Path
import numpy as np
from pair_math23 import report,srgb_encode,STAGE


def exif(path:Path)->dict:
    p=subprocess.run(['exiftool','-json','-n','-Model','-ISO','-DateTimeOriginal',str(path)],
                     check=True,capture_output=True,text=True,timeout=55)
    rows=json.loads(p.stdout)
    if len(rows)!=1:raise ValueError('Invalid EXIF response')
    d=rows[0]
    return {'model':d.get('Model'),'iso':d.get('ISO'),'time':d.get('DateTimeOriginal')}


def exif_provenance(raw:Path,jpg:Path)->dict:
    if raw.stem!=jpg.stem or raw.suffix.lower()!='.3fr' or jpg.suffix.lower() not in ('.jpg','.jpeg'):
        raise ValueError('Capture pair filenames do not match')
    a,b=exif(raw),exif(jpg)
    for d in (a,b):
        if 'X2D II' not in str(d.get('model') or '').upper():
            raise ValueError('Not a documented X2D II camera model')
        try:
            if int(d.get('iso'))!=50:raise ValueError('Unexpected capture ISO')
        except (ValueError,TypeError) as e:raise ValueError('ISO not documented as 50') from e
        if not d.get('time'):raise ValueError('Missing EXIF DateTimeOriginal')
    try:
        t1=datetime.datetime.strptime(a['time'][:19],'%Y:%m:%d %H:%M:%S')
        t2=datetime.datetime.strptime(b['time'][:19],'%Y:%m:%d %H:%M:%S')
    except ValueError as e:raise ValueError('Unsupported EXIF timestamp') from e
    offset=abs((t1-t2).total_seconds())
    if offset>2:raise ValueError('Capture timestamps differ by more than 2s')
    return {'same_stem':True,'same_model':True,'iso_matches':True,'time_offset_seconds':offset}


def scaled_for_chart(rgb:np.ndarray,target_max_dim:int=1500)->np.ndarray:
    import cv2
    if rgb.ndim!=3 or rgb.shape[2]!=3:raise ValueError('Not RGB image')
    h,w=rgb.shape[:2]
    if max(h,w)>target_max_dim:
        k=target_max_dim/max(h,w)
        rgb=cv2.resize(rgb,(max(1,round(w*k)),max(1,round(h*k))),interpolation=cv2.INTER_AREA)
    return rgb


def detect_quads(display_rgb:np.ndarray):
    import cv2
    if not hasattr(cv2,'mcc'):raise RuntimeError('Need OpenCV contrib ColorChecker detector')
    bgr=np.uint8(np.round(np.clip(display_rgb,0,1)*255))[...,::-1].copy()
    detector=cv2.mcc.CCheckerDetector_create()
    if hasattr(detector,'setColorChartType'):
        detector.setColorChartType(cv2.mcc.MCC24)
        ok=detector.process(bgr)
    else:ok=detector.process(bgr,cv2.mcc.MCC24)
    if not ok:raise ValueError('No ColorChecker detected; do not output fabricated patch statistics')
    found=detector.getListColorChecker()
    if not found:raise ValueError('Detector did not return a chart')
    return found[0].getColorCharts().reshape(24,4,2)


def extract_patches(data:np.ndarray,quads:np.ndarray)->np.ndarray:
    h,w=data.shape[:2]
    out=np.zeros((24,3),dtype=np.float64)
    if quads.shape!=(24,4,2):raise ValueError('Unknown chart geometry')
    for k,q in enumerate(quads):
        x0,y0=q.min(axis=0);x1,y1=q.max(axis=0)
        cx,cy=(x0+x1)/2,(y0+y1)/2
        hw,hh=(x1-x0)*0.25,(y1-y0)*0.25
        sx0=max(0,math.floor(cx-hw));sx1=min(w,math.ceil(cx+hw))
        sy0=max(0,math.floor(cy-hh));sy1=min(h,math.ceil(cy+hh))
        if min(sx1-sx0,sy1-sy0)<2:raise ValueError('Patch centre too small')
        out[k]=np.mean(data[sy0:sy1,sx0:sx1],axis=(0,1))
    return out


def get_jpeg_display(jpg:Path):
    from PIL import Image,ImageCms,ImageOps
    with Image.open(jpg) as im:
        if im.width*im.height>200_000_000:raise ValueError('Oversize JPEG')
        im.draft('RGB',(1600,1600))
        image=ImageOps.exif_transpose(im).convert('RGB')
        icc=im.info.get('icc_profile')
        if icc:
            import io
            src=ImageCms.ImageCmsProfile(io.BytesIO(icc))
            dst=ImageCms.createProfile('sRGB')
            image=ImageCms.profileToProfile(image,src,dst,outputMode='RGB')
        arr=np.asarray(image,dtype=np.float32)/255.0
    arr=scaled_for_chart(arr)
    return arr,bool(icc)


def get_raw_linear(raw:Path):
    import rawpy
    import cv2
    with rawpy.imread(str(raw)) as im:
        tmp=im.postprocess(half_size=True,use_camera_wb=True,no_auto_bright=True,
            output_bps=16,output_color=rawpy.ColorSpace.sRGB,gamma=(1,1))
    h,w=tmp.shape[:2]
    k=min(1.,1500/max(h,w))
    small=cv2.resize(tmp,(round(w*k),round(h*k)),interpolation=cv2.INTER_AREA) if k<1 else tmp
    del tmp
    return small.astype(np.float32)/65535.0


def execute(raw:Path,jpg:Path)->dict:
    prov=exif_provenance(raw,jpg)
    jpeg,jpeg_icc=get_jpeg_display(jpg)
    quads_jpeg=detect_quads(jpeg)
    patches_jpeg=extract_patches(jpeg,quads_jpeg)
    linear=get_raw_linear(raw)
    # The stretched preview is only used for the detector; unscaled linear
    # RGB is used for all colour calculations.
    lo,hi=np.percentile(linear,[.5,99.5])
    stretched=np.clip((linear-lo)/max(1.e-6,hi-lo),0,1)
    preview=srgb_encode(stretched)
    quads_raw=detect_quads(preview)
    patches_raw=extract_patches(linear,quads_raw)
    z=report(patches_raw,patches_jpeg,file_stems_match=prov['same_stem'],
        metadata_match=prov['same_model'] and prov['iso_matches'] and prov['time_offset_seconds']<=2,
        source_category='camera_jpeg',applied_icc_profile=jpeg_icc,
        chart_detected_independently=True)
    z['public_reference_set']='kmichels-x2dii-2026-07'
    z['source_repository']='songjiun10-collab/Hncs'
    z['manifest_revision']='5f1dd7e8f4fa64b16032842e4be50208c16a4140'
    z['manifest_git_blob']='eddba2570ba2d19f443920483e5228685830127f'
    z['reference_capture_stem']=raw.stem
    z['iso']=50
    z['same_capture_exif_within_seconds']=prov['time_offset_seconds']
    z['camera_JPEG_provenance']='provided_by_contributor_as_in_camera'
    z['chart_measurement_context']='one_related_burst_one_unmeasured_illuminant'
    z['sRGB_assumed_when_JPEG_ICC_absent']=not jpeg_icc
    z['raw_pixel_coordinates_exported']=False
    return z

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--jpeg',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=execute(a.raw,a.jpeg)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'patches':r['patch_count'],'pair':r['reference_capture_stem'],
                      'rawpy_baseline_deltaE00':r['baseline_rawpy_vs_camera_JPEG']['mean_delta_e00'],
                      'exposure_only_adjusted_deltaE00':r['exposure_scaled_rawpy_vs_camera_JPEG']['mean_delta_e00'],
                      'has_original_phocus_reference':False}))
