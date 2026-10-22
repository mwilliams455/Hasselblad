#!/usr/bin/env python3
"""Stage 7B: research-only cross-capture WB reference/holdout evaluator.

Consumes PRIVATE reports emitted by stage7_labelled_roi.py, which validates an
original RGGB DNG+capture+ROI binding. This second-stage aggregator does not
read photograph pixels and DOES NOT independently re-verify DNG contents;
raw identity must be established by the producer, not assumed from filenames.

Never selects a photographic neutral, fits an AWB policy, changes the phone's
renderer, or calls a pale/unlabelled/coloured object a certified grey card.
All frame identities and scene measurements remain in --private-report only.
"""
import argparse
import collections
import copy
import hashlib
import json
import math
import pathlib
import re
import statistics
import tempfile

SCHEMA = 'hasselblad-stage7b-study-manifest-v1'
EVIDENCE_SCHEMA = 'hasselblad-stage7-labelled-roi-evidence-v1'
BASE = 'original_dng_no_extra_shading_dynamic_black'
HYPOTHESES = ('original_dng_no_extra_shading_dynamic_black',
              'original_dng_no_extra_shading_static_black',
              'hypothetical_absolute_hal_shading',
              'hypothetical_photon_relative_shading')
ALLOWED_ILLUMINANTS = ('daylight', 'warm_artificial', 'other')
ROLES = ('neutral_reference', 'nonneutral_holdout', 'unlabelled_scene')
GAIN_ID_RE = re.compile(r'^(HAL_original_capture|stage4_diagnostic_radius_q12_\d+)$')
HASH_RE = re.compile(r'^[0-9a-f]{64}$')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def positive(v, reason):
    require(type(v) in (float, int) and math.isfinite(v) and v > 0, reason)
    return float(v)


def finite(v, reason):
    require(type(v) in (float, int) and math.isfinite(v), reason)
    return float(v)


def safe_path(root, rel):
    require(isinstance(rel, str) and len(rel) < 300 and rel and '\\' not in rel,
            'invalid_relative_input_path')
    require(all(x not in ('.','..') for x in rel.split('/')),
            'unsafe_input_report_path')
    p = pathlib.PurePosixPath(rel)
    require(not p.is_absolute() and all(x not in ('..', '.') for x in p.parts)
            and len(p.parts) >= 1 and p.suffix == '.json',
            'unsafe_input_report_path')
    resolved = (root / rel).resolve()
    require(resolved.is_relative_to(root.resolve()), 'report_path_outside_private_study_root')
    return resolved


def read_manifest(path):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    require(manifest.get('schema') == SCHEMA, 'wrong_manifest_schema')
    items = manifest.get('reports')
    require(isinstance(items, list) and 1 <= len(items) <= 256, 'invalid_study_report_count')
    seen = set()
    for item in items:
        require(isinstance(item, dict) and set(item) == {'id','path','binding'},
                'invalid_study_item_fields')
        label = item['id']
        require(isinstance(label, str) and 1 <= len(label) <= 64 and label not in seen,
                'duplicate_or_invalid_study_id')
        seen.add(label)
        b = item['binding']
        require(isinstance(b,dict) and set(b) == {'dng_sha256','physical_sensor_id',
             'frame_number','sensor_timestamp_ns'}, 'manifest_binding_fields')
        require(isinstance(b['dng_sha256'],str) and HASH_RE.fullmatch(b['dng_sha256']),
                'invalid_manifest_hash')
        for key in ('physical_sensor_id','frame_number','sensor_timestamp_ns'):
            require(str(b[key]).isdigit(), 'invalid_manifest_binding_'+key)
    return items


