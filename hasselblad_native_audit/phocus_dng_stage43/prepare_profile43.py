#!/usr/bin/env python3
"""Locally derive a private data-only profile from the owner's supplied APK.
No private arrays, photo pixels or camera-specific coefficients enter this repo.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_port_stage42'))
from prepare_preview42 import load_private,y

def main():
    p=argparse.ArgumentParser();p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--temperature',type=int,default=4000);a=p.parse_args()
    if not 2000<=a.temperature<=10000:raise ValueError('LUT temperature out of range')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    elf,profile=load_private(a.apk)
    basis,internal,transforms=y.matrix_constants(elf)
    # Only D50 -> internal basis here. The selected DNG supplies camera -> D50.
    domain=basis@internal;second=transforms[0]@np.linalg.inv(basis)
    # Same explicit output adapter as Stage42; these values are derived locally.
    import offline_render24 as old
    core=old.compile_shared(a.out.parent/'private-dng43.so')
    import ctypes as C
    class Receipt(C.Structure):_fields_=[('v',C.c_uint32*9)]
    core.hb19_build_output_matrix.argtypes=[C.c_int,C.POINTER(C.c_double),C.POINTER(Receipt)]
    matrix=(C.c_double*9)();receipt=Receipt()
    if core.hb19_build_output_matrix(0,matrix,C.byref(receipt))!=0:raise ValueError('Display matrix failed')
    display=np.asarray(matrix).reshape(3,3)@np.linalg.inv(internal)
    exponent=1/struct.unpack('<d',elf.read(0x306f9a0,8))[0]
    values=np.r_[domain.ravel(),second.ravel(),y.shadow_oracle(elf,0,1),[1.,1.,1.],1.,20.,32.,display.ravel(),exponent]
    grid=y.lut_oracle(profile,a.temperature,False);curve=y.curve_oracle(elf,1,1)
    data=b'HB43LUT1'+struct.pack('<6i',105,89,a.temperature,0,1,0)+values.astype('<f8').tobytes()
    data+=grid.astype('<f8').tobytes()+curve.astype('<f4').tobytes()
    a.out.write_bytes(data+hashlib.sha256(data).digest())
    print(json.dumps({'bytes':a.out.stat().st_size,'photo_pixels_included':False,
        'phone_camera_matrix_included':False,'manual_lut_temperature':a.temperature,
        'sha256':hashlib.sha256(a.out.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
