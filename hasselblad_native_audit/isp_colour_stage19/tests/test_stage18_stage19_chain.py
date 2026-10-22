#!/usr/bin/env python3
"""Synthetic only: Stage18 camera->D50 + Stage19 D50->linear output primaries.
Does not approximate an original Hasselblad photographic colour transform.
"""
from __future__ import annotations
import argparse,ctypes as C,json,sys,tempfile
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from test_colour_stage19 import load as load19, arr, p, Receipt, numpy_reference

def check(stage18_src:Path,output:Path|None):
    sys.path.insert(0,str(stage18_src.parent.parent/'tests'))
    from test_dng_pcs_bridge import load_compiled as load18, cp, create_data, ref_build, build
    runs=[]
    with tempfile.TemporaryDirectory() as name:
        work=Path(name)
        for compiler in ('gcc','clang'):
            lib18=load18(compiler,work)
            lib19=load19(compiler,work)
            matrices=[]
            for g in (0,1):
                m=arr(np.zeros(9));receipt=Receipt()
                assert lib19.hb19_build_output_matrix(g,p(m),C.byref(receipt))==0
                assert receipt.photographic_render_authorized==0
                matrices.append((m,numpy_reference(g)[0]))
            rng=np.random.default_rng(190019)
            count=0;largest=0;scalars=0
            for ix in range(64):
                fm,cc,ab,n=create_data(ix)
                status,transform,r=build(lib18,fm,cc,ab,n)
                assert status==0 and r.photographic_render_authorized==0
                reftransform=ref_build(fm,cc,ab,n)
                rgb=arr(rng.uniform(-.2,3.2,(1024,3)))
                xyz=arr(np.full_like(rgb,-127.))
                assert lib18.hb_dng_pcs_apply(cp(arr(transform)),cp(rgb),len(rgb),cp(xyz))==0
                assert np.allclose(xyz,rgb@reftransform.T,rtol=0,atol=3e-12)
                for mat,rm in matrices:
                    linear=arr(np.full_like(rgb,456.))
                    assert lib19.hb19_apply_output_matrix(p(mat),p(xyz),len(xyz),p(linear))==0
                    ref=rgb@reftransform.T@rm.T
                    err=float(np.max(abs(linear-ref)))
                    largest=max(largest,err)
                    assert err<4e-12,(compiler,ix,err)
                    assert np.isfinite(linear).all()
                    count+=1;scalars+=linear.size
            runs.append({'compiler':compiler,'status':'PASS','end_to_end_camera_profile_cases':64,
                         'target_gamut_checks':count,'compared_output_scalars':scalars,
                         'max_abs_error':largest,'photographic_look_or_HNCS_applied':False})
    o={'schema':'hasselblad-stage19-synthetic-stage18-to-stage19-chain-v1',
       'status':'PASS','results':runs,
       'source_data':'synthetic_only','original_camera_lut_absent':True,
       'original_main_ccm_pixel_equation_not_established':True,
       'dng_dual_differing_matrices_still_unsupported':True,
       'photo_saved':False}
    if output:output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(o,indent=2)+'\n')
    print(json.dumps({'status':'PASS','compiler_runs':2,
      'total_compared_scalars':sum(r['compared_output_scalars'] for r in runs),
      'max_abs_error':max(r['max_abs_error'] for r in runs),
      'not_hasselblad_colour_science':True}))

def main():
    ap=argparse.ArgumentParser()
    default=HERE.parents[1]/'isp_dng_stage18/src/hb_dng_pcs_bridge.c'
    ap.add_argument('--stage18-src',type=Path,default=default)
    ap.add_argument('--output',type=Path)
    a=ap.parse_args()
    if not a.stage18_src.exists():raise SystemExit('stage18_reference_source_required')
    check(a.stage18_src,a.output)
if __name__=='__main__':main()
