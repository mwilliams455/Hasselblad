#!/usr/bin/env python3
"""Hasselblad Photon Stage7: read-only labelled Bayer ROI evidence.

This does NOT implement Hasselblad AWB, choose white balance, or modify JPEG/DNG.
A human-provided ROI label is never inferred from a neutral-looking colour.
The HAL and native Stage4 scene candidates are *comparators*, not truth labels.

Input: original 2D regular RGGB DNG, original .capture.json and bound ROI JSON.
Output: private measurements and a separately public-safe audit (no scene data).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import tifffile

SCHEMA = 'hasselblad-stage7-labelled-roi-v1'
ROLES = ('neutral_reference', 'nonneutral_holdout', 'unlabelled_scene')
SOURCES = ('measured_reference_card', 'human_visual_annotation', 'unlabelled')
ILLUMINANTS = ('daylight', 'warm_artificial', 'mixed', 'other', 'unknown')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def rational(entry):
    check(isinstance(entry, dict), 'neutral_rational_invalid')
    a, b = entry.get('numerator'), entry.get('denominator')
    check(isinstance(a, int) and isinstance(b, int) and b > 0 and a > 0, 'neutral_rational_invalid')
    return a / b


def verify_capture(cap, dng_path, raw):
    check(cap.get('schema') == 'hasselblad-photon-capture-evidence-v1', 'bad_capture_schema')
    check(cap.get('calibration_evidence_usable') is True, 'unproven_capture_metadata')
    check(cap.get('input_frame_count') == 1, 'multi_frame_capture')
    check(cap.get('pixel_rendering_changed_by_sidecar') is False, 'changed_rendering')
    identity = cap['dng']
    check(identity['sha256'] == sha256(dng_path), 'wrong_dng_sha256')
    check(identity['bytes'] == dng_path.stat().st_size, 'wrong_dng_size')
    still = cap['original_still']
    provenance = still['sensor_provenance']
    for k in ('sensor_provenance_matched', 'result_camera_id_matched',
              'request_targets_recorded_raw_surface', 'selected_and_logical_frame_number_matched'):
        check(provenance.get(k) is True, 'unproven_' + k)
    check(provenance.get('selected_characteristics_are_logical') is False, 'logical_sensor_not_supported')
    check(provenance['selected_calibration_camera_id'] == provenance['selected_result_camera_id'], 'sensor_mismatch')
    check(cap['frame_number'] == still['selected_result_frame_number'], 'frame_mismatch')
    dr = cap['delivered_raw']
    check(dr['format'] == 32 and dr['binned'] is False and dr['copy_offset_bytes'] == 0,
          'unsupported_raw_copy')
    w, h = int(dr['copied_width']), int(dr['copied_height'])
    check(dr['image_crop_rect'] == [0, 0, w, h] and dr['copied_crop_x'] == 0 and
          dr['copied_crop_y'] == 0, 'cropped_raw')
    check(w % 2 == 0 and h % 2 == 0 and raw.shape == (h, w) and raw.dtype == np.uint16,
          'unsupported_raw_geometry')
    check(dr['sensor_timestamp_ns'] == still['selected_sensor_timestamp_ns'] ==
          still['selected_raw_sensor_result']['android.sensor.timestamp'], 'timestamp_mismatch')
    characteristics = still['selected_sensor_characteristics']
    check(characteristics['android.sensor.info.colorFilterArrangement'] == 0, 'only_RGGB_supported')
    check(still['selected_raw_sensor_result']['android.sensor.pixelMode'] == 0, 'unsupported_pixel_mode')
    black = np.asarray(still['selected_raw_sensor_result']['android.sensor.dynamicBlackLevel'], dtype=np.float64)
    white = int(still['selected_raw_sensor_result']['android.sensor.dynamicWhiteLevel'])
    check(black.shape == (4,) and np.isfinite(black).all() and
          (black >= 0).all() and white > max(black), 'invalid_dynamic_levels')
    original_result = still['selected_raw_sensor_result']
    exposure = int(original_result['android.sensor.exposureTime'])
    iso = int(original_result['android.sensor.sensitivity'])
    check(1000 <= exposure <= 60_000_000_000 and 1 <= iso <= 409600,
          'unusable_exposure_or_iso')
    neutral = [rational(e) for e in still['selected_raw_sensor_result']['android.sensor.neutralColorPoint']]
    check(len(neutral) == 3 and abs(neutral[1] - 1) < 1e-8, 'invalid_green_normalization')
    export = cap['effective_photon_export']
    check(export['camera_id'] == provenance['selected_calibration_camera_id'], 'effective_camera_mismatch')
    check(export['raw_size'] == [w, h] and export['cfa_pattern'] == 0, 'effective_raw_mismatch')
    check(np.allclose(export['neutral_used'], neutral, atol=1e-6, rtol=0), 'effective_neutral_mismatch')
    return {
        'sensor_id': provenance['selected_calibration_camera_id'],
        'frame': cap['frame_number'], 'timestamp': dr['sensor_timestamp_ns'],
        'dng_sha256': identity['sha256'], 'width': w, 'height': h,
        'dynamic_black': black, 'static_black': np.asarray(characteristics['android.sensor.blackLevelPattern'],dtype=np.float64),
        'white': white, 'hal_neutral': neutral, 'exposure_time_ns': exposure, 'ISO': iso,
        'raw_binning_factor_reported': still['selected_raw_sensor_result'].get('android.sensor.rawBinningFactorUsed'),
    }


def verify_annotations(ann, binding):
    check(ann.get('schema') == SCHEMA, 'wrong_roi_annotation_schema')
    b = ann.get('binding', {})
    for k, v in [('dng_sha256', binding['dng_sha256']), ('physical_sensor_id', binding['sensor_id']),
                 ('frame_number', binding['frame']), ('sensor_timestamp_ns', binding['timestamp'])]:
        check(str(b.get(k)) == str(v), 'annotation_capture_binding_mismatch_' + k)
    regions = ann.get('regions', [])
    check(isinstance(regions, list) and 1 <= len(regions) <= 32, 'invalid_region_count')
    identifiers = set()
    for r in regions:
        check(isinstance(r,dict), 'invalid_region_record')
        name = r.get('id')
        check(isinstance(name, str) and 1 <= len(name) <= 64 and name not in identifiers, 'invalid_roi_id')
        identifiers.add(name)
        check(r.get('role') in ROLES, 'invalid_role')
        check(r.get('source') in SOURCES, 'invalid_label_source')
        check(r.get('illuminant') in ILLUMINANTS, 'invalid_illuminant_label')
        check(r['role'] != 'neutral_reference' or r['source'] == 'measured_reference_card',
              'neutral_requires_known_reference_card')
        if r['source'] == 'measured_reference_card':
            check(r['role'] == 'neutral_reference', 'reference_card_label_conflict')
            check(r['illuminant'] in ('daylight','warm_artificial','other'),
                  'reference_requires_single_illuminant_label')
        rect = r.get('rect_raw_xywh')
        check(isinstance(rect,list) and len(rect)==4 and all(type(i) is int for i in rect), 'invalid_raw_roi')
        x, y, w, h = rect
        check(w >= 32 and h >= 32 and (x|y|w|h) % 2 == 0 and x >= 0 and y >= 0 and
              x+w <= binding['width'] and y+h <= binding['height'], 'raw_roi_out_of_bounds_or_unaligned')
    return regions


def sample_map(mp, px, py, w, h):
    """Stage5-like GL_LINEAR sample; a research hypothesis, not camera's RAW shading state."""
    rows, cols, _ = mp.shape
    fx = px * cols/w - .5
    fy = py * rows/h - .5
    xi = np.floor(fx).astype(np.int64); yi = np.floor(fy).astype(np.int64)
    tx = fx - xi; ty = fy - yi
    x0 = np.clip(xi, 0, cols-1); x1 = np.clip(xi+1, 0, cols-1)
    y0 = np.clip(yi, 0, rows-1); y1 = np.clip(yi+1, 0, rows-1)
    a = mp[y0, x0]; b = mp[y0, x1]; c = mp[y1, x0]; d = mp[y1, x1]
    return (a*(1-tx[...,None])+b*tx[...,None])*(1-ty[...,None]) + \
           (c*(1-tx[...,None])+d*tx[...,None])*ty[...,None]


