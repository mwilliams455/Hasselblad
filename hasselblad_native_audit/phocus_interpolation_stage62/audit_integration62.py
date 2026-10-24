#!/usr/bin/env python3
"""Substitute nine independent components; remaining native pixel work stays explicit."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_gradient_stage61'))
from audit_integration61 import (SubstitutionRunner, PORT_NAMES, load_private,
    PortableMaps, synthetic_patterns, pad_bayer, prepare_private_dng, exact)
from audit_interpolation62 import BLUE, RED_BLUE, NEW_PORT_NAMES
from portable62 import PortableInterpolation
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC

ALL_PORT_NAMES = {**PORT_NAMES, **NEW_PORT_NAMES}


class InterpolationRunner(SubstitutionRunner):
    def __init__(self, elf, profile, maps, interpolation):
        self.interpolation = interpolation
        self.original_entries_when_replaced = set()
        self.alias_calls = 0
        self.original_invocations = self.substituted_invocations = 0
        super().__init__(elf, profile, maps)

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        if self.gradient_active and self.replace and address in self.gradient_entries:
            self.original_entries_when_replaced.add(self.gradient_entries[address])
        if not (self.gradient_active and self.replace and name in NEW_PORT_NAMES):
            return super().hook(cpu, address, size, user)
        reg = lambda i: cpu.reg_read(UC_ARM64_REG_X0+i)
        stride = struct.unpack('<i', struct.pack('<I', reg(3 if name == BLUE else 6) & 0xffffffff))[0]
        assert 3 <= stride <= 4096
        # Snapshot every required input before writing aliased plane outputs.
        stencils = [np.stack([self.array(reg(i)+(dy*stride-1)*2, (3,), '<u2')
                              for dy in (-1,0,1)])
                    for i in range(2 if name == BLUE else 3)]
        ptrs = [a.ctypes.data+8 for a in stencils]
        if name == BLUE:
            value = self.interpolation.lib.hb_blue_at_red62(*ptrs, reg(2)&0xffffffff, 3)
            cpu.reg_write(UC_ARM64_REG_X0, value & 0xffffffff)
        else:
            out = np.zeros(2, '<u2')
            self.interpolation.lib.hb_red_blue_at_green62(*ptrs, out.ctypes.data,
                                        out.ctypes.data+2, reg(5)&0xffffffff, 3)
            if reg(3) == reg(0) and reg(4) == reg(2):
                self.alias_calls += 1
            cpu.mem_write(reg(4), out[1:].tobytes())
            cpu.mem_write(reg(3), out[:1].tobytes())
        self.replacements[NEW_PORT_NAMES[name]] += 1
        cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))

    def compare(self, mosaic, label):
        self.replace = False
        native = self.demosaic(mosaic); self.original_invocations += 1
        self.replace = True
        independent = self.demosaic(mosaic); self.substituted_invocations += 1
        exact(native, independent, label)
        return {'fixture':label, 'pixels':int(native.shape[0]*native.shape[1]),
                'exact_rgb16_channels':int(native.size), 'max_absolute_difference':0}


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
    r = InterpolationRunner(*load_private(a.apk), maps, interpolation); r.setup_graph()
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
        print(json.dumps({'synthetic_fixture':name,'nine_component_substitution':'EXACT'}),flush=True)
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
                print(json.dumps({'private_tile':prefix,'nine_component_substitution':'EXACT'}),flush=True)
    r.check_guards()
    for ptr,frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(frozen))) == frozen
    assert all(r.replacements[name] > 0 for name in ALL_PORT_NAMES.values())
    assert not r.original_entries_when_replaced.intersection(ALL_PORT_NAMES)
    assert r.alias_calls == r.replacements['red_blue_at_green']
    assert before == [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    report = {'schema':'hasselblad-stage62-interpolation-substitution-v1',
              'status':'PASS_EXACT_NINE_COMPONENT_SUBSTITUTION',
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
