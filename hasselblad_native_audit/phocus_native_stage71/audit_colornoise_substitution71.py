#!/usr/bin/env python3
"""Bounded 12th-component ColorNoise substitution into original Phocus CPU demosaic.

Original vendor binary/photograph supplied locally; never bundled with this code.
The original InterpolateRGB loop and other native functions still execute.
"""
import argparse
from collections import Counter
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X30, UC_ARM64_REG_PC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_colour_stage64'))
sys.path.insert(0, str(ROOT / 'phocus_noise_stage65'))
from audit_integration64 import (ColourRunner, PortableMaps, PortableInterpolation,
    PortableGreen, PortableYCC, load_private, synthetic_patterns, pad_bayer,
    prepare_private_dng)
from portable65 import PortableNoise65, NoiseCounters65

COLOR_NOISE = '_ZN20CGradientInterpolate10ColorNoiseEii'
NATIVE_OFFSETS = {'red':0xb0, 'green':0xb8, 'blue':0xc0,
    'y':0xd0, 'c1':0xd8, 'c2':0xe0, 'direction_mask':0xc8,
    'smooth_y':0x98, 'median_c1':0xa0, 'median_c2':0xa8,
    'out_y':0x68, 'out_c1':0x70, 'out_c2':0x78, 'out_aux':0x80}
UNSIGNED = {'red','green','blue','y','direction_mask','smooth_y','out_y'}
READONLY = {'red','green','blue','direction_mask'}
OUTPUTS = set(NATIVE_OFFSETS)-READONLY

