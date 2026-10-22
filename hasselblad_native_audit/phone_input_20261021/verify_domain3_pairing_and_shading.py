#!/usr/bin/env python3
"""Verify Domain3 frame/DNG binding and audit unmodified Camera2 shading basis.

Usage:
  python verify_domain3_pairing_and_shading.py --capture /private/IMG...capture.json \
      --dng /private/IMG...dng --domain-json /private/Domain3.json \
      --host-library /private/libphone_domain_real_O2.so \
      --private-report /private/PAIR_AND_SHADING_PRIVATE.json \
      --public-report /public/PAIR_AND_SHADING_RESULT.json

Private sensor readings and image-derived ratios never enter public report.
Does not alter RAW, input metadata, or any app/rendering path. The shading
result is hypothetical: never apply correction twice or fit WB to the HAL.
"""
import argparse, ctypes as C, fractions, hashlib, json, re
from pathlib import Path
import numpy as np
import tifffile
from audit_domain3_device import model_from_dng, start_library, Estimate

MATRIX_TAGS = [
    ('ColorMatrix1', 'android.sensor.colorTransform1'),
    ('ColorMatrix2', 'android.sensor.colorTransform2'),
    ('CameraCalibration1', 'android.sensor.calibrationTransform1'),
    ('CameraCalibration2', 'android.sensor.calibrationTransform2'),
    ('ForwardMatrix1', 'android.sensor.forwardMatrix1'),
    ('ForwardMatrix2', 'android.sensor.forwardMatrix2'),
]


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(b, reason):
    if not b:
        raise AssertionError(reason)


def q(v):
    return [float(x) for x in np.percentile(np.asarray(v), [5, 50, 95])]


