#!/usr/bin/env python3
"""Stage21 synthetic-only NumPy and original Stage9 DISPLAY numerical parity.

This validates a *hypothetical MAIN* sampler's own maths. It is NOT a MAIN
hardware oracle and contains no vendor LUT/profile source or captured photos.
"""
from __future__ import annotations
import argparse, ctypes as ct, hashlib, itertools, json, os
from pathlib import Path
import subprocess, tempfile
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
C21=ROOT/'src'/'hb_main_candidate21.c'
C9=Path(os.environ.get('HB_STAGE9_C', '/mnt/data/hb_stage9/src/hb_display_lut16.c'))
C8=Path(os.environ.get('HB_STAGE8_C', '/mnt/data/hb_stage8/src/hb_main_lut_profile.c'))

class Receipt(ct.Structure):
    _fields_=[('schema',ct.c_uint32),('points',ct.c_uint32),('interpolation',ct.c_uint32),('axis_to_input_code',ct.c_uint32),('bank_to_output_code',ct.c_uint32),('source_words',ct.c_uint32),('planar_packing_assumed',ct.c_uint32),('main_isp_pixel_equivalence_proven',ct.c_uint32),('photographic_render_authorized',ct.c_uint32)]
class ProfileReceipt(ct.Structure):
    _fields_=[('schema',ct.c_uint32),('first_cct',ct.c_uint32),('frac_cct',ct.c_uint32),('gamut_index',ct.c_uint32),('gamut_frac',ct.c_uint32),('written',ct.c_uint32),('pixel_sampler',ct.c_uint32),('render',ct.c_uint32)]

def compile_lib(directory:Path,cc='cc',opt='-O2',name='stage21.so'):
    target=directory/name
    flags=['-std=c11','-fPIC','-shared','-Wall','-Wextra','-Werror',opt]
    subprocess.run([cc,*flags,str(C21),str(C9),str(C8),'-lm','-o',str(target)],check=True,capture_output=True,timeout=30)
    obj=ct.CDLL(str(target))
    p32=ct.POINTER(ct.c_uint32);pd=ct.POINTER(ct.c_double);p8=ct.POINTER(ct.c_uint8)
    obj.hb21_sample_candidate.argtypes=[p32,ct.c_size_t,pd,ct.c_size_t,pd,ct.c_size_t,ct.c_size_t,p8,p8,ct.c_int,ct.POINTER(Receipt)]
    obj.hb21_sample_candidate.restype=ct.c_int
    obj.hb_display_lut16_trilinear.argtypes=[p32,ct.c_size_t,pd,pd]
    obj.hb_display_lut16_trilinear.restype=ct.c_int
    obj.hb_main_lut_prepare.argtypes=[p32,ct.c_size_t,ct.c_size_t,ct.c_int32,ct.c_int32,p32,ct.c_size_t,ct.POINTER(ProfileReceipt)]
    obj.hb_main_lut_prepare.restype=ct.c_int
    return obj

def as_ptr(a,ctype):return a.ctypes.data_as(ct.POINTER(ctype))

def cube_to_words(cube):
    assert cube.shape==(16,16,16,3)
    arr=np.moveaxis(cube,-1,0).reshape(3,4096)
    lanes=np.rint(np.clip(arr,0,1)*4095).astype(np.uint16).reshape(-1)
    return (lanes[::2].astype(np.uint32)|(lanes[1::2].astype(np.uint32)<<16)).copy()

def words_to_cube(words):
    words=np.asarray(words,dtype=np.uint32)
    assert words.size==6144
    lanes=np.empty(12288,dtype=np.float64)
    lanes[::2]=(words&65535).astype(float)/4095
    lanes[1::2]=(words>>16).astype(float)/4095
    return np.moveaxis(lanes.reshape(3,16,16,16),0,-1)

def make_cube(which='nonlinear'):
    x=np.stack(np.meshgrid(*([np.arange(16)/15.0]*3),indexing='ij'),axis=-1)
    r,g,b=x[...,0],x[...,1],x[...,2]
    if which=='identity':return x
    if which=='nonlinear':
        return np.stack((np.clip(.86*r+.08*g*b+.03*b,0,1),
                         np.clip(.90*g+.04*r*b+.02*r,0,1),
                         np.clip(.92*b+.05*r*g+.02*g,0,1)),axis=-1)
    if which=='adversarial':
        return np.stack((r*(.5+.5*b),g*(.6+.4*r),b*(.5+.5*g)),axis=-1)
    raise ValueError(which)

