#!/usr/bin/env python3
"""Independent NumPy oracle, capture binding, ASan/UBSan and ARM64 replay.

All raw arrays, derived grids and original capture metadata stay private.
Only aggregate counts and hashes are emitted to the optional safe report.
"""
import argparse
import copy
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

import numpy as np
from capture_binding import bind_capture, decode_bound_dng

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD = HERE.parent/'awb_rebuild_04_20261021/src'


class Frame(C.Structure):
    _fields_ = [(x,C.c_uint32) for x in ['width','height','row_stride_bytes','pixel_stride_bytes','left','top','right','bottom']] + [('cfa',C.c_int),('black_q16',C.c_int64*4),('white_code',C.c_uint16)]


class Block(C.Structure):
    _fields_ = [('site_sum_q16',C.c_int64*4),('site_count',C.c_uint32*4),('raw_brightness_sum_q16',C.c_int64)] + [(x,C.c_uint32) for x in ['sample_count','at_or_above_white_count','above_white_count','at_or_below_black_count']] + [('min_sample',C.c_uint16),('max_sample',C.c_uint16)]


class Stats(C.Structure):
    _fields_ = [('blocks',Block*1024),('input_sample_count',C.c_uint64),('vendor_e2_equivalence_proven',C.c_uint8)]


class Derived(C.Structure):
    _fields_ = [('mean',C.c_double*4),('mean_brightness',C.c_double),('red_gain_q12',C.c_uint32),('blue_gain_q12',C.c_uint32),('flags',C.c_uint32)]


class Grid(C.Structure):
    _fields_ = [('raw',Stats),('blocks',Derived*1024)] + [(x,C.c_uint32) for x in ['ratio_blocks','nonpositive_blocks','saturated_blocks','range_blocks']]


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def descriptor(w,h,cfa=0,black=(64,64,64,64),white=1023,stride=None,pixel=2,crop=None):
    return Frame(w,h,stride or w*pixel,pixel,*(crop or [0,0,w,h]),cfa,(C.c_int64*4)(*[int(x*65536) for x in black]),white)


def frame_from_binding(b):
    return Frame(b['width'],b['height'],b['row_stride_bytes'],b['pixel_stride_bytes'],*b['crop'],b['cfa'],(C.c_int64*4)(*b['black_q16']),b['white_code'])


