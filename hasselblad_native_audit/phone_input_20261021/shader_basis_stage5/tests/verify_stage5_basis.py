#!/usr/bin/env python3
"""Independent source-matched CPU projection checks.

The PRIMARY path (no capture) uses synthetic RAW/map values, verifying API,
float16 quantization and GL_LINEAR integer pixel sampling. With --capture,
--dng and --domain-json, a separate private replay validates the exact original
DNG/Camera2 pairing and compares projected Stage4 *abstention*, never WB.
This does not claim byte-equal GPU FP16 shader parity or authorised colour.
"""
import argparse,ctypes as C,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
import tifffile

ROOT=Path(__file__).resolve().parents[1]
STAGE4=(ROOT.parent/'neutral_observation' if (ROOT.parent/'neutral_observation').is_dir() else ROOT.parent/'hasselblad_stage4')
sys.path.insert(0,str(STAGE4/'tests'))
from verify_phone_neutral_observation import Frame,Domain,Policy,Result,build as build_stage4,load_domain,run as run_stage4

class Input(C.Structure):
    _fields_=[('raw_le16',C.POINTER(C.c_uint8)),('raw_bytes',C.c_size_t),
      ('width',C.c_uint32),('height',C.c_uint32),('row_stride_bytes',C.c_uint32),
      ('cfa',C.c_uint32),('black_raw_code',C.c_uint32),('white_raw_code',C.c_uint32),
      ('lens_map_rg_gb_b',C.POINTER(C.c_float)),('map_width',C.c_uint32),('map_height',C.c_uint32),('map_floats',C.c_size_t),
      ('study_basis',C.c_uint32),('timestamp_ns',C.c_uint64),('exposure_ns',C.c_uint64),
      ('ISO',C.c_uint32),('proven_sensor_and_frame',C.c_uint32),('original_single_raw',C.c_uint32)]
class Output(C.Structure):
    _fields_=[('schema',C.c_uint32),('study_basis',C.c_uint32),('observed_pixels',C.c_uint32),
      ('map_quantized_as_fp16',C.c_uint32),('green_channel_average',C.c_uint32),
      ('saturated_blocks',C.c_uint32),('invalid_ratio_blocks',C.c_uint32),
      ('study_only',C.c_uint32),('render_permitted',C.c_uint32),('observation',Frame)]

def build(out,compiler='cc',opt='-O2',label='host'):
    out.mkdir(parents=True,exist_ok=True)
    path=out/f'libstage5_{label}.so'
    subprocess.run([compiler,'-std=c11',opt,'-Wall','-Wextra','-Werror',
      '-ffp-contract=off','-fPIC','-shared',
      '-I',str(ROOT/'src'),'-I',str(STAGE4/'src'),
      str(ROOT/'src'/'hb_phone_stage5_basis.c'),'-lm','-o',str(path)],check=True)
    lib=C.CDLL(str(path.resolve()))
    lib.hb_s5_project.argtypes=[C.POINTER(Input),C.POINTER(Output)]
    lib.hb_s5_project.restype=C.c_int
    return lib,path

def invoke(lib, raw, mp, study=2,black=64,white=1023):
    assert raw.dtype==np.uint16 and raw.ndim==2 and raw.flags.c_contiguous
    assert mp.dtype==np.float32 and mp.ndim==3 and mp.shape[2]==4 and mp.flags.c_contiguous
    h,w=raw.shape; my,mx,_=mp.shape
    inp=Input(raw.view(np.uint8).ctypes.data_as(C.POINTER(C.c_uint8)),int(raw.nbytes),
        w,h,w*2,0,black,white,mp.ctypes.data_as(C.POINTER(C.c_float)),mx,my,int(mp.size),study,
        219959124714440,24000000,50,1,1)
    out=Output()
    status=lib.hb_s5_project(C.byref(inp),C.byref(out))
    return status,inp,out

def gl_indices(coord,n,frame):
    z=(np.asarray(coord,dtype=np.float64)*n/frame)-0.5
    base=np.floor(z).astype(np.intp); t=z-base
    return np.clip(base,0,n-1),np.clip(base+1,0,n-1),t