def map_factor(mp, px, py, w, h, site):
    v = sample_map(mp, px, py, w, h)
    rgb = np.stack((v[...,0], (v[...,1]+v[...,2])*.5, v[...,3]), axis=-1)
    channel = (0,1,1,2)[site]
    return rgb[...,channel]/np.maximum(rgb.mean(axis=-1), 1e-4)


def site_stack(raw, rect, black, white):
    x, y, w, h = rect
    patch = raw[y:y+h, x:x+w].astype(np.float64)
    sites = np.stack((patch[0::2,0::2], patch[0::2,1::2],
                      patch[1::2,0::2], patch[1::2,1::2]),axis=-1)
    return (sites-black)/(white-black)


def model_sites(raw, rect, binding, lens_map):
    d = site_stack(raw, rect, binding['dynamic_black'], binding['white'])
    x,y,w,h = rect
    versions = {'original_dng_no_extra_shading_dynamic_black': d}
    versions['original_dng_no_extra_shading_static_black'] = site_stack(raw, rect, binding['static_black'], binding['white'])
    if lens_map is not None:
        # Gain-map interpolation at the actual four Bayer sites. The camera HAL
        # may already compensate RAW shading; both corrections are hypotheses.
        gx, gy = np.meshgrid(np.arange(x,x+w,2,dtype=np.float64),
                             np.arange(y,y+h,2,dtype=np.float64))
        absolute = np.empty_like(d)
        relative = np.empty_like(d)
        for site,(dx,dy) in enumerate(((0,0),(1,0),(0,1),(1,1))):
            g = sample_map(lens_map,gx+dx,gy+dy,binding['width'],binding['height'])
            absolute[...,site] = d[...,site]*g[...,site]
            relative[...,site] = d[...,site]*map_factor(lens_map,gx+dx,gy+dy,
                        binding['width'],binding['height'],site)
        versions['hypothetical_absolute_hal_shading'] = absolute
        versions['hypothetical_photon_relative_shading'] = relative
    return versions


