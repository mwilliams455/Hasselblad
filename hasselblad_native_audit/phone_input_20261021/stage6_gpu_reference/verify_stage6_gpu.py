#!/usr/bin/env python3
"""Stage6 read-only Bayer2Float GPU patch comparison against a verified DNG.

User-supplied originals only: --capture sidecar --dng file --gpu copied-stage6-json
--private-report path. A self-test is available with --self-test.

This is a PIXEL comparison with two explicitly labelled RAW-row hypotheses,
not a certified GPU oracle. Only regular full-frame RGGB one-RAW mode. The
project's Photon shader performs a separate fp16 normalize, gain-map GL_LINEAR
sample and inverse whitePoint before storing RGBA16F; this script models those
operations and reports residuals without authorizing WB or rendering.
"""
import argparse, base64, hashlib, json, math, pathlib, struct, sys
import numpy as np
import tifffile

PATCH_GRID, PATCH_W, N = 4, 8, 1024


def require(value, reason):
    if not value:
        raise ValueError(reason)


def rect(w, h, idx):
    if idx not in range(16) or w < 64 or h < 64 or w % 2 or h % 2:
        raise ValueError('invalid_patch_geometry')
    gx, gy = idx % 4, idx // 4
    cx, cy = (2*gx + 1)*w//8, (2*gy + 1)*h//8
    return [max(0, min(w - PATCH_W, (cx - 4)&~1)),
            max(0, min(h - PATCH_W, (cy - 4)&~1)), PATCH_W, PATCH_W]


def gl_lerp_indices(v, total, count):
    z = float(v)*count/total - .5
    start = math.floor(z)
    return max(0,min(count-1,start)),max(0,min(count-1,start+1)),z-start


def float32_half(x):
    return float(np.float16(np.float32(x)))


def shader_projection(raw, lens_map, w, h, gpu_x, gpu_y, sample_y, black, white, neutral, hl_recon, hl_clip):
    # Internal reference input texture row orientation is still a hypothesis.
    sample=int(raw[sample_y,gpu_x]); site=(gpu_y%2)*2+(gpu_x%2)
    ch = 0 if site==0 else 2 if site==3 else 1
    scale = np.float32(1.) / max(np.float32(white-black[site]),np.float32(1.))
    normalized=float32_half(np.clip((np.float32(sample)-np.float32(black[site]))*scale,0,1))
    yy0, yy1, ty = gl_lerp_indices(gpu_y,h,lens_map.shape[0])
    xx0, xx1, tx = gl_lerp_indices(gpu_x,w,lens_map.shape[1])
    a,b,c,d = lens_map[yy0,xx0],lens_map[yy0,xx1],lens_map[yy1,xx0],lens_map[yy1,xx1]
    m=((a*(1-tx)+b*tx)*(1-ty)+(c*(1-tx)+d*tx)*ty)
    red,green,blue = float(m[0]),float((m[1]+m[2])/2.),float(m[3])
    factor = (red,green,blue)[ch] / max((red+green+blue)/3.,1.e-4)
    hl_val=normalized/neutral[ch]
    if hl_recon and hl_val>=hl_clip:
        return float('nan') # reconstruction depends on spatial opposed chroma
    return float32_half(np.clip(factor*hl_val,0.,1.))


