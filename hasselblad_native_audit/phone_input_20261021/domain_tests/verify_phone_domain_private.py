#!/usr/bin/env python3
"""PRIVATE original-metadata replay of the real-leaf-linked Domain1 host .so.

Input metadata, capture hashes and per-point temperature ratios remain private.
The original capture JSON is read-only; no render changes or HAL-based fit.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import zipfile

class Anchor(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('color', C.c_float*9), ('calibration', C.c_float*9)]
class Input(C.Structure):
    _fields_ = [('anchor', Anchor*2)]
class Request(C.Structure):
    _fields_ = [('first_kelvin', C.c_uint32), ('last_kelvin', C.c_uint32),
                ('kelvin_step', C.c_uint32), ('first_tint', C.c_int32),
                ('last_tint', C.c_int32), ('tint_step', C.c_uint32)]
class Point(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('tint', C.c_int32),
                ('exclusion', C.c_uint32), ('temperature_status', C.c_uint32),
                ('gain_q12', C.c_uint32*3)]
class Result(C.Structure):
    _fields_ = [('schema_version', C.c_uint32), ('requested', Request),
                ('kelvin_count', C.c_uint32), ('tint_count', C.c_uint32),
                ('point_count', C.c_uint32), ('representable', C.c_uint32),
                ('temperature_clipped', C.c_uint32), ('scene_signed_gain', C.c_uint32),
                ('adjacent_duplicate', C.c_uint32), ('points', Point*729)]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def original_profile(json_path):
    obj=json.loads(Path(json_path).read_text())
    chars=obj['original_still']['selected_sensor_characteristics']
    illum={17:2856,21:6504}
    anchors=[]
    for index in (1,2):
        temp=illum[chars['android.sensor.referenceIlluminant'+str(index)]]
        def rational_tag(name):
            vals=chars['android.sensor.'+name+str(index)]
            assert len(vals)==9
            return (C.c_float*9)(*(C.c_float(v['numerator']/v['denominator']).value for v in vals))
        anchors.append(Anchor(temp,rational_tag('colorTransform'),rational_tag('calibrationTransform')))
    return Input((Anchor*2)(*anchors))

def load_library(path):
    lib=C.CDLL(str(Path(path).resolve()))
    lib.hb_phone_domain_evaluate.argtypes=[C.POINTER(Input),C.POINTER(Request),C.POINTER(Result)]
    lib.hb_phone_domain_evaluate.restype=C.c_int
    return lib

def main():
    ap=argparse.ArgumentParser()
    for opt in ('capture','acceptance-zip','library','private-report','public-report'):
        ap.add_argument('--'+opt, type=Path, required=True)
    a=ap.parse_args()
    with zipfile.ZipFile(a.acceptance_zip) as z:
        evidence=json.loads(z.read('ACCEPTANCE_AUDIT_PRIVATE.json'))
    captures=evidence['captures']
    assert len(captures)==3
    assert sha(a.capture)==captures[0]['capture_sha256']
    inp=original_profile(a.capture)
    lib=load_library(a.library)
    request=Request(2000,10000,100,-100,100,25)
    result=Result()
    code=lib.hb_phone_domain_evaluate(C.byref(inp),C.byref(request),C.byref(result))
    assert code==0 and result.point_count==729,code
    verified=0
    per_capture=[]
    for cap in captures:
        coverage=cap['temperature_coverage']
        assert [c['tint'] for c in coverage]==list(range(-100,101,25))
        for i,point in enumerate((p for row in coverage for p in row['points'])):
            actual=result.points[i]
            expected_status=point['temperature_status']
            expected_reason=(1 if expected_status==4 else
                             0 if point['scene_signed_domain'] else 2)
            assert expected_status in (0,4)
            assert (actual.kelvin,actual.tint,actual.temperature_status,actual.exclusion)==(
                point['kelvin'],coverage[i//81]['tint'],expected_status,expected_reason), (cap['label'],i)
            if expected_reason==0:
                assert list(actual.gain_q12)==[point['gain_q12'][0],4096,point['gain_q12'][1]],(cap['label'],i)
            else:
                assert list(actual.gain_q12)==[0,0,0]
            verified+=1
        per_capture.append({'label':cap['label'], 'point_checks':729,
                            'capture_sha256':cap['capture_sha256']})
    summary={'status':'PASS','capture_replays':len(captures),'original_profile_captures':1,
             'point_checks':verified,'domain_counts':{
                'representable':result.representable,
                'temperature_clipped':result.temperature_clipped,
                'scene_signed_gain':result.scene_signed_gain,
                'adjacent_duplicate':result.adjacent_duplicate},
             'library_sha256':sha(a.library), 'metadata_source_sha256':sha(a.capture),
             'saved_capture_labels':per_capture,
             'source_photographic_pixels_modified':False,'renderer_changed':False,
             'HAL_fitted':False,'scene_candidate_selected':False}
    a.private_report.parent.mkdir(parents=True, exist_ok=True)
    a.private_report.write_text(json.dumps(summary, indent=2)+'\n')
    public={k:v for k,v in summary.items() if k not in ('metadata_source_sha256','saved_capture_labels')}
    public['capture_replays_from_same_original_sensor_profile']=True
    a.public_report.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps(public,indent=2))

if __name__=='__main__':main()
