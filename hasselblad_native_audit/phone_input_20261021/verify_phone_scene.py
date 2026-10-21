#!/usr/bin/env python3
"""Bound original RAW -> phone locus -> owned ordinary candidate kernels.

Policies in this verifier are TEST SWEEPS, never shipping defaults. Private
per-capture grids, candidate values, locus and complete traces stay in --out.
"""
import argparse
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess

import numpy as np
from capture_binding import bind_capture, decode_bound_dng
from temperature_binding import bind_temperature
from verify_phone_temperature import Input, Gains, descriptor as temperature_descriptor
from verify_phone_raw import Grid, Frame, descriptor as raw_descriptor, frame_from_binding

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
RUNTIME=HERE.parent/'awb_original_runtime_20261021'
OLD=HERE.parent/'awb_rebuild_04_20261021/src'


class Policy(C.Structure):
    _fields_=[('center_tint',C.c_float),('radius_q12',C.c_uint32),('neighbor_factor',C.c_uint32),
              ('minimum_blocks',C.c_uint32),('minimum_brightness',C.c_double),('maximum_brightness',C.c_double)]


class Trace(C.Structure):
    _fields_=[(k,C.c_uint32) for k in ['reason','classified','locus_index','survives']]+[
        ('distance_q12',C.c_float),('weight_before',C.c_uint16),('weight_after',C.c_uint16)]


class Result(C.Structure):
    _fields_=[(k,C.c_uint32) for k in ['decision','native_status','raw_valid','admitted','classified','retained']]+[
        ('gain_q12',C.c_uint32*3),('neutral',C.c_float*3),('temperature',C.c_float*3),('blocks',Trace*1024)]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(compiler,out,label,extra,shared=False):
    sources=[HERE/'hb_phone_scene.c',HERE/'hb_phone_temperature.c',HERE/'hb_phone_raw.c',
             *[RUNTIME/(name+'.c') for name in ['hb_temperature','hb_user_controls',
               'hb_scene_optimizer','hb_scene_candidates','hb_scene_filter']],
             OLD/'hb_awb_frame_stats.c',OLD/'hb_awb_stages.c']
    flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
           '-ffp-contract=off','-ffunction-sections','-fdata-sections',*extra]
    objects=[]
    for source in sources:
        obj=out/(label+'_'+source.stem+'.o');objects.append(str(obj))
        subprocess.run([str(compiler),*[f for f in flags if not f.startswith('-Wl,')],
                        *(['-fvisibility=hidden'] if source.parent!=HERE else []),
                        '-c',str(source),'-o',str(obj)],check=True)
    target=out/('libphone_scene.so' if shared else 'phone_scene_'+label)
    subprocess.run([str(compiler),*flags,*(['-shared'] if shared else ['-pie',str(HERE/'phone_scene_probe.c')]),
                    *objects,'-Wl,--gc-sections,-z,defs','-lm','-o',str(target)],check=True)
    return target,sources


