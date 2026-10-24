#!/usr/bin/env python3
"""Direct original ARM64 green-estimator fixtures and independent C comparison."""
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
from audit_maps61 import MapRunner, load_private, OBJ
from audit_kernels61 import guarded, guard_ok
from portable63 import PortableGreen

GREEN_FIRST='_ZN20CGradientInterpolate18GetGreenAtRedFirstEPKtPKfS3_S3_S1_iRiS4_PsS5_Rs'
PTRS=tuple(0x50010000+i*0x10000 for i in range(10))


def compare(r,c,raw,maps,first,second,floors=(50,400),label='',unused_pointer=0):
    stride=raw.shape[1]; offset=(2*stride+2)
    arrays=[np.ascontiguousarray(x) for x in [raw,*maps,first,second]]
    outputs=[np.array([1234567],'<i4'),np.array([7654321],'<i4'),np.array([12345],'<i2')]
    for ptr,a in zip(PTRS,arrays+outputs):
        r.u.mem_write(ptr-16,b'\xa5'*16+a.tobytes()+b'\xa5'*16)
    r.u.mem_write(OBJ-16,b'\xa5'*16+b'\0'*0x100+b'\xa5'*16)
    r.put(OBJ,0xe8,'<2h',*floors)
    frozen_object=bytes(r.u.mem_read(OBJ-16,0x120))
    r.map_stack=(r.e.func[GREEN_FIRST][0],struct.pack('<4Q',PTRS[7],PTRS[4],PTRS[5],PTRS[8]))
    r.call(GREEN_FIRST,(OBJ,PTRS[0]+offset*2,*[p+offset*4 for p in PTRS[1:4]],
                        unused_pointer,stride,PTRS[6]))
    native=tuple(struct.unpack('<i' if i<2 else '<h',bytes(r.u.mem_read(PTRS[6+i],a.nbytes)))[0]
                 for i,a in enumerate(outputs))
    guarded_arrays=[guarded(a) for a in arrays+outputs]
    views=[x[1] for x in guarded_arrays]
    c.lib.hb_green_at_colour63(views[0].ctypes.data+offset*2,
        *[x.ctypes.data+offset*4 for x in views[1:4]],stride,
        *[x.ctypes.data for x in views[4:6]],*floors,*[x.ctypes.data for x in views[6:]])
    actual=tuple(int(x[0]) for x in views[6:])
    assert native==actual,(label,'native',native,'portable',actual)
    for i,(ptr,a,(storage,view)) in enumerate(zip(PTRS,arrays+outputs,guarded_arrays)):
        assert bytes(r.u.mem_read(ptr-16,16))==bytes(r.u.mem_read(ptr+a.nbytes,16))==b'\xa5'*16
        guard_ok(storage)
        if i<6:
            assert bytes(r.u.mem_read(ptr,a.nbytes))==a.tobytes()==view.tobytes()
    assert bytes(r.u.mem_read(OBJ-16,0x120))==frozen_object
    return native


