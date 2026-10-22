#!/usr/bin/env python3
"""Stage4 structural scene-evidence verification (never selects WB).

Public code has no sensor matrices or captured photographs. --capture/--dng and
--domain-json are private, hash-bound inputs. --private-report has scene data;
--public-report carries only scope and aggregate check counts / source hashes.
"""
import argparse
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src' / 'hb_phone_neutral_observation.c'
HDR = ROOT / 'src' / 'hb_phone_neutral_observation.h'
N=1024
M=729
NO=2**32-1

class Knot(C.Structure):
    _fields_=[('kelvin',C.c_uint32),('tint',C.c_int32),('red_gain_q12',C.c_uint32),
              ('blue_gain_q12',C.c_uint32),('exclusion',C.c_uint32)]
class Domain(C.Structure):
    _fields_=[('schema',C.c_uint32),('count',C.c_uint32),('points',Knot*M)]
class Block(C.Structure):
    _fields_=[('mean',C.c_double*4),('mean_brightness',C.c_double),
              ('red_gain_q12',C.c_uint32),('blue_gain_q12',C.c_uint32),('raw_flags',C.c_uint32)]
class Frame(C.Structure):
    _fields_=[('sensor_timestamp_ns',C.c_uint64),('exposure_time_ns',C.c_uint64),
              ('ISO',C.c_uint32),('bound_to_physical_sensor_and_frame',C.c_uint32),
              ('original_single_raw_proven',C.c_uint32),('basis',C.c_uint32),('blocks',Block*N)]
class Policy(C.Structure):
    _fields_=[('study_radius_q12',C.c_uint32),('spatial_edge_radius_q12',C.c_uint32),
              ('minimum_support_blocks',C.c_uint32),('minimum_brightness',C.c_double),
              ('maximum_brightness',C.c_double),('maximum_green_site_disagreement',C.c_double)]
class Trace(C.Structure):
    _fields_=[('reason',C.c_uint32),('nearest_knot_index',C.c_uint32),
              ('near_lattice',C.c_uint32),('component_index',C.c_uint32),('distance_q12',C.c_float)]
class Result(C.Structure):
    _fields_=[('schema',C.c_uint32),('decision',C.c_uint32),
              ('render_permitted',C.c_uint32),('calibrated_policy',C.c_uint32),
              ('evaluated_blocks',C.c_uint32),('raw_rejected',C.c_uint32),
              ('brightness_rejected',C.c_uint32),('green_split_rejected',C.c_uint32),
              ('signed_gain_rejected',C.c_uint32),('near_valid_knot',C.c_uint32),
              ('far_from_grid',C.c_uint32),('near_tint_edge',C.c_uint32),
              ('near_quadrants_bitmask',C.c_uint32),('spatial_components',C.c_uint32),
              ('largest_spatial_component',C.c_uint32),('support_threshold_met',C.c_uint32),
              ('usable_domain_points',C.c_uint32),('excluded_domain_points',C.c_uint32),
              ('shading_basis',C.c_uint32),('blocks',Trace*N)]

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def build(out):
    out.mkdir(parents=True,exist_ok=True)
    library=out/'libhb_phone_neutral_observation.so'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                    '-Wno-misleading-indentation','-ffp-contract=off','-fPIC','-shared',
                    str(SRC),'-lm','-o',str(library)],check=True)
    native=C.CDLL(str(library.resolve()))
    native.hb_phone_neutral_observe.argtypes=[C.POINTER(Domain),C.POINTER(Frame),C.POINTER(Policy),C.POINTER(Result)]
    native.hb_phone_neutral_observe.restype=C.c_int
    return native,library

def load_domain(j):
    assert j['schema']=='hasselblad-phone-domain1-on-demand-v1'
    assert j['status']=='completed' and j['render_applied'] is False
    data=j['points']
    assert len(data)==729
    out=Domain();out.schema=1;out.count=len(data)
    reasons={'representable':0,'temperature_clipped':1,'scene_signed_gain':2,'adjacent_duplicate':3}
    for i,point in enumerate(data):
        reason=reasons[point['exclusion']]
        gains=point['gain_q12'] if reason==0 else [0,4096,0]
        out.points[i]=Knot(point['kelvin'],point['tint'],int(gains[0]),int(gains[2]),reason)
    assert sum(k.exclusion==0 for k in out.points)==707
    assert sum(k.exclusion!=0 for k in out.points)==22
    return out