def verify_capture_sidecar(capture,gpu,dng,sha):
    require(capture.get('schema')=='hasselblad-photon-capture-evidence-v1','bad_capture_schema')
    require(gpu.get('schema')=='hasselblad-stage6-bayer-gpu-samples-v1','bad_gpu_schema')
    require(gpu.get('status')=='completed','gpu_readback_not_completed')
    require(gpu.get('render_applied') is False and gpu.get('automatic_white_balance_calibrated') is False,
            'gpu_attempted_render_or_WB')
    require(capture.get('calibration_evidence_usable') is True,'capture_provenance_unusable')
    require(capture.get('input_frame_count')==1,'not_single_raw')
    c=capture['original_still']; p=c['sensor_provenance']; raw=capture['delivered_raw']
    for key in ('sensor_provenance_matched','result_camera_id_matched',
                'request_targets_recorded_raw_surface','selected_and_logical_frame_number_matched'):
        require(p.get(key) is True,'unverified_'+key)
    require(p.get('selected_characteristics_are_logical') is False,'logical_camera_not_allowed')
    got=gpu['capture']
    require(got['physical_sensor_id']==p['selected_calibration_camera_id']==p['selected_result_camera_id'],
            'sensor_id_mismatch')
    require(str(got['frame_number'])==str(capture['frame_number'])==str(c['selected_result_frame_number']),
            'frame_number_mismatch')
    require(str(got['sensor_timestamp_ns'])==str(raw['sensor_timestamp_ns'])
            ==str(c['selected_sensor_timestamp_ns'])
            ==str(c['selected_raw_sensor_result']['android.sensor.timestamp']), 'timestamp_mismatch')
    require(got['original_dng_name']==capture['dng']['name'],'original_dng_name_mismatch')
    require(got['original_dng_sha256']==capture['dng']['sha256']==sha,'saved_dng_checksum_mismatch')
    require(got['original_dng_bytes']==capture['dng']['bytes']==dng.stat().st_size,
            'saved_dng_size_mismatch')
    w=int(raw['copied_width']);h=int(raw['copied_height'])
    require(w>=64 and h>=64 and w%2==0 and h%2==0 and w*h<=32000000,'unsupported_dimensions')
    require(got['width']==gpu['output_width']==w and got['height']==gpu['output_height']==h,
            'gpu_geometry_mismatch')
    require(got['cfa']==c['selected_sensor_characteristics']['android.sensor.info.colorFilterArrangement']==0,
            'only_RGGB_supported')
    require(raw['format']==32 and not raw['binned'] and raw['copy_offset_bytes']==0,'unsupported_RAW_copy')
    require(raw['image_crop_rect']==[0,0,w,h] and not gpu['full_frame_readback'],
            'unknown_crop_or_full_frame_readback')
    require(capture['effective_photon_export']['app']['version_code']==27185,
            'unexpected_application_version')
    require(gpu.get('samples_count')==N,'wrong_gpu_pixel_count')
    require(gpu.get('patches_xywh')==[rect(w,h,i) for i in range(16)],'wrong_gpu_patch_order')
    return w,h


def compare(capture,gpu,raw,w,h):
    src=capture['original_still']['selected_raw_sensor_result']
    lens=src['android.statistics.lensShadingCorrectionMap']
    effective=capture['effective_photon_export']
    mapshape=(lens['rows'],lens['columns'],4)
    srcmap=np.asarray(lens['gains'],dtype=np.float32).reshape(mapshape)
    effmap=np.asarray(effective['lens_shading_gain_map'],dtype=np.float32).reshape(mapshape)
    require(np.array_equal(srcmap,effmap),'effective_versus_original_lens_map_changed')
    mp=srcmap.astype(np.float16).astype(np.float64)
    neutral=list(map(float,gpu['photon_white_point']))
    require(np.array_equal(np.asarray(neutral,dtype=np.float32),
                           np.asarray(effective['neutral_used'],dtype=np.float32)),
            'gpu_versus_effective_Photon_neutral_changed')
    black=list(map(float,gpu['original_black_site_counts']))
    require(np.array_equal(np.asarray(black),np.asarray(effective['black_level_raw_counts'])),
            'gpu_versus_effective_black_levels_changed')
    white=int(gpu['original_white_level'])
    require(white==src['android.sensor.dynamicWhiteLevel']==effective['white_level_raw_counts'],
            'gpu_versus_original_white_level_changed')
    encoding=gpu['sample_encoding']
    if encoding=='base64-little-endian-r16f':dt='<f2'
    elif encoding=='base64-little-endian-r32f':dt='<f4'
    else:raise ValueError('unrecognized_GPU_sample_encoding')
    data=base64.b64decode(gpu['samples_r_base64'],validate=True)
    require(len(data)==N*np.dtype(dt).itemsize==gpu['readback_bytes'],'incorrect_encoded_GPU_length')
    observed=np.frombuffer(data,dtype=dt).astype(np.float64)
    require(np.all(np.isfinite(observed)),'nonfinite_GPU_pixels')
    coordinates=[]
    for rectangle in gpu['patches_xywh']:
        x0,y0,pw,ph=rectangle
        coordinates.extend((x0+x,y0+y) for y in range(ph) for x in range(pw))
    require(len(coordinates)==N,'wrong_patch_pixel_count')
    hl=bool(gpu['highlight_reconstruction_enabled'])
    clip=float(gpu['highlight_clip_threshold'])
    predictions={}
    for hypothesis in ['raw_rows_as_uploaded','raw_rows_flipped_vertically']:
        values=[]
        for x,y in coordinates:
            source_y=y if hypothesis=='raw_rows_as_uploaded' else h-1-y
            values.append(shader_projection(raw,mp,w,h,x,y,source_y,black,white,neutral,hl,clip))
        expected=np.asarray(values)
        mask=np.isfinite(expected)
        residual=observed[mask]-expected[mask]
        require(mask.sum()>=128,'too_many_highlight_reconstruction_pixels_to_compare')
        predictions[hypothesis]={
            'compared_samples':int(mask.sum()),
            'ineligible_highlight_samples':int(N-mask.sum()),
            'mae':float(np.mean(np.abs(residual))),
            'p95_abs':float(np.percentile(np.abs(residual),95)),
            'max_abs':float(np.max(np.abs(residual))),
            'rms':float(np.sqrt(np.mean(residual**2)))}
    return predictions


