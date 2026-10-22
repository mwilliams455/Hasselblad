#!/usr/bin/env python3
"""Stage19 synthetic-only colourimetric/Phocus selector audit.
The public Phocus401 source describes selector arithmetic, not distributable
Phocus tuning records. No Hasselblad pixel transform is evaluated here.
"""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src/hb_colour_stage19.c'
P=C.POINTER(C.c_double)
Q=C.POINTER(C.c_float)

class Receipt(C.Structure):
    _fields_=[(k,C.c_uint32) for k in ('schema','linear_rgb_only','d50_to_d65_bradford',
       'output_gamut','profile_connection_space_only','original_main_ccm_pixel_verified',
       'original_main_lut_pixel_verified','vendor_hncs_colour_applied','photographic_render_authorized')]
class Selector(C.Structure):
    _fields_=[('schema',C.c_uint32),('truncated_kelvin',C.c_int32),
              ('lut_effective_kelvin',C.c_int32),('matrix_effective_kelvin',C.c_int32),
              ('lut_lower_index',C.c_uint32),('matrix_lower_index',C.c_uint32),
              ('lut_alpha',C.c_double),('matrix_alpha',C.c_double),
              ('original_phocus_payload_present',C.c_uint32),('hncs_render_authorized',C.c_uint32)]
def arr(data):return np.ascontiguousarray(data,dtype=np.float64)
def p(a):return a.ctypes.data_as(P)
def load(cc,folder):
    so=folder/f'{Path(cc).name}.so'
    subprocess.run([cc,'-std=c11','-O2','-ffp-contract=off','-fPIC','-shared',
        '-Wall','-Wextra','-Werror',str(SRC),'-lm','-o',str(so)],
        check=True,capture_output=True,text=True,timeout=45)
    lib=C.CDLL(str(so));lib.hb19_build_output_matrix.argtypes=[C.c_int,P,C.POINTER(Receipt)]
    lib.hb19_build_output_matrix.restype=C.c_int
    lib.hb19_apply_output_matrix.argtypes=[P,P,C.c_size_t,P]
    lib.hb19_apply_output_matrix.restype=C.c_int
    lib.hb19_select_phocus_wb.argtypes=[C.c_double,C.POINTER(Selector)]
    lib.hb19_select_phocus_wb.restype=C.c_int
    lib.hb19_synthetic_phocus_blend.argtypes=[P,P,C.c_size_t,C.c_double,Q]
    lib.hb19_synthetic_phocus_blend.restype=C.c_int
    return lib
D50=np.array((.9642,1.,.8249))
D65=np.array((.3127/.329,1.,(1.-.3127-.329)/.329))
B=np.array(((.8951,.2664,-.1614),(-.7502,1.7135,.0367),(.0389,-.0685,1.0296)))

def numpy_reference(gamut):
    chroma=((.64,.33),(.30,.60),(.15,.06)) if gamut==0 else ((.68,.32),(.265,.69),(.15,.06))
    xyz=np.array([(x/y,1.,(1.-x-y)/y) for x,y in chroma]).T
    s=np.linalg.solve(xyz,D65)
    rgb_to_xyz=xyz@np.diag(s)
    adapt=np.linalg.solve(B, np.diag((B@D65)/(B@D50))@B)
    return np.linalg.inv(rgb_to_xyz)@adapt,rgb_to_xyz,adapt

def ref_segment(k,anchors):
    hi=int(np.searchsorted(anchors,k,side='right'))
    hi=min(max(hi,1),len(anchors)-1)
    return hi-1,(k-anchors[hi-1])/(anchors[hi]-anchors[hi-1])

def ref_selector(k):
    ki=int(k); kl=np.clip(ki,2000,10000);km=np.clip(ki,2000,8000)
    li,la=ref_segment(kl,np.array((3100,5550,9100)))
    mi,ma=ref_segment(km,np.array((2400,3100,5550,9100)))
    return (ki,int(kl),int(km),li,mi,float(la),float(ma))

