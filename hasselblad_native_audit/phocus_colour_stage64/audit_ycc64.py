#!/usr/bin/env python3
"""Direct original CPU vs independent C YCC fixtures; private Phocus binary required.

Runs only when the existing Stage60-63 Unicorn audit environment is available.
Neither the original library nor any private DNG/profile/pixel data is exported.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_gradient_stage61'))
from audit_maps61 import MapRunner,load_private
from audit_kernels61 import guarded,guard_ok
from portable64 import PortableYCC

NATIVE_YCC='_Z29DirectionalColorCorrectionYCCiPKtPKsS2_S0_S2_S2_RtRsS4_S4_i'
PTRS=tuple(0x50010000+i*0x10000 for i in range(10))


def fixture(r,c,mask,centres,neighbours,label):
    y0,c10,c20=centres
    y,a,b=(np.ascontiguousarray(x) for x in neighbours)
    assert y.shape==a.shape==b.shape and y.dtype==np.dtype('<u2')
    assert a.dtype==b.dtype==np.dtype('<i2') and y.ndim==2 and y.shape[0]==3
    stride=y.shape[1]; assert stride>=3
    offset=stride+1
    # Three independent scalar source pointers, three input stencils and four
    # scalar output references. This call deliberately exercises no aliasing.
    arrays=[np.array([y0],'<u2'),np.array([c10],'<i2'),np.array([c20],'<i2'),
            y,a,b,np.array([12345],'<u2'),np.array([12345],'<i2'),
            np.array([-23456],'<i2'),np.array([23456],'<i2')]
    for ptr,arr in zip(PTRS,arrays):
        r.u.mem_write(ptr-16,b'\xa5'*16+arr.tobytes()+b'\xa5'*16)
    entry=r.e.func[NATIVE_YCC][0]
    r.map_stack=(entry,struct.pack('<4Q',PTRS[7],PTRS[8],PTRS[9],stride))
    r.call(NATIVE_YCC,(mask,PTRS[0],PTRS[1],PTRS[2],
                       PTRS[3]+2*offset,PTRS[4]+2*offset,PTRS[5]+2*offset,PTRS[6]))
    native=tuple(int.from_bytes(r.u.mem_read(PTRS[i],2),'little') for i in range(6,10))
    buffers=[guarded(arr) for arr in arrays]
    views=[x[1] for x in buffers]
    centre=[views[0].ctypes.data,views[1].ctypes.data,views[2].ctypes.data]
    neigh=[views[i].ctypes.data+2*offset for i in (3,4,5)]
    outputs=[views[i].ctypes.data for i in range(6,10)]
    assert c.lib.hb_directional_ycc64(mask,*centre,*neigh,*outputs,stride)==0
    result=tuple(int(view[0])&65535 for view in views[6:])
    assert native==result,(label,'native',native,'C',result)
    for i,(ptr,original,(storage,view)) in enumerate(zip(PTRS,arrays,buffers)):
        guest=bytes(r.u.mem_read(ptr,original.nbytes))
        assert guest==view.tobytes(),(label,'storage mismatch',i)
        if i<6:assert guest==original.tobytes(),(label,'source mutation',i)
        assert bytes(r.u.mem_read(ptr-16,16))==bytes(r.u.mem_read(ptr+original.nbytes,16))==b'\xa5'*16
        guard_ok(storage)
    return native


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',required=True,type=Path)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--safe-receipt',required=True,type=Path)
    p.add_argument('--sanitize',action='store_true')
    p.add_argument('--compiler',default='gcc')
    args=p.parse_args();assert __debug__
    frozen=hashlib.sha256(args.apk.read_bytes()).digest()
    native=MapRunner(*load_private(args.apk));portable=PortableYCC(args.work,args.compiler,args.sanitize)
    rng=np.random.default_rng(6404)
    calls=0;strides=(3,8,19)
    for stride in strides:
        for mask in range(256):
            y=np.full((3,stride),10000,'<u2')
            aa=np.full((3,stride),1200,'<i2')
            bb=np.full((3,stride),-2000,'<i2')
            n=mask.bit_count()
            fixture(native,portable,mask|(n<<8),(10000,1200,-2000),(y,aa,bb),('flat',stride,mask))
            calls+=1
        print(json.dumps({'stride':stride,'all_256_low_direction_masks':'EXACT'}),flush=True)
    for i in range(3072):
        stride=strides[i%3];shape=(3,stride)
        raw=rng.integers(0,65536,shape,dtype=np.uint16)
        aa=rng.integers(-32768,32768,shape,dtype=np.int16)
        bb=rng.integers(-32768,32768,shape,dtype=np.int16)
        mask=int(rng.integers(0,1<<16,dtype=np.uint64))
        centres=tuple(int(x) for x in (rng.integers(0,65536),rng.integers(-32768,32768),rng.integers(-32768,32768)))
        if i%11==0:raw.fill(0);aa.fill(-32768);bb.fill(32767)
        if i%23==0:raw.fill(65535);aa.fill(32767);bb.fill(-32768)
        if i%31==0:centres=(0,centres[1],centres[2])
        fixture(native,portable,mask,centres,(raw,aa,bb),('random',i))
        calls+=1
        if (i+1)%512==0:
            print(json.dumps({'random_cases':i+1,'YCC_CPU_vs_C':'EXACT'}),flush=True)
    for ptr,saved in native.frozen_profile:
        assert bytes(native.u.mem_read(ptr,len(saved)))==saved
    native.check_guards()
    assert hashlib.sha256(args.apk.read_bytes()).digest()==frozen
    receipt={'schema':'hasselblad-stage64-directional-ycc-native-v1',
             'status':'PASS_EXACT_DIRECT_ORIGINAL_CPU_YCC',
             'original_cpu_to_independent_c_cases':calls,
             'exact_output_codes':calls*4,'max_absolute_difference':0,
             'mask_low_bits_covered':256,'strides_tested':list(strides),
             'high_mask_count_inconsistencies_tested':True,
             'input_output_native_canaries_pass':True,
             'native_source_and_private_profile_unchanged':True,
             'complete_demosaic_port':False,'device_execution_compared':False,
             'original_apk_modified':False,'normal_capture_changed':False,
             'full_phocus_equivalence':False}
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'direct_original_cpu_check':receipt['status'],'cases':calls}),flush=True)


if __name__=='__main__':main()
