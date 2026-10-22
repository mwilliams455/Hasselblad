#!/usr/bin/env python3
"""Stage18 reproducible host tests for DNG forward-matrix camera->D50 branch.
All synthetic values are authored, with optional private real-DNG numerical check.
Never publish real-DNG output, camera matrices, frames or hashes to GitHub.
"""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
D50=np.array([.9642,1.0,.8249],dtype=float)
ROOT=Path(__file__).resolve().parents[1]

class Receipt(C.Structure):
    _fields_=[(n,C.c_uint) for n in ('schema','dual_forward_equal','dual_calibration_equal','camera_white_balanced','numerical_pcs_white_verified','original_hasselblad_ccm_verified','original_hasselblad_lut_verified','photographic_render_authorized')]

P=C.POINTER(C.c_double)

def load_compiled(compiler:str, dir:Path):
    path=dir/('hb_dng_pcs_'+compiler.replace('/','_')+'.so')
    subprocess.run([compiler,'-std=c11','-O2','-ffp-contract=off','-fPIC','-shared','-Wall','-Wextra','-Werror',str(ROOT/'src/hb_dng_pcs_bridge.c'),'-lm','-o',str(path)],check=True,capture_output=True,text=True)
    obj=C.CDLL(str(path))
    obj.hb_dng_pcs_build.argtypes=[P,P,P,P,P,P,P,C.POINTER(Receipt)]
    obj.hb_dng_pcs_build.restype=C.c_int
    obj.hb_dng_pcs_apply.argtypes=[P,P,C.c_size_t,P]
    obj.hb_dng_pcs_apply.restype=C.c_int
    return obj

def pa(x):return np.ascontiguousarray(x,dtype=np.float64)
def cp(x):return x.ctypes.data_as(P)

def ref_build(fm,cc,ab,neutral):
    f=np.asarray(fm,dtype=float).reshape(3,3).copy()
    f*=D50[:,None]/f.sum(axis=1)[:,None]
    if cc is None:cc=np.eye(3)
    m=np.linalg.inv(np.diag(ab)@cc)
    neutral=np.asarray(neutral,dtype=float)
    white=neutral/np.max(neutral)
    refwhite=m@white
    return f@np.diag(1/refwhite)@m

def create_data(seed):
    rng=np.random.default_rng(seed)
    f=np.array([[.6,.15,.25],[.2,.75,.05],[-.03,-.2,1.23]])
    f+=rng.uniform(-.03,.03,(3,3));f*=D50[:,None]/f.sum(axis=1)[:,None]
    cc=np.eye(3)+rng.uniform(-.05,.05,(3,3))
    ab=np.asarray(rng.uniform(.87,1.13,3))
    n=np.asarray(rng.uniform(.3,1.0,3));n/=max(n)
    return tuple(pa(x) for x in (f,cc,ab,n))

def build(lib,f,cc,ab,n):
    out=pa(np.full(9,12345.))
    r=Receipt();r.schema=999
    code=lib.hb_dng_pcs_build(cp(f),cp(f),cp(cc),cp(cc),cp(ab),cp(n),cp(out),C.byref(r))
    return code,out.reshape(3,3),r