def summarize_sites(z, valid):
    if not np.any(valid):
        return {'status':'no_valid_2x2_cells','valid_cells':0}
    arr = z[valid]
    avg = arr.mean(axis=0)
    green = (avg[1]+avg[2])/2
    check(avg[0] > 0 and green > 0 and avg[3] > 0, 'nonpositive_region_means')
    neutral = [float(avg[0]/green),1.,float(avg[3]/green)]
    gains = [float(green/avg[0]),1.,float(green/avg[3])]
    vgr = float(abs(avg[1]-avg[2])/green)
    return {'status':'measured','valid_cells':int(valid.sum()),
            'site_means_linear':list(map(float,avg)),
            'neutral_green_normalized':neutral, 'gains_green_normalized':gains,
            'green_site_disagreement_fraction':vgr,
            'green_mean_linear':float(green)}


def comparison(region_gain, candidate_gain):
    c = np.asarray(candidate_gain,dtype=np.float64)
    a = np.asarray(region_gain,dtype=np.float64)
    check(c.shape == (3,) and a.shape == (3,) and np.isfinite(c).all() and
          (c > 0).all(), 'invalid_candidate_gain')
    residual = np.log2(c[[0,2]]/a[[0,2]])
    return {'signed_red_blue_gain_residual_stops':residual.tolist(),
            'max_abs_gain_residual_stops':float(np.abs(residual).max()),
            'l2_green_normalized_q12_distance':float(np.linalg.norm((c[[0,2]]-a[[0,2]])*4096))}