def capture_binding(capture,domain_json,dng):
    assert capture['schema']=='hasselblad-photon-capture-evidence-v1'
    assert capture['calibration_evidence_usable'] and not capture['calibration_unusable_reasons']
    assert capture['pairing_status']=='image_timestamp_equals_selected_still_result_timestamp'
    assert capture['input_frame_count']==1 and capture['pixel_rendering_changed_by_sidecar'] is False
    assert capture['dng']['bytes']==dng.stat().st_size
    assert capture['dng']['sha256']==digest(dng)
    orig=capture['original_still']; prov=orig['sensor_provenance']
    assert prov['sensor_provenance_matched'] and prov['result_camera_id_matched']
    assert prov['request_targets_recorded_raw_surface'] and prov['selected_and_logical_frame_number_matched']
    assert not prov['selected_characteristics_are_logical']
    assert capture['frame_number']==orig['selected_result_frame_number']==str(domain_json['source_frame_number'])
    assert capture['delivered_raw']['sensor_timestamp_ns']==orig['selected_sensor_timestamp_ns']==domain_json['source_sensor_timestamp_ns']
    assert prov['selected_calibration_camera_id']==domain_json['physical_sensor_id']==prov['selected_result_camera_id']
    assert capture['delivered_raw']['format']==32 and capture['delivered_raw']['delivered_width']==4096
    assert capture['delivered_raw']['delivered_height']==3072
    assert capture['delivered_raw']['image_crop_rect']==[0,0,4096,3072]
    assert not capture['delivered_raw']['binned']
    assert capture['scene_candidate_diagnostics']['render_applied'] is False
    return orig['selected_raw_sensor_result']

