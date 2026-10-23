#!/usr/bin/env python3
"""Validate the curve0-only private profile and construct a local JNI reference.
No calibration/image payload is exported to public evidence.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
from PIL import Image
from audit_colour44 import read_bundle,Core,trace,diff,panel,load_private
from prepare_preview42 import native_photo_sample

def main():
    p=argparse.ArgumentParser()
    for key in ('apk','bundle','original-profile','trial-profile','out'):p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    original=a.original_profile.read_bytes();trial=a.trial_profile.read_bytes()
    gw,gh,t,model,film,space=struct.unpack_from('<6i',trial,8)
    assert (t,model,film,space)==(4000,0,0,0)
    curve_at=32+38*8+gw*gh*16
    assert len(original)==len(trial) and original[:24]==trial[:24] and original[28:curve_at]==trial[28:curve_at]
    assert hashlib.sha256(trial[:-32]).digest()==trial[-32:]
    newcurve=np.frombuffer(trial,dtype='<f4',count=65536,offset=curve_at).copy()
    rgb,baseline,v,grid,curve,digest,orientation=read_bundle(a.bundle)
    first=v[:9].reshape(3,3);second=v[9:18].reshape(3,3);shadow=v[18:22];D=v[28:37].reshape(3,3);exponent=v[37]
    core=Core(a.out/'trial-core44.so');params=core.params(first,second,grid,False,newcurve,shadow)
    output=core.render(rgb,params);traced,preview,stats=trace(rgb,params,D,exponent);assert np.array_equal(output,traced)
    _,current,_=trace(rgb,core.params(first,second,grid,False,curve,shadow),D,exponent)
    elf,profile=load_private(a.apk)
    sample=rgb.reshape(-1,3)[np.linspace(0,rgb.size//3-1,512,dtype=int)]
    native=native_photo_sample(elf,profile,sample,params,4000)
    assert np.array_equal(native,core.render(sample,params))
    payload=bytearray(a.bundle.read_bytes());struct.pack_into('<i',payload,40,0)
    bundle_curve=48+38*8+gw*gh*16
    payload[bundle_curve:bundle_curve+65536*4]=newcurve.astype('<f4').tobytes()
    hash_at=bundle_curve+65536*4+32
    payload[hash_at:hash_at+32]=hashlib.sha256(output.astype('<u2').tobytes()).digest()
    payload[-32:]=hashlib.sha256(payload[:-32]).digest()
    (a.out/'Stage44_Private_JNI_Reference.hb42').write_bytes(payload)
    orient=lambda x:np.rot90(x,-1) if orientation==6 else x
    panel([('Earlier phone RAW',[('Neutral baseline',orient(baseline)),('Current curve 1',orient(current)),('Trial curve 0',orient(preview)),('Difference x4',orient(np.clip(abs(preview.astype(int)-current.astype(int))*4,0,255).astype(np.uint8)))])],a.out/'Stage44_Phone_Curve_Comparison.jpg','Same earlier phone DNG · only the recovered film curve changes · no exposure fitting')
    result={'schema':'hasselblad-stage44-curve0-trial-v1','status':'PASS_HOST_AND_NATIVE_SAMPLE',
        'only_profile_changes':['film code 1 to 0','recovered 65536-entry curve','file checksum'],
        'unchanged':['LUT and temperature 4000 K','D50 input conversion','display adapter','shadow settings','separate WB unity','exposure unity'],
        'original_arm64_pixel_routine_channels_exact':1536,'all_preview_trace_channels_exact':int(output.size),
        'phone_input':'Earlier Stage42 DNG, not latest Stage43 screenshot scene',
        'trial_vs_current':diff(preview,current),'trial_clipping':stats,
        'full_phocus_equivalence':False,'default_profile_changed':False,'device_trial_pending':True}
    (a.out/'STAGE44_CURVE0_TRIAL.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
