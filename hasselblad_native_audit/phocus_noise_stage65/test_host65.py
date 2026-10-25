#!/usr/bin/env python3
"""Independent Python-versus-C host tests for supported ColorNoise65 routes.

All fixtures are generated synthetically. Tests involving a nonzero direction
mask are done separately with the Stage64 independent YCC candidate.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import numpy as np
from portable65 import PortableNoise65, NoiseCounters65
import ctypes as C

KEYS = ('red', 'green', 'blue', 'y', 'c1', 'c2', 'direction_mask',
        'smooth_y', 'median_c1', 'median_c2', 'out_y', 'out_c1', 'out_c2', 'out_aux')
SOURCES_U16 = {'red', 'green', 'blue', 'y', 'direction_mask', 'smooth_y', 'out_y'}


def make_arrays(rng, h, width, stride, kind):
    arrays = {}
    for key in KEYS:
        if key in SOURCES_U16:
            a = rng.integers(0, 65536, (h, stride), dtype=np.uint16)
        else:
            a = rng.integers(-32768, 32768, (h, stride), dtype=np.int16)
        arrays[key] = a
    if kind == 'flat':
        arrays['red'].fill(10000); arrays['green'].fill(10000); arrays['blue'].fill(10000)
        arrays['y'].fill(10000); arrays['c1'].fill(0); arrays['c2'].fill(0)
    if kind == 'full':
        arrays['red'].fill(65535); arrays['green'].fill(0); arrays['blue'].fill(0)
        arrays['y'].fill(65535); arrays['c1'].fill(-32768); arrays['c2'].fill(32767)
    if kind == 'zero':
        for key in ('red', 'green', 'blue', 'y', 'c1', 'c2'):
            arrays[key].fill(0)
    arrays['direction_mask'].fill(0)
    return arrays


def med3(a,b,c):
    return sorted((a,b,c))[1]


def reference65(a, width, height, flags, optimized_view=0, strength=0):
    stride = a['y'].shape[1]
    ctr = Counter()
    if (flags & 0x40) and not optimized_view and strength > 0:
        return -2, ctr
    if (flags & 0x20) and width >= 17 and height >= 17:
        for yy in range(8, height-8):
            for xx in range(8,width-8):
                p = yy,xx
                r,g,b = (int(a[key][p]) for key in ('red','green','blue'))
                total = r+2*g+b
                a['y'][p] = total >> 2
                # Python // rounds toward -infinity, but ARM/C signed SDIV
                # truncates toward zero, including for negative chroma.
                a['c1'][p] = int(np.int16(np.uint16(((abs(r-g)*32768)//(total+1)) * (1 if r>=g else -1) & 65535)))
                a['c2'][p] = int(np.int16(np.uint16(((abs(b-g)*32768)//(total+1)) * (1 if b>=g else -1) & 65535)))
                ctr['converted_sites'] += 1
        # The original clamp starts at horizontal column zero, not eight;
        # flat indexing preserves its negative-neighbour cross-row accesses.
        flat_y=a['y'].ravel()
        for yy in range(8,height-8):
            for xx in range(0,width-16):
                center=yy*stride+xx
                neighbours=[int(flat_y[center+dy*stride+dx]) for dy in (-1,0,1)
                            for dx in (-1,0,1) if (dx,dy)!=(0,0)]
                value=int(flat_y[center])
                flat_y[center]=min(max(value,min(neighbours)),max(neighbours))
                ctr['clamped_sites'] += 1
    if (flags & 0x40) and not optimized_view and height >= 3:
        for yy in range(1,height-1):
            for xx in range(width):
                if xx==0 or xx==width-1:
                    a['smooth_y'][yy,xx]=0
                    for o,i in (('median_c1','c1'),('median_c2','c2')):
                        a[o][yy,xx]=a[i][yy,xx]
                    continue
                p=lambda dy,dx: int(a['y'][yy+dy,xx+dx])
                corner=p(-1,-1)+p(-1,1)+p(1,-1)+p(1,1)
                cross=p(-1,0)+p(1,0)+p(0,-1)+p(0,1)
                a['smooth_y'][yy,xx]=(corner+2*cross+4*p(0,0))//16
                for output,source in (('median_c1','c1'),('median_c2','c2')):
                    three = [med3(*[int(a[source][yy+dy,xx+dx]) for dx in (-1,0,1)])
                             for dy in (-1,0,1)]
                    a[output][yy,xx]=med3(*three)
            ctr['smoothing_rows'] += 1
            ctr['median_rows'] += 2
    if (flags & 0x40) and not optimized_view and width >= 25 and height >= 25:
        for yy in range(12,height-12):
            for xx in range(12,width-12):
                assert a['direction_mask'][yy,xx]==0
                a['out_y'][yy,xx]=a['y'][yy,xx]
                a['out_aux'][yy,xx]=0
                one,two = int(a['c1'][yy,xx]),int(a['c2'][yy,xx])
                m1,m2 = int(a['median_c1'][yy,xx]),int(a['median_c2'][yy,xx])
                # Vector compare after signed 16-bit narrowing of sums.
                score_med=int(np.array([(abs(m1)+abs(m2))&65535],'<u2').view('<i2')[0])
                score_old=int(np.array([(abs(one)+abs(two))&65535],'<u2').view('<i2')[0])
                if score_old > score_med:
                    one,two=m1,m2
                    ctr['median_selected_sites']+=1
                a['out_c1'][yy,xx]=one;a['out_c2'][yy,xx]=two
                ctr['correction_sites']+=1
    return 0,ctr


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sanitize',action='store_true')
    args=p.parse_args()
    assert __debug__
    candidate=PortableNoise65(args.work,sanitize=args.sanitize)
    rng=np.random.default_rng(6501)
    dims=((3,1,5),(16,16,21),(17,17,20),(24,28,32),(25,25,29),
          (26,28,32),(40,48,52),(34,36,39))
    kinds=('zero','flat','full','random')
    flags_list=(0x00,0x20,0x40,0x60)
    checked=0;compared=0;unsup=0;counts=Counter()
    for h,width,stride in dims:
        for kind in kinds:
            for flags in flags_list:
                for view,strength in ((0,0),(1,0),(0,1)):
                    initial=make_arrays(rng,h,width,stride,kind)
                    portable={key:a.copy() for key,a in initial.items()}
                    original={key:a.copy() for key,a in initial.items()}
                    context=candidate.bind(portable,width,h,flags,strength,view)
                    counter=NoiseCounters65()
                    ret=candidate.lib.hb_color_noise65(C.byref(context),C.byref(counter))
                    expected,summary=reference65(original,width,h,flags,view,strength)
                    assert ret==expected,(h,width,stride,kind,flags,view,strength,ret,expected)
                    for key in KEYS:
                        assert portable[key].tobytes()==original[key].tobytes(),(key,h,width,stride,kind,flags,view,strength)
                        compared+=original[key].size
                    if ret==0:
                        for name in (name for name,_ in counter._fields_):
                            assert int(getattr(counter,name))==summary.get(name,0),(name,h,width,stride,kind,flags,view,strength)
                            counts[name]+=int(getattr(counter,name))
                    else:
                        unsup+=1
                    checked+=1
    out={'schema':'hasselblad-stage65-noise-bounded-host-v1',
         'status':'PASS_INDEPENDENT_SYNTHETIC_HOST_CHECKS',
         'synthetic_input_cases':checked,
         'compared_storage_elements_including_unwritten':compared,
         'unsupported_positive_strength_cases':unsup,
         'counted_supported_operations':dict(counts),
         'max_difference':0,
         'original_cpu_comparison_performed':False,
         'stage64_ycc_native_parity_established':False,
         'full_colornoise_original_equivalence':False,
         'full_gradient_demosaic_port':False,
         'device_renderer_changed':False,
         'source_apk_or_photo_used':False,
         'scene_fitted_parameters':0}
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