class ColorNoiseRunner71(ColourRunner):
    def __init__(self, elf, profile, maps, interp, green, ycc, noise, probe=False):
        self.noise_portable = noise
        self.noise_entry_original = elf.func[COLOR_NOISE][0]
        self.probe = probe
        self.probe_only = False
        self.graph_observations = Counter()
        self.noise_replacements = 0
        self.noise_counters = Counter()
        self.max_native_plane_overlap = 0
        super().__init__(elf, profile, maps, interp, green, ycc)

    def _context(self, cpu):
        obj = cpu.reg_read(UC_ARM64_REG_X0)
        width = cpu.reg_read(UC_ARM64_REG_X1) & 0xffffffff
        height = cpu.reg_read(UC_ARM64_REG_X2) & 0xffffffff
        flags = self.get(obj, 0x38, '<H')[0]
        optimized = self.get(obj, 0x08, '<B')[0]
        strength = self.get(obj, 0x28, '<i')[0]
        stride = self.get(obj, 0x3c, '<i')[0]
        if not (25 <= width <= stride <= 4096 and 25 <= height <= 4096 and
                height * stride <= 600000):
            raise AssertionError(('unsupported native ColorNoise dimensions',width,height,stride))
        if flags != 0xffff or optimized or strength != 0:
            raise AssertionError(('unsupported graph branch',flags,optimized,strength))
        ptrs = {name:self.get(obj,off,'<Q')[0] for name,off in NATIVE_OFFSETS.items()}
        if not all(x>0 for x in ptrs.values()):
            raise AssertionError('Null native ColorNoise buffer')
        ranges = [(ptr,ptr+height*stride*2,name) for name,ptr in ptrs.items()]
        overlaps = [(a,b) for i,(start,end,a) in enumerate(ranges)
                    for start2,end2,b in ranges[i+1:]
                    if start<end2 and start2<end]
        self.max_native_plane_overlap = max(self.max_native_plane_overlap,len(overlaps))
        if overlaps:
            raise AssertionError(('Unsupported native plane overlap',overlaps))
        self.graph_observations[(flags,optimized,strength,width,height,stride)]+=1
        return width,height,stride,flags,optimized,strength,ptrs

    def hook(self,cpu,address,size,user):
        if self.gradient_active and address==self.noise_entry_original:
            width,height,stride,flags,opt,strength,ptrs=self._context(cpu)
            if self.probe_only:
                # This call still executes the original body for geometry probes.
                return super().hook(cpu,address,size,user)
            if self.replace:
                shape=(height,stride)
                arrays={name:self.array(ptr,shape,'<u2' if name in UNSIGNED else '<i2')
                        for name,ptr in ptrs.items()}
                pristine={name:arrays[name].tobytes() for name in READONLY}
                ctx=self.noise_portable.bind(arrays,width,height,flags,strength,opt)
                counters=NoiseCounters65()
                result=self.noise_portable.lib.hb_color_noise65(C.byref(ctx),C.byref(counters))
                if result!=0:
                    raise AssertionError(('ColorNoise independent rejected graph',result))
                for name in READONLY:
                    assert arrays[name].tobytes()==pristine[name], ('input mutated',name)
                for name in OUTPUTS:
                    cpu.mem_write(ptrs[name],arrays[name].tobytes())
                self.noise_replacements+=1
                for key in ('converted_sites','clamped_sites','smoothing_rows','median_rows',
                            'correction_sites','nonzero_mask_sites','median_selected_sites'):
                    self.noise_counters[key]+=int(getattr(counters,key))
                cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))
                return
        return super().hook(cpu,address,size,user)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--dng',type=Path)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sanitize',action='store_true')
    p.add_argument('--probe-only',action='store_true')
    p.add_argument('--fixture',choices=('neutral','flat_colour','ramp','colour_edge','red_impulse','random_codes','all'),default='neutral')
    a=p.parse_args(); assert __debug__
    original_files=[a.apk]+([a.dng] if a.dng else [])
    initial_hashes=[hashlib.sha256(f.read_bytes()).digest() for f in original_files]
    noise=PortableNoise65(a.work/'noise',sanitize=a.sanitize)
    r=ColorNoiseRunner71(*load_private(a.apk),
        PortableMaps(a.work/'maps',sanitize=a.sanitize),
        PortableInterpolation(a.work/'interp',sanitize=a.sanitize),
        PortableGreen(a.work/'green',sanitize=a.sanitize),
        PortableYCC(a.work/'ycc',sanitize=a.sanitize),noise,probe=a.probe_only)
    r.probe_only=a.probe_only
    r.setup_graph()
    cases=[]
    for name,bayer in synthetic_patterns():
        if a.fixture not in ('all',name):continue
        padded=pad_bayer(bayer,32)
        if a.probe_only:
            r.replace=False
            r.demosaic(padded)
            print(json.dumps({'fixture':name,'graph_probed':True,'observed_contracts':len(r.graph_observations)}),flush=True)
        else:
            cases.append(r.compare(padded,name+'/highlight_bypass'))
            corrected=r.black59(bayer[...,None],512)[...,0]
            fast=r.fast(pad_bayer(corrected,36))
            r.prepare((.5,.7,1.),(65023,)*3)
            highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
            cases.append(r.compare(r.remosaic(highlighted),name+'/highlight_Bayer'))
            print(json.dumps({'fixture':name,'two_highlight_modes':'PASS'}),flush=True)
    if a.dng and not a.probe_only:
        mosaic,gains,_=prepare_private_dng(a.dng)
        h,w=mosaic.shape
        for idx,(gy,gx) in enumerate(((1,1),(1,3),(3,1),(3,3)),1):
            top,left=(gy*h//4-16)//2*2,(gx*w//4-16)//2*2
            patch=mosaic[top-36:top+68,left-36:left+68]
            assert patch.shape==(104,104)
            cases.append(r.compare(patch[4:-4,4:-4],f'private_tile_{idx}/highlight_bypass'))
            fast=r.fast(patch)
            r.prepare(gains,(65535,)*3)
            highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
            cases.append(r.compare(r.remosaic(highlighted),f'private_tile_{idx}/highlight_Bayer'))
            print(json.dumps({'tile':idx,'two_highlight_modes':'PASS'}),flush=True)
    r.check_guards()
    for ptr,frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(frozen)))==frozen
    assert initial_hashes==[hashlib.sha256(f.read_bytes()).digest() for f in original_files]
    assert r.graph_observations
    if not a.probe_only:
        assert r.noise_replacements==len(cases)
        assert COLOR_NOISE not in r.original_entries_when_replaced
    status='PASS_NATIVE_GRAPH_CONTEXT_OBSERVED' if a.probe_only else 'PASS_EXACT_TWELVE_COMPONENT_SUBSTITUTION'
    report={'schema':'hasselblad-stage71-noise-substitution-v1','status':status,
       'configuration':[{'flags':k[0],'optimized_view':bool(k[1]),'strength':k[2],
                         'width':k[3],'height':k[4],'stride':k[5], 'calls':v}
                         for k,v in sorted(r.graph_observations.items())],
       'native_plane_overlap_count':r.max_native_plane_overlap,
       'independent_colornoise_calls':r.noise_replacements,
       'independent_colornoise_counters':dict(r.noise_counters),
       'checked_fixture_names':[x['fixture'] for x in cases],
       'exact_linear_rgb16_channels':sum(x['exact_rgb16_channels'] for x in cases),
       'maximum_absolute_rgb16_difference':0 if not a.probe_only else None,
       'original_noise_body_skipped_in_substituted_run':not a.probe_only,
       'other_native_gradient_and_pixel_loop_operations_still_execute':True,
       'complete_independent_demosaic':False,'device_parity':False,
       'source_apk_and_private_dng_unchanged':True,
       'private_photo_and_original_executable_exported':False}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':status,'noise_replacements':r.noise_replacements,
        'exact_rgb16_channels':report['exact_linear_rgb16_channels']}),flush=True)
if __name__=='__main__':main()