def evaluate(cap, raw, ann, binding):
    still = cap['original_still']['selected_raw_sensor_result']
    lens = still.get('android.statistics.lensShadingCorrectionMap')
    mp = None
    if lens is not None:
        r,c = int(lens['rows']),int(lens['columns'])
        gains = np.asarray(lens['gains'],dtype=np.float32)
        check(r >= 2 and c >= 2 and gains.size == r*c*4 and np.isfinite(gains).all(), 'invalid_lens_map')
        mp = gains.astype(np.float16).astype(np.float64).reshape(r,c,4)
    candidates = [{'id':'HAL_original_capture','role':'external_comparator',
                   'gains':[1/binding['hal_neutral'][0],1.,1/binding['hal_neutral'][2]]}]
    diag = cap.get('scene_candidate_diagnostics',{})
    for policy in diag.get('policies',[]):
        q = policy.get('gain_q12')
        if policy.get('decision') == 'diagnostic_candidate' and isinstance(q,list) and len(q)==3 and all(isinstance(e,int) and e>0 for e in q):
            candidates.append({'id':'stage4_diagnostic_radius_q12_'+str(policy['radius_q12']),
                               'role':'uncalibrated_diagnostic_not_selected',
                               'gains':[x/4096 for x in q]})
    records=[]
    for reg in verify_annotations(ann,binding):
        rect = reg['rect_raw_xywh']
        sources = model_sites(raw,rect,binding,mp)
        canonical = sources['original_dng_no_extra_shading_dynamic_black']
        valid = np.all((canonical >= .005)&(canonical <= .95)&np.isfinite(canonical),axis=-1)
        too_dim = np.any(canonical < .005,axis=-1)
        too_bright = np.any(canonical > .95,axis=-1)
        hist = {'total_cells':int(valid.size),'valid_cells':int(valid.sum()),
                'excluded_dim_or_saturated_cells':int(valid.size-valid.sum()),
                'dim_cells':int(too_dim.sum()), 'near_saturation_cells':int(too_bright.sum()),
                'valid_fraction':float(valid.mean())}
        bases = {}
        for name, z in sources.items():
            m = summarize_sites(z,valid)
            if m['status']=='measured':
                m['comparisons_not_truth_checks'] = {t['id']:comparison(m['gains_green_normalized'],t['gains'])
                                                       for t in candidates}
            bases[name] = m
        original = bases['original_dng_no_extra_shading_dynamic_black']
        roi_result = {'id':reg['id'],'role':reg['role'],'source':reg['source'],
                      'illuminant':reg['illuminant'],'rect_raw_xywh':rect,
                      'cell_quality':hist,'basis_hypotheses':bases,
                      'eligible_for_future_controlled_reference_study':reg['role']=='neutral_reference' and
                           reg['source']=='measured_reference_card' and original['status']=='measured' and
                           hist['valid_fraction']>=.95,
                      'calibration_authorized':False,'render_permitted':False}
        records.append(roi_result)
    return {'schema':'hasselblad-stage7-labelled-roi-evidence-v1','status':'completed',
            'render_applied':False,'automatic_wb_selected':False,'calibrated_policy':False,
            'production_wb_unchanged':True,'capture_identity':{
                'dng_sha256':binding['dng_sha256'],'physical_sensor_id':binding['sensor_id'],
                'frame_number':binding['frame'],'sensor_timestamp_ns':binding['timestamp'],
                'width':binding['width'],'height':binding['height'],
                'raw_binning_factor_used_reported':binding['raw_binning_factor_reported']},
            'neutral_comparators':[{'id':x['id'],'role':x['role']} for x in candidates],
            'scope':'DNG Bayer ROI evidence; hypothetical shading bases. No illuminant ground truth inferred from pixels.',
            'regions':records}


