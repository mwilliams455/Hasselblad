#!/usr/bin/env python3
"""Independent CPython arbitrary-precision oracle for bounded owned stage03.

The checked equations are CONTRACT DEFINITIONS, not vendor firmware AWB.
An optional private DNG test validates that this code can consume the saved
Native1C capture without embedding pixels, unredacted sidecars or calibrations.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import sys

from test_frame_stats_python import Stats, Frame, check, LIB
from test_components_python import oracle as component_oracle
from test_accumulation_python import CompStats, Acc

N=1024
class Calibration(ctypes.Structure):
    _fields_=[('channel_gain_q16',ctypes.c_uint32*4),
              ('channel_bias_q16',ctypes.c_int64*4),
              ('spatial_gain_q16',ctypes.POINTER(ctypes.c_uint32))]
class AE(ctypes.Structure):
    _fields_=[('raw_block_mean_q16',ctypes.c_int64*N),
              ('at_or_above_white_ppm',ctypes.c_uint32*N),
              ('at_or_below_black_ppm',ctypes.c_uint32*N),
              ('total_raw_sum_q16',ctypes.c_int64),
              ('total_samples',ctypes.c_uint64),
              ('total_at_or_above_white',ctypes.c_uint64),
              ('total_at_or_below_black',ctypes.c_uint64),
              ('frame_raw_mean_q16',ctypes.c_int64),
              ('vendor_ae_equivalence_proven',ctypes.c_uint8)]
class Masks(ctypes.Structure):
    _fields_=[('classifier_accepted',ctypes.c_uint8*N),
              ('zone_override',ctypes.c_uint8*N),
              ('final_weight',ctypes.c_uint8*N),
              ('neighbours',ctypes.c_int)]
class Scene(ctypes.Structure):
    _fields_=[('calibrated',Stats),('ae',AE),('accumulation',Acc),
              ('weighted_from_zone_not_classifier',ctypes.c_uint32),
              ('weighted_from_classifier',ctypes.c_uint32),
              ('weighted_with_both_origins',ctypes.c_uint32),
              ('vendor_calibration_equivalence_proven',ctypes.c_uint8),
              ('vendor_classification_equivalence_proven',ctypes.c_uint8),
              ('produces_selected_neutral',ctypes.c_uint8)]
LIB.hb_awb_scene_prepare_bounded.argtypes=[ctypes.POINTER(Stats),ctypes.POINTER(Calibration),ctypes.POINTER(Masks),ctypes.POINTER(Scene)]
LIB.hb_awb_scene_prepare_bounded.restype=ctypes.c_int
LIB.hb_awb_apply_explicit_calibration.argtypes=[ctypes.POINTER(Stats),ctypes.POINTER(Calibration),ctypes.POINTER(Stats)]
LIB.hb_awb_apply_explicit_calibration.restype=ctypes.c_int
LIB.hb_awb_prepare_raw_ae_evidence.argtypes=[ctypes.POINTER(Stats),ctypes.POINTER(AE)]
LIB.hb_awb_prepare_raw_ae_evidence.restype=ctypes.c_int

def trunc0(a,b):
    assert b>0
    return (-1 if a<0 else 1)*(abs(a)//b)

def calc_raw_and_mask(gains,bias,spatial,stats,accepted,zone,weight,topology,output):
    filtered,fstats=component_oracle(weight,topology)
    active=[(i,int(weight[i])) for i in range(N) if filtered[i]]
    cc=[None]*N
    for i,b in enumerate(stats.blocks):
        cc[i]=[trunc0(trunc0(int(b.site_sum_q16[k])*int(gains[k]),65536)*int(spatial[i]),65536)
                    +int(b.site_count[k])*int(bias[k]) for k in range(4)]
        assert list(output.calibrated.blocks[i].site_sum_q16)==cc[i]
        assert output.calibrated.blocks[i].raw_brightness_sum_q16==b.raw_brightness_sum_q16
        assert output.calibrated.blocks[i].sample_count==b.sample_count
        assert output.ae.raw_block_mean_q16[i]==trunc0(int(b.raw_brightness_sum_q16),int(b.sample_count))
        assert output.ae.at_or_above_white_ppm[i]==int(b.at_or_above_white_count)*1000000//int(b.sample_count)
        assert output.ae.at_or_below_black_ppm[i]==int(b.at_or_below_black_count)*1000000//int(b.sample_count)
    a=output.accumulation
    assert list(a.weighted_site_sum_q16)==[
        sum(cc[i][k]*w for i,w in active) for k in range(4)]
    assert list(a.weighted_site_count)==[
        sum(int(stats.blocks[i].site_count[k])*w for i,w in active) for k in range(4)]
    assert a.weighted_raw_brightness_q16==sum(int(stats.blocks[i].raw_brightness_sum_q16)*w for i,w in active)
    assert a.weighted_sample_count==sum(int(stats.blocks[i].sample_count)*w for i,w in active)
    assert a.weighted_at_or_above_white_count==sum(int(stats.blocks[i].at_or_above_white_count)*w for i,w in active)
    assert a.surviving_blocks==len(active)
    assert a.weighted_but_unclassified_blocks==sum(accepted[i]==0 for i,w in active)
    assert (a.filter.groups_removed,a.filter.groups_kept,a.filter.blocks_removed,a.filter.blocks_kept)==fstats
    assert output.weighted_from_zone_not_classifier==sum(bool(zone[i]) and not accepted[i] for i,w in active)
    assert output.weighted_from_classifier==sum(bool(accepted[i]) and not zone[i] for i,w in active)
    assert output.weighted_with_both_origins==sum(bool(zone[i]) and bool(accepted[i]) for i,w in active)
    assert not output.produces_selected_neutral
    assert not output.vendor_calibration_equivalence_proven
    assert not output.vendor_classification_equivalence_proven
    assert not output.calibrated.vendor_e2_equivalence_proven
    assert not output.ae.vendor_ae_equivalence_proven
    assert not output.accumulation.vendor_candidate_equivalence_proven
    raw_sum=sum(int(b.raw_brightness_sum_q16) for b in stats.blocks)
    assert output.ae.total_raw_sum_q16==raw_sum
    assert output.ae.total_samples==stats.input_sample_count
    assert output.ae.frame_raw_mean_q16==trunc0(raw_sum,stats.input_sample_count)
    assert output.ae.total_at_or_above_white==sum(int(b.at_or_above_white_count) for b in stats.blocks)
    assert output.ae.total_at_or_below_black==sum(int(b.at_or_below_black_count) for b in stats.blocks)


def synthetic():
    rng=random.Random(202610211234)
    cases=0
    for test_id in range(64):
        s=Stats()
        for b in s.blocks:
            counts=[]
            for k in range(4):
                b.site_sum_q16[k]=rng.randrange(-100_000_000,100_000_000)
                b.site_count[k]=rng.randrange(1,25)
                counts.append(b.site_count[k])
            b.sample_count=sum(counts)
            b.raw_brightness_sum_q16=sum(b.site_sum_q16)
            b.at_or_above_white_count=rng.randrange(0,b.sample_count+1)
            b.at_or_below_black_count=rng.randrange(0,b.sample_count+1)
            b.min_sample=0;b.max_sample=2048
            s.input_sample_count+=b.sample_count
        gains=[rng.randrange(0,4*65536+1) for k in range(4)]
        bias=[rng.randrange(-100000,100001) for k in range(4)]
        spatial=[rng.randrange(0,4*65536+1) for i in range(N)]
        spatial_array=(ctypes.c_uint32*N)(*spatial)
        c=Calibration((ctypes.c_uint32*4)(*gains),(ctypes.c_int64*4)(*bias),spatial_array)
        m=Masks();m.neighbours=4 if test_id%2==0 else 8
        for i in range(N):
            m.classifier_accepted[i]=rng.randrange(2)
            m.zone_override[i]=rng.randrange(2)
            m.final_weight[i]=(rng.choice([0,0,0,1,2,7,31,32])
                             if (m.classifier_accepted[i] or m.zone_override[i]) else 0)
        out=Scene()
        assert LIB.hb_awb_scene_prepare_bounded(ctypes.byref(s),ctypes.byref(c),ctypes.byref(m),ctypes.byref(out))==0
        calc_raw_and_mask(gains,bias,spatial,s,m.classifier_accepted,m.zone_override,m.final_weight,m.neighbours,out)
        cases+=1
    return cases


def private_dng_replay(filename, return_accumulation=False):
    import tifffile
    import numpy as np
    p=Path(filename)
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest=='4a275648d6490ad32c156bedf1abd1d08618e942ca658893d4374ac93e23101a'
    with tifffile.TiffFile(str(p)) as t:
        pg=t.pages[0]
        data=pg.asarray()
        assert data.shape==(3072,4096) and data.dtype==np.uint16
        blacks=tuple(int(v)*65536 for v in pg.tags['BlackLevel'].value)
        white=int(pg.tags['WhiteLevel'].value)
        # Re-run independent Bayer/site/brightness oracle from checkpoint02.
        s=check(data,blacks,white,0,(0,0,data.shape[1],data.shape[0]))
    spatial=[65536+(i%9)*147 for i in range(N)]
    gains=[65536,70000,61000,81920]
    bias=[0,-240,123,-33]
    spatial_array=(ctypes.c_uint32*N)(*spatial)
    cal=Calibration((ctypes.c_uint32*4)(*gains),(ctypes.c_int64*4)(*bias),spatial_array)
    m=Masks();m.neighbours=4
    # A controlled, explicitly *synthetic* zone/classifier response map.
    for iy in range(32):
        for ix in range(32):
            i=iy*32+ix
            m.classifier_accepted[i]=int(8<=iy<24 and 8<=ix<24)
            m.zone_override[i]=int(12<=iy<20 and 4<=ix<28)
            m.final_weight[i]=(1+(i%7)) if m.classifier_accepted[i] or m.zone_override[i] else 0
    out=Scene()
    assert LIB.hb_awb_scene_prepare_bounded(ctypes.byref(s),ctypes.byref(cal),ctypes.byref(m),ctypes.byref(out))==0
    calc_raw_and_mask(gains,bias,spatial,s,m.classifier_accepted,m.zone_override,m.final_weight,m.neighbours,out)
    report={'private_capture_sha256':digest,'native1c_dng':True,'raw_dimensions':[4096,3072],
            'blocks_independently_checked':1024,'per_block_calibration_matched':True,
            'raw_ae_brightness_preserved':True,'selected_neutral_produced':False,
            'no_private_pixels_in_report':True,'vendor_equivalence_claimed':False}
    return (report,out.accumulation) if return_accumulation else report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private-dng');ap.add_argument('--report');args=ap.parse_args()
    cases=synthetic()
    result={'checkpoint':'AWB_REBUILD_03','synthetic_cases':cases,
            'blocks_checked_per_case':1024,
            'independent_oracle':'Python arbitrary-precision exact two-stage Q16 arithmetic / BFS / replay sums',
            'original_vendor_firmware_compared':False,'status':'PASS'}
    if args.private_dng: result['private_capture']=private_dng_replay(args.private_dng)
    if args.report:Path(args.report).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()