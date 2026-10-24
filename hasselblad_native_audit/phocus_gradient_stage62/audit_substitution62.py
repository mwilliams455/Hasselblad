#!/usr/bin/env python3
"""Substitute two independently reconstructed interpolation helpers plus Stage61.

Requires the privately supplied original Phocus APK and the Stage61 original
native runtime. New C calls receive *snapshotted* Bayer-neighbourhood data.
Never publish the original binary, executable disassembly or private pixels.
This connected comparison MUST execute before claiming final native parity.
"""
import argparse
from collections import Counter
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'phocus_gradient_stage61'))
from audit_integration61 import (SubstitutionRunner, PortableMaps, PORT_NAMES,
    load_private, synthetic_patterns, pad_bayer, prepare_private_dng)
from helper_trace62 import BLUE,RED_BLUE
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X30,UC_ARM64_REG_PC


class PortableInterpolation62:
    def __init__(self,work,sanitize=False):
        path=Path(work)/'libinterpolate62.so'
        args=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
              '-fno-fast-math','-ffp-contract=off','-fPIC','-shared']
        if sanitize:args.extend(['-fsanitize=undefined','-fno-sanitize-recover=all'])
        subprocess.run([*args,str(HERE/'interpolate62.c'),'-o',str(path)],
                       check=True,capture_output=True)
        self.lib=C.CDLL(str(path))
        self.lib.hb_blue_at_red_code62.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32,C.c_int]
        self.lib.hb_blue_at_red_code62.restype=C.c_uint32
        self.lib.hb_red_blue_at_green62.argtypes=[C.c_void_p]*5+[C.c_uint32,C.c_int]
        self.lib.hb_red_blue_at_green62.restype=C.c_int