def test():
    raw = np.full((64,64),64,dtype=np.uint16)
    raw[0::2,0::2]=164
    raw[0::2,1::2]=264
    raw[1::2,0::2]=264
    raw[1::2,1::2]=114
    binding={'width':64,'height':64,'dynamic_black':np.full(4,64.),'static_black':np.full(4,64.),'white':1024,
             'dng_sha256':'a','sensor_id':'2','frame':'1','timestamp':'2','hal_neutral':[.5,1,.25],
             'raw_binning_factor_reported':False}
    v=model_sites(raw,[0,0,64,64],binding,np.ones((2,2,4),dtype=np.float16))
    k=summarize_sites(v['original_dng_no_extra_shading_dynamic_black'],np.ones((32,32),bool))
    assert abs(k['neutral_green_normalized'][0]-.5)<1e-12
    assert abs(k['neutral_green_normalized'][2]-.25)<1e-12
    assert comparison(k['gains_green_normalized'],[2,1,4])['max_abs_gain_residual_stops']<1e-12
    assert np.allclose(v['original_dng_no_extra_shading_dynamic_black'],v['hypothetical_photon_relative_shading'])
    assert np.allclose(v['original_dng_no_extra_shading_dynamic_black'],v['hypothetical_absolute_hal_shading'])
    ann={'schema':SCHEMA,'binding':{'dng_sha256':'a','physical_sensor_id':'2','frame_number':'1','sensor_timestamp_ns':'2'},
         'regions':[{'id':'gray_card','role':'neutral_reference','source':'measured_reference_card',
                     'illuminant':'daylight','rect_raw_xywh':[0,0,64,64]}]}
    verify_annotations(ann,binding)
    # A perfectly neutral-looking synthetic sample is not, by its pixels,
    # grounds to select a WB. Even an annotated card remains reference-only.
    mockcap={'original_still':{'selected_raw_sensor_result':{}},
       'scene_candidate_diagnostics':{'policies':[{'decision':'diagnostic_candidate',
           'radius_q12':128,'gain_q12':[8192,4096,16384]}]}}
    outcome=evaluate(mockcap,raw,ann,binding)
    assert outcome['production_wb_unchanged'] and not outcome['automatic_wb_selected']
    assert outcome['regions'][0]['eligible_for_future_controlled_reference_study']
    assert not outcome['regions'][0]['render_permitted']
    assert outcome['regions'][0]['basis_hypotheses']['original_dng_no_extra_shading_dynamic_black']['comparisons_not_truth_checks']['stage4_diagnostic_radius_q12_128']['max_abs_gain_residual_stops']<1e-12
    ann['regions'][0]['role']='nonneutral_holdout'
    ann['regions'][0]['source']='human_visual_annotation'
    ann['regions'][0]['illuminant']='unknown'
    outcome=evaluate(mockcap,raw,ann,binding)
    assert not outcome['regions'][0]['eligible_for_future_controlled_reference_study']
    assert not outcome['regions'][0]['render_permitted']
    ann['regions'][0]['role']='neutral_reference'
    ann['regions'][0]['source']='measured_reference_card'
    ann['regions'][0]['illuminant']='daylight'
    import copy
    for bad, value in [('rect_raw_xywh',[1,0,32,32]),('role','not_really_neutral'),('source','unlabelled')]:
        other=copy.deepcopy(ann);other['regions'][0][bad]=value
        try:verify_annotations(other,binding)
        except ValueError:pass
        else:raise AssertionError('invalid_roi_not_rejected:'+bad)
    other=copy.deepcopy(ann);other['binding']['dng_sha256']='wrong'
    try:verify_annotations(other,binding)
    except ValueError:pass
    else:raise AssertionError('annotation_hash_not_bound')
    print('PASS Stage7 ROI orientation-free RGGB measurements, gain comparisons, strict labels/bindings and abstention')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--capture',type=Path)
    p.add_argument('--dng',type=Path)
    p.add_argument('--annotations',type=Path)
    p.add_argument('--private-report',type=Path)
    p.add_argument('--public-report',type=Path)
    args=p.parse_args()
    if args.self_test:
        test();return
    check(all([args.capture,args.dng,args.annotations,args.private_report,args.public_report]),'missing_required_paths')
    cap=json.loads(args.capture.read_text());ann=json.loads(args.annotations.read_text())
    raw=tifffile.imread(args.dng)
    binding=verify_capture(cap,args.dng,raw)
    verify_annotations(ann,binding)
    result=evaluate(cap,raw,ann,binding)
    args.private_report.parent.mkdir(parents=True,exist_ok=True)
    args.public_report.parent.mkdir(parents=True,exist_ok=True)
    args.private_report.write_text(json.dumps(result,indent=2)+'\n')
    public={'schema':'hasselblad-stage7-public-audit-v1','status':'completed',
            'region_count':len(result['regions']), 'no_photographic_wb_selected':True,
            'render_applied':False,'unlabelled_scene_neutral_claim':False,
            'private_scene_or_sensor_data_exported':False}
    args.public_report.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps(public,indent=2))


if __name__ == '__main__':
    main()
