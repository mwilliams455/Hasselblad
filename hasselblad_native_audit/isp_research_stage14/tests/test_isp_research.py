#!/usr/bin/env python3
"""Synthetic-only Stage14 software ISP assembly contract + independent oracle.

Original vendor camera LUT bytes, user photos, RAW and gamma pixel curves
are deliberately absent. Stage8 and CCM *parameter* arithmetic has prior
original-code evidence. Stage9 pixel sampler is DISPLAY ONLY.
"""
import argparse
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
AUDIT_ROOT=ROOT.parents[0]
LUT_C=Path(os.environ.get('HB_STAGE8_LUT_C', str(ROOT.parent/'hb_stage8/src/hb_main_lut_profile.c')))
DISPLAY_C=Path(os.environ.get('HB_STAGE9_DISPLAY_C',str(ROOT.parent/'hb_stage9/src/hb_display_lut16.c')))
CCM_C=Path(os.environ.get('HB_CCM_PREPARE_C',str(ROOT/'src/ccm_prepare.c')))
SRC=ROOT/'src/hb_isp_research.c'
MAIN_HEADER=LUT_C.parent
DISP_HEADER=DISPLAY_C.parent
CCM_HEADER=CCM_C.parent

class Receipt(C.Structure):
    _fields_=[(name,C.c_uint32) for name in (
        'schema','research_only','photographic_render_authorized',
        'main_pixel_sampler_verified','ccm_pixel_equation_verified',
        'gamma_pixel_evaluation_verified','display_only_sampler_reference',
        'route','cct_first_index','cct_fraction_q8','gamut_selector',
        'secondary_ccm_weight_q8','prepared_lut_words',
        'prepared_ccm_values','gamma_coordinate_count','sampled_test_pixels',
        'unresolved_contracts_mask')]

def lib_compile(directory:Path, optimization='-O2'):
    libpath=directory/'libhb_isp_research.so'
    args=[os.environ.get('CC','cc'),'-std=c11',optimization,'-Wall','-Wextra','-Werror','-ffp-contract=off',
          '-fPIC','-shared',
          '-I'+str(ROOT/'src'),'-I'+str(MAIN_HEADER),
          '-I'+str(DISP_HEADER),'-I'+str(CCM_HEADER),
          str(SRC),str(LUT_C),str(DISPLAY_C),str(CCM_C),'-lm','-o',str(libpath)]
    subprocess.run(args,check=True,capture_output=True,text=True)
    lib=C.CDLL(str(libpath))
    u32=C.POINTER(C.c_uint32)
    i32=C.POINTER(C.c_int32)
    f64=C.POINTER(C.c_double)
    lib.hb_isp_research_prepare.argtypes=[u32,C.c_size_t,i32,C.c_size_t,u32,
                                          C.c_int32,C.c_int32,C.c_int32,C.c_uint32,
                                          u32,i32,u32,C.POINTER(Receipt)]
    lib.hb_isp_research_prepare.restype=C.c_int
    lib.hb_isp_research_gamma_knots.argtypes=[u32,u32]
    lib.hb_isp_research_gamma_knots.restype=C.c_int
    lib.hb_isp_research_display_candidate.argtypes=[u32,f64,C.c_size_t,
                                                     f64,C.POINTER(Receipt)]
    lib.hb_isp_research_display_candidate.restype=C.c_int
    lib.hb_isp_research_main_gate.argtypes=[u32]
    lib.hb_isp_research_main_gate.restype=C.c_int
    return lib,args

def synthetic_main_profiles():
    """Six distinct synthetic profiles, [0,1]/[4,5] equal like original hashes.
    Deliberately NOT actual vendor values or purported ISP format.
    Input data encoded in known verified DISPLAY packing for hypothesis tests.
    """
    words=[0]*(8*6144)
    for p in range(8):
        ck=p%4
        if ck==1:ck=0
        g=p//4
        for r in range(16):
            for gr in range(16):
                for b in range(16):
                    comps=[64+40*r+13*gr+9*b+112*ck+190*g,
                           85+17*r+47*gr+23*b+131*ck+90*g,
                           90+19*r+11*gr+49*b+109*ck+153*g]
                    q=128*r+8*gr+b//2;shift=16*(b&1)
                    for c,val in enumerate(comps):
                        assert 0<=val<=4095
                        words[p*6144+2048*c+q]|=val<<shift
    assert len(words)==49152
    return words