def validate_report(report, declared):
    require(isinstance(report,dict) and report.get('schema') == EVIDENCE_SCHEMA
            and report.get('status') == 'completed', 'unrecognized_stage7_report')
    for field, expected in [('render_applied',False),('automatic_wb_selected',False),
                            ('calibrated_policy',False),('production_wb_unchanged',True)]:
        require(report.get(field) is expected, 'report_render_or_calibration_not_safe_'+field)
    cid = report.get('capture_identity')
    require(isinstance(cid,dict), 'missing_capture_identity')
    for report_key, manifest_key in [('dng_sha256','dng_sha256'),
                    ('physical_sensor_id','physical_sensor_id'),
                    ('frame_number','frame_number'),
                    ('sensor_timestamp_ns','sensor_timestamp_ns')]:
        require(str(cid.get(report_key)) == str(declared[manifest_key]),
                'manifest_and_report_capture_mismatch_'+report_key)
    require(HASH_RE.fullmatch(str(cid.get('dng_sha256',''))), 'invalid_report_dng_hash')
    require(HASH_RE.fullmatch(str(cid.get('camera_profile_sha256',''))),
            'missing_or_invalid_profile_fingerprint')
    for key in ('width','height','exposure_time_ns','ISO'):
        require(type(cid.get(key)) is int and cid[key]>0,'invalid_capture_'+key)
    require(cid['width']%2 == 0 and cid['height']%2 == 0
            and cid['exposure_time_ns'] >= 1000 and cid['exposure_time_ns'] <= 60_000_000_000
            and cid['ISO'] <= 409600,'invalid_capture_geometry_or_exposure')
    require(cid.get('raw_binning_factor_used_reported') in (True,False,None),
            'unrecognized_raw_binning_flag')
    comp = report.get('neutral_comparators')
    require(isinstance(comp,list) and 1 <= len(comp) <= 20,
            'invalid_reference_comparator_list')
    seen = set()
    for c in comp:
        require(isinstance(c,dict), 'invalid_comparator')
        name = c.get('id')
        require(isinstance(name,str) and GAIN_ID_RE.fullmatch(name) and name not in seen,
                'invalid_or_duplicate_comparator_id')
        seen.add(name)
        require(c.get('role') == ('external_comparator' if name=='HAL_original_capture'
              else 'uncalibrated_diagnostic_not_selected'), 'comparator_mislabelled')
    require('HAL_original_capture' in seen,'missing_original_HAL_reference')
    rois = report.get('regions')
    require(isinstance(rois,list) and 1 <= len(rois) <= 32, 'invalid_report_regions')
    ids = set()
    for r in rois:
        require(isinstance(r,dict),'invalid_roi_record')
        label=r.get('id')
        require(isinstance(label,str) and label not in ids and label != '',
                'invalid_or_repeated_roi_id')
        ids.add(label)
        require(r.get('role') in ROLES, 'invalid_roi_role')
        require(r.get('render_permitted') is False and r.get('calibration_authorized') is False,
                'unsafe_roi_render_authorization')
        if r['role']=='neutral_reference':
            target_id=r.get('reference_target_id')
            require(isinstance(target_id,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',target_id),
                    'missing_or_invalid_reference_card_identity')
            require(r.get('source') == 'measured_reference_card' and
                    r.get('illuminant') in ALLOWED_ILLUMINANTS,
                    'uncertified_or_mixed_reference_label')
        else:
            require(r.get('source') != 'measured_reference_card', 'card_source_not_reference')
            require(r.get('reference_target_id') is None, 'reference_target_on_nonneutral_roi')
        cq = r.get('cell_quality',{})
        valid_fraction = finite(cq.get('valid_fraction'), 'invalid_valid_fraction')
        require(0 <= valid_fraction <= 1,'invalid_valid_fraction_range')
        require(type(cq.get('valid_cells')) is int and
                type(cq.get('total_cells')) is int and
                0 <= cq['valid_cells'] <= cq['total_cells'] and cq['total_cells'] > 0,
                'invalid_quality_cell_count')
        require(abs(cq['valid_cells']/cq['total_cells'] - valid_fraction)<1e-8,
                'quality_fraction_not_backed_by_counts')
        bases = r.get('basis_hypotheses',{})
        require(isinstance(bases,dict) and BASE in bases and
                all(k in HYPOTHESES for k in bases),'invalid_shading_hypothesis_label')
        canonical = bases[BASE]
        measured = canonical.get('status')=='measured'
        expected_eligible=(r['role']=='neutral_reference' and
                  r.get('source')=='measured_reference_card' and measured and
                  valid_fraction >= .95)
        require(r.get('eligible_for_future_controlled_reference_study') is expected_eligible,
                'roi_eligibility_claim_inconsistent')
        for name, result in bases.items():
            require(isinstance(result,dict),'bad_basis_measurement')
            if result.get('status')=='no_valid_2x2_cells':
                require(result.get('valid_cells')==0,'invalid_empty_measurement')
                continue
            require(result.get('status')=='measured','invalid_basis_status')
            neutral=result.get('neutral_green_normalized')
            gains=result.get('gains_green_normalized')
            require(isinstance(neutral,list) and isinstance(gains,list) and
                    len(neutral)==len(gains)==3,'missing_raw_neutral_and_gains')
            for a,b in zip(neutral,gains):
                positive(a,'invalid_raw_neutral');positive(b,'invalid_raw_gain')
                require(abs(a*b-1.)<2e-5,'reciprocal_gain_neutral_mismatch')
            require(abs(neutral[1]-1)<1e-8 and abs(gains[1]-1)<1e-8,
                    'unscaled_green_gain')
            gsplit=finite(result.get('green_site_disagreement_fraction'),
                          'invalid_green_site_disagreement')
            require(gsplit >= 0 and gsplit <= 2, 'green_site_disagreement_out_of_range')
            comps=result.get('comparisons_not_truth_checks',{})
            require(isinstance(comps,dict) and set(comps) == seen,
                    'incomplete_or_changed_comparator_set')
            for cname,metric in comps.items():
                rr=metric.get('signed_red_blue_gain_residual_stops')
                require(isinstance(rr,list) and len(rr)==2,'bad_candidate_residual_pair')
                for q in rr:finite(q,'nonfinite_candidate_residual')
                require(abs(max(abs(rr[0]),abs(rr[1]))-
                        finite(metric.get('max_abs_gain_residual_stops'),
                               'invalid_candidate_max_residual'))<1e-5,
                        'candidate_residual_magnitude_mismatch')
                finite(metric.get('l2_green_normalized_q12_distance'),
                       'invalid_candidate_q12_distance')
    return cid, rois


def med(vals):
    return float(statistics.median(vals)) if vals else None


def deviation(vals):
    if len(vals)<2:return None
    midpoint=statistics.median(vals)
    return float(statistics.median(abs(x-midpoint) for x in vals))


def summarize_target(by_illum, target_id, has_nonneutral):
    per_illum={}
    for illum, entries in sorted(by_illum.items()):
        per_basis={}
        bases=sorted({k for _,r in entries for k in r['basis_hypotheses']})
        for basis in bases:
            # First combine repeated ROIs WITHIN each capture, then compute
            # across-frame variability. ROIs from one shot are not independent.
            by_frame=collections.defaultdict(list)
            for c,r in entries:
                z=r['basis_hypotheses'].get(basis)
                if z is not None and z['status']=='measured':
                    by_frame[c['dng_sha256']].append((c,z))
            if not by_frame:continue
            reds=[];blues=[]
            residual_by_candidate=collections.defaultdict(list)
            for image_hash, rois in sorted(by_frame.items()):
                reds.append(med([math.log2(z['neutral_green_normalized'][0]) for _,z in rois]))
                blues.append(med([math.log2(z['neutral_green_normalized'][2]) for _,z in rois]))
                per_frame_comp=collections.defaultdict(list)
                for c,z in rois:
                    for name,cmp in z['comparisons_not_truth_checks'].items():
                        per_frame_comp[name].append(cmp['max_abs_gain_residual_stops'])
                for name,values in per_frame_comp.items():
                    residual_by_candidate[name].append(max(values))
            per_basis[basis]={
                'labelled_roi_count':sum(len(x) for x in by_frame.values()),
                'unique_capture_count':len(by_frame),
                'median_log2_red_green':med(reds),
                'median_log2_blue_green':med(blues),
                'median_absolute_deviation_red_stops':deviation(reds),
                'median_absolute_deviation_blue_stops':deviation(blues),
                'comparator_residuals_not_ground_truth':{
                    name:{'unique_capture_count':len(arr),
                          'median_per_capture_worst_residual_stops':med(arr),
                          'worst_observed_residual_stops':max(arr)}
                    for name,arr in sorted(residual_by_candidate.items())}}
        per_illum[illum]={
            'reference_regions':len(entries),
            'independent_frames':len({c['dng_sha256'] for c,_ in entries}),
            'basis_specific_repeatability':per_basis,
            'exposure_ns_range':[min(c['exposure_time_ns'] for c,_ in entries),
                                 max(c['exposure_time_ns'] for c,_ in entries)],
            'ISO_range':[min(c['ISO'] for c,_ in entries),max(c['ISO'] for c,_ in entries)]}
    enough_daylight=per_illum.get('daylight',{}).get('independent_frames',0)>=2
    enough_warm=per_illum.get('warm_artificial',{}).get('independent_frames',0)>=2
    return {'reference_target_id':target_id,
        'reference_by_illumination':per_illum,
        'same_card_two_illuminants_minimum_exploratory_coverage':
            enough_daylight and enough_warm and has_nonneutral,
        'coverage_missing':
            ([] if enough_daylight else ['two_independent_daylight_reference_captures'])+
            ([] if enough_warm else ['two_independent_warm_reference_captures'])+
            ([] if has_nonneutral else ['labelled_nonneutral_holdout']),
        'neutral_selection_authorized':False,
        'reference_card_spectral_properties_independently_verified':False}


def compare_records(records, guard_stop):
    """Only descriptive metrics. Never select a neutral or set a shipping rule."""
    frames = set()
    roi_counts=collections.Counter()
    groups = collections.defaultdict(list)
    for sample in records:
        cid=sample['capture_identity']
        framekey=(cid['dng_sha256'],cid['physical_sensor_id'],str(cid['frame_number']),
                  str(cid['sensor_timestamp_ns']))
        require(framekey not in frames,'duplicate_original_capture_in_study')
        frames.add(framekey)
        profile=(cid['camera_profile_sha256'],cid['physical_sensor_id'],
                 cid['width'],cid['height'],cid['raw_binning_factor_used_reported'])
        groups[profile].append(sample)
        for r in sample['regions']:
            roi_counts[r['role']]+=1
    findings=[]
    for profile, members in groups.items():
        by_target=collections.defaultdict(lambda:collections.defaultdict(list))
        holdouts=[]
        for m in members:
            cid=m['capture_identity']
            for r in m['regions']:
                if r['role']=='neutral_reference':
                    if r['eligible_for_future_controlled_reference_study']:
                        by_target[r['reference_target_id']][r['illuminant']].append((cid,r))
                elif r['role']=='nonneutral_holdout':
                    holdouts.append((cid,r))
        targets={t:summarize_target(v,t,bool(holdouts)) for t,v in sorted(by_target.items())}
        exploratory_ready=any(v['same_card_two_illuminants_minimum_exploratory_coverage']
                              for v in targets.values())
        collisions=collections.Counter()
        for c,r in holdouts:
            b=r['basis_hypotheses'][BASE]
            if b['status'] != 'measured':continue
            for comparator,metric in b['comparisons_not_truth_checks'].items():
                if metric['max_abs_gain_residual_stops']<=guard_stop:
                    collisions[comparator]+=1
        findings.append({'physical_sensor_id':profile[1],
            'camera_profile_sha256':profile[0],
            'raw_geometry':[profile[2],profile[3]],
            'raw_binning_factor_used_reported':profile[4],
            'frame_count':len(members),
            'reference_targets_separately_grouped':targets,
            'nonneutral_holdout_roi_count':len(holdouts),
            'nonneutral_ratio_near_candidate_diagnostic_count':dict(collisions),
            'nonneutral_near_radius_stops_descriptive_only':guard_stop,
            'exploratory_coverage_sufficient_for_future_policy_study':exploratory_ready,
            'coverage_missing':[] if exploratory_ready else
                ['same_reference_target_with_daylight_and_warm_repeats']+
                ([] if holdouts else ['labelled_nonneutral_holdout']),
            'neutral_selection_authorized':False,
            'illuminant_cct_ground_truth_measured':False})
    return {'schema':'hasselblad-stage7b-cross-capture-private-study-v1',
        'status':'completed','frame_count':len(frames),
        'profile_groups':findings,
        'region_role_counts':dict(roi_counts),
        'capture_content_rehashed_by_aggregator':False,
        'render_applied':False,'production_wb_unchanged':True,
        'calibrated_policy':False,'automatic_wb_selected':False,
        'neutral_selection_authorized':False,'hasselblad_hncs_calibrated':False,
        'study_only_thresholds_not_shipping':{'holdout_near_gain_stop':guard_stop},
        'limits':['Existing stage7 reports must have been independently verified against original DNGs',
                  'Card source labels are user-provided; no independent spectral reflectance or Kelvin measurement',
                  'HAL neutral and Stage4 candidates are measured comparators, never certified true illuminants',
                  'Lens shading bases are separate competing hypotheses, not an identified sensor correction',
                  'ROI measurements from one capture are not counted as independent capture replicates',
                  'No threshold in this tool authorizes calibration, firmware AWB, HNCS or photo rendering']}

def public_from_private(data):
    return {'schema':'hasselblad-stage7b-public-safe-summary-v1',
        'status':'completed','captures_aggregated':data['frame_count'],
        'camera_profile_groups':len(data['profile_groups']),
        'exploratory_coverage_groups':sum(p['exploratory_coverage_sufficient_for_future_policy_study']
                                          for p in data['profile_groups']),
        'production_wb_unchanged':True,'automatic_wb_selected':False,
        'calibrated_policy':False,'render_applied':False,
        'neutral_selection_authorized':False,'private_scene_or_sensor_data_exported':False}


def run(manifest_path, private_path, public_path, guard_stop):
    finite(guard_stop,'invalid_holdout_stop_radius')
    require(0<guard_stop<=2.0,'out_of_range_experimental_holdout_stop_radius')
    items=read_manifest(manifest_path)
    reports=[]
    root=manifest_path.parent
    for i in items:
        path=safe_path(root,i['path'])
        obj=json.loads(path.read_text(encoding='utf-8'))
        validate_report(obj,i['binding'])
        reports.append(obj)
    data=compare_records(reports,guard_stop)
    private_path.parent.mkdir(parents=True,exist_ok=True)
    public_path.parent.mkdir(parents=True,exist_ok=True)
    require(private_path.resolve()!=public_path.resolve(), 'private_and_public_destinations_match')
    # No partially written output on a validation failure.
    private_path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    public_path.write_text(json.dumps(public_from_private(data),indent=2,sort_keys=True)+'\n')
    return data


def synthetic_sample(n,illum='daylight',role='neutral_reference',profile='1'*64,
                    neutral=(0.65,0.38),quality=1.0,card='reference_card_A'):
    gains=[1/neutral[0],1.,1/neutral[1]]
    half=['HAL_original_capture','stage4_diagnostic_radius_q12_2048']
    def basis():
        comps={}
        for name in half:
            alt=[1.6,1.,2.6] if name==half[0] else [1.5,1.,2.75]
            residual=[math.log2(alt[0]/gains[0]),math.log2(alt[2]/gains[2])]
            comps[name]={'signed_red_blue_gain_residual_stops':residual,
                   'max_abs_gain_residual_stops':max(abs(x) for x in residual),
                   'l2_green_normalized_q12_distance':
                       math.hypot((alt[0]-gains[0])*4096,(alt[2]-gains[2])*4096)}
        return {'status':'measured','valid_cells':int(1000*quality),
                'neutral_green_normalized':[neutral[0],1.,neutral[1]],
                'gains_green_normalized':gains,
                'green_site_disagreement_fraction':.003,
                'comparisons_not_truth_checks':comps}
    r={'id':'synthetic-'+str(n),'role':role,
       'reference_target_id':card if role=='neutral_reference' else None,
       'source':'measured_reference_card' if role=='neutral_reference' else 'human_visual_annotation',
       'illuminant':illum if role=='neutral_reference' else 'unknown',
       'cell_quality':{'valid_fraction':quality,'valid_cells':int(1000*quality),'total_cells':1000},
       'eligible_for_future_controlled_reference_study':role=='neutral_reference' and quality>=.95,
       'basis_hypotheses':{BASE:basis()},
       'calibration_authorized':False,'render_permitted':False}
    return {'schema':EVIDENCE_SCHEMA,'status':'completed','render_applied':False,
      'automatic_wb_selected':False,'calibrated_policy':False,'production_wb_unchanged':True,
      'capture_identity':{'dng_sha256':f'{n:064x}',
        'physical_sensor_id':'2','frame_number':str(n),
        'sensor_timestamp_ns':str(n*10_000_000),
        'camera_profile_sha256':profile,
        'width':4096,'height':3072,'exposure_time_ns':10_000_000*n,'ISO':100,
        'raw_binning_factor_used_reported':True},
      'neutral_comparators':[{'id':x,'role':'external_comparator' if x==half[0]
                           else 'uncalibrated_diagnostic_not_selected'} for x in half],
      'regions':[r]}


def selftest():
    examples=[synthetic_sample(1),synthetic_sample(2,neutral=(.655,.382)),
       synthetic_sample(3,'warm_artificial',neutral=(.71,.26)),
       synthetic_sample(4,'warm_artificial',neutral=(.705,.258)),
       synthetic_sample(5,'unknown','nonneutral_holdout',neutral=(.8,.20))]
    b=[x['capture_identity'] for x in examples]
    for ex,ident in zip(examples,b):
        declared={k:ident[k] for k in ('dng_sha256','frame_number','sensor_timestamp_ns')}
        declared['physical_sensor_id']=ident['physical_sensor_id']
        validate_report(ex,declared)
    summary=compare_records(examples,.125)
    assert summary['frame_count']==5
    assert len(summary['profile_groups'])==1
    assert summary['profile_groups'][0]['exploratory_coverage_sufficient_for_future_policy_study']
    assert summary['profile_groups'][0]['neutral_selection_authorized'] is False
    assert summary['calibrated_policy'] is False
    assert len(summary['profile_groups'][0]['reference_targets_separately_grouped']['reference_card_A']['reference_by_illumination'])==2
    assert summary['profile_groups'][0]['reference_targets_separately_grouped']['reference_card_A']['reference_by_illumination']['daylight']['basis_specific_repeatability'][BASE]['median_absolute_deviation_red_stops']>0
    assert not public_from_private(summary).get('profile_sha256')
    assert 'dng_sha256' not in json.dumps(public_from_private(summary))
    assert 'capture_identity' not in json.dumps(public_from_private(summary))
    cat=synthetic_sample(17,'unknown','unlabelled_scene')
    cat['regions'][0]['source']='unlabelled'
    validate_report(cat,{k:cat['capture_identity'][k] for k in ('dng_sha256','physical_sensor_id','frame_number','sensor_timestamp_ns')})
    assert not compare_records([cat],.125)['profile_groups'][0]['exploratory_coverage_sufficient_for_future_policy_study']
    assert len(compare_records([cat],.125)['profile_groups'][0]['coverage_missing'])==2
    x=copy.deepcopy(examples)
    x[2]['capture_identity']['camera_profile_sha256']='2'*64
    assert len(compare_records(x,.125)['profile_groups'])==2
    assert not any(g['exploratory_coverage_sufficient_for_future_policy_study']
                   for g in compare_records(x,.125)['profile_groups'])
    # Four complete captures spread across DIFFERENT reference cards are NOT
    # enough to calibrate a single target, even with matched lighting names.
    separated=copy.deepcopy(examples)
    separated[2]['regions'][0]['reference_target_id']='reference_card_B'
    separated[3]['regions'][0]['reference_target_id']='reference_card_B'
    y=compare_records(separated,.125)['profile_groups'][0]
    assert len(y['reference_targets_separately_grouped'])==2
    assert not y['exploratory_coverage_sufficient_for_future_policy_study']
    # Two ROIs in the same exposure must NOT appear as two independent frames.
    rois=copy.deepcopy(examples)
    roi2=copy.deepcopy(rois[0]['regions'][0])
    roi2['id']='synthetic_same_frame_repeat'
    rois[0]['regions'].append(roi2)
    srois=compare_records(rois,.125)['profile_groups'][0]['reference_targets_separately_grouped']['reference_card_A']['reference_by_illumination']['daylight']
    assert srois['reference_regions']==3 and srois['independent_frames']==2
    def reject(mutator,expected_reason):
        y=copy.deepcopy(examples[0]);mutator(y)
        try:validate_report(y,{k:examples[0]['capture_identity'][k] for k in
                        ('dng_sha256','physical_sensor_id','frame_number','sensor_timestamp_ns')})
        except ValueError as e:assert expected_reason in str(e),(str(e),expected_reason)
        else:raise AssertionError('accepted_tampered_report_'+expected_reason)
    reject(lambda o:o.update(automatic_wb_selected=True),'report_render_or_calibration_not_safe')
    reject(lambda o:o['regions'][0].update(role='nonneutral_holdout'),'card_source_not_reference')
    reject(lambda o:o['regions'][0].update(reference_target_id='unsafe path'),'missing_or_invalid_reference_card_identity')
    reject(lambda o:o['regions'][0].update(illuminant='mixed'),'uncertified_or_mixed_reference_label')
    reject(lambda o:o['regions'][0].update(calibration_authorized=True),'unsafe_roi_render_authorization')
    reject(lambda o:o['regions'][0].update(eligible_for_future_controlled_reference_study=False),'roi_eligibility_claim_inconsistent')
    reject(lambda o:o['regions'][0]['basis_hypotheses'][BASE].update(gains_green_normalized=[1,1,1]),'reciprocal_gain_neutral_mismatch')
    reject(lambda o:o['capture_identity'].update(camera_profile_sha256='oops'),'missing_or_invalid_profile_fingerprint')
    reject(lambda o:o['capture_identity'].update(sensor_timestamp_ns='9999'),'manifest_and_report_capture_mismatch')
    reject(lambda o:o['neutral_comparators'][0].update(role='certified_truth'),'comparator_mislabelled')
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d)
        (root/'frame.json').write_text(json.dumps(examples[0]))
        manifest={'schema':SCHEMA,'reports':[{'id':'s1','path':'frame.json',
                'binding':{k:examples[0]['capture_identity'][k] for k in
                ('dng_sha256','physical_sensor_id','frame_number','sensor_timestamp_ns')}}]}
        (root/'manifest.json').write_text(json.dumps(manifest))
        out=run(root/'manifest.json',root/'private.json',root/'public.json',.125)
        assert out['frame_count']==1
        assert json.loads((root/'public.json').read_text())['neutral_selection_authorized'] is False
        for bad in ('../frame.json','/etc/passwd','./frame.json'):
            try:safe_path(root,bad)
            except ValueError:pass
            else:raise AssertionError('accepted_unsafe_path_'+bad)
        manifest['reports'].append(manifest['reports'][0].copy())
        manifest['reports'][-1]['id']='s2'
        try:compare_records([examples[0],examples[0]],.125)
        except ValueError as e:assert 'duplicate_original_capture' in str(e)
        else:raise AssertionError('duplicate_capture_accepted')
    print('PASS Stage7B cross-frame study: two illuminants, repeated captures, holdout,\n'
          'camera-profile isolation, non-neutral guard, strict input binding,\n'
          'synthetic negative cases, private/public split and NO-WB authorization')


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--self-test',action='store_true')
    cli.add_argument('--manifest',type=pathlib.Path)
    cli.add_argument('--private-report',type=pathlib.Path)
    cli.add_argument('--public-report',type=pathlib.Path)
    cli.add_argument('--holdout-near-stop',type=float,default=.125)
    args=cli.parse_args()
    if args.self_test:
        selftest();return
    require(all(x is not None for x in (args.manifest,args.private_report,args.public_report)),
            'missing_required_study_args')
    r=run(args.manifest,args.private_report,args.public_report,args.holdout_near_stop)
    print(json.dumps(public_from_private(r),indent=2))


if __name__=='__main__':
    main()
