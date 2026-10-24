#!/usr/bin/env python3
"""Exact original CPU checks for independent gradient row/direction kernels."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from audit_maps61 import MapRunner, load_private, PortableMaps, OBJ, BUFFERS, exact
from unicorn.arm64_const import UC_ARM64_REG_X0

ROWS = {
 'smooth': '_ZN13FilterGeneric20Smooth3x3_Special121EPKtPtii',
 'edge': '_ZN13FilterGeneric23Edge3x3_SpecialSobel121EPKtPsii',
 'median': '_ZN13FilterGeneric9Median3x3EPKsPsii'}
DIRECTIONS = '_Z21GetGradientSingleStepIsEvPKT_Psi'
MASK = '_ZN20CGradientInterpolate15GetGradientMaskEPKsS1_'


def guarded(a):
    a = np.ascontiguousarray(a)
    storage = np.full(a.nbytes+32, 0xa5, np.uint8)
    view = storage[16:-16].view(a.dtype).reshape(a.shape)
    view[...] = a
    return storage, view


def guard_ok(storage):
    assert np.all(storage[:16] == 0xa5) and np.all(storage[-16:] == 0xa5)


def native_fixture(r, name, source, output, offset=0, args=()):
    for ptr, a in zip(BUFFERS[:2], (source, output)):
        r.u.mem_write(ptr-16, b'\xa5'*16+a.tobytes()+b'\xa5'*16)
    r.call(name, (BUFFERS[0]+offset, BUFFERS[1], *args))
    assert bytes(r.u.mem_read(BUFFERS[0], source.nbytes)) == source.tobytes()
    for ptr, a in zip(BUFFERS[:2], (source, output)):
        assert bytes(r.u.mem_read(ptr-16, 16)) == bytes(r.u.mem_read(ptr+a.nbytes, 16)) == b'\xa5'*16
    return np.frombuffer(bytes(r.u.mem_read(BUFFERS[1], output.nbytes)), output.dtype).reshape(output.shape).copy()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--sanitize', action='store_true')
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    r = MapRunner(*load_private(a.apk)); c = PortableMaps(a.work, sanitize=a.sanitize)
    for name, scalar, vector in (('smooth', 0x50, 0x170), ('edge', 0x50, 0x144), ('median', 0x5c, 0x1dc)):
        entry = r.e.func[ROWS[name]][0]
        r.path_probes.update({entry+scalar: name+'_scalar_loop', entry+vector: name+'_vector_loop'})
    rng = np.random.default_rng(6102)
    row_cases = row_codes = direction_cases = direction_codes = mask_cases = 0
    for width in (2, 3, 9, 10, 17, 18, 19, 33, 258):
        stride = width+6
        yy, xx = np.indices((3, stride))
        fixtures = [np.zeros((3, stride), '<u2'), np.full((3, stride), 65535, '<u2'),
                    np.where((yy+xx)%2, 65535, 0).astype('<u2'),
                    ((xx*117+yy*233)%65536).astype('<u2'),
                    rng.integers(0, 65536, (3, stride), dtype=np.uint16)]
        for name, symbol in ROWS.items():
            dtype = '<u2' if name == 'smooth' else '<i2'
            for fixture in fixtures:
                raw = fixture.view('<i2') if name == 'median' else fixture
                out = np.full(stride, 12345, dtype)
                expected = native_fixture(r, symbol, raw, out, stride*2, (stride, width))
                gs, src = guarded(raw); go, actual = guarded(out)
                f = getattr(c.lib, 'hb_gradient_'+name+'_row61')
                assert f(src.ctypes.data+stride*2, actual.ctypes.data, stride, width) == 0
                exact(expected, actual, (name, width))
                exact(src, raw, 'portable row source unchanged')
                guard_ok(gs); guard_ok(go)
                row_cases += 1; row_codes += width
    # Distinguishes the original median-of-row-medians from a full 9-value median.
    witness = np.array([[0, 0, 9], [1, 2, 3], [8, 8, 8]], '<i2')
    median = native_fixture(r, ROWS['median'], witness, np.zeros(3, '<i2'), 6, (3, 3))
    portable_median = np.zeros(3, '<i2')
    assert c.lib.hb_gradient_median_row61(witness.ctypes.data+6, portable_median.ctypes.data, 3, 3) == 0
    exact(median, portable_median, 'median-of-row-medians witness')
    assert median[1] == 2 and int(np.median(witness)) == 3
    for stride in (5, 8, 17):
        yy, xx = np.indices((5, stride))
        fixtures = [np.zeros((5, stride), '<i2'), np.full((5, stride), -32768, '<i2'),
                    np.full((5, stride), 32767, '<i2'),
                    np.where((yy+xx)%2, 32767, -32768).astype('<i2')]
        fixtures += [rng.integers(-32768, 32768, (5, stride), dtype=np.int16) for _ in range(64)]
        for raw in fixtures:
            output = np.full(8, 12345, '<i2'); offset = (2*stride+2)*2
            expected = native_fixture(r, DIRECTIONS, raw, output, offset, (stride,))
            gs, src = guarded(raw); go, actual = guarded(output)
            assert c.lib.hb_gradient_directions61(src.ctypes.data+offset, stride, actual.ctypes.data) == 0
            exact(expected, actual, ('directions', stride))
            exact(raw, src, 'direction source unchanged'); guard_ok(gs); guard_ok(go)
            direction_cases += 1; direction_codes += 8
    masks = [(np.full(8, v, '<i2'), np.full(8, w, '<i2'))
             for v in (-32768, -1, 0, 49, 50, 51, 32767)
             for w in (-32768, -1, 0, 399, 400, 401, 32767)]
    masks += [(rng.integers(-32768, 32768, 8, dtype=np.int16),
               rng.integers(-32768, 32768, 8, dtype=np.int16)) for _ in range(512)]
    for floor_a, floor_b in ((50, 400), (32, 200), (100, 800)):
        for first, second in masks:
            data = np.concatenate((first, second))
            r.u.mem_write(BUFFERS[0]-16, b'\xa5'*16+data.tobytes()+b'\xa5'*16)
            r.u.mem_write(OBJ-16, b'\xa5'*16+b'\0'*0x100+b'\xa5'*16)
            r.put(OBJ, 0xe8, '<2h', floor_a, floor_b)
            frozen = bytes(r.u.mem_read(OBJ-16, 0x120))
            r.call(MASK, (OBJ, BUFFERS[0], BUFFERS[0]+16))
            expected = r.u.reg_read(UC_ARM64_REG_X0)
            actual = c.lib.hb_gradient_mask61(first.ctypes.data, second.ctypes.data, floor_a, floor_b)
            assert actual == expected, ('mask', floor_a, floor_b, first, second, expected, actual)
            assert bytes(r.u.mem_read(BUFFERS[0]-16, 64)) == b'\xa5'*16+data.tobytes()+b'\xa5'*16
            assert bytes(r.u.mem_read(OBJ-16, 0x120)) == frozen
            mask_cases += 1
    r.check_guards()
    row_paths = {k: v for k, v in r.path_hits.items() if k.split('_')[0] in ROWS}
    assert len(row_paths) == 6 and all(v > 0 for v in row_paths.values())
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    result = {'schema': 'hasselblad-stage61-gradient-kernels-v1', 'status': 'PASS_EXACT_KERNELS',
              'row_filter_cases': row_cases, 'exact_row_output_codes': row_codes,
              'direction_cases': direction_cases, 'exact_direction_codes': direction_codes,
              'exact_mask_cases': mask_cases, 'max_absolute_code_difference': 0,
              'median_row_medians_witness': {'native_and_portable': 2, 'full_nine_value_median': 3},
              'signed_extremes_and_narrowing_tested': True,
              'scalar_and_vector_widths_tested': True,
              'native_row_path_execution_blocks': row_paths,
              'source_and_memory_guards_pass': True,
              'undefined_behavior_sanitizer': a.sanitize,
              'complete_gradient_port': False, 'scene_fitted_parameters': 0,
              'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
