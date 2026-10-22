#!/usr/bin/env python3
"""Stage 11 — evidence-bounded study of X2D II conditional photographic LUTs.

Reads only ALREADY-PUBLIC source-derived research reports and original-native
execution receipts in this repository; does not open firmware, original camera
LUT payloads, photographs, buffers, or an Android camera. Nothing is rendered.

This verifies condition-dependent PROFILE PREPARATION and distinct configured
LUT ASSET FAMILIES. It does not infer undocumented runtime scene conditions,
path activation, RGB pixel hardware equations, or a photographic look.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

AUDIT_ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'photographic': 'photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.json',
    'assets': 'pixel_contract_20261019/asset_format_relationship.json',
    'gamma': 'main_colour_20261019/gamma/main_gamma_config_metadata.json',
    'ccm': 'main_colour_20261019/ccm/ccm_static_evidence.json',
    'main_hardware': 'main_colour_20261019/main_lut/main_lut_static_evidence.json',
}
PINNED_CONFIG = '2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
PINNED_MAIN_ASSET = '0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911'
EXPECTED_CCTS = [2400, 3050, 5550, 9100]
EXPECTED_GAMUTS = [0, 1]
PUBLIC_SCOPE = 'source reports and archived native-execution receipts only; NOT live camera selection'


def require(pred, reason):
    if not pred:
        raise ValueError(reason)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load_reports(root=AUDIT_ROOT):
    reports, identities = {}, {}
    for key, subpath in FILES.items():
        path = root / subpath
        payload = path.read_bytes()
        require(len(payload) < 250_000, f'unexpected_public_report_size:{key}')
        reports[key] = json.loads(payload)
        identities[key] = {'path': str(subpath), 'source_sha256': sha(payload)}
    return reports, identities


def select_cct(cct, gamut, axis=EXPECTED_CCTS):
    """Reconstruct only the verified profile-selector indices/Q8 fraction.

    This is NOT an AWB estimator; cct must be an externally specified label,
    not a reconstructed illuminant or measured scene state.
    """
    require(type(cct) is int, 'CCT_integer_required')
    require(type(gamut) is int and gamut in (0,1), 'invalid_gamut')
    require(axis == EXPECTED_CCTS, 'unexpected_CCT_axis')
    if cct < axis[0]:
        i, fraction = 0, 0
    elif cct >= axis[-1]:
        i, fraction = len(axis)-2, 256
    else:
        i, fraction = 0, 0
        for k in range(len(axis)-1):
            if axis[k] <= cct < axis[k+1]:
                i = k
                fraction = ((cct-axis[k])*256)//(axis[k+1]-axis[k])
                break
    return {'cct_input_kelvin':cct,'gamut_selector':gamut,
            'cct_lower_index':i,'cct_fraction_q8':fraction,
            'profile_a_index':i+4*gamut,
            'profile_b_index':i+1+4*gamut}


def build_report(reports, identities):
    p = reports['photographic']
    a = reports['assets']
    gamma = reports['gamma']
    ccm = reports['ccm']
    hardware = reports['main_hardware']
    require(p['firmware']['version'] == '1.3.16.2', 'unexpected_firmware')
    for key, value in [('photographic',p['config_provenance']['sha256']),
                       ('assets',a['config_sha256']),
                       ('gamma',gamma['config_sha256']),
                       ('ccm',ccm['config_sha256'])]:
        require(value == PINNED_CONFIG, f'config_hash_drift:{key}')
    lut = p['photographic_lut']
    require(lut['packed_words_sha256'] == PINNED_MAIN_ASSET,'main_payload_hash_drift')
    require(lut['metadata']['group'] == 'global_frame','main_not_global_frame')
    require(lut['metadata']['type'] == 'lerp_lut_mem_3d','selector_changed')
    require(lut['axis_order'] == ['cc_color_temp','color_gamut'],'axis_order_changed')
    require(lut['cct_knots_k'] == EXPECTED_CCTS,'cct_knots_changed')
    require(lut['gamut_selectors'] == EXPECTED_GAMUTS,'gamut_knots_changed')
    require(lut['profile_count'] == 8 and lut['total_word_count'] == 49152 and
            lut['words_per_profile'] == 6144,'LUT_shape_changed')
    profiles = sorted(lut['profiles'],key=lambda x: x['profile_index'])
    require(len(profiles)==8 and [r['profile_index'] for r in profiles]==list(range(8)),
            'wrong_profile_order')
    hashes = []
    for i, item in enumerate(profiles):
        require(item['cct_k'] == EXPECTED_CCTS[i%4] and
                item['gamut_selector'] == i//4,'profile_axis_binding_changed')
        require(item['word_count'] == 6144, 'profile_size_changed')
        val=item['little_endian_packed_words_sha256']
        require(isinstance(val,str) and len(val)==64,'profile_hash_missing')
        hashes.append(val)
    require(len(set(hashes)) == 6,'expected_six_distinct_recorded_profiles')
    require(hashes[0] == hashes[1] and hashes[4] == hashes[5],
            'warm_profile_identity_changed')
    require(all(hashes[i]!=hashes[i+4] for i in range(4)),
            'expected_gamut_bank_distinction_missing')

    real=p['real_asset_probe']
    require(real['all_passed'] and real['case_count']==10 and
            real['all_output_bytes_match_independent_python_reference'],
            'archived_original_execution_not_passed')
    require(real['input_words'] == 49152 and real['output_words_per_case']==6144,
            'original_native_real_asset_shape_changed')
    checked = set()
    for item in real['case_metadata']:
        require(item['passed'] and item['output_sha256'] == item['python_reference_sha256'],
                'native_python_hash_mismatch')
        knot=select_cct(item['cct'],item['gamut'])
        if item['cct'] in (2400,5550,9100):
            idx = knot['profile_b_index'] if knot['cct_fraction_q8']==256 else knot['profile_a_index']
            require(item['output_sha256']==hashes[idx], 'knot_output_hash_changed')
        checked.add((item['cct'],item['gamut']))
    require(checked == {(t,g) for t in [2400,4300,5550,7001,9100] for g in (0,1)},
            'original_native_case_coverage_changed')

    arrays = {x['path']:x for x in a['arrays']}
    expected_paths = {
        'main': ['root.iq_table.data[0].main_3dlut[0].lut_data'],
        'lcdc': ['root.iq_table.data[0].lcdc_3dlut0[0].tlut',
                 'root.iq_table.data[0].lcdc_3dlut1[0].tlut'],
        'pyramid': [f'root.iq_table.data[0].pyra_3dlut{i}[0].tlut' for i in range(3)]
    }
    require(all(path in arrays for paths in expected_paths.values() for path in paths),
            'original_asset_family_path_missing')
    signatures = {}
    for family,paths in expected_paths.items():
        records = [arrays[x] for x in paths]
        expected_words = 30720 if family=='pyramid' else 49152
        require(all(q['words']==expected_words for q in records),'asset_family_size_changed')
        require(len({q['sha256'] for q in records})==1,'intra_family_payload_changed')
        signatures[family]=records[0]['sha256']
    require(len(set(signatures.values()))==3,'three_distinct_families_not_supported')
    require(signatures['main']==PINNED_MAIN_ASSET, 'main_asset_not_same_config')
    require(all(not arrays[z].get('matches_main_profile_chunks') for family in ('lcdc','pyramid')
                for z in expected_paths[family]),'other_assets_match_main_chunk')

    gamma_modes={x['mode']:x for x in gamma['still_modes']}
    modes=[f'still{i}' for i in range(5)]
    require(set(gamma_modes)==set(modes),'gamma_modes_changed')
    curves={x['positive_curve']['values_json_sha256'] for x in gamma_modes.values()}
    require(len(curves)==1 and all(x['controls']['enable']==1 for x in gamma_modes.values()),
            'gamma_base_curves_not_identical')
    require([gamma_modes[m]['controls']['knee_en'] for m in modes]==[0,0,0,0,1],
            'gamma_knee_mode_pattern_changed')
    main_modevals={x['mode']:x for x in hardware['actual_config_pre_gamma']['selected_mode_values']}
    require(main_modevals['global']['enable_pre_gamma']==[0],'pre_gamma_global_changed')
    require(all(main_modevals[m]['module_en_lut']==[1] and
                main_modevals[m]['tlut_en']==[1] for m in modes),
            'main_lut_mode_enable_changed')

    require(ccm['source']['secondary_banks_identical'] is True,'ccm_secondary_bank_changed')
    require(ccm['cct_axis']==EXPECTED_CCTS,'ccm_knot_axis_changed')
    require(ccm['source']['profiles']==8 and ccm['source']['values_per_profile']==96,
            'ccm_table_geometry_changed')
    require([(x['color_hiso_gain'],x['color_hiso_rate']) for x in ccm['color_hiso_gain_rate']]
            == [(0,0),(18,0),(20,0),(42,256)],'ccm_high_iso_control_changed')
    require(ccm['pixel_ccm_formula_proven'] is False,'unexpected_ccm_pixel_claim')

    segments=p['topology_evidence']['selected_segments']
    require(len(segments)==3,'saved_still_path_count_changed')
    for segment in segments:
        require(all(key in segment['module'] for key in ('MAIN_CCM','MAIN_GAMMA','MAIN_3DLUT')),
                'saved_still_module_missing')
        require('MAIN_HNCS' in segment['bypass'], 'hncs_bypass_changed')
    calls={x['name']:x for x in p['functions']}
    for name in ('post_scap3_calc_3dlut','post_hdr_calc_3dlut','main_3dlut_calc_frame'):
        require(name in calls and
                any(q['symbol']=='rcam_adj_calc_common' for q in calls[name]['calls']),
                f'missing_dispatch_call:{name}')

    samples=[2000,2400,2725,3050,3350,4300,5550,7001,9100,10000]
    scenario_rows=[]
    for gamut in (0,1):
        for cct in samples:
            row=select_cct(cct,gamut)
            i,j=row['profile_a_index'],row['profile_b_index']
            row['endpoint_profiles_identical']=hashes[i]==hashes[j]
            row['warm_plateau_proven']=cct<=3050
            row['output_hash_verified_for_this_case']= next((x['output_sha256'] for x in real['case_metadata']
                if x['cct']==cct and x['gamut']==gamut),None)
            row['no_pixel_rendering_claim']=True
            scenario_rows.append(row)
    return {
        'schema':'hasselblad-stage11-conditional-photographic-colour-evidence-v1',
        'status':'PASS',
        'scope':PUBLIC_SCOPE,
        'source_reports':identities,
        'firmware':'X2D II 100C 1.3.16.2',
        'original_firmware_executed_in_this_stage':False,
        'original_camera_asset_used_in_this_stage':False,
        'main_lut':{
            'profile_count':8,'unique_stored_profile_payloads':6,
            'cct_knots_kelvin':EXPECTED_CCTS,'gamut_selectors':{'0':'sRGB','1':'P3'},
            'preparation_axes':['cc_color_temp','color_gamut'],
            'per_frame_group':'global_frame',
            'warm_region_same_profile_within_each_gamut':[2400,3050],
            'native_real_asset_cases_already_verified':10,
            'native_real_asset_comparison_method':'archived earlier original librcam.so outputs; SHA256 cross-checked',
            'all_still0_to_still4_enable_lut':True,
        },
        'distinct_lut_asset_families':{
            'family_count':3,
            'main':{'arrays':1,'words_per_array':49152,'payload_sha256':signatures['main']},
            'lcdc':{'arrays':2,'words_per_array':49152,'payload_sha256':signatures['lcdc'],
                    'other_family_dynamic_selector_proven':False},
            'pyramid':{'arrays':3,'words_per_array':30720,'payload_sha256':signatures['pyramid'],
                    'other_family_dynamic_selector_proven':False},
            'no_cross_family_profile_chunk_match_to_main':True
        },
        'other_condition_dependence':{
            'gamma':{'all_five_modes_share_identical_positive_curve':True,
                     'still0_to_still3_knee_enabled':False,'still4_knee_enabled':True,
                     'gamma_pixel_formula_proven':False},
            'ccm':{'secondary_axis':'color_hiso',
                   'secondary_profile_banks_identical_in_this_config':True,
                   'same_output_from_secondary_bank_weight_alone':True,
                   'full_pixel_ccm_formula_proven':False},
            'reprocessing':{'named_segments':[s['segment_name'] for s in segments],
                            'all_include_MAIN_3DLUT':True,
                            'all_bypass_MAIN_HNCS':True,
                            'different_main_lut_payload_selected_per_path_proven':False}
        },
        'selector_scenarios':scenario_rows,
        'explicitly_unproven':[
          'scene/subject classifications choosing different photographic MAIN_3DLUT tables',
          'ISO-only choice changing the MAIN_3DLUT payload',
          'HDR/enhancement mode changing the actual MAIN_3DLUT source data',
          'LCDC/PYRA LUT use as alternatives in the MAIN ISP block',
          'interpolated profile word hashes where no archived original output is available',
          'photographic MAIN per-pixel LUT bank layout/input coordinates/interpolation',
          'camera-specific sensor adaptation, calibrated AWB, photographic output or look',
          'actual runtime source LUT selection under a known photograph'
        ],
        'photographic_renderer_modified':False,
        'render_permitted':False
    }


def self_test():
    assert select_cct(1000,0)=={'cct_input_kelvin':1000,'gamut_selector':0,'cct_lower_index':0,
                                'cct_fraction_q8':0,'profile_a_index':0,'profile_b_index':1}
    assert select_cct(2725,0)['cct_fraction_q8']==128
    assert select_cct(4300,1)['cct_fraction_q8']==128
    assert select_cct(7001,1)['cct_fraction_q8']==104
    assert select_cct(9099,1)['cct_fraction_q8']==255
    assert select_cct(9100,1)['cct_fraction_q8']==256
    assert select_cct(10000,0)['cct_fraction_q8']==256
    assert select_cct(2400,1)['profile_a_index']==4
    for badc,badg in ((3500,2),(3500,-1),(3500,True),('3500',0),(3500,False)):
        try: select_cct(badc,badg)
        except ValueError: pass
        else: raise AssertionError('invalid_selector_input_was_accepted')
    require(PUBLIC_SCOPE.startswith('source reports'), 'scope_changed')
    print('PASS: Stage11 bounded CCT/gamut selector, endpoint and negative tests')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--audit-root',type=Path,default=AUDIT_ROOT)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.self_test:
        self_test()
        return
    data,source=load_reports(args.audit_root)
    report=build_report(data,source)
    require(report['status']=='PASS' and report['render_permitted'] is False,'unexpected_result')
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PASS','unique_main_profiles':6,'distinct_lut_families':3,
                     'gamma_mode_knee_difference':'still4_only',
                     'original_firmware_rerun':False,
                     'render_permitted':False},sort_keys=True))

if __name__=='__main__':main()
