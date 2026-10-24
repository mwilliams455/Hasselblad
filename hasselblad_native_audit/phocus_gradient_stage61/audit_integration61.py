#!/usr/bin/env python3
"""Substitute seven independent C kernels inside the bounded original demosaic.

The remaining native interpolation and colour/noise operations still execute.
Exact final RGB16 here establishes substitution parity, not a complete port.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from audit_maps61 import GradientRunner, load_private, PortableMaps, SCALE, GREEN, exact
from audit_kernels61 import ROWS, DIRECTIONS, MASK
from audit_gradient60 import synthetic_patterns, pad_bayer
from audit_saved60 import prepare as prepare_private_dng
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC

PORT_NAMES = {SCALE: 'scale_map', GREEN: 'initial_green', DIRECTIONS: 'directions', MASK: 'direction_mask',
              **{symbol: name+'_row' for name, symbol in ROWS.items()}}


class SubstitutionRunner(GradientRunner):
    def __init__(self, elf, profile, portable):
        self.portable = portable
        self.replace = False
        self.replacements = Counter()
        super().__init__(elf, profile)

    def array(self, ptr, shape, dtype):
        n = int(np.prod(shape)) * np.dtype(dtype).itemsize
        return np.frombuffer(bytes(self.u.mem_read(ptr, n)), dtype=dtype).reshape(shape).copy()

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        if not (self.gradient_active and self.replace and name in PORT_NAMES):
            return super().hook(cpu, address, size, user)
        reg = lambda i: cpu.reg_read(UC_ARM64_REG_X0+i)
        sint = lambda n: struct.unpack('<i', struct.pack('<I', n & 0xffffffff))[0]
        stack = cpu.reg_read(UC_ARM64_REG_SP)
        if name == SCALE:
            stride, x0, y0, x1 = [sint(reg(i)) for i in range(4, 8)]
            y1 = self.get(stack, 0, '<i')[0]
            shape = (y1+2, stride)
            raw = self.array(reg(1), shape, '<u2')
            horizontal, vertical = [self.array(reg(i), shape, '<f4') for i in (2, 3)]
            threshold = self.get(reg(0), 0x30, '<d')[0]
            assert self.portable.scale(raw, horizontal, vertical, (x0, y0, x1, y1), threshold) == 0
            for ptr, a in ((reg(2), horizontal), (reg(3), vertical)):
                cpu.mem_write(ptr, a.tobytes())
        elif name == GREEN:
            stride, x0 = sint(reg(6)), sint(reg(7))
            y0, x1, y1 = [self.get(stack, off, '<i')[0] for off in (0, 8, 16)]
            shape = (y1+2, stride)
            raw = self.array(reg(1), shape, '<u2')
            horizontal, vertical, scale = [self.array(reg(i), shape, '<f4') for i in (2, 3, 4)]
            green = self.array(reg(5), shape, '<u2')
            assert self.portable.green(raw, horizontal, vertical, scale, green, (x0, y0, x1, y1)) == 0
            cpu.mem_write(reg(4), scale.tobytes()); cpu.mem_write(reg(5), green.tobytes())
        elif name in ROWS.values():
            kind = next(k for k, v in ROWS.items() if v == name)
            stride, width = sint(reg(2)), sint(reg(3))
            assert 2 <= width <= stride <= 4096
            dtype = '<i2' if kind == 'median' else '<u2'
            raw = np.stack([self.array(reg(0)+dy*stride*2, (width,), dtype) for dy in (-1, 0, 1)])
            output = self.array(reg(1), (width,), '<u2' if kind == 'smooth' else '<i2')
            f = getattr(self.portable.lib, 'hb_gradient_'+kind+'_row61')
            assert f(raw.ctypes.data+width*2, output.ctypes.data, width, width) == 0
            cpu.mem_write(reg(1), output.tobytes())
        elif name == DIRECTIONS:
            stride = sint(reg(2))
            stencil = np.stack([self.array(reg(0)+(dy*stride-2)*2, (5,), '<i2') for dy in (-2, -1, 0, 1, 2)])
            output = np.zeros(8, '<i2')
            assert self.portable.lib.hb_gradient_directions61(stencil.ctypes.data+24, 5, output.ctypes.data) == 0
            cpu.mem_write(reg(1), output.tobytes())
        else:
            first, second = [self.array(reg(i), (8,), '<i2') for i in (1, 2)]
            floors = self.get(reg(0), 0xe8, '<2h')
            value = self.portable.lib.hb_gradient_mask61(first.ctypes.data, second.ctypes.data, *floors)
            cpu.reg_write(UC_ARM64_REG_X0, value)
        self.replacements[PORT_NAMES[name]] += 1
        cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))

    def compare(self, mosaic, label):
        self.replace = False
        native = self.demosaic(mosaic)
        self.replace = True
        independent = self.demosaic(mosaic)
        exact(native, independent, label)
        return {'fixture': label, 'pixels': int(native.shape[0]*native.shape[1]),
                'exact_rgb16_channels': int(native.size), 'max_absolute_difference': 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--dng', type=Path)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--sanitize', action='store_true')
    a = p.parse_args(); assert __debug__
    paths = [a.apk] + ([a.dng] if a.dng else [])
    before = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    c = PortableMaps(a.work, sanitize=a.sanitize)
    r = SubstitutionRunner(*load_private(a.apk), c); r.setup_graph()
    synthetic, saved = [], []
    for name, mosaic in synthetic_patterns():
        synthetic.append(r.compare(pad_bayer(mosaic, 32), name+'/highlight_bypass'))
        corrected = r.black59(mosaic[..., None], 512)[..., 0]
        fast = r.fast(pad_bayer(corrected, 36))
        r.prepare((.5, .7, 1.), (65023,)*3)
        highlighted = r.cpu16(fast.reshape(-1, 3)).reshape(fast.shape)
        synthetic.append(r.compare(r.remosaic(highlighted), name+'/highlight_bayer_chain'))
        print(json.dumps({'synthetic_fixture': name, 'substituted_final_rgb16': 'EXACT'}), flush=True)
    if a.dng:
        mosaic, gains, maps = prepare_private_dng(a.dng)
        assert np.sort(gains)[0] != np.sort(gains)[1]
        h, w = mosaic.shape
        for number, (gy, gx) in enumerate(((1, 1), (1, 3), (3, 1), (3, 3)), 1):
            top, left = (gy*h//4-16)//2*2, (gx*w//4-16)//2*2
            patch = mosaic[top-36:top+68, left-36:left+68]
            assert patch.shape == (104, 104)
            saved.append(r.compare(patch[4:-4, 4:-4], 'fixed_grid_'+str(number)+'/highlight_bypass'))
            fast = r.fast(patch); r.prepare(gains, (65535,)*3)
            highlighted = r.cpu16(fast.reshape(-1, 3)).reshape(fast.shape)
            saved.append(r.compare(r.remosaic(highlighted), 'fixed_grid_'+str(number)+'/highlight_bayer_chain'))
            print(json.dumps({'fixed_grid_tile': number, 'substituted_final_rgb16': 'EXACT'}), flush=True)
    r.check_guards()
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    assert all(r.replacements[name] > 0 for name in PORT_NAMES.values())
    assert before == [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    report = {'schema': 'hasselblad-stage61-gradient-substitution-v1', 'status': 'PASS_EXACT_SUBSTITUTED_RGB16',
              'synthetic_comparisons': synthetic, 'private_dng_comparisons': saved,
              'synthetic_exact_channels': sum(x['exact_rgb16_channels'] for x in synthetic),
              'private_dng_exact_channels': sum(x['exact_rgb16_channels'] for x in saved),
              'portable_kernel_count': len(PORT_NAMES), 'portable_kernel_calls': dict(r.replacements),
              'native_functions_replaced_in_harness': sorted(PORT_NAMES.values()),
              'remaining_native_gradient_and_colour_operations_still_execute': True,
              'complete_gradient_port': False, 'undefined_behavior_sanitizer': a.sanitize,
              'configuration_scope': 'Stage60 graph-captured fixed camera context; noise/lens-disabled fixture; unity demosaic gains',
              'boundary_scope': 'Stage60 reflect-101 synthetic halo; interior private-DNG tiles; original full-frame policy not reproduced',
              'dng_input_domain': 'Stage58 common range and gain-map clamps, quantized to Bayer before interpolation; not device RGB16 buffer' if a.dng else None,
              'source_and_memory_guards_pass': True,
              'source_apk_modified': False, 'source_dng_modified': False,
              'scene_fitted_parameters': 0, 'device_execution_compared': False,
              'physical_camera_colour_match_validated': False,
              'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
