#!/usr/bin/env python3
"""Ten-component substitution, including independent green estimation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_interpolation_stage62'))
from audit_integration62 import (InterpolationRunner, ALL_PORT_NAMES as PREVIOUS_PORT_NAMES,
    load_private, PortableMaps, PortableInterpolation, synthetic_patterns, pad_bayer, prepare_private_dng)
from audit_green63 import GREEN_FIRST
from portable63 import PortableGreen
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC, UC_ARM64_REG_SP

ALL_PORT_NAMES={**PREVIOUS_PORT_NAMES,GREEN_FIRST:'green_at_colour'}


class GreenRunner(InterpolationRunner):
    def __init__(self,elf,profile,maps,interpolation,green):
        self.green=green
        super().__init__(elf,profile,maps,interpolation)

    def hook(self,cpu,address,size,user):
        name=self.e.plt.get(address,'')
        if not (self.gradient_active and self.replace and name==GREEN_FIRST):
            return super().hook(cpu,address,size,user)
        reg=lambda i:cpu.reg_read(UC_ARM64_REG_X0+i)
        stride=struct.unpack('<i',struct.pack('<I',reg(6)&0xffffffff))[0]
        assert 5<=stride<=4096
        stack=cpu.reg_read(UC_ARM64_REG_SP)
        out_mask,first_ptr,second_ptr,out_max=self.get(stack,0,'<4Q')
        destinations=[(reg(7),4),(out_mask,4),(out_max,2)]
        assert all(p+n<=q or q+m<=p for i,(p,n) in enumerate(destinations)
                   for q,m in destinations[i+1:])
        raw=np.stack([self.array(reg(1)+(dy*stride-2)*2,(5,),'<u2') for dy in (-2,-1,0,1,2)])
        maps=[np.stack([self.array(reg(i)+(dy*stride-2)*4,(5,),'<f4') for dy in (-2,-1,0,1,2)])
              for i in (2,3,4)]
        # Only these sites belong to this helper's scale-map contract; other
        # cells may be untouched map storage and are not consumed by the C code.
        sampled=np.concatenate((maps[0][2,[1,3]],maps[1][[1,3],2],
            maps[2][[0,0,1,1,2,3,3,4,4],[0,4,1,3,2,1,3,0,4]]))
        assert np.isfinite(sampled).all() and (sampled>=0).all()
        first=self.array(first_ptr,(8,),'<i2'); second=self.array(second_ptr,(8,),'<i2')
        floors=self.get(reg(0),0xe8,'<2h')
        out=[np.zeros(1,'<i4'),np.zeros(1,'<i4'),np.zeros(1,'<i2')]
        self.green.lib.hb_green_at_colour63(raw.ctypes.data+24,*[x.ctypes.data+48 for x in maps],
            5,first.ctypes.data,second.ctypes.data,*floors,*[x.ctypes.data for x in out])
        cpu.mem_write(out_max,out[2].tobytes())
        cpu.mem_write(reg(7),out[0].tobytes()); cpu.mem_write(out_mask,out[1].tobytes())
        self.replacements['green_at_colour']+=1
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--dng', type=Path)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--sanitize', action='store_true')
    a = p.parse_args(); assert __debug__
    paths = [a.apk]+([a.dng] if a.dng else [])
    before = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    maps = PortableMaps(a.work / 'maps', sanitize=a.sanitize)
    interpolation = PortableInterpolation(a.work / 'interpolation', sanitize=a.sanitize)
    green = PortableGreen(a.work / 'green', sanitize=a.sanitize)
    r = GreenRunner(*load_private(a.apk), maps, interpolation, green); r.setup_graph()
    synthetic, saved, held_out = [], [], []
    patterns = synthetic_patterns()
    rng = np.random.default_rng(6202)
    patterns += [('rectangle_16x24',rng.integers(0,65536,(16,24),dtype=np.uint16)),
                 ('rectangle_18x34',rng.integers(0,65536,(18,34),dtype=np.uint16))]
    for name, mosaic in patterns:
        synthetic.append(r.compare(pad_bayer(mosaic,32), name+'/highlight_bypass'))
        corrected = r.black59(mosaic[...,None],512)[...,0]
        fast = r.fast(pad_bayer(corrected,36)); r.prepare((.5,.7,1.),(65023,)*3)
        highlighted = r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
        synthetic.append(r.compare(r.remosaic(highlighted),name+'/highlight_bayer_chain'))
        print(json.dumps({'synthetic_fixture':name,'ten_component_substitution':'EXACT'}),flush=True)
    if a.dng:
        mosaic, gains, _ = prepare_private_dng(a.dng)
        assert np.sort(gains)[0] != np.sort(gains)[1]
        h,w = mosaic.shape
        selections = [(saved, 'fixed_grid',32,32,((1,1),(1,3),(3,1),(3,3))),
                      (held_out, 'held_out_grid',16,24,((1,2),(2,1),(2,3),(3,2)))]
        for destination,label,th,tw,grid in selections:
            for number,(gy,gx) in enumerate(grid,1):
                top,left = (gy*h//4-th//2)//2*2,(gx*w//4-tw//2)//2*2
                patch = mosaic[top-36:top+th+36,left-36:left+tw+36]
                assert patch.shape == (th+72,tw+72)
                prefix = label+'_'+str(number)
                destination.append(r.compare(patch[4:-4,4:-4],prefix+'/highlight_bypass'))
                fast = r.fast(patch); r.prepare(gains,(65535,)*3)
                highlighted = r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
                destination.append(r.compare(r.remosaic(highlighted),prefix+'/highlight_bayer_chain'))
                print(json.dumps({'private_tile':prefix,'ten_component_substitution':'EXACT'}),flush=True)
    r.check_guards()
    for ptr,frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(frozen))) == frozen
    assert all(r.replacements[name] > 0 for name in ALL_PORT_NAMES.values())
    assert not r.original_entries_when_replaced.intersection(ALL_PORT_NAMES)
    assert r.alias_calls == r.replacements['red_blue_at_green']
    assert before == [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    report = {'schema':'hasselblad-stage63-green-substitution-v1',
              'status':'PASS_EXACT_TEN_COMPONENT_SUBSTITUTION',
              'synthetic_comparisons':synthetic,'private_dng_comparisons':saved,
              'held_out_private_dng_comparisons':held_out,
              'synthetic_exact_channels':sum(x['exact_rgb16_channels'] for x in synthetic),
              'private_dng_exact_channels':sum(x['exact_rgb16_channels'] for x in saved),
              'held_out_private_dng_exact_channels':sum(x['exact_rgb16_channels'] for x in held_out),
              'native_original_invocations':r.original_invocations,
              'native_substituted_invocations':r.substituted_invocations,
              'portable_kernel_count':len(ALL_PORT_NAMES),'portable_kernel_calls':dict(r.replacements),
              'native_plane_centre_alias_calls':r.alias_calls,
              'original_replaced_function_bodies_executed':False,
              'remaining_original_gradient_function_entries':sorted(r.original_entries_when_replaced),
              'remaining_native_gradient_and_colour_operations_still_execute':True,
              'complete_gradient_port':False,'undefined_behavior_sanitizer':a.sanitize,
              'configuration_scope':'Stage60 graph-captured fixed camera context; noise/lens-disabled fixture; unity demosaic gains',
              'boundary_scope':'reflect-101 synthetic halo; interior private-DNG tiles; original full-frame edge policy unresolved',
              'dng_input_domain':'Stage58 common range and gain-map clamps, quantized before interpolation; not device RGB16 buffer' if a.dng else None,
              'source_and_memory_guards_pass':True,'source_apk_modified':False,'source_dng_modified':False,
              'scene_fitted_parameters':0,'device_execution_compared':False,
              'physical_camera_colour_match_validated':False,'capture_renderer_changed':False,
              'full_phocus_equivalence':False}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'], 'total_exact_rgb16_channels':
        sum(x['exact_rgb16_channels'] for x in synthetic+saved+held_out)}),flush=True)


if __name__ == '__main__':
    main()
