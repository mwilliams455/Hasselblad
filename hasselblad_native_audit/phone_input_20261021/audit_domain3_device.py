#!/usr/bin/env python3
"""Domain3 white-surface device evidence: on-demand grid + original Bayer DNG.

IMPORTANT:
- Not a shipping white-balance selector or physical light-temperature probe.
- Without the original same-frame .capture.json, DNG+Domain3 result frame identity
  is NOT cryptographically certified; agreement proves model consistency only.
- Never publish full per-point grids or capture-derived ratios in public Git.
- No HAL result is fitted or used for candidate selection and no pixel is altered.

Uses: numpy, tifffile, Pillow, a verified local host build linking the OWNED
hb_phone_domain and temperature kernels, and optional prior private audit ZIP.

Example:
python audit_domain3_device.py --domain-json /private/domain1.json \\
  --dng /private/61243.dng --jpeg /private/61245.jpg \\
  --host-library /private/libphone_domain_real_O2.so \\
  --previous-private-audit /private/Hasselblad_Acceptance_Audit_PRIVATE_20261021.zip \\
  --private-report /private/DOMAIN3_DEVICE_PRIVATE.json \\
  --public-report /public/DOMAIN3_DEVICE_RESULT.json
"""
import argparse
import ctypes as C
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

SCHEMA = "hasselblad-phone-domain1-on-demand-v1"
EXCLUSIONS = ["representable", "temperature_clipped", "scene_signed_gain", "adjacent_duplicate"]

class Anchor(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('color', C.c_float * 9), ('calibration', C.c_float * 9)]
class Input(C.Structure):
    _fields_ = [('anchor', Anchor * 2)]
class Request(C.Structure):
    _fields_ = [('first_kelvin', C.c_uint32), ('last_kelvin', C.c_uint32), ('kelvin_step', C.c_uint32),
                ('first_tint', C.c_int32), ('last_tint', C.c_int32), ('tint_step', C.c_uint32)]
class Point(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('tint', C.c_int32), ('exclusion', C.c_uint32),
                ('temperature_status', C.c_uint32), ('gain_q12', C.c_uint32 * 3)]
class Domain(C.Structure):
    _fields_ = [('schema_version', C.c_uint32), ('requested', Request), ('kelvin_count', C.c_uint32),
                ('tint_count', C.c_uint32), ('point_count', C.c_uint32), ('representable', C.c_uint32),
                ('temperature_clipped', C.c_uint32), ('scene_signed_gain', C.c_uint32),
                ('adjacent_duplicate', C.c_uint32), ('points', Point * 729)]
class Estimate(C.Structure):
    _fields_ = [('kelvin', C.c_float), ('tint', C.c_float), ('ratio_residual', C.c_float)]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def quantiles(vals):
    return [float(v) for v in np.percentile(np.asarray(vals), [0,5,25,50,75,95,100])]

