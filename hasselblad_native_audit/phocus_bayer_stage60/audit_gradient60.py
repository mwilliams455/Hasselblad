#!/usr/bin/env python3
"""Bounded original CPU gradient-demosaic execution, not an independent port."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from audit_bayer60 import (BayerRunner, load_private, y, FILT, POINT, SR, DR,
                           SRC, DST, IP, OP, SDATA, DDATA, pad_bayer, fast_bayer)
from audit_import52 import DEMOSAIC
from reference60 import extract_bayer
from unicorn.arm64_const import *

CPU = '_ZNK15CDemosaicFilter12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'
GG = '_Z17GGDirInterpolator10CImageViewItLi1EE7CXPoint6CXRectS_ItLi3EEdPKddsP11CTaskQueuesdd'


class GradientRunner(BayerRunner):
    def __init__(self, elf, profile):
        self.large_arena = False
        self.poison = 0xcc
        names = {n for n in elf.func if any(k in n for k in (
                    'CGradientInterpolate', 'CBaseInterpolate', 'FilterGeneric',
                    'GetGradientSingleStep', 'DirectionalColorCorrectionYCC',
                    'DirectionalSmooth', 'getYErrorMap', 'ColorFilter2',
                    'MaxMinClip2DFloat', 'C2DIIRFilter2Order_UShort', 'GetIIRFilter2LPCoef'))
                 and not n.startswith(('_ZTh', '_ZTv'))}
        names.update({CPU, GG, '_ZN6CXRect6OffsetEii', '_ZN6CXRect5InsetEii'})
        y.ALLOWED.update(names)
        self.gradient_entries = {elf.func[n][0]: n for n in names}
        self.gradient_active = False
        self.graph_demosaic_ptr = None
        self.graph_demosaic = None
        super().__init__(elf, profile)
        self.u.mem_map(0x40000000, 0x8000000)
        self.arena_next = 0x40000000
        self.large_arena = True

    def alloc(self, count):
        if not self.large_arena:
            return super().alloc(count)
        if self.pool.get(count):
            ptr = self.pool[count].pop()
            self.allocations.append((ptr, count))
            self.u.mem_write(ptr+16, bytes([self.poison])*count)
            self.reused_allocations += 1
            return ptr+16
        assert 0 <= count <= 64*1024*1024
        ptr = self.arena_next
        self.arena_next += (count+47)&~15
        assert self.arena_next < 0x48000000
        self.u.mem_write(ptr, b'\xa5'*16+bytes([self.poison])*count+b'\xa5'*16)
        self.allocations.append((ptr, count))
        return ptr+16

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0+i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        if self.raw_builder and name == DEMOSAIC:
            self.graph_demosaic_ptr = reg(0)
        if self.raw_builder and name.startswith('_ZN15CImageProcessor9AddFilterE') and self.graph_demosaic_ptr:
            self.graph_demosaic = bytes(self.u.mem_read(self.graph_demosaic_ptr, 0xa0))
        if self.gradient_active:
            if address == self.e.func[GG][0]+0x12e0:
                self.gradient_status.append(cpu.reg_read(UC_ARM64_REG_X19) & 0xffffffff)
            if address in self.gradient_entries:
                n = self.gradient_entries[address]; lo, length = self.e.func[n]
                if (lo, lo+length) not in self.active: self.active.append((lo, lo+length))
                self.called.add(n)
            if name in ('_Z17HasSupportForSIMDv', '_ZNSt6__ndk16chrono12steady_clock3nowEv'):
                cpu.reg_write(UC_ARM64_REG_X0, 0); finish(); return
            if name == '_Z9StrFormatIJPKcsEENSt6__ndk112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEES1_DpT_':
                # Formatting a disabled performance-log label occurs after
                # pixel work and cannot affect its result.
                self.putstr(reg(8), b''); finish(); return
        return super().hook(cpu, address, size, user)

    def setup_graph(self):
        self.configure((1., 1.4, 1.8)); self.process()
        self.graph59(512, 65535, (.5, .7, 1.), (1., 1., 1., 1.), 65535)
        assert self.graph_demosaic is not None

    def demosaic(self, padded, halo=32):
        m = np.ascontiguousarray(padded, dtype='<u2')
        h, w = m.shape[0]-halo*2, m.shape[1]-halo*2
        assert min(h, w) > 0 and halo >= 32 and halo % 2 == 0
        assert m.nbytes < 900000 and h*w*6 < 900000
        self.u.mem_write(SDATA-16, b'\xa5'*16+m.tobytes()+b'\xa5'*16)
        self.u.mem_write(DDATA-16, b'\xa5'*16+bytes([self.poison])*(h*w*6)+b'\xa5'*16)
        self.buffer(SRC, SDATA, (*m.shape, 1)); self.buffer(DST, DDATA, (h, w, 3))
        self.u.mem_write(FILT-16, b'\xa5'*16+self.graph_demosaic+b'\xa5'*16)
        frozen = bytes(self.u.mem_read(FILT-16, 0xc0))
        self.rect(SR, (-halo, -halo, w+halo, h+halo)); self.rect(DR, (0, 0, w, h))
        self.put(IP, 0, '<Q', SRC); self.put(OP, 0, '<Q', DST)
        self.gradient_status = []
        self.bayer_fixture = self.gradient_active = True
        try:
            self.call(CPU, (FILT, SR, DR, IP, OP))
        finally:
            self.bayer_fixture = self.gradient_active = False
        assert self.get(0x10002000, 0, '<Q') == (DST,)
        assert self.gradient_status == [0], self.gradient_status
        assert frozen == bytes(self.u.mem_read(FILT-16, 0xc0))
        assert bytes(self.u.mem_read(SDATA, m.nbytes)) == m.tobytes()
        for ptr, length in ((SDATA, m.nbytes), (DDATA, h*w*6)):
            assert bytes(self.u.mem_read(ptr-16, 16)) == bytes(self.u.mem_read(ptr+length, 16)) == b'\xa5'*16
        return np.frombuffer(bytes(self.u.mem_read(DDATA, h*w*6)), dtype='<u2').reshape(h, w, 3).copy()


def difference(a, b):
    d = np.abs(a.astype(np.int32)-b.astype(np.int32))
    return {'channels': int(d.size), 'max_absolute_rgb16_difference': int(d.max()),
            'mean_absolute_rgb16_difference': float(d.mean()),
            'changed_pixels': int(np.count_nonzero(np.any(d != 0, axis=-1)))}


def synthetic_patterns():
    yy, xx = np.indices((64, 64))
    neutral = np.full((64, 64), 10000, '<u2')
    flat_colour = extract_bayer(np.broadcast_to(np.array([8000, 12000, 20000], '<u2'), (64, 64, 3)))
    ramp = (4096+xx*256+yy*128).astype('<u2')
    rgb_edge = np.where((xx < 32)[..., None], [6000, 12000, 20000], [50000, 30000, 9000]).astype('<u2')
    impulse = neutral.copy(); impulse[32, 32] = 60000
    noise = np.random.default_rng(6001).integers(0, 65536, (64, 64), dtype=np.uint16)
    return [('neutral', neutral), ('flat_colour', flat_colour), ('ramp', ramp),
            ('colour_edge', extract_bayer(rgb_edge)), ('red_impulse', impulse), ('random_codes', noise)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    r = GradientRunner(*load_private(a.apk)); r.setup_graph()
    cases, chains = [], []
    for name, mosaic in synthetic_patterns():
        padded = pad_bayer(mosaic, 32)
        r.poison = 0xcc
        actual = r.demosaic(padded)
        r.poison = 0x33
        repeat = r.demosaic(padded)
        assert np.array_equal(actual, repeat), name
        if name == 'neutral':
            assert np.all(actual == 10000)
        diagnostic = fast_bayer(pad_bayer(mosaic))
        cases.append({'fixture': name, 'native_vs_bilinear': difference(actual, diagnostic),
                      'different_initial_memory_poison_exact': True})
        # The graph-captured demosaic parameters came from the same bounded
        # noise/lens-disabled setup. Use a fixed synthetic WB and source limit.
        corrected = r.black59(mosaic[..., None], 512)[..., 0]
        fast = r.fast(pad_bayer(corrected, 36))
        r.prepare((.5, .7, 1.), (65023,)*3)
        highlighted = r.cpu16(fast.reshape(-1, 3)).reshape(fast.shape)
        restored = r.remosaic(highlighted)
        after = r.demosaic(restored, 32)
        direct = highlighted[32:-32, 32:-32]
        bypass = r.demosaic(pad_bayer(corrected, 32))
        chains.append({'fixture': name, 'native_chain_vs_direct_highlight_rgb': difference(after, direct),
                       'native_chain_vs_native_gradient_highlight_bypass': difference(after, bypass)})
        print(json.dumps({'fixture': name, 'native_gradient_and_chain': 'PASS'}), flush=True)
    assert any(row['native_vs_bilinear']['max_absolute_rgb16_difference'] > 100 for row in cases)
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    r.check_guards()
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    result = {'schema': 'hasselblad-stage60-gradient-execution-v1', 'status': 'EXECUTED_BOUNDED_CPU',
              'synthetic_cases': cases, 'connected_pixel_chain_cases': chains,
              'unique_pixels_per_comparison': 6*64*64,
              'native_gradient_invocations': 24,
              'neutral_constant_10000_exact': True,
              'allocation_poison_repeat_cases': 6,
              'source_and_memory_guards_pass': True,
              'graph_captured_demosaic_parameters': True,
              'configuration_scope': 'fixed camera context; noise/lens-disabled graph fixture; unity demosaic gains',
              'cpu_dispatch': 'HasSupportForSIMD false fixture; original scalar class, compiler vector instructions still execute',
              'host_allocations_and_clock_and_disabled_log_label_mocked': True,
              'task_queue': 'null, synchronous original execution',
              'edge_extension': 'reflect-101 fixture with 32-pixel gradient halo',
              'gradient_executed_functions': sorted(r.called.intersection(r.gradient_entries.values())),
              'comparison_is_accuracy_score': False,
              'independent_gradient_port_compared': False,
              'native_gpu_compared': False, 'source_description_import_executed': False,
              'native_gainmap_path_executed': False,
              'physical_camera_colour_match_validated': False,
              'scene_fitted_parameters': 0, 'source_apk_modified': False,
              'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
