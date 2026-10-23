#!/usr/bin/env python3
"""Isolate LUT temperature with curve0 fixed; produce a private Stage43 trial.

This does not estimate the phone illuminant or change DNG white balance. The
earlier phone RAW is a sensitivity fixture, not the latest tungsten-room RAW.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_colour_stage44'))
from audit_colour44 import read_bundle,Core,trace,diff,panel,load_private
from prepare_preview42 import native_photo_sample,y

def main():
    p=argparse.ArgumentParser()
    for name in ('apk','bundle','profile','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();assert __debug__;a.out.mkdir(parents=True,exist_ok=True)
    inputs=[a.apk,a.bundle,a.profile];before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    elf,profile=load_private(a.apk)
    old=a.profile.read_bytes();assert old[:8]==b'HB43LUT1' and hashlib.sha256(old[:-32]).digest()==old[-32:]
    assert struct.unpack_from('<6i',old,8)==(105,89,4000,0,0,0)
    grid_at=32+38*8;grid_end=grid_at+105*89*16
    curve=np.frombuffer(old,dtype='<f4',count=65536,offset=grid_end).copy()
    assert np.array_equal(curve,y.curve_oracle(elf,0,1))
    rgb,baseline,v,oldgrid,unused_curve,digest,orientation=read_bundle(a.bundle)
    first=v[:9].reshape(3,3);second=v[9:18].reshape(3,3)
    shadow=v[18:22];D=v[28:37].reshape(3,3);exponent=v[37]
    core=Core(a.out/'private-core45.so');images={};results={};codes={}
    samples=rgb.reshape(-1,3)[np.linspace(0,rgb.size//3-1,512,dtype=int)]
    # Uniform common-space neutral controls independently exercise hue neutrality.
    B,A,_=y.matrix_constants(elf)
    d50=np.array([.9642,1.,.8249])
    neutrals=np.rint(np.linspace(.001,.8,32)[:,None]*d50*65535).astype(np.uint16)
    neutral_images={}
    for t in (2400,2850,3050,3200,4000,5550):
        grid=y.lut_oracle(profile,t,False)
        params=core.params(first,second,grid,False,curve,shadow)
        codes[t]=core.render(rgb,params);traced,images[t],stats=trace(rgb,params,D,exponent)
        assert np.array_equal(codes[t],traced)
        native=native_photo_sample(elf,profile,samples,params,t)
        assert np.array_equal(native,core.render(samples,params))
        neutral_params=core.params(B@A,second,grid,False,curve,shadow)
        neutral_images[t]=trace(neutrals,neutral_params,D,exponent)[1]
        results[str(t)]={'clipping':stats,'trace_channels_exact':int(codes[t].size),'original_arm64_channels_exact':int(native.size)}
        print(f'Curve0 LUT-only comparison verified at {t} K',flush=True)
    for t in images:
        results[str(t)]['vs_4000K']=diff(images[t],images[4000])
        results[str(t)]['neutral_controls_vs_4000K']=diff(neutral_images[t],neutral_images[4000])
    t=3050;grid=y.lut_oracle(profile,t,False)
    new=bytearray(old);struct.pack_into('<i',new,16,t)
    new[grid_at:grid_end]=grid.astype('<f8').tobytes();new[-32:]=hashlib.sha256(new[:-32]).digest()
    assert new[:16]==old[:16] and new[20:grid_at]==old[20:grid_at] and new[grid_end:-32]==old[grid_end:-32]
    dest=a.out/'Stage45_Private_Curve0_3050K.hbc';dest.write_bytes(new)
    payload=bytearray(a.bundle.read_bytes());struct.pack_into('<i',payload,32,t);struct.pack_into('<i',payload,40,0)
    bundle_grid_at=48+38*8;bundle_curve_at=bundle_grid_at+105*89*16
    payload[bundle_grid_at:bundle_curve_at]=grid.astype('<f8').tobytes()
    payload[bundle_curve_at:bundle_curve_at+65536*4]=curve.astype('<f4').tobytes()
    hash_at=bundle_curve_at+65536*4+32
    payload[hash_at:hash_at+32]=hashlib.sha256(codes[t].astype('<u2').tobytes()).digest()
    payload[-32:]=hashlib.sha256(payload[:-32]).digest()
    (a.out/'Stage45_Private_JNI_Reference.hb42').write_bytes(payload)
    orient=lambda x:np.rot90(x,-1) if orientation==6 else x
    amplified=np.clip(abs(images[3050].astype(int)-images[4000].astype(int))*16,0,255).astype(np.uint8)
    panel([('Same earlier RAW',[(name,orient(im)) for name,im in [('Curve0 / 4000K',images[4000]),('Curve0 / 3050K',images[3050]),('Curve0 / 2850K',images[2850]),('Difference x16',amplified)]])],
        a.out/'Stage45_Tungsten_LUT_Comparison.jpg','LUT temperature only · exposure, film curve and DNG white balance held fixed')
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in inputs)
    result={'schema':'hasselblad-stage45-tungsten-isolation-v1','status':'PASS_HOST_AND_ORIGINAL_PIXEL_SAMPLES',
        'phone_fixture':'Earlier Stage42 cat DNG; latest tungsten-room RAW unavailable',
        'film_code':0,'white_balance_owner':'unchanged DNG camera-to-D50 transform','exposure_unchanged':True,
        'temperature_cases':results,'trial_temperature':3050,'trial_temperature_is_measured_phone_illuminant':False,
        'trial_basis':'Recovered profile tungsten LUT calibration anchor; controlled diagnostic only',
        'profile_changes_only':['temperature field','chroma LUT','checksum'],
        'profile_sha256':hashlib.sha256(new).hexdigest(),'profile_bytes':len(new),
        'source_inputs_unchanged':True,'AI_image_editing_used':False,
        'panel_from_renderer_outputs':True,'capture_renderer_changed':False,'phone_temperature_mapping_validated':False,
        'full_phocus_equivalence':False,'new_apk_required':False}
    (a.out/'STAGE45_TUNGSTEN_ISOLATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'profile_sha256':result['profile_sha256'],'trial_vs_4000K':results['3050']['vs_4000K']}),flush=True)
if __name__=='__main__':main()