def run(args):
    capture=json.loads(args.capture.read_text())
    gpu=json.loads(args.gpu.read_text())
    with args.dng.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    w,h=verify_capture_sidecar(capture,gpu,args.dng,sha)
    raw=tifffile.imread(args.dng)
    require(raw.dtype==np.uint16 and raw.shape==(h,w),'DNG_geometry_or_dtype_wrong')
    predictions=compare(capture,gpu,raw,w,h)
    public={
        'schema':'hasselblad-stage6-gpu-reference-report-v1','status':'STRUCTURAL_PASS',
        'capture_paired_with_original_dng':True,'sample_count':N,
        'gpu_execution_in_report':True,'candidate_wb_authorized':False,
        'shader_gpu_bit_exact_claim':False,'renderer_changed':False,
        'orientation_not_yet_proven':True,
        'scope':'CPU model vs recorded GPU readback, two RAW-row orientation hypotheses; no tuned acceptance threshold'}
    private=dict(public,physical_sensor_id=gpu['capture']['physical_sensor_id'],
        frame=gpu['capture']['frame_number'],dng_sha256=sha,
        hypotheses=predictions,read_type=gpu['sample_encoding'])
    args.public_report.parent.mkdir(parents=True,exist_ok=True)
    args.private_report.parent.mkdir(parents=True,exist_ok=True)
    args.public_report.write_text(json.dumps(public,indent=2)+'\n')
    args.private_report.write_text(json.dumps(private,indent=2)+'\n')
    print(json.dumps(private,indent=2))


def selftest():
    raw=np.full((64,64),250,dtype=np.uint16)
    mp=np.ones((2,2,4),dtype=np.float16).astype(np.float64)
    pixels=[]
    for i in range(16):
        x,y,w,h=rect(64,64,i)
        for dy in range(h):
            for dx in range(w):
                pixels.append(shader_projection(raw,mp,64,64,x+dx,y+dy,y+dy,[64]*4,1023,
                     [0.5,1,0.5],False,1.0))
    assert len(pixels)==1024 and all(math.isfinite(x) for x in pixels)
    assert rect(4096,3072,0)==[508,380,8,8]
    assert rect(4096,3072,15)==[3580,2684,8,8]
    for i in range(16):
        p=rect(4096,3072,i)
        assert all(v>=0 for v in p)
    try:rect(63,64,0)
    except ValueError:pass
    else:raise AssertionError('invalid dimension accepted')
    print('PASS Stage6 offline shader-pixel reference geometry and half-float arithmetic')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    for option in ['capture','dng','gpu','private-report','public-report']:
        p.add_argument('--'+option, type=pathlib.Path)
    args=p.parse_args()
    if args.self_test:
        selftest();return
    require(all(getattr(args,option.replace('-','_')) is not None for option in
                ['capture','dng','gpu','private-report','public-report']), 'missing_required_inputs')
    run(args)
if __name__=='__main__':main()