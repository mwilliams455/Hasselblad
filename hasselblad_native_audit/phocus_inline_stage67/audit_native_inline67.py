#!/usr/bin/env python3
"""Prepared Stage67 original-CPU green-site inline-gradient boundary audit.

REQUIRES local private Phocus APK and Stage60–63 original Unicorn runner.
It is not yet executed in the current environment. No executable bytes,
private raw tiles, sample values, camera calibration, or hashes exported.

At each original GetGradientMask call, compare independent C RAW gradients
against the native inline SIMD operand, and Stage61 signed-edge gradients
against the native signed operand. In substitution mode replace the eight RAW
operands with the independent C outputs before the downstream mask helper.
This does not skip execution of the inline SIMD work or port the full loop.
"""
import argparse
from collections import Counter
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_green_stage63'))
sys.path.insert(0,str(ROOT/'phocus_gradient_stage61'))
from audit_integration63 import (GreenRunner,PortableMaps,PortableInterpolation,
                                  PortableGreen,load_private,synthetic_patterns,pad_bayer)
from audit_kernels61 import MASK
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X19,
                                  UC_ARM64_REG_X20, UC_ARM64_REG_X24)


class NativeInline67(GreenRunner):
    def __init__(self,elf,profile,maps,interpolation,green,lib,sample_every):
        self.inline_lib=lib
        self.sample_every=sample_every
        self.original_mask_entries=0
        self.substituted_mask_entries=0
        self.checked_native_inline=0
        self.checked_native_signed=0
        self.outward_gradient_overwrites=0
        self.coverage=Counter()
        super().__init__(elf,profile,maps,interpolation,green)

    def stencil(self,ptr,stride,dtype):
        return np.stack([
            self.array(ptr+(dy*stride-2)*np.dtype(dtype).itemsize,(5,),dtype)
            for dy in range(-2,3)])

    def hook(self,cpu,address,size,user):
        symbol=self.e.plt.get(address,'')
        if self.gradient_active and symbol==MASK:
            # This PLT entry is called for green-site masks in the audited
            # scalar InterpolateRGB. Check the original object and pointers.
            read=lambda i:cpu.reg_read(UC_ARM64_REG_X0+i)
            obj=read(0)
            stride=self.get(obj,0x3c,'<i')[0]
            if not 5<=stride<=4096:
                raise AssertionError('Unsupported native green-site stride')
            count=(self.substituted_mask_entries if self.replace else self.original_mask_entries)+1
            if self.replace:self.substituted_mask_entries+=1
            else:self.original_mask_entries+=1
            if count<=64 or count%self.sample_every==0:
                offset=cpu.reg_read(UC_ARM64_REG_X24)
                native_raw_center=cpu.reg_read(UC_ARM64_REG_X20)+offset
                original=np.asarray(self.array(read(2),(8,),'<i2'))
                first=np.asarray(self.array(read(1),(8,),'<i2'))
                raw=self.stencil(native_raw_center,stride,'<u2')
                edge_base=self.get(obj,0x90,'<Q')[0]
                edge=self.stencil(edge_base+offset,stride,'<i2')
                calc_raw=np.zeros(8,np.int16)
                calc_edge=np.zeros(8,np.int16)
                status=self.inline_lib.hb_inline_raw_gradient67(
                    raw.ctypes.data+24,5,calc_raw.ctypes.data)
                assert status==0
                assert self.portable.lib.hb_gradient_directions61(
                    edge.ctypes.data+24,5,calc_edge.ctypes.data)==0
                if not np.array_equal(original,calc_raw):
                    raise AssertionError('RAW inline gradient mismatch: private inputs omitted')
                if not np.array_equal(first,calc_edge):
                    raise AssertionError('Stage61 signed gradient operand mismatch')
                self.checked_native_inline+=1
                self.checked_native_signed+=1
                self.coverage['original' if not self.replace else 'substituted']+=1
                if self.replace:
                    # Original inline SIMD already executed; only its output
                    # is replaced. This is not a complete independent loop.
                    cpu.mem_write(read(2),calc_raw.tobytes())
                    self.outward_gradient_overwrites+=1
        return super().hook(cpu,address,size,user)


def build(src,dst,sanitize=False):
    dst.parent.mkdir(parents=True,exist_ok=True)
    cmd=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
         '-fno-fast-math','-ffp-contract=off','-shared','-fPIC']
    if sanitize:cmd+=['-fsanitize=undefined','-fno-sanitize-recover=all']
    subprocess.run([*cmd,str(src),'-o',str(dst)],check=True)
    lib=C.CDLL(str(dst)); f=lib.hb_inline_raw_gradient67
    f.argtypes=[C.c_void_p,C.c_int,C.c_void_p];f.restype=C.c_int
    return lib


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sample-every',type=int,default=31)
    p.add_argument('--sanitize',action='store_true')
    a=p.parse_args();assert __debug__
    if a.sample_every<1: p.error('--sample-every must be positive')
    before=hashlib.sha256(a.apk.read_bytes()).digest()
    a.work.mkdir(parents=True,exist_ok=True)
    so=build(Path(__file__).with_name('raw_gradient67.c'),a.work/'libraw67.so',a.sanitize)
    maps=PortableMaps(a.work/'maps',sanitize=a.sanitize)
    interp=PortableInterpolation(a.work/'interpolation',sanitize=a.sanitize)
    green=PortableGreen(a.work/'green',sanitize=a.sanitize)
    r=NativeInline67(*load_private(a.apk),maps,interp,green,so,a.sample_every)
    r.setup_graph()
    results=[]
    for label,mosaic in synthetic_patterns():
        if label not in ('neutral','flat_colour','ramp','colour_edge','red_impulse','random_codes'):
            continue
        image=pad_bayer(mosaic,32)
        results.append(r.compare(image,label+'/original_v_11_component_operand_bridge'))
        print(json.dumps({'fixture':label,'original_v_independent_operand':'EXACT'}),flush=True)
    assert r.original_mask_entries>0 and r.substituted_mask_entries>0
    assert r.checked_native_inline>0 and r.checked_native_signed>0
    assert r.outward_gradient_overwrites>0
    r.check_guards()
    for ptr,profile in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(profile)))==profile
    assert hashlib.sha256(a.apk.read_bytes()).digest()==before
    report={'schema':'hasselblad-stage67-inline-native-boundary-v1',
            'status':'PASS_BOUNDED_NATIVE_OPERAND_SUBSTITUTION',
            'original_mask_entries':r.original_mask_entries,
            'substituted_mask_entries':r.substituted_mask_entries,
            'native_inline_samples_compared_exact':r.checked_native_inline,
            'native_signed_samples_compared_exact':r.checked_native_signed,
            'new_raw_gradient_operand_replacements':r.outward_gradient_overwrites,
            'comparison_scope':'Stage63 bounded CPU graph; aligned RGGB; synthetic padded tiles',
            'exact_final_rgb16_channels':sum(x['exact_rgb16_channels'] for x in results),
            'max_absolute_difference':0,'native_inline_instructions_still_executed':True,
            'complete_independent_demosaic':False,
            'device_execution_compared':False,
            'source_apk_modified':False,'scene_fitted_parameters':0}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],
                      'native_inline_samples_compared_exact':r.checked_native_inline}))
if __name__=='__main__':main()
