#!/usr/bin/env python3
"""Original-CPU colour-site gradient operand parity, when Unicorn is installed.

Prepared, NOT executed in the current environment. The original SIMD
instructions still run. Only operands to GetGreenAtRedFirst are checked and
(optionally) replaced; this does NOT port the complete pixel loop.
Keep native binary, raw DNG, profiles and hashes outside public receipts.
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
sys.path.insert(0,str(ROOT/'phocus_interpolation_stage62'))
sys.path.insert(0,str(ROOT/'phocus_gradient_stage61'))
from audit_integration63 import (GreenRunner,PortableMaps,PortableInterpolation,
    PortableGreen,load_private,synthetic_patterns,pad_bayer,prepare_private_dng)
from audit_green63 import GREEN_FIRST
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X21, UC_ARM64_REG_SP


def build(work,sanitize):
    work.mkdir(parents=True,exist_ok=True)
    so=work/'lib_colour_site68.so'
    cmd=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
         '-fno-fast-math','-ffp-contract=off','-fPIC','-shared']
    if sanitize: cmd+=['-fsanitize=undefined','-fno-sanitize-recover=all']
    subprocess.run([*cmd,str(Path(__file__).with_name('colour_gradient68.c')),
        str(ROOT/'phocus_inline_stage67/raw_gradient67.c'),'-o',str(so)],check=True)
    lib=C.CDLL(str(so))
    fn=lib.hb_colour_raw_gradient68
    fn.argtypes=[C.c_void_p,C.c_int,C.c_void_p];fn.restype=C.c_int
    return lib


class ColourOperand68(GreenRunner):
    def __init__(self,elf,profile,maps,interp,green,lib,sample_every):
        self.colour_lib68=lib
        self.sample_every=sample_every
        self.opcode_observations=Counter()
        self.native_original_calls=0
        self.native_substituted_calls=0
        self.operand_overwrites=0
        super().__init__(elf,profile,maps,interp,green)

    def native_stencil(self,center,stride,dtype):
        size=np.dtype(dtype).itemsize
        return np.stack([self.array(center+(dy*stride-2)*size,(5,),dtype)
                         for dy in (-2,-1,0,1,2)])

    def hook(self,cpu,address,size,user):
        name=self.e.plt.get(address,'')
        if self.gradient_active and name==GREEN_FIRST:
            label='substituted' if self.replace else 'original'
            if self.replace: self.native_substituted_calls+=1
            else:self.native_original_calls+=1
            n=self.native_substituted_calls if self.replace else self.native_original_calls
            if n<=64 or n%self.sample_every==0:
                reg=lambda i:cpu.reg_read(UC_ARM64_REG_X0+i)
                stride=reg(6)&0xffffffff
                assert 5<=stride<=4096
                stack=cpu.reg_read(UC_ARM64_REG_SP)
                _,first_ptr,second_ptr,_=self.get(stack,0,'<4Q')
                original_second=self.array(second_ptr,(8,),'<i2')
                raw=self.native_stencil(reg(1),stride,'<u2')
                independent=np.empty(8,'<i2')
                assert self.colour_lib68.hb_colour_raw_gradient68(
                    raw.ctypes.data+24,5,independent.ctypes.data)==0
                assert np.array_equal(original_second,independent),(
                    'private colour-site raw gradient operand mismatch',label,n)
                self.opcode_observations[label]+=1
                # Optional signed-edge candidate: the original GetGradientSingleStep
                # obtains its centre from the original edge plane at object+0x90;
                # the RAW base remains x21 in this scoped scalar InterpolateRGB.
                try:
                    edge_base=self.get(reg(0),0x90,'<Q')[0]
                    raw_base=cpu.reg_read(UC_ARM64_REG_X21)
                    delta=reg(1)-raw_base
                    if edge_base and 0<=delta<0x1000000 and delta%2==0:
                        edge=self.native_stencil(edge_base+delta,stride,'<i2')
                        first=self.array(first_ptr,(8,),'<i2')
                        first_c=np.empty(8,'<i2')
                        assert self.portable.lib.hb_gradient_directions61(
                            edge.ctypes.data+24,5,first_c.ctypes.data)==0
                        assert np.array_equal(first,first_c),(
                            'private colour-site signed gradient mismatch',label,n)
                        self.opcode_observations[label+'_signed_edge']+=1
                except (ValueError,RuntimeError):
                    # No claim about the optional signed-edge plane unless read.
                    pass
                if self.replace:
                    # This cannot skip the original SIMD instructions, which
                    # already ran. It only replaces the next helper operand.
                    cpu.mem_write(second_ptr,independent.tobytes())
                    self.operand_overwrites+=1
        return super().hook(cpu,address,size,user)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',required=True,type=Path)
    p.add_argument('--dng',type=Path)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--safe-receipt',required=True,type=Path)
    p.add_argument('--sanitize',action='store_true')
    p.add_argument('--sample-every',type=int,default=31)
    args=p.parse_args();assert __debug__
    if args.sample_every<1:p.error('--sample-every must be positive')
    paths=[args.apk]+([args.dng] if args.dng else [])
    frozen=[hashlib.sha256(x.read_bytes()).digest() for x in paths]
    maps=PortableMaps(args.work/'maps',sanitize=args.sanitize)
    interp=PortableInterpolation(args.work/'interp',sanitize=args.sanitize)
    green=PortableGreen(args.work/'green',sanitize=args.sanitize)
    lib=build(args.work/'colour',args.sanitize)
    r=ColourOperand68(*load_private(args.apk),maps,interp,green,lib,args.sample_every)
    r.setup_graph()
    cases=[]
    for name,mosaic in synthetic_patterns():
        cases.append(r.compare(pad_bayer(mosaic,32),name+'/bypass'))
        corrected=r.black59(mosaic[...,None],512)[...,0]
        fast=r.fast(pad_bayer(corrected,36))
        r.prepare((.5,.7,1.),(65023,)*3)
        highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
        cases.append(r.compare(r.remosaic(highlighted),name+'/highlight_Bayer'))
        print(json.dumps({'synthetic_case':name,'stage68_operand_parity':'EXACT'}),flush=True)
    private_tiles=0
    if args.dng:
        mosaic,gains,_=prepare_private_dng(args.dng)
        height,width=mosaic.shape
        for gy,gx in ((1,1),(1,3),(3,1),(3,3)):
            top,left=(gy*height//4-16)//2*2,(gx*width//4-16)//2*2
            patch=mosaic[top-36:top+68,left-36:left+68]
            assert patch.shape==(104,104)
            cases.append(r.compare(patch[4:-4,4:-4],f'grid_{gy}_{gx}/bypass'))
            fast=r.fast(patch);r.prepare(gains,(65535,)*3)
            highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
            cases.append(r.compare(r.remosaic(highlighted),f'grid_{gy}_{gx}/highlight_Bayer'))
            private_tiles+=2
    r.check_guards()
    for ptr,original in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(original)))==original
    assert [hashlib.sha256(x.read_bytes()).digest() for x in paths]==frozen
    assert r.opcode_observations['original']>0
    assert r.opcode_observations['substituted']>0
    assert r.operand_overwrites>0
    report={'schema':'hasselblad-stage68-native-colour-site-operand-v1',
        'status':'PASS_ORIGINAL_CPU_COLOUR_SITE_OPERAND' ,
        'original_helper_calls':r.native_original_calls,
        'substituted_helper_calls':r.native_substituted_calls,
        'native_operand_samples_compared':dict(r.opcode_observations),
        'new_raw_operand_replacements':r.operand_overwrites,
        'linear_RGB16_channels_exact':sum(x['exact_rgb16_channels'] for x in cases),
        'original_inline_SIMD_still_executes':True,
        'complete_independent_demosaic':False,
        'device_parity':False,
        'private_DNG_tiles_compared':private_tiles,
        'source_apk_modified':False,
        'source_dng_modified':False}
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'stage68_status':report['status'],
                      'channel_checks':report['linear_RGB16_channels_exact']}),flush=True)

if __name__=='__main__':main()