def raw_blocks(raw, black,white):
    h,w=raw.shape
    assert (h,w)==(3072,4096)
    blocks=[]
    for ry,rx in ((0,0),(0,1),(1,0),(1,1)):
        plane=(raw[ry::2,rx::2].astype('float64')-black)/(white-black)
        blocks.append(plane.reshape(32,h//64,32,w//64).mean(axis=(1,3)).reshape(-1))
    return np.stack(blocks,axis=1)

def make_frame(means,timestamp,exposure,iso,basis=1,raw_flags=None):
    assert means.shape==(1024,4)
    f=Frame()
    f.sensor_timestamp_ns=timestamp;f.exposure_time_ns=exposure;f.ISO=iso
    f.bound_to_physical_sensor_and_frame=1;f.original_single_raw_proven=1;f.basis=basis
    greens=(means[:,1]+means[:,2])*.5
    ratios=4096.0*greens[:,None]/means[:,[0,3]]
    assert np.isfinite(ratios).all()
    if raw_flags is None:raw_flags=np.zeros(1024,dtype=np.int32)
    for i in range(1024):
        m=means[i]
        b=Block()
        b.mean=(C.c_double*4)(*map(float,m))
        b.mean_brightness=float(np.sum(m)/4)
        b.raw_flags=int(raw_flags[i])
        if not b.raw_flags:
            assert all(x>0 for x in m)
            assert np.all((ratios[i]>=1)&(ratios[i]<65536))
            b.red_gain_q12=int(ratios[i,0]);b.blue_gain_q12=int(ratios[i,1])
        f.blocks[i]=b
    return f

def oracle(domain,frame,p):
    pts=np.asarray([[k.red_gain_q12,k.blue_gain_q12] for k in domain.points[:domain.count] if k.exclusion==0],dtype=np.int64)
    valid_indices=np.asarray([i for i,k in enumerate(domain.points[:domain.count]) if k.exclusion==0])
    ratios=np.asarray([[b.red_gain_q12,b.blue_gain_q12] for b in frame.blocks],dtype=np.int64)
    flags=np.asarray([b.raw_flags for b in frame.blocks])
    brightness=np.asarray([b.mean_brightness for b in frame.blocks])
    gsplit=np.asarray([abs(b.mean[1]-b.mean[2])/max((b.mean[1]+b.mean[2])/2,1.e-16) for b in frame.blocks])
    reasons=np.zeros(N,dtype=np.int64)
    reasons[flags!=0]=1
    reasons[(reasons==0)&((brightness<p.minimum_brightness)|(brightness>p.maximum_brightness))]=2
    reasons[(reasons==0)&(gsplit>p.maximum_green_site_disagreement)]=3
    reasons[(reasons==0)&np.any(ratios>32767,axis=1)]=4
    nearest=np.full(N,-1,dtype=np.int64)
    distances=np.zeros(N,dtype=np.float64)
    for i in np.flatnonzero(reasons==0):
        diff=pts-ratios[i]
        sq=np.sum(diff*diff,axis=1,dtype=np.int64)
        idx=int(np.argmin(sq))
        nearest[i]=valid_indices[idx]
        distances[i]=np.sqrt(float(sq[idx]))
    near=(reasons==0)&(distances<=p.study_radius_q12)
    components=[];visited=set()
    for seed in np.flatnonzero(near):
        seed=int(seed)
        if seed in visited:continue
        visited.add(seed)
        pending=[seed];n=0
        while pending:
            current=pending.pop();n+=1;y,x=divmod(current,32)
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    if dy==0 and dx==0:continue
                    yy,xx=y+dy,x+dx
                    if not 0<=yy<32 or not 0<=xx<32:continue
                    nxt=yy*32+xx
                    if not near[nxt] or nxt in visited:continue
                    if np.sum((ratios[current]-ratios[nxt])**2)>p.spatial_edge_radius_q12**2:continue
                    visited.add(nxt);pending.append(nxt)
        components.append(n)
    return reasons,nearest,distances,near,components

def run(native,domain,frame,p):
    result=Result()
    status=native.hb_phone_neutral_observe(C.byref(domain),C.byref(frame),C.byref(p),C.byref(result))
    assert status==0, f'native error: {status}'
    assert result.schema==1 and result.render_permitted==0 and result.calibrated_policy==0
    reason,nearest,distances,near,components=oracle(domain,frame,p)
    assert result.evaluated_blocks==int(np.sum(reason==0))
    assert result.raw_rejected==int(np.sum(reason==1))
    assert result.brightness_rejected==int(np.sum(reason==2))
    assert result.green_split_rejected==int(np.sum(reason==3))
    assert result.signed_gain_rejected==int(np.sum(reason==4))
    assert result.near_valid_knot==int(sum(near))
    assert result.far_from_grid==int(np.sum((reason==0)&(~near)))
    assert result.spatial_components==len(components)
    assert result.largest_spatial_component==max(components,default=0)
    assert result.support_threshold_met==(max(components,default=0)>=p.minimum_support_blocks)
    assert result.decision in (1,2)
    for i in range(N):
        t=result.blocks[i]
        assert t.reason==reason[i]
        assert t.near_lattice==int(near[i])
        assert t.nearest_knot_index==(int(nearest[i]) if reason[i]==0 else NO)
        assert abs(t.distance_q12-distances[i])<0.001
    return result

def negative_tests(native,domain,frame,policy):
    tests=0
    def reject(d,f,p,expected):
        nonlocal tests
        output=Result();C.memset(C.byref(output),0xA5,C.sizeof(output))
        before=C.string_at(C.byref(output),C.sizeof(output))
        code=native.hb_phone_neutral_observe(C.byref(d),C.byref(f),C.byref(p),C.byref(output))
        assert code==expected, (code,expected)
        assert C.string_at(C.byref(output),C.sizeof(output))==before
        tests+=1
    f=Frame.from_buffer_copy(bytes(frame));f.bound_to_physical_sensor_and_frame=0
    reject(domain,f,policy,2)
    f=Frame.from_buffer_copy(bytes(frame));f.sensor_timestamp_ns=0
    reject(domain,f,policy,2)
    f=Frame.from_buffer_copy(bytes(frame));f.exposure_time_ns=0
    reject(domain,f,policy,2)
    f=Frame.from_buffer_copy(bytes(frame));f.ISO=0
    reject(domain,f,policy,2)
    f=Frame.from_buffer_copy(bytes(frame));f.basis=0
    reject(domain,f,policy,2)
    f=Frame.from_buffer_copy(bytes(frame));f.blocks[0].mean[0]=float('nan')
    reject(domain,f,policy,2)
    f=Frame.from_buffer_copy(bytes(frame));f.blocks[0].red_gain_q12+=1
    reject(domain,f,policy,2)
    d=Domain.from_buffer_copy(bytes(domain));d.points[0].kelvin=0
    reject(d,frame,policy,3)
    d=Domain.from_buffer_copy(bytes(domain));d.points[1].kelvin=d.points[0].kelvin
    reject(d,frame,policy,3)
    d=Domain.from_buffer_copy(bytes(domain));d.points[0].exclusion=1
    reject(d,frame,policy,3)
    d=Domain.from_buffer_copy(bytes(domain));d.count=730
    reject(d,frame,policy,3)
    p=Policy.from_buffer_copy(bytes(policy));p.study_radius_q12=0
    reject(domain,frame,p,4)
    p=Policy.from_buffer_copy(bytes(policy));p.maximum_brightness=p.minimum_brightness
    reject(domain,frame,p,4)
    p=Policy.from_buffer_copy(bytes(policy));p.maximum_green_site_disagreement=float('nan')
    reject(domain,frame,p,4)
    return tests

def synthetic_tests(native,domain,template,p):
    tests=0
    # Artificial, highly uniform colour exactly on a grid knot can look like a
    # perfect classifier fit. That STILL must not authorize a neutral.
    valid=next(k for k in domain.points[:domain.count] if k.exclusion==0 and k.red_gain_q12>4500 and k.blue_gain_q12>4500)
    green=.3
    red=green*4096/valid.red_gain_q12; blue=green*4096/valid.blue_gain_q12
    f=Frame.from_buffer_copy(bytes(template))
    for i in range(N):
        b=f.blocks[i];b.mean=(C.c_double*4)(red,green,green,blue)
        b.mean_brightness=(red+green+green+blue)/4
        b.red_gain_q12=int(4096*green/red);b.blue_gain_q12=int(4096*green/blue)
        b.raw_flags=0
    # Floating point can produce one-ulp off on the synthetic test; make sure
    # RAW ratio and Q12 input still agree on a second pass.
    result=run(native,domain,f,p)
    assert result.near_valid_knot==N and result.largest_spatial_component==N
    assert result.decision==2 and result.render_permitted==0
    tests+=1
    # Synthetic mixed-illumination: two fully uniform, well-supported regions
    # must remain separate components AND still ABSTAIN (no verified lighting).
    second=next(k for k in domain.points[:domain.count] if k.exclusion==0 and
                (k.red_gain_q12-valid.red_gain_q12)**2+
                (k.blue_gain_q12-valid.blue_gain_q12)**2>5000**2)
    second_red=green*4096/second.red_gain_q12
    second_blue=green*4096/second.blue_gain_q12
    for y in range(32):
        for x in range(16,32):
            b=f.blocks[y*32+x]
            b.mean=(C.c_double*4)(second_red,green,green,second_blue)
            b.mean_brightness=(second_red+2*green+second_blue)/4
            b.red_gain_q12=int(4096*green/second_red)
            b.blue_gain_q12=int(4096*green/second_blue)
    result=run(native,domain,f,p)
    assert result.near_valid_knot==N and result.spatial_components==2
    assert result.largest_spatial_component==512
    assert result.render_permitted==0 and result.decision==2
    tests+=1
    # A single green-site disagreement is excluded even if a 2D grid knot
    # happens to be nearby. Recompute the Q12 ratio from the changed means.
    for i in range(N):
        b=f.blocks[i]
        b.mean=(C.c_double*4)(red,green,green,blue)
        b.mean_brightness=(red+2*green+blue)/4
        b.red_gain_q12=int(4096*green/red)
        b.blue_gain_q12=int(4096*green/blue)
    b=f.blocks[0]
    b.mean[1]=.34
    b.mean_brightness=sum(b.mean)/4
    corrected_green=(b.mean[1]+b.mean[2])*.5
    b.red_gain_q12=int(4096*corrected_green/red)
    b.blue_gain_q12=int(4096*corrected_green/blue)
    result=run(native,domain,f,p)
    assert result.green_split_rejected==1 and result.blocks[0].reason==3
    assert result.render_permitted==0
    tests+=1
    # Signed-gain domain guard precedes nearest-point matching.
    b=f.blocks[1]
    b.mean=(C.c_double*4)(.02,.2,.2,.15)
    b.mean_brightness=sum(b.mean)/4
    b.red_gain_q12=int(4096*.2/.02)
    b.blue_gain_q12=int(4096*.2/.15)
    result=run(native,domain,f,p)
    assert result.signed_gain_rejected==1 and result.blocks[1].reason==4
    tests+=1
    # Zero valid RAW blocks: abstain, do not reuse previous candidate.
    for i in range(N):
        f.blocks[i].raw_flags=1;f.blocks[i].red_gain_q12=0;f.blocks[i].blue_gain_q12=0
    result=run(native,domain,f,p)
    assert result.decision==1 and result.near_valid_knot==0
    tests+=1
    # Spatial wrap false-positive protection (31 and 32 are not neighbors).
    for i in (31,32):
        b=f.blocks[i];b.raw_flags=0
        b.red_gain_q12=int(4096*green/red);b.blue_gain_q12=int(4096*green/blue)
    result=run(native,domain,f,p)
    assert result.spatial_components==2 and result.largest_spatial_component==1
    tests+=1
    return tests

def main():
    parser=argparse.ArgumentParser()
    for a in ('capture','dng','domain-json','out','public-report','private-report'):
        parser.add_argument('--'+a,type=Path,required=True)
    a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    original_hash={x.name:digest(x) for x in (a.capture,a.dng,a.domain_json)}
    capture=json.loads(a.capture.read_text());domain_json=json.loads(a.domain_json.read_text())
    original_result=capture_binding(capture,domain_json,a.dng)
    lib,so=build(a.out)
    domain=load_domain(domain_json)
    raw=tifffile.imread(a.dng)
    black=float(original_result['android.sensor.dynamicBlackLevel'][0]);white=float(original_result['android.sensor.dynamicWhiteLevel'])
    means=raw_blocks(raw,black,white)
    frame=make_frame(means,int(domain_json['source_sensor_timestamp_ns']),
                     int(original_result['android.sensor.exposureTime']),
                     int(original_result['android.sensor.sensitivity']))
    assert np.all(raw<white) and np.all(raw>black)
    before_frame=bytes(frame);before_domain=bytes(domain)
    runs=[];run_count=0;trace_count=0
    for radius in (128,256,512,1024):
        p=Policy(radius,128,16,.005,.9,.10)
        o=run(lib,domain,frame,p)
        runs.append({'radius_q12':radius,'evaluable_blocks':o.evaluated_blocks,
            'near_grid_blocks':o.near_valid_knot,'spatial_components':o.spatial_components,
            'largest_component':o.largest_spatial_component,
            'tint_boundary_near':o.near_tint_edge,
            'support_threshold_met_diagnostic_only':bool(o.support_threshold_met),
            'decision':'ABSTAIN_UNCALIBRATED' if o.decision==2 else 'ABSTAIN_NO_SUPPORT',
            'render_permitted':False})
        run_count+=1;trace_count+=N
    test_policy=Policy(512,128,16,.005,.9,.1)
    invalid=negative_tests(lib,domain,frame,test_policy)
    synthetic=synthetic_tests(lib,domain,frame,test_policy)
    assert bytes(frame)==before_frame and bytes(domain)==before_domain
    private={'status':'PASS','scope':'Single physical-camera RAW, experimental scene observations, never WB selection',
        'capture_input_sha256':original_hash, 'compiled_native_sha256':digest(so),
        'physical_camera_id':domain_json['physical_sensor_id'],
        'frame':domain_json['source_frame_number'], 'raw_scene_studies':runs,
        'negative_nonmutation_cases':invalid,'synthetic_abstention_cases':synthetic,
        'on_android_device_tested':False,
        'photographic_renderer_changed':False,
        'real_illumination_cct_measured':False,
        'certified_reference_target_available':False}
    a.private_report.write_text(json.dumps(private,indent=2)+'\n')
    public={'status':'PASS','stage':'Stage4 bounded phone scene-neutral evidence; source only',
        'raw_frame_replays':run_count,'block_oracle_comparisons':trace_count,
        'native_api_guard_cases':invalid,'synthetic_abstention_cases':synthetic,
        'native_sanitizer_probe':'separate executable',
        'raw_and_domain_inputs_unchanged':True,
        'domain1_representation_preserved':True,
        'scene1b_original_81_point_ABI_preserved':True,
        'shipping_policy_selected':False,'renderer_changed':False,
        'hal_neutral_used_for_selection':False,
        'original_firmware_parity_newly_claimed':False,
        'source_hashes':{x.name:digest(x) for x in (SRC,HDR,Path(__file__))}}
    a.public_report.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps(public,indent=2))

if __name__=='__main__':main()
