#!/usr/bin/env python3
"""Private Stage44 tone/LUT isolation and bounded camera-reference benchmark.

All photo data and calibration arrays stay in --out. Only the explicit safe
receipt is suitable for public git. No fitted colour correction is produced.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.optimize import minimize_scalar
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'phocus_port_stage42'),str(ROOT/'isp_3fr_stage41k'),str(ROOT/'isp_3fr_stage41l')]
from prepare_preview42 import load_private,y,srgb,display
from core42 import Core
from test_shared_render41k import preview_to_srgb,split_masks,measurements
from test_highlights41l import roi_masks

def hashfile(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def multiply(pixels,matrix):
    p=np.asarray(pixels,np.float64);m=np.asarray(matrix).reshape(3,3)
    return np.stack([(p[...,0]*m[c,0]+p[...,1]*m[c,1])+p[...,2]*m[c,2] for c in range(3)],-1)
def trace(pixels,p,display_matrix,exponent):
    """Independent vectorized trace; exact RGB16 assertion against unchanged C."""
    grid,curve=p._arrays
    src=np.asarray(pixels,np.float64)*np.asarray(p.wb)*p.exposure
    yc=multiply(src,np.asarray(p.first));Y=yc[...,0];valid=Y>0
    denom=np.where(valid,Y,1)
    coords=yc[...,1:]/denom[...,None]*32+np.array([p.bias_x,p.bias_y])
    xy=np.clip(coords,0,np.array([p.width-1,p.height-1]))
    x,yv=xy[...,0],xy[...,1];x0=x.astype(int);y0=yv.astype(int)
    x1=np.minimum(x0+1,p.width-1);y1=np.minimum(y0+1,p.height-1)
    dx=(x-x0)[...,None];dy=(yv-y0)[...,None]
    top=grid[y0,x0]*(1-dx)+grid[y0,x1]*dx;bottom=grid[y1,x0]*(1-dx)+grid[y1,x1]*dx
    chroma=(top*(1-dy)+bottom*dy)/32
    s=np.asarray(p.shadow);weight=np.where(Y>s[0],1,(s[1]*Y+s[2])*Y+s[3]);weight=np.clip(weight,0,1)
    cb=chroma[...,0]*Y*weight;cr=chroma[...,1]*Y*weight;k=np.asarray(p.second).reshape(3,3)
    internal=np.stack([(Y+k[c,1]*cb)+k[c,2]*cr for c in range(3)],-1)
    index=np.clip(internal,0,65535).astype(int);out=curve[index].astype(np.uint16);out[~valid]=0
    decoded=(out.astype(float)/65536)**exponent;linear=multiply(decoded,display_matrix)
    total=out.size;v=valid[...,None]
    count=lambda mask:int(np.count_nonzero(mask))
    stats={'pixels':out.size//3,'nonpositive_luminance_pixels':count(~valid),
        'lut_coordinate_clamped_pixels':count(valid&np.any(coords!=xy,axis=-1)),
        'pre_curve_below_zero_channels':count((internal<0)&v),
        'pre_curve_above_65535_channels':count((internal>65535)&v),
        'post_curve_code_65535_channels':count(out==65535),
        'display_linear_below_zero_channels':count(linear<0),
        'display_linear_above_one_channels':count(linear>1),
        'display_linear_above_one_pct':count(linear>1)*100/total,
        'display_rgb8_zero_channels':count(srgb(linear)==0),
        'display_rgb8_255_channels':count(srgb(linear)==255)}
    return out,srgb(linear),stats

def diff(a,b):
    d=np.abs(a.astype(float)-b.astype(float))
    return {'mean_abs_rgb8':float(d.mean()),'p95_abs_rgb8':float(np.percentile(d,95)),
        'max_abs_rgb8':float(d.max()),'pixels_with_any_change_gt_2_pct':float((d.max(-1)>2).mean()*100)}

def read_bundle(path):
    b=path.read_bytes();assert b[:8]==b'HB42RAW1' and hashlib.sha256(b[:-32]).digest()==b[-32:]
    w,h,gw,gh,owner,orientation,temp,model,film,space=struct.unpack_from('<10i',b,8)
    values=np.frombuffer(b,dtype='<f8',count=38,offset=48).copy();at=48+304
    grid=np.frombuffer(b,dtype='<f8',count=gw*gh*2,offset=at).reshape(gh,gw,2).copy();at+=gw*gh*16
    curve=np.frombuffer(b,dtype='<f4',count=65536,offset=at).copy();at+=65536*4+32
    digest=b[at:at+32];at+=32
    rgb=np.frombuffer(b,dtype='<u2',count=w*h*3,offset=at).reshape(h,w,3).copy();at+=w*h*6
    baseline=np.frombuffer(b,dtype=np.uint8,count=w*h*3,offset=at).reshape(h,w,3).copy()
    return rgb,baseline,values,grid,curve,digest,orientation

def panel(items,path,heading):
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
    small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
    out=Image.new('RGB',(1240,100+len(items)*390),(24,27,30));draw=ImageDraw.Draw(out)
    draw.text((20,20),heading,fill='white',font=font)
    for row,(label,images) in enumerate(items):
        for col,(name,array) in enumerate(images):
            x=20+col*305;y0=100+row*390
            im=Image.fromarray(array);im.thumbnail((285,340));out.paste(im,(x+(285-im.width)//2,y0+34))
            draw.text((x,y0),label+' · '+name,fill='white',font=small)
    out.save(path)

def main():
    p=argparse.ArgumentParser()
    for key in ('apk','bundle','cache_dir','out','safe_receipt'):p.add_argument('--'+key.replace('_','-'),required=True,type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    source_paths=[a.apk,a.bundle]+[a.cache_dir/(label+'_analysis.npz') for label in 'ABCD']
    before={str(p):hashfile(p) for p in source_paths}
    elf,profile=load_private(a.apk);B,A,W=y.matrix_constants(elf)
    core=Core(a.out/'private-core44.so');neutral_curve=y.curve_oracle(elf,7,1)
    rgb,baseline,v,grid,curve,digest,orientation=read_bundle(a.bundle)
    gy,gx=np.mgrid[:89,:105];identity=np.stack([gx-20,gy-32],-1).astype(float)
    D=v[28:37].reshape(3,3);exponent=v[37];first=v[:9].reshape(3,3);second=v[9:18].reshape(3,3)
    no_shadow=np.array([2,0,0,1]);native_shadow=v[18:22]
    configs={'adapter_only':(identity,neutral_curve,no_shadow),'shadow_only':(identity,neutral_curve,native_shadow),
        'tone_shadow':(identity,curve,native_shadow),'lut_shadow':(grid,neutral_curve,native_shadow),'full':(grid,curve,native_shadow)}
    outputs={'baseline':baseline};phone={}
    for name,(g,c,s) in configs.items():
        params=core.params(first,second,g,False,c,s)
        codes=core.render(rgb,params);traced,image,stats=trace(rgb,params,D,exponent)
        assert np.array_equal(codes,traced),name+' trace != C'
        if name=='full':assert hashlib.sha256(codes.astype('<u2').tobytes()).digest()==digest
        outputs[name]=image;phone[name]=stats
        oriented=np.rot90(image,-1) if orientation==6 else image
        Image.fromarray(oriented).save(a.out/('Phone_'+name+'.png'))
    phone['effects']={
        'adapter_roundtrip_vs_baseline':diff(outputs['adapter_only'],baseline),
        'shadow_only_effect':diff(outputs['shadow_only'],outputs['adapter_only']),
        'tone_curve_effect_with_identity_lut':diff(outputs['tone_shadow'],outputs['shadow_only']),
        'lut_effect_with_tone_fixed':diff(outputs['full'],outputs['tone_shadow']),
        'lut_effect_without_film_curve':diff(outputs['lut_shadow'],outputs['shadow_only']),
        'total_effect':diff(outputs['full'],baseline)}
    # Display -> D50 linear RGB is a controlled stand-in to test the exact same
    # D50 adapter across existing X2D II baseline caches. This is not native
    # Phocus X2D sensor rendering and does not use X2D coefficients on phone RGB.
    from prepare_preview42 import old
    lib=old.compile_shared(a.out/'private-pcs44.so')
    import ctypes as C
    class Receipt(C.Structure):_fields_=[('v',C.c_uint32*9)]
    lib.hb19_build_output_matrix.argtypes=[C.c_int,C.POINTER(C.c_double),C.POINTER(Receipt)]
    matrix=(C.c_double*9)();receipt=Receipt();assert lib.hb19_build_output_matrix(0,matrix,C.byref(receipt))==0
    xyz_to_srgb=np.asarray(matrix).reshape(3,3);input_matrix=B@A@np.linalg.inv(xyz_to_srgb)
    plainparams=core.params(input_matrix,second,identity,False,curve,native_shadow)
    fullparams=core.params(input_matrix,second,grid,False,curve,native_shadow)
    def render(linear,ev,mode):
        linear=np.asarray(linear,np.float64)*2**ev
        if mode=='baseline':return srgb(linear).astype(np.float32)/255
        q=np.floor(np.clip(linear,0,1)*65535).astype(np.uint16)
        encoded=core.render(q,plainparams if mode=='tone_shadow' else fullparams)
        return display(encoded,D,exponent).astype(np.float32)/255
    benchmark=[];panels=[]
    for label in 'ABCD':
        with np.load(a.cache_dir/(label+'_analysis.npz')) as z:data={k:z[k] for k in z.files}
        ref=preview_to_srgb(data['reference'],'DisplayP3');data['reference']=ref;mask=data['mask']&(ref.min(2)>.02)&(ref.max(2)<.98)
        record={'label':label,'reference_type':'camera embedded preview, empirical P3 conversion; tagged sRGB JPEG secondary','phases':[]}
        for phase in (0,1):
            cal,score=split_masks(mask,phase);chosen=np.flatnonzero(cal)[::5]
            x=data['linear'].reshape(-1,3)[chosen];target=ref.reshape(-1,3)[chosen]
            phase_results={}
            for mode in ('baseline','tone_shadow','full'):
                fit=minimize_scalar(lambda ev:float(abs(render(x,ev,mode)-target).mean()),bounds=(-4,4),method='bounded',options={'xatol':1e-5})
                assert fit.success and abs(fit.x)<3.98
                pred=render(data['linear'],float(fit.x),mode)
                phase_results[mode]={'reference_fitted_exposure_ev':float(fit.x),'preview':measurements(pred,ref,score),'jpeg':measurements(pred,data['jpeg'],score),
                    'regions':{name:{'preview':measurements(pred,ref,m),'jpeg':measurements(pred,data['jpeg'],m)} for name,m in roi_masks(data,score,label,phase).items() if m.sum()>10}}
                if phase==0:
                    Image.fromarray(np.rint(pred*255).astype(np.uint8)).save(a.out/(label+'_'+mode+'.png'))
            record['phases'].append(phase_results)
        benchmark.append(record)
        imgs=[('Camera reference',np.rint(ref*255).astype(np.uint8))]
        imgs += [(name,np.array(Image.open(a.out/(label+'_'+key+'.png')))) for name,key in [('Neutral + EV','baseline'),('Tone / no LUT','tone_shadow'),('Full Stage43','full')]]
        panels.append((label,imgs))
        print(label,{mode:record['phases'][0][mode]['preview']['rgb_mae_8bit'] for mode in ('baseline','tone_shadow','full')},flush=True)
    panel(panels,a.out/'Stage44_Camera_Reference_Comparison.jpg','Same D50 adapter on four X2D II baselines · exposure fitted on separate tiles')
    oriented=lambda a:np.rot90(a,-1) if orientation==6 else a
    panel([('Earlier phone RAW',[(name,oriented(outputs[key])) for name,key in [('Neutral','baseline'),('Tone / no LUT','tone_shadow'),('LUT / no film','lut_shadow'),('Full Stage43','full')]])],a.out/'Stage44_Phone_Tone_LUT_Isolation.jpg','Earlier phone DNG · identical exposure / WB / input · diagnostic isolation')
    # Fixed-temperature sensitivity; do not select a temperature by taste.
    temperatures={}
    for t in (2500,3100,4000,5550,6500,9100):
        p0=core.params(first,second,y.lut_oracle(profile,t,False),False,curve,native_shadow)
        im=display(core.render(rgb,p0),D,exponent);temperatures[str(t)]=diff(im,outputs['full'])
    white=A@np.array([.9642,1,.8249]);original_inverse=np.frombuffer(elf.read(0x314ed48,72),dtype='<f8').reshape(3,3)
    report={'schema':'hasselblad-stage44-colour-isolation-v1','status':'PASS_DIAGNOSTICS_ONLY',
        'phone_input':'earlier Stage42 DNG bundle, not the newer Stage43 screenshot scene',
        'phone_pixels':rgb.size//3,'full_render_matches_stage42_reference_exact':True,'all_five_trace_outputs_match_unchanged_C_core_exact':True,
        'phone':phone,'phone_lut_temperature_sensitivity':temperatures,
        'matrix_checks':{'D50_internal_white_relative_spread':float(np.ptp(white)/np.mean(white)),
            'inverse_A_vs_original_matrix_max_error':float(np.max(abs(np.linalg.inv(A)-original_inverse))),
            'reconstruction_luminance_column_max_deviation_from_one':float(np.max(abs(second[:,0]-1)))},
        'camera_reference_benchmark':benchmark,
        'benchmark_scope':'Same experimental D50 adapter on existing LibRaw linear-sRGB baselines; not full native Phocus sensor rendering. Per-image reference-assisted exposure fit on separate tiles; no colour fitting, no independent new scenes.',
        'verified_phocus_export_reference_available':False,'phone_sensor_calibration_validated':False,
        'camera_capture_pipeline_changed':False,'new_look_or_parameter_fit_deployed':False,
        'all_inputs_unchanged':all(hashfile(Path(p))==h for p,h in before.items()),'full_phocus_equivalence':False}
    assert report['all_inputs_unchanged']
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True);a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    (a.out/'Stage44_Private_Input_Hashes.json').write_text(json.dumps(before,indent=2)+'\n')
    print(json.dumps({'phone_effects':phone['effects'],'sensitivity':temperatures}),flush=True)
if __name__=='__main__':main()