def oracle(grid,policy,locus,result):
    """Independent double-distance scan, Python DFS and integer accumulation.

    The retained native filter uses linear neighbor offsets, including row
    edges. Reproduce that documented behavior rather than claiming 2D topology.
    """
    gains=np.array([[b.red_gain_q12,b.blue_gain_q12] for b in grid.blocks],dtype=np.int64)
    flags=np.array([b.flags for b in grid.blocks]);brightness=np.array([b.mean_brightness for b in grid.blocks])
    reason=np.zeros(1024,dtype=int);reason[flags!=0]=1
    valid=reason==0
    reason[valid&((brightness<policy.minimum_brightness)|(brightness>policy.maximum_brightness))]=2
    reason[(reason==0)&np.any(gains>32767,axis=1)]=3
    admitted=reason==0
    distances=np.sum((gains[:,None,:]-locus[None,:,1:])**2,axis=2)
    nearest=np.argmin(distances,axis=1)
    d2=distances[np.arange(1024),nearest];distance=np.sqrt(d2)
    classified=admitted&(d2<=policy.radius_q12**2)
    weight=np.zeros(1024,dtype=np.uint16)
    value=(1-distance[classified]/policy.radius_q12).astype(np.float32)
    weight[classified]=np.maximum(1,(np.float32(255)*value).astype(np.uint16))
    filtered=weight.copy();visited=set();threshold=policy.radius_q12//policy.neighbor_factor
    # The native filter is depth-first and removes components of <=3 blocks.
    for i in range(1024):
        if not weight[i] or i in visited:continue
        stack=[i];component=[];visited.add(i)
        while stack:
            index=stack.pop();component.append(index)
            for offset in [-33,-32,-31,-1,1,31,32,33]:
                other=index+offset
                if 0<=other<1024 and other not in visited and weight[other] and np.all(abs(gains[index]-gains[other])<threshold):
                    stack.append(other);visited.add(other)
        if len(component)<=3:filtered[component]=0
    assert (result.raw_valid,result.admitted,result.classified,result.retained)==(
        int(sum(flags==0)),int(sum(admitted)),int(sum(classified)),int(sum(filtered!=0)))
    for i,t in enumerate(result.blocks):
        assert t.reason==reason[i] and t.classified==classified[i]
        assert (t.weight_before,t.weight_after,t.survives)==(weight[i],filtered[i],filtered[i]!=0)
        if admitted[i]:
            assert t.locus_index==nearest[i] and t.distance_q12==np.float32(distance[i])
        else:assert t.locus_index==0 and t.distance_q12==0
    if sum(filtered!=0)<policy.minimum_blocks:
        assert result.decision==0 and list(result.gain_q12)==[0,0,0] and list(result.neutral)==[0,0,0]
    elif result.decision==1:
        total=sum(int(x) for x in filtered); red=sum(int(gains[i,0])*int(filtered[i]) for i in range(1024))//total
        blue=sum(int(gains[i,1])*int(filtered[i]) for i in range(1024))//total
        assert list(result.gain_q12)==[red,4096,blue]
        assert list(result.neutral)==[np.float32(np.float32(4096)/np.float32(red)),1,np.float32(np.float32(4096)/np.float32(blue))]
        assert all(math.isfinite(x) for x in result.temperature) and result.temperature[2]<=.003
    else:
        assert result.decision==2 and result.native_status!=0 and list(result.gain_q12)==[0,0,0]