def validate_domain(j):
    assert j['schema'] == SCHEMA and j['status'] == 'completed'
    assert j['matrix_source'] == 'original_camera2_characteristics_before_Photon_fix'
    for key in ['render_applied','shipping_policy_selected','full_automatic_controller',
                'selection_uses_hal_neutral','scene_candidate_selected','original_scene1b_policies_changed']:
        assert j[key] is False, key
    bounds = j['requested_grid']
    assert tuple(bounds[k] for k in ['kelvin_first','kelvin_last','kelvin_step','tint_first','tint_last','tint_step']) == (2000,10000,100,-100,100,25)
    assert bounds['point_order'] == 'tint-major, ascending kelvin'
    pts=j['points']; assert len(pts) == 729
    counted=Counter()
    for i,p in enumerate(pts):
        assert p['kelvin'] == 2000+(i%81)*100
        assert p['tint'] == -100+(i//81)*25
        reason=p['exclusion']; assert reason in EXCLUSIONS
        status=p['temperature_status'];gain=p['gain_q12']
        counted[reason]+=1
        if reason=='representable':
            assert status==0 and isinstance(gain,list) and len(gain)==3
            assert gain[1]==4096 and 0<gain[0]<=32767 and 0<gain[2]<=32767
        else:
            assert gain is None
            assert (status==4) if reason=='temperature_clipped' else status==0
    counts=j['counts']; assert counts['total']==729
    for name in EXCLUSIONS:
        assert counted[name]==counts[name]
    assert 0<=j['elapsed_ms']<60000
    return counted

def ratio(vals):
    assert len(vals)==18
    return [float(np.float32(np.float32(vals[i])/np.float32(vals[i+1]))) for i in range(0,18,2)]

def model_from_dng(tags):
    model=Input()
    reference={17:2856, 21:6504}
    for index in range(2):
        n=index+1
        model.anchor[index].kelvin=reference[int(tags[f'CalibrationIlluminant{n}'].value)]
        model.anchor[index].color[:]=(C.c_float*9)(*ratio(tags[f'ColorMatrix{n}'].value))
        model.anchor[index].calibration[:]=(C.c_float*9)(*ratio(tags[f'CameraCalibration{n}'].value))
    assert {model.anchor[0].kelvin,model.anchor[1].kelvin} == {2856,6504}
    return model

def start_library(path):
    lib=C.CDLL(str(path))
    lib.hb_phone_domain_evaluate.argtypes=[C.POINTER(Input),C.POINTER(Request),C.POINTER(Domain)]
    lib.hb_phone_domain_evaluate.restype=C.c_int
    lib.hb_phone_temperature_create.argtypes=[C.POINTER(Input),C.POINTER(C.c_void_p)]
    lib.hb_phone_temperature_create.restype=C.c_int
    lib.hb_phone_temperature_from_gain.argtypes=[C.c_void_p,C.POINTER(C.c_uint32),C.POINTER(Estimate)]
    lib.hb_phone_temperature_from_gain.restype=C.c_int
    lib.hb_phone_temperature_destroy.argtypes=[C.c_void_p]
    return lib

def means(raw,black,white):
    height,width=raw.shape
    assert height%64==0 and width%64==0
    site=[]
    for y,x in ((0,0),(0,1),(1,0),(1,1)):
        plane=(raw[y::2,x::2].astype(np.float64)-black)/(white-black)
        site.append(plane.reshape(32,height//64,32,width//64).mean((1,3)))
    return np.stack(site,axis=-1).reshape(-1,4)

def nearest(gains,locus):
    # 1024 x 729 x 2; 64-bit float, no Q12 truncation in independent distance.
    d2=((gains[:,None,:]-locus[None,:,:])**2).sum(axis=2)
    idx=np.argmin(d2,axis=1)
    return np.sqrt(d2[np.arange(len(idx)),idx]), idx

def main():
    p=argparse.ArgumentParser()
    for name in ['domain-json','dng','jpeg','host-library','private-report','public-report']:
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--previous-private-audit',type=Path)
    a=p.parse_args()
    paths=[a.domain_json,a.dng,a.jpeg,a.host_library]
    before={v.name:sha(v) for v in paths}
    j=json.loads(a.domain_json.read_text())
    count=validate_domain(j)
    with tifffile.TiffFile(a.dng) as tif:
        assert len(tif.pages)==1
        page=tif.pages[0]
        assert str(page.dtype)=='uint16' and page.shape==(3072,4096)
        assert int(page.tags['Compression'].value)==1
        assert page.tags['CFAPattern'].value==bytes([0,1,1,2])
        tags=page.tags
        software=str(tags['Software'].value)
        assert '0.1-hb-domain3' in software and '27184' in software
        image_description=str(tags['ImageDescription'].value)
        m=re.search(r'CameraID\s*=\s*(\w+)', image_description)
        camera_id=m.group(1) if m else None
        original_camera_matches=camera_id == j['physical_sensor_id']
        model=model_from_dng(tags)
        raw=page.asarray()
        black=tags['BlackLevel'].value
        assert len(black)==4 and len(set(black))==1
        black=float(black[0]);white=float(tags['WhiteLevel'].value)
        assert white>black>=0
        neutral_tag=tags['AsShotNeutral'].value
        asshot=[float(neutral_tag[i]/neutral_tag[i+1]) for i in (0,2,4)]
        exposure=tags['ExposureTime'].value
        exposure_s=exposure[0]/exposure[1]
        iso=tags['ISOSpeedRatings'].value
        image_date=tags['DateTime'].value
        orientation=tags['Orientation'].value
    lib=start_library(a.host_library)
    result=Domain()
    status=lib.hb_phone_domain_evaluate(C.byref(model),C.byref(Request(2000,10000,100,-100,100,25)),C.byref(result))
    assert status==0 and result.point_count==729
    mismatches=[]
    for i,pt in enumerate(result.points):
        expected=j['points'][i]
        computed=list(pt.gain_q12) if pt.exclusion==0 else None
        if (int(pt.kelvin),int(pt.tint),int(pt.exclusion),int(pt.temperature_status),computed) != (
                expected['kelvin'],expected['tint'],EXCLUSIONS.index(expected['exclusion']),expected['temperature_status'],expected['gain_q12']):
            mismatches.append(i)
    assert not mismatches, f'model point mismatches: {mismatches[:3]}'
    assert [result.representable,result.temperature_clipped,result.scene_signed_gain,result.adjacent_duplicate] == [count[v] for v in EXCLUSIONS]

    grid=means(raw,black,white)
    arithmetic=grid.mean(axis=1)
    ggreen=(grid[:,1]+grid[:,2])*.5
    block_gains=4096*ggreen[:,None]/grid[:,[0,3]]
    eligible=np.all(grid>0,axis=1)&(arithmetic>=.005)&(arithmetic<=.9)&np.all(block_gains<=32767,axis=1)
    assert eligible.all(), 'This particular white-surface RAW was expected to have all 1024 eligible blocks'
    handle=C.c_void_p()
    assert lib.hb_phone_temperature_create(C.byref(model),C.byref(handle))==0
    inverse=[];inversion_status=Counter()
    try:
        for r,b in block_gains:
            gains=(C.c_uint32*3)(int(r),4096,int(b))
            estimate=Estimate()
            st=lib.hb_phone_temperature_from_gain(handle,gains,C.byref(estimate))
            inversion_status[st]+=1
            if st==0:inverse.append([estimate.kelvin,estimate.tint,estimate.ratio_residual])
    finally:
        lib.hb_phone_temperature_destroy(handle)
    assert inversion_status=={0:1024}
    inverse=np.array(inverse)
    valid=[p for p in j['points'] if p['exclusion']=='representable']
    locus=np.array([[p['gain_q12'][0],p['gain_q12'][2]] for p in valid],dtype=np.float64)
    coords=np.array([[p['kelvin'],p['tint']] for p in valid])
    zero=locus[coords[:,1]==0]
    distance2d,indices=nearest(block_gains,locus)
    distance0,_=nearest(block_gains,zero)
    nearest_tints=Counter(int(v) for v in coords[indices,1])
    jpeg=Image.open(a.jpeg).convert('RGB')
    jpgarr=np.asarray(jpeg,dtype=np.float64)
    jpg_mean=jpgarr.mean((0,1)).tolist()
    jpg_exif_count=len(jpeg.getexif())
    old_comparison=None
    if a.previous_private_audit:
        with zipfile.ZipFile(a.previous_private_audit) as z:
            old=json.loads(z.read('ACCEPTANCE_AUDIT_PRIVATE.json'))
        old_door=next(x for x in old['captures'] if x['label']=='Latest pale surface')
        oldg=np.array(old_door['eligible_block_gains'])
        old_comparison={
            'earlier_capture_label':old_door['label'],
            'earlier_surface_description_from_verified_handoff':'white door under tungsten lighting',
            'previous_red_gain_median_q12':float(np.median(oldg[:,0])),
            'previous_blue_gain_median_q12':float(np.median(oldg[:,1])),
            'new_red_gain_median_q12':float(np.median(block_gains[:,0])),
            'new_blue_gain_median_q12':float(np.median(block_gains[:,1])),
            'previous_tint_median':float(old_door['block_tint_quantiles'][2]),
            'new_tint_median':float(np.median(inverse[:,1])),
            'note':'Similar RAW ratios are repeatable sensor-response evidence; not proof of identical lighting or certified surface reflectance.'
        }

    private={
      'status':'PASS', 'module':'hasselblad-domain3-device-verification-v1',
      'source_hashes_sha256':before,
      'domain_provenance':{'physical_sensor_id':j['physical_sensor_id'],'source_frame_number':j['source_frame_number'],
        'source_sensor_timestamp_ns':j['source_sensor_timestamp_ns'],'status':j['status'],'elapsed_ms':j['elapsed_ms']},
      'dng':{'software':software,'tiff_datetime':image_date,'physical_camera_id_in_description':camera_id,
        'sensor_id_agrees_with_domain':original_camera_matches,'size_pixels':list(raw.shape),
        'iso':iso,'exposure_seconds':exposure_s,'orientation':orientation,'black':black,'white':white,
        'as_shot_neutral':asshot,'measured_min':int(raw.min()),'measured_max':int(raw.max()),
        'clipped_pixel_count':int(np.sum(raw>=white)),'below_black_pixel_count':int(np.sum(raw<=black))},
      'identity_limit':{
        'strict_dng_to_domain_frame_pairing_proven':False,
        'reason':'No same-capture .capture.json with original sensor frame/timestamp and DNG SHA256 was supplied; matching model and camera ID alone cannot prove frame identity',
        'jpeg_to_dng_file_level_pairing_proven':False,
        'reason_jpeg':'Supplied JPEG is resized and has no EXIF or original capture hash'},
      'domain_counts':{k:int(count[k]) for k in EXCLUSIONS},
      'dng_model_vs_device_grid':{'points_compared':729,'mismatches':len(mismatches),'source':'DNG embedded colour/calibration matrices, actual owned host native leaf'},
      'raw_blocks':{'total':len(block_gains),'eligible':int(eligible.sum()),
        'native_inverse_successful':inversion_status[0],
        'red_gain_q12_quantiles':quantiles(block_gains[:,0]),
        'blue_gain_q12_quantiles':quantiles(block_gains[:,1]),
        'green_split_quantiles':quantiles(grid[:,1]/grid[:,2]),
        'model_kelvin_quantiles':quantiles(inverse[:,0]),
        'model_tint_quantiles':quantiles(inverse[:,1]),
        'model_ratio_residual_quantiles':quantiles(inverse[:,2]),
        'nearest_2d_q12_distance_quantiles':quantiles(distance2d),
        'nearest_0_tint_q12_distance_quantiles':quantiles(distance0),
        'nearest_2d_tint_distribution':{str(k):int(v) for k,v in sorted(nearest_tints.items())},
        'counts_2d_within_test_radii':{str(i):int(np.count_nonzero(distance2d<=i)) for i in [128,256,512,1024,2048,4096]},
        'counts_zero_tint_within_test_radii':{str(i):int(np.count_nonzero(distance0<=i)) for i in [128,256,512,1024,2048,4096]}},
      'jpeg':{'width':jpeg.size[0],'height':jpeg.size[1],'exif_tag_count':jpg_exif_count,
              'average_rgb_8bit':jpg_mean,'note':'JPEG is a supplied resized copy with unproven pairing and Photon rendering.'},
      'prior_private_comparison':old_comparison,
      'safety':{'firmware_rerun':False,'source_image_modified':False,'hal_wb_fit':False,
        'physically_calibrated_kelvin':False,'shipping_policy_selected':False,'render_applied':False},
      'research_interpretation':'Repeatable high positive model tint on pale surfaces. Grid representability is NOT neutral classification. Two-dimensional proximity must not be a shipping acceptance rule without independent neutral evidence.'}
    public={
      'status':'PASS','schema':'hasselblad-domain3-device-verification-public-v1',
      'domain3_report_status':'completed',
      'on_device_domain1_reported':True,
      'grid_points_checked':729,
      'dng_model_grid_comparisons':729,
      'dng_model_grid_mismatches':0,
      'raw_blocks_checked':1024,
      'domain_counts':{k:int(count[k]) for k in EXCLUSIONS},
      'validation_scope':'One real phone calibration and RAW mode; real native phone report plus independent host DNG-matrix replay. No physical Kelvin accuracy or device generalization.',
      'strict_dng_frame_pairing_proven':False,
      'jpeg_file_pairing_proven':False,
      'photographic_wb_changed':False,
      'shipping_policy_selected':False,
      'automatic_controller_in_phone':False,
      'hncs_rendering_integrated':False,
      'warning':'Do not infer physical illuminant from reconstructed CT/tint on uncertified surfaces. White-like and colored subjects can both match 2D chromaticity curves.',
      'new_apk_required_for_this_verification':False,
    }
    after={v.name:sha(v) for v in paths}
    assert after==before, 'Source input mutation detected'
    a.private_report.parent.mkdir(parents=True,exist_ok=True)
    a.public_report.parent.mkdir(parents=True,exist_ok=True)
    a.private_report.write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
    a.public_report.write_text(json.dumps(public,indent=2,sort_keys=True)+'\n')
    print(json.dumps(public,indent=2))

if __name__=='__main__':
    main()
