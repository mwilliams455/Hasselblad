#!/usr/bin/env python3
"""Original CPU/GPU highlight arithmetic and SDR exposure ownership audit."""
import argparse
import hashlib
import itertools
import json
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_import_stage52'))
from audit_import52 import ImportRunner, load_private, y, z, CORR, DESC, HR_CTOR, HR_CONVERT, delta
from audit_gpu50 import shader, encoded8
from highlight53 import Highlight, equal_lower_limit, factor_dng_white_balance
from gles53 import HighlightGLES
from portable53 import Portable
from unicorn.arm64_const import *

FILTER_CTOR = '_ZN36CHighlightReconstructionScalarFilterC1E6CArrayIdLi3EdES0_ItLi3EtE7CXPoint'
CPU = '_ZNK36CHighlightReconstructionScalarFilter12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'
GPU = '_ZN36CHighlightReconstructionScalarFilter15FilterResultGpuER19CGpuPipelineManager6CXRectS2_'
HF, SCALAR, RECT, POINT = 0x100f0000, 0x100f1000, 0x100f2000, 0x100f3000
FLOAT_KEYS = ('uBoScale', 'uBoLevel', 'uNeutral', 'uMidGrayScales',
              'uFullScales', 'uRatioGreenBlue', 'uRatioRed')


class HighlightRunner(ImportRunner):
    def __init__(self, elf, profile):
        y.ALLOWED.update({FILTER_CTOR, CPU, GPU, '_ZN10CImageViewItLi3EEC2ER14CBufferedImage'})
        self.gpu_shape = (1, 1)
        self.highlight_capture = False
        super().__init__(elf, profile)
        for p, n in ((HF, 0x80), (SCALAR, 0xc0)):
            self.u.mem_write(p-16, b'\xa5'*16)
            self.u.mem_write(p+n, b'\xa5'*16)
        self.highlight_guards = True

    def check_guards(self):
        super().check_guards()
        if getattr(self, 'highlight_guards', False):
            for p, n in ((HF, 0x80), (SCALAR, 0xc0)):
                assert bytes(self.u.mem_read(p-16, 16)) == bytes(self.u.mem_read(p+n, 16)) == b'\xa5'*16

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0+i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        if self.highlight_capture:
            if name.startswith('_ZN10GpuHandler18GetTextureInFormatE'):
                assert self.get(reg(1), 0, '<i') == (8,) and reg(2) == 1
                self.texture_requests.append(8)
                self.u.mem_write(reg(8), b'\0'*48)
                self.put(reg(8), 20, '<2i', *self.gpu_shape)
                finish(); return
            if name.startswith('_ZN11ComputeTask10SetUniformE') and 'vectorI' in name:
                lo, hi, end = self.get(reg(2), 0, '<3Q')
                assert hi-lo in (8, 12) and end >= hi
                dtype = '<i4' if 'vectorIi' in name else '<f4'
                self.uniforms[self.getstr(reg(1))] = np.frombuffer(bytes(self.u.mem_read(lo, hi-lo)), dtype=dtype).copy()
                finish(); return
        return super().hook(cpu, address, size, user)

    def prepare(self, gains, truncation):
        packed = sum(int(t) << (16*i) for i, t in enumerate(truncation))
        self.u.mem_write(POINT, b'\0'*24)
        self.call(FILTER_CTOR, (HF, packed, POINT), gains)
        self.call(HR_CTOR, (SCALAR, packed), gains)
        params = {n: self.doubles(SCALAR+0x18+24*i, 3) for i, n in enumerate(FLOAT_KEYS)}
        params['uOrder'] = np.array(self.get(SCALAR, 0, '<3i'))
        params['uOrderBack'] = np.array(self.get(SCALAR, 12, '<3i'))
        return params

    def scalar(self, pixels):
        frozen = bytes(self.u.mem_read(SCALAR, 0xc0))
        output = []
        for p in pixels:
            self.call(HR_CONVERT, (SCALAR,), p)
            output.append([struct.unpack('<d', struct.pack('<Q', self.u.reg_read(UC_ARM64_REG_D0+i)))[0]
                           for i in range(3)])
        assert frozen == bytes(self.u.mem_read(SCALAR, 0xc0))
        return np.asarray(output)

    def cpu16(self, pixels):
        pixels = np.ascontiguousarray(pixels, dtype='<u2').reshape(-1, 3)
        data, obj, ip, op = 0x10100000, 0x100d5000, 0x100f4000, 0x100f4010
        self.u.mem_write(data-16, b'\xa5'*16+pixels.tobytes()+b'\xa5'*16)
        self.u.mem_write(obj, b'\0'*48)
        self.put(obj, 8, '<4i', len(pixels), 1, 3, len(pixels)*3)
        self.put(obj, 0x20, '<Q', data)
        self.u.mem_write(RECT, b'\0'*32)
        self.put(RECT, 8, '<?', True)
        self.put(RECT, 12, '<4i', 0, 0, len(pixels), 1)
        self.put(ip, 0, '<Q', obj); self.put(op, 0, '<Q', 0)
        self.cpu_fixture = True
        self.call(CPU, (HF, RECT, RECT, ip, op))
        self.cpu_fixture = False
        assert self.get(0x10002000, 0, '<Q') == (obj,)
        assert bytes(self.u.mem_read(data-16, 16)) == bytes(self.u.mem_read(data+pixels.nbytes, 16)) == b'\xa5'*16
        return np.frombuffer(bytes(self.u.mem_read(data, pixels.nbytes)), dtype='<u2').copy().reshape(pixels.shape)

    def gpu_parameters(self, width, height):
        self.u.mem_write(RECT, b'\0'*32)
        self.put(RECT, 8, '<?', True)
        self.put(RECT, 12, '<4i', 0, 0, width, height)
        self.gpu_shape = width, height
        self.uniforms, self.texture_requests, self.dispatches = {}, [], []
        self.highlight_capture = self.record_gpu = True
        self.call(GPU, (HF, 0x100c0000, RECT, RECT))
        self.highlight_capture = self.record_gpu = False
        assert self.compute_name == 'HighlightRecoveryScalarRGB'
        assert self.texture_requests == [8, 8] and self.dispatches == [[width, height]]
        return {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in self.uniforms.items()}


