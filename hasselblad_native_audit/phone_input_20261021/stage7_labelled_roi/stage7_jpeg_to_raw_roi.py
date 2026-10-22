#!/usr/bin/env python3
"""Create strictly bound Stage7 RAW ROI annotations from upright JPEG rectangles.

Only the DNG Orientation=6 (90-degree clockwise) and matching uncropped
JPEG/DNG aspect are supported. This maps rectangles geometrically; it does
NOT prove JPEG pixels have no resampling, distortion or per-pixel warping.
"""
import argparse
import json
import math
from pathlib import Path
from PIL import Image
import tifffile


def req(ok, why):
    if not ok:raise ValueError(why)


def even_down(v): return int(v)//2*2

def even_up(v): return math.ceil(v/2)*2


def jpeg_to_raw(rect, jw, jh, rw, rh, orientation):
    req(orientation==6, 'unsupported_orientation_not_clockwise_right_top')
    req(jw > 0 and jh > 0 and rw > 0 and rh > 0, 'invalid_dimensions')
    req(abs((jw/jh)-(rh/rw))<1e-9, 'jpeg_raw_aspect_or_crop_mismatch')
    req(isinstance(rect,list) and len(rect)==4 and all(type(i) is int for i in rect), 'invalid_jpeg_rect')
    x,y,w,h=rect
    req(x>=0 and y>=0 and w>=16 and h>=16 and x+w<=jw and y+h<=jh,'jpeg_rect_out_of_bounds')
    rx0=even_down(y*rw/jh)
    rx1=even_up((y+h)*rw/jh)
    ry0=even_down((jw-(x+w))*rh/jw)
    ry1=even_up((jw-x)*rh/jw)
    req(rx0>=0 and ry0>=0 and rx1<=rw and ry1<=rh and rx1-rx0>=32 and ry1-ry0>=32,
        'mapped_raw_rect_out_of_bounds')
    return [rx0,ry0,rx1-rx0,ry1-ry0]


def make_annotation(cap, dng_path, jpeg_path, spec):
    # External DNG/JPEG hash matching is NOT assumed; the private Stage7
    # evaluator separately requires the *DNG* to match the captured sidecar.
    with tifffile.TiffFile(dng_path) as f:
        pg=f.pages[0]
        rw,rh=pg.shape[1],pg.shape[0]
        orientation=int(pg.tags['Orientation'].value)
    with Image.open(jpeg_path) as im:
        jw,jh=im.size
    provenance=cap['original_still']['sensor_provenance']
    req(provenance['sensor_provenance_matched'] is True,'unproven_sensor')
    out={'schema':'hasselblad-stage7-labelled-roi-v1',
         'binding':{'dng_sha256':cap['dng']['sha256'],
                    'physical_sensor_id':provenance['selected_calibration_camera_id'],
                    'frame_number':cap['frame_number'],
                    'sensor_timestamp_ns':cap['delivered_raw']['sensor_timestamp_ns']},
         'regions':[]}
    for r in spec['regions']:
        region={k:r[k] for k in ['id','role','source','illuminant']}
        region['rect_raw_xywh']=jpeg_to_raw(r['rect_jpeg_xywh'],jw,jh,rw,rh,orientation)
        out['regions'].append(region)
    return out


def selftest():
    assert jpeg_to_raw([200,100,100,150],1536,2048,4096,3072,6)==[200,2472,300,200]
    assert jpeg_to_raw([600,500,200,160],1536,2048,4096,3072,6)==[1000,1472,320,400]
    assert jpeg_to_raw([0,0,1536,2048],1536,2048,4096,3072,6)==[0,0,4096,3072]
    for (rect, orientation) in [([1,1,20,20],1),([-1,0,32,32],6),([0,0,8,30],6)]:
        try:jpeg_to_raw(rect,1536,2048,4096,3072,orientation)
        except ValueError:pass
        else:raise AssertionError('invalid_map_not_rejected')
    print('PASS Stage7 JPEG orientation geometry, bounds, 2px alignment and safe rejection')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    for arg in ('dng','jpeg','capture','spec','output'):
        p.add_argument('--'+arg,type=Path)
    opts=p.parse_args()
    if opts.self_test: selftest(); return
    req(all(getattr(opts,x) for x in ('dng','jpeg','capture','spec','output')),'missing_required_paths')
    cap=json.loads(opts.capture.read_text())
    spec=json.loads(opts.spec.read_text())
    req(spec.get('schema')=='hasselblad-stage7-jpeg-region-spec-v1','wrong_jpeg_region_spec_schema')
    out=make_annotation(cap,opts.dng,opts.jpeg,spec)
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(out,indent=2)+'\n')
    print('Written', opts.output, 'regions:',len(out['regions']))


if __name__=='__main__': main()
