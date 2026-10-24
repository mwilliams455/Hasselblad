#!/usr/bin/env python3
"""Execute original Bayer/highlight/Bayer bodies on synthetic, guarded images."""
import argparse
import hashlib
import itertools
import json
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'phocus_rawdomain_stage59'))
from audit_rawdomain59 import RawDomainRunner, load_private, y
from audit_highlight53 import Portable
from reference60 import fast_bayer, extract_bayer, pad_bayer
from unicorn.arm64_const import *

FAST_CTOR = '_ZN23CBayerFastInterpolationC1Ei7CXPointb'
FAST_CPU = '_ZNK23CBayerFastInterpolation12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'
MULTI_CTOR = '_ZN18CMulti2BayerFilterC1E7CXPointi'
MULTI_CPU = '_ZNK18CMulti2BayerFilter12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'
EXTRACT = '_ZN13CRawUtilities17ExtractBayerImageENSt6__ndk110unique_ptrI14CBufferedImageNS0_14default_deleteIS2_EEEEi7CXPoint'
BUFFER_CTOR = '_ZN14CBufferedImageC1EjjjjPtbj14EPixelDataType'
VIEW1 = '_ZN10CImageViewItLi1EEC2ER14CBufferedImage'
VIEW1_CONST = '_ZN10CImageViewIKtLi1EEC2ER14CBufferedImage'
DELETE_HOOK = 0x30006000
FILT, POINT, SR, DR, IP, OP = 0x100f8000, 0x100f9000, 0x100fa000, 0x100fb000, 0x100fd000, 0x100fd010
SRC, DST, VTABLE = 0x100fe000, 0x100fe100, 0x100ff000
SDATA, DDATA = 0x10200000, 0x10300000