def test_pixels(truncation):
    unit = np.linspace(0, 1, 9)
    cube = np.stack(np.meshgrid(*[unit]*3, indexing='ij'), -1).reshape(-1, 3)
    ramp = np.repeat(np.linspace(0, 1, 257)[:, None], 3, 1)
    rng = np.random.default_rng(53)
    points = [cube*65535, cube*np.asarray(truncation), ramp*65535, rng.uniform(0, 65535, (256, 3))]
    for ch in range(3):
        for offset in (-1, 0, 1):
            boundary = rng.uniform(0, 65535, (9, 3))
            boundary[:, ch] = min(65535, max(0, truncation[ch]+offset))
            points.append(boundary)
    return np.rint(np.vstack(points)).astype(np.uint16)


def summarize(results):
    return {'cases': len(results), 'channels': sum(r['channels'] for r in results),
            'maximum_absolute_difference': max(r['max_abs_difference'] for r in results),
            'mean_absolute_difference': sum(r['mean_abs_difference']*r['channels'] for r in results)/sum(r['channels'] for r in results),
            'exact_channels': sum(r['exact_channels'] for r in results)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--work-dir', type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    elf, profile = load_private(a.apk)
    r = HighlightRunner(elf, profile)
    portable = Portable(a.work_dir)
    rejection_cases = portable.check_rejections()
    cases = []
    for gains in itertools.permutations((1., 1.4, 1.8)):
        for truncation in ((65535,)*3, (60000, 58000, 62000), (1023, 4095, 16383)):
            cases.append((gains, truncation, 'synthetic_regular'))
    for gains in sorted(set(itertools.permutations((1., 2., 2.)))):
        for truncation in ((65535,)*3, (60000, 58000, 62000)):
            cases.append((gains, truncation, 'equal_upper'))
    for gains in itertools.permutations((1., 1.0001, 2.)):
        cases.append((gains, (65535,)*3, 'near_equal_lower'))
    wb_matrix = (np.array(profile['mf'])*.5+1).reshape(3, 3) @ np.diag(np.array(profile['vf'])*.5+1)
    wb_inverse, wb_table = np.linalg.inv(wb_matrix), z.temperature_table(elf)
    for temp, tint in itertools.product((2850, 4000, 6500, 10000), (-.003, .003)):
        gain = z.temp_to_gain_oracle(temp, tint, wb_inverse, wb_table, elf)
        cases.append((gain, (65535,)*3, 'private_profile_generated'))
    original_cpu, c_cpu, c_oracle, c_float, gpu16, gpu8, gpu32 = [], [], [], [], [], [], []
    cpu_gpu16, cpu_gpu32 = [], []
    parameter_errors, uniform_errors, scalar_errors = [], [], []
    g = HighlightGLES()
    fragment = shader(elf, 'highlightrecoveryscalarrgb_fragmentShaderSource')
    for case_index, (gains, truncation, kind) in enumerate(cases):
        actual = r.prepare(gains, truncation)
        h = Highlight.prepare(gains, truncation)
        assert portable.prepare(gains, truncation) == 0
        for n, v in h.parameters().items():
            relative = np.max(np.abs(actual[n]-v)/np.maximum(1, np.abs(v)))
            assert relative < 1e-10, (case_index, n, relative)
            parameter_errors.append(float(relative))
        pixels = test_pixels(truncation)
        expected = np.floor(np.clip(h.convert(pixels/65535), 0, 1)*65535+.5).astype(np.uint16)
        native = r.cpu16(pixels)
        c = portable.render(pixels)
        assert np.array_equal(c, portable.render(pixels, inplace=True))
        original_cpu.append(delta(native, expected)); c_cpu.append(delta(c, native)); c_oracle.append(delta(c, expected))
        assert max(original_cpu[-1]['max_abs_difference'], c_cpu[-1]['max_abs_difference'], c_oracle[-1]['max_abs_difference']) <= 1
        fp = (pixels/65535).astype(np.float32)
        c_float.append(delta(portable.render(fp), h.convert(fp).astype(np.float32)))
        assert c_float[-1]['max_abs_difference'] < 2e-7
        # Original double pixel body is checked separately from integer wrappers.
        sample = fp[::67].astype(float)
        scalar_error = np.max(np.abs(r.scalar(sample)-h.convert(sample)))
        scalar_errors.append(float(scalar_error)); assert scalar_error < 1e-10
        uniforms = r.gpu_parameters(len(pixels), 1)
        for n, v in h.parameters().items():
            expected_uniform = v.astype(np.int32 if n.startswith('uOrder') else np.float32)
            rel = np.max(np.abs(uniforms[n]-expected_uniform)/np.maximum(1, np.abs(expected_uniform)))
            uniform_errors.append(float(rel)); assert rel < 3e-7
        for storage in (0x881a, 0x8814):
            output = g.render(fragment, fp, uniforms, storage)
            gpu_oracle = Highlight.from_float32_uniforms(uniforms)
            reference = np.clip(gpu_oracle.convert(g.last_stored_input, gpu_dark_threshold=True), 0, 1)
            assert np.isfinite(output).all()
            metric = delta(output, reference)
            if storage == 0x881a:
                gpu16.append(metric); gpu8.append(delta(encoded8(output), encoded8(reference)))
                cpu_gpu16.append(delta(native/65535, output))
                assert metric['max_abs_difference'] < 6e-4 and gpu8[-1]['max_abs_difference'] <= 1, (case_index, metric)
            else:
                gpu32.append(metric); assert metric['max_abs_difference'] < 2e-5, (case_index, metric)
                cpu_gpu32.append(delta(native/65535, output))
        print(f'Case {case_index+1}/{len(cases)}: {kind}, CPU/C/GPU passed', flush=True)
    # Characterize native singularities, without requiring a platform's NaN
    # clamp result to be reproduced by the independent implementation.
    singularities, limits, extension_float, extension_uint16 = [], [], [], []
    small = np.array(list(itertools.product(np.linspace(0, 1, 5), repeat=3)))
    for gains in ((1., 1., 1.), (2., 1., 1.), (1., 2., 1.), (1., 1., 2.)):
        r.prepare(gains, (65535,)*3)
        native = r.scalar(small)
        native16 = r.cpu16(np.rint(small*65535).astype(np.uint16))
        uniforms = r.gpu_parameters(len(small), 1)
        gpu = g.render(fragment, small, uniforms)
        assert np.count_nonzero(~np.isfinite(native)) > 0
        assert portable.prepare(gains, (65535,)*3, limit=False) == -2
        assert portable.prepare(gains, (65535,)*3, limit=True) == 1
        expected = equal_lower_limit(small, gains)
        c = portable.render(small.astype(np.float32))
        assert np.max(np.abs(c-expected)) < 1e-7 and np.isfinite(c).all()
        if gains == (1., 1., 1.): assert np.array_equal(c, small.astype(np.float32))
        singularities.append({'synthetic_gains': list(gains),
            'native_scalar_nonfinite_channels': int(np.count_nonzero(~np.isfinite(native))),
            'native_cpu16_vs_gpu16_max_linear_difference': float(np.nanmax(np.abs(native16/65535-gpu))),
            'regular_c_path_rejects': True, 'opt_in_limit_is_finite': True})
        # Approach the same limit from both orderings of the equal lower pair.
        lower = [i for i, x in enumerate(gains) if x == min(gains)]
        for selected in lower[:2]:
            errors = []
            for eps in (1e-4, 1e-6, 1e-8):
                near = np.array(gains); near[selected] += eps
                if gains == (1., 1., 1.): near[(selected+1)%3] += 2*eps
                r.prepare(near, (65535,)*3)
                result = r.scalar(small)
                errors.append(float(np.max(np.abs(result-expected))))
            assert all(errors[i+1] < errors[i] for i in range(2)) and errors[-1] < 3e-8
            limits.append({'synthetic_gains': list(gains), 'approach_channel': selected,
                           'epsilon': [1e-4, 1e-6, 1e-8], 'maximum_errors_to_analytic_limit': errors})
        for truncation in ((65535,)*3, (60000, 58000, 62000), (1023, 4095, 16383)):
            assert portable.prepare(gains, truncation, limit=True) == 1
            pixels = test_pixels(truncation)
            fp = (pixels/65535).astype(np.float32)
            expected = equal_lower_limit(fp, gains, truncation).astype(np.float32)
            extension_float.append(delta(portable.render(fp), expected))
            assert extension_float[-1]['max_abs_difference'] < 1e-7
            expected16 = np.floor(equal_lower_limit(pixels/65535, gains, truncation)*65535+.5).astype(np.uint16)
            actual16 = portable.render(pixels)
            assert np.array_equal(actual16, portable.render(pixels, inplace=True))
            extension_uint16.append(delta(actual16, expected16))
            assert extension_uint16[-1]['max_abs_difference'] <= 1
    print('Native singularities characterized; opt-in analytic limits converge from both channel orders', flush=True)
    # Original tool-4 exposure scalar, with explicit raw-description source factors.
    exposure_errors = []
    for temp, tint, ev, enabled, factors in itertools.product((2850, 4000, 6500), (-.003, .003),
            (-2., 0., 2.), (False, True), ((1., 1., 1.), (1.25, .8, 1.1))):
        source = z.temp_to_gain_oracle(temp, tint, wb_inverse, wb_table, elf)
        r.configure(source, ev, present=(True, False, False))
        gains = r.process()
        r.put(CORR, 0x93, '<?', enabled)
        for off, value in zip((0x18, 0x40, 0x50), factors): r.put(DESC, off, '<d', value)
        r.call(z.EXPOSURE, (0, CORR, DESC))
        actual = np.array([struct.unpack('<d', struct.pack('<Q', r.u.reg_read(UC_ARM64_REG_D0+i)))[0] for i in range(2)])
        expected = np.array([1., gains.max()*np.prod(factors)*(2**ev if enabled else 1)])
        error = float(np.max(np.abs(actual-expected))); assert error < 1e-10
        exposure_errors.append(error)
    # Algebraic WB ownership for a future DNG bridge; deliberately no private
    # sensor matrices or photographic pixels are used in this invariant check.
    bridge_errors = []
    rng = np.random.default_rng(5300)
    for _ in range(100):
        matrix = np.eye(3)+rng.uniform(-.3, .3, (3, 3))
        neutral = rng.uniform(.15, 1.5, 3)
        gains, after = factor_dng_white_balance(matrix, neutral)
        pixels = rng.uniform(0, 1, (20, 3))
        difference = (pixels*(gains/gains.max()))@after.T-pixels@matrix.T
        error = float(np.max(np.abs(difference))); assert error < 2e-15
        bridge_errors.append(error)
    print(f'{len(exposure_errors)} native exposure routes and {len(bridge_errors)} synthetic DNG WB factorizations passed', flush=True)
    for ptr, frozen in r.frozen_profile: assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    g.close()
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    receipt = {'schema': 'hasselblad-stage53-native-highlight-v1',
        'status': 'PASS_BOUNDED_HIGHLIGHT_RECONSTRUCTION_WITH_SINGULARITY_CHARACTERIZATION',
        'regular_cases': len(cases), 'native_parameter_max_relative_error': max(parameter_errors),
        'gpu_uniform_max_relative_error': max(uniform_errors), 'native_double_max_absolute_error': max(scalar_errors),
        'native_cpu16_vs_independent': summarize(original_cpu), 'portable_c_vs_native_cpu16': summarize(c_cpu),
        'portable_c_vs_python_uint16': summarize(c_oracle), 'portable_c_float_vs_python': summarize(c_float),
        'original_shader_rgba16f_vs_independent_linear': summarize(gpu16),
        'original_shader_rgba16f_vs_independent_code8': summarize(gpu8),
        'original_shader_rgba32f_diagnostic_vs_independent_linear': summarize(gpu32),
        'native_cpu16_vs_original_gpu16_characterization': summarize(cpu_gpu16),
        'native_cpu16_vs_original_gpu32_characterization': summarize(cpu_gpu32),
        'cpu_gpu_equality_asserted': False,
        'cpu_gpu_precision_note': 'Different arithmetic precision, input storage, dark threshold and clipping-branch decisions; reference paths validated separately',
        'portable_api_rejected_input_checks': rejection_cases,
        'rejected_inputs_preserve_parameters_and_output': True,
        'native_singularities': singularities, 'analytic_limit_convergence': limits,
        'analytic_limit_portable_float_vs_python': summarize(extension_float),
        'analytic_limit_portable_uint16_vs_python': summarize(extension_uint16),
        'analytic_limit_is_deliberate_extension_not_native_nan_emulation': True,
        'native_tool4_exposure_cases': len(exposure_errors), 'native_exposure_max_absolute_error': max(exposure_errors),
        'exposure_rule': 'max(WB gains) * source18 * source40 * source50 * enabled exposure scalar',
        'synthetic_dng_wb_factorizations': len(bridge_errors), 'wb_factorization_max_absolute_error': max(bridge_errors),
        'bridge_rule': 'post_matrix = existing_camera_to_D50 * diag(max(gains)/gains); gains = reciprocal AsShotNeutral',
        'compiler': portable.compiler, 'compiler_warnings_are_errors': True, 'gles': g.info,
        'fixtures': ['host allocation/libm/configuration/private profile cache inherited from Stage52',
            'CPU image ownership fixture; original constructor and complete uint16 pixel filter execute',
            'GPU handler/texture/task recording fixtures; original GPU parameter body and unmodified private fragment shader execute',
            'software GLES with actual stored input readback; RGBA16F selected native format, RGBA32F diagnostic only'],
        'private_shader_calibration_or_source_hash_exported': False, 'source_apk_and_profile_unchanged': True,
        'scene_pixels_used': False, 'scene_specific_tuning': False, 'capture_renderer_changed': False,
        'new_apk_built': False, 'physical_phone_adaptation_validated': False, 'full_phocus_equivalence': False,
        'next_boundary': 'sensor clipping and DNG WB factorization integration in an isolated saved-DNG preview'}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(receipt, indent=2)+'\n')
    print(receipt['status'], flush=True)


if __name__ == '__main__': main()
