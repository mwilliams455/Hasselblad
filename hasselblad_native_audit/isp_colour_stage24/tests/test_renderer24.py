#!/usr/bin/env python3
"""Independent synthetic C/NumPy parity and fail-closed pixel checks for Stage24.

No original phone images, Hasselblad LUT payloads or private camera matrices.
"""
from __future__ import annotations
import argparse, ctypes as C,json,tempfile,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'src'))
from offline_render24 import Context,Receipt,compile_shared,p,srgb_preview,decode_rationals

D50=np.array([.9642,1.,.8249]);I=np.eye(3)
P=C.POINTER(C.c_double)

def refbuild(fm,cc,ab,neutral):
    fm=np.asarray(fm).reshape(3,3).copy()
    fm=fm*(D50/(fm@np.ones(3)))[:,None]
    b=np.linalg.inv(np.diag(ab)@cc)
    n=neutral/max(neutral)
    return fm@np.diag(1/(b@n))@b

def output_ref(gamut):
    xy=np.array([[.64,.33],[.30,.60],[.15,.06]] if gamut==0 else
                [[.68,.32],[.265,.69],[.15,.06]])
    prim=np.stack([xy[:,0]/xy[:,1],np.ones(3),(1-xy[:,0]-xy[:,1])/xy[:,1]])
    D65=np.array([.3127/.329,1,(1-.3127-.329)/.329])
    B=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
    cat=np.linalg.inv(B)@np.diag((B@D65)/(B@D50))@B
    return np.linalg.inv(prim@np.diag(np.linalg.solve(prim,D65)))@cat

def call_build(lib,fm,cc,ab,n,gamut):
    ctx=Context();r=Receipt();r.schema=333
    fm=np.ascontiguousarray(fm,dtype=np.float64)
    cc=np.ascontiguousarray(cc,dtype=np.float64)
    ab=np.ascontiguousarray(ab,dtype=np.float64)
    n=np.ascontiguousarray(n,dtype=np.float64)
    status=lib.hb24_build(p(fm),p(fm),p(cc),p(cc),p(ab),p(n),gamut,
                           C.byref(ctx),C.byref(r))
    return status,ctx,r

def call_pixels(lib,ctx,x,mode=0,lut=None,axes=None,banks=None,interp=0):
    x=np.ascontiguousarray(x,dtype=np.float64)
    y=np.full_like(x,37.0)
    receipt=Receipt();receipt.schema=999
    lp=lut.ctypes.data_as(C.POINTER(C.c_uint32)) if lut is not None else None
    ac=axes.ctypes.data_as(C.POINTER(C.c_uint8)) if axes is not None else None
    bc=banks.ctypes.data_as(C.POINTER(C.c_uint8)) if banks is not None else None
    status=lib.hb24_process(C.byref(ctx),p(x),len(x),p(y),mode,lp,
                len(lut) if lut is not None else 0,ac,bc,interp,C.byref(receipt))
    return status,y,receipt

def identity_lut():
    src=np.zeros(6144,dtype=np.uint32)
    for r in range(16):
      for g in range(16):
       for b in range(16):
        idx=128*r+8*g+b//2;shift=(b&1)*16
        for bank,val in enumerate((r,g,b)):
            code=round(4095*val/15)
            src[2048*bank+idx]|=np.uint32(code<<shift)
    assert (src&0xf000f000==0).all()
    return src

