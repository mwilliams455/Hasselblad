#!/usr/bin/env python3
"""Stage10: bounded competing packed-3D-LUT hypotheses; NO MAIN pixel oracle.

This is a synthetic study (not a photographic colour renderer). It demonstrates
how a captured MAIN ISP pixel output would distinguish multiple 6144-word layout
and interpolation contracts. The only native pixel oracle used here is the
independent Stage9 DISPLAY-library fixture. MAIN_3DLUT remains unverified.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import math
import struct
import subprocess
import tempfile
from pathlib import Path

WIDTH=16
WORDS=6144
NODES=WIDTH**3
STEPS=15
MODELS=("display_planar_b_fast_trilinear", "node_interleaved_rgb_trilinear",
        "display_planar_r_fast_trilinear", "display_planar_bgr_banks_trilinear",
        "display_planar_b_fast_tetrahedral")
PROBES=[
 (0.,0.,0.),(1.,1.,1.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.),
 (1.,1.,0.),(1.,0.,1.),(0.,1.,1.),
 (1/15,7/15,14/15),(14/15,2/15,1/15),
 (.123,.456,.789),(.876,.234,.567),(.5,.5,.5),
 (.999999999,.999999997,.999999991),(.000000001,.000000003,.000000009),
 (.067,.134,.201),(.934,.867,.799),(1.,.345,.678),
 (.123,1.,.789),(.123,.456,1.),
 (.283,.371,.659),(.412,.574,.763),(.619,.255,.934),
 (.333,.667,.125),(.711,.881,.292),(.135,.555,.845),
 (.765,.221,.515),(.975,.415,.235),(.245,.915,.725),
 (.538,.622,.482),(.887,.123,.369),(.123,.887,.369)
]

def synthetic_fixture()->list[int]:
    # Unique pseudo-random 12-bit lane values and nonzero reserved high nibbles.
    # Deterministic local bytes, NOT a Hasselblad camera tuning table.
    state=0x13579BDF
    out=[]
    for _ in range(WORDS):
        state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
        lo=state & 4095
        state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
        hi=state & 4095
        out.append(0xA0005000 | (hi<<16) | lo)
    return out

def get_lane(words:list[int], index:int)->float:
    if index<0 or index>=WORDS*2:raise ValueError('bad_halfword_index')
    return ((words[index//2]>>(16*(index&1)))&4095)/4095.

def node(words:list[int],r:int,g:int,b:int,layout:str)->tuple[float,float,float]:
    if not (0<=r<16 and 0<=g<16 and 0<=b<16):raise ValueError('out_of_domain')
    if len(words)!=WORDS:raise ValueError('bad_table_size')
    if layout=='node_interleaved_rgb_trilinear':
        base=((r*16+g)*16+b)*3
        return tuple(get_lane(words,base+c) for c in range(3))
    if layout=='display_planar_r_fast_trilinear':
        q=128*b+8*g+r//2;sh=(r&1)*16
    else:
        q=128*r+8*g+b//2;sh=(b&1)*16
    if layout=='display_planar_bgr_banks_trilinear':
        banks=(2,1,0)
    else:banks=(0,1,2)
    return tuple(((words[q+2048*bank]>>sh)&4095)/4095. for bank in banks)

def validate_pos(pos):
    if len(pos)!=3 or not all(math.isfinite(v) and 0.<=v<=1. for v in pos):
        raise ValueError('invalid_normalized_RGB')

def sample(words:list[int],pos:tuple[float,float,float],model:str)->tuple[float,float,float]:
    if model not in MODELS:raise ValueError('unknown_model')
    validate_pos(pos)
    a=[c*STEPS for c in pos];lo=[math.floor(v) for v in a]
    hi=[min(v+1,15) for v in lo]; frac=[a[i]-lo[i] for i in range(3)]
    base='display_planar_b_fast_trilinear' if model=='display_planar_b_fast_tetrahedral' else model
    if model=='display_planar_b_fast_tetrahedral':
        order=sorted(range(3), key=lambda i:(-frac[i],i))
        start=list(lo)
        c0=node(words,*start,base)
        points=[c0]
        for dim in order:
            start[dim]=hi[dim]
            points.append(node(words,*start,base))
        result=[points[0][j]+sum(frac[order[k]]*(points[k+1][j]-points[k][j]) for k in range(3)) for j in range(3)]
        return tuple(result)
    out=[0.,0.,0.]
    for rr in (0,1):
        for gg in (0,1):
            for bb in (0,1):
                w=(frac[0] if rr else 1-frac[0])*(frac[1] if gg else 1-frac[1])*(frac[2] if bb else 1-frac[2])
                q=node(words,hi[0] if rr else lo[0],hi[1] if gg else lo[1],hi[2] if bb else lo[2],base)
                for j in range(3):out[j]+=w*q[j]
    return tuple(out)

def check_against_stage9_c(words:list[int],st9_c:Path):
    if not st9_c.is_file():raise FileNotFoundError(f'Stage9 source missing: {st9_c}')
    with tempfile.TemporaryDirectory(prefix='hb-stage10-c-') as tmp:
        so=Path(tmp)/'libstage9c.so'
        subprocess.run(['cc','-std=c11','-O2','-ffp-contract=off','-Wall','-Wextra','-Werror','-fPIC','-shared',str(st9_c),'-lm','-o',str(so)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        dll=ctypes.CDLL(str(so))
        pointer=ctypes.POINTER(ctypes.c_uint32)
        dbl=ctypes.POINTER(ctypes.c_double)
        dll.hb_display_lut16_node.argtypes=[pointer,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,dbl]
        dll.hb_display_lut16_node.restype=ctypes.c_int
        dll.hb_display_lut16_trilinear.argtypes=[pointer,ctypes.c_size_t,dbl,dbl]
        dll.hb_display_lut16_trilinear.restype=ctypes.c_int
        fixture=(ctypes.c_uint32*WORDS)(*words)
        original=bytes(fixture)
        max_node=0.;max_sample=0.
        for r in range(16):
            for g in range(16):
                for b in range(16):
                    out=(ctypes.c_double*3)()
                    assert dll.hb_display_lut16_node(fixture,WORDS,r,g,b,out)==0
                    expected=node(words,r,g,b,MODELS[0])
                    max_node=max(max_node,max(abs(expected[j]-out[j]) for j in range(3)))
        for p in PROBES:
            input_c=(ctypes.c_double*3)(*p)
            output=(ctypes.c_double*3)()
            assert dll.hb_display_lut16_trilinear(fixture,WORDS,input_c,output)==0
            expect=sample(words,p,MODELS[0])
            max_sample=max(max_sample,max(abs(expect[j]-output[j]) for j in range(3)))
        assert bytes(fixture)==original
        assert max_node==0 and max_sample<2e-15,(max_node,max_sample)
        return {'status':'PASS','display_node_components_compared':NODES*3,
                'display_trilinear_components_compared':len(PROBES)*3,
                'max_abs_node_residual':max_node,'max_abs_sample_residual':max_sample,
                'existing_stage9_source_sha256':hashlib.sha256(st9_c.read_bytes()).hexdigest()}

def selftest():
    w=synthetic_fixture()
    assert len(w)==WORDS and len(PROBES)==32
    assert all(0<=x<=0xffffffff for x in w)
    assert len(set(MODELS))==len(MODELS)
    assert node(w,0,0,0,MODELS[0])!=node(w,0,0,0,MODELS[1])
    assert sample(w,(1.,1.,1.),MODELS[0])==node(w,15,15,15,MODELS[0])
    for bad in [(-0.001,0,0),(1.0001,0,0),(float('nan'),0,0),(float('inf'),0,0)]:
        try:sample(w,bad,MODELS[0])
        except ValueError:pass
        else:raise AssertionError('invalid_normalized_RGB_accepted')
    print('PASS 32 fixed probes, five independent candidate contracts, rejected invalid inputs')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--stage9-source',type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.self_test:selftest();return
    if not args.stage9_source or not args.output:ap.error('--stage9-source and --output required')
    selftest()
    words=synthetic_fixture()
    portable=check_against_stage9_c(words,args.stage9_source)
    answers={m:[sample(words,p,m) for p in PROBES] for m in MODELS}
    baseline=MODELS[0]
    candidate_differences={}
    for m in MODELS[1:]:
        discrepancies=[max(abs(a-b) for a,b in zip(x,y)) for x,y in zip(answers[baseline],answers[m])]
        candidate_differences[m]={
            'probes_distinguishing_at_1_lsb':sum(d>1/4095. for d in discrepancies),
            'probes_total':len(PROBES),
            'max_normalized_difference':max(discrepancies),
            'median_normalized_difference':sorted(discrepancies)[len(discrepancies)//2]
        }
    assert all(d['probes_distinguishing_at_1_lsb']>0 for d in candidate_differences.values())
    chosen=[];remaining=set(range(len(PROBES)))
    # Greedy basis: maximize minimum pairwise contrast among the five models.
    for _ in range(8):
        scores=[]
        for i in remaining:
            cands=[answers[m][i] for m in MODELS]
            gaps=[max(abs(a-b) for a,b in zip(cands[u],cands[v])) for u in range(len(MODELS)) for v in range(u+1,len(MODELS))]
            scores.append((min(gaps),i))
        score,best=max(scores)
        chosen.append({'index':best,'input_RGB':list(PROBES[best]),'min_pairwise_model_delta':score,
                       'predictions':{m:[round(v,9) for v in answers[m][best]] for m in MODELS}})
        remaining.remove(best)
    fixture=struct.pack('<6144I',*words)
    result={
        'schema':'hasselblad-stage10-main-pixel-contract-discrimination-v1',
        'status':'PASS','device_MAIN_pixel_oracle_available':False,
        'photographic_MAIN_3DLUT_compatible_with_DISPLAY_proven':False,
        'hypotheses_are_not_vendor_implementations':True,
        'observed_vendor_facts':{'MAIN_words':6144,'MAIN_profile_prep_axes':['cc_color_temp','color_gamut'],
           'DISPLAY_words':6144,'DISPLAY_verified_cubic_grid_size':16,'DISPLAY_verified_trilinear_subset':True},
        'research_stage9_portable_parity':portable,
        'synthetic_fixture_sha256':hashlib.sha256(fixture).hexdigest(),
        'fixture_contains_user_photo_or_vendor_table':False,
        'alternative_models':list(MODELS),
        'probe_count':len(PROBES),
        'discriminating_probes':chosen,
        'baseline_vs_alternative_differences':candidate_differences,
        'acceptance_gate':'Controlled original MAIN pixel outputs with specified register state, input numeric basis and known submitted synthetic table. Until then no MAIN format or photographic colour decision.',
        'render_applied':False,'pixel_colour_pipeline_modified':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'stage9_portable':portable,'candidate_differences':candidate_differences,
                      'report':str(args.output)},indent=2))

if __name__=='__main__':main()
