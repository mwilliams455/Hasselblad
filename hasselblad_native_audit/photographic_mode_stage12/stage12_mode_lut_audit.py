#!/usr/bin/env python3
"""Stage12: hash-only original-IQ / mode-to-LUT causal-scope audit.

This program DOES NOT load vendor firmware, sample pixels, run camera modes,
or establish a photographic MAIN_3DLUT hardware oracle.  It reads reports from
prior hash-bound original research, and labels predictions as CONDITIONAL.
The 6144-word post/HDR asset search has the frozen narrow scope of the earlier
inspect_pixel_contract.py scan, not an exhaustive filesystem/runtime search.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = {
    'photographic': ROOT/'photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.json',
    'native_lut': ROOT/'photographic_path/lut_profile_real_asset_execution.json',
    'dispatch': ROOT/'photographic_path/adj_dispatch_table.json',
    'array_scan': ROOT/'pixel_contract_20261019/asset_format_relationship.json',
    'gamma': ROOT/'main_colour_20261019/gamma/main_gamma_config_metadata.json',
    'main_register': ROOT/'main_colour_20261019/main_lut/main_lut_static_evidence.json',
    'ccm': ROOT/'main_colour_20261019/ccm/ccm_static_evidence.json',
}
FIRMWARE_SHA='9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'
IQ_SHA='2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
SOURCE_MAIN_SHA='0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911'
LUT_MODULE='MAIN_3DLUT'
ROUTES = {
    'normal':('frog_raw_reprocess_2-r2y-still','still3'),
    'enhanced_normal':('frog_raw_reprocess_2-r2y-still_scap3_enh_normal','still0'),
    'enhanced_hdr':('frog_raw_reprocess_2-r2y-still_scap3_enh_hdr','still0'),
}
FUNCTIONS = ('main_3dlut_calc_frame','post_scap3_calc_3dlut','post_hdr_calc_3dlut')


def require(condition, why):
    if not condition: raise ValueError(why)


def load_input():
    data={}
    for label,path in EVIDENCE.items():
        require(path.is_file(),'missing_'+label+'_source_report')
        data[label]=json.loads(path.read_text())
    return data


def cct_coefficient(cct):
    knots=[2400,3050,5550,9100]
    if cct < knots[0]: return [0,0]
    if cct>=knots[-1]:return [2,256]
    for i in range(3):
        if cct < knots[i+1]:
            return [i,(cct-knots[i])*256//(knots[i+1]-knots[i])]
    raise AssertionError('out_of_range')


def asset_scan(arrays):
    # The previous scan accepts uint32 arrays >=6144 words containing
    # '3dlut', 'lut3d', or 'tlut' in their path.  This audit cannot infer
    # absence of a smaller LUT or runtime/sideloaded table.
    require(len(arrays)>=1 and all(isinstance(a.get('words'),int) and a['words']>=6144
                                   and isinstance(a.get('sha256'),str)
                                   and len(a['sha256'])==64 for a in arrays),
            'invalid_large_lut_array_scan')
    recognized={'main':[], 'lcdc':[], 'pyramid':[], 'other':[]}
    for a in arrays:
        low=a['path'].lower()
        family='main' if 'main_3dlut' in low else ('lcdc' if 'lcdc_3dlut' in low
            else ('pyramid' if 'pyra_3dlut' in low else 'other'))
        recognized[family].append({'path':a['path'],'words':a['words'],'sha256':a['sha256']})
    return recognized


def validate(data):
    p=data['photographic']; nr=data['native_lut']; asm=data['array_scan']
    gamma=data['gamma']; main=data['main_register']; ccm=data['ccm']; dispatch=data['dispatch']
    require(p['firmware']['cim_sha256']==FIRMWARE_SHA,'firmware_identity_changed')
    require(p['config_provenance']['sha256']==IQ_SHA
            and asm['config_sha256']==IQ_SHA and ccm['config_sha256']==IQ_SHA,
            'not_same_firmware_IQ_configuration')
    require(nr['library_sha256']==p['library_hashes']['librcam.so'],
            'native_receipt_wrong_library')
    lut=p['photographic_lut']; metadata=lut['metadata']
    require(metadata['group']=='global_frame' and metadata['type']=='lerp_lut_mem_3d'
            and metadata['axis']==['cc_color_temp','color_gamut'],
            'main_global_selection_contract_changed')
    require(lut['cct_knots_k']==[2400,3050,5550,9100]
            and lut['gamut_selectors']==[0,1]
            and lut['total_word_count']==49152
            and lut['profile_count']==8 and lut['words_per_profile']==6144
            and lut['packed_words_sha256']==SOURCE_MAIN_SHA,
            'main_lut_shape_or_identity_changed')
    profiles=lut['profiles'];require(len(profiles)==8,'profile_count_changed')
    for idx,profile in enumerate(profiles):
        require(profile['profile_index']==idx and
                profile['gamut_selector']==idx//4 and
                profile['cct_k']==lut['cct_knots_k'][idx%4] and
                len(profile['little_endian_packed_words_sha256'])==64,
                'profile_bank_indexing_invalid')
    require(profiles[0]['little_endian_packed_words_sha256']==profiles[1]['little_endian_packed_words_sha256']
            and profiles[4]['little_endian_packed_words_sha256']==profiles[5]['little_endian_packed_words_sha256'],
            'warm_knot_equality_not_present')
    require(len({v['little_endian_packed_words_sha256'] for v in profiles})==6,
            'six_profile_hash_uniques_not_preserved')
    require(nr.get('case_count')==10 and nr.get('all_passed') is True
            and nr.get('photographic_lut_payload_used') is True
            and nr['real_asset_validation']['source_payload_sha256']==SOURCE_MAIN_SHA,
            'native_real_lut_reference_incomplete')
    originals={}
    for receipt in nr['cases']:
        g=receipt['gamut']; c=receipt['cct'];k=f'{c}:{g}'
        require(k not in originals and g in (0,1)
                and receipt['passed'] is True and receipt['failed_lanes']==0
                and receipt['output_words']==6144 and receipt['output_lanes']==12288
                and receipt['python_reference_all_bytes_match'] is True
                and receipt['output_sha256']==receipt['python_reference_sha256'],
                'unusable_original_native_receipt')
        require(receipt['coefficients']==[cct_coefficient(c),[0,256*g]],
                'unexpected_native_CCT_gamut_coefficients')
        if c in lut['cct_knots_k']:
            knot=lut['cct_knots_k'].index(c)
            require(receipt['output_sha256']==profiles[g*4+knot]['little_endian_packed_words_sha256'],
                    'original_native_knot_hash_mismatch')
        originals[k]=receipt['output_sha256']
    require(len(originals)==10,'native_receipt_count_changed')
    topo=p['topology_evidence'];modules=topo['selected_segments']
    require(len(modules)==3,'unexpected_route_segment_count')
    mode_maps=topo['selected_mode_maps']
    require(len(mode_maps)>=1,'missing_still_mode_mapping')
    route_records=[]
    for route,(segment,mode) in ROUTES.items():
        hits=[m for m in modules if m['segment_name']==segment]
        require(len(hits)==1 and LUT_MODULE in hits[0]['module']
                and 'MAIN_GAMMA' in hits[0]['module']
                and 'MAIN_CCM' in hits[0]['module']
                and 'MAIN_HNCS' in hits[0]['bypass'],
                'unsupported_route_module_topology_'+route)
        require(all(len([z for z in entry['selected_segment_map']
                         if z['segment_name']==segment and z['mode']==mode])==1
                    for entry in mode_maps),
                'route_has_unexpected_mode_'+route)
        route_records.append({'name':route,'segment':segment,'selected_mode':mode,
                              'main_3dlut_enabled_in_segment':True,
                              'main_hncs_module_bypassed_in_segment':True})
    actual=main['actual_config_pre_gamma']['selected_mode_values']
    mode_controls={i['mode']:i for i in actual if i['mode'].startswith('still')}
    require(set(mode_controls)=={f'still{i}' for i in range(5)}
            and all(x['module_en_lut']==[1] and x['tlut_en']==[1]
                    for x in mode_controls.values()),
            'main_mode_enable_settings_changed')
    gammas={x['mode']:x for x in gamma['still_modes']}
    require(set(gammas)=={f'still{i}' for i in range(5)},'missing_gamma_modes')
    gammahashes={i['positive_curve']['values_json_sha256'] for i in gammas.values()}
    require(len(gammahashes)==1 and all(gammas[f'still{i}']['controls']['knee_en']==0 for i in range(4))
            and gammas['still4']['controls']['knee_en']==1,'gamma_mode_conditional_not_verified')
    require(ccm['source']['secondary_banks_identical'] is True
            and len(ccm['color_hiso_gain_rate'])==4,
            'ccm_secondary_bank_invariance_not_supported')
    arrays=asset_scan(asm['arrays'])
    require(len(arrays['main'])==1 and arrays['main'][0]['sha256']==SOURCE_MAIN_SHA
            and arrays['main'][0]['words']==49152,
            'main_source_table_not_unique_in_prior_scan')
    require(len(arrays['lcdc'])==2 and len(arrays['pyramid'])==3
            and not arrays['other'], 'unexpected_large_LUT_array_family')
    require(len({x['sha256'] for v in arrays.values() for x in v})==3,
            'expected_three_distinct_LUT_families')
    require(not [x for v in arrays.values() for x in v
                 if re.search(r'post[_-]?hdr|post[_-]?scap|scap3|hdr.*3dlut',x['path'],re.I)],
            'post_mode_specific_large_LUT_candidate_present')
    fns={f['name']:f for f in p['functions']}
    require(all(n in fns for n in FUNCTIONS),'missing_original_function_record')
    require(len([x for x in fns['main_3dlut_calc_frame']['calls']
                 if x['symbol']=='DjiIsp_Reg_Set'])==2,
            'main_register_submission_calls_changed')
    for name in FUNCTIONS:
        require(len([x for x in fns[name]['calls'] if x['symbol']=='rcam_adj_calc_common'])==2,
                'common_adjustment_dispatch_record_changed_'+name)
    require(len(dispatch['verified_entries'])==1
            and dispatch['verified_entries'][0]['index']==37
            and dispatch['verified_entries'][0]['target_va']=='0x3b8c78'
            and dispatch['verified_entries'][0]['matches'] is True,
            'native_calc_dispatch_not_verified')
    return { 'route_records':route_records,'native_hashes':originals,
             'luts':arrays,'main_profiles':profiles,
             'gamma_mode_controls':{mode:{'positive_curve_sha256':g['positive_curve']['values_json_sha256'],
                                           'knee_enabled':bool(g['controls']['knee_en'])}
                                    for mode,g in gammas.items()},
             'original_function_calls':{name:{'va':fns[name]['va'],
                         'common_adjustment_call_sites':[v['va'] for v in fns[name]['calls']
                                                        if v['symbol']=='rcam_adj_calc_common'],
                         'isp_register_set_call_sites':[v['va'] for v in fns[name]['calls']
                                                       if v['symbol']=='DjiIsp_Reg_Set']}
                                        for name in FUNCTIONS}}


def report(result):
    # The same recorded profile hash is a MODEL PREDICTION under an explicitly
    # hypothetical shared source table.  It is NOT a camera measurement for 3 modes.
    cct_hashes=result['native_hashes']
    matched_conditions=[]
    for key,hashval in sorted(cct_hashes.items(),key=lambda kv: tuple(map(int,kv[0].split(':')))):
        cct,gamut=map(int,key.split(':'))
        matched_conditions.append({
            'cct_kelvin':cct,'gamut_selector':gamut,
            'original_native_profile_sha256':hashval,
            'predicted_hash_if_identical_global_source_and_inputs':hashval,
            'route_predictions':[{'route':r['name'],'mode':r['selected_mode'],
                                  'predicted_sha256':hashval,
                                  'observed_mode_specific_hardware_output':False}
                                 for r in result['route_records']]})
    return {
        'schema':'hasselblad-stage12-mode-main-lut-evidence-v1',
        'status':'PASS_STATIC_SOURCE_AND_NATIVE_RECEIPT_AUDIT',
        'firmware_model':'X2D II 100C', 'firmware_version':'1.3.16.2',
        'investigation':'Do normal, enhanced-normal, and enhanced-HDR modes independently select alternate photographic MAIN LUT contents?',
        'main_source_table':{'name':'iq_table.data[0].main_3dlut[0].lut_data',
            'calculation_group':'global_frame',
            'condition_axes':['cc_color_temp','color_gamut'],
            'stored_profiles':8, 'unique_profile_contents':6,
            'source_words_total':49152,'words_per_prepared_profile':6144,
            'source_sha256':SOURCE_MAIN_SHA},
        'configured_reprocessing_routes':result['route_records'],
        'two_enhanced_routes_same_still_mode':True,
        'mode_controls':{'main_enabled_still0_through_still4':True,
            'main_pre_gamma_enabled_in_global_configuration':False,
            'gamma':result['gamma_mode_controls'],
            'ccm_high_iso_secondary_banks_byte_equivalent':True},
        'large_LUT_array_inventory':{'scan_scope':'Archived config scan: integer arrays >=6144 words with path containing 3dlut/lut3d/tlut; excludes smaller arrays and externally loaded/runtime assets',
            'families':result['luts'],
            'post_HDR_or_SCAP_specific_large_arrays_in_inventory':False},
        'original_call_evidence':result['original_function_calls'],
        'native_original_real_asset_receipts':{'compared':10,
            'all_previous_original_native_comparisons_passed':True,
            'vendor_original_functions_executed_in_THIS_Stage12':False},
        'fixed_condition_counterfactuals':matched_conditions,
        'counterfactual_count':len(matched_conditions),
        'predicted_route_outputs':len(matched_conditions)*len(result['route_records']),
        'counterfactual_is_runtime_observation':False,
        'supported_conclusions':[
            'One MAIN global-frame source was observed in the audited 6144+-word config inventory.',
            'The three selected reprocessing routes all enable MAIN CCM, gamma and 3DLUT and bypass MAIN_HNCS.',
            'Enhanced normal and enhanced HDR both map to still0 in the pinned topology.',
            'Different input CCT or output gamut produces firmware-verified prepared profile variation.',
            'Mode changes alone are not an input to the verified mm_mx_lerp_vec_mix2 profile arithmetic.',
            'No separately named post-HDR/post-SCAP 6144+-word 3D LUT asset was seen in the archived filtered IQ-array scan.'
        ],
        'unresolved_gates':[
            'Do the three function paths supply the same IQ source pointer and destination MAIN register ID 2998 at runtime?',
            'Are enhanced/HDR post processing controls or external LUTs applied after/during MAIN?',
            'Can a live ISP or a proven full original-code wrapper trace show effective prepared table hashes for matched CCT and gamut?',
            'MAIN pixel bank/axis/interpolation and CCM/gamma domains are still unproven.',
            'No scene-recognition or atmosphere-triggered alternate MAIN table was demonstrated.'
        ],
        'photographic_colour_still_photon':True,
        'photographic_render_applied':False,
        'new_phone_APK_created':False,
        'no_proprietary_table_or_user_capture_pixels_in_report':True
    }


def selftest():
    assert cct_coefficient(1000)==[0,0]
    assert cct_coefficient(2725)==[0,128]
    assert cct_coefficient(4300)==[1,128]
    assert cct_coefficient(7001)==[2,104]
    assert cct_coefficient(9100)==[2,256]
    assert cct_coefficient(10000)==[2,256]
    sample=[{'path':'root.x.main_3dlut[0].lut_data','words':49152,'sha256':'0'*64},
            {'path':'root.x.post_hdr.3dlut','words':6144,'sha256':'1'*64}]
    x=asset_scan(sample)
    assert len(x['main'])==1 and len(x['other'])==1
    # The audit must NOT silently discard an extra candidate table.
    assert any(re.search(r'post.*hdr',a['path'],re.I) for a in x['other'])
    assert asset_scan([sample[0]])['main'][0]['words']==49152
    try:asset_scan([{'path':'a','words':1024,'sha256':'a'*64}])
    except ValueError:pass
    else:raise AssertionError('undersize_lut_not_rejected')
    try:asset_scan([])
    except ValueError:pass
    else:raise AssertionError('no_lut_not_rejected')
    # The native RECEIPT is one cct+gamut profile, not a mode-tagged trace.
    m={'native_hashes':{'2400:0':'a'*64},'route_records':[
        {'name':'normal','selected_mode':'still3'},
        {'name':'enhanced_normal','selected_mode':'still0'},
        {'name':'enhanced_hdr','selected_mode':'still0'}],
        'luts':{},'main_profiles':[],'gamma_mode_controls':{},'original_function_calls':{}}
    counter=report(m)
    assert counter['predicted_route_outputs']==3
    assert not counter['counterfactual_is_runtime_observation']
    assert all(not r['observed_mode_specific_hardware_output']
               for r in counter['fixed_condition_counterfactuals'][0]['route_predictions'])
    print('PASS Stage12 hypothetical mode selection, source bank, and counterfactual scope guards')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--output',type=Path)
    opts=p.parse_args()
    if opts.self_test: selftest();return
    require(opts.output is not None,'output_path_required')
    data=load_input()
    checked=validate(data)
    res=report(checked)
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':res['status'],
        'routes':len(res['configured_reprocessing_routes']),
        'original_native_receipts':res['native_original_real_asset_receipts']['compared'],
        'hypothetical_route_outputs':res['predicted_route_outputs'],
        'mode_specific_hardware_oracle':False,
        'output':str(opts.output)}))

if __name__=='__main__':main()
