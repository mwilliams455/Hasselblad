#!/usr/bin/env python3
"""Independent simulation of recorded copy/status clauses on synthetic frames.
No original firmware invoked. Check 920560+1000 bytes and recovery provenance.
"""
import ctypes as C, random
from pathlib import Path
LIB=C.CDLL(str(Path(__file__).resolve().parents[1]/'build/libhbstages.so'))
CB, HB=920560,1000
CLEAR,REQ,REFERENCE=0x174,0xd338,0xd3d8
LIVE_A,LIVE_B,CONF_A,CONF_B=0xb0c48,0xb0ce4,0xb0d80,0xb0e1c
class Journal(C.Structure):
    _fields_=[('revision',C.c_uint32),('last_frame_serial',C.c_uint64),('processed_frames',C.c_uint64),('live_publications',C.c_uint64),('confirmed_restorations',C.c_uint64),('reference_overrides',C.c_uint64),('outer_returns_success',C.c_uint64),('inner_returns_error',C.c_uint64),('original_scene_estimate_verified',C.c_uint8)]
class Result(C.Structure):
    _fields_=[('frame_serial',C.c_uint64),('inner_status',C.c_int),('outer_status',C.c_int),('result_origin',C.c_int),('result_restored_or_overridden',C.c_uint8),('outer_success',C.c_uint8),('fresh_vendor_estimate_proven',C.c_uint8),('passive_reawb_preserved',C.c_uint8)]
B=C.c_uint8*CB
H=C.c_uint8*HB
LIB.hb_awb_lifecycle_advance.argtypes=[C.POINTER(Journal),C.c_uint64,C.POINTER(C.c_uint8),C.c_size_t,C.POINTER(C.c_uint8),C.c_size_t,C.c_int,C.c_int,C.POINTER(Result)]
LIB.hb_awb_lifecycle_advance.restype=C.c_int
rng=random.Random(432001)
j=Journal();j.revision=1
counts={1:0,2:0,3:0};success=0;inner_errors=0
for k in range(144):
    # Avoid Python 144*920560 random byte loop: zeroed other regions are valid
    # synthetic context; randomized source/destination bytes still independent.
    expected=bytearray(CB)
    for addr in [LIVE_A,LIVE_B,CONF_A,CONF_B,REFERENCE]:
        expected[addr:addr+156]=rng.randbytes(156)
    expected[CLEAR:CLEAR+4]=rng.randbytes(4)
    req=[0,0,0,1,2][k%5]
    expected[REQ]=req
    before=bytes(expected)
    arr=B.from_buffer_copy(before)
    passive=H.from_buffer_copy(rng.randbytes(HB))
    passive_before=bytes(passive)
    inner=[0,151,40,-37][k%4]
    final=[0,0,0,9][k%4]
    output=Result(); serial=k+1
    assert LIB.hb_awb_lifecycle_advance(C.byref(j),serial,arr,CB,passive,HB,inner,final,C.byref(output))==0
    expected[CLEAR:CLEAR+4]=b'\0'*4
    if req==1:
        val=expected[REFERENCE:REFERENCE+156]
        for a in [LIVE_A,LIVE_B,CONF_A,CONF_B]:expected[a:a+156]=val
        expected[REQ]=0; origin=3
    elif inner:
        expected[LIVE_A:LIVE_A+156]=expected[CONF_A:CONF_A+156]
        expected[LIVE_B:LIVE_B+156]=expected[CONF_B:CONF_B+156]
        origin=2
    else:
        expected[CONF_A:CONF_A+156]=expected[LIVE_A:LIVE_A+156]
        expected[CONF_B:CONF_B+156]=expected[LIVE_B:LIVE_B+156]
        origin=1
    assert bytes(arr)==bytes(expected)
    assert bytes(passive)==passive_before
    assert (output.result_origin,output.inner_status,output.outer_status)==(origin,inner,final)
    assert output.outer_success==(final==0)
    assert output.fresh_vendor_estimate_proven==0
    counts[origin]+=1;success+=final==0;inner_errors+=inner!=0
assert j.processed_frames==144
assert j.live_publications==counts[1]
assert j.confirmed_restorations==counts[2]
assert j.reference_overrides==counts[3]
assert j.outer_returns_success==success
assert j.inner_returns_error==inner_errors
print('INDEPENDENT LIFECYCLE PASS 144 full-context synthetic frames; vendor_freshness=NOT_PROVEN')