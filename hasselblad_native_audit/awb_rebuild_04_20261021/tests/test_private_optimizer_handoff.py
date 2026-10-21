#!/usr/bin/env python3
"""Local-only real DNG -> 1024 stats -> owned calibrated scene ->
 optimizer CALL/AFTER-CALL trace boundary. The observed caller deltas below
 are synthetic TEST FIXTURES, not measured Hasselblad optimizer outputs.
 No original vendor file, RAW pixels or DNG is serialized in output.
"""
from __future__ import annotations
import argparse
import ctypes as C
import json
from pathlib import Path
import test_scene_prepare_python as scene

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

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--private-dng',required=True)
p.add_argument('--report')
a=p.parse_args()
report,acc=scene.private_dng_replay(a.private_dng,return_accumulation=True)
scene.LIB.hb_awb_accumulation_fingerprint.argtypes=[C.POINTER(scene.Acc)]
scene.LIB.hb_awb_accumulation_fingerprint.restype=C.c_uint64
scene.LIB.hb_awb_optimizer_stage_observation.argtypes=[C.POINTER(scene.Acc),C.POINTER(Trace),C.POINTER(Staged)]
scene.LIB.hb_awb_optimizer_stage_observation.restype=C.c_int
scene.LIB.hb_awb_optimizer_apply_observed_caller_update.argtypes=[C.POINTER(Staged),C.POINTER(Caller)]
scene.LIB.hb_awb_optimizer_apply_observed_caller_update.restype=C.c_int
fingerprint=scene.LIB.hb_awb_accumulation_fingerprint(C.byref(acc))
assert acc.surviving_blocks>0 and acc.weighted_sample_count>0
trace=Trace(revision=1,frame_serial=124,
           expected_accumulation_fingerprint=fingerprint,observed_optimizer_status=0,
           observed_caller_delta_candidates=1,
           observed_caller_delta_blocks=acc.surviving_blocks,
           observed_caller_delta_samples=acc.weighted_sample_count,
           caller_window_observed=1)
staged=Staged();caller=Caller()
assert scene.LIB.hb_awb_optimizer_stage_observation(C.byref(acc),C.byref(trace),C.byref(staged))==0
assert caller.candidate_count==0 and caller.last_applied_frame_serial==0
assert scene.LIB.hb_awb_optimizer_apply_observed_caller_update(C.byref(staged),C.byref(caller))==0
assert caller.candidate_count==1 and caller.consumed_block_count==acc.surviving_blocks
assert caller.consumed_sample_count==acc.weighted_sample_count
assert caller.last_applied_frame_serial==124
assert scene.LIB.hb_awb_optimizer_apply_observed_caller_update(C.byref(staged),C.byref(caller))!=0
assert staged.original_firmware_equivalence_proven==0 and staged.selected_neutral_produced==0
report.update({'phase':'owned RAW->stat->calibration->candidate->optimizer-trace replay',
    'candidate_survivors':acc.surviving_blocks,'trace_frame_serial':124,
    'caller_deltas_are_synthetic_test_fixtures':True,
    'optimizer_input_fingerprint_match':True,
    'caller_updates_applied_after_observed_return':True,
    'double_update_rejected':True,'actual_original_vendor_trace_present':False,
    'actual_original_optimizer_reconstructed':False,
    'original_firmware_equivalence_proven':False})
if a.report:Path(a.report).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'PASS',**report}))