def synthetic_ccm_profiles():
    src=[]
    for p in range(8):
        for j in range(96):
            src.append(200*(p%4)+300*(p//4)+(-190 if j%2 else 70)+j%6*13-600)
    assert len(src)==768 and min(src)>-32768 and max(src)<32767
    return src

def coeff(cct):
    t=[2400,3050,5550,9100]
    if cct<t[0]:return 0,0
    if cct>=t[-1]:return 2,256
    for i in range(3):
        if cct<t[i+1]:return i,(cct-t[i])*256//(t[i+1]-t[i])
    raise RuntimeError

def interpolate(a,b,wt):return a+((b-a)*wt//256)

def s16(word,shift):
    v=(word>>shift)&65535
    return v-65536 if v>=32768 else v

def ref_profile(source,cct,gamut):
    ci,wt=coeff(cct)
    out=[]
    for j in range(6144):
        lanes=[]
        for sh in (0,16):
            a=interpolate(s16(source[ci*6144+j],sh),
                          s16(source[(ci+1)*6144+j],sh),wt)
            b=interpolate(s16(source[(ci+4)*6144+j],sh),
                          s16(source[(ci+5)*6144+j],sh),wt)
            lanes.append(interpolate(a,b,256*gamut))
        out.append((lanes[0]&65535)|((lanes[1]&65535)<<16))
    return out

def ref_ccm(source,cct,highiso):
    ci,wt=coeff(cct)
    out=[]
    for j in range(96):
        a=interpolate(source[ci*96+j],source[(ci+1)*96+j],wt)
        b=interpolate(source[(ci+4)*96+j],source[(ci+5)*96+j],wt)
        out.append(interpolate(a,b,highiso))
    return out

def ref_knots(divs):
    bs=[0,1024,2048,4096,8192,16384,32768,65536]
    if len(divs)!=7 or any(not 0<=d<=7 for d in divs) or sum(1<<d for d in divs)!=256:
        raise ValueError('unsupported gamma division')
    result=[0]
    for i,d in enumerate(divs):
        n=1<<d
        step=(bs[i+1]-bs[i]+n//2)//n
        result.extend(bs[i]+step*j for j in range(1,n))
        result.append(bs[i+1])
    assert len(result)==257
    return result

def ref_node(table,r,g,b):
    q=128*r+8*g+b//2
    shift=16*(b&1)
    return [((table[q+i*2048]>>shift)&4095)/4095.0 for i in range(3)]

def ref_trilinear(table,rgb):
    coord=[x*15.0 for x in rgb]
    lo=[int(math.floor(x)) for x in coord]
    hi=[min(15,x+1) for x in lo]
    f=[p-base for p,base in zip(coord,lo)]
    accum=[0.0,0.0,0.0]
    for rr in range(2):
        for gg in range(2):
            for bb in range(2):
                w=(f[0] if rr else 1-f[0])*(f[1] if gg else 1-f[1])*(f[2] if bb else 1-f[2])
                node=ref_node(table,hi[0] if rr else lo[0],hi[1] if gg else lo[1],hi[2] if bb else lo[2])
                for c in range(3): accum[c]+=w*node[c]
    return accum

def digest_words(data):return hashlib.sha256(struct.pack('<%dI'%len(data),*data)).hexdigest()

def make_receipt():
    obj=Receipt()
    C.memset(C.byref(obj),0x5a,C.sizeof(obj))
    return obj

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/STAGE14_SOFTWARE_ISP_REFERENCE.json')
    opts=parser.parse_args()
    cases=0; checks=0
    source=synthetic_main_profiles(); ccm_source=synthetic_ccm_profiles()
    lsrc=(C.c_uint32*len(source))(*source)
    csrc=(C.c_int32*len(ccm_source))(*ccm_source)
    divs=(C.c_uint32*7)(2,2,3,4,5,6,7)
    cct_examples=[2400,3050,4300,5550,7001,9100]
    inputs=[]
    for i in range(1024):
        inputs.extend(((i%32)/31.0,(i//32)/31.0,((i*37)%1024)/1023.0))
    cin=(C.c_double*len(inputs))(*inputs)
    maxdiff=0.0
    run_receipts=[]
    with tempfile.TemporaryDirectory(prefix='hb-stage14-research-') as tmp:
        for opt in ('-O0','-O2'):
            lib,build=lib_compile(Path(tmp),opt)
            checkmask=C.c_uint32(0)
            assert lib.hb_isp_research_main_gate(C.byref(checkmask))==7
            assert checkmask.value==255
            assert lib.hb_isp_research_main_gate(None)==1
            checks+=2
            for test_divs in ([2,2,3,4,5,6,7],[7,6,5,4,3,2,2],[2,3,2,4,6,5,7]):
                p=(C.c_uint32*7)(*test_divs)
                out=(C.c_uint32*257)()
                assert lib.hb_isp_research_gamma_knots(p,out)==0
                assert list(out)==ref_knots(test_divs)
                checks+=257
            assert ref_knots([2,2,3,4,5,6,7])==list(range(0,65537,256))
            checks+=1
            fullcases=[]
            for cct in cct_examples:
                for gamut in (0,1):
                    for route in range(3):
                        wt=73 if route==0 else 191 if route==1 else 256
                        lut=(C.c_uint32*6144)()
                        ccm=(C.c_int32*96)()
                        gamma=(C.c_uint32*257)()
                        receipt=make_receipt()
                        assert lib.hb_isp_research_prepare(lsrc,49152,csrc,768,divs,cct,gamut,wt,route,
                                                           lut,ccm,gamma,C.byref(receipt))==0
                        ref=ref_profile(source,cct,gamut)
                        assert list(lut)==ref,(cct,gamut,route)
                        assert list(ccm)==ref_ccm(ccm_source,cct,wt)
                        assert list(gamma)==ref_knots([2,2,3,4,5,6,7])
                        assert receipt.photographic_render_authorized==0
                        assert receipt.main_pixel_sampler_verified==0
                        assert receipt.ccm_pixel_equation_verified==0
                        assert receipt.gamma_pixel_evaluation_verified==0
                        assert receipt.research_only==1
                        assert receipt.unresolved_contracts_mask==255
                        assert receipt.prepared_lut_words==6144
                        assert receipt.prepared_ccm_values==96
                        assert receipt.gamma_coordinate_count==257
                        assert receipt.route==route
                        checks+=6144+96+257
                        output=(C.c_double*len(inputs))()
                        assert lib.hb_isp_research_display_candidate(lut,cin,1024,output,C.byref(receipt))==0
                        assert receipt.sampled_test_pixels==1024
                        diffs=[]
                        for i in range(1024):
                            oracle=ref_trilinear(ref,inputs[i*3:i*3+3])
                            diffs.extend(abs(output[3*i+ch]-oracle[ch]) for ch in range(3))
                        err=max(diffs)
                        assert err<3e-15,err
                        maxdiff=max(maxdiff,err)
                        checks+=len(diffs)
                        fullcases.append((cct,gamut,route,wt,digest_words(ref),err))
                        cases+=1
            # Fixed-CCT/gamut preparation is route-independent in this RESEARCH fixture.
            for cct in cct_examples:
                for g in (0,1):
                    group={row[4] for row in fullcases if row[0]==cct and row[1]==g}
                    assert len(group)==1
                    checks+=1
            # Duplicated warm profiles are the only predeclared equality.
            for gamut in (0,1):
                assert ref_profile(source,2400,gamut)==ref_profile(source,3050,gamut)
                assert ref_profile(source,3050,gamut)!=ref_profile(source,5550,gamut)
                checks+=2
            # Rejected photo domain, invalid sampling, alias and malformed LUT.
            lut=(C.c_uint32*6144)()
            ccm=(C.c_int32*96)()
            gamma=(C.c_uint32*257)()
            receipt=make_receipt()
            assert lib.hb_isp_research_prepare(lsrc,49152,csrc,768,divs,4300,0,0,0,
                                               lut,ccm,gamma,C.byref(receipt))==0
            snap_lut=bytes(lut);snap_ccm=bytes(ccm);snap_gamma=bytes(gamma);snap_receipt=bytes(receipt)
            baddiv=(C.c_uint32*7)(0,0,0,0,0,0,0)
            for params in [
                (lsrc,49151,csrc,768,divs,4300,0,0,0),
                (lsrc,49152,csrc,767,divs,4300,0,0,0),
                (lsrc,49152,csrc,768,divs,4300,2,0,0),
                (lsrc,49152,csrc,768,divs,4300,0,257,0),
                (lsrc,49152,csrc,768,divs,4300,0,-1,0),
                (lsrc,49152,csrc,768,divs,4300,0,0,3),
                (lsrc,49152,csrc,768,baddiv,4300,0,0,0),
                (lsrc,49152,csrc,768,divs,4300,0,0,0)
                ]:
                if params is not None:
                    if params== (lsrc,49152,csrc,768,divs,4300,0,0,0):
                        # Explicit output/input alias case.
                        result=lib.hb_isp_research_prepare(*params,lsrc,ccm,gamma,C.byref(receipt))
                    else:
                        result=lib.hb_isp_research_prepare(*params,lut,ccm,gamma,C.byref(receipt))
                    assert result!=0
                    assert bytes(lut)==snap_lut and bytes(ccm)==snap_ccm
                    assert bytes(gamma)==snap_gamma and bytes(receipt)==snap_receipt
                    checks+=4
            altered=(C.c_int32*768)(*ccm_source)
            altered[4]=40000
            assert lib.hb_isp_research_prepare(lsrc,49152,altered,768,divs,4300,0,0,0,
                                               lut,ccm,gamma,C.byref(receipt))!=0
            assert bytes(lut)==snap_lut and bytes(ccm)==snap_ccm and bytes(gamma)==snap_gamma
            checks+=4
            valid_px=(C.c_double*3)(0.1,0.2,0.3)
            bad_px_cases=[(C.c_double*3)(-0.001,0.5,0.3),
                          (C.c_double*3)(1.001,0.5,0.3),
                          (C.c_double*3)(float('nan'),0.5,0.3),
                          (C.c_double*3)(float('inf'),0.5,0.3)]
            result=(C.c_double*3)(-999,-999,-999)
            receipt_snapshot=bytes(receipt)
            for inp in bad_px_cases:
                assert lib.hb_isp_research_display_candidate(lut,inp,1,result,C.byref(receipt))==3
                assert list(result)==[-999]*3 and bytes(receipt)==receipt_snapshot
                checks+=3
            assert lib.hb_isp_research_display_candidate(lut,valid_px,0,result,C.byref(receipt))==2
            assert lib.hb_isp_research_display_candidate(lut,valid_px,1025,result,C.byref(receipt))==2
            assert lib.hb_isp_research_display_candidate(lut,valid_px,1,valid_px,C.byref(receipt))==4
            checks+=3
            # The testing modes are labels, not evidence that normal and HDR vendor
            # routes actually share the same final photographic image output.
            run_receipts.extend({'optimization':opt,'cct_k':cct,'gamut':g,
                                 'research_route':route,'ccm_secondary_weight_q8':w,
                                 'synthetic_prepared_lut_sha256':sha,'max_abs_pixel_error':e}
                                for cct,g,route,w,sha,e in fullcases)
    report={
        'schema':'hasselblad-stage14-composed-software-isp-research-v1',
        'status':'PASS',
        'original_firmware_version':'X2D II 100C 1.3.16.2',
        'librcam_preparation':'Stage8 native-vector validated; portable linkage exercised',
        'ccm_preparation':'prior original-reference validated; 96 coefficients per synthetic profile',
        'gamma_coordinates':'prior original-instruction validated; 257 positive coordinates, NOT pixel evaluation',
        'pixel_lut_interpretation':'Stage9 exact DISPLAY library format only; MAIN relation unverified',
        'optimization_levels':['-O0','-O2'],
        'prepared_synthetic_profile_cases':cases,
        'sampled_test_pixels_per_case':1024,
        'synthetic_pixel_components_compared':cases*1024*3,
        'max_pixel_absolute_difference':maxdiff,
        'total_independent_checks':checks,
        'mode_route_changes_profile_in_lab':False,
        'original_mode_equality_proven':False,
        'original_isp_or_dsp_executed_in_this_study':False,
        'original_vendor_pixel_sampler_executed_in_this_study':False,
        'original_3d_lut_payload_used':False,
        'original_user_pixels_processed':False,
        'photographic_render_authorized':False,
        'automatic_wb_calibrated':False,
        'production_photon_changed':False,
        'main_missing_contracts_mask':255,
        'main_missing_contracts':['AWB calibration','phone sensor to ISP domain',
            'MAIN CCM pixel equation','MAIN gamma pixel equation',
            'MAIN LUT sampler oracle','MAIN stage order','output transfer/R2Y',
            'runtime mode controls'],
        'case_receipts':run_receipts,
    }
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('schema','status','prepared_synthetic_profile_cases',
           'synthetic_pixel_components_compared','max_pixel_absolute_difference',
           'total_independent_checks','photographic_render_authorized')}))

if __name__=='__main__':main()
