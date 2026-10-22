#!/usr/bin/env python3
"""Stage22: inspect two original X2D MAIN gamut banks with known RGB primaries.

The original LUT profiles are proprietary transient inputs. The report emits
ONLY aggregate numerical scores of hypotheses. Neither the Stage21 planar
pixel model nor transfer function nor physical RGB identity is verified.
"""
from __future__ import annotations
import argparse
import ctypes as ct
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import numpy as np

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parents[1]
STAGE21 = AUDIT / 'isp_main_stage21'
if not STAGE21.is_dir(): STAGE21=AUDIT / 'hb_stage21'
STAGE8 = AUDIT / 'photographic_profile_stage8'
if not STAGE8.is_dir(): STAGE8=AUDIT / 'hb_stage8'
STAGE9 = AUDIT / 'photographic_pixel_stage9'
if not STAGE9.is_dir(): STAGE9=AUDIT / 'hb_stage9'
STAGE19 = AUDIT / 'isp_colour_stage19'
if not STAGE19.is_dir(): STAGE19=AUDIT / 'hb_stage19'
os.environ.setdefault('HB_STAGE8_C', str(STAGE8/'src/hb_main_lut_profile.c'))
os.environ.setdefault('HB_STAGE9_C', str(STAGE9/'src/hb_display_lut16.c'))
sys.path.insert(0, str(STAGE21 / 'tests'))
sys.path.insert(0, str(STAGE21 / 'src'))
from test_candidate21 import (compile_lib, c_apply, as_ptr, ProfileReceipt, words_to_cube)
from original_candidate_probe21 import (originals, NATIVE_REFERENCE_HASHES)
import hashlib

SAMPLES = 4096  # full sixteen-cubed symmetric grid: deliberately no interp assumption
PERMUTATIONS = list(itertools.permutations(range(3)))
INPUT_HYPOTHESES = ('identity', 'linear_standard_gamut', 'encoded_standard_gamut')
CC_TEMPS = (2400, 4300, 5550, 7001, 9100)


def primary_matrix(primaries: tuple[tuple[float, float], ...]) -> np.ndarray:
    p = np.asarray(primaries, dtype=np.float64)
    a = np.stack((p[:, 0] / p[:, 1], np.ones(3), (1 - p[:, 0] - p[:, 1]) / p[:, 1]))
    white = np.array((0.3127 / 0.3290, 1, (1 - 0.3127 - 0.3290) / 0.3290))
    return a @ np.diag(np.linalg.solve(a, white))


def srgb_to_p3_matrix() -> np.ndarray:
    s = primary_matrix(((.64,.33),(.30,.60),(.15,.06)))
    p = primary_matrix(((.68,.32),(.265,.69),(.15,.06)))
    m = np.linalg.solve(p, s)
    if np.max(np.abs(m @ np.ones(3) - 1)) > 2e-14:
        raise AssertionError('D65 white preservation failed')
    if np.min(m) < -1e-12:
        raise AssertionError('sRGB primary not inside Display P3')
    return m


def eotf(v: np.ndarray) -> np.ndarray:
    a = np.asarray(v, dtype=np.float64)
    return np.where(a <= .04045, a / 12.92, ((a + .055) / 1.055) ** 2.4)


def oetf(v: np.ndarray) -> np.ndarray:
    a = np.asarray(v, dtype=np.float64)
    # Input to this research conversion should be nonnegative; never hide out-of-gamut.
    if np.any(a < -1e-11): raise ValueError('negative linear conversion input')
    a = np.maximum(a, 0.)
    return np.where(a <= .0031308, 12.92 * a, 1.055 * (a ** (1/2.4)) - .055)


def transform(src: np.ndarray, m: np.ndarray, hypothesis: str) -> np.ndarray:
    if hypothesis == 'identity': return np.asarray(src, dtype=np.float64).copy()
    if hypothesis == 'linear_standard_gamut': return src @ m.T
    if hypothesis == 'encoded_standard_gamut': return oetf(eotf(src) @ m.T)
    raise ValueError('unsupported transfer hypothesis')


