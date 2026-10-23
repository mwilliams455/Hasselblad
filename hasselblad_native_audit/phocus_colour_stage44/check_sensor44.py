#!/usr/bin/env python3
"""Bounded camera-sensor check; never applies X2D coefficients to phone data.
Uses explicit half-size RGGB cell reduction, as-shot gains, the recovered profile
and the existing registration. This is not the full Phocus RAW pipeline.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
import cv2,tifffile,rawpy
from PIL import Image
from scipy.optimize import minimize_scalar
from audit_colour44 import ROOT,load_private,y,Core,display,hashfile,panel
sys.path[:0]=[str(ROOT/'phocus_stage41z'),str(ROOT/'isp_3fr_stage41j'),str(ROOT/'isp_3fr_stage41l')]
from inspect_phocus_input41z import temperature_table,gain_to_temp_oracle
from compare_hasselblad_pairs41j import orient
from test_shared_render41k import preview_to_srgb,split_masks,measurements
from test_highlights41l import roi_masks

def prepare(rawpath,target_size):
    with tifffile.TiffFile(rawpath) as t:
        root=t.pages[0];pg=root.pages[0]
        assert pg.compression==1 and len(pg.dataoffsets)==1
        assert 'X2D II' in str(root.tags['Model'].value)
        with rawpy.imread(str(rawpath)) as decoder:
            assert decoder.raw_pattern.tolist()==[[0,1],[3,2]] and decoder.color_desc==b'RGBG'
            assert decoder.raw_image.shape==pg.shape
        origin=pg.tags['DefaultCropOrigin'].value;size=pg.tags['DefaultCropSize'].value
        assert all(v%2==0 for v in (*origin,*size))
        x,y0=map(int,origin);w,h=map(int,size);orientation=root.tags['Orientation'].value
        black=pg.tags['BlackLevel'].value;black=black[0]/black[1];white=pg.tags['WhiteLevel'].value
        n=np.array(root.tags['AsShotNeutral'].value).reshape(3,2);neutral=n[:,0]/n[:,1]
        mm=np.memmap(rawpath,mode='r',dtype=t.byteorder+'u2',offset=pg.dataoffsets[0],shape=pg.shape)
        camera=np.empty((h//2,w//2,3),np.float32)
        for row in range(0,h,128):
            block=np.asarray(mm[y0+row:y0+min(row+128,h),x:x+w],np.float32)
            out=camera[row//2:(row+block.shape[0])//2]
            out[...,0]=block[0::2,0::2];out[...,1]=(block[0::2,1::2]+block[1::2,0::2])*.5;out[...,2]=block[1::2,1::2]
            out-=black;out/=white-black
        del mm
    camera=cv2.resize(orient(camera,orientation),tuple(target_size),interpolation=cv2.INTER_AREA)
    return camera,1/neutral

def main():
    parser=argparse.ArgumentParser()
    for key in ('apk','manifest','cache-dir','stage41j-receipt','out','receipt'):parser.add_argument('--'+key,required=True,type=Path)
    a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    elf,profile=load_private(a.apk);B,A,_=y.matrix_constants(elf)
    # Same independently defined display adapter; no photo-specific matrix used.
    import ctypes as C
    from prepare_preview42 import old
    lib=old.compile_shared(a.out/'pcs44.so')
    class Receipt(C.Structure):_fields_=[('v',C.c_uint32*9)]
    lib.hb19_build_output_matrix.argtypes=[C.c_int,C.POINTER(C.c_double),C.POINTER(Receipt)]
    m=(C.c_double*9)();r=Receipt();assert lib.hb19_build_output_matrix(0,m,C.byref(r))==0
    D=np.array(m).reshape(3,3)@np.linalg.inv(A)
    import struct
    exponent=1/struct.unpack('<d',elf.read(0x306f9a0,8))[0]
    wb_matrix=(np.array(profile['mf'])*.5+1).reshape(3,3)@np.diag(np.array(profile['vf'])*.5+1)
    curve=y.curve_oracle(elf,1,1);shadow=y.shadow_oracle(elf,0,1);K=np.linalg.inv(B)
    gy,gx=np.mgrid[:89,:105];identity=np.stack([gx-20,gy-32],-1)
    core=Core(a.out/'core44.so');rows=[];panels=[]
    registration={v['label']:v['registration'] for v in json.loads(a.stage41j_receipt.read_text())['pairs']}
    manifest=json.loads(a.manifest.read_text())
    originals={item['label']:hashfile(Path(item['raw'])) for item in manifest}
    for item in manifest:
        label=item['label']
        with np.load(a.cache_dir/(label+'_analysis.npz')) as z:data={k:z[k] for k in z.files}
        h,w=data['linear'].shape[:2];camera,gains=prepare(item['raw'],(w,h));gains/=gains[1]
        reg=registration[label];theta=np.radians(reg['rotation_degrees']);s=reg['scale'];tx,ty=reg['translation_px']
        warp=np.array([[s*np.cos(theta),-s*np.sin(theta),tx],[s*np.sin(theta),s*np.cos(theta),ty]])
        camera=cv2.warpAffine(camera,warp,(w,h),flags=cv2.INTER_LINEAR)
        candidates,boundary=gain_to_temp_oracle(gains,wb_matrix,temperature_table(elf));assert len(candidates)==1
        temp,tint=candidates[0]
        first=B@A@y.matrix_oracle(profile,temp).reshape(3,3)@np.diag(gains)
        grid=y.lut_oracle(profile,temp,False)
        params={mode:core.params(first,K,g,False,c,shadow) for mode,g,c in [
            ('profile_tone_no_lut',identity,curve),('profile_full',grid,curve),
            ('profile_film0',grid,y.curve_oracle(elf,0,1)),('profile_no_film',grid,y.curve_oracle(elf,7,1))]}
        rgb=np.floor(np.clip(camera,0,1)*65535).astype(np.uint16)
        ref=preview_to_srgb(data['reference'],'DisplayP3');data['reference']=ref
        mask=data['mask']&(ref.min(2)>.02)&(ref.max(2)<.98)
        record={'label':label,'phases':[],'temperature_from_verified_CCNC_false_converter':True,'raw_unchanged':True}
        for phase in (0,1):
            cal,score=split_masks(mask,phase);chosen=np.flatnonzero(cal)[::5]
            sample=rgb.reshape(-1,3)[chosen];target=ref.reshape(-1,3)[chosen];phase_results={}
            regions=roi_masks(data,score,label,phase)
            for mode,p in params.items():
                def render(px,ev):
                    p.exposure=2**ev
                    return display(core.render(px,p),D,exponent).astype(np.float32)/255
                fit=minimize_scalar(lambda ev:float(abs(render(sample,ev)-target).mean()),bounds=(-4,4),method='bounded',options={'xatol':1e-5})
                assert fit.success and abs(fit.x)<3.98
                pred=render(rgb,float(fit.x));phase_results[mode]={'reference_fitted_exposure_ev':float(fit.x),
                    'preview':measurements(pred,ref,score),'jpeg':measurements(pred,data['jpeg'],score),
                    'regions':{name:{'preview':measurements(pred,ref,m),'jpeg':measurements(pred,data['jpeg'],m)} for name,m in regions.items() if m.sum()>10}}
                if phase==0:Image.fromarray(np.rint(pred*255).astype(np.uint8)).save(a.out/(label+'_'+mode+'.png'))
            record['phases'].append(phase_results)
        rows.append(record)
        images=[('Camera reference',np.rint(ref*255).astype(np.uint8)),('D50 route',np.array(Image.open(a.out.parent/(label+'_full.png'))))]
        images += [(name,np.array(Image.open(a.out/(label+'_'+key+'.png')))) for name,key in [('Sensor / no LUT','profile_tone_no_lut'),('Sensor + LUT','profile_full')]]
        panels.append((label,images))
        print(label,{mode:record['phases'][0][mode]['preview']['rgb_mae_8bit'] for mode in params},flush=True)
    report={'schema':'hasselblad-stage44-native-sensor-diagnostic-v1','status':'PASS_DIAGNOSTICS_ONLY','cases':rows,
        'preparation':'black/white normalized half-size RGGB cell reduction, mean green, linear area resize and prior similarity registration',
        'capture_gains_source':'inverse AsShotNeutral, green normalized; unity-gain input RGB; WB owned by profile matrix',
        'profile_temperature':'verified CCNC=false gain converter; live Android setting not observed',
        'selected_profile':'Stage41W sensor22/filter6 normal profile; model0/space0; fixed curve1 primary, curve0 and no-film counterfactuals',
        'reference':'Earlier camera embedded previews normalized empirically from P3, tagged JPEG secondary; not verified Phocus exports',
        'reference_assisted_exposure_fit_on_separate_tiles':True,'complete_phocus_pipeline_executed':False,
        'sensor_profile_applied_to_phone':False,'parameter_changes_deployed':False,
        'all_raws_unchanged':all(hashfile(Path(i['raw']))==originals[i['label']] for i in manifest)}
    assert report['all_raws_unchanged'];a.receipt.write_text(json.dumps(report,indent=2)+'\n')
    panel(panels,a.out/'Stage44_Sensor_Profile_Comparison.jpg','X2D II sensor-profile diagnostic · explicit half-size preparation · separate exposure-fit tiles')
    curve_panels=[]
    for label,imgs in panels:
        curve_panels.append((label,[imgs[0]]+[(name,np.array(Image.open(a.out/(label+'_'+mode+'.png')))) for name,mode in [('Curve 1','profile_full'),('Curve 0','profile_film0'),('No film curve','profile_no_film')]]))
    panel(curve_panels,a.out/'Stage44_Film_Curve_Comparison.jpg','Fixed recovered curve alternatives · not live-setting identification or a deployment decision')
if __name__=='__main__':main()
