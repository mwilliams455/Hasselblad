#!/usr/bin/env python3
"""Independent synthetic RGB-plane write oracle; no vendor binary or DNG pixels."""
from pathlib import Path
import argparse
import ctypes as C
import json
import subprocess
import numpy as np
from test_schedule66 import Domain, Counts

HERE=Path(__file__).resolve().parent
PTR=C.c_void_p
PF=C.CFUNCTYPE(C.c_int,PTR,C.c_int,C.c_int)
GF=C.CFUNCTYPE(C.c_int,PTR,C.c_int,C.c_int,C.POINTER(C.c_uint16),C.POINTER(C.c_uint16))
OF=C.CFUNCTYPE(C.c_int32,PTR,C.c_int,C.c_int,C.c_int,C.c_uint16)
MF=C.CFUNCTYPE(C.c_int,PTR,C.c_int,C.c_int,C.POINTER(C.c_uint16))
BF=C.CFUNCTYPE(C.c_int,PTR,C.c_int,C.c_int,C.c_uint16,C.POINTER(C.c_uint16),C.POINTER(C.c_uint16))
class Planes(C.Structure):
    _fields_=[('domain',Domain),('raw',PTR),('red',PTR),('green',PTR),('blue',PTR),('mask',PTR)]
class Callbacks(C.Structure):
    _fields_=[('user',PTR),('prepare',PF),('estimate_green',GF),
              ('estimate_opposite_colour',OF),('compute_green_site_mask',MF),
              ('estimate_red_blue_green_site',BF)]
class Wires(C.Structure):
    _fields_=[('events',Counts)]+[(name,C.c_uint64) for name in (
      'green_red_calls','green_blue_calls','opposite_colour_calls',
      'opposite_zero_fallbacks','green_site_mask_calls','green_site_rb_calls','green_site_zero_fallbacks')]

def green_choice(raw,x,y):
    return (int(raw[y,x])+7)&0xffff, (0 if ((x+y)//2)%3==0 else 0x101)

def ref_run(raw,values,w,h):
    red,green,blue,mask=(v.copy() for v in values)
    green[...] = raw
    for y in range(4,h-4,2):
        for x in range(4,w-4,2):
            vg,vm=green_choice(raw,x,y)
            red[y,x]=raw[y,x];green[y,x]=vg;blue[y,x]=0;mask[y,x]=vm
            for yy,xx in ((y,x+1),(y+1,x)):
                red[yy,xx]=0;green[yy,xx]=raw[yy,xx];blue[yy,xx]=0
            vg,vm=green_choice(raw,x+1,y+1)
            red[y+1,x+1]=0;green[y+1,x+1]=vg
            blue[y+1,x+1]=raw[y+1,x+1];mask[y+1,x+1]=vm
    for y in range(6,h-6,2):
        for x in range(6,w-6,2):
            red_site,blue_site=(y,x),(y+1,x+1)
            blue[red_site]=1 if mask[red_site]!=0 else 0
            red[blue_site]=32769 if mask[blue_site]!=0 else 0
    for y in range(8,h-8,2):
        for x in range(8,w-8,2):
            for yy,xx in ((y,x+1),(y+1,x)):
                chosen_mask=0 if (xx+yy)%3==0 else 0x101
                mask[yy,xx]=chosen_mask
                red[yy,xx]=3000+xx if chosen_mask else 0
                blue[yy,xx]=7000+yy if chosen_mask else 0
    return red,green,blue,mask

def run(work,seed=6602,cases=28):
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    so=work/'libstage66_wiring.so'
    command=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
     '-fno-fast-math','-ffp-contract=off','-fPIC','-shared',
     str(HERE/'schedule66.c'),str(HERE/'wiring66.c'),'-o',str(so)]
    subprocess.run(command,check=True,capture_output=True)
    lib=C.CDLL(str(so));fn=lib.hb_wire_interpolate66
    fn.argtypes=[C.POINTER(Planes),C.POINTER(Callbacks),C.POINTER(Wires)];fn.restype=C.c_int
    rng=np.random.default_rng(seed)
    fixtures=[(24,24,24),(32,24,40),(32,32,43),(64,64,72),(80,88,96),(128,96,136)]
    fixtures += [(int(x),int(y),int(x+z)) for x,y,z in zip(
       rng.integers(3,14,cases)*8,rng.integers(3,14,cases)*8,rng.integers(0,16,cases))]
    tested_elements=0
    zero_gates=0;nonzero_gates=0;count_only_sites=0
    for w,h,stride in fixtures:
        raw=rng.integers(0,65536,(h,stride),dtype=np.uint16)
        arrays=[np.full((h,stride),v,dtype=np.uint16) for v in (111,222,333,444)]
        copies=[a.copy() for a in arrays]
        frozen_raw=raw.copy()
        preps=[]
        @PF
        def prep(user,ev,row):preps.append((ev,row));return 0
        @GF
        def green(user,x,y,out_green,out_mask):
            out_green[0],out_mask[0]=green_choice(raw,x,y);return 0
        @OF
        def opposite(user,x,y,is_red,mask):return -131071 if is_red else 32769
        @MF
        def green_mask(user,x,y,output):output[0]=0 if (x+y)%3==0 else 0x101;return 0
        @BF
        def rb(user,x,y,mask,out_r,out_b):out_r[0]=3000+x;out_b[0]=7000+y;return 0
        cb=Callbacks(None,prep,green,opposite,green_mask,rb)
        plane=Planes(Domain(w,h,stride,0xffff),raw.ctypes.data,*(a.ctypes.data for a in arrays))
        c=Wires()
        assert fn(C.byref(plane),C.byref(cb),C.byref(c))==0
        expected=ref_run(raw,copies,w,h)
        for name,a,b in zip(('red','green','blue','mask'),arrays,expected):
            assert np.array_equal(a,b), (name,w,h,stride,np.argwhere(a!=b)[:5])
            tested_elements+=a.size
        assert c.green_red_calls==c.green_blue_calls
        assert c.green_site_mask_calls==c.green_site_rb_calls+c.green_site_zero_fallbacks
        assert c.events.total_events==len(preps)+c.events.green_colour_estimates+\
            c.events.untouched_green_site_assignments+\
            c.events.blue_at_red_candidates+c.events.red_at_blue_candidates+\
            c.events.green_site_masks+c.events.red_blue_green_candidates+1
        assert np.array_equal(raw,frozen_raw)
        zero_gates+=c.opposite_zero_fallbacks+c.green_site_zero_fallbacks
        nonzero_gates+=c.opposite_colour_calls+c.green_site_rb_calls
        count_only_sites+=c.events.total_events
    assert zero_gates>0 and nonzero_gates>0
    return {'schema':'hasselblad-stage66-synthetic-pixel-plane-wiring-v1',
            'status':'PASS_EXACT_SYNTHETIC_PLANE_OWNERSHIP',
            'fixture_count':len(fixtures),'whole_plane_storage_elements_compared':tested_elements,
            'total_event_callbacks_executed':count_only_sites,
            'tested_zero_mask_fallback_sites':int(zero_gates),
            'tested_nonzero_mask_helper_sites':int(nonzero_gates),
            'source_images_private':False,'native_demosaic_executed':False,
            'pixel_values_from_mock_helpers_only':True,
            'original_CPU_RGB16_equivalence_established':False,
            'current_device_APK_changed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--cases',type=int,default=28)
    args=p.parse_args();assert 0<=args.cases<=256
    result=run(args.work,cases=args.cases)
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'fixture_count':result['fixture_count'],
                      'plane_elements_compared':result['whole_plane_storage_elements_compared']}))
if __name__=='__main__':main()
