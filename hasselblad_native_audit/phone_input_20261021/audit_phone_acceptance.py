#!/usr/bin/env python3
"""Explain diagnostic policy rejection from hash-bound RAW; never fit a policy.

All capture-derived values, curves and plots are private outputs. The optional
public report contains aggregate verification counts and source hashes only.
Manifest: [{"label": "...", "capture": "/...json", "dng": "/...dng"}].
Only an original full active-array RGGB/Bayer capture is supported for the
hypothetical lens-shading sensitivity calculation. No pixels are exported.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from capture_binding import bind_capture, decode_bound_dng
from temperature_binding import bind_temperature
from verify_phone_raw import frame_from_binding, oracle as raw_oracle
from verify_phone_scene import build, Input, Gains, Policy, Result, Frame, Grid, temperature_descriptor
from verify_phone_temperature import Estimate

HERE = Path(__file__).resolve().parent
RADII = [128, 256, 512, 1024, 2048, 4096]
TINTS = list(range(-100, 101, 25))


def quantiles(values):
    values = np.asarray(values)
    return np.quantile(values, [0, .05, .5, .95, 1]).tolist() if values.size else None


def map_plane(gain_map, channel, xs, ys):
    """Bilinear samples at sensor pixel coordinates normalized to [0,1]."""
    h, w, _ = gain_map.shape
    x = np.clip(xs, 0, 1) * (w - 1); y = np.clip(ys, 0, 1) * (h - 1)
    ix = np.minimum(x.astype(int), w - 2); iy = np.minimum(y.astype(int), h - 2)
    fx = x - ix; fy = y - iy
    upper = gain_map[iy[:, None], ix, channel] * (1 - fx) + gain_map[iy[:, None], ix + 1, channel] * fx
    lower = gain_map[iy[:, None] + 1, ix, channel] * (1 - fx) + gain_map[iy[:, None] + 1, ix + 1, channel] * fx
    return upper * (1 - fy[:, None]) + lower * fy[:, None]


def block_means(plane):
    h, w = plane.shape
    ye = (np.arange(33) * h + 31) // 32; xe = (np.arange(33) * w + 31) // 32
    return np.array([plane[ye[y]:ye[y+1], xe[x]:xe[x+1]].mean() for y in range(32) for x in range(32)])


def gains_from_means(means):
    green = (means[:, 1] + means[:, 2]) / 2
    return 4096 * green[:, None] / means[:, [0, 3]]


def shade_means(raw, binding):
    """Sensitivity replay only; source saturation/brightness policy is unchanged."""
    w, h = binding['width'], binding['height']; chars = binding['original_characteristics']
    assert chars['android.sensor.info.preCorrectionActiveArraySize'] == [0, 0, w, h]
    assert chars['android.sensor.info.activeArraySize'] == [0, 0, w, h]
    result = binding['original_sensor_metadata']; m = result['android.statistics.lensShadingCorrectionMap']
    gains = np.array(m['gains'], dtype=float).reshape(m['rows'], m['columns'], 4)
    assert min(gains.shape[:2]) >= 2 and np.isfinite(gains).all() and (gains >= 1).all()
    pixels = np.frombuffer(raw, dtype='<u2').reshape(h, w)
    positions = [[(0,0),(0,1),(1,0),(1,1)],[(0,1),(0,0),(1,1),(1,0)],
                 [(1,0),(1,1),(0,0),(0,1)],[(1,1),(1,0),(0,1),(0,0)]][binding['cfa']]
    means = []
    for channel, (ry, rx) in enumerate(positions):
        black = binding['black_q16'][ry * 2 + rx] / 65536
        plane = (pixels[ry::2, rx::2].astype(float) - black) / (binding['white_code'] - black)
        ys = np.arange(ry, h, 2) / (h - 1); xs = np.arange(rx, w, 2) / (w - 1)
        # Camera2 map greens are EVEN/ODD SENSOR ROWS, whereas our grid
        # channels are green-on-red-row/green-on-blue-row. These differ for
        # GBRG and BGGR; do not silently copy an RGGB-only channel ordering.
        map_channel = 1 + ry if channel in (1,2) else channel
        means.append(block_means(plane * map_plane(gains, map_channel, xs, ys)))
    return np.array(means).T


def table():
    text = (HERE/'hb_phone_temperature.c').read_text().split('static const float isotemperature')[1].split('};')[0]
    rows = re.findall(r'\{([^{}]+)\}', text)
    return np.array([[float(v.strip().rstrip('f')) for v in row.split(',')] for row in rows])


def oracle_gain(inp, ct, tint, rows):
    a, b = sorted(inp.anchor, key=lambda a: a.kelvin)
    products = [np.array(x.calibration,dtype=float).reshape(3,3) @ np.array(x.color,dtype=float).reshape(3,3) for x in (a,b)]
    weight = np.clip((1/ct - 1/b.kelvin) / (1/a.kelvin - 1/b.kelvin), 0, 1)
    matrix = weight * products[0] + (1 - weight) * products[1]
    mired = 1e6/ct; i = int(np.clip(np.searchsorted(rows[:,0], mired, side='right')-1, 0, 29))
    lo, hi = rows[i:i+2]; f = (hi[0] - mired)/(hi[0] - lo[0])
    directions = np.array([[1,lo[3]], [1,hi[3]]]); directions /= np.linalg.norm(directions, axis=1)[:,None]
    direction = f*directions[0] + (1-f)*directions[1]; direction /= np.linalg.norm(direction)
    u, v = f*lo[1:3] + (1-f)*hi[1:3] - tint/3000*direction
    x, y = 1.5*u/(u-4*v+2), v/(u-4*v+2)
    rgb = matrix @ [x,y,1-x-y]
    return rgb, np.max(rgb)/rgb*4096


def main():
    p = argparse.ArgumentParser()
    for n in ['manifest', 'out', 'public-report']: p.add_argument('--'+n, type=Path, required=True)
    p.add_argument('--plot', action='store_true'); a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    libpath, sources = build('cc', a.out, 'acceptance', ['-fPIC'], True); lib = C.CDLL(str(libpath.resolve()))
    lib.hb_phone_raw_build.argtypes = [C.c_void_p,C.c_size_t,C.POINTER(Frame),C.c_int,C.POINTER(Grid)]
    lib.hb_phone_scene_create.argtypes = [C.POINTER(Input),C.POINTER(Policy),C.POINTER(C.c_void_p)]
    lib.hb_phone_scene_run.argtypes = [C.c_void_p,C.POINTER(Grid),C.POINTER(Result)]
    lib.hb_phone_scene_locus.argtypes = [C.c_void_p,C.c_void_p]
    lib.hb_phone_scene_destroy.argtypes = [C.c_void_p]
    lib.hb_phone_temperature_create.argtypes = [C.POINTER(Input),C.POINTER(C.c_void_p)]
    lib.hb_phone_temperature_to_gain.argtypes = [C.c_void_p,C.c_uint32,C.c_float,C.POINTER(Gains)]
    lib.hb_phone_temperature_from_gain.argtypes = [C.c_void_p,C.POINTER(C.c_uint32),C.POINTER(Estimate)]
    lib.hb_phone_temperature_destroy.argtypes = [C.c_void_p]
    rows = table(); assert rows.shape == (31,4)
    # Analytic checks of the new spatial interpolation, including all edges.
    xs=np.linspace(0,1,19);ys=np.linspace(0,1,15);base=np.zeros((3,4,4))
    for ch in range(4):
        base[:,:,ch] = 1+ch + np.linspace(0,1,3)[:,None]*.3 + np.linspace(0,1,4)*.7
        assert np.allclose(map_plane(base,ch,xs,ys),1+ch + ys[:,None]*.3 + xs*.7,atol=1e-14,rtol=0)
    known=[[200,600,1500,2800],[400,300,2000,2100],[600,2000,300,1400],[800,1500,600,700]]
    for cfa in range(4):
        fake={'width':64,'height':64,'cfa':cfa,'black_q16':[64*65536]*4,'white_code':1023,
              'original_characteristics':{'android.sensor.info.preCorrectionActiveArraySize':[0,0,64,64],'android.sensor.info.activeArraySize':[0,0,64,64]},
              'original_sensor_metadata':{'android.statistics.lensShadingCorrectionMap':{'rows':2,'columns':2,'gains':[2,3,5,7]*4}}}
        raw=np.tile(np.array([[164,264],[364,464]],dtype='<u2'),(32,32)).tobytes()
        assert np.allclose(shade_means(raw,fake),np.array(known[cfa])/959,atol=1e-14,rtol=0)
    totals={'spatial_affine_checks':4,'spatial_bayer_channel_checks':4,'raw_block_oracle_checks':0,'matrix_gain_oracle_checks':0,'policy_runs':0,'policy_model_rejections':0,'phone_policy_comparisons':0}
    outputs=[]
    for item in json.loads(a.manifest.read_text()):
        capture=Path(item['capture']);j=json.loads(capture.read_text());before=json.dumps(j,sort_keys=True)
        binding=bind_capture(j,'dynamic');raw=decode_bound_dng(item['dng'],j,binding);buf=C.create_string_buffer(raw)
        frame=frame_from_binding(binding);grid=Grid();assert lib.hb_phone_raw_build(buf,len(raw),C.byref(frame),0,C.byref(grid))==0
        raw_oracle(raw,frame,grid);totals['raw_block_oracle_checks']+=1024
        means=np.array([list(b.mean) for b in grid.blocks]);gains=np.array([[b.red_gain_q12,b.blue_gain_q12] for b in grid.blocks])
        eligible=np.array([not b.flags and .005<=b.mean_brightness<=.9 and max(b.red_gain_q12,b.blue_gain_q12)<=32767 for b in grid.blocks])
        inp=temperature_descriptor(bind_temperature(j,'dynamic')['anchors']);temp=C.c_void_p();assert lib.hb_phone_temperature_create(C.byref(inp),C.byref(temp))==0
        def inverse(g):
            e=Estimate();status=lib.hb_phone_temperature_from_gain(temp,(C.c_uint32*3)(*map(int,g)),C.byref(e))
            return {'status':status,'kelvin':e.kelvin if status==0 else None,'tint':e.tint if status==0 else None,'residual':e.ratio_residual if status==0 else None}
        interpreted=[inverse([gains[i,0],4096,gains[i,1]]) for i in np.flatnonzero(eligible)]
        policy_rows=[];coverage=[];zero_locus=None
        for tint in TINTS:
            point_rows=[]
            for ct in range(2000,10001,100):
                gain=Gains();status=lib.hb_phone_temperature_to_gain(temp,ct,tint,C.byref(gain));rgb,expected=oracle_gain(inp,ct,tint,rows)
                if status==0:
                    assert np.min(rgb)>=1e-5 and np.max(np.abs(np.array(gain.gain_q12)-expected))<1.3
                else:assert status==4 and (np.min(rgb)<1e-5 or np.max(expected)>=40960)
                totals['matrix_gain_oracle_checks']+=1
                g=list(gain.gain_q12);green=[g[0]*4096//g[1],g[2]*4096//g[1]] if status==0 else None
                point_rows.append({'kelvin':ct,'temperature_status':status,'gain_q12':green,'scene_signed_domain':green is not None and min(green)>0 and max(green)<=32767})
            valid=np.array([p['gain_q12'] for p in point_rows if p['scene_signed_domain']])
            valid_dist=np.linalg.norm(gains[:,None,:]-valid[None,:,:],axis=2).min(axis=1) if valid.size else None
            coverage.append({'tint':tint,'points':point_rows,
                'representable_point_count':len(valid),
                'exploratory_valid_point_distance_quantiles_q12':quantiles(valid_dist[eligible]) if valid_dist is not None else None,
                'exploratory_classified_counts_at_test_radii':[int(np.count_nonzero(eligible&(valid_dist<=r))) for r in RADII] if valid_dist is not None else [0]*len(RADII),
                'scope':'Per-point coverage exploration only; not the native candidate policy, filter, optimizer or a shipping recommendation.'})
            for radius in RADII:
                handle=C.c_void_p();policy=Policy(tint,radius,2,16,.005,.9);status=lib.hb_phone_scene_create(C.byref(inp),C.byref(policy),C.byref(handle))
                row={'tint':tint,'radius_q12':radius,'create_status':status}
                if status:
                    assert any(not point['scene_signed_domain'] for point in point_rows)
                    totals['policy_model_rejections']+=1;policy_rows.append(row);continue
                result=Result();assert lib.hb_phone_scene_run(handle,C.byref(grid),C.byref(result))==0
                locus=(C.c_uint32*243)();assert lib.hb_phone_scene_locus(handle,locus)==0;lib.hb_phone_scene_destroy(handle)
                curve=np.array(locus,dtype=np.int64).reshape(81,3)
                d=np.linalg.norm(gains[:,None,:]-curve[None,:,1:],axis=2).min(axis=1)
                assert result.classified==int(np.count_nonzero(eligible&(d<=radius)))
                totals['policy_runs']+=1
                row.update(classified=result.classified,retained=result.retained,decision=result.decision,gain_q12=list(result.gain_q12),temperature=list(result.temperature))
                policy_rows.append(row)
                if tint==0:
                    zero_locus=curve
                    phone=j.get('scene_candidate_diagnostics',{})
                    if phone.get('status')=='completed':
                        saved=next(x for x in phone['policies'] if x['radius_q12']==radius)
                        assert result.classified==saved['classified_blocks'] and result.retained==saved['retained_blocks']
                        assert result.decision=={'no_candidate':0,'diagnostic_candidate':1,'temperature_rejected':2}[saved['decision']]
                        if result.decision==1:assert list(result.gain_q12)==saved['gain_q12'] and list(result.temperature)==saved['temperature_kelvin_tint_residual']
                        totals['phone_policy_comparisons']+=1
        shade=shade_means(raw,binding);shade_gains=gains_from_means(shade)
        d=np.linalg.norm(gains[:,None,:]-zero_locus[None,:,1:],axis=2).min(axis=1)
        shade_d=np.linalg.norm(shade_gains[:,None,:]-zero_locus[None,:,1:],axis=2).min(axis=1)
        hal=j['original_still']['selected_raw_sensor_result']['android.sensor.neutralColorPoint'];hal_gain=[int(4096*x['denominator']/x['numerator']) for x in hal]
        out={'label':item['label'],'capture_sha256':hashlib.sha256(capture.read_bytes()).hexdigest(),'dng_sha256':j['dng']['sha256'],
             'eligible_blocks':int(eligible.sum()),'distance_quantiles_min_p05_p50_p95_max_q12':quantiles(d[eligible]),
             'hypothetical_shading_distance_quantiles_q12':quantiles(shade_d[eligible]),
             'hypothetical_shading_classified_counts_at_test_radii':[int(np.count_nonzero(eligible&(shade_d<=r))) for r in RADII],
             'hypothetical_shading_note':'Bilinear original map at original active-array pixel coordinates, before block averaging; source eligibility retained. Sensitivity only, not a renderer or native input change.',
             'green_split_quantiles':quantiles(means[eligible,1]/means[eligible,2]),
             'block_temperature_status_counts':{str(s):sum(x['status']==s for x in interpreted) for s in sorted({x['status'] for x in interpreted})},
             'block_tint_quantiles':quantiles([x['tint'] for x in interpreted if x['status']==0]),
             'hal_reference_only':{'gain_q12':hal_gain,'interpretation':inverse(hal_gain),'zero_tint_distance_q12':float(np.linalg.norm(zero_locus[:,1:]-np.array(hal_gain)[[0,2]],axis=1).min())},
             'policy_sweep':policy_rows,'temperature_coverage':coverage,'zero_tint_locus':zero_locus.tolist(),
             'eligible_block_gains':gains[eligible].tolist(),'hypothetical_shaded_block_gains':shade_gains[eligible].tolist(),
             'render_applied':False,'shipping_policy_selected':False,'hal_used_to_select_policy':False}
        lib.hb_phone_temperature_destroy(temp);assert json.dumps(j,sort_keys=True)==before and buf.raw[:len(raw)]==raw
        outputs.append(out)
    (a.out/'ACCEPTANCE_AUDIT_PRIVATE.json').write_text(json.dumps({'quantile_order':['minimum','p05','median','p95','maximum'],'captures':outputs},indent=2)+'\n')
    report={'status':'PASS',**totals,'capture_replays':len(outputs),'test_tints':TINTS,'test_radii_q12':RADII,'input_and_metadata_unmodified':True,'renderer_changed':False,'shipping_policy_selected':False,'source_sha256':{str(f.relative_to(HERE.parents[1])):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),*sources]}}
    a.public_report.write_text(json.dumps(report,indent=2)+'\n')
    if a.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,len(outputs),figsize=(5*len(outputs),4.6),squeeze=False)
        for ax,out in zip(axes[0],outputs):
            curve=np.array(out['zero_tint_locus']);points=np.array(out['eligible_block_gains'])
            ax.plot(curve[:,1]/4096,curve[:,2]/4096,color='#1e657b',label='Model: zero tint')
            example=next(c for c in out['temperature_coverage'] if c['tint']==75)
            shifted=np.array([p['gain_q12'] for p in example['points'] if p['scene_signed_domain']])
            ax.plot(shifted[:,0]/4096,shifted[:,1]/4096,'--',color='#8d849b',label='Test: +75 tint, valid points')
            ax.scatter(points[:,0]/4096,points[:,1]/4096,s=5,alpha=.25,color='#ad4b35',label='Measured RAW blocks')
            ax.set_title(out['label']);ax.set_xlabel('Red correction / green correction');ax.set_ylabel('Blue correction / green correction');ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle('Acceptance investigation — test curves, not calibrated settings',fontsize=14)
        fig.tight_layout();fig.savefig(a.out/'Acceptance_Comparison_PRIVATE.png',dpi=160);plt.close(fig)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