def c_apply(lib,words,pixels,interp=0,axes=(0,1,2),banks=(0,1,2)):
    words=np.ascontiguousarray(words,dtype=np.uint32)
    pixels=np.ascontiguousarray(pixels,dtype=np.float64)
    result=np.full_like(pixels,-999.0)
    a=(ct.c_uint8*3)(*axes);b=(ct.c_uint8*3)(*banks);rc=Receipt()
    status=lib.hb21_sample_candidate(as_ptr(words,ct.c_uint32),len(words),as_ptr(pixels,ct.c_double),pixels.size,as_ptr(result,ct.c_double),result.size,len(pixels),a,b,interp,ct.byref(rc))
    return status,result,rc

def py_eval(cube,pixels,interp=0,axes=(0,1,2),banks=(0,1,2)):
    # Original physical banks, always ordered 0,1,2
    cube=np.asarray(cube,float);p=np.asarray(pixels,float)
    normalized=np.clip(p[:,list(axes)]*15,0,15)
    lo=np.floor(normalized).astype(int)
    hi=np.minimum(lo+1,15)
    fractions=normalized-lo
    result=np.zeros((len(p),3),float)
    def nodes(bits):
        ind=np.where(bits,hi,lo)
        return cube[ind[:,0],ind[:,1],ind[:,2]]
    if interp==0:
        for bits in itertools.product((0,1),repeat=3):
            bits=np.asarray(bits,dtype=int)
            weights=np.prod(np.where(bits,fractions,1-fractions),axis=1)
            result+=nodes(bits)*weights[:,None]
    else:
        c0=nodes(np.zeros((len(p),3),dtype=int))
        order=np.argsort(-fractions,axis=1,kind='stable')
        result[:]=c0
        for j in range(3):
            bits=np.zeros((len(p),3),dtype=int)
            for k in range(j+1):bits[np.arange(len(p)),order[:,k]]=1
            new=nodes(bits)
            mask=np.take_along_axis(fractions,order[:,j:j+1],axis=1)
            result+=(new-c0)*mask
            c0=new
    out=np.zeros_like(result)
    for bank,outchannel in enumerate(banks):out[:,outchannel]=result[:,bank]
    return out

def test_invalid(lib,words,p):
    words=np.ascontiguousarray(words,dtype=np.uint32);p=np.ascontiguousarray(p,dtype=np.float64)
    ret=np.full_like(p,4321.0);r=Receipt();r.schema=0xdeadbeef
    identity=(ct.c_uint8*3)(0,1,2)
    def run(src=words,pix=p,out=ret,shape=None,pcode=identity,interp=0,rec=r,points=None):
        pts=len(pix) if points is None else points
        return lib.hb21_sample_candidate(as_ptr(src,ct.c_uint32),len(src),as_ptr(pix,ct.c_double),pix.size if shape is None else shape,as_ptr(out,ct.c_double),out.size,pts,pcode,identity,interp,ct.byref(rec))
    checks=0
    malformed=words.copy();malformed[0]|=np.uint32(0xf0000000)
    assert run(src=malformed)==3 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    badp=p.copy();badp[-1,1]=float('nan')
    assert run(pix=badp)==4 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    badp=p.copy();badp[-1,1]=-0.01
    assert run(pix=badp)==4 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    badp=p.copy();badp[-1,1]=1.01
    assert run(pix=badp)==4 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    badperm=(ct.c_uint8*3)(0,0,2)
    assert run(pcode=badperm)==5 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    assert run(interp=17)==6 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    assert run(shape=p.size-1)==2 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    # source/input overlap caught: point at uint32 table reinterpretation
    fake=np.ndarray((3,),dtype=np.float64,buffer=words,offset=0)
    n=lib.hb21_sample_candidate(as_ptr(words,ct.c_uint32),len(words),as_ptr(fake,ct.c_double),3,as_ptr(ret[:1],ct.c_double),3,1,identity,identity,0,ct.byref(r))
    assert n==7 and np.all(ret==4321) and r.schema==0xdeadbeef;checks+=1
    # partial input/output overlap caught
    slab=np.ones((len(p)*3+1,),dtype=np.float64)
    pi=slab[:-1].reshape(-1,3);po=slab[1:].reshape(-1,3)
    assert run(pix=pi,out=po)==7 and r.schema==0xdeadbeef;checks+=1
    # Exact in-place is valid and correct
    inplace=p.copy();status=lib.hb21_sample_candidate(as_ptr(words,ct.c_uint32),len(words),as_ptr(inplace,ct.c_double),inplace.size,as_ptr(inplace,ct.c_double),inplace.size,len(p),identity,identity,0,ct.byref(r))
    assert status==0 and r.photographic_render_authorized==0;checks+=1
    return checks