def oracle(raw,f,g):
    """Block slicing is independent of the C scatter loop; exact integer sums."""
    pixels=np.ndarray((f.height,f.width),dtype='<u2',buffer=raw,strides=(f.row_stride_bytes,f.pixel_stride_bytes))
    region=pixels[f.top:f.bottom,f.left:f.right]
    qh,qw=region.shape[0]//2,region.shape[1]//2
    yedges=(np.arange(33)*qh+31)//32; xedges=(np.arange(33)*qw+31)//32
    # Colour -> position, independently specified for each Bayer arrangement.
    positions=[[(0,0),(0,1),(1,0),(1,1)],[(0,1),(0,0),(1,1),(1,0)],[(1,0),(1,1),(0,0),(0,1)],[(1,1),(1,0),(0,1),(0,0)]][f.cfa]
    black=np.array(list(f.black_q16),dtype=np.int64).reshape(2,2)
    expected_counts=[0,0,0,0]
    for by in range(32):
        for bx in range(32):
            i=by*32+bx;s=g.raw.blocks[i];d=g.blocks[i]
            patch=region[2*yedges[by]:2*yedges[by+1],2*xedges[bx]:2*xedges[bx+1]]
            sums=[];means=[];counts=[];below=0
            for ry,rx in positions:
                plane=patch[ry::2,rx::2].astype(np.int64);n=plane.size
                v=int(plane.sum())*65536-int(black[ry,rx])*n
                sums.append(v);counts.append(n)
                means.append(v/(n*(int(f.white_code)*65536-int(black[ry,rx]))))
                below+=int(np.count_nonzero(plane*65536<=black[ry,rx]))
            sat=int(np.count_nonzero(patch>=f.white_code));above=int(np.count_nonzero(patch>f.white_code))
            assert list(s.site_sum_q16)==sums and list(s.site_count)==counts
            assert (s.raw_brightness_sum_q16,s.sample_count,s.at_or_above_white_count,s.above_white_count,s.at_or_below_black_count,s.min_sample,s.max_sample)==(sum(sums),patch.size,sat,above,below,int(patch.min()),int(patch.max()))
            assert list(d.mean)==means
            assert math.isclose(d.mean_brightness,sum(means)*0.25,rel_tol=2e-15,abs_tol=1e-18)
            flags=int(min(means)<=0)|(2 if sat else 0);r=b=0
            if not flags&1:
                green=(means[1]+means[2])/2
                qr,qb=green/means[0]*4096,green/means[3]*4096
                if not (1<=qr<65536 and 1<=qb<65536):flags|=4
                elif not flags:r,b=int(qr),int(qb)
            assert (d.red_gain_q12,d.blue_gain_q12,d.flags)==(r,b,flags)
            expected_counts[0]+=flags==0
            for j,flag in enumerate([1,2,4],1):expected_counts[j]+=bool(flags&flag)
    assert [g.ratio_blocks,g.nonpositive_blocks,g.saturated_blocks,g.range_blocks]==expected_counts
    assert g.raw.input_sample_count==region.size and g.raw.vendor_e2_equivalence_proven==0


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--dng',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--ndk',type=Path,required=True);p.add_argument('--qemu',type=Path,required=True);p.add_argument('--firmware-root',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    sources=[HERE/'hb_phone_raw.c',OLD/'hb_awb_frame_stats.c',OLD/'hb_awb_stages.c']
    flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off']
    libpath=a.out/'libphone_raw.so'
    subprocess.run(['cc',*flags,'-shared','-fPIC',*map(str,sources),'-lm','-o',str(libpath)],check=True)
    lib=C.CDLL(str(libpath.resolve()));fn=lib.hb_phone_raw_build
    fn.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Frame),C.c_int,C.POINTER(Grid)];fn.restype=C.c_int
    synthetic=0;guards=0;cases=[];rng=np.random.default_rng(20261021)
    def run_case(name,raw,f,retain=False):
        nonlocal synthetic
        data=C.create_string_buffer(raw);before=bytes(data);g=Grid()
        assert fn(data,len(raw),C.byref(f),0,C.byref(g))==0
        assert bytes(data)==before;oracle(raw,f,g)
        if retain:
            (a.out/(name+'.raw')).write_bytes(raw);(a.out/(name+'.grid')).write_bytes(bytes(g))
            vals=[getattr(f,k) for k in ['width','height','row_stride_bytes','pixel_stride_bytes','left','top','right','bottom','cfa']]+list(f.black_q16)+[f.white_code]
            (a.out/(name+'.txt')).write_text(' '.join(map(str,vals))+'\n')
        return g
    # Non-square grids, nonuniform quad partitions, all CFAs, fractional/per-site black,
    # padding and pixels outside the selected crop; no implementation-derived goldens.
    for cfa in range(4):
        for index,(w,h,crop,pixel) in enumerate([(64,64,None,2),(130,98,None,4),(140,110,[2,4,136,106],3),(192,66,None,2)]):
            stride=w*pixel+13;f=descriptor(w,h,cfa,black=(63.9375,65.25,67.5,70.125),stride=stride,pixel=pixel,crop=crop)
            raw=bytearray([0xa5]*(stride*h));arr=np.ndarray((h,w),dtype='<u2',buffer=raw,strides=(stride,pixel));arr[:]=rng.integers(0,1300,(h,w),dtype=np.uint16)
            run_case(f'synthetic_{cfa}_{index}',bytes(raw),f,retain=cfa==3 and index==2);synthetic+=1
        for label,tile,white in [('positive',[[164,264],[264,464]],1023),('negative',[[63,64],[65,62]],1023),('saturated',[[1023,1024],[65535,64]],1023),('range',[[1,65534],[65534,1]],65535)]:
            f=descriptor(64,64,cfa,black=(0,0,0,0) if label=='range' else (64,64,64,64),white=white)
            raw=np.tile(np.array(tile,dtype='<u2'),(32,32)).tobytes();run_case(label,raw,f);synthetic+=1
    # Every rejecting call must preserve all output bytes; caller input remains untouched.
    base=descriptor(64,64);data=C.create_string_buffer(np.full((64,64),200,dtype='<u2').tobytes())
    invalid=[('width',63),('height',63),('cfa',4),('cfa',-1),('row_stride_bytes',1),('pixel_stride_bytes',1),('left',1),('right',66),('bottom',62),('white_code',0),('width',65536),('height',65537)]
    for key,value in invalid:
        f=Frame.from_buffer_copy(base);setattr(f,key,value);cases.append((f,len(data)-1,0,1))
    for black in [-1,1023*65536,65535*65536]:
        f=Frame.from_buffer_copy(base);f.black_q16[0]=black;cases.append((f,len(data)-1,0,1))
    cases.extend([(base,len(data)-2,0,1),(base,len(data)-1,1,2),(base,len(data)-1,-1,2)])
    for case_index,(f,size,history,want) in enumerate(cases):
        g=Grid();C.memset(C.byref(g),0xa5,C.sizeof(g));before=bytes(g)
        assert fn(data,size,C.byref(f),history,C.byref(g))==want and bytes(g)==before,case_index;guards+=1
    g=Grid();C.memset(C.byref(g),0xa5,C.sizeof(g));before=bytes(g)
    for ptr,fp,op in [(None,C.byref(base),C.byref(g)),(data,None,C.byref(g)),(data,C.byref(base),None)]:
        assert fn(ptr,len(data)-1,fp,0,op)==1 and bytes(g)==before;guards+=1
    j=json.loads(a.capture.read_text());original=copy.deepcopy(j);bound=[]
    for black_source in ['exported','dynamic','static']:
        binding=bind_capture(j,black_source);raw=decode_bound_dng(a.dng,j,binding);f=frame_from_binding(binding)
        start=time.perf_counter();grid=run_case('capture_'+black_source,raw,f,retain=True);elapsed=time.perf_counter()-start
        (a.out/('binding_'+black_source+'.json')).write_text(json.dumps(binding,indent=2)+'\n')
        bound.append({'black_source':black_source,'samples':grid.raw.input_sample_count,'ratio_blocks':grid.ratio_blocks,'nonpositive_blocks':grid.nonpositive_blocks,'saturated_blocks':grid.saturated_blocks,'range_blocks':grid.range_blocks,'host_build_and_oracle_seconds':elapsed})
    assert j==original
    # Mutate provenance independently of the pixel implementation.
    mutations=[('timestamp',lambda m:m['delivered_raw'].__setitem__('sensor_timestamp_ns','1')),
      ('frame',lambda m:m.__setitem__('frame_number',125)),('camera',lambda m:m['original_still']['sensor_provenance'].__setitem__('selected_calibration_camera_id','wrong')),
      ('callback',lambda m:m['original_still']['sensor_provenance'].__setitem__('callback_session_device_id','wrong')),
      ('unproven',lambda m:m['original_still']['sensor_provenance'].__setitem__('sensor_provenance_matched',False)),
      ('raw_target',lambda m:m['original_still']['sensor_provenance'].__setitem__('request_targets_recorded_raw_surface',False)),
      ('crop',lambda m:m['delivered_raw'].__setitem__('image_crop_rect',[1,0,4096,3072])),
      ('binned',lambda m:m['delivered_raw'].__setitem__('binned',True)),('stride',lambda m:m['delivered_raw'].__setitem__('row_stride_bytes',1)),
      ('capacity',lambda m:m['delivered_raw'].__setitem__('original_buffer_capacity_bytes',1)),
      ('cfa',lambda m:m['original_still']['selected_sensor_characteristics'].__setitem__('android.sensor.info.colorFilterArrangement',4)),
      ('white',lambda m:m['effective_photon_export'].__setitem__('white_level_raw_counts',0)),
      ('black',lambda m:m['effective_photon_export'].__setitem__('black_level_raw_counts',[float('nan')]*4)),
      ('matrix',lambda m:m['original_still']['selected_sensor_characteristics']['android.sensor.colorTransform1'][0].__setitem__('denominator',0)),
      ('logical',lambda m:m['original_still']['selected_sensor_characteristics']['android.request.availableCapabilities'].append(11)),
      ('pixel_mode',lambda m:m['original_still']['selected_raw_sensor_result'].__setitem__('android.sensor.pixelMode',1)),
      ('multiple',lambda m:m.__setitem__('input_frame_count',2)),('partial_copy',lambda m:m['delivered_raw'].__setitem__('copied_crop_x',2))]
    for name,edit in mutations:
        m=copy.deepcopy(j);edit(m)
        try:bind_capture(m,'exported')
        except (ValueError,KeyError,TypeError):pass
        else:raise AssertionError(name)
    m=copy.deepcopy(j);m['dng']['sha256']='0'*64
    try:decode_bound_dng(a.dng,m,bind_capture(m,'exported'))
    except ValueError:pass
    else:raise AssertionError('DNG identity')
    # Same actual capture through optimized host, sanitizer and API28 ARM64.
    probe_sources=[*sources,HERE/'phone_raw_probe.c'];outputs=[]
    sanitized=a.out/'phone_raw_sanitized'
    subprocess.run(['cc',*flags,'-fsanitize=address,undefined','-fno-omit-frame-pointer',*map(str,probe_sources),'-lm','-o',str(sanitized)],check=True)
    compiler=a.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang';android=a.out/'phone_raw_android28'
    subprocess.run([str(compiler),*flags,'-fPIE','-pie','-Wl,-z,max-page-size=16384',*map(str,probe_sources),'-lm','-o',str(android)],check=True)
    for name in ['capture_exported','capture_dynamic','synthetic_3_2']:
        expected=(a.out/(name+'.grid')).read_bytes()
        for label,command in [('sanitized',[str(sanitized)]),('android',[str(a.qemu),'-L',str(a.firmware_root),str(android)])]:
            target=a.out/(name+'.'+label+'.grid')
            env=dict(os.environ)
            if label=='sanitized':
                # This executor cannot inspect /proc tasks for LeakSanitizer.
                # Address/undefined checks remain enabled and fatal.
                env['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'
                env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
            run=subprocess.run([*command,str(a.out/(name+'.raw')),str(a.out/(name+'.txt')),str(target)],capture_output=True,text=True,timeout=60,env=env)
            (a.out/(name+'.'+label+'.log')).write_text(run.stdout+run.stderr)
            assert run.returncode==0,(label,run.stderr)
            assert target.read_bytes()==expected,(label,name);outputs.append({'case':name,'runtime':label,'exact_bytes':len(expected),'sha256':sha(target)})
    tracked=[*sources,HERE/'hb_phone_raw.h',HERE/'phone_raw_probe.c',Path(__file__),HERE/'capture_binding.py',OLD/'hb_awb_frame_stats.h',OLD/'hb_awb_stages.h',REPO/'hasselblad_device_validation_20261019/raw_audit/audit_dng.py']
    report={'status':'PASS','synthetic_frames':synthetic,'native_rejection_cases':guards,'metadata_rejection_cases':len(mutations)+1,'real_capture_variants':bound,'independent_block_comparisons':1024*(synthetic+len(bound)),'cross_runtime':outputs,'source_sha256':{str(p.relative_to(REPO)):sha(p) for p in tracked},'input_sha256':{'capture':sha(a.capture),'dng':sha(a.dng)},'binary_sha256':{p.name:sha(p) for p in [libpath,sanitized,android]},'sanitizers':{'address':True,'undefined':True,'leak':False,'leak_limitation':'Executor denies /proc task inspection'},'original_capture_unchanged':j==original,'phone_estimator_calibration_available':False,'vendor_e2_equivalence_proven':False,'automatic_controller_called':False,'apk_built':False,'photographic_colour_validated':False}
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','binary_sha256','cross_runtime','real_capture_variants']},indent=2))


if __name__=='__main__':main()