def main():
    p=argparse.ArgumentParser()
    for name in ['capture','dng','out','report','ndk','qemu','firmware-root']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    libpath,sources=build('cc',a.out,'host',['-fPIC'],True);lib=C.CDLL(str(libpath.resolve()))
    create=lib.hb_phone_scene_create;create.argtypes=[C.POINTER(Input),C.POINTER(Policy),C.POINTER(C.c_void_p)];create.restype=C.c_int
    destroy=lib.hb_phone_scene_destroy;destroy.argtypes=[C.c_void_p]
    run=lib.hb_phone_scene_run;run.argtypes=[C.c_void_p,C.POINTER(Grid),C.POINTER(Result)];run.restype=C.c_int
    get_locus=lib.hb_phone_scene_locus;get_locus.argtypes=[C.c_void_p,C.c_void_p];get_locus.restype=C.c_int
    raw_build=lib.hb_phone_raw_build;raw_build.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Frame),C.c_int,C.POINTER(Grid)];raw_build.restype=C.c_int
    temp_create=lib.hb_phone_temperature_create;temp_create.argtypes=[C.POINTER(Input),C.POINTER(C.c_void_p)];temp_create.restype=C.c_int
    temp_destroy=lib.hb_phone_temperature_destroy;temp_destroy.argtypes=[C.c_void_p]
    temp_forward=lib.hb_phone_temperature_to_gain;temp_forward.argtypes=[C.c_void_p,C.c_uint32,C.c_float,C.POINTER(Gains)];temp_forward.restype=C.c_int
    j=json.loads(a.capture.read_text());original=json.dumps(j,sort_keys=True)
    binding=bind_temperature(j,'exported');inp=temperature_descriptor(binding['anchors']);original_input=bytes(inp)
    temp=C.c_void_p();assert temp_create(C.byref(inp),C.byref(temp))==0
    def make_grid(raw,frame):
        data=C.create_string_buffer(raw);g=Grid()
        assert raw_build(data,len(raw),C.byref(frame),0,C.byref(g))==0
        assert data.raw[:len(raw)]==raw
        return g
    real=[]
    for black in ['exported','dynamic']:
        bound=bind_capture(j,black);raw=decode_bound_dng(a.dng,j,bound)
        grid=make_grid(raw,frame_from_binding(bound));real.append(('capture_'+black,grid))
        (a.out/('binding_'+black+'.json')).write_text(json.dumps(bound,indent=2)+'\n')
    # Synthetic RAW mosaics: neutral illuminants, spatial islands, mixed
    # illuminants, saturation, low light, unequal greens and signed-filter limit.
    frames=[];tiles={}
    for ct in [2856,4000,5500,6500,9000]:
        gains=Gains();assert temp_forward(temp,ct,0,C.byref(gains))==0
        r,g,b=gains.gain_q12
        for level in [.002,.03,.25,.8]:
            tile=np.rint(64+959*np.array([[level*g/r,level],[level,level*g/b]])).clip(0,65535).astype('<u2')
            raw=np.tile(tile,(64,64));frames.append((f'neutral_{ct}_{level}',raw))
            if level==.25:tiles[ct]=tile
    base=np.full((128,128),64,dtype='<u2')
    for count in [1,3,4,15,16]:
        raw=base.copy()
        for x in range(count):raw[0:4,x*4:x*4+4]=np.tile(tiles[5500],(2,2))
        frames.append((f'island_{count}',raw))
    mixed=np.tile(tiles[4000],(64,64));mixed[:,64:]=np.tile(tiles[6500],(64,32));frames.append(('mixed',mixed))
    frames.extend([('saturated',np.full((128,128),1023,dtype='<u2')),
                   ('below_black',np.full((128,128),63,dtype='<u2')),
                   ('signed_range',np.tile(np.array([[66,84],[84,84]],dtype='<u2'),(64,64))),
                   ('unequal_greens',np.tile(np.array([[180,210],[230,145]],dtype='<u2'),(64,64)))])
    synthetic=[(name,make_grid(raw.tobytes(),raw_descriptor(128,128))) for name,raw in frames]
    temp_destroy(temp)
    totals={'cases':0,'block_oracle_comparisons':0,'diagnostic_candidates':0,'no_candidates':0,'temperature_rejections':0}
    captures=[];selected=[];model_rejections=0;locus_basis_checks=0
    # Explicit test policies. No selected policy is persisted as a default.
    policies=[Policy(0,radius,2,16,.005,.9) for radius in [128,256,512,1024,2048,4096]]
    for policy_index,policy in enumerate(policies):
        s=C.c_void_p();assert create(C.byref(inp),C.byref(policy),C.byref(s))==0
        native_locus=(C.c_uint32*(81*3))();assert get_locus(s,native_locus)==0
        locus=np.array(native_locus,dtype=np.int64).reshape(81,3)
        temp=C.c_void_p();assert temp_create(C.byref(inp),C.byref(temp))==0
        for i,(ct,r,b) in enumerate(locus):
            g=Gains();assert temp_forward(temp,int(ct),policy.center_tint,C.byref(g))==0
            assert [r,b]==[int(g.gain_q12[k])*4096//g.gain_q12[1] for k in [0,2]]
            locus_basis_checks+=1
        temp_destroy(temp)
        try:
            for name,grid in [*real,*synthetic]:
                before=bytes(grid);result=Result();assert run(s,C.byref(grid),C.byref(result))==0
                assert bytes(grid)==before;oracle(grid,policy,locus,result)
                totals['cases']+=1;totals['block_oracle_comparisons']+=1024
                totals[['no_candidates','diagnostic_candidates','temperature_rejections'][result.decision]]+=1
                if name.startswith('capture'):
                    captures.append({'case':name,'policy_test_index':policy_index,'radius_q12':policy.radius_q12,
                                     'decision':result.decision,'classified':result.classified,'retained':result.retained,
                                     'gains':list(result.gain_q12),'temperature':list(result.temperature)})
                retain=(name=='capture_exported' and policy_index in [0,5]) or (policy_index==3 and name in ['neutral_5500_0.25','mixed','island_3'])
                if retain:
                    key=name+'_p'+str(policy_index);selected.append(key)
                    (a.out/(key+'.input')).write_bytes(bytes(inp)+bytes(policy))
                    (a.out/(key+'.grid')).write_bytes(bytes(grid))
                    (a.out/(key+'.expected')).write_bytes(bytes(result))
                    (a.out/(key+'.locus')).write_bytes(bytes(native_locus))
                # Independently known support topology for same neutral block.
                if policy_index==3 and name=='island_3':assert result.retained==0 and result.decision==0
                if policy_index==3 and name=='island_16':assert result.retained==16 and result.decision==1
                if name=='signed_range':assert result.raw_valid==1024 and all(t.reason==3 for t in result.blocks)
        finally:destroy(s)
    # A valid temperature model can still be invalid for this scene domain:
    # the blue/red gain cap or signed filter domain must reject model creation.
    bad_model=Input.from_buffer_copy(inp)
    for anchor in bad_model.anchor:
        for k in range(3):anchor.color[k]*=.001
    sentinel=C.c_void_p(1234)
    assert create(C.byref(bad_model),C.byref(policies[0]),C.byref(sentinel))==3 and sentinel.value==1234
    model_rejections+=1
    assert bytes(inp)==original_input and json.dumps(j,sort_keys=True)==original
    (a.out/'capture_policy_sweep.json').write_text(json.dumps(captures,indent=2)+'\n')
    host,_=build('cc',a.out,'optimized',['-fPIE'])
    san,_=build('cc',a.out,'sanitized',['-fPIE','-fsanitize=address,undefined','-fno-omit-frame-pointer'])
    compiler=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang'
    android,_=build(compiler,a.out,'android28',['-fPIE','-Wl,-z,max-page-size=16384'])
    cross=[]
    for key in selected:
        expected=(a.out/(key+'.expected')).read_bytes()
        for label,cmd in [('optimized',[str(host)]),('sanitized',[str(san)]),
                          ('android28',[str(a.qemu),'-L',str(a.firmware_root),str(android)])]:
            output=a.out/(key+'.'+label+'.result')
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            process=subprocess.run([*cmd,str(a.out/(key+'.input')),str(a.out/(key+'.grid')),str(output)],
                                   capture_output=True,text=True,timeout=60,env=env)
            (a.out/(key+'.'+label+'.log')).write_text(process.stdout+process.stderr)
            assert process.returncode==0,(key,label,process.stderr)
            assert '16 guards' in process.stderr and output.read_bytes()==expected,(key,label)
            cross.append({'case':key,'runtime':label,'exact_bytes':len(expected),'sha256':sha(output)})
    tracked=[*sources,HERE/'hb_phone_scene.h',HERE/'phone_scene_probe.c',Path(__file__),
             HERE/'capture_binding.py',HERE/'temperature_binding.py',HERE/'verify_phone_raw.py',
             HERE/'verify_phone_temperature.py',HERE/'hb_phone_raw.h',HERE/'hb_phone_temperature.h',
             *sorted(RUNTIME.glob('hb_*.h')),OLD/'hb_awb_frame_stats.h',OLD/'hb_awb_stages.h']
    report={'status':'PASS',**totals,'real_capture_variants':2,'synthetic_raw_frames':len(synthetic),
            'explicit_test_policies':len(policies),'locus_green_basis_checks':locus_basis_checks,
            'model_rejections':model_rejections,'native_guards_per_probe':16,
            'cross_runtime':cross,'input_and_metadata_unchanged':True,
            'scene_route':'phone exhaustive locus classification -> owned weighting/filter/accumulation/optimizer -> calibrated temperature validation',
            'full_automatic_controller_called':False,'automatic_initializer_used':False,
            'shipping_profile_selected':False,'hal_neutral_used_for_selection':False,
            'fresh_candidate_is_diagnostic_only':True,'photographic_colour_validated':False,'apk_built':False,
            'real_policy_sensitivity':'Radii128..2048 reject; radius4096 produces candidates in both black interpretations. This is not calibration ground truth.',
            'sanitizers':{'address':True,'undefined':True,'leak':False,'leak_limitation':'Executor denies /proc task inspection'},
            'source_sha256':{str(f.relative_to(REPO)):sha(f) for f in tracked},
            'input_sha256':{'capture':sha(a.capture),'dng':sha(a.dng)},
            'binary_sha256':{f.name:sha(f) for f in [libpath,host,san,android]}}
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','input_sha256','binary_sha256','cross_runtime']},indent=2))


if __name__=='__main__':main()
