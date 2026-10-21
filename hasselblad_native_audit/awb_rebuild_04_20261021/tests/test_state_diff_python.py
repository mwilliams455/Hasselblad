#!/usr/bin/env python3
"""Independent Python array oracle for same-execution byte comparisons.
Synthetic arrays only; does not assert that vendor state was available.
"""
import ctypes as C
import json
import random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIB=C.CDLL(str(ROOT/'build/libhbstages.so'))
C_BYTES=920560
H_BYTES=1000
class Diff(C.Structure):
    _fields_=[('context_differences',C.c_uint64),('reawb_differences',C.c_uint64),
              ('context_first_mismatch',C.c_uint32),('reawb_first_mismatch',C.c_uint32),
              ('original_return_status',C.c_int32),('owned_return_status',C.c_int32),
              ('all_bytes_and_status_equal',C.c_uint8),('original_reference_proven',C.c_uint8)]
A=C.c_uint8*C_BYTES
H=C.c_uint8*H_BYTES
LIB.hb_awb_compare_state_snapshots.argtypes=[C.POINTER(C.c_uint8),C.c_size_t,
    C.POINTER(C.c_uint8),C.c_size_t,C.POINTER(C.c_uint8),C.c_size_t,
    C.POINTER(C.c_uint8),C.c_size_t,C.c_int32,C.c_int32,C.POINTER(Diff)]
LIB.hb_awb_compare_state_snapshots.restype=C.c_int
rng=random.Random(142002)
cases=0
for i in range(80):
    c0=A();c1=A();h0=H();h1=H()
    chg_c=set(rng.sample(range(C_BYTES),rng.randrange(0,15)))
    chg_h=set(rng.sample(range(H_BYTES),rng.randrange(0,15)))
    for idx in chg_c:c1[idx]=rng.randrange(1,256)
    for idx in chg_h:h1[idx]=rng.randrange(1,256)
    os,ns=(0,1) if i%7==0 else (151,151)
    out=Diff()
    ok=LIB.hb_awb_compare_state_snapshots(c0,C_BYTES,c1,C_BYTES,h0,H_BYTES,h1,H_BYTES,os,ns,C.byref(out))
    assert ok==0
    assert out.context_differences==len(chg_c)
    assert out.reawb_differences==len(chg_h)
    assert out.context_first_mismatch==(min(chg_c) if chg_c else (1<<32)-1)
    assert out.reawb_first_mismatch==(min(chg_h) if chg_h else (1<<32)-1)
    assert bool(out.all_bytes_and_status_equal)==(not chg_c and not chg_h and os==ns)
    assert out.original_reference_proven==0
    cases+=1
print(json.dumps({'status':'PASS','independent_state_comparator_cases':cases,
    'original_firmware_compared':False,'state_bytes':C_BYTES,'reawb_bytes':H_BYTES}))