def test(cc='cc',opt='-O2'):
    rng=np.random.default_rng(20261022)
    pts=np.concatenate((rng.uniform(0,1,(1020,3)), np.array([[0,0,0],[1,1,1],[0,0,1],[1,0,0.5]])))
    tested=0;maxerr=0;stage9err=0;permutation_tests=0;tetra_vs_tri=[]
    with tempfile.TemporaryDirectory() as td:
        lib=compile_lib(Path(td),cc=cc,opt=opt)
        invalid_checks=0
        for shape in ('identity','nonlinear','adversarial'):
            words=cube_to_words(make_cube(shape));cube=words_to_cube(words)
            invalid_checks+=test_invalid(lib,words,pts[:16])
            for axes in itertools.permutations((0,1,2)):
                # all six relabellings in Stage20's equivalence class
                for mode in (0,1):
                    status,y,receipt=c_apply(lib,words,pts,mode,axes,axes)
                    assert status==0 and receipt.main_isp_pixel_equivalence_proven==0 and receipt.photographic_render_authorized==0
                    expected=py_eval(cube,pts,mode,axes,axes)
                    e=float(np.max(np.abs(y-expected)))
                    assert e<3e-15,(shape,axes,mode,e)
                    maxerr=max(maxerr,e)
                    tested+=pts.size
                    permutation_tests+=1
                    if axes==(0,1,2) and mode==1:
                        tri=py_eval(cube,pts,0)
                        tetra_vs_tri.append(float(np.max(np.abs(y-tri))))
                    if axes==(0,1,2) and mode==0:
                        for k in (0,12,88,700,1023):
                            x=pts[k].copy();yy=np.zeros(3,float)
                            z=lib.hb_display_lut16_trilinear(as_ptr(words,ct.c_uint32),len(words),as_ptr(x,ct.c_double),as_ptr(yy,ct.c_double))
                            assert z==0
                            er=float(np.max(np.abs(yy-y[k])));assert er<1e-15
                            stage9err=max(stage9err,er)
        # Exercise real original Stage8 profile-preparation engine on synthetic matrices
        sources=np.concatenate([cube_to_words(np.clip(make_cube('nonlinear')*(0.9+0.01*k),0,1)) for k in range(8)]).astype(np.uint32)
        out=np.zeros(6144,dtype=np.uint32);rr=ProfileReceipt()
        status=lib.hb_main_lut_prepare(as_ptr(sources,ct.c_uint32),sources.size,6144,4300,1,as_ptr(out,ct.c_uint32),6144,ct.byref(rr))
        assert status==0 and rr.written==6144 and rr.pixel_sampler==0 and rr.render==0
        status,y,rc=c_apply(lib,out,pts,0)
        assert status==0 and np.isfinite(y).all()
    return {'schema':'hb-stage21-candidate-tests-v1','status':'PASS','cc':cc,'optimization':opt,
            'reference':'independent_numpy_and_original_verified_stage9_DISPLAY_sampler',
            'synthetic_cube_families':3,'input_points_per_case':len(pts),'tested_permutations':6,
            'modes':['trilinear','tetrahedral'],'validated_scalar_outputs':tested,
            'max_absolute_error_vs_numpy':maxerr,'stage9_display_baseline_max_absolute_error':stage9err,
            'synthetic_permutation_mode_cases':permutation_tests,
            'negative_and_nonmutation_checks':invalid_checks,
            'tetrahedral_vs_trilinear_max_on_synthetic_per_case':tetra_vs_tri,
            'original_main_isp_pixel_oracle_used':False,
            'original_vendor_table_values_used':False,
            'photographic_render_authorized':False,'photo_renderer_modified':False}

def main():
    pa=argparse.ArgumentParser();pa.add_argument('--cc',default='cc');pa.add_argument('--opt',default='-O2');pa.add_argument('--output',type=Path)
    a=pa.parse_args();v=test(a.cc,a.opt)
    if a.output:a.output.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps(v))
if __name__=='__main__':main()
