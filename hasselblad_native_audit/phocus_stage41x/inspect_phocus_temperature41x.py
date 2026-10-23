#!/usr/bin/env python3
"""Execute private Phocus temperature/LUT/setup code; export aggregate evidence only.

Requires the hash-pinned, separately supplied APK and sibling Stage41W audit.
No native code, calibration arrays, image data or cryptographic tables are saved.
Run without -O: assertions are verification gates.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'phocus_stage41w'))
from inspect_phocus_profiles41w import (
    Elf, Native, APK_SHA, LIB_SHA, TARGET, DECODE, decrypt_blocks, sha,
)
import argparse
import collections
import io
import json
import plistlib
import struct
import zipfile
from importlib.metadata import version
import numpy as np
from unicorn.arm64_const import *

MATRIX = '_ZNK7CXMLLut15CalculateMatrixEPdi'
LUT = '_ZNK7CXMLLut12CalculateLUTEib'
EXPANDED = '_ZN7CXMLLut20CalculateExpandedLUTE6CArrayIiLi2EiES1_ib'
SETUP = '_ZN16CColorCorrection7SetupCCE9Matrix3x3S0_P7CXMLLutibNSt6__ndk14spanIKfLm18446744073709551615EEEPttddbb'
PIXELS = '_ZN14CVectorMethods24ColorNormalCorrectPixelsEP16CColorCorrectionPtS2_ib'
ALLOWED = {
    DECODE, MATRIX, LUT, EXPANDED, SETUP, PIXELS,
    '_ZN7CXMLLut14InitializeLUTsEbii',
    '_ZN11Scaled2DLUT12FromCbCrDataEP5sCbCriiiii',
    '_ZN12CUniqueImageIdLi2ENSt6__ndk110unique_ptrIA_d14AlignedDeleterIdEEEEC2Eiii',
    '_ZN9CGenImageC1Eiii12EelementType14EinitialActionPvi',
    '_ZN9CGenImageD1Ev', '_ZN11CStreamableC2Ev', '_ZN11CStreamableD2Ev',
    '_ZN6CXRectC1Eiiii', '_ZN6CXRectD1Ev', '_ZN9Matrix3x34CopyES_',
    '_ZNK9Matrix3x3ixEi',
    '_ZNK9Matrix3x3mlE6CArrayIdLi3E23Matrix3x1InitializationE',
    '_ZNK11Scaled2DLUT6LookupE6CArrayIdLi2EdEb',
    '_ZNK11Scaled2DLUT11LookupIndexE6CArrayIdLi2EdEb',
    '_ZNK16CColorCorrection19CalculateGrayWeightEddb',
}
# Fixed before the audit: arithmetic-order tolerance, not bit-exact equivalence.
DOUBLE_TOLERANCE = 1e-12
PIXEL_TOLERANCE = 1
TEMPERATURES = [-100, 1999, 2000, 2001, 2399, 2400, 2401, 3049, 3050,
                3051, 4000, 5549, 5550, 5551, 7000, 9099, 9100, 9101,
                9999, 10000, 10001, 15000]


class Runner(Native):
    """Original arithmetic; bounded host allocation/string/config/XML fixtures."""
    def __init__(self, elf):
        super().__init__(elf)
        self.host_calls = collections.Counter()
        # Resolve defined ELF data/vtable relocations. No external native loading.
        for row in elf.rels:
            typ = int(row['info']) & 0xffffffff
            idx = int(row['info']) >> 32
            if typ in (257, 1025, 1027) and (typ == 1027 or elf.sym[idx]['sh'] != 0):
                ptr = int(row['addend']) + (int(elf.sym[idx]['addr']) if typ != 1027 else 0)
                self.u.mem_write(int(row['offset']), struct.pack('<Q', ptr))
        self.u.mem_write(0x37c49e8, struct.pack('<Q', 0x10005000))

    def hook(self, cpu, address, size, user):
        if address in self.e.plt:
            name = self.e.plt[address]
            if name in ALLOWED:
                start, length = self.e.func[name]
                if (start, start + length) not in self.active:
                    self.active.append((start, start + length))
                self.called.add(name)
                cpu.reg_write(UC_ARM64_REG_PC, start)
                return
            self.host_calls[name] += 1
            if name in ('calloc', 'malloc', 'free'):
                if name != 'free':
                    count = cpu.reg_read(UC_ARM64_REG_X0)
                    if name == 'calloc':
                        count *= cpu.reg_read(UC_ARM64_REG_X1)
                    assert 0 < count < 0x1000000
                    ptr = self.alloc(count)
                    # calloc requires zero; deterministic malloc is an explicit fixture.
                    cpu.mem_write(ptr, b'\0' * count)
                    cpu.reg_write(UC_ARM64_REG_X0, ptr)
                cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
                return
        super().hook(cpu, address, size, user)

    def call(self, name, args=(), floats=(), ret=0x10002000, stack=b''):
        assert name in ALLOWED
        start, length = self.e.func[name]
        self.active = [(start, start + length)]
        self.called.add(name)
        self.u.mem_write(ret, b'\0' * 80)
        self.u.reg_write(UC_ARM64_REG_X8, ret)
        for i in range(8):
            value = args[i] if i < len(args) else 0
            self.u.reg_write(UC_ARM64_REG_X0 + i, value & 0xffffffffffffffff)
            value = floats[i] if i < len(floats) else 0.
            self.u.reg_write(UC_ARM64_REG_D0 + i, struct.unpack('<Q', struct.pack('<d', value))[0])
        self.u.mem_write(0x200ff000, stack + b'\0' * 64)
        self.u.reg_write(UC_ARM64_REG_SP, 0x200ff000)
        self.u.reg_write(UC_ARM64_REG_X30, 0x30000000)
        self.u.emu_start(start, 0x30000000, count=5000000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == 0x30000000, 'Instruction budget exhausted'
        self.check_guards()

    def check_guards(self):
        for ptr, length in self.allocations:
            assert bytes(self.u.mem_read(ptr, 16)) == b'\xa5' * 16
            assert bytes(self.u.mem_read(ptr + 16 + length, 16)) == b'\xa5' * 16
        for ptr, length in ((self.obj, 0x318), (0x10010000, 0x298)):
            assert bytes(self.u.mem_read(ptr - 16, 16)) == b'\xa5' * 16
            assert bytes(self.u.mem_read(ptr + length, 16)) == b'\xa5' * 16

    def checkpoint(self):
        self.saved_heap = self.heap
        self.saved_allocs = len(self.allocations)

    def discard_case(self):
        self.check_guards()
        self.u.mem_write(self.saved_heap, b'\0' * (self.heap - self.saved_heap))
        self.heap = self.saved_heap
        del self.allocations[self.saved_allocs:]
        self.u.mem_write(0x10010000, b'\0' * 0x298)

    def table(self, ptr=0x10002000):
        owner, data, w, h, stride, channels = struct.unpack('<QQiiii', bytes(self.u.mem_read(ptr, 32)))
        assert owner == data and channels == 2 and stride == 2 * w
        assert (w, h) in ((105, 89), (165, 108))
        scale = struct.unpack('<5d', bytes(self.u.mem_read(ptr + 32, 40)))
        expected = (20., 32., 32., 32., 32.) if w == 105 else (25., 39., 32., 32., 32.)
        assert scale == expected
        values = np.frombuffer(bytes(self.u.mem_read(data, h * stride * 8)), dtype='<f8').reshape(h, w, 2)
        return values.copy(), scale


def interpolate(low, high, t0, t1, temperature):
    # Independent mathematical expression, deliberately not native FMA ordering.
    return low + (high - low) * ((temperature - t0) / (t1 - t0))


def matrix_oracle(profile, temperature):
    t = np.clip(temperature, 2000, 10000)
    if t < profile['tt']:
        a, b, t0, t1 = 'mlt', 'mt', profile['tlt'], profile['tt']
    elif t < profile['tf']:
        a, b, t0, t1 = 'mt', 'mf', profile['tt'], profile['tf']
    else:
        a, b, t0, t1 = 'mf', 'mh', profile['tf'], profile['th']
    return interpolate(np.array(profile[a]) * .5 + 1, np.array(profile[b]) * .5 + 1, t0, t1, t)


def lut_oracle(profile, temperature, repro):
    t = np.clip(temperature, 2000, 10000)
    suffix = 'Repro' if repro else 'Std'
    if t < profile['tf']:
        a, b, t0, t1 = 'TS', 'Flash', profile['tt'], profile['tf']
    else:
        a, b, t0, t1 = 'Flash', 'HT', profile['tf'], profile['th']
    a = np.array(profile['LUTTable' + a + suffix])
    b = np.array(profile['LUTTable' + b + suffix])
    return interpolate(a, b, t0, t1, t).reshape(89, 105, 2)


def expand_oracle(grid):
    yy, xx = np.indices((108, 165))
    cx, cy = np.clip(xx - 5, 0, 104), np.clip(yy - 7, 0, 88)
    return grid[cy, cx] + np.stack([xx - 5 - cx, yy - 7 - cy], axis=-1)


def compare(actual, expected):
    assert actual.shape == expected.shape and np.isfinite(actual).all()
    delta = np.abs(actual - expected)
    maximum = float(delta.max())
    assert maximum <= DOUBLE_TOLERANCE, maximum
    return {'values': actual.size, 'exact_values': int(np.count_nonzero(delta == 0)),
            'max_abs_difference': maximum}


def pixel_oracle(pixels, matrix, inverse, grid, scale, protection):
    bx, by, sx, sy, divisor = scale
    height, width, _ = grid.shape
    output = []
    for rgb in pixels.astype(float):
        yy, cb, cr = matrix @ rgb
        if yy <= 0:
            output.append([0, 0, 0])
            continue
        x, y = np.clip([cb / yy * sx + bx, cr / yy * sy + by], [0, 0], [width - 1, height - 1])
        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, width - 1), min(y0 + 1, height - 1)
        dx, dy = x - x0, y - y0
        chroma = ((grid[y0, x0] * (1 - dx) + grid[y0, x1] * dx) * (1 - dy)
                  + (grid[y1, x0] * (1 - dx) + grid[y1, x1] * dx) * dy) / divisor
        if protection:
            ratio = np.max(np.abs(rgb - rgb.mean())) / rgb.mean()
            weight = (ratio - .1) / .3 if ratio < .4 else 1.
            weight = max(0., min(weight, 1. if yy > 16384. else yy / 32768. + .25))
        else:
            weight = 1.
        converted = inverse @ np.array([yy, chroma[0] * yy * weight, chroma[1] * yy * weight])
        output.append(np.clip(converted, 0, 65535).astype(np.uint16))
    return np.asarray(output, dtype='<u2')


def audit(elf, profile):
    runner = Runner(elf)
    runner.profile = profile
    for ptr, length in ((runner.obj, 0x318), (0x10010000, 0x298)):
        runner.u.mem_write(ptr - 16, b'\xa5' * 16)
        runner.u.mem_write(ptr + length, b'\xa5' * 16)
    runner.call(DECODE, (runner.obj, runner.coder))
    # Stage41W constructor trace: this byte is 1 for normal CPID 0x0616.
    # Full CXMLLut and CColorCorrection constructors are not run in this harness.
    runner.u.mem_write(runner.obj + 9, b'\1')
    runner.checkpoint()
    frozen = [(runner.obj, bytes(runner.u.mem_read(runner.obj, 0x318)))]
    frozen += [(p + 16, bytes(runner.u.mem_read(p + 16, n))) for p, n in runner.allocations]
    matrices, tables, expanded, config_checks, pixel_cases = [], [], [], [], []
    for temperature in TEMPERATURES:
        runner.call(MATRIX, (runner.obj, 0x10003000, temperature))
        actual = np.frombuffer(bytes(runner.u.mem_read(0x10003000, 72)), dtype='<f8')
        matrices.append({'temperature': temperature, **compare(actual, matrix_oracle(profile, temperature))})
        runner.discard_case()
        for repro in (False, True):
            runner.call(LUT, (runner.obj, temperature, int(repro)))
            actual, _ = runner.table()
            tables.append({'temperature': temperature, 'repro': repro,
                           **compare(actual, lut_oracle(profile, temperature, repro))})
            runner.discard_case()
    print('Matrix and LUT temperature boundaries passed', flush=True)
    for temperature in (2000, 2400, 3050, 4000, 5550, 9100, 10000):
        for repro in (False, True):
            runner.call(EXPANDED, (runner.obj, 5 + (7 << 32), 55 + (12 << 32), temperature, int(repro)))
            actual, _ = runner.table()
            expected = lut_oracle(profile, temperature, repro)
            expanded.append({'temperature': temperature, 'repro': repro,
                             **compare(actual, expand_oracle(expected)),
                             'interior': compare(actual[7:96, 5:110], expected)})
            runner.discard_case()
    # Version 3 takes its temperature branch for either boolean service fixture.
    for temperature in (4000, 7000):
        for repro in (False, True):
            values = []
            for flag in (False, True):
                runner.config = flag
                runner.call(LUT, (runner.obj, temperature, int(repro)))
                values.append(runner.table()[0])
                runner.discard_case()
            assert np.array_equal(*values)
            config_checks.append({'temperature': temperature, 'repro': repro, 'both_boolean_settings_exact': True})
    runner.config = False
    print('Expanded LUT and configuration branch checks passed', flush=True)
    cc, mat1, mat2, grad, inp, out = 0x10010000, 0x10011000, 0x10012000, 0x10020000, 0x10080000, 0x10090000
    matrix = np.array([[.25, .5, .25], [1., -1., 0.], [0., -1., 1.]], dtype='<f8')
    inverse = np.array([[1., .75, -.25], [1., -.25, -.25], [1., -.25, .75]], dtype='<f8')
    curve = np.arange(65536, dtype='<f4')
    runner.u.mem_write(mat1, matrix.tobytes())
    runner.u.mem_write(mat2, inverse.tobytes())
    runner.u.mem_write(grad, curve.tobytes())
    rng = np.random.default_rng(410024)
    basis = np.array([[0, 0, 0], [65535, 0, 0], [0, 65535, 0], [0, 0, 65535],
                      [65535, 65535, 0], [65535, 0, 65535], [0, 65535, 65535], [65535] * 3], dtype='<u2')
    ramps = np.repeat(np.array([1, 2, 7, 255, 256, 1023, 4095, 16383, 32767, 65534], dtype='<u2')[:, None], 3, axis=1)
    pixels = np.vstack([basis, ramps, rng.integers(0, 65536, (256, 3), dtype=np.uint16)]).astype('<u2')
    source = pixels.tobytes()
    runner.u.mem_write(inp, source)
    for temperature in (3050, 5550, 9100):
        for repro in (False, True):
            for expand in (False, True):
                for protection in (False, True):
                    low, high = (.1, .4) if protection else (-1., 0.)
                    runner.call(SETUP, (cc, mat1, mat2, runner.obj, temperature, int(repro), grad, 65536),
                                floats=(low, high), stack=struct.pack('<QQQQ', 0, 50, int(expand), 1))
                    grid, scale = runner.table(cc + 0x138)
                    expected_grid = lut_oracle(profile, temperature, repro)
                    if expand:
                        expected_grid = expand_oracle(expected_grid)
                    compare(grid, expected_grid)
                    stored_matrix = np.frombuffer(bytes(runner.u.mem_read(cc + 0xf0, 72)), dtype='<f8')
                    compare(stored_matrix, matrix_oracle(profile, temperature))
                    assert bytes(runner.u.mem_read(cc + 8, 72)) == matrix.tobytes()
                    assert bytes(runner.u.mem_read(cc + 0x50, 72)) == inverse.tobytes()
                    curve_ptr = struct.unpack('<Q', bytes(runner.u.mem_read(cc + 0x188, 8)))[0]
                    assert bytes(runner.u.mem_read(curve_ptr, curve.nbytes)) == curve.tobytes()
                    # Explicit test thresholds; these are not inferred app defaults.
                    runner.u.mem_write(cc + 0x1b8, struct.pack('<4d', 16384., 0., 1. / 32768., .25))
                    before = [(cc, bytes(runner.u.mem_read(cc, 0x298))), (inp, source)]
                    before += [(p + 16, bytes(runner.u.mem_read(p + 16, n))) for p, n in runner.allocations]
                    runner.u.mem_write(out, b'\xa5' * 32 + b'\xcc' * len(source) + b'\xa5' * 32)
                    runner.call(PIXELS, (0, cc, out + 32, inp, len(pixels), int(not protection)))
                    actual = np.frombuffer(bytes(runner.u.mem_read(out + 32, len(source))), dtype='<u2').reshape(-1, 3)
                    expected = pixel_oracle(pixels, matrix, inverse, expected_grid, scale, protection)
                    delta = np.abs(actual.astype(np.int32) - expected.astype(np.int32))
                    assert delta.max() <= PIXEL_TOLERANCE, (temperature, repro, expand, protection, delta.max())
                    assert bytes(runner.u.mem_read(out, 32)) == bytes(runner.u.mem_read(out + 32 + len(source), 32)) == b'\xa5' * 32
                    assert all(bytes(runner.u.mem_read(p, len(v))) == v for p, v in before)
                    pixel_cases.append({'temperature': temperature, 'repro': repro, 'expanded': expand,
                        'neutral_and_shadow_protection_fixture': protection, 'pixels': len(pixels),
                        'channels': actual.size, 'exact_channels': int(np.count_nonzero(delta == 0)),
                        'max_abs_u16_difference': int(delta.max()), 'black_outputs_zero': bool(np.all(actual[0] == 0)),
                        'setup_fields_verified': True, 'inputs_unchanged_and_output_guards_pass': True})
                    runner.discard_case()
    assert all(bytes(runner.u.mem_read(p, len(v))) == v for p, v in frozen)
    assert runner.called == ALLOWED, sorted(ALLOWED - runner.called)
    return {'matrix_cases': matrices, 'lut_cases': tables, 'expanded_lut_cases': expanded,
        'configuration_checks': config_checks, 'setup_and_pixel_cases': pixel_cases,
        'double_absolute_tolerance': DOUBLE_TOLERANCE, 'pixel_code_tolerance': PIXEL_TOLERANCE,
        'original_functions': [{'name': n, 'address': hex(elf.func[n][0]), 'bytes': elf.func[n][1],
                               'sha256': sha(elf.read(*elf.func[n]))} for n in sorted(runner.called)],
        'host_external_calls': dict(sorted(runner.host_calls.items())),
        'configuration_query_names': sorted(set(runner.config_queries)),
        'allocation_and_object_guards_pass': True, 'loaded_profile_unchanged': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    assert __debug__, 'Do not disable assertions'
    original = args.apk.read_bytes()
    assert sha(original) == APK_SHA
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        lib = archive.read('lib/arm64-v8a/libcrosssdk.so')
        data = archive.read('assets/Colormaps/' + TARGET)
    assert sha(lib) == LIB_SHA
    elf = Elf(lib)
    blocks = np.frombuffer(data, dtype=np.uint8).reshape(-1, 16)
    plain = (decrypt_blocks(elf, blocks[1:]) ^ blocks[:-1]).tobytes()
    padding = plain[-1]
    assert 1 <= padding <= 16 and plain[-padding:] == bytes([padding]) * padding
    plain = plain[:-padding]
    assert sha(plain) == 'c2b3d08e0d489eb852610c12a9b985e9d0340a4dd544f5b0b5b7a6a4f3427e95'
    profile = plistlib.loads(plain)
    assert profile['Version'] == '3.0'
    assert [profile[k] for k in ('tlt', 'tt', 'tf', 'th')] == [2400, 3050, 5550, 9100]
    result = {'schema': 'hasselblad-stage41x-phocus-temperature-v1',
        'apk_sha256': APK_SHA, 'library_sha256': LIB_SHA, 'selected_asset': TARGET,
        'decoded_profile_sha256': sha(plain), 'profile_cpid': '0x0616',
        'selection_provenance': 'Stage41W native selector with ClosedLoop=false; actual app setting unobserved',
        'temperature_clamp_kelvin': [2000, 10000], 'matrix_anchors_kelvin': [2400, 3050, 5550, 9100],
        'chroma_lut_anchors_kelvin': [3050, 5550, 9100], 'interpolation_domain': 'linear Kelvin',
        'grid': {'base_width_height': [105, 89], 'expanded_width_height': [165, 108],
                 'padding_before_xy': [5, 7], 'padding_after_xy': [55, 12],
                 'base_bias_xy': [20, 32], 'expanded_bias_xy': [25, 39],
                 'input_scale_xy': [32, 32], 'output_divisor': 32},
        'audit': audit(elf, profile),
        'fixtures': {'xml_parser_and_key_getters': 'Python plist/key-value facade',
            'profile_object': 'zeroed, original DecodeFrom, profile flag byte +9 set to 1 per constructor trace',
            'correction_object': 'zeroed, original SetupCC; full constructor not executed',
            'allocators_and_memory_functions': 'host-backed guarded arena; free deferred until case discard',
            'pixel_input': '274 synthetic RGB16 triplets reused across configurations',
            'rgb_basis_and_inverse': 'synthetic matrices, not complete app working-space transforms',
            'gradation_curve': 'identity float table, not Phocus film curve',
            'neutral_and_shadow_thresholds': 'explicit test values, not observed app defaults'},
        'bounds': {'arithmetic_or_lookup_functions_stubbed': False,
            'real_profile_matrix_interpolation_executed': True, 'real_profile_lut_reached_native_pixels': True,
            'real_profile_matrix_in_complete_pixel_transform_verified': False,
            'full_app_or_complete_raw_pipeline_executed': False, 'photo_pixels_processed': False,
            'camera_main_isp_equivalence_proven': False, 'production_renderer_changed': False,
            'calibration_arrays_or_crypto_tables_exported': False},
        'runtime': {p: version(p) for p in ('numpy', 'unicorn', 'capstone', 'pyelftools', 'tifffile')}}
    assert sha(args.apk.read_bytes()) == APK_SHA
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    a = result['audit']
    print(json.dumps({'matrix_cases': len(a['matrix_cases']), 'lut_cases': len(a['lut_cases']),
        'expanded_cases': len(a['expanded_lut_cases']), 'pixel_cases': len(a['setup_and_pixel_cases']),
        'pixels': sum(r['pixels'] for r in a['setup_and_pixel_cases']),
        'native_functions': len(a['original_functions']), 'full_raw_render': False}))


if __name__ == '__main__':
    main()
