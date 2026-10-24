#!/usr/bin/env python3
"""Private full-preview integration check; only aggregate receipt is public."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
import tifffile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'phocus_highlight_stage53'),str(ROOT/'phocus_room_stage46')]
from audit_highlight53 import HighlightRunner,load_private
from highlight53 import Highlight,equal_lower_limit
from analyse_room46 import read_profile,Core,trace,diff


def metric(a,b):
    d=np.abs(a.astype(float)-b.astype(float))
    return {'channels':int(d.size),'exact_channels':int((d==0).sum()),
            'maximum_absolute_difference':float(d.max()),'mean_absolute_difference':float(d.mean())}


def main():
    p=argparse.ArgumentParser()
    for name in ('dng','profile','apk','host','previous','work','safe-receipt'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();assert __debug__;a.work.mkdir(parents=True,exist_ok=True)
    paths=(a.dng,a.profile,a.apk)
    before=[hashlib.sha256(f.read_bytes()).digest() for f in paths]
    subprocess.run(['java','-Djava.library.path='+str(a.host.resolve()),'-cp',str((a.host/'classes').resolve()),
        'Stage54PrivateCheck',str(a.dng.resolve()),str(a.profile.resolve()),str(a.work.resolve())],check=True)
    host=json.loads((a.work/'HOST_RENDER54.json').read_text())
    def read(name,dtype='<f8'):return np.fromfile(a.work/(name+'.bin'),dtype=dtype)
    raw=read('camera_rgb16','<u2').reshape(-1,3);actual=read('highlight_input_rgb16','<u2').reshape(-1,3)
    matrix=read('camera_to_d50').reshape(3,3)
    original=read('original_rgb16','<u2').reshape(-1,3)
    assert np.array_equal(raw,np.fromfile(a.previous/'camera_rgb16.bin',dtype='<u2').reshape(-1,3))
    assert np.array_equal(matrix,np.fromfile(a.previous/'camera_to_d50.bin',dtype='<f8').reshape(3,3))
    temp,film,v,grid,curve=read_profile(a.profile)
    assert np.array_equal(original,np.fromfile(a.previous/f'curve{film}_{temp}_rgb16.bin',dtype='<u2').reshape(-1,3))
    with tifffile.TiffFile(a.dng) as document:
        value=document.pages[0].tags['AsShotNeutral'].value
        neutral=np.asarray(value,dtype=float).reshape(3,2)
        neutral=neutral[:,0]/neutral[:,1]
    gains=neutral.min()/neutral;after=matrix@np.diag(1/gains)
    assert np.array_equal(gains,read('gains'))
    matrix_error=float(np.max(np.abs(after-read('after_matrix').reshape(3,3))))
    assert matrix_error<1e-12
    singular=np.sort(gains)[0]==np.sort(gains)[1]
    floating=equal_lower_limit(raw/65535,gains) if singular else Highlight.prepare(gains).convert(raw/65535)
    expected=np.floor(np.clip(floating,0,1)*65535+.5).astype(np.uint16)
    highlight_difference=metric(actual,expected)
    assert highlight_difference['maximum_absolute_difference']<=1
    params=read('highlight_params');first=v[:9].reshape(3,3)@after
    assert np.max(np.abs(first-params[:9].reshape(3,3)))<1e-12
    core=Core(a.work/'core54.so')
    cp=core.params(params[:9].reshape(3,3),v[9:18].reshape(3,3),grid,False,curve,v[18:22])
    traced,display,stats=trace(actual,cp,v[28:37].reshape(3,3),v[37])
    colour=read('highlight_rgb16','<u2').reshape(-1,3)
    assert np.array_equal(colour,traced)
    complete,_,_=trace(expected,cp,v[28:37].reshape(3,3),v[37])
    complete_difference=metric(colour,complete)
    assert complete_difference['maximum_absolute_difference']<=4
    packed=read('display_argb','<u4').reshape(2,-1)
    rgb=lambda x:np.stack([(x>>16)&255,(x>>8)&255,x&255],-1).astype(np.uint8)
    assert np.array_equal(rgb(packed[1]),display)
    # Retained real data checks execution, never coefficients or target colour.
    elf,private_profile=load_private(a.apk);native=HighlightRunner(elf,private_profile)
    native.prepare(gains,(65535,)*3)
    sample=np.arange(0,len(raw),997)
    native_difference=metric(actual[sample],native.cpu16(raw[sample]))
    assert native_difference['maximum_absolute_difference']<=1
    for f,old in zip(paths,before):assert hashlib.sha256(f.read_bytes()).digest()==old
    result={'schema':'hasselblad-stage54-preview-integration-v1','status':'PASS_EXPERIMENTAL_PREPARED_RGB_BRIDGE',
        'host_suite':json.loads((a.host/'STAGE54_HOST_SUITE.json').read_text()),
        'private_preview':host,'original_prepared_rgb16_unchanged_exact':True,
        'original_colour_rgb16_unchanged_exact':True,'camera_matrix_unchanged_exact':True,
        'post_matrix_maximum_error':matrix_error,'highlight_java_jni_vs_numpy':highlight_difference,
        'highlight_java_jni_vs_original_cpu_sample':native_difference,
        'colour_core_vs_independent_trace_exact_channels':int(colour.size),
        'display_vs_independent_trace_exact_channels':int(display.size),
        'complete_numpy_vs_java_jni':complete_difference,
        'highlight_vs_original_display_change_not_accuracy_score':diff(rgb(packed[1]),rgb(packed[0])),
        'highlight_stage_clipping':stats,
        'input_domain':'existing post-gainmap bilinear prepared RGB16, already clamped',
        'clipping_levels':'65535 per prepared channel; not measured physical sensor saturation',
        'wb_source':'only selected DNG AsShotNeutral; max-normalized reciprocal ratios',
        'source_files_unchanged':True,'parameters_fitted_to_scene':False,'private_arrays_or_input_hashes_exported':False,
        'capture_renderer_changed':False,'device_tested':False,'original_raw_graph_reproduced':False,
        'lost_raw_headroom_recovered':False,'full_phocus_equivalence':False}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],json.dumps(complete_difference),flush=True)


if __name__=='__main__':main()
