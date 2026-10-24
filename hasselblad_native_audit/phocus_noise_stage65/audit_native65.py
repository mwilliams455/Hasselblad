#!/usr/bin/env python3
"""Original CPU versus bounded ColorNoise65 C, executed ONLY when emulation exists.

Uses locally supplied private Phocus APK. Original binary, inputs, private
pointer values and pixel arrays are never saved in the aggregate receipt.
This script has not been executed in the Stage65 host checkpoint.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import ctypes as C

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_gradient_stage61'))
from audit_maps61 import MapRunner, load_private, OBJ
from audit_kernels61 import guarded, guard_ok
from portable65 import PortableNoise65, NoiseCounters65
from test_host65 import KEYS, make_arrays

COLOR_NOISE = '_ZN20CGradientInterpolate10ColorNoiseEii'
DIRECTIONAL_YCC = '_Z29DirectionalColorCorrectionYCCiPKtPKsS2_S0_S2_S2_RtRsS4_S4_i'
PTRS={name:0x50010000+idx*0x18000 for idx,name in enumerate(KEYS)}
OFFSETS={'red':0xb0,'green':0xb8,'blue':0xc0,'y':0xd0,
         'c1':0xd8,'c2':0xe0,'direction_mask':0xc8,
         'smooth_y':0x98,'median_c1':0xa0,'median_c2':0xa8,
         'out_y':0x68,'out_c1':0x70,'out_c2':0x78,'out_aux':0x80}


def original_fixture(native, portable, original, flags, width, height, strength=0,
                     optimized_view=0, case=''):
    assert strength==0, 'Only bounded no-extended-strength route in native audit'
    arrays={name:np.ascontiguousarray(a) for name,a in original.items()}
    stride=arrays['red'].shape[1]
    initial={name:a.copy() for name,a in arrays.items()}
    for name,a in arrays.items():
        ptr=PTRS[name]
        native.u.mem_write(ptr-16,b'\xa5'*16+a.tobytes()+b'\xa5'*16)
    native.u.mem_write(OBJ-16,b'\xa5'*16+b'\0'*0x100+b'\xa5'*16)
    native.put(OBJ,0x38,'<H',flags)
    native.put(OBJ,0x08,'<B',optimized_view)
    native.put(OBJ,0x28,'<i',strength)
    native.put(OBJ,0x3c,'<i',stride)
    for name,off in OFFSETS.items():native.put(OBJ,off,'<Q',PTRS[name])
    before_obj=bytes(native.u.mem_read(OBJ-16,0x120))
    before_calls=dict(native.path_hits)
    native.call(COLOR_NOISE,(OBJ,width,height))
    after_calls=dict(native.path_hits)
    ycc_entry=native.e.func[DIRECTIONAL_YCC][0]
    # Probe label assigned in main. Calls are counted, never assumed.
    observed_ycc=after_calls.get('direct_original_ycc_entry',0)-before_calls.get('direct_original_ycc_entry',0)
    guarded_arrays={name:guarded(a) for name,a in initial.items()}
    views={name:storage[1] for name,storage in guarded_arrays.items()}
    ctx=portable.bind(views,width,height,flags,strength,optimized_view)
    counts=NoiseCounters65()
    assert portable.lib.hb_color_noise65(C.byref(ctx),C.byref(counts))==0
    for name in KEYS:
        p=PTRS[name];a=views[name]
        result=bytes(native.u.mem_read(p,a.nbytes))
        if result!=a.tobytes():
            mismatches=np.frombuffer(result,dtype=a.dtype).reshape(a.shape)!=a
            loc=tuple(np.argwhere(mismatches)[0])
            # The failure stays local in a private terminal log, not receipt.
            raise AssertionError(('ColorNoise65 native mismatch',case,name,loc,
                                  int(np.frombuffer(result,dtype=a.dtype).reshape(a.shape)[loc]),
                                  int(a[loc])))
        assert bytes(native.u.mem_read(p-16,16))==bytes(native.u.mem_read(p+a.nbytes,16))==b'\xa5'*16
        guard_ok(guarded_arrays[name][0])
        if name in ('red','green','blue','direction_mask'):
            assert result==initial[name].tobytes()
    assert bytes(native.u.mem_read(OBJ-16,0x120))==before_obj
    expected_ycc=int(counts.nonzero_mask_sites)
    assert observed_ycc==expected_ycc,(case,'YCC calls mismatch',observed_ycc,expected_ycc)
    return {'case':case,'arrays_compared':len(KEYS),
            'storage_elements_compared':sum(x.size for x in arrays.values()),
            'nonzero_mask_original_calls':observed_ycc,
            'colour_noise_sites':int(counts.correction_sites)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',required=True,type=Path)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--safe-receipt',required=True,type=Path)
    p.add_argument('--sanitize',action='store_true')
    args=p.parse_args();assert __debug__
    immutable=hashlib.sha256(args.apk.read_bytes()).digest()
    native=MapRunner(*load_private(args.apk)); portable=PortableNoise65(args.work,sanitize=args.sanitize)
    native.path_probes={native.e.func[DIRECTIONAL_YCC][0]:'direct_original_ycc_entry'}
    rng=np.random.default_rng(6503)
    results=[];masks=set();modes=set()
    dims=((17,17,21),(24,28,32),(25,25,29),(32,34,40))
    for h,w,stride in dims:
        for flags in (0x20,0x40,0x60):
            for kind in ('zero','flat','full','random'):
                fixture=make_arrays(rng,h,w,stride,kind)
                mask_variation=(flags&0x40 and h>=25 and w>=25)
                if mask_variation and kind!='zero':
                    for y in range(12,h-12):
                        for x in range(12,w-12):
                            low=int(rng.integers(0,256,dtype=np.uint16))
                            if low:
                                packed=low | (int(low.bit_count())<<8)
                                fixture['direction_mask'][y,x]=packed
                                masks.add(low)
                label=f'{h}x{w}/flags_{flags:02x}/{kind}'
                results.append(original_fixture(native,portable,fixture,flags,w,h,case=label))
                modes.add(flags)
        print(json.dumps({'size':f'{h}x{w}', 'bounded_CPU_ColorNoise_check':'EXACT'}),flush=True)
    for ptr,frozen in native.frozen_profile:
        assert bytes(native.u.mem_read(ptr,len(frozen)))==frozen
    native.check_guards()
    assert hashlib.sha256(args.apk.read_bytes()).digest()==immutable
    report={'schema':'hasselblad-stage65-colour-noise-direct-native-v1',
      'status':'PASS_EXACT_BOUNDED_NATIVE_COLORNOISE',
      'cases':len(results),'exact_storage_elements':sum(x['storage_elements_compared'] for x in results),
      'directional_ycc_actual_native_calls':sum(x['nonzero_mask_original_calls'] for x in results),
      'modes_tested':sorted(modes),'unique_low_masks_used':len(masks),
      'configuration':'manual supported scalar CPU fixtures; zero extended strength; 8px conversion,12px directional margins',
      'original_executable_or_photo_exported':False,'source_binary_modified':False,
      'source_profile_unchanged':True,'undefined_behavior_sanitizer':args.sanitize,
      'full_demosaic_independent':False,'device_comparison_performed':False}
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'cases':report['cases']}),flush=True)

if __name__=='__main__':main()
