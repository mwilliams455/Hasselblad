#!/usr/bin/env python3
"""Known-scene Bayer fixtures and independent local-correction reference.
All fixtures are synthetic; no private photo/profile is required or embedded.
"""
import ctypes as C,json,sys
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter,maximum_filter
from reference97 import filter_chroma

def run(work):
    lib=C.CDLL(str((work/'libhbframe97.so').resolve()));U=C.POINTER(C.c_uint16)
    sig=[U,C.c_size_t,C.c_int,C.c_int,C.c_int,C.c_int,U,C.c_size_t,C.c_double,C.c_double]
    lib.hb96_render_band.argtypes=sig;lib.hb97_render_band.argtypes=sig
    lib.hb97_chroma_roi.argtypes=[U,C.c_size_t,C.c_int,C.c_int,C.c_double,C.c_double,U,C.c_size_t]
    ptr=lambda a:a.ctypes.data_as(U)
    def render(raw,n,revision):
        h,w=raw.shape;dst=np.empty((h-64,(w-64)&~1,3),np.uint16)
        for y in range(0,h-64,64):
            anchor=min(y,h-128);rows=min(64,h-64-y)
            a=np.ascontiguousarray(raw[anchor:anchor+128]);b=dst[y:y+rows]
            assert getattr(lib,'hb%d_render_band'%revision)(ptr(a),a.size,w,y-anchor,rows,4,ptr(b),b.size,n[0],n[2])==0
        return dst
    # Direct correction: independent float64 oracle, clipping guards, bound,
    # luminance preservation, identity, failure output, immutable input.
    rng=np.random.default_rng(970031);max_ref=0;max_y=0.;max_move=0.
    for n in [np.array([1.,1.,1.]),np.array([.35,1.,.6]),np.array([.0625,1.,16.])]:
        for style in ['flat','chroma','clipped','dark']:
            shape=(31,47,3)
            a=rng.integers(2000,40000,shape[:2])[...,None]*np.ones(shape)
            a*=n
            if style!='flat':a*=rng.uniform(.85,1.15,shape)
            if style=='dark':a*=.002
            src=np.clip(np.floor(a+.5),0,65535).astype(np.uint16)
            if style=='clipped':src[10,13,0]=0;src[20,27,1]=65535
            copy=src.copy();dst=np.full((27,43,3),123,np.uint16)
            assert lib.hb97_chroma_roi(ptr(src),src.size,47,31,n[0],n[2],ptr(dst),dst.size)==0
            expected=filter_chroma(src,n)[2:-2,2:-2]
            max_ref=max(max_ref,int(np.abs(dst.astype(int)-expected.astype(int)).max()))
            assert max_ref<=1
            orig=src[2:-2,2:-2];before=orig/n;after=dst/n
            yd=((after[:,:,0]+2*after[:,:,1]+after[:,:,2])-(before[:,:,0]+2*before[:,:,1]+before[:,:,2]))*.25
            max_y=max(max_y,float(np.abs(yd).max()))
            assert np.abs(yd).max() <= .125*(1/n[0]+2+1/n[2])+1e-9
            def chroma(x):
                s=x[:,:,0]+2*x[:,:,1]+x[:,:,2]
                return np.stack([(x[:,:,0]-x[:,:,1])/(s+1),(x[:,:,2]-x[:,:,1])/(s+1)],2)
            # Quantization-aware bound: compare against reference's continuous
            # correction separately; dark pixels can have larger relative ULPs.
            bright=np.min(before,2)>1000
            if np.any(bright):max_move=max(max_move,float(np.abs(chroma(after)-chroma(before))[bright].max()))
            unsafe=maximum_filter(np.any((src==0)|(src==65535),2),5)[2:-2,2:-2]
            assert np.array_equal(dst[unsafe],orig[unsafe])
            if style=='flat' and n[0]==1:assert np.array_equal(dst,orig)
            assert np.array_equal(src,copy)
            dst.fill(123)
            assert lib.hb97_chroma_roi(ptr(src),src.size-1,47,31,n[0],n[2],ptr(dst),dst.size)==-1
            assert np.all(dst==123)
            assert lib.hb97_chroma_roi(ptr(src),src.size,47,31,float('nan'),n[2],ptr(dst),dst.size)==-2
            assert np.all(dst==123)
            assert lib.hb97_chroma_roi(ptr(src),src.size,47,31,n[0],n[2],ptr(src),src.size)==-1
    assert max_move<=.0056
    records=[];seam_max=0;reference_max=0
    y,x=np.mgrid[:192,:192]
    colours=[([.55]*3,[.03]*3),([.5,.04,.04],[.04,.5,.04]),([.04,.08,.5],[.5,.4,.04]),
             ([.5]*3,[.25,.02,.25]),([.5]*3,[.18,.15,.18]),([.5]*3,[.08,.06,.08])]
    def case(n,angle,shape,sigma,ci,noise=0,scale=50000):
        nonlocal seam_max,reference_max
        d=(x-96.3)*np.cos(np.deg2rad(angle))+(y-96.3)*np.sin(np.deg2rad(angle))
        mask=(d>0).astype(float) if shape=='edge' else (np.abs(d)<int(shape[-1])*.5).astype(float)
        mask=gaussian_filter(mask,sigma);a,b=map(np.array,colours[ci]);truth=(a+(b-a)*mask[:,:,None])*n*scale
        raw=np.empty((192,192),np.float64)
        raw[::2,::2]=truth[::2,::2,0];raw[1::2,1::2]=truth[1::2,1::2,2]
        raw[::2,1::2]=truth[::2,1::2,1];raw[1::2,::2]=truth[1::2,::2,1]
        if noise:raw+=rng.normal(0,noise,raw.shape)
        raw=np.clip(np.floor(raw+.5),0,65535).astype(np.uint16)
        baseline=render(raw,n,96);candidate=render(raw,n,97);expected=filter_chroma(baseline,n)
        censored=maximum_filter((raw==0)|(raw==65535),5)[32:-32,32:-32]
        expected[censored]=baseline[censored]
        assert np.array_equal(candidate[censored],baseline[censored])
        diff=np.abs(candidate[2:-2,2:-2].astype(int)-expected[2:-2,2:-2].astype(int))
        reference_max=max(reference_max,int(diff.max()));seam_max=max(seam_max,int(diff[60:64].max()))
        # A neighbouring band's halo must contain the same RGB as the assembled
        # Stage96 image, including where 64-row bands meet.
        assert reference_max<=1,(n,angle,shape,sigma,ci,reference_max)
        target=truth[32:-32,32:-32];edge=np.abs(d[32:-32,32:-32])<8
        row={'neutral':n.tolist(),'angle':angle,'blur':sigma,'shape':shape,'colour':ci,'noise':noise,'scale':scale}
        for name,out in [('baseline',baseline),('candidate',candidate)]:
            err=(out.astype(float)-target)/n/scale
            row[name]={'rgb_rmse':float(np.sqrt(np.mean(err[edge]**2))),
                'chroma_rmse':float(np.sqrt(np.mean(((err[:,:,0]-err[:,:,1])**2+(err[:,:,2]-err[:,:,1])**2)[edge])))}
        row['material_rgb_regression']=row['candidate']['rgb_rmse']>row['baseline']['rgb_rmse']*1.05+.0001
        return row
    for n in map(np.array,[[1.,1.,1.],[.35,1.,.6],[.6,1.,.25],[1.5,1.,.7]]):
        for angle in [0,23,45,73,90]:
            for shape in ['edge','line1','line2','line4']:
                for sigma in [.3,1.]:
                    for ci in range(6):records.append(case(n,angle,shape,sigma,ci))
    # Held-out neutral vectors, orientations, blur and sensor noise. These test
    # bounds and measured regression; they do not establish high-ISO phone IQ.
    holdout=[]
    for n in map(np.array,[[.2,1.,.9],[.8,1.,1.4]]):
        for angle in [11,37,61,87]:
            for ci in range(6):
                for noise,scale in [(0,50000),(100,50000),(200,5000),(0,150000)]:
                    holdout.append(case(n,angle,'line2',.65,ci,noise,scale))
    def groups(rows):
        result=[]
        for ci,name in enumerate(['neutral','red_green','blue_yellow','strong_purple','pale_purple','dark_pale_purple']):
            rr=[r for r in rows if r['colour']==ci]
            result.append({'group':name,'cases':len(rr),'rgb_regressions':sum(r['material_rgb_regression'] for r in rr),
                'baseline_chroma_rmse':float(np.mean([r['baseline']['chroma_rmse'] for r in rr])),
                'candidate_chroma_rmse':float(np.mean([r['candidate']['chroma_rmse'] for r in rr]))})
        return result
    for row in groups(records):print(row,flush=True)
    for row in groups(holdout):print('holdout',row,flush=True)
    result={'status':'PASS_HOST_QUALITY_CHECKS','fixture_cases':len(records),'holdout_cases':len(holdout),
        'material_regression_definition':'candidate RGB RMSE > baseline * 1.05 + 0.0001',
        'groups':groups(records),'holdout_groups':groups(holdout),
        'largest_added_rgb_rmse':max(r['candidate']['rgb_rmse']-r['baseline']['rgb_rmse'] for r in records+holdout),
        'direct_reference_max_rgb16_error':max_ref,'assembled_reference_max_rgb16_error':reference_max,
        'band_seam_reference_max_rgb16_error':seam_max,'max_observed_luminance_rounding_error':max_y,
        'max_observed_bright_chroma_change_including_rounding':max_move,
        'clipped_neighbourhoods_unchanged':True,'phone_tested':False,'private_fixture_embedded':False}
    (work/'STAGE97_QUALITY_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
    (work/'STAGE97_SYNTHETIC_CASES.json').write_text(json.dumps(records+holdout,indent=2)+'\n')
    assert not any(r['material_rgb_regression'] for r in records+holdout),'Material synthetic colour regression'
    return result
if __name__=='__main__':run(Path(sys.argv[1]))