def metrics(a: np.ndarray, b: np.ndarray) -> dict:
    z = np.abs(np.asarray(a, np.float64) - np.asarray(b, np.float64)).reshape(-1)
    return {'mae': round(float(np.mean(z)), 9),
            'p95_abs': round(float(np.quantile(z, .95)), 9),
            'max_abs': round(float(np.max(z)), 9),
            'fraction_over_1_lsb': round(float(np.mean(z > 1 / 4095)), 6)}


def select(s: np.ndarray, p: np.ndarray, m: np.ndarray) -> dict:
    """Given hypothetical planar-bank node arrays, rank *output* bank identities.

    Axis identities are mathematically unidentifiable from a symmetric full-node
    comparison. For any fixed output-bank relabelling, simultaneous input-axis
    permutations only reorder this complete grid and leave scores unchanged.
    """
    s = np.asarray(s, dtype=np.float64).reshape(4096,3)
    p = np.asarray(p, dtype=np.float64).reshape(4096,3)
    if (not np.isfinite(s).all() or not np.isfinite(p).all() or
            min(float(s.min()), float(p.min())) < 0 or
            max(float(s.max()), float(p.max())) > 1):
        raise ValueError('candidate LUT node range invalid')
    rows = []
    for outperm in PERMUTATIONS:
        a = np.empty_like(s);b = np.empty_like(p)
        for bank, channel in enumerate(outperm):
            a[:,channel] = s[:,bank]
            b[:,channel] = p[:,bank]
        for model in INPUT_HYPOTHESES:
            predicted = transform(a, m, model)
            row = {'output_bank_map':''.join(map(str, outperm)),
                   'hypothesis':model,
                   **metrics(predicted, b)}
            rows.append(row)
    rows.sort(key=lambda x: (x['mae'], x['output_bank_map'], x['hypothesis']))
    best,second=rows[:2]
    return {'hypotheses_tested':len(rows),
            'best_numerical_hypothesis_not_verified':best,
            'runner_up':second,
            'runner_up_mae_over_best':round(second['mae']/max(best['mae'],1e-12),6),
            'per_hypothesis_best': {h:min((r for r in rows if r['hypothesis']==h), key=lambda z:z['mae'])
                                   for h in INPUT_HYPOTHESES},
            'by_bank_order':{''.join(map(str,p)): {h:next(r for r in rows if r['output_bank_map']==''.join(map(str,p)) and r['hypothesis']==h)['mae'] for h in INPUT_HYPOTHESES}
                             for p in PERMUTATIONS},
            'input_axis_order_identified':False,
            'output_bank_order_hardware_proven':False,
            'output_transfer_function_hardware_proven':False,
            'main_isp_pixel_oracle_used':False}


def source_at_original_poses(root: Path, compiler: str='cc') -> dict:
    arr = originals(root)
    m = srgb_to_p3_matrix()
    cases = {}
    with tempfile.TemporaryDirectory(prefix='hb22-') as td:
        lib = compile_lib(Path(td),cc=compiler)
        for temp in CC_TEMPS:
            pair=[]
            for gamut in (0,1):
                profile=np.zeros(6144,dtype=np.uint32)
                r=ProfileReceipt()
                status=lib.hb_main_lut_prepare(as_ptr(arr,ct.c_uint32),len(arr),6144,temp,gamut,
                                                as_ptr(profile,ct.c_uint32),len(profile),ct.byref(r))
                if status!=0 or r.pixel_sampler or r.render:raise AssertionError('original profile precheck failed')
                digest=hashlib.sha256(profile.astype('<u4').tobytes()).hexdigest()
                if digest!=NATIVE_REFERENCE_HASHES[(temp,gamut)]:
                    raise AssertionError('native reference hash mismatch')
                cube=words_to_cube(profile)
                # Use ONLY exact 16^3 nodes: grid order is known in the hypothesized
                # model, but no interpolation rule is assumed for these scores.
                pair.append(cube.reshape(4096,3))
                if temp==5550:
                    rng=np.random.default_rng(20261022)
                    coords=rng.integers(0,16,size=(128,3))
                    points=np.ascontiguousarray(coords/15.0, dtype=np.float64)
                    code,vals,receipt=c_apply(lib,profile,points,interp=0)
                    expected=cube[coords[:,0],coords[:,1],coords[:,2]]
                    if code!=0 or receipt.main_isp_pixel_equivalence_proven or receipt.photographic_render_authorized or np.max(np.abs(vals-expected))>2e-15:
                        raise AssertionError('C candidate does not agree at exact grid nodes')
            cases[str(temp)]=select(pair[0],pair[1],m)
    # No raw/gamut LUT words or individual pixel RGB values are retained.
    best_winners = [v['best_numerical_hypothesis_not_verified']['output_bank_map'] for v in cases.values()]
    return {
      'schema':'hasselblad-stage22-gamut-relation-hypotheses-v1',
      'status':'PASS_original_source_gamut_relation_diagnostic',
      'source_firmware':'X2D II 100C 1.3.16.2',
      'profile_sources':'hash-pinned_original_MAIN_3DLUT_sRGB_and_P3',
      'original_native_prepared_profile_hashes_verified':2*len(CC_TEMPS),
      'cct_conditions_tested':list(CC_TEMPS),
      'synthetic_full_grid_points_per_gamut':SAMPLES,
      'theoretical_colourimetry':'known_sRGB_and_DisplayP3_primaries_D65',
      'hypotheses':['same_normalized_RGB','linear_output_standard_gamut_transform','sRGB_transfer_encoded_standard_gamut_transform'],
      'candidate_decode':'Stage21_16cube_planar_unproven_MAIN',
      'input_axis_order_unidentifiable_by_full_grid_relabelling':True,
      'outputs_as_standard_gamut_RGB_unverified':True,
      'gamma_output_encoding_unverified':True,
      'results_by_kelvin':cases,
      'best_bank_map_same_across_temperature':len(set(best_winners))==1,
      'best_bank_map_candidates_are_not_physical_ground_truth':True,
      'main_pixel_sampler_validated':False,
      'main_6_coefficient_CCM_pixel_math_validated':False,
      'linear_sRGB_P3_colour_transform_is_a_tested_mathematical_hypothesis':True,
      'empirical_Phocus_colour_match_tested':False,
      'vendor_tuning_payload_exported':False,
      'original_pixel_values_exported':False,
      'photographic_render_authorized':False,
      'phone_saved_photo_colour_still_Photon':True,
    }