class BayerRunner(RawDomainRunner):
    def __init__(self, elf, profile):
        y.ALLOWED.update({FAST_CTOR, FAST_CPU, MULTI_CTOR, MULTI_CPU, EXTRACT, VIEW1, VIEW1_CONST})
        self.bayer_fixture = False
        self.constructing_multi = False
        self.buffer_constructions = 0
        self.buffer_destructions = 0
        super().__init__(elf, profile)
        self.u.mem_write(VTABLE, b'\0'*24)
        self.put(VTABLE, 8, '<Q', DELETE_HOOK)

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0+i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        if self.constructing_multi and address == 0x30002008:
            # Keep the native caller's default value, unlike the unrelated
            # gradation fixture's zero-valued configuration service.
            self.multi_config.append(self.getstr(reg(1)))
            finish(); return
        if self.bayer_fixture and name == BUFFER_CTOR:
            width, height, channels = (reg(i) for i in (1, 2, 3))
            assert 0 < width <= 128 and 0 < height <= 128 and channels in (1, 3)
            data = self.alloc(width*height*channels*2)
            self.buffer(reg(0), data, (height, width, channels))
            self.buffer_constructions += 1
            finish(); return
        if self.bayer_fixture and address == DELETE_HOOK:
            # Only ownership is mocked; input/output data stay guarded.
            self.buffer_destructions += 1
            finish(); return
        if self.bayer_fixture and name.startswith('_ZN12CImageFilter15SetupForInplaceE'):
            src, dst = self.get(reg(2), 0, '<Q')[0], self.get(reg(3), 0, '<Q')[0]
            assert src and not dst
            self.put(reg(8), 0, '<Q', src)
            self.put(reg(2), 0, '<Q', 0); self.put(reg(3), 0, '<Q', 0)
            finish(); return
        return super().hook(cpu, address, size, user)

    def buffer(self, ptr, data, shape):
        h, w, ch = shape
        self.u.mem_write(ptr, b'\0'*56)
        self.put(ptr, 0, '<Q', VTABLE)
        self.put(ptr, 8, '<4i', w, h, ch, w*ch)
        self.put(ptr, 0x20, '<Q', data)

    def rect(self, ptr, coords):
        self.u.mem_write(ptr, b'\0'*32)
        self.put(ptr, 8, '<?', True)
        self.put(ptr, 12, '<4i', *coords)

    def fast(self, mosaic, halo=4):
        m = np.ascontiguousarray(mosaic, dtype='<u2')
        h, w = m.shape[0]-halo*2, m.shape[1]-halo*2
        assert min(h, w) > 0 and halo >= 1 and halo % 2 == 0
        assert m.nbytes < 900000 and h*w*6 < 900000
        self.u.mem_write(SDATA-16, b'\xa5'*16+m.tobytes()+b'\xa5'*16)
        self.u.mem_write(DDATA-16, b'\xa5'*16+b'\xcc'*(h*w*6)+b'\xa5'*16)
        self.buffer(SRC, SDATA, (*m.shape, 1)); self.buffer(DST, DDATA, (h, w, 3))
        self.call('_ZN7CXPointC1Eii', (POINT, 0, 0))
        self.u.mem_write(FILT-16, b'\xa5'*16+b'\0'*0x70+b'\xa5'*16)
        self.call(FAST_CTOR, (FILT, 1, POINT, 0))
        frozen = bytes(self.u.mem_read(FILT-16, 0x90))
        self.rect(SR, (-halo, -halo, w+halo, h+halo)); self.rect(DR, (0, 0, w, h))
        self.put(IP, 0, '<Q', SRC); self.put(OP, 0, '<Q', DST)
        self.bayer_fixture = True
        try:
            self.call(FAST_CPU, (FILT, SR, DR, IP, OP))
        finally:
            self.bayer_fixture = False
        assert self.get(0x10002000, 0, '<Q') == (DST,)
        assert self.get(OP, 0, '<Q') == (0,)
        assert frozen == bytes(self.u.mem_read(FILT-16, 0x90))
        assert bytes(self.u.mem_read(SDATA, m.nbytes)) == m.tobytes()
        for p, n in ((SDATA, m.nbytes), (DDATA, h*w*6)):
            assert bytes(self.u.mem_read(p-16, 16)) == bytes(self.u.mem_read(p+n, 16)) == b'\xa5'*16
        return np.frombuffer(bytes(self.u.mem_read(DDATA, h*w*6)), dtype='<u2').reshape(h, w, 3).copy()

    def remosaic(self, rgb, phase=(0, 0), origin=(0, 0)):
        rgb = np.ascontiguousarray(rgb, dtype='<u2')
        h, w, channels = rgb.shape
        assert channels == 3 and 0 < h <= 128 and 0 < w <= 128
        self.u.mem_write(SDATA-16, b'\xa5'*16+rgb.tobytes()+b'\xa5'*16)
        self.buffer(SRC, SDATA, rgb.shape)
        self.call('_ZN7CXPointC1Eii', (POINT, *phase))
        self.u.mem_write(FILT-16, b'\xa5'*16+b'\0'*0x70+b'\xa5'*16)
        self.constructing_multi = True; self.multi_config = []
        try:
            self.call(MULTI_CTOR, (FILT, POINT, 3))
        finally:
            self.constructing_multi = False
        assert self.get(FILT, 0x64, '<i') == (2,)
        assert len(self.multi_config) == 1
        frozen = bytes(self.u.mem_read(FILT-16, 0x90))
        ox, oy = origin
        self.rect(SR, (ox, oy, ox+w, oy+h)); self.rect(DR, (ox, oy, ox+w, oy+h))
        self.put(IP, 0, '<Q', SRC); self.put(OP, 0, '<Q', 0)
        self.bayer_fixture = True
        try:
            self.call(MULTI_CPU, (FILT, SR, DR, IP, OP))
        finally:
            self.bayer_fixture = False
        result = self.get(0x10002000, 0, '<Q')[0]
        assert self.get(result, 8, '<3i') == (w, h, 1)
        data = self.get(result, 0x20, '<Q')[0]
        assert frozen == bytes(self.u.mem_read(FILT-16, 0x90))
        assert bytes(self.u.mem_read(SDATA, rgb.nbytes)) == rgb.tobytes()
        assert bytes(self.u.mem_read(SDATA-16, 16)) == bytes(self.u.mem_read(SDATA+rgb.nbytes, 16)) == b'\xa5'*16
        return np.frombuffer(bytes(self.u.mem_read(data, h*w*2)), dtype='<u2').reshape(h, w).copy()


