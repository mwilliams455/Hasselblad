#!/usr/bin/env python3
"""Independent Python reference for FNV field layout + observed caller handoff.
No proprietary implementation or numerical scene optimizer is asserted.
"""
from __future__ import annotations
import ctypes as C
import json
import random
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIB=C.CDLL(str(ROOT/'build/libhbstages.so'))
class Filter(C.Structure):
    _fields_=[('groups_removed',C.c_uint16),('groups_kept',C.c_uint16),
              ('blocks_removed',C.c_uint16),('blocks_kept',C.c_uint16)]
class Acc(C.Structure):
    _fields_=[('weighted_site_sum_q16',C.c_int64*4),('weighted_site_count',C.c_uint64*4),
              ('weighted_raw_brightness_q16',C.c_int64),('weighted_sample_count',C.c_uint64),
              ('weighted_at_or_above_white_count',C.c_uint64),('surviving_blocks',C.c_uint32),
              ('weighted_but_unclassified_blocks',C.c_uint32),('filter',Filter),
              ('vendor_candidate_equivalence_proven',C.c_uint8)]
class Trace(C.Structure):
    _fields_=[('revision',C.c_uint32),('frame_serial',C.c_uint64),
              ('expected_accumulation_fingerprint',C.c_uint64),('observed_optimizer_status',C.c_int32),
              ('observed_caller_delta_candidates',C.c_uint32),('observed_caller_delta_blocks',C.c_uint32),
              ('observed_caller_delta_samples',C.c_uint64),('caller_window_observed',C.c_uint8),
              ('opaque_result',C.c_uint8*32)]
class Staged(C.Structure):
    _fields_=[('frame_serial',C.c_uint64),('input_fingerprint',C.c_uint64),
              ('observed_optimizer_status',C.c_int32),('caller_delta_candidates',C.c_uint32),
              ('caller_delta_blocks',C.c_uint32),('caller_delta_samples',C.c_uint64),
              ('opaque_result',C.c_uint8*32),('original_firmware_equivalence_proven',C.c_uint8),
              ('selected_neutral_produced',C.c_uint8)]
class Caller(C.Structure):
    _fields_=[('last_applied_frame_serial',C.c_uint64),('candidate_count',C.c_uint64),
              ('consumed_block_count',C.c_uint64),('consumed_sample_count',C.c_uint64),
              ('last_optimizer_status',C.c_int32),('opaque_last_result',C.c_uint8*32),
              ('selected_neutral_produced',C.c_uint8)]
LIB.hb_awb_accumulation_fingerprint.argtypes=[C.POINTER(Acc)]
LIB.hb_awb_accumulation_fingerprint.restype=C.c_uint64
LIB.hb_awb_optimizer_stage_observation.argtypes=[C.POINTER(Acc),C.POINTER(Trace),C.POINTER(Staged)]
LIB.hb_awb_optimizer_stage_observation.restype=C.c_int
LIB.hb_awb_optimizer_apply_observed_caller_update.argtypes=[C.POINTER(Staged),C.POINTER(Caller)]
LIB.hb_awb_optimizer_apply_observed_caller_update.restype=C.c_int
MASK=(1<<64)-1

def oracle(a:Acc)->int:
    v=14695981039346656037
    fields=[]
    for j in range(4):fields.extend((int(a.weighted_site_sum_q16[j]),int(a.weighted_site_count[j])))
    fields.extend([a.weighted_raw_brightness_q16,a.weighted_sample_count,
                   a.weighted_at_or_above_white_count,a.surviving_blocks,
                   a.weighted_but_unclassified_blocks,
                   a.filter.groups_removed,a.filter.groups_kept,
                   a.filter.blocks_removed,a.filter.blocks_kept])
    for f in fields:
        for c in (int(f)&MASK).to_bytes(8,'little',signed=False):
            v=((v^c)*1099511628211)&MASK
    return v

rng=random.Random(20261021)
s=Caller()
cases=0
for serial in range(1,2049):
    a=Acc()
    for j in range(4):
        a.weighted_site_sum_q16[j]=rng.randint(-(1<<55),(1<<55))
        a.weighted_site_count[j]=rng.randrange(1,1<<33)
    a.weighted_raw_brightness_q16=rng.randint(-(1<<53),(1<<53))
    a.weighted_sample_count=rng.randrange(1,1<<33)
    a.weighted_at_or_above_white_count=rng.randrange(0,1<<20)
    a.surviving_blocks=rng.randrange(1,1025)
    a.weighted_but_unclassified_blocks=rng.randrange(a.surviving_blocks+1)
    a.filter.blocks_kept=a.surviving_blocks
    a.filter.blocks_removed=rng.randrange(1025-a.surviving_blocks)
    a.filter.groups_kept=1
    got=LIB.hb_awb_accumulation_fingerprint(C.byref(a))
    assert got==oracle(a),(serial,got,oracle(a))
    t=Trace(revision=1,frame_serial=serial,expected_accumulation_fingerprint=got,
            observed_optimizer_status=rng.choice((0,0,40,151,-7)),
            observed_caller_delta_candidates=rng.randrange(6),
            observed_caller_delta_blocks=rng.randrange(50),
            observed_caller_delta_samples=rng.randrange(10000),caller_window_observed=1)
    for j in range(32):t.opaque_result[j]=rng.randrange(256)
    staged=Staged()
    assert LIB.hb_awb_optimizer_stage_observation(C.byref(a),C.byref(t),C.byref(staged))==0
    old=(s.candidate_count,s.consumed_block_count,s.consumed_sample_count)
    assert LIB.hb_awb_optimizer_apply_observed_caller_update(C.byref(staged),C.byref(s))==0
    assert (s.candidate_count,s.consumed_block_count,s.consumed_sample_count)==tuple(
        x+y for x,y in zip(old,(t.observed_caller_delta_candidates,t.observed_caller_delta_blocks,
                                t.observed_caller_delta_samples)))
    assert s.last_applied_frame_serial==serial and s.last_optimizer_status==t.observed_optimizer_status
    assert bytes(s.opaque_last_result)==bytes(t.opaque_result)
    assert staged.selected_neutral_produced==0 and staged.original_firmware_equivalence_proven==0
    assert LIB.hb_awb_optimizer_apply_observed_caller_update(C.byref(staged),C.byref(s))==-1
    if serial%127==0:
        a.weighted_site_sum_q16[0]+=1
        assert LIB.hb_awb_optimizer_stage_observation(C.byref(a),C.byref(t),C.byref(staged))==-2
    cases+=1
print(json.dumps({'status':'PASS','python_independent_replay_cases':cases,
    'oracle':'field-by-field big integer FNV + two-phase accumulator arithmetic',
    'original_firmware_compared':False,'original_awb_optimizer_reconstructed':False}))