def shade_grid(raw, maps, black, white):
    """Mirror the diagnostic sensitivity geometry, NOT a render-stage operation.

    Pixel-space bilinear map at active-array positions, then Bayer 32x32 block
    accumulation. Camera2 greens are even-/odd-sensor-row channels.
    """
    h, w = raw.shape
    rows, cols = maps.shape[:2]
    out = []
    for site, (ry, rx) in enumerate(((0,0), (0,1), (1,0), (1,1))):
        plane = (raw[ry::2, rx::2].astype(np.float64) - black) / (white-black)
        y = np.arange(ry, h, 2) / (h-1) * (rows-1)
        x = np.arange(rx, w, 2) / (w-1) * (cols-1)
        y0 = np.minimum(y.astype(np.int64), rows-2)
        x0 = np.minimum(x.astype(np.int64), cols-2)
        fy = (y-y0)[:, None]
        fx = (x-x0)[None, :]
        ch = site if site in (0,3) else 1+ry
        m = maps[:, :, ch]
        top = m[y0[:,None], x0[None,:]] * (1-fx) + m[y0[:,None],x0[None,:]+1]*fx
        bottom = m[y0[:,None]+1, x0[None,:]] * (1-fx) + m[y0[:,None]+1,x0[None,:]+1]*fx
        multiplier = top*(1-fy)+bottom*fy
        out.append(((plane*multiplier).reshape(32,h//64,32,w//64).mean(axis=(1,3))).ravel())
    return np.column_stack(out)


def raw_grid(raw, black, white):
    h,w = raw.shape
    return np.column_stack([((raw[ry::2,rx::2].astype(np.float64)-black)/(white-black))
                            .reshape(32,h//64,32,w//64).mean(axis=(1,3)).ravel()
                            for ry,rx in ((0,0),(0,1),(1,0),(1,1))])


def grid_ratios(g):
    green = (g[:,1]+g[:,2]) * .5
    return green[:,None] / g[:,[0,3]] * 4096.0


def inverse(lib, descriptor, ratios):
    handle = C.c_void_p()
    require(lib.hb_phone_temperature_create(C.byref(descriptor), C.byref(handle))==0,
            'phone model could not be created')
    output=[]
    try:
        for red, blue in ratios:
            gain=(C.c_uint32*3)(int(red),4096,int(blue))
            estimate=Estimate()
            st=lib.hb_phone_temperature_from_gain(handle,gain,C.byref(estimate))
            require(st==0, f'inverse failed: {st}')
            output.append([float(estimate.kelvin),float(estimate.tint),float(estimate.ratio_residual)])
    finally:
        lib.hb_phone_temperature_destroy(handle)
    return np.asarray(output)


def main():
    p=argparse.ArgumentParser()
    for name in ['capture','dng','domain-json','host-library','private-report','public-report']:
        p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    input_paths=(a.capture,a.dng,a.domain_json,a.host_library)
    original_hashes={path.name:sha256(path) for path in input_paths}
    capture=json.loads(a.capture.read_text())
    domain=json.loads(a.domain_json.read_text())
    orig=capture['original_still']
    selected=orig['selected_raw_sensor_result']
    chars=orig['selected_sensor_characteristics']
    provenance=orig['sensor_provenance']
    delivered=capture['delivered_raw']
    effective=capture['effective_photon_export']
    scene=capture['scene_candidate_diagnostics']
    require(capture['schema']=='hasselblad-photon-capture-evidence-v1', 'capture schema')
    require(capture['input_frame_count']==1 and capture['calibration_evidence_usable'] is True,
            'capture usability')
    require(capture['pairing_status']=='image_timestamp_equals_selected_still_result_timestamp',
            'capture pairing status')
    require(not capture['calibration_unusable_reasons'] and not provenance['unproven_reasons'],
            'provenance exclusions')
    for field in ('sensor_provenance_matched','result_camera_id_matched',
                  'request_targets_recorded_raw_surface','selected_and_logical_frame_number_matched'):
        require(provenance[field] is True, 'unproven '+field)
    require(provenance['selected_characteristics_are_logical'] is False,'selected logical sensor')
    frame=capture['frame_number']
    timestamp=delivered['sensor_timestamp_ns']
    camera_id=provenance['selected_calibration_camera_id']
    require(frame==orig['selected_result_frame_number']==orig['logical_frame_number']
            ==str(domain['source_frame_number']), 'frame number mismatched')
    require(timestamp==selected['android.sensor.timestamp']
            ==orig['selected_sensor_timestamp_ns']
            ==domain['source_sensor_timestamp_ns'], 'capture timestamp mismatched')
    require(camera_id==provenance['selected_result_camera_id']
            ==domain['physical_sensor_id']==effective['camera_id'], 'physical camera mismatch')
    require(scene['raw_sensor_timestamp_ns']==timestamp and
            scene['frame_number']==frame and scene['status']=='completed', 'scene sidecar mismatch')
    require(scene['render_applied'] is False and domain['render_applied'] is False,
            'diagnostic used as renderer')
    require(effective['app']['version_code']==27184 and
            effective['app']['version_name']=='0.1-hb-domain3', 'wrong build')
    require(delivered['sensor_timestamp_ns']==selected['android.sensor.timestamp'] and
            delivered['row_stride_bytes']==8192 and delivered['pixel_stride_bytes']==2 and
            delivered['image_crop_rect']==[0,0,4096,3072] and not delivered['binned'] and
            delivered['copy_offset_bytes']==0, 'unexpected RAW geometry')
    require(capture['dng']['bytes']==a.dng.stat().st_size and
            capture['dng']['sha256']==original_hashes[a.dng.name], 'original DNG hash mismatch')
    require(re.fullmatch(r'IMG_[0-9]{8}_[0-9]{6}\.dng', capture['dng']['name']) is not None, 'original filename identity')

    all_values=all_exact=0
    canonicalizations=[]
    with tifffile.TiffFile(a.dng) as tif:
        require(len(tif.pages)==1,'multiple image IFDs')
        page=tif.pages[0]
        require(page.shape==(3072,4096) and str(page.dtype)=='uint16', 'DNG RAW geometry')
        require(int(page.tags['Compression'].value)==1 and
                page.tags['CFAPattern'].value==bytes([0,1,1,2]), 'RAW CFA encoding')
        tags=page.tags
        require(camera_id in re.findall(r'CameraID\s*=\s*(\w+)',str(tags['ImageDescription'].value)),
                'DNG camera id absent')
        for dng_tag, camera_key in MATRIX_TAGS:
            vals=tags[dng_tag].value
            rats=chars[camera_key]
            require(len(vals)==18 and len(rats)==9, 'matrix size mismatch')
            for idx in range(9):
                a_rat=tuple(vals[2*idx:2*idx+2]); b_rat=(rats[idx]['numerator'],rats[idx]['denominator'])
                require(fractions.Fraction(*a_rat)==fractions.Fraction(*b_rat),
                        'DNG matrix numerical difference '+dng_tag+'['+str(idx)+']')
                all_values+=1
                all_exact+=(a_rat==b_rat)
                if a_rat!=b_rat: canonicalizations.append({'tag':dng_tag,'index':idx,
                    'dng':list(a_rat),'camera2':list(b_rat)})
        for idx in (1,2):
            dng_illum=int(tags['CalibrationIlluminant'+str(idx)].value)
            orig_illum=int(chars['android.sensor.referenceIlluminant'+str(idx)])
            require(dng_illum==orig_illum, 'DNG illuminant mismatch')
            all_values+=1;all_exact+=1
        neutral_tag=tags['AsShotNeutral'].value
        raw_neutral=selected['android.sensor.neutralColorPoint']
        for idx in range(3):
            a_rat=tuple(neutral_tag[2*idx:2*idx+2])
            b_rat=(raw_neutral[idx]['numerator'],raw_neutral[idx]['denominator'])
            require(fractions.Fraction(*a_rat)==fractions.Fraction(*b_rat),'AsShotNeutral mismatch')
            all_values+=1;all_exact+=(a_rat==b_rat)
        require(all_values==59,'expected 59 tags/coefficients')
        photon=np.asarray(effective['neutral_used'],dtype=np.float64)
        original=np.array([r['numerator']/r['denominator'] for r in raw_neutral])
        require(np.array_equal(photon,original),'Photon/HAL neutral differs')
        require(all(float(neutral_tag[2*i]/neutral_tag[2*i+1])==original[i]
                    for i in range(3)),'DNG/HAL neutral differs')
        original_shading=selected['android.statistics.lensShadingCorrectionMap']
        require(original_shading['columns']==17 and original_shading['rows']==13,'original shading dimensions')
        require(effective['has_lens_shading_map'] is True and
                effective['lens_shading_map_size']==[17,13], 'Photon shading dimensions')
        require(original_shading['gains']==effective['lens_shading_gain_map'] and
                len(original_shading['gains'])==884, 'Photon shade-map copy differs')
        require(scene['lens_shading_applied'] is False,
                'Scene1B shading sensitivity no longer applicable')
        require(scene['raw_valid_blocks']==1024 and scene['saturated_blocks']==0,
                'Unexpected scene blocks')
        black_values=tuple(tags['BlackLevel'].value)
        require(len(black_values)==4 and len(set(black_values))==1, 'unequal DNG Bayer site blacks')
        black=float(black_values[0]); white=float(tags['WhiteLevel'].value)
        require(white>black>=0, 'DNG black/white mismatch')
        require([float(v) for v in selected['android.sensor.dynamicBlackLevel']]==[black]*4
                and float(selected['android.sensor.dynamicWhiteLevel'])==white,
                'original sensor black/white differs from DNG')
        model=model_from_dng(tags)
        raw=page.asarray()
    mapped=np.array(original_shading['gains']).reshape(13,17,4)
    base=raw_grid(raw,black,white)
    corrected=shade_grid(raw,mapped,black,white)
    base_ratio=grid_ratios(base)
    corrected_ratio=grid_ratios(corrected)
    lib=start_library(a.host_library)
    base_interp=inverse(lib,model,base_ratio)
    corrected_interp=inverse(lib,model,corrected_ratio)
    require(np.all(np.isfinite(base_interp)) and np.all(np.isfinite(corrected_interp)),
            'nonfinite inverse model')
    old_to_shaded=np.median(corrected_interp[:,1])-np.median(base_interp[:,1])
    require(all(sha256(path)==original_hashes[path.name] for path in input_paths),
            'input modified during audit')
    private={
      'status':'PASS','schema':'hasselblad-domain3-pair-and-shading-private-v1',
      'source_hashes':original_hashes,'source_capture_original_dng_name':capture['dng']['name'],
      'identity':{'dng_hash_exact':True,'size_exact':True,'camera_id':camera_id,
                  'frame_number':frame,'sensor_timestamp_ns':timestamp,
                  'frame_domain_and_scene_match':True,'physical_sensor_provenance_match':True,
                  'dng_original_camera_metadata_match':True,
                  'jpeg_file_level_pairing_verified':False},
      'camera2_to_dng':{'numerical_coefficients_equal':all_values,
                        'rational_entries_exact':all_exact,
                        'equivalent_zero_denominator_changes':canonicalizations},
      'color_and_photon':{'HAL_original_neutral':original.tolist(),
                          'Photon_effective_neutral':photon.tolist(),
                          'DNG_neutral_equal':True,'Photon_matrix_processing':'Existing Photon, not HNCS',
                          'original_raw_binning_flag_reported':selected.get('android.sensor.rawBinningFactorUsed'),
                          'scene_raw_binning_flag_outside_scope':scene['raw_binning_flag_outside_scope']},
      'shading_sensitivity':{'provenance':'Camera2 actual shading map; hypothetical bilinear application to original DNG Bayer pixels; rendering not modified',
                            'map_rows':13,'map_columns':17,'map_channel_count':4,
                            'original_map_equal_to_Photon_export':True,
                            'scene_diagnostic_shading_applied':False,
                            'original_red_blue_median_q12':np.median(base_ratio,axis=0).tolist(),
                            'hypothetical_red_blue_median_q12':np.median(corrected_ratio,axis=0).tolist(),
                            'original_red_blue_std_q12':np.std(base_ratio,axis=0).tolist(),
                            'hypothetical_red_blue_std_q12':np.std(corrected_ratio,axis=0).tolist(),
                            'original_Ct_tint_median':np.median(base_interp,axis=0).tolist(),
                            'hypothetical_Ct_tint_median':np.median(corrected_interp,axis=0).tolist(),
                            'hypothetical_tint_median_shift':float(old_to_shaded),
                            'tint_not_physically_calibrated':True},
      'photographic_renderer_changed':False,'shipping_neutral_selected':False,
    }
    public={'status':'PASS','schema':'hasselblad-domain3-pair-and-shading-public-v1',
            'strict_dng_frame_pairing_proven':True,
            'original_dng_sha256_verified':True,'dng_file_size_verified':True,
            'original_physical_camera_and_timestamp_verified':True,
            'device_domain_frame_matches_capture_sidecar':True,
            'camera2_to_dng_numerical_value_matches':all_values,
            'camera2_to_dng_exact_rational_matches':all_exact,
            'camera2_to_dng_equivalent_zero_denominator_changes':len(canonicalizations),
            'original_HAL_and_effective_Photon_neutral_equal':True,
            'original_and_effective_lens_shading_map_equal':True,
            'scene1b_shading_unchanged':True,
            'shading_sensitivity_evaluated_not_rendered':True,
            'shading_explains_tint_offset_fully':False,
            'photographic_renderer_changed':False,'shipping_neutral_selected':False,
            'jpeg_file_level_pairing_proven':False,
            'missing_external_physical_light_and_target_calibration':True}
    a.private_report.parent.mkdir(parents=True,exist_ok=True)
    a.public_report.parent.mkdir(parents=True,exist_ok=True)
    a.private_report.write_text(json.dumps(private,indent=2)+'\n')
    a.public_report.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps(public,indent=2))

if __name__=='__main__':main()