def run(compiler):
    rng=np.random.default_rng(20261022)
    tested=0;channels=0;worst=0;negative=0;header_cases=0
    with tempfile.TemporaryDirectory() as td:
        lib=compile_shared(Path(td)/('hb24_'+compiler+'.so'),cc=compiler)
        for index in range(64):
            fm=np.array([[.6,.14,.21],[.17,.72,.09],[-.03,-.14,1.23]],dtype=float)
            fm+=rng.uniform(-.025,.025,(3,3))
            cc=I+rng.uniform(-.02,.02,(3,3))
            ab=rng.uniform(.92,1.06,3)
            neutral=rng.uniform(.4,1.0,3)
            neutral/=max(neutral)
            x=rng.uniform(-.07,1.6,(256,3));x=np.ascontiguousarray(x)
            for g in (0,1):
                status,ctx,receipt=call_build(lib,fm,cc,ab,neutral,g)
                assert status==0 and ctx.schema==24 and receipt.schema==24
                assert receipt.photographic_render_authorized==0
                actual_matrix=np.asarray(ctx.camera_to_xyz_d50).reshape(3,3)
                ref=refbuild(fm,cc,ab,neutral)
                assert np.max(abs(actual_matrix-ref))<4e-15
                actual_output_matrix=np.asarray(ctx.xyz_d50_to_linear_rgb).reshape(3,3)
                assert np.max(abs(actual_output_matrix-output_ref(g)))<4e-15
                status,y,r=call_pixels(lib,ctx,x)
                assert status==0 and r.schema==24 and r.pixel_count==256
                assert r.photographic_render_authorized==0
                assert r.true_hasselblad_ccm_pixel_proven==0
                assert r.true_hasselblad_gamma_pixel_proven==0
                assert r.true_hasselblad_lut_pixel_proven==0
                assert r.existing_phone_renderer_modified==0
                expect=(x@ref.T)@output_ref(g).T
                err=float(np.max(np.abs(y-expect)))
                assert err<2.e-14,err
                worst=max(worst,err);channels+=len(x)*3;tested+=1
                negative+=int((y<0).sum())
        fm=D50[:,None]*np.eye(3)
        status,ctx,r=call_build(lib,fm,I,np.ones(3),np.ones(3),0)
        assert status==0
        # This is a synthetic *identity colour cube*, NOT vendor data.
        table=identity_lut();axes=np.array([0,1,2],dtype=np.uint8);banks=axes.copy()
        target=np.ascontiguousarray(rng.uniform(.05,.95,(100,3)))
        # Context construction above yields neutral linear RGB for camera RGB
        # that is the inverse of the composed matrix: solve for a bounded target.
        m=np.asarray(ctx.xyz_d50_to_linear_rgb).reshape(3,3)@np.asarray(ctx.camera_to_xyz_d50).reshape(3,3)
        camera=np.ascontiguousarray(target@np.linalg.inv(m).T)
        for method in (0,1):
            status,y,r=call_pixels(lib,ctx,camera,1,table,axes,banks,method)
            assert status==0 and r.uses_stage21_MAIN_hypothesis==1
            assert r.photographic_render_authorized==0
            assert np.max(abs(y-target))<=1.0/4095+1e-13
            header_cases+=1
        # Deliberate high-headroom input must fail without clipping/mutating output.
        overshoot=target.copy();overshoot[-1,0]=1.4
        camera=np.ascontiguousarray(overshoot@np.linalg.inv(m).T)
        status,y,r=call_pixels(lib,ctx,camera,1,table,axes,banks,0)
        assert status==5 and np.all(y==37) and r.schema==999
        header_cases+=1
        bad=table.copy();bad[0]=np.uint32(0xf0000000)
        status,y,r=call_pixels(lib,ctx,np.ascontiguousarray(target@np.linalg.inv(m).T),1,bad,axes,banks,0)
        assert status!=0 and np.all(y==37.) and r.schema==999
        header_cases+=1
        invalidcam=np.ascontiguousarray(target@np.linalg.inv(m).T);invalidcam[0,0]=np.nan
        status,y,r=call_pixels(lib,ctx,invalidcam)
        assert status!=0 and np.all(y==37.) and r.schema==999
        header_cases+=1
        invalid=np.array([0,0,2],dtype=np.uint8)
        status,y,r=call_pixels(lib,ctx,np.ascontiguousarray(target@np.linalg.inv(m).T),1,table,invalid,banks,0)
        assert status!=0 and np.all(y==37.) and r.schema==999
        header_cases+=1
        # No original DNG processing opcode, Film Tone or camera WB claim.
        e=srgb_preview(np.array([[-0.1,.02,.5],[1.5,0.5,1.]],dtype=np.float32))
        assert e.dtype==np.uint8 and e.shape==(2,3) and e[0,0]==0 and e[1,0]==255
        header_cases+=1
    return {'status':'PASS','schema':'stage24_native_colourimetric_composition-v1',
       'compiler':compiler,'synthetic_camera_profile_gamut_cases':tested,
       'synthetic_channel_outputs_compared':channels,
       'C_vs_Numpy_max_abs_error':worst,
       'negative_synthetic_output_components_preserved':negative,
       'candidate_identity_and_finite_fail_closed_cases':header_cases,
       'Hasselblad_ISP_equivalence_proven':False,
       'vendor_main_lut_data_used':False,
       'production_saved_photo_renderer_unchanged':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--compiler',default='gcc');ap.add_argument('--output',type=Path)
    a=ap.parse_args();data=run(a.compiler)
    if a.output:
        a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))
if __name__=='__main__':main()
