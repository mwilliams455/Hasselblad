#!/usr/bin/env python3
"""Compare independent C gradient prepasses with original ARM64 CPU bodies."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_bayer_stage60'))
from audit_gradient60 import GradientRunner, load_private
from unicorn.arm64_const import UC_ARM64_REG_SP
from portable61 import PortableMaps

SCALE = '_ZN20CGradientInterpolate17CalculateScaleMapEPKtPfS2_iiiii'
GREEN = '_ZN20CGradientInterpolate20CalculateMidGreenMapEPKtPKfS3_PfPtiiiii'
OBJ = 0x50001000
BUFFERS = (0x50010000, 0x50210000, 0x50410000, 0x50610000, 0x50810000)


class MapRunner(GradientRunner):
    def __init__(self, *args):
        self.map_stack = None
        self.path_hits = Counter()
        self.path_probes = {}
        super().__init__(*args)
        self.u.mem_map(0x50000000, 0x1000000)
        self.path_probes = {self.e.func[GREEN][0]+0x5c4: 'green_scalar_loop',
                            self.e.func[GREEN][0]+0x840: 'green_vector_loop'}

    def hook(self, cpu, address, size, user):
        for target, label in self.path_probes.items():
            if address <= target < address+size:
                self.path_hits[label] += 1
        if self.map_stack is not None and address == self.map_stack[0]:
            cpu.mem_write(cpu.reg_read(UC_ARM64_REG_SP), self.map_stack[1])
            self.map_stack = None
        return super().hook(cpu, address, size, user)

    def original_maps(self, raw, horizontal, vertical, scale, green, bounds, threshold):
        arrays = (raw, horizontal, vertical, scale, green)
        for ptr, a in zip(BUFFERS, arrays):
            assert a.flags.c_contiguous and a.nbytes < 0x1f0000
            self.u.mem_write(ptr-16, b'\xa5'*16+a.tobytes()+b'\xa5'*16)
        self.u.mem_write(OBJ-16, b'\xa5'*16+b'\0'*0x100+b'\xa5'*16)
        self.put(OBJ, 0x30, '<d', threshold)
        frozen = bytes(self.u.mem_read(OBJ-16, 0x120))
        x0, y0, x1, y1 = bounds
        stride = raw.shape[1]
        self.map_stack = (self.e.func[SCALE][0], struct.pack('<q', y1))
        self.call(SCALE, (OBJ, *BUFFERS[:3], stride, x0, y0, x1))
        actual_h, actual_v = [np.frombuffer(bytes(self.u.mem_read(p, a.nbytes)), '<f4').reshape(a.shape).copy()
                              for p, a in zip(BUFFERS[1:3], arrays[1:3])]
        self.map_stack = (self.e.func[GREEN][0], struct.pack('<3q', y0, x1, y1))
        self.call(GREEN, (OBJ, *BUFFERS, stride, x0))
        outputs = [np.frombuffer(bytes(self.u.mem_read(p, a.nbytes)), a.dtype).reshape(a.shape).copy()
                   for p, a in zip(BUFFERS[3:], arrays[3:])]
        assert bytes(self.u.mem_read(BUFFERS[0], raw.nbytes)) == raw.tobytes()
        assert bytes(self.u.mem_read(OBJ-16, 0x120)) == frozen
        for ptr, a in zip(BUFFERS, arrays):
            assert bytes(self.u.mem_read(ptr-16, 16)) == bytes(self.u.mem_read(ptr+a.nbytes, 16)) == b'\xa5'*16
        return actual_h, actual_v, *outputs


def exact(a, b, label):
    assert a.shape == b.shape and a.dtype == b.dtype
    if a.tobytes() != b.tobytes():
        mismatch = a.view('u' + str(a.dtype.itemsize)) != b.view('u' + str(b.dtype.itemsize))
        loc = tuple(np.argwhere(mismatch)[0])
        raise AssertionError((label, loc, float(a[loc]), float(b[loc]),
                              int(np.count_nonzero(mismatch)), float(np.max(np.abs(a.astype(float)-b)))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--compiler', default='gcc')
    p.add_argument('--sanitize', action='store_true')
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    native = MapRunner(*load_private(a.apk))
    portable = PortableMaps(a.work, a.compiler, a.sanitize)
    rng = np.random.default_rng(6101)
    cases = cells = scale_values = green_values = compared_storage = 0
    contrast_witness = None
    # A single two-row cell band exercises the original vector loop. The
    # tested multi-band regions select its scalar loop; record both paths.
    for h, width, stride in ((16, 24, 32), (32, 256, 264), (20, 21, 24), (6, 256, 264)):
        yy, xx = np.indices((h, stride))
        patterns = [('zero', np.zeros((h, stride), '<u2')),
                    ('one', np.ones((h, stride), '<u2')),
                    ('threshold25', np.full((h, stride), 25, '<u2')),
                    ('threshold100', np.full((h, stride), 100, '<u2')),
                    ('full', np.full((h, stride), 65535, '<u2')),
                    ('ramp', ((xx*79+yy*173) % 65536).astype('<u2')),
                    ('random', rng.integers(0, 65536, (h, stride), dtype=np.uint16)),
                    ('low_codes', rng.integers(0, 102, (h, stride), dtype=np.uint16))]
        boundary = np.full((h, stride), 10, '<u2')
        boundary[2, 1:6] = [10, 10000, 10, 10000, 9]
        patterns.append(('contrast_double_threshold', boundary))
        bounds = (2, 2, ((width-2)//2)*2, h-2)
        ncell = ((bounds[2]-2+1)//2)*((bounds[3]-2+1)//2)
        for name, raw in patterns:
            for threshold in (1., 25., 100.):
                initial = [np.full((h, stride), 7.25, '<f4') for _ in range(3)]
                initial.append(np.full((h, stride), 12345, '<u2'))
                expected = native.original_maps(raw, *initial, bounds, threshold)
                guards, arrays = [], []
                for original in (raw, *initial):
                    storage = np.full(original.nbytes+32, 0xa5, np.uint8)
                    view = storage[16:-16].view(original.dtype).reshape(original.shape)
                    view[...] = original
                    guards.append(storage); arrays.append(view)
                portable_raw, *actual = arrays
                assert portable.scale(portable_raw, *actual[:2], bounds, threshold, width) == 0
                assert portable.green(portable_raw, *actual, bounds, width) == 0
                for label, original, independent in zip(('horizontal', 'vertical', 'scale', 'green'), expected, actual):
                    exact(original, independent, (h, width, stride, name, threshold, label))
                exact(raw, portable_raw, 'portable source unchanged')
                for storage in guards:
                    assert np.all(storage[:16] == 0xa5) and np.all(storage[-16:] == 0xa5)
                if name == 'contrast_double_threshold' and threshold == 1:
                    incorrectly_unweighted = np.float32(3)/(np.float32(1000)+np.float32(2)*np.float32(20000/21))
                    assert expected[0][2, 3] != incorrectly_unweighted
                    contrast_witness = {'five_samples': [10, 10000, 10, 10000, 9],
                                        'contrast_float32': float(np.float32(1)/np.float32(20)),
                                        'native_and_portable_scale': float(expected[0][2, 3]),
                                        'incorrect_float_threshold_scale': float(incorrectly_unweighted)}
                cases += 1; cells += ncell; scale_values += ncell*8; green_values += ncell*2
                compared_storage += h*stride*4
            print(json.dumps({'shape': [h, width, stride], 'fixture': name, 'exact_prepasses': True}), flush=True)
    for ptr, frozen in native.frozen_profile:
        assert bytes(native.u.mem_read(ptr, len(frozen))) == frozen
    native.check_guards()
    assert all(native.path_hits[name] > 0 for name in ('green_scalar_loop', 'green_vector_loop'))
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    result = {'schema': 'hasselblad-stage61-gradient-maps-v1', 'status': 'PASS_EXACT_PREPASSES',
              'compiler': a.compiler, 'undefined_behavior_sanitizer': a.sanitize,
              'cases': cases, 'cfa_cells': cells,
              'scale_ratio_and_contrast_slot_comparisons': scale_values,
              'green_scale_and_green_code_comparisons_each': green_values,
              'complete_output_storage_elements_compared_including_untouched': compared_storage,
              'max_absolute_float_difference': 0, 'max_absolute_green_code_difference': 0,
              'float_comparison': 'bit exact including untouched slots',
              'thresholds_synthetic': [1, 25, 100],
              'native_path_execution_blocks': dict(native.path_hits),
              'double_comparison_boundary_witness': contrast_witness,
              'row_padding_and_unwritten_slots_preserved': True,
              'source_and_memory_guards_pass': True,
              'complete_gradient_port': False, 'device_execution_compared': False,
              'scene_fitted_parameters': 0, 'source_apk_modified': False,
              'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
