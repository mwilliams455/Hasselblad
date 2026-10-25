#!/usr/bin/env python3
"""Create an owner's private curve-only pack from the hash-pinned original APK.
Output must stay out of public source/CI. No LUT, camera data or photo pixels.
Uses the previously verified Stage41y reconstruction without fitting or scaling.
"""
import argparse,hashlib,json,struct,sys,zipfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_stage41y'))
import inspect_phocus_pipeline41y as y

def main():
    p=argparse.ArgumentParser();p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    apk=a.apk.read_bytes()
    if hashlib.sha256(apk).hexdigest()!=y.APK_SHA:raise ValueError('Unexpected source APK')
    with zipfile.ZipFile(a.apk) as z:lib=z.read('lib/arm64-v8a/libcrosssdk.so')
    if hashlib.sha256(lib).hexdigest()!=y.LIB_SHA:raise ValueError('Unexpected source library')
    elf=y.Elf(lib);data=b'HB83CRV1'+struct.pack('<I',3);cases=[]
    for film in (0,1,7):
        curve=y.curve_oracle(elf,film,1)
        assert curve.shape==(65536,) and np.isfinite(curve).all()
        assert curve.min()>=0 and curve.max()<=65535 and (np.diff(curve)>=0).all()
        payload=curve.astype('<f4').tobytes();data+=struct.pack('<I',film)+payload
        cases.append({'film_code':film,'entries':len(curve),'curve_sha256':hashlib.sha256(payload).hexdigest(),
                      'finite_monotonic_bounded':True})
    data+=hashlib.sha256(data).digest();assert len(data)==786488
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(data)
    receipt={'schema':'hasselblad-stage83-private-tone-pack-v1','bytes':len(data),
             'sha256':hashlib.sha256(data).hexdigest(),'curves':cases,
             'source_apk_sha256':y.APK_SHA,'source_library_sha256':y.LIB_SHA,
             'reconstruction':'Unchanged Stage41y curve_oracle, companding code 1',
             'photo_pixels_or_camera_calibration_included':False,'public_distribution':False}
    a.out.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