def oracle(raw,mp,study=2,black=64,white=1023):
    h,w=raw.shape;mh,mw,_=mp.shape
    # Shader uploads the original Camera2 map as FLOAT16. Independent numpy
    # conversion, unlike C's bitfield-based float32->binary16 implementation.
    map16=mp.astype(np.float16).astype(np.float32)
    allmeans=[]
    # CFA site pixel lattice, but use actual pixel (not Bayer-cell) UV.
    for site,(ry,rx) in enumerate(((0,0),(0,1),(1,0),(1,1))):
        yy=np.arange(ry,h,2,dtype=np.intp)
        xx=np.arange(rx,w,2,dtype=np.intp)
        ya,yb,fy=gl_indices(yy,mh,h)
        xa,xb,fx=gl_indices(xx,mw,w)
        def sample(ch):
            z=map16[:,:,ch]
            a=z[ya[:,None],xa[None,:]]
            b=z[ya[:,None],xb[None,:]]
            c=z[yb[:,None],xa[None,:]]
            d=z[yb[:,None],xb[None,:]]
            return (a*(1-fx)+b*fx)*(1-fy[:,None])+(c*(1-fx)+d*fx)*fy[:,None]
        pixel=(raw[ry::2,rx::2].astype(np.float64)-black)/(white-black)
        if study==2:
            red=sample(0);green=(sample(1)+sample(2))*.5;blue=sample(3)
            mean=(red+green+blue)/3
            factor=[red,green,green,blue][site]/np.maximum(mean,1e-4)
            pixel*=factor
        block=pixel.reshape(32,h//64,32,w//64).mean(axis=(1,3)).ravel()
        allmeans.append(block)
    return np.stack(allmeans,axis=1)

def frame_means(out):
    return np.asarray([[float(x) for x in b.mean] for b in out.observation.blocks])

def assert_aligned(lib,raw,mp,study,black=64,white=1023):
    status,inp,out=invoke(lib,raw,mp,study,black=black,white=white)
    assert status==0,(status,raw.shape,study)
    measured=frame_means(out)
    expected=oracle(raw,mp,study,black=black,white=white)
    maxerror=float(np.max(np.abs(measured-expected)))
    assert maxerror<3e-12,maxerror
    assert out.study_only==1 and out.render_permitted==0 and out.observation.basis==(1 if study==1 else 2)
    assert out.observation.bound_to_physical_sensor_and_frame==1 and out.observation.original_single_raw_proven==1
    assert out.observed_pixels==int(raw.size) and out.schema==1
    return maxerror,inp,out

def negative_tests(lib,inp):
    checks=0
    for key,val,expected in [
      ('width',62,3),('height',63,3),('cfa',3,3),('row_stride_bytes',inp.row_stride_bytes+2,3),
      ('white_raw_code',64,3),('map_width',1,3),('map_height',1,3),('study_basis',3,3),
      ('timestamp_ns',0,2),('proven_sensor_and_frame',0,2),('original_single_raw',0,2),
      ('ISO',0,2),('raw_bytes',inp.raw_bytes-2,3),('map_floats',inp.map_floats-1,4)]:
        temp=Input.from_buffer_copy(bytes(inp));setattr(temp,key,val)
        output=Output();C.memset(C.byref(output),0xa5,C.sizeof(output));initial=bytes(output)
        result=lib.hb_s5_project(C.byref(temp),C.byref(output))
        assert result==expected,(key,result,expected)
        assert bytes(output)==initial, 'API modified output after '+key
        checks+=1
    output=Output();C.memset(C.byref(output),0xa5,C.sizeof(output));initial=bytes(output)
    assert lib.hb_s5_project(None,C.byref(output))==1 and bytes(output)==initial
    checks+=1
    return checks

def synthetic(lib):
    rng=np.random.default_rng(20261022)
    raw=rng.integers(70,650,size=(64,64),dtype=np.uint16)
    mp=(rng.uniform(0.9,5.1,size=(3,4,4))).astype('float32')
    errs=[]
    for study in (1,2):
        e,inp,out=assert_aligned(lib,raw,mp,study)
        errs.append(e)
    neg=negative_tests(lib,inp)
    # Constant test and exact-on-edge sample tests defend clamping and the
    # 0.5-texel texture coordinate offset at x=0, y=0 and x=w-1,y=h-1.
    raw=np.full((64,64),100,dtype=np.uint16)
    mp=np.array([[[1.0,1.3,1.7,2.0],[2,2.3,2.7,3]],
                 [[2,2.1,2.4,2.7],[4,4.1,4.4,4.7]]],dtype=np.float32)
    errs.append(assert_aligned(lib,raw,mp,2)[0])
    # Preserve even G-site split in stage4 ABI and exact Q12 ratio truncation.
    valid=assert_aligned(lib,raw,mp,1)[2]
    b=valid.observation.blocks[0]
    assert b.red_gain_q12==4096 and b.blue_gain_q12==4096
    return neg,max(errs)

def replay_private(lib,capture_path,dng,domain_path,private_report):
    capture=json.loads(capture_path.read_text())
    domain_json=json.loads(domain_path.read_text())
    with dng.open('rb') as fp:sha=hashlib.file_digest(fp,'sha256').hexdigest()
    assert capture['dng']['sha256']==sha and capture['dng']['bytes']==dng.stat().st_size
    assert str(domain_json['source_frame_number'])==capture['frame_number']==capture['original_still']['selected_result_frame_number']
    assert domain_json['source_sensor_timestamp_ns']==capture['delivered_raw']['sensor_timestamp_ns']
    assert capture['original_still']['sensor_provenance']['sensor_provenance_matched']
    map_json=capture['original_still']['selected_raw_sensor_result']['android.statistics.lensShadingCorrectionMap']
    mp=np.ascontiguousarray(np.asarray(map_json['gains'],np.float32).reshape(map_json['rows'],map_json['columns'],4))
    original=capture['original_still']['selected_raw_sensor_result']
    black=original['android.sensor.dynamicBlackLevel']
    assert len(black)==4 and all(x==black[0] for x in black)
    white=original['android.sensor.dynamicWhiteLevel']
    assert black[0]==int(black[0]) and isinstance(white,int)
    raw=np.ascontiguousarray(tifffile.imread(dng).astype(np.uint16))
    results=[]
    stage4,_=build_stage4(ROOT/'artifacts')
    domain=load_domain(domain_json)
    for study in (1,2):
        err,inp,out=assert_aligned(lib,raw,mp,study,black=int(black[0]),white=white)
        assert out.saturated_blocks==0 and out.invalid_ratio_blocks==0
        row={'basis':'original_unshaded' if study==1 else 'hypothetical_photon_relative_lens_gain',
             'max_normalized_site_mean_abs_error':err,'result':[]}
        for radius in [128,256,512,1024]:
            policy=Policy(radius,128,16,.005,.9,.1)
            q=run_stage4(stage4,domain,out.observation,policy)
            assert q.render_permitted==0 and q.calibrated_policy==0
            row['result'].append({'radius':radius,'near_valid_grid':q.near_valid_knot,
                         'largest_spatial_component':q.largest_spatial_component,
                         'abstain_decision':q.decision})
        results.append(row)
    report={'scope':'Private verified DNG replay, no GL execution and no selected white balance',
            'frame_number':capture['frame_number'],'sensor':capture['original_still']['sensor_provenance']['selected_calibration_camera_id'],'source_dng_sha256':sha,
            'raw_unmodified':True,'render_applied':False,'results':results}
    private_report.parent.mkdir(parents=True,exist_ok=True)
    private_report.write_text(json.dumps(report,indent=2)+'\n')
    return results

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--private-replay',action='store_true')
    for name in ['capture','dng','domain-json','private-report']:
        ap.add_argument('--'+name,type=Path)
    a=ap.parse_args()
    results=[]
    for compiler,opt,label in [('cc','-O0','gcc_o0'),('cc','-O2','gcc_o2'),('clang','-O2','clang_o2')]:
        lib,path=build(ROOT/'artifacts',compiler,opt,label)
        neg,err=synthetic(lib)
        results.append({'build':label,'negative_cases':neg,'max_synthetic_oracle_error':err,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    private=None
    if a.private_replay:
        lib,_=build(ROOT/'artifacts')
        assert all((a.capture,a.dng,a.domain_json,a.private_report)), 'all private replay paths are required'
        private=replay_private(lib,a.capture,a.dng,a.domain_json,a.private_report)
    public={'schema':'hasselblad-stage5-color-basis-verification-v1',
            'status':'PASS','n_builds':len(results),'negative_cases_per_build':results[0]['negative_cases'],
            'source':'Standalone C pixel-wise full-frame RGGB reference and independent Python float64/FP16 texture oracle',
            'max_synthetic_oracle_error':max(r['max_synthetic_oracle_error'] for r in results),
            'private_capture_replayed':bool(private),
            'device_gpu_parity':False,'production_color_calibrated':False,'render_modified':False,
            'no_render_neutral_generated':True,'no_shutter_hook':True}
    a.out.parent.mkdir(exist_ok=True,parents=True)
    a.out.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps(public,indent=2))
if __name__=='__main__':main()
