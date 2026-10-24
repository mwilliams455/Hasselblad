#!/usr/bin/env python3
"""Substitute independent directional YCC into the ten-component Stage63 graph.

Requires the private original Phocus APK and the existing Stage60-63 emulation
stack. This is a parity runner, NOT evidence that it has actually run here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_green_stage63'))
from audit_integration63 import (GreenRunner,ALL_PORT_NAMES as PREVIOUS_PORT_NAMES,
    PortableMaps, PortableInterpolation,PortableGreen,load_private,
    synthetic_patterns,pad_bayer,prepare_private_dng)
from audit_ycc64 import NATIVE_YCC
from portable64 import PortableYCC
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X30,UC_ARM64_REG_PC,UC_ARM64_REG_SP

ALL_PORT_NAMES={**PREVIOUS_PORT_NAMES,NATIVE_YCC:'directional_ycc'}


class ColourRunner(GreenRunner):
    def __init__(self,elf,profile,maps,interpolation,green,colour):
        self.colour=colour
        self.native_ycc_reference_aliases=0
        super().__init__(elf,profile,maps,interpolation,green)

    def hook(self,cpu,address,size,user):
        name=self.e.plt.get(address,'')
        if not (self.gradient_active and self.replace and name==NATIVE_YCC):
            return super().hook(cpu,address,size,user)
        reg=lambda i:cpu.reg_read(UC_ARM64_REG_X0+i)
        stack=cpu.reg_read(UC_ARM64_REG_SP)
        out_c1,out_c2,out_level=self.get(stack,0,'<3Q')
        stride=self.get(stack,24,'<i')[0]
        assert 3<=stride<=4096,(name,'unsupported stride',stride)
        destinations=[(reg(7),2),(out_c1,2),(out_c2,2),(out_level,2)]
        assert all(p+length<=q or q+other<=p for i,(p,length) in enumerate(destinations)
                   for q,other in destinations[i+1:]),'Output references alias; contract requires investigation'
        if any(reg(i)==p for i in range(1,7) for p,_ in destinations):
            self.native_ycc_reference_aliases+=1
        # Snapshot original source values and the complete 3x3 stencil *before*
        # any potential writes. Each local plane has contiguous stride=3 and
        # origin at index (1,1); the native stride is used only when reading.
        centres=[self.array(reg(i),(1,),dtype) for i,dtype in
                 ((1,'<u2'),(2,'<i2'),(3,'<i2'))]
        planes=[np.stack([self.array(reg(i)+(dy*stride-1)*2,(3,),dtype)
                          for dy in (-1,0,1)]) for i,dtype in
                ((4,'<u2'),(5,'<i2'),(6,'<i2'))]
        outputs=[np.zeros(1,dtype) for dtype in ('<u2','<i2','<i2','<i2')]
        ptr=lambda a:a.ctypes.data
        assert self.colour.lib.hb_directional_ycc64(reg(0)&0xffffffff,
                   *map(ptr,centres),*[ptr(a)+8 for a in planes],
                   *map(ptr,outputs),3)==0
        # These references are distinct in the declared supported call-site
        # contract. Preserve output encodings exactly; no host float path.
        for addr,out in zip((reg(7),out_c1,out_c2,out_level),outputs):
            cpu.mem_write(addr,out.tobytes())
        self.replacements['directional_ycc']+=1
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--dng',type=Path)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sanitize',action='store_true')
    a=p.parse_args();assert __debug__
    paths=[a.apk]+([a.dng] if a.dng else [])
    original_hashes=[hashlib.sha256(p.read_bytes()).digest() for p in paths]
    maps=PortableMaps(a.work/'maps',sanitize=a.sanitize)
    interpolation=PortableInterpolation(a.work/'interpolation',sanitize=a.sanitize)
    green=PortableGreen(a.work/'green',sanitize=a.sanitize)
    colour=PortableYCC(a.work/'colour',sanitize=a.sanitize)
    r=ColourRunner(*load_private(a.apk),maps,interpolation,green,colour)
    r.setup_graph()
    synthetic,saved,held_out=[],[],[]
    patterns=synthetic_patterns()
    rng=np.random.default_rng(6202)
    patterns += [('rectangle_16x24',rng.integers(0,65536,(16,24),dtype=np.uint16)),
                 ('rectangle_18x34',rng.integers(0,65536,(18,34),dtype=np.uint16))]
    for name,mosaic in patterns:
        synthetic.append(r.compare(pad_bayer(mosaic,32),name+'/highlight_bypass'))
        corrected=r.black59(mosaic[...,None],512)[...,0]
        fast=r.fast(pad_bayer(corrected,36));r.prepare((.5,.7,1.),(65023,)*3)
        highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
        synthetic.append(r.compare(r.remosaic(highlighted),name+'/highlight_bayer_chain'))
        print(json.dumps({'synthetic_fixture':name,'independent_ycc_substitution':'EXACT'}),flush=True)
    if a.dng:
        mosaic,gains,_=prepare_private_dng(a.dng)
        h,w=mosaic.shape
        selections=[(saved,'fixed_grid',32,32,((1,1),(1,3),(3,1),(3,3))),
                    (held_out,'held_out_grid',16,24,((1,2),(2,1),(2,3),(3,2)))]
        for destination,label,th,tw,grid in selections:
            for number,(gy,gx) in enumerate(grid,1):
                top,left=(gy*h//4-th//2)//2*2,(gx*w//4-tw//2)//2*2
                patch=mosaic[top-36:top+th+36,left-36:left+tw+36]
                assert patch.shape==(th+72,tw+72)
                prefix=label+'_'+str(number)
                destination.append(r.compare(patch[4:-4,4:-4],prefix+'/highlight_bypass'))
                fast=r.fast(patch);r.prepare(gains,(65535,)*3)
                highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
                destination.append(r.compare(r.remosaic(highlighted),prefix+'/highlight_bayer_chain'))
                print(json.dumps({'private_tile':prefix,'independent_ycc_substitution':'EXACT'}),flush=True)
    r.check_guards()
    for ptr,snapshot in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(snapshot)))==snapshot
    assert all(r.replacements[name]>0 for name in ALL_PORT_NAMES.values())
    assert not r.original_entries_when_replaced.intersection(ALL_PORT_NAMES)
    assert r.alias_calls==r.replacements['red_blue_at_green']
    assert [hashlib.sha256(p.read_bytes()).digest() for p in paths]==original_hashes
    record={'schema':'hasselblad-stage64-colour-substitution-v1',
            'status':'PASS_EXACT_ELEVEN_COMPONENT_SUBSTITUTION',
            'stage63_parent_components':10,
            'new_independent_helper':'DirectionalColorCorrectionYCC',
            'portable_component_count':len(ALL_PORT_NAMES),
            'portable_helper_calls':dict(r.replacements),
            'native_reference_aliased_to_source_calls':r.native_ycc_reference_aliases,
            'original_replaced_function_bodies_executed':False,
            'synthetic_comparisons':synthetic,'private_dng_comparisons':saved,
            'held_out_private_dng_comparisons':held_out,
            'total_exact_rgb16_channels':sum(x['exact_rgb16_channels'] for x in synthetic+saved+held_out),
            'native_original_invocations':r.original_invocations,
            'native_substituted_invocations':r.substituted_invocations,
            'remaining_original_gradient_function_entries':sorted(r.original_entries_when_replaced),
            'complete_gradient_port':False,
            'stage58_device_binary_changed':False,
            'device_execution_compared':False,
            'original_apk_or_private_dng_modified':False,
            'physical_camera_colour_equivalence_validated':False,
            'full_phocus_equivalence':False}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'status':record['status'],'total_exact_rgb16_channels':record['total_exact_rgb16_channels']}),flush=True)


if __name__=='__main__':main()