def test_all(compiler, tmp):
    lib=load_compiled(compiler,tmp)
    nprofiles=128; nprobe=0; cases=0;max_error=0.0; guards=0
    for seed in range(nprofiles):
        f,cc,ab,n=create_data(seed)
        code,out,r=build(lib,f,cc,ab,n)
        assert code==0 and r.schema==18 and r.photographic_render_authorized==0
        assert r.original_hasselblad_ccm_verified==0 and r.original_hasselblad_lut_verified==0
        ref=ref_build(f,cc,ab,n)
        err=np.max(np.abs(out-ref));max_error=max(max_error,float(err))
        assert err<2e-12,(seed,err)
        assert np.allclose(out@(n/n.max()),D50,rtol=0,atol=2e-12)
        assert r.numerical_pcs_white_verified==1
        rng=np.random.default_rng(seed+999)
        probe=pa(rng.uniform(-.25,2.5,(512,3)))
        dst=pa(np.full((512,3),8888.))
        status=lib.hb_dng_pcs_apply(cp(out),cp(probe),512,cp(dst))
        assert status==0
        err=float(np.max(np.abs(dst-probe@ref.T)))
        assert err<2e-12,(seed,err)
        max_error=max(max_error,err)
        cases+=1;nprobe+=512*3
    # Fixed diagonal CameraCalibration and analog cancel in F*diag(1/neutral)
    f,cc,ab,n=create_data(0);cc=np.diag([1.03125,1.0,1.015625]);ab=pa([1.04,1,.96]);
    code,out,r=build(lib,f,pa(cc),ab,n)
    target=(f*(D50/f.sum(axis=1))[:,None])@np.diag(1/n)
    assert code==0 and np.max(abs(target-out))<2e-12;guards+=1
    # Full shape-mismatch, nonfinite, out-of-range and alias validation.
    src=pa(f); end=pa(np.full(9,42.));receipt=Receipt();receipt.schema=123
    diff=pa(f.copy());diff[0]+=0.002
    def reject(f1,f2,cc1,cc2,abv,nv,expected):
        out=pa(np.full(9,42.));rr=Receipt();rr.schema=123
        st=lib.hb_dng_pcs_build(cp(f1),cp(f2) if f2 is not None else None,
                 cp(cc1) if cc1 is not None else None,cp(cc2) if cc2 is not None else None,
                 cp(abv),cp(nv),cp(out),C.byref(rr))
        assert st==expected,(st,expected)
        assert np.all(out==42.) and rr.schema==123
    reject(f,diff,cc,cc,ab,n,2);guards+=1
    cc_diff=pa(cc.copy());cc_diff[0,1]+=0.03
    reject(f,f,cc,cc_diff,ab,n,2);guards+=1
    reject(f,f,None,cc,ab,n,2);guards+=1
    reject(f,f,pa(np.zeros((3,3))),pa(np.zeros((3,3))),ab,n,3);guards+=1
    bad_n=pa(n.copy());bad_n[0]=0;reject(f,f,cc,cc,ab,bad_n,1);guards+=1
    bad_n=pa(n.copy());bad_n[0]=np.nan;reject(f,f,cc,cc,ab,bad_n,1);guards+=1
    bad_f=pa(f.copy());bad_f[1,:]=0;reject(bad_f,bad_f,cc,cc,ab,n,3);guards+=1
    bad_f=pa(f.copy());bad_f[1,2]=np.inf;reject(bad_f,bad_f,cc,cc,ab,n,1);guards+=1
    bad_ab=pa(ab.copy());bad_ab[2]=-1;reject(f,f,cc,cc,bad_ab,n,1);guards+=1
    bad_ab=pa(ab.copy());bad_ab[2]=0;reject(f,f,cc,cc,bad_ab,n,1);guards+=1
    # No overlap: input==output rejected without mutation.
    out=pa(f.copy());prev=out.copy();rr=Receipt();rr.schema=123
    st=lib.hb_dng_pcs_build(cp(out),cp(out),cp(cc),cp(cc),cp(ab),cp(n),cp(out),C.byref(rr))
    assert st==4 and np.array_equal(out,prev) and rr.schema==123;guards+=1
    # Apply must preserve output on finite validation errors and on aliasing.
    bad=pa([np.nan,1.,2.]);out=pa([77.,77.,77.]);st=lib.hb_dng_pcs_apply(cp(f),cp(bad),1,cp(out));assert st==1 and np.all(out==77);guards+=1
    probe=pa([0.2,0.4,1.7]);snapshot=probe.copy()
    st=lib.hb_dng_pcs_apply(cp(f),cp(probe),1,cp(probe));assert st==4 and np.array_equal(probe,snapshot);guards+=1
    probe=pa([0.2,0.4,1.7]);out=pa([77.,77.,77.]);st=lib.hb_dng_pcs_apply(cp(f),cp(probe),0,cp(out));assert st==1 and np.all(out==77.);guards+=1
    return {'compiler':compiler,'status':'PASS','synthetic_profile_cases':cases,
            'synthetic_pixel_scalars_compared':nprobe,'max_abs_error':max_error,
            'negative_guard_cases':guards,'real_dng_test_omitted':True,
            'vendor_hncs_pixel_math_verified':False,'original_hasselblad_ccm_verified':False,
            'photo_render_authorized':False}