def run_one(compiler,folder):
    lib=load(compiler,folder)
    guards=0;maxerr=0.;scalar_compared=0;pixel_count=0;shapes={}
    for gamut in (0,1):
        m=arr(np.full(9,1234.));receipt=Receipt();receipt.schema=345
        code=lib.hb19_build_output_matrix(gamut,p(m),C.byref(receipt))
        assert code==0 and receipt.schema==19 and receipt.linear_rgb_only==1
        assert receipt.d50_to_d65_bradford==1 and receipt.output_gamut==gamut
        assert receipt.original_main_ccm_pixel_verified==0 and receipt.original_main_lut_pixel_verified==0
        assert receipt.vendor_hncs_colour_applied==0 and receipt.photographic_render_authorized==0
        m=m.reshape(3,3)
        expected,rgb_to_xyz,cat=numpy_reference(gamut)
        e=float(np.max(np.abs(m-expected)));maxerr=max(maxerr,e);assert e<1e-12,e
        white=m@D50;assert np.max(np.abs(white-1.))<1e-11
        scalar_compared+=12
        rng=np.random.default_rng(193+gamut)
        for step in range(12):
            # A deliberately wide, signed, scene-linear light domain: no clipping.
            linear=arr(rng.uniform(-.30,4.5,(4096,3)))
            xyz=arr(linear@(np.linalg.inv(cat)@rgb_to_xyz).T)
            output=arr(np.full_like(linear,999.))
            code=lib.hb19_apply_output_matrix(p(arr(m)),p(xyz),len(xyz),p(output))
            assert code==0,code
            direct=xyz@expected.T
            e=float(np.max(abs(output-direct)));maxerr=max(maxerr,e)
            assert e<2e-12,(gamut,e)
            # Roundtrip includes out-of-range values and meaningful negative codes.
            e2=float(np.max(abs(output-linear)));maxerr=max(maxerr,e2)
            assert e2<2e-12,(gamut,e2)
            scalar_compared+=12+linear.size*2;pixel_count+=len(xyz)
        shapes[str(gamut)]={'matrix_sha256_le':hashlib.sha256(m.astype('<f8').tobytes()).hexdigest(),
                            'D50_white_to_linear_rgb':white.tolist(),
                            'out_of_range_retained':True}
    bad=arr(np.full(9,501.));rc=Receipt();rc.schema=552
    assert lib.hb19_build_output_matrix(5,p(bad),C.byref(rc))==2
    assert np.all(bad==501.) and rc.schema==552;guards+=1
    shared=arr(np.full(16,303.));copy=shared.copy();rc=Receipt();rc.schema=552
    assert lib.hb19_build_output_matrix(0,p(shared),C.cast(shared.ctypes.data+8*8,C.POINTER(Receipt)))==3
    assert np.array_equal(shared,copy);guards+=1
    matrix=arr(np.eye(3).flatten());src=arr([[.4,1.3,-.1]]);dst=arr([[123.,123.,123.]])
    assert lib.hb19_apply_output_matrix(p(matrix),p(src),0,p(dst))==1
    assert np.array_equal(dst,arr([[123.,123.,123.]]));guards+=1
    assert lib.hb19_apply_output_matrix(p(matrix),p(src),1,p(src))==3;guards+=1
    inf=arr([[float('nan'),1,1]])
    assert lib.hb19_apply_output_matrix(p(matrix),p(inf),1,p(dst))==1 and np.all(dst==123);guards+=1
    enormous=arr([[1.7e308,1.7e308,1.7e308]])
    badm=arr([[1,1,1],[1,1,1],[1,1,1]])
    assert lib.hb19_apply_output_matrix(p(badm),p(enormous),1,p(dst))==4
    assert np.all(dst==123);guards+=1
    sel=Selector();sel.truncated_kelvin=911
    assert lib.hb19_select_phocus_wb(float('nan'),C.byref(sel))==1 and sel.truncated_kelvin==911;guards+=1
    assert lib.hb19_select_phocus_wb(1.e30,C.byref(sel))==1 and sel.truncated_kelvin==911;guards+=1
    samples=[-100.4,1999.99,2000.,2000.8,2399.,2400.,2725.,3050.,3099.99,3100.,
         3500.1,4300.,5549.9,5550.,5550.99,7001.75,7999.,8000.,8000.6,9000.,
         9100.,9999.7,10000.,10000.99,12000.]
    rng=np.random.default_rng(29118)
    samples+=rng.uniform(1300,16000,4000).tolist()
    selector_cases=0
    for k in samples:
        s=Selector();q=lib.hb19_select_phocus_wb(float(k),C.byref(s))
        assert q==0 and s.schema==19 and s.original_phocus_payload_present==0 and s.hncs_render_authorized==0
        exp=ref_selector(k)
        got=(s.truncated_kelvin,s.lut_effective_kelvin,s.matrix_effective_kelvin,
              s.lut_lower_index,s.matrix_lower_index,s.lut_alpha,s.matrix_alpha)
        assert np.allclose(got,exp,rtol=0,atol=1e-14),(k,got,exp)
        selector_cases+=1;scalar_compared+=7
    assert lib.hb19_select_phocus_wb(-1.e7,C.byref(sel))==1;guards+=1
    # The public Phocus reconstruction casts its interpolated LUT to
    # float32 and back to float64 (the source tuning records are not public).
    for k in (2050.,3100.,3500.,5550.,8000.,9100.,9999.):
        spec=ref_selector(k)
        a=arr(np.random.default_rng(int(k)).uniform(-1,1,1024))
        b=arr(np.random.default_rng(int(k)+8).uniform(-1,1,1024))
        out=np.full((1024,),np.float32(55.),dtype=np.float32)
        code=lib.hb19_synthetic_phocus_blend(p(a),p(b),1024,spec[5],out.ctypes.data_as(Q))
        assert code==0
        ref=(a+spec[5]*(b-a)).astype(np.float32)
        assert np.array_equal(out,ref)
        scalar_compared+=1024
    small=arr([1.,2.,3.]);large=arr([4.,5.,6.]);dstf=np.full(3,44,dtype=np.float32)
    assert lib.hb19_synthetic_phocus_blend(p(small),p(large),0,.3,dstf.ctypes.data_as(Q))==1
    assert np.all(dstf==44);guards+=1
    assert lib.hb19_synthetic_phocus_blend(p(small),p(large),3,float('nan'),dstf.ctypes.data_as(Q))==1
    assert np.all(dstf==44);guards+=1
    return {'compiler':compiler,'status':'PASS','max_abs_error':maxerr,
            'output_spaces_checked':2,'linear_rgb_sample_pixels':pixel_count,
            'phocus_selector_cases':selector_cases,'float32_synthetic_selector_values':7*1024,
            'compared_scalars':scalar_compared,'negative_guards':guards,
            'matrix_results':shapes,'source_tuning_payload_present':False,
            'hasselblad_original_pixel_pipeline_verified':False,'production_renderer_unchanged':True}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    with tempfile.TemporaryDirectory() as s:
        tmp=Path(s);runs=[run_one(x,tmp) for x in ('gcc','clang')]
    out={'schema':'hasselblad-stage19-pcs-output-and-phocus-selector-v1',
         'status':'PASS' if all(z['status']=='PASS' for z in runs) else 'FAIL',
         'runtimes':runs,
         'origin':{'Stage18_D50':'portable-phone-DNG-colourimetric-conversion',
                   'output_gamut':'CIE/ICC primaries, D65 and Bradford numerical reference',
                   'Phocus_selector':'Public fishvivfish/HNCS-Lightroom/hncs_core/phocus401_wb.py; NOT X2DII firmware'}
         ,'limitations':['No original Phocus numeric color-correction records were obtained or used.',
           'P3/sRGB transforms are standard output primaries, not the X2D II MAIN 3DLUT space.',
           'No Film Curve, RAW demosaic, HDR gainmap, or saved-photo colour rendering.']}
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':out['status'],'runs':len(runs),'total_compared_scalars':sum(z['compared_scalars'] for z in runs),
         'total_selector_cases':sum(z['phocus_selector_cases'] for z in runs),'max_error':max(z['max_abs_error'] for z in runs),
         'photographic_render_applied':False}))
if __name__=='__main__':main()
