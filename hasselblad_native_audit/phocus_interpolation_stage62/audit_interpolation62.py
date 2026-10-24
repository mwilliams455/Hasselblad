#!/usr/bin/env python3
"""Direct original-CPU comparison; source images and executable stay private."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_gradient_stage61'))
from audit_maps61 import MapRunner, load_private, BUFFERS, exact
from audit_kernels61 import guarded, guard_ok
from portable62 import PortableInterpolation
from unicorn.arm64_const import UC_ARM64_REG_X0

BLUE = '_ZN20CGradientInterpolate12GetBlueAtRedEPKtS1_ii'
RED_BLUE = '_ZN20CGradientInterpolate17GetRedBlueAtGreenEPKtS1_S1_RtS2_ii'
NEW_PORT_NAMES = {BLUE: 'blue_at_red', RED_BLUE: 'red_blue_at_green'}


def fixture(r, c, planes, mask, kind, outputs=None, inputs=(0, 1, 2)):
    """Compare all storage, including aliased outputs and untouched padding."""
    arrays = [np.ascontiguousarray(x, dtype='<u2') for x in planes]
    stride = arrays[0].shape[1]
    center = stride+1
    arrays += [np.array([12345, 54321], '<u2')]
    for ptr, a in zip(BUFFERS, arrays):
        r.u.mem_write(ptr-16, b'\xa5'*16+a.tobytes()+b'\xa5'*16)
    portable_storage = [guarded(a) for a in arrays]
    views = [x[1] for x in portable_storage]
    nptrs = [BUFFERS[i]+center*2 for i in inputs]
    cptrs = [views[i].ctypes.data+center*2 for i in inputs]
    raw_result = None
    if kind == 'blue':
        r.call(BLUE, (*nptrs[:2], mask, stride))
        raw_result = r.u.reg_read(UC_ARM64_REG_X0) & 0xffffffff
        actual = c.lib.hb_blue_at_red62(*cptrs[:2], mask, stride)
        assert raw_result == actual & 0xffffffff, ('blue register', mask, raw_result, actual)
        assert raw_result & 0xffff == actual & 0xffff
        writable = set()
    else:
        outputs = outputs or ((3, 0), (3, 1))
        nout = [BUFFERS[i]+offset*2 for i, offset in outputs]
        cout = [views[i].ctypes.data+offset*2 for i, offset in outputs]
        r.call(RED_BLUE, (*nptrs, *nout, mask, stride))
        c.lib.hb_red_blue_at_green62(*cptrs, *cout, mask, stride)
        writable = set(outputs)
    for i, (ptr, original, (storage, actual)) in enumerate(zip(BUFFERS, arrays, portable_storage)):
        native = np.frombuffer(bytes(r.u.mem_read(ptr, original.nbytes)), '<u2').reshape(original.shape)
        exact(native, actual, (kind, 'whole buffer', i, mask, outputs, inputs))
        unchanged = np.ones(original.size, bool)
        for j, offset in writable:
            if i == j:
                unchanged[offset] = False
        assert np.array_equal(native.ravel()[unchanged], original.ravel()[unchanged])
        assert bytes(r.u.mem_read(ptr-16, 16)) == bytes(r.u.mem_read(ptr+original.nbytes, 16)) == b'\xa5'*16
        guard_ok(storage)
    return raw_result, [x.copy() for x in views]


def patterns(stride, rng):
    shape = (3, stride)
    def const(value): return np.full(shape, value, '<u2')
    cases = []
    for value in (0, 1, 3, 4, 25, 32767, 32768, 65533, 65534, 65535):
        cases.append(('constant_'+str(value), [const(value) for _ in range(3)]))
    cases.append(('flat_colour', [const(8000), const(12000), const(20000)]))
    yy, xx = np.indices(shape)
    cases.append(('edge', [np.where(xx < 1, lo, hi).astype('<u2')
                          for lo, hi in ((0,65535),(65535,0),(1,32768))]))
    for central_green in (0, 1, 32768, 65535):
        green = const(1); green[1, 1] = central_green
        cases.append(('ratio_boundary_'+str(central_green), [const(65535), green, const(32768)]))
    cases.append(('zero_denominator', [const(65535), const(0), const(12345)]))
    green = const(0); green[1, 1] = 60000; green[0, 0] = 1; green[0, 1] = 1
    cases.append(('partial_zero_denominators', [const(65535), green, const(12345)]))
    impulse = const(0); impulse[0, 0] = 65535; impulse[0, 1] = 65535
    cases.append(('impulse', [impulse, const(16384), const(60000)]))
    for i in range(8):
        cases.append(('random_'+str(i), [rng.integers(0, 65536, shape, dtype=np.uint16) for _ in range(3)]))
    return cases


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--compiler', default='gcc')
    p.add_argument('--sanitize', action='store_true')
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    r = MapRunner(*load_private(a.apk))
    c = PortableInterpolation(a.work, a.compiler, a.sanitize)
    rng = np.random.default_rng(6201)
    counts = Counter(); masks = set(); negative = 0
    for stride in (3, 8, 19):
        for name, planes in patterns(stride, rng):
            for mask in range(256):
                result, _ = fixture(r, c, planes, mask, 'blue')
                fixture(r, c, planes, mask, 'red_blue')
                counts['blue_cases'] += 1; counts['red_blue_cases'] += 1
                negative += result >= 0x80000000
                masks.add(mask)
        print(json.dumps({'stride': stride, 'all_256_low_masks': 'EXACT'}), flush=True)
    # Additional varied codes/masks, packed count and irrelevant high bits.
    for i in range(1024):
        stride = (3, 8, 19)[i % 3]
        planes = [rng.integers(0, 65536, (3, stride), dtype=np.uint16) for _ in range(3)]
        mask = int(rng.integers(0, 2**32, dtype=np.uint64))
        result, _ = fixture(r, c, planes, mask, 'blue')
        fixture(r, c, planes, mask, 'red_blue')
        counts['blue_cases'] += 1; counts['red_blue_cases'] += 1
        negative += result >= 0x80000000
    # Native caller aliases each output with its own plane centre. Also test
    # neighbour/green aliases, shared output addresses and shared input planes.
    layouts = [((0,9),(2,9)), ((0,1),(2,10)), ((1,9),(1,1)),
               ((3,0),(3,0)), ((0,9),(0,9))]
    input_layouts = [(0,1,2), (0,1,0), (0,0,2), (0,0,0)]
    for mask in (0, 1, 2, 4, 8, 16, 32, 64, 128, 0x55, 0xaa, 0xff, 0x800, 0x8ff, 0xffffffff):
        planes = [rng.integers(0, 65536, (3, 8), dtype=np.uint16) for _ in range(3)]
        for inputs in input_layouts:
            result, _ = fixture(r, c, planes, mask, 'blue', inputs=inputs)
            counts['blue_cases'] += 1
            for outputs in layouts:
                fixture(r, c, planes, mask, 'red_blue', outputs=outputs, inputs=inputs)
                counts['red_blue_cases'] += 1; counts['alias_cases'] += 1
    # Fixed synthetic counterexample: ordinary saturating arithmetic is wrong.
    green = np.ones((3,3), '<u2'); green[1,1] = 65535
    planes = [np.full((3,3), 65535, '<u2'), green, np.full((3,3), 65535, '<u2')]
    register, out = fixture(r, c, planes, 1, 'blue')
    _, rb = fixture(r, c, planes, 1, 'red_blue')
    assert register == 0xfffe0001 and register & 65535 == 1
    assert rb[3].tolist() == [1, 1]
    counts['blue_cases'] += 1; counts['red_blue_cases'] += 1
    # Positive individual ratios cross signed 32-bit range only when summed.
    green[1,1] = 32768
    register, _ = fixture(r, c, planes, 3, 'blue')
    _, rb = fixture(r, c, planes, 3, 'red_blue')
    assert register == 0xffff8000 and rb[3].tolist() == [32768,32768]
    counts['blue_cases'] += 1; counts['red_blue_cases'] += 1
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    r.check_guards()
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    assert len(masks) == 256 and negative > 0
    report = {'schema':'hasselblad-stage62-interpolation-helpers-v1', 'status':'PASS_EXACT_HELPERS',
              **dict(counts), 'exact_blue_register_results':counts['blue_cases'],
              'exact_output_codes':counts['blue_cases']+2*counts['red_blue_cases'],
              'low_direction_masks_covered':len(masks), 'strides_tested':[3,8,19],
              'negative_native_register_results_observed':negative,
              'single_ratio_wrap_witness':{'center_green':65535,'neighbour_green':1,
                 'neighbour_colour':65535,'mask':1,'signed_native_and_portable':-131071,
                 'stored_low16':1,'incorrect_saturating_result':65534},
              'sum_wrap_witness':{'center_green':32768,'neighbour_green':1,
                 'neighbour_colour':65535,'mask':3,'signed_native_and_portable':-32768,
                 'stored_low16':32768,'incorrect_saturating_result':65534},
              'all_storage_and_unchanged_inputs_compared':True,
              'native_and_portable_guards_pass':True, 'zero_denominator_and_no_direction_fallback_tested':True,
              'native_caller_alias_and_shared_output_write_order_tested':True,
              'compiler':a.compiler, 'undefined_behavior_sanitizer':a.sanitize,
              'max_absolute_output_difference':0,'complete_gradient_port':False,
              'source_apk_modified':False,'scene_fitted_parameters':0,
              'device_execution_compared':False,'capture_renderer_changed':False,'full_phocus_equivalence':False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
