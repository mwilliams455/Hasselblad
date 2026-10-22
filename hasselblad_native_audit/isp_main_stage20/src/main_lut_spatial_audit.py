#!/usr/bin/env python3
"""Research-only spatial structure audit of MAIN vs LCDC 16-cube LUT assets.

Does not implement or infer an ISP pixel function. All numeric rankings are
conditional on an explicitly hypothetical identity-like RGB LUT objective.
Use --self-test on synthetic fixtures; --original-root needs exact unpacked
X2D II 1.3.16.2 firmware in temporary protected storage.

No source LUT words, node values, vendor binaries, photographed pixels, or
individual proprietary matrix values are ever placed in the report.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import struct
import sys
import numpy as np

CUBE_SIDE=16
PROFILE_WORDS=6144
LANES=PROFILE_WORDS*2
KNOTS=tuple(range(16))
ORDERS=list(itertools.permutations('rgb'))
CHANNEL_ORDERS=list(itertools.permutations((0,1,2)))
PROFILES_PER_ASSET=8
SOURCE_DIGESTS={
  'main_3dlut': '0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911',
  'lcdc_3dlut0': '8ecdab80c175a3594a5b251df8628bbd8978415201068429a8894026d4b883df',
  'lcdc_3dlut1': '8ecdab80c175a3594a5b251df8628bbd8978415201068429a8894026d4b883df',
}
LIB_IQ_SHA='2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
PROFILE_REFS={
 'main_3dlut': ('ed9fd193ea763ecb3defec69a73152ff250cb89e04292ee347dee6950cec66e1',
                 'ed9fd193ea763ecb3defec69a73152ff250cb89e04292ee347dee6950cec66e1',
                 'de9ee466e2452d222fa0db4c330c709bebb6364a50584c902ff0b6169f4964bb',
                 '12099cc658824d593bb2fbd6273089c719658b4177a00f2341f6b1169430397b',
                 '295b3bea3fc1cf8d862cfe11815cec8b01d0e50bb0e366516976c185d3fc6220',
                 '295b3bea3fc1cf8d862cfe11815cec8b01d0e50bb0e366516976c185d3fc6220',
                 '3392785a7389c5827cfeb835eed8b271394331ec79c75967be05c0319a51022f',
                 'f21ab71851421ab5b88c993ef2878ffe274fae44dd55a2b6249da169287ff55b'),
}


def require(condition:bool, reason:str)->None:
    if not condition:raise ValueError(reason)


def words_to_lanes(words:np.ndarray)->np.ndarray:
    if not isinstance(words,np.ndarray) or words.dtype!=np.uint32 or words.shape!=(PROFILE_WORDS,):
        raise ValueError('bad_lut_profile_dtype_or_extent')
    lanes=np.empty(LANES, dtype=np.uint16)
    lanes[::2] = (words & np.uint32(0xffff)).astype(np.uint16)
    lanes[1::2] = (words >> np.uint32(16)).astype(np.uint16)
    return lanes


def model_name(family:str, axes:tuple[str,...], banks:tuple[int,...])->str:
    return f'{family}:memory_axes={"".join(axes)}:output_banks={"".join(str(x) for x in banks)}'


def unpack_candidate(lanes:np.ndarray, family:str, axes:tuple[str,...], banks:tuple[int,...])->np.ndarray:
    require(isinstance(lanes,np.ndarray) and lanes.shape==(LANES,) and lanes.dtype==np.uint16, 'bad_lanes')
    require(tuple(sorted(axes))==('b','g','r') and len(axes)==3, 'bad_axis_permutation')
    require(tuple(sorted(banks))==(0,1,2), 'bad_bank_permutation')
    # Original DISPLAY model: three planar 2048-word banks, two B-adjacent
    # nodes packed per word; this is ONE hypothesis for MAIN only.
    if family=='planar':
        storage=lanes.reshape((3,16,16,16))
        reordered=np.transpose(storage,axes=(0,)+(tuple(axes.index(x)+1 for x in 'rgb')))
        nodes=np.moveaxis(reordered[list(banks)],0,-1)
    elif family=='interleaved':
        storage=lanes.reshape((16,16,16,3))
        reordered=np.transpose(storage,axes=tuple(axes.index(x) for x in 'rgb')+(3,))
        nodes=reordered[...,list(banks)]
    else:raise ValueError('unknown_lut_model')
    assert nodes.shape==(16,16,16,3)
    return nodes.astype(np.float64)/4095.0


def metrics(nodes:np.ndarray)->dict:
    require(nodes.shape==(16,16,16,3) and np.isfinite(nodes).all(), 'bad_nodes')
    coords=np.stack(np.meshgrid(*([np.arange(16,dtype=float)/15]*3),indexing='ij'),axis=-1)
    delta=nodes-coords
    rmse=float(np.sqrt(np.mean(delta*delta)))
    step=[]; curv=[];jac=[];diagmon=[]
    for axis in range(3):
        diff=np.diff(nodes,axis=axis)
        step.append(float(np.mean(np.abs(diff))))
        curv.append(float(np.mean(np.abs(np.diff(diff,axis=axis)))))
        jac.append([float(x) for x in np.mean(diff,axis=(0,1,2))])
        diagmon.append(float(np.mean(diff[...,axis]>0)))
    jac=np.asarray(jac,dtype=float)
    diag=float(np.mean(np.diag(jac)))
    cross=float(np.mean(np.abs(jac-np.diag(np.diag(jac)))))
    # Explicit heuristic. A lower score indicates greater *compatibility*
    # with a smooth, approximately identity RGB lookup; it is NOT a
    # posterior probability, a measured camera output, or pixel parity.
    score=rmse + .65*np.mean(step) + 1.25*np.mean(curv) + .3*max(0.,.06-diag)+.2*cross
    return {
     'score':float(score),
     'identity_rmse':rmse,
     'mean_abs_neighbor_jump':float(np.mean(step)),
     'mean_abs_curvature':float(np.mean(curv)),
     'mean_diagonal_gain_per_knot':diag,
     'mean_off_diagonal_gain_magnitude':cross,
     'positive_diagonal_derivative_fraction':float(np.mean(diagmon)),
    }


def evaluate_one(words:np.ndarray, max_models:int=5)->dict:
    lanes=words_to_lanes(words)
    reserved=int(np.count_nonzero(lanes&np.uint16(0xf000)))
    all_models=[]
    for family in ('planar','interleaved'):
      for axes in ORDERS:
        for banks in CHANNEL_ORDERS:
          result=metrics(unpack_candidate(lanes,family,axes,banks))
          all_models.append((result['score'],model_name(family,axes,banks),result))
    all_models.sort(key=lambda x:(x[0],x[1]))
    display=next(result for _,name,result in all_models if name==model_name('planar',('r','g','b'),(0,1,2)))
    best=all_models[0]
    tied=[name for score,name,_ in all_models if abs(score-best[0])<=1e-10]
    by_family={name:next((score for score,n,_ in all_models if n.startswith(name+':')),None) for name in ('planar','interleaved')}
    return {
      'models_examined':len(all_models),
      'nonzero_reserved_halfword_high_nibbles':reserved,
      'best_by_synthetic_heuristic':best[1],
      'equivalent_top_models_under_axis_colour_relabelling':tied,
      'top_equivalence_class_size':len(tied),
      'unique_RGB_axis_and_bank_order_inferable_from_structure':False,
      'top_synthetic_heuristic_models':[{'model':n,'rank_score':round(score,9)} for score,n,_ in all_models[:max_models]],
      'baseline_display_lut_hypothesis_metrics':{k:round(v,9) for k,v in display.items()},
      'lowest_rank_score_by_family':{x:round(v,9) for x,v in by_family.items()},
      'top2_score_gap':round(all_models[1][0]-all_models[0][0],9),
      'ranking_is_not_MAIN_hardware_pixel_oracle':True,
    }


def encode_identity(family:str,axes:tuple[str,...],banks:tuple[int,...],degree:float=.9)->np.ndarray:
    coords=np.stack(np.meshgrid(*([np.arange(16,dtype=float)/15]*3),indexing='ij'),axis=-1)
    # Monotonic RGB transform with weak channel cross-talk.
    mat=np.array([[degree,.03,.02],[.02,degree,.025],[.035,.02,degree]],dtype=float)
    values=np.clip(coords@mat.T,0,1)
    out=np.empty_like(values)
    # inverse decoder permutation: bank-indexed output
    for channel, bank in enumerate(banks): out[...,bank]=values[...,channel]
    raw_axes=tuple('rgb'.index(x) for x in axes)
    if family=='planar':
       bank_first=np.moveaxis(out,-1,0)
       physical=np.transpose(bank_first, (0,)+tuple(1+i for i in raw_axes))
       lanes=np.rint(physical.reshape(-1)*4095).astype(np.uint16)
    elif family=='interleaved':
       physical=np.transpose(out, raw_axes+(3,))
       lanes=np.rint(physical.reshape(-1)*4095).astype(np.uint16)
    else:raise ValueError('unknown_model')
    words=lanes[::2].astype(np.uint32)|(lanes[1::2].astype(np.uint32)<<16)
    require(words.shape==(PROFILE_WORDS,), 'bad_words_generated')
    return words


def selftest()->dict:
    types=[('planar',('r','g','b'),(0,1,2)),
           ('planar',('b','g','r'),(1,2,0)),
           ('interleaved',('r','g','b'),(0,1,2)),
           ('interleaved',('g','r','b'),(2,1,0))]
    results=[]
    for family,axes,banks in types:
      words=encode_identity(family,axes,banks)
      decoded=unpack_candidate(words_to_lanes(words),family,axes,banks)
      coords=np.stack(np.meshgrid(*([np.arange(16,dtype=float)/15]*3),indexing='ij'),axis=-1)
      expected=coords@np.array([[.9,.03,.02],[.02,.9,.025],[.035,.02,.9]],dtype=float).T
      assert np.max(np.abs(decoded-expected))<.00013
      evaluated=evaluate_one(words)
      assert evaluated['models_examined']==72
      assert evaluated['nonzero_reserved_halfword_high_nibbles']==0
      assert model_name(family,axes,banks) in evaluated['equivalent_top_models_under_axis_colour_relabelling'], (family,axes,banks,evaluated['top_synthetic_heuristic_models'])
      assert evaluated['top_equivalence_class_size']>=2  # joint RGB relabelling is not identifiable
      assert evaluated['best_by_synthetic_heuristic'].split(':')[0]==family
      results.append(evaluated['best_by_synthetic_heuristic'])
    for malformed in [np.zeros(6000,dtype=np.uint32),np.zeros(6144,dtype=np.int64),np.zeros((6144,1),dtype=np.uint32)]:
      try:words_to_lanes(malformed)
      except ValueError:pass
      else:raise AssertionError('invalid_profile_shape_accepted')
    constant=np.zeros(6144,dtype=np.uint32)
    c=evaluate_one(constant)
    assert c['top2_score_gap']==0, c
    return {'status':'PASS','synthetic_models_tested':len(types),'correct_families_recovered':len(results),
            'flat_LUT_ambiguous_ranking':c['top2_score_gap']==0,'invalid_profile_shapes_rejected':3,
            'models_per_profile':72,'original_vendor_assets_used':False}


def original_report(root:Path)->dict:
    iq=root/'system/etc/iq/hb722_config.json'
    with iq.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
    require(sha==LIB_IQ_SHA,'wrong_original_X2D_II_1_3_16_2_config')
    sys.dont_write_bytecode=True
    parser=Path(__file__).resolve().parents[2]/'photographic_path/inspect_iq_config.py'
    spec=importlib.util.spec_from_file_location('stage20_pinned_iq_parser',parser)
    require(spec is not None and spec.loader is not None,'no_trusted_iq_parser')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    src=m.read_config(iq)['iq_table']['data'][0]
    reports={}
    for name in SOURCE_DIGESTS:
      val=src[name][0]['lut_data' if name=='main_3dlut' else 'tlut']
      require(isinstance(val,list) and len(val)==8*PROFILE_WORDS and all(type(x)==int and 0<=x<=0xffffffff for x in val),'bad_table_size_or_word')
      raw=struct.pack('<%dI'%len(val),*val)
      require(hashlib.sha256(raw).hexdigest()==SOURCE_DIGESTS[name], 'wrong_source_asset_hash_'+name)
      profiles=[]
      for i in range(8):
        w=np.asarray(val[i*PROFILE_WORDS:(i+1)*PROFILE_WORDS],dtype=np.uint32)
        digest=hashlib.sha256(w.astype('<u4',copy=False).tobytes()).hexdigest()
        if name in PROFILE_REFS:require(digest==PROFILE_REFS[name][i],'profile_hash_discrepancy')
        report=evaluate_one(w)
        report['profile_index']=i
        # No vendor profile bytes, RGB vertices or per-node values in reports.
        report['source_profile_sha256']=digest
        profiles.append(report)
      groups={}
      for entry in profiles:groups.setdefault(entry['best_by_synthetic_heuristic'],[]).append(entry['profile_index'])
      reports[name]={'profile_count':len(profiles),
                     'source_sha256':SOURCE_DIGESTS[name],
                     'chosen_layout_frequency_under_heuristic':groups,
                     'profiles':profiles}
    require(reports['lcdc_3dlut0']['source_sha256']==reports['lcdc_3dlut1']['source_sha256'], 'lcdc_identical_assets_expected')
    family_summary={}
    canonical=model_name('planar',('r','g','b'),(0,1,2))
    for source, record in reports.items():
      # Report both physical profile count and independent profile contents.
      unique={}
      for p in record['profiles']: unique.setdefault(p['source_profile_sha256'],p)
      distinct=list(unique.values())
      all_entries=record['profiles']
      planar_is_lower=sum(p['lowest_rank_score_by_family']['planar'] < p['lowest_rank_score_by_family']['interleaved'] for p in all_entries)
      canonical_at_best=sum(canonical in p['equivalent_top_models_under_axis_colour_relabelling'] for p in all_entries)
      means={family:round(sum(p['lowest_rank_score_by_family'][family] for p in distinct)/len(distinct),9)
             for family in ('planar','interleaved')}
      family_summary[source]={
          'stored_profiles':len(all_entries),
          'unique_profile_contents':len(distinct),
          'planar_family_lower_heuristic_count':planar_is_lower,
          'Stage9_original_DISPLAY_canonical_decode_in_best_equivalence_class_count':canonical_at_best,
          'unique_content_mean_family_heuristic_score':means,
          'mean_interleaved_to_planar_score_ratio':round(means['interleaved']/means['planar'],6),
          'canonical_RGB_axis_or_bank_order_proven':False,
          'spatial_interpolation_algorithm_proven':False,
          'rank_not_a_photographic_similarity_or_deltaE':True,
      }
    return {'schema':'hasselblad-stage20-LUT-spatial-consistency-v1',
            'status':'PASS_original_X2D_IQ_structural_audit',
            'firmware':'X2D II 100C 1.3.16.2',
            'source_original_iq_sha256':LIB_IQ_SHA,
            'candidate_model_count':72,'profile_size_words':PROFILE_WORDS,
            'source_bytes_exported':False,'vendor_code_executed':False,
            'camera_data_or_photo_exported':False,
            'MAIN_pixel_layout_proven':False,'MAIN_pixel_sampler_proven':False,
            'MAIN_ccm_and_gamma_order_proven':False,'original_ISP_pixel_oracle_available':False,
            'render_applied':False,'phone_colour_still_Photon':True,
            'hypothesis_selection_is_smooth_identity_prior_not_hardware_parity':True,
            'candidate_families_are_not_exhaustive':True,
            'not_evaluated_layouts':['Morton_or_other_hardware_swizzles','nonuniform_3D_grid','per-channel_nonstandard_scaling'],
            'unique_content_aggregate_summary':family_summary,
            'results':reports}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--original-root',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    summary=selftest()
    if args.self_test:
        print(json.dumps(summary,sort_keys=True));return
    if args.original_root is None or args.output is None:p.error('--original-root and --output are needed')
    report=original_report(args.original_root.resolve())
    report['synthetic_selftest']=summary
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'MAIN_profile_best_layouts':report['results']['main_3dlut']['chosen_layout_frequency_under_heuristic'],
                      'LCDC_profile_best_layouts':report['results']['lcdc_3dlut0']['chosen_layout_frequency_under_heuristic'],
                      'report':str(args.output)}))

if __name__=='__main__':main()
