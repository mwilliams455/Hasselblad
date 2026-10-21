#!/usr/bin/env python3
"""Independent 4/8-neighbour mask + synthetic candidate-accumulation oracle.
    This validates the OWNED bounded contract, not original scene weighting.
"""
import ctypes
import json
from pathlib import Path
import random
from test_frame_stats_python import Stats,LIB
from test_components_python import oracle
class CompStats(ctypes.Structure):
    _fields_=[('groups_removed',ctypes.c_uint16),('groups_kept',ctypes.c_uint16),
              ('blocks_removed',ctypes.c_uint16),('blocks_kept',ctypes.c_uint16)]
class Acc(ctypes.Structure):
    _fields_=[('weighted_site_sum_q16',ctypes.c_int64*4),
              ('weighted_site_count',ctypes.c_uint64*4),
              ('weighted_raw_brightness_q16',ctypes.c_int64),
              ('weighted_sample_count',ctypes.c_uint64),
              ('weighted_at_or_above_white_count',ctypes.c_uint64),
              ('surviving_blocks',ctypes.c_uint32),
              ('weighted_but_unclassified_blocks',ctypes.c_uint32),
              ('filter',CompStats),('vendor_candidate_equivalence_proven',ctypes.c_uint8)]
LIB.hb_awb_accumulate_owned_candidates.argtypes=[ctypes.POINTER(Stats),ctypes.POINTER(ctypes.c_uint8),
                     ctypes.POINTER(ctypes.c_uint8),ctypes.c_int,ctypes.POINTER(Acc)]
LIB.hb_awb_accumulate_owned_candidates.restype=ctypes.c_int
Array=ctypes.c_uint8*1024
rng=random.Random(0xCE202610)
cases=0
for adjacency in (4,8):
    for i in range(128):
        obj=Stats()
        weight=[rng.randrange(33) if rng.randrange(100)<rng.choice([1,3,5,12,35,75,99,100]) else 0 for _ in range(1024)]
        accepted=[rng.randrange(2) for _ in range(1024)]
        for b in obj.blocks:
            for col in range(4):
                b.site_sum_q16[col]=rng.randint(-500000,500000)
                b.site_count[col]=rng.randrange(30)
            b.raw_brightness_sum_q16=sum(b.site_sum_q16)
            b.sample_count=sum(b.site_count)
            b.at_or_above_white_count=rng.randrange(20)
        out=Acc()
        assert LIB.hb_awb_accumulate_owned_candidates(ctypes.byref(obj),Array(*weight),Array(*accepted),adjacency,ctypes.byref(out))==0
        filtered,counts=oracle(weight,adjacency)
        active=[(j,weight[j]) for j,v in enumerate(filtered) if v]
        expected_sums=[sum(int(obj.blocks[j].site_sum_q16[c])*w for j,w in active) for c in range(4)]
        expected_counts=[sum(int(obj.blocks[j].site_count[c])*w for j,w in active) for c in range(4)]
        assert list(out.weighted_site_sum_q16)==expected_sums
        assert list(out.weighted_site_count)==expected_counts
        assert out.weighted_raw_brightness_q16==sum(int(obj.blocks[j].raw_brightness_sum_q16)*w for j,w in active)
        assert out.weighted_sample_count==sum(int(obj.blocks[j].sample_count)*w for j,w in active)
        assert out.weighted_at_or_above_white_count==sum(int(obj.blocks[j].at_or_above_white_count)*w for j,w in active)
        assert out.surviving_blocks==len(active)
        assert out.weighted_but_unclassified_blocks==sum(accepted[j]==0 for j,w in active)
        assert (out.filter.groups_removed,out.filter.groups_kept,out.filter.blocks_removed,out.filter.blocks_kept)==counts
        assert not out.vendor_candidate_equivalence_proven
        cases+=1
print(json.dumps({'result':'PASS','owned_candidate_oracle_cases':cases,'topologies':[4,8],
  'oracle':'independent Python BFS and integer candidate sums, not original vendor AWB',
  'vendor_verified':False}))