def selftest(cc='cc') -> dict:
    matrix=srgb_to_p3_matrix()
    # Independently cross-check the Stage19 native D50->sRGB/P3 bridge: the
    # chromatic adaptation cancels from their same-source cross-gamut product.
    import subprocess
    with tempfile.TemporaryDirectory(prefix='hb22-matrix-') as td:
        so=Path(td)/'gamut.so'
        subprocess.run([cc,'-O2','-std=c11','-fPIC','-shared','-Wall','-Wextra','-Werror',
                        str(STAGE19/'src/hb_colour_stage19.c'),'-lm','-o',str(so)],
                       capture_output=True,text=True,check=True,timeout=30)
        lib=ct.CDLL(str(so))
        lib.hb19_build_output_matrix.argtypes=[ct.c_int,ct.POINTER(ct.c_double),ct.c_void_p]
        lib.hb19_build_output_matrix.restype=ct.c_int
        # receipt is nine 32bit ints
        out=[]
        for g in (0,1):
            v=(ct.c_double*9)();receipt=(ct.c_uint32*9)()
            if lib.hb19_build_output_matrix(g,v,ct.cast(receipt,ct.c_void_p))!=0 or receipt[8]!=0:
                raise AssertionError('Stage19 bridge failed')
            out.append(np.asarray(list(v)).reshape(3,3))
        ms = out[1] @ np.linalg.inv(out[0])
        if np.max(np.abs(ms-matrix))>3e-14:raise AssertionError('standard matrices disagree')
    grid=np.stack(np.meshgrid(*([np.arange(16)/15]*3),indexing='ij'),axis=-1).reshape(4096,3)
    perm=(2,0,1)
    # First fixture, linear gamut relationship.
    rgb=np.empty_like(grid)
    rgb[:,0]=.12+.46*grid[:,0]+.08*grid[:,1]*grid[:,2]
    rgb[:,1]=.13+.51*grid[:,1]+.06*grid[:,0]*grid[:,2]
    rgb[:,2]=.12+.48*grid[:,2]+.05*grid[:,0]*grid[:,1]
    samples=np.stack([rgb[:,p] for p in perm],axis=-1)
    p3=rgb@matrix.T
    targets=np.stack([p3[:,p] for p in perm],axis=-1)
    r=select(samples,targets,matrix)
    best=r['best_numerical_hypothesis_not_verified']
    if best['output_bank_map']!='201' or best['hypothesis']!='linear_standard_gamut' or best['mae']>1e-12:
        raise AssertionError(('linear fixture not detected',best))
    # Same RGB relationship and transfer-coded conversion must remain separable.
    sames=select(samples,samples,matrix)
    if sames['best_numerical_hypothesis_not_verified']['hypothesis']!='identity':
        raise AssertionError('identical-bank negative control failed')
    encoded=rgb.copy()
    encoded_p3=transform(encoded,matrix,'encoded_standard_gamut')
    en=select(np.stack([encoded[:,p] for p in perm],axis=-1),
              np.stack([encoded_p3[:,p] for p in perm],axis=-1),matrix)
    if en['best_numerical_hypothesis_not_verified']['hypothesis']!='encoded_standard_gamut':
        raise AssertionError('transfer-coded fixture not detected')
    # Complete-grid spatial-axis permutations cannot distinguish input-axis identity:
    # they reorder matched node pairs but preserve all cross-gamut residual scores.
    for axisperm in PERMUTATIONS:
        s_reindex=np.transpose(samples.reshape(16,16,16,3),axes=(*axisperm,3)).reshape(4096,3)
        p_reindex=np.transpose(targets.reshape(16,16,16,3),axes=(*axisperm,3)).reshape(4096,3)
        assert select(s_reindex,p_reindex,matrix)['by_bank_order']==r['by_bank_order'], \
            'full-grid mapping must be invariant to input-axis permutation'
    # Monochrome channels intentionally make bank IDs ambiguous; fail closed.
    grey=grid.mean(axis=1,keepdims=True)*np.ones((1,3))
    mono=select(grey,grey,matrix)
    if len(set(round(row['identity'],8) for row in mono['by_bank_order'].values()))!=1:
        raise AssertionError('symmetric monochrome bank ambiguity missing')
    return {'schema':'hasselblad-stage22-synthetic-gamut-check-v1',
            'status':'PASS','compiler':cc,
            'standard_primaries_vs_stage19_bridge_max_error':float(np.max(np.abs(ms-matrix))),
            'synthetic_grid_nodes':4096,
            'tested_output_bank_permutations':6,
            'tested_transfer_hypotheses':list(INPUT_HYPOTHESES),
            'linear_known_bank_winner':best['output_bank_map'],
            'identity_negative_control_winner':sames['best_numerical_hypothesis_not_verified']['hypothesis'],
            'encoded_transfer_control_winner':en['best_numerical_hypothesis_not_verified']['hypothesis'],
            'monochrome_equal_bank_ambiguity_confirmed':True,
            'full_grid_axis_permutations_proven_score_invariant':6,
            'axis_mapping_unidentifiable_without_input_pixel_oracle':True,
            'no_original_vendor_data_in_synthetic_test':True,
            'renderer_unchanged':True,
            'photographic_render_authorized':False}


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--selftest',action='store_true')
    a.add_argument('--cc',default='cc')
    a.add_argument('--original-root',type=Path)
    a.add_argument('--output',type=Path,required=True)
    z=a.parse_args()
    if z.selftest:
        d=selftest(cc=z.cc)
    elif z.original_root:
        d=source_at_original_poses(z.original_root,compiler=z.cc)
    else:raise ValueError('must select --selftest or --original-root')
    z.output.parent.mkdir(parents=True,exist_ok=True)
    z.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':d['status'],'output':str(z.output),'render_authorized':False}))
if __name__=='__main__':main()