def cardinal_fixture(codes,center=10000,extra_diagonal=False,stride=9):
    raw=np.full((5,stride),center,'<u2')
    maps=[np.ones((5,stride),'<f4') for _ in range(3)]
    h,v,_=maps
    for (y,x),value in zip(((1,2),(2,3),(3,2),(2,1)),codes):
        (v if x==2 else h)[y,x]=np.float32(value/center)
    a=np.array([100]*4+[100 if extra_diagonal else 30000]+[30000]*3,'<i2')
    b=np.zeros(8,'<i2')
    return raw,maps,a,b


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sanitize',action='store_true')
    a=p.parse_args(); assert __debug__
    before=hashlib.sha256(a.apk.read_bytes()).digest()
    r=MapRunner(*load_private(a.apk)); c=PortableGreen(a.work,sanitize=a.sanitize)
    entry=r.e.func[GREEN_FIRST][0]
    r.path_probes={entry+0x7f4:'nearest_direction_selection',entry+0x9e8:'replace_with_single_direction',
                   entry+0x888:'no_direction_bilinear',entry+0x8b4:'selected_direction_average'}
    rng=np.random.default_rng(6301); cases=0; masks=set(); output_masks=Counter()
    for stride in (5,9,23):
        shape=(5,stride)
        patterns=[('zero',np.zeros(shape,'<u2'),[np.zeros(shape,'<f4') for _ in range(3)]),
          ('flat',np.full(shape,10000,'<u2'),[np.ones(shape,'<f4') for _ in range(3)]),
          ('full',np.full(shape,65535,'<u2'),[np.full(shape,2.,'<f4') for _ in range(3)]),
          ('random',rng.integers(0,65536,shape,dtype=np.uint16),
           [rng.uniform(0.01,4.,shape).astype('<f4') for _ in range(3)])]
        for name,raw,maps in patterns:
            for bitmask in range(256):
                for which in (0,1):
                    gradients=[np.zeros(8,'<i2'),np.zeros(8,'<i2')]
                    gradients[which]=np.array([0 if bitmask&(1<<i) else 32767 for i in range(8)],'<i2')
                    out=compare(r,c,raw,maps,*gradients,label=(stride,name,bitmask,which))
                    output_masks[out[1]]+=1; cases+=1; masks.add(bitmask)
        print(json.dumps({'stride':stride,'all_masks_on_both_gradient_inputs':'EXACT'}),flush=True)
    # Finite nonnegative scale maps spanning normal and saturating FCVTZS inputs.
    for i in range(4096):
        stride=(5,9,23)[i%3]; shape=(5,stride)
        raw=rng.integers(0,65536,shape,dtype=np.uint16)
        limit=(0.1,1.,4.,65536.,1e20)[i%5]
        maps=[rng.uniform(0.,limit,shape).astype('<f4') for _ in range(3)]
        bounds=(-32768,32768) if i%4==0 else (0,2000)
        first,second=[rng.integers(*bounds,8,dtype=np.int16) for _ in range(2)]
        floors=((50,400),(32,200),(100,800),(-32768,-32768),(32767,32767))[i%5]
        out=compare(r,c,raw,maps,first,second,floors,label=('random',i))
        output_masks[out[1]]+=1; cases+=1
    # Check the declared finite-input extremes as well: subnormal scales and
    # finite scales whose multiplication overflows to positive infinity.
    for scale in (np.nextafter(np.float32(0),np.float32(1)),np.finfo(np.float32).tiny,np.finfo(np.float32).max):
        for code in (0,1,65535):
            for bitmask in (0xff,0x10):
                raw=np.full((5,5),code,'<u2')
                maps=[np.full((5,5),scale,'<f4') for _ in range(3)]
                first=np.array([0 if bitmask&(1<<i) else 32767 for i in range(8)],'<i2')
                compare(r,c,raw,maps,first,np.zeros(8,'<i2'),label=('float_extreme',float(scale),code,bitmask))
                cases+=1
    witnesses=[]
    targeted=[('nearest_nonzero',[5000,20000,5000,20000],10000,False),
              ('nearest_zero_retains_mask',[5000,20000,5000,20000],5000,False),
              ('sentinel_original_count',[200000,1000000,200000,1000000],10000,False),
              ('sentinel_five_directions',[200000,1000000,200000,1000000],10000,True),
              ('signed_product_boundary',[0,120000,0,120000],10000,False)]
    for name,codes,center,extra in targeted:
        fixture=cardinal_fixture(codes,center,extra)
        out=compare(r,c,*fixture,label=name); cases+=1
        witnesses.append({'fixture':name,'cardinal_candidate_targets':codes,
                          'centre_raw':center,'extra_diagonal_selected':extra,
                          'native_and_portable_green_mask_maximum':list(out)})
    # Exercise all nearest-direction choices, plus a wider range of edge
    # candidates and positive gradient levels under the special-branch gates.
    nearest_masks=set()
    for i in range(512):
        codes=rng.integers(0,262144,4).tolist()
        raw,maps,first,second=cardinal_fixture(codes,extra_diagonal=bool(i%2))
        out=compare(r,c,raw,maps,first,second,label=('edge_random',i)); cases+=1
        if out[1]>>8==1: nearest_masks.add(out[1]&255)
    for direction in range(4):
        codes=[20000]*4; codes[direction]=6000; codes[(direction+2)%4]=5000
        out=compare(r,c,*cardinal_fixture(codes),label=('nearest_direction',direction)); cases+=1
        assert out[1]==(0x100|(1<<direction)); nearest_masks.add(out[1]&255)
    assert nearest_masks=={1,2,4,8}
    # Search deterministic synthetic values for a rounding boundary at which
    # unfused multiplication/addition changes the final integer output.
    unfused=PortableGreen(a.work/'unfused',sanitize=a.sanitize,unfused_negative_control=True)
    frng=np.random.default_rng(6303); fma_witness=None
    for i in range(50000):
        raw=np.full((5,5),10000,'<u2')
        raw[2,2]=frng.integers(1,65536); raw[1,3]=frng.integers(1,65536)
        maps=[np.ones((5,5),'<f4') for _ in range(3)]
        maps[2][2,2]=np.float32(frng.uniform(0.01,2.))
        maps[2][1,3]=np.float32(frng.uniform(0.01,2.))
        maps[2][1,1]=0.; maps[2][3,3]=2.
        maps[2][0,0]=0.; maps[2][4,4]=2.
        first=np.full(8,32767,'<i2'); first[4]=0
        second=np.zeros(8,'<i2')
        results=[]
        for implementation in (c,unfused):
            outputs=[np.zeros(1,'<i4'),np.zeros(1,'<i4'),np.zeros(1,'<i2')]
            implementation.lib.hb_green_at_colour63(raw.ctypes.data+24,
                *[x.ctypes.data+48 for x in maps],5,first.ctypes.data,second.ctypes.data,50,400,
                *[x.ctypes.data for x in outputs])
            results.append(tuple(int(x[0]) for x in outputs))
        if results[0]!=results[1]:
            native=compare(r,c,raw,maps,first,second,label='fma_boundary'); cases+=1
            assert native==results[0]
            fma_witness={'centre_raw':int(raw[2,2]),'north_east_raw':int(raw[1,3]),
                'centre_scale_float32_bits':int(maps[2][2,2].view(np.uint32)),
                'north_east_scale_float32_bits':int(maps[2][1,3].view(np.uint32)),
                'native_and_portable':list(native),'incorrect_unfused':list(results[1]),
                'search_iteration':i}
            break
    assert fma_witness is not None
    # A mapped unused legacy green-plane argument can vary without effect in
    # this entry; zero was used above. This does not generalize to other entries.
    raw,maps,first,second=cardinal_fixture([5000,20000,5000,20000])
    for ptr in (PTRS[0],PTRS[1],PTRS[4]):
        assert compare(r,c,raw,maps,first,second,unused_pointer=ptr)==tuple(witnesses[0]['native_and_portable_green_mask_maximum'])
        cases+=1
    assert len(masks)==256
    assert all(r.path_hits[label]>0 for label in r.path_probes.values()),dict(r.path_hits)
    for ptr,frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(frozen)))==frozen
    r.check_guards(); assert hashlib.sha256(a.apk.read_bytes()).digest()==before
    report={'schema':'hasselblad-stage63-green-estimator-v1','status':'PASS_EXACT_GREEN_ESTIMATOR',
       'cases':cases,'exact_output_scalars':cases*3,'low_masks_covered_on_each_gradient_input':len(masks),
       'strides_tested':[5,9,23],'distinct_output_masks':len(output_masks),
       'native_branch_execution_blocks':dict(r.path_hits),'synthetic_branch_witnesses':witnesses,
       'nearest_cardinal_direction_bits_observed':sorted(nearest_masks),
       'fused_arithmetic_negative_control':fma_witness,
       'float_fused_multiply_add_explicit':True,'float_to_signed_integer_saturation_tested':True,
       'subnormal_and_finite_scale_overflow_cases':18,
       'signed_gradient_extremes_tested':True,'finite_nonnegative_scale_input_contract':True,
       'input_output_and_object_guards_pass':True,'source_and_profile_unchanged':True,
       'undefined_behavior_sanitizer':a.sanitize,'max_absolute_difference':0,
       'complete_gradient_port':False,'device_execution_compared':False,'scene_fitted_parameters':0,
       'capture_renderer_changed':False,'full_phocus_equivalence':False}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report),flush=True)


if __name__=='__main__': main()
