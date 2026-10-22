#!/usr/bin/env python3
"""PRIVATE: original bound DNG -> diagnostic Bayer -> D50 XYZ -> linear sRGB/P3.
Does not output photos, tuning, render, HNCS, hue or gamma. Never commit output.
"""
from __future__ import annotations
import argparse,ctypes as C,hashlib,json,tempfile,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from test_colour_stage19 import arr,p,load,numpy_reference

def stat(x):
    return {'minimum':np.min(x,axis=0).tolist(),
            'maximum':np.max(x,axis=0).tolist(),
            'negative_component_count':int((x<0).sum()),
            'over_unity_component_count':int((x>1).sum())}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--private-dng',required=True,type=Path)
    ap.add_argument('--stage18-private-matrix',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--stage18-tests-dir',type=Path,
         default=HERE.parents[1]/'isp_dng_stage18/tests')
    args=ap.parse_args()
    sys.path.insert(0,str(args.stage18_tests_dir.resolve()))
    from test_dng_pcs_bridge import load_compiled as load_stage18,cp
    from dng_cfa_probe import reconstruct_rg_at
    import tifffile
    matrix_report=json.loads(args.stage18_private_matrix.read_text())
    original_sha=hashlib.sha256(args.private_dng.read_bytes()).hexdigest()
    if original_sha!=matrix_report['original_dng_sha256']:
        raise ValueError('Private DNG/source-matrix provenance mismatch')
    matrix=arr(matrix_report['camera_to_xyz_d50']).reshape(3,3)
    with tifffile.TiffFile(args.private_dng) as doc:
        page=doc.pages[0]
        if page.tags['CFAPattern'].value!=b'\x00\x01\x01\x02':
            raise ValueError('Unexpected CFA')
        raw=page.asarray()
        black=arr(page.tags['BlackLevel'].value)
        white=float(page.tags['WhiteLevel'].value)
    ys=np.linspace(5,raw.shape[0]-6,32,dtype=int)
    xs=np.linspace(5,raw.shape[1]-6,32,dtype=int)
    inputs=arr(np.asarray([reconstruct_rg_at(raw,black,white,int(y),int(x)) for y in ys for x in xs]))
    assert inputs.shape==(1024,3)
    results={}
    with tempfile.TemporaryDirectory() as tmp:
        temp=Path(tmp)
        a=load_stage18('gcc',temp)
        b=load('gcc',temp)
        xyz=arr(np.full_like(inputs,345.))
        if a.hb_dng_pcs_apply(cp(arr(matrix)),cp(inputs),len(inputs),cp(xyz))!=0:
            raise ValueError('Stage18 output invalid')
        if not np.allclose(xyz,inputs@matrix.T,rtol=0,atol=1e-12):
            raise AssertionError('Stage18 vs NumPy mismatch')
        for g,name in ((0,'srgb'),(1,'display_p3')):
            native_matrix=arr(np.zeros(9));
            # Receipt is not needed by this private operation except as a memory-safe output.
            from test_colour_stage19 import Receipt
            receipt=Receipt()
            if b.hb19_build_output_matrix(g,p(native_matrix),C.byref(receipt))!=0:
                raise ValueError('Stage19 gamut build failed')
            rgb=arr(np.full_like(inputs,999.))
            if b.hb19_apply_output_matrix(p(native_matrix),p(xyz),len(xyz),p(rgb))!=0:
                raise ValueError('Stage19 output invalid')
            reference,_rgbxyz,_cat=numpy_reference(g)
            difference=np.abs(rgb-xyz@reference.T)
            err=float(np.max(difference))
            assert err<2e-12,err
            results[name]={'status':'PASS',
               'c_vs_numpy_max_abs_error':err,'source_camera_linear':stat(inputs),
               'linear_output':stat(rgb),
               'output_f64_sha256_le':hashlib.sha256(rgb.astype('<f8').tobytes()).hexdigest(),
               'white_ref_receipt':receipt.schema,
               'no_clip_or_transfer_function':True}
    report={'schema':'hasselblad-stage19-private-linear-sdr-pcs-probe-v1',
      'status':'PASS','sample_count':int(len(inputs)),
      'source_dng_hash_private':original_sha,
      'scene_specific_pixel_data_private':True,
      'linear_xyz_d50':stat(xyz),
      'gamuts':results,
      'source_white_balance':'Phone Camera2 HAL/Photon neutral (uncalibrated for Hasselblad)',
      'demosaic':'Diagnostic-only simple RGGB bilinear; NOT Photon or Hasselblad demosaic',
      'd50_to_output':'Standard linear output primaries, NO HNCS',
      'processing_boundary':{'original_HNCS_applied':False,'original_main_ccm_applied':False,
            'film_curve_applied':False,'photo_saved':False,'gamma_oetf_applied':False,
            'hdr_gainmap_applied':False,'wb_calibrated':False}}
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'samples':report['sample_count'],
          'max_error_across_both_gamuts':max(v['c_vs_numpy_max_abs_error'] for v in results.values()),
          'no_photo_rendering':True,'private_report':str(args.output)}))
if __name__=='__main__':main()
