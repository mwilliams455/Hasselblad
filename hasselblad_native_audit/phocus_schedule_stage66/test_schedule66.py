#!/usr/bin/env python3
"""Independent Python position/order oracle for the bounded C11 CPU scheduler.

No camera RAW, proprietary library or vendor disassembly is loaded.
Pixel interpolation is deliberately delegated to future native-verified C.
"""
import argparse
import ctypes as C
from itertools import product
from pathlib import Path
import json
import random
import subprocess

HERE=Path(__file__).resolve().parent
class Domain(C.Structure):
    _fields_=[('width',C.c_int),('height',C.c_int),('stride',C.c_int),('flags',C.c_uint16)]
COUNT_NAMES=('smooth_rows','edge_rows','scale_calls','midgreen_calls','copy_raw_codes',
             'green_colour_estimates','untouched_green_site_assignments',
             'blue_at_red_candidates','red_at_blue_candidates','green_site_masks',
             'red_blue_green_candidates','total_events')
class Counts(C.Structure):
    _fields_=[(name,C.c_uint64) for name in COUNT_NAMES]
CALLBACK=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_int,C.c_int,C.c_int)

def oracle(w,h):
    """Mathematical Cartesian reference instead of translating the C loops."""
    events=[]
    events.extend((1,0,y) for y in range(1,h-1))
    events.extend((2,0,y) for y in range(2,h-2))
    events.extend(((3,2,2),(4,2,2),(5,0,0)))
    for y,x in product(range(4,h-4,2),range(4,w-4,2)):
        events.extend(((6,x,y),(7,x+1,y),(8,x,y+1),(9,x+1,y+1)))
    for y,x in product(range(6,h-6,2),range(6,w-6,2)):
        events.extend(((10,x,y),(11,x+1,y+1)))
    for y,x in product(range(8,h-8,2),range(8,w-8,2)):
        events.extend(((12,x+1,y),(13,x+1,y),(14,x,y+1),(15,x,y+1)))
    return events

def counts_of(events,stride,height):
    seq=[0]*16
    for i,x,y in events:seq[i]+=1
    return {
     'smooth_rows':seq[1], 'edge_rows':seq[2],
     'scale_calls':seq[3],'midgreen_calls':seq[4],
     'copy_raw_codes':stride*height,
     'green_colour_estimates':seq[6]+seq[9],
     'untouched_green_site_assignments':seq[7]+seq[8],
     'blue_at_red_candidates':seq[10], 'red_at_blue_candidates':seq[11],
     'green_site_masks':seq[12]+seq[14],
     'red_blue_green_candidates':seq[13]+seq[15],
     'total_events':len(events)}

def build(out,compiler='gcc',sanitize=False):
    cmd=[compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-fno-fast-math',
         '-ffp-contract=off','-fPIC','-shared',str(HERE/'schedule66.c'),'-o',str(out)]
    if sanitize:cmd[1:1]=['-fsanitize=undefined','-fno-sanitize-recover=all']
    subprocess.run(cmd,check=True,capture_output=True)

def verify(work,cases=40,seed=6601):
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    so=work/'libstage66_schedule.so'
    build(so)
    lib=C.CDLL(str(so));fn=lib.hb_schedule66
    fn.argtypes=[Domain,C.c_void_p,C.c_void_p,C.POINTER(Counts)];fn.restype=C.c_int
    rng=random.Random(seed)
    targets=[(24,24,24),(24,32,37),(32,24,41),(32,32,48),
             (64,64,68),(80,88,104),(96,96,104),(128,96,142)]
    targets.extend((8*rng.randint(3,14),8*rng.randint(3,14),0) for _ in range(cases))
    compared_events=0; max_events=0; differing_strides=0
    for w,h,stride in targets:
        stride=stride or w+rng.randint(0,17)
        differing_strides+=stride>w
        ref=oracle(w,h)
        recorded=[]
        def cb(user,event,x,y):recorded.append((event,x,y));return 0
        handler=CALLBACK(cb)
        native=Counts()
        assert fn(Domain(w,h,stride,0xffff),handler,None,C.byref(native))==0
        assert recorded==ref, (w,h,stride,'event sequence mismatch',len(recorded),len(ref))
        expected=counts_of(ref,stride,h)
        assert {n:getattr(native,n) for n in COUNT_NAMES}==expected,(w,h,'count mismatch')
        count_only=Counts()
        assert fn(Domain(w,h,stride,0xffff),None,None,C.byref(count_only))==0
        assert {n:getattr(count_only,n) for n in COUNT_NAMES}==expected,(w,h,'count-only mismatch')
        compared_events+=len(ref);max_events=max(max_events,len(ref))
    fail_calls=[]
    @CALLBACK
    def should_not_call(user,event,x,y):fail_calls.append(event);return 0
    for flags in (0,1,2,8,16,32,64,0x60,0xfffe,0x00ff):
        count=Counts()
        assert fn(Domain(32,32,40,flags),should_not_call,None,C.byref(count))==-2
    for invalid in (Domain(24,23,24,0xffff),Domain(23,24,24,0xffff),
                    Domain(8,8,8,0xffff),Domain(31,32,32,0xffff),
                    Domain(32,32,31,0xffff),Domain(-1,32,32,0xffff)):
        count=Counts();assert fn(invalid,should_not_call,None,C.byref(count)) in (-1,-2)
    assert not fail_calls
    # No image is created or rendered by this operation; just a checked
    # mathematical count for an aligned approximately-12MP input domain.
    full=Counts()
    assert fn(Domain(4096,3072,4096,0xffff),None,None,C.byref(full))==0
    return {'schema':'hasselblad-stage66-bounded-scheduler-host-v1',
            'status':'PASS_HOST_SCHEDULE_EXACT',
            'supported_configuration':'aligned_RGGB_scalar_cpu_0xffff_padded_working_domain',
            'synthetic_domain_cases':len(targets),
            'event_sequence_exact_comparisons':compared_events,
            'max_events_per_fixture':max_events,
            'different_stride_cases':differing_strides,
            'negative_contract_cases':16,
            'all_event_positions_and_order_exact':True,
            'count_only_parity_exact':True,
            'full_size_4096x3072_event_count_only':int(full.total_events),
            'full_size_pixel_values_computed':False,
            'original_ARM64_executed':False,
            'original_CPU_pixel_equivalence_established':False,
            'full_independent_pixel_loop_completed':False,
            'source_uses_private_values':False,
            'new_APK_built':False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--cases',type=int,default=40)
    a=p.parse_args();assert 0<=a.cases<=512
    result=verify(a.work,a.cases)
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'synthetic_domain_cases':result['synthetic_domain_cases'],
                      'exact_events':result['event_sequence_exact_comparisons']}))
if __name__=='__main__':main()
