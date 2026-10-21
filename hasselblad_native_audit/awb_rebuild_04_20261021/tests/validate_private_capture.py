#!/usr/bin/env python3
"""Private optional Native1C DNG + sidecar provenance validation.

Not a Hasselblad vendor AWB replay. Does not save photo pixels or sidecar.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tifffile
import numpy as np
from test_frame_stats_python import check

p=argparse.ArgumentParser()
p.add_argument('--dng',required=True)
p.add_argument('--json',required=True)
p.add_argument('--report',required=True)
a=p.parse_args()
s=json.loads(Path(a.json).read_text())
with tifffile.TiffFile(a.dng) as tf:
    page=tf.pages[0]
    raw=page.asarray()
    assert raw.dtype==np.uint16 and raw.ndim==2
    w,h=raw.shape[1],raw.shape[0]
    raw_json=s['delivered_raw']
    eff=s['effective_photon_export']
    original=s['original_still']
    sensor=original['selected_raw_sensor_result']
    assert s['input_frame_count']==1 and raw_json['format']==32
    assert raw_json['delivered_width']==w and raw_json['delivered_height']==h
    assert raw_json['copied_width']==w and raw_json['copied_height']==h
    assert raw_json['pixel_stride_bytes']==2
    assert raw_json['row_stride_bytes']>=w*2
    assert raw_json['image_crop_rect']==[0,0,w,h]
    assert raw_json['binned'] is False
    assert s['pairing_status']=='image_timestamp_equals_selected_still_result_timestamp'
    assert sensor['android.sensor.timestamp']==raw_json['sensor_timestamp_ns']
    assert original['selected_sensor_timestamp_ns']==raw_json['sensor_timestamp_ns']
    assert str(original['logical_frame_number'])==s['frame_number']
    provenance=original['sensor_provenance']
    assert provenance['sensor_provenance_matched']
    assert provenance['opened_camera_id']==provenance['selected_calibration_camera_id']
    assert str(eff['camera_id'])==provenance['opened_camera_id']
    assert eff['cfa_pattern']==0 and eff['raw_copy_geometry_matches_export']
    assert tuple(page.tags['CFARepeatPatternDim'].value)==(2,2)
    assert bytes(page.tags['CFAPattern'].value)==b'\x00\x01\x01\x02'
    assert eff['white_level_raw_counts']==page.tags['WhiteLevel'].value
    black=[int(x) for x in page.tags['BlackLevel'].value]
    assert black==[int(x) for x in eff['black_level_raw_counts']]
    assert sensor['android.sensor.dynamicBlackLevel']!=eff['black_level_raw_counts']
    assert eff['used_dynamic_black_level'] is False
    dng_neutral=page.tags['AsShotNeutral'].value
    assert len(dng_neutral)==6
    camera_neutral=sensor['android.sensor.neutralColorPoint']
    for i in range(3):
        assert int(dng_neutral[2*i])==camera_neutral[i]['numerator']
        assert int(dng_neutral[2*i+1])==camera_neutral[i]['denominator']
        assert abs(eff['neutral_used'][i]-dng_neutral[2*i]/dng_neutral[2*i+1])<1e-7
    assert Path(a.dng).stat().st_size==s['dng']['bytes']
    assert hashlib.sha256(Path(a.dng).read_bytes()).hexdigest()==s['dng']['sha256']
    crop=(0,0,w,h)
    # Original DNG selection: export black level 64, not the dynamic 63.9375.
    check(raw,[int(v*65536) for v in black],int(page.tags['WhiteLevel'].value),0,crop)
    # Controlled alternative metadata: preserve fractional 63.9375.
    dynamic=[round(float(v)*65536) for v in sensor['android.sensor.dynamicBlackLevel']]
    check(raw,dynamic,int(page.tags['WhiteLevel'].value),0,crop)
    result={'checkpoint':'AWB_REBUILD_02_CAPTURE_PROVENANCE',
            'result':'PASS',
            'source':'private Native1C DNG + capture sidecar, no redistribution',
            'fixture_dng_sha256':s['dng']['sha256'],
            'capture_format':'RAW_SENSOR',
            'raw_dimensions':[w,h],
            'raw_sensor_samples':int(raw.size),
            'frame_timestamp_and_camera_provenance':'matched',
            'dng_as_shot_neutral_matches_original_camera2':True,
            'effective_export_black_distinct_from_dynamic_black':True,
            'both_original_dynamic_and_export_black_reruns_match_independent_reference':True,
            'block_count_checked_per_black_variant':1024,
            'synthetic_original_vendor_comparison':False,
            'original_vendor_E2_semantics_proven':False,
            'raw_pixel_values_or_sidecar_in_output':False}
    Path(a.report).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))