def main():
    p = argparse.ArgumentParser()
    for name in ('apk', 'safe-receipt', 'work'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    r = BayerRunner(*load_private(a.apk))
    rng = np.random.default_rng(60)
    cases = channels = roundtrip_sites = 0
    for h, w in ((6, 8), (7, 9), (24, 32)):
        yy, xx = np.indices((h, w))
        patterns = [np.zeros((h, w), '<u2'), np.full((h, w), 65535, '<u2'),
                    rng.integers(0, 65536, (h, w), dtype=np.uint16),
                    ((xx+yy*3)*217).astype('<u2'),
                    np.where(xx < w//2, 1000, 60000).astype('<u2')]
        for row, col in itertools.product(range(2), repeat=2):
            impulse = np.zeros((h, w), '<u2'); impulse[2+row, 2+col] = 65535
            patterns.append(impulse)
        for mosaic in patterns:
            padded = pad_bayer(mosaic)
            actual = r.fast(padded)
            expected = fast_bayer(padded)
            assert np.array_equal(actual, expected), (h, w, int(np.max(np.abs(actual.astype(int)-expected))))
            restored = r.remosaic(actual)
            assert np.array_equal(restored, mosaic)
            cases += 1; channels += actual.size; roundtrip_sites += mosaic.size
    print(json.dumps({'fast_cases': cases, 'exact_channels': channels, 'roundtrip_sites': roundtrip_sites}), flush=True)
    phase_cases = phase_sites = phase_matches = phase_mismatches = 0
    phase_patterns = []
    rgb = rng.integers(0, 65536, (9, 11, 3), dtype=np.uint16)
    for phase, origin in itertools.product(itertools.product(range(2), repeat=2), ((0, 0), (1, 0), (0, 1), (1, 1), (4, 6))):
        actual = r.remosaic(rgb, phase, origin)
        expected = extract_bayer(rgb, tuple((p+o)%2 for p, o in zip(phase, origin)))
        effective = tuple((p+o)%2 for p, o in zip(phase, origin))
        equal = np.array_equal(actual, expected)
        if effective[0] == 0:
            assert equal
        else:
            # These deliberately unverified horizontal alignments do not
            # implement an ordinary shifted CFA in this original RGB branch.
            # Retain the mismatch; do not redefine a correct CFA to hide it.
            assert not equal
        phase_matches += int(equal); phase_mismatches += int(not equal)
        phase_cases += 1; phase_sites += actual.size
    for phase in itertools.product(range(2), repeat=2):
        constant = np.broadcast_to(np.array([1000, 2000, 3000], '<u2'), (2, 2, 3)).copy()
        selected = r.remosaic(constant, phase)
        phase_patterns.append({'requested_phase': list(phase), 'selected_rgb_channels': (selected//1000-1).tolist()})
    portable = Portable(a.work)
    chain_cases = chain_channels = chain_sites = 0
    r.configure((1., 1.4, 1.8)); r.process()
    for black, gains in itertools.product((0, 512), itertools.permutations((.5, .7, 1.))):
        raw = rng.integers(0, 65536, (24, 32), dtype=np.uint16)
        # Native black subtraction is executed before native interpolation.
        corrected = r.black59(raw[..., None], black)[..., 0]
        independent_black = np.maximum(raw.astype(np.int32)-black, 0).astype('<u2')
        assert np.array_equal(corrected, independent_black)
        native_rgb = r.fast(pad_bayer(corrected))
        expected_rgb = fast_bayer(pad_bayer(independent_black))
        levels = (65535-black,)*3
        r.prepare(gains, levels)
        highlighted = r.cpu16(native_rgb.reshape(-1, 3)).reshape(native_rgb.shape)
        assert portable.prepare(gains, levels) == 0
        expected_highlight = portable.render(expected_rgb)
        assert np.array_equal(highlighted, expected_highlight)
        actual_bayer = r.remosaic(highlighted)
        expected_bayer = extract_bayer(expected_highlight)
        assert np.array_equal(actual_bayer, expected_bayer)
        chain_cases += 1; chain_channels += highlighted.size; chain_sites += actual_bayer.size
    r.check_guards()
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    result = {'schema': 'hasselblad-stage60-bayer-native-v1', 'status': 'PASS_BOUNDED_BAYER_CHAIN',
        'fast_interpolation': {'cases': cases, 'exact_rgb16_channels': channels,
            'step': 1, 'green_blending': False, 'cfa': 'RGGB with aligned destination origin',
            'max_absolute_difference': 0},
        'unmodified_rgb_bayer_roundtrip': {'exact_sites': roundtrip_sites, 'max_absolute_difference': 0},
        'remosaic_phase_probe': {'cases': phase_cases, 'sites_inspected': phase_sites,
            'ordinary_shifted_cfa_matching_cases': phase_matches,
            'ordinary_shifted_cfa_mismatching_cases': phase_mismatches,
            'constant_rgb_channel_patterns': phase_patterns,
            'native_alignment_scheduler_executed': False,
            'supported_port_domain': 'aligned RGGB only; odd horizontal phase is not generalized'},
        'black_fast_highlight_bayer_chain': {'cases': chain_cases, 'exact_highlight_channels': chain_channels,
            'exact_output_bayer_sites': chain_sites, 'max_absolute_difference': 0},
        'native_cpu_pixel_bodies_executed': ['black subtraction', 'fast Bayer interpolation', 'highlight reconstruction', 'Multi2Bayer wrapper', 'ExtractBayerImage RGB branch'],
        'buffer_allocation_and_ownership_mocked': True,
        'outer_edge_extension': 'explicit reflect-101 fixture, not native outer-frame policy',
        'final_native_demosaic_executed': False, 'native_gainmap_path_executed': False,
        'source_description_import_executed': False, 'source_apk_modified': False,
        'private_tables_exported': False, 'scene_fitted_parameters': 0,
        'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'chain_cases': chain_cases}), flush=True)


if __name__ == '__main__':
    main()