class NineKernelSubstitutionRunner(SubstitutionRunner):
    def __init__(self,elf,profile,portable61,portable62):
        self.portable62=portable62
        self.interpolation_replacements=Counter()
        super().__init__(elf,profile,portable61)

    def _stencil(self,base,stride,diagonal):
        # Read only sample coordinates the original helper actually uses.
        # All source samples are private; never log these values.
        st=np.zeros((3,3),'<u2')
        st[1,1]=struct.unpack('<H',self.u.mem_read(base,2))[0]
        points=((-1,-1),(-1,1),(1,-1),(1,1)) if diagonal else (
                (-1,0),(0,1),(1,0),(0,-1))
        for dy,dx in points:
            ptr=base+2*(dy*stride+dx)
            st[dy+1,dx+1]=struct.unpack('<H',self.u.mem_read(ptr,2))[0]
        return st

    def hook(self,cpu,address,size,user):
        name=self.e.plt.get(address,'')
        if not (self.gradient_active and self.replace and name in (BLUE,RED_BLUE)):
            return super().hook(cpu,address,size,user)
        reg=lambda i:int(cpu.reg_read(UC_ARM64_REG_X0+i))
        signed32=lambda v:struct.unpack('<i',struct.pack('<I',v&0xffffffff))[0]
        stride=signed32(reg(3 if name==BLUE else 6))
        assert 3<=stride<=8192, ('unexpected native stride',stride)
        mask=reg(2 if name==BLUE else 5)&0xffffffff
        if name==BLUE:
            chroma=self._stencil(reg(0),stride,True)
            green=self._stencil(reg(1),stride,True)
            result=self.portable62.lib.hb_blue_at_red_code62(
                chroma.ctypes.data+8,green.ctypes.data+8,mask,3)
            cpu.reg_write(UC_ARM64_REG_X0,int(result))
            self.interpolation_replacements['blue_at_red']+=1
        else:
            colour_a=self._stencil(reg(0),stride,False)
            green=self._stencil(reg(1),stride,False)
            colour_b=self._stencil(reg(2),stride,False)
            output_a=C.c_uint16()
            output_b=C.c_uint16()
            status=self.portable62.lib.hb_red_blue_at_green62(
                colour_a.ctypes.data+8,green.ctypes.data+8,
                colour_b.ctypes.data+8,C.addressof(output_a),
                C.addressof(output_b),mask,3)
            assert status==0
            # Native writes second reference first, then first; this matters
            # if both refer to the same location or overlap input planes.
            cpu.mem_write(reg(4),struct.pack('<H',output_b.value))
            cpu.mem_write(reg(3),struct.pack('<H',output_a.value))
            self.interpolation_replacements['red_blue_at_green']+=1
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--dng',type=Path)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sanitize',action='store_true')
    a=p.parse_args()
    assert __debug__
    work=a.work.resolve();repo=HERE.parents[1]
    if work==repo or repo in work.parents:
        p.error('private work directory must be outside repository')
    work.mkdir(parents=True,exist_ok=True)
    inputs=[a.apk]+([a.dng] if a.dng else [])
    frozen=[hashlib.sha256(f.read_bytes()).digest() for f in inputs]
    portable61=PortableMaps(work,sanitize=a.sanitize)
    portable62=PortableInterpolation62(work,sanitize=a.sanitize)
    r=NineKernelSubstitutionRunner(*load_private(a.apk),portable61,portable62)
    r.setup_graph()
    synthetic=[];saved=[]
    for name,mosaic in synthetic_patterns():
        synthetic.append(r.compare(pad_bayer(mosaic,32),name+'/highlight_bypass'))
        corrected=r.black59(mosaic[...,None],512)[...,0]
        fast=r.fast(pad_bayer(corrected,36))
        r.prepare((.5,.7,1.),(65023,)*3)
        highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
        synthetic.append(r.compare(r.remosaic(highlighted),name+'/highlight_bayer_chain'))
        print(json.dumps({'synthetic_fixture':name,'nine_substitutions':'PASS_EXACT'}),flush=True)
    if a.dng:
        mosaic,gains,maps=prepare_private_dng(a.dng)
        h,w=mosaic.shape
        for number,(gy,gx) in enumerate(((1,1),(1,3),(3,1),(3,3)),1):
            top,left=(gy*h//4-16)//2*2,(gx*w//4-16)//2*2
            patch=mosaic[top-36:top+68,left-36:left+68]
            assert patch.shape==(104,104)
            saved.append(r.compare(patch[4:-4,4:-4],
                                   'fixed_grid_'+str(number)+'/highlight_bypass'))
            fast=r.fast(patch);r.prepare(gains,(65535,)*3)
            highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
            saved.append(r.compare(r.remosaic(highlighted),
                                   'fixed_grid_'+str(number)+'/highlight_bayer_chain'))
            print(json.dumps({'private_tile':number,'nine_substitutions':'PASS_EXACT'}),flush=True)
    r.check_guards()
    for ptr,b in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(b)))==b
    assert all(r.replacements[n]>0 for n in PORT_NAMES.values())
    assert all(r.interpolation_replacements[n]>0 for n in
               ('blue_at_red','red_blue_at_green'))
    assert frozen==[hashlib.sha256(f.read_bytes()).digest() for f in inputs]
    result={
      'schema':'hasselblad-stage62-nine-kernel-native-substitution-v1',
      'status':'PASS_EXACT_SUBSTITUTED_RGB16',
      'stage61_c_kernels_substituted':len(PORT_NAMES),
      'stage62_c_helpers_substituted':2,
      'stage62_helper_calls':dict(r.interpolation_replacements),
      'synthetic_comparisons':synthetic,'private_dng_comparisons':saved,
      'synthetic_exact_rgb16_channels':sum(x['exact_rgb16_channels'] for x in synthetic),
      'private_dng_exact_rgb16_channels':sum(x['exact_rgb16_channels'] for x in saved),
      'remaining_native_green_estimation_colour_noise_pixel_loop':True,
      'complete_independent_demosaic':False,
      'source_apk_modified':False,'source_dng_modified':False,
      'source_photograph_pixels_exported':False,'capture_renderer_changed':False,
      'device_executed':False,'physical_hasselblad_colour_match_validated':False,
      'scene_specific_tuning':False,
    }
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],
                      'interpolation_replacements':dict(r.interpolation_replacements)}),flush=True)


if __name__=='__main__':main()