def real_dng_check(compiler,tmp,path):
    import tifffile
    lib=load_compiled(compiler,tmp)
    path=Path(path)
    with tifffile.TiffFile(path) as f:
        page=f.pages[0]
        tags=page.tags
        def rat(name):
            z=tags[name].value
            assert len(z)%2==0
            d=pa(z[1::2]);assert np.all(d!=0)
            return pa(pa(z[::2])/d)
        fm1=rat('ForwardMatrix1').reshape(3,3)
        fm2=rat('ForwardMatrix2').reshape(3,3)
        cc1=rat('CameraCalibration1').reshape(3,3) if 'CameraCalibration1' in tags else pa(np.eye(3))
        cc2=rat('CameraCalibration2').reshape(3,3) if 'CameraCalibration2' in tags else cc1
        neutral=rat('AsShotNeutral')
        ab=rat('AnalogBalance') if 'AnalogBalance' in tags else pa([1.,1.,1.])
        black=pa(tags['BlackLevel'].value)
        white=float(tags['WhiteLevel'].value)
        width=int(page.imagewidth);height=int(page.imagelength)
    assert neutral.shape==(3,) and black.shape==(4,) and white>max(black)
    code,mat,receipt=build(lib,pa(fm1),pa(cc1),pa(ab),pa(neutral))
    assert code==0 and np.array_equal(fm1,fm2) and np.array_equal(cc1,cc2)
    expected=ref_build(fm1,cc1,ab,neutral)
    assert np.max(abs(mat-expected))<2e-12
    return {'schema':'stage18-real-dng-d50-adapter-check-v1','status':'PASS','original_dng_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'capture_dimensions':[width,height],'black_values':black.tolist(),'white_level':white,
        'as_shot_neutral':neutral.tolist(),'calibration_illuminants':None,
        'camera_calibration_matches_between_illuminants':True,'forward_matrix_matches_between_illuminants':True,
        'd50_white_point':D50.tolist(),'white_mapped_xyz_d50':(mat@(neutral/neutral.max())).tolist(),
        'camera_to_xyz_d50':mat.tolist(),'max_host_vs_numpy_error':float(np.max(abs(mat-expected))),
        'camera_profile_is_from_original_phone_dng_not_hasselblad':True,'photon_colour_still_unchanged':True,
        'hasselblad_color_pipeline_applied':False,'uses_as_shot_hal_neutral_not_calibrated_hasselblad_wb':True,
        'full_sdk_dual_illuminant_interpolation_implemented':False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path)
    ap.add_argument('--private-dng',type=Path)
    args=ap.parse_args()
    with tempfile.TemporaryDirectory() as tmpstr:
        tmp=Path(tmpstr)
        records=[test_all('gcc',tmp),test_all('clang',tmp)]
        if args.private_dng:
            d=real_dng_check('gcc',tmp,args.private_dng)
            if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(d,indent=2)+'\n')
            print(json.dumps({'status':d['status'],'scope':'private_real_dng_metadata','profile_matrix_verified':True,'private_report':str(args.output)}))
        else:
            assert all(x['status']=='PASS' for x in records)
            result={'schema':'stage18-forward-matrix-pcs-reference-v1','status':'PASS',
                    'test_runs':records,'notes':['Uses Adobe SDK ForwardMatrix normalization and CameraToPCS factorization',
                        'AsShotNeutral supplies bounded white input; NeutralToXY iteration not replicated',
                        'Dual differing forward/calibration matrices rejected',
                        'No original X2D CCM pixel, HNCS FilmCurve, gamma or MAIN LUT sampling claim']}
            if args.output: args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result))

if __name__=='__main__':main()
