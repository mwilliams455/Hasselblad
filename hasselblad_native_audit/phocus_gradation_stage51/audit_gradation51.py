#!/usr/bin/env python3
"""Original default SDR gradation, with independent math and synthetic pixels.

The private APK supplies original code. No vendor shader/table, calibration,
private hash or photographic pixels are included in the aggregate receipt.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_gpu_stage50'))
from audit_gpu50 import Runner, load_private, y, shader, encoded8, delta, TEXTURE
from audit_output49 import cmm_oracle
from gles51 import CurveGLES
from unicorn.arm64_const import *

CTOR = '_ZN16CImageCorrectionC1Ev'
CALC = '_ZN17CCalculatedCurvesC1ERK16CImageCorrection'
GRAD = '_ZN16CGradationFilterC1ENSt6__ndk110shared_ptrIK17CCalculatedCurvesEEb'
CPU = '_ZNK16CGradationFilter12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'
GPU = '_ZN16CGradationFilter15FilterResultGpuER19CGpuPipelineManager6CXRectS2_'
CURVE_TEXTURE = '_Z11CreateCurveR10GpuHandlerNSt6__ndk14spanIKtLm18446744073709551615EEES4_S4_'
PIXEL = '_ZN14CBufferedImage11GetPixelPtrEjj'
FILE_CTOR = '_ZN9CFileSpecC1EPKcbii'
CORR, CURVES, FILTER, SHARED = 0x100d0000, 0x100d1000, 0x100d2000, 0x100d3000


def allow(elf):
    # Bounded local vector-storage and shared-pointer construction helpers.
    elf.func['stage51_u16_append'] = (0x3320ed8, 0x1b4)
    elf.func['stage51_highshadow_factory'] = (0x32e11d4, 0x11c)
    families = ('CPointCurve', 'CContrastCurve', 'CGammaCurve', 'CAggregateCurve',
                'CHighShadowCurve', '6CCurve', 'CCalculatedCurves', '16CGradationFilter')
    names = {n for n in elf.func if any(k in n for k in families)
             and not n.startswith(('_ZTh', '_ZTv'))}
    names.update({CTOR, CALC, GRAD, CPU, GPU, PIXEL, CURVE_TEXTURE,
        'stage51_u16_append', 'stage51_highshadow_factory',
        '_ZN16CImageCorrection4InitEv', '_ZN16CImageCorrection16SetDefaultValuesEv',
        '_ZN16CImageCorrection15ResetGradationsEv',
        '_ZN16CImageCorrection25SetDefaultColorManagementEv',
        '_ZN16CImageCorrection18SetDefaultKeystoneEv', '_ZN12CCustomWhiteC1Ev',
        '_ZNK16CImageCorrection12GetGradationE10eColorType',
        '_ZNK16CImageCorrection14EffectiveGammaE10eColorType',
        '_ZNK16CImageCorrection11GetContrastEv', '_ZNK16CImageCorrection13GetBrightnessEv',
        '_ZNK16CImageCorrection11GetDotColorE7eHSType10eColorType',
        '_ZNK16CImageCorrection11GetShadow14E10eColorType',
        '_ZNK16CImageCorrection14GetHighlight14E10eColorType',
        '_ZNK16CImageCorrection11GetEndPointE7eHSType',
        '_Z14CalculateCurveP6CCurveb', '_ZN9CFileSpecC1Ev', '_ZN9CFileSpecD1Ev',
        '_ZN12CImageFilterC2ENSt6__ndk112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEEd'})
    y.ALLOWED.update(names)
    return names


class GradationRunner(Runner):
    def __init__(self, elf):
        names = allow(elf)
        super().__init__(elf)
        self.entries = {elf.func[n][0]: n for n in names}
        self.u.mem_write(0x10005248, struct.pack('<Q', 0x30002008))
        self.curve_textures, self.samplers = [], {}
        self.cpu_fixture = False
        self.fixture_calls = {'file_name_constructor': 0, 'reference_count': 0,
                              'point_curve_shared_array_destruction': 0, 'inplace_ownership': 0}
        for p, n in ((CORR, 0x460), (CURVES, 0x80), (FILTER, 0xf0)):
            self.u.mem_write(p - 16, b'\xa5' * 16)
            self.u.mem_write(p + n, b'\xa5' * 16)

    def hook(self, cpu, address, size, user):
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0 + i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        name = self.e.plt.get(address, '')
        if name == FILE_CTOR:
            # File-service availability cannot affect these curve calculations.
            self.fixture_calls['file_name_constructor'] += 1
            self.u.mem_write(reg(0), b'\0' * 0x38); finish(); return
        if address == 0x30002008:
            self.config_queries.append(self.getstr(reg(1)))
            cpu.reg_write(UC_ARM64_REG_D0, 0); finish(); return
        if address in self.entries:
            n = self.entries[address]; a, length = self.e.func[n]
            if (a, a + length) not in self.active: self.active.append((a, a + length))
            self.called.add(n)
        if address in (0x3790b20, 0x3790b50):
            self.fixture_calls['reference_count'] += 1
            cpu.reg_write(UC_ARM64_REG_X0, 1); finish(); return
        if name == '_ZNSt6__ndk15arrayINS_10shared_ptrI11CPointCurveEELm8EED2Ev':
            self.fixture_calls['point_curve_shared_array_destruction'] += 1
            finish(); return
        if self.cpu_fixture and name.startswith('_ZN12CImageFilter15SetupForInplaceE'):
            self.fixture_calls['inplace_ownership'] += 1
            self.u.mem_write(reg(2), b'\0' * 8)
            self.u.mem_write(reg(3), b'\0' * 8)
            self.u.mem_write(reg(8), struct.pack('<Q', 0x100d5000)); finish(); return
        if self.record_gpu:
            if name.startswith('_ZN10GpuHandler25MakeTextureFromBytesConstE'):
                assert [reg(i) for i in (1, 3, 4, 5, 6)] == [15, 256, 256, 1, 0]
                self.curve_textures.append(np.frombuffer(bytes(self.u.mem_read(reg(2), 256 * 256 * 16)), dtype='<f4').copy().reshape(256, 256, 4))
                self.u.mem_write(reg(8), struct.pack('<I', len(self.curve_textures)) + b'\0' * 44)
                finish(); return
            if name.startswith('_ZN11ComputeTask18InsertInputTextureE'):
                texture = struct.unpack('<I', bytes(self.u.mem_read(reg(3), 4)))[0]
                self.samplers[self.getstr(reg(2))] = texture - 1
                finish(); return
        return super().hook(cpu, address, size, user)

    def check_guards(self):
        super().check_guards()
        if hasattr(self, 'fixture_calls'):
            for p, n in ((CORR, 0x460), (CURVES, 0x80), (FILTER, 0xf0)):
                assert bytes(self.u.mem_read(p - 16, 16)) == bytes(self.u.mem_read(p + n, 16)) == b'\xa5' * 16

    def defaults(self):
        self.call(CTOR, (CORR,))
        assert struct.unpack('<i', bytes(self.u.mem_read(CORR + 0x428, 4)))[0] == 2
        assert struct.unpack('<i', bytes(self.u.mem_read(CORR + 0xe4, 4)))[0] == 0
        assert struct.unpack('<i', bytes(self.u.mem_read(CORR + 0x2cc, 4)))[0] == 4
        assert self.config_queries == ['DumpCW', 'LogCW']
        for channel in (1, 2, 3):
            for name, args, expected in (
                ('_ZNK16CImageCorrection11GetDotColorE7eHSType10eColorType', (0, channel), 0),
                ('_ZNK16CImageCorrection11GetDotColorE7eHSType10eColorType', (1, channel), 255),
                ('_ZNK16CImageCorrection11GetShadow14E10eColorType', (channel,), 0),
                ('_ZNK16CImageCorrection14GetHighlight14E10eColorType', (channel,), 16383)):
                self.call(name, (CORR, *args))
                assert self.u.reg_read(UC_ARM64_REG_X0) == expected

    def calculate(self):
        before = bytes(self.u.mem_read(CORR, 0x460))
        self.call(CALC, (CURVES, CORR))
        assert bytes(self.u.mem_read(CORR, 0x460)) == before
        rows = []
        for off in (0, 24, 48, 72, 96):
            lo, hi, end = struct.unpack('<3Q', bytes(self.u.mem_read(CURVES + off, 24)))
            assert hi - lo == 65536 * 2 and end >= hi
            rows.append(np.frombuffer(bytes(self.u.mem_read(lo, hi - lo)), dtype='<u2').copy())
        self.u.mem_write(SHARED, struct.pack('<2Q', CURVES, 0))
        self.call(GRAD, (FILTER, SHARED, 0))
        assert struct.unpack('<i', bytes(self.u.mem_read(FILTER + 0xe8, 4)))[0] == 2
        return np.stack(rows)

    def cpu(self, pixels, version):
        p = np.ascontiguousarray(pixels, dtype='<u2').reshape(-1, 3)
        data, obj, rect, ip, op = 0x10100000, 0x100d5000, 0x100d4000, 0x100d6000, 0x100d6010
        self.u.mem_write(data - 16, b'\xa5' * 16 + p.tobytes() + b'\xa5' * 16)
        self.u.mem_write(obj, b'\0' * 48)
        self.u.mem_write(obj + 8, struct.pack('<4i', len(p), 1, 3, len(p) * 3))
        self.u.mem_write(obj + 0x20, struct.pack('<Q', data))
        self.u.mem_write(rect, b'\0' * 32)
        self.u.mem_write(rect + 8, b'\1')
        self.u.mem_write(rect + 12, struct.pack('<4i', 0, 0, len(p), 1))
        self.u.mem_write(ip, struct.pack('<Q', obj)); self.u.mem_write(op, b'\0' * 8)
        self.u.mem_write(FILTER + 0xec, bytes([version]))
        self.cpu_fixture = True
        self.call(CPU, (FILTER, rect, rect, ip, op))
        self.cpu_fixture = False
        assert struct.unpack('<Q', bytes(self.u.mem_read(0x10002000, 8)))[0] == obj
        assert bytes(self.u.mem_read(data - 16, 16)) == bytes(self.u.mem_read(data + p.nbytes, 16)) == b'\xa5' * 16
        return np.frombuffer(bytes(self.u.mem_read(data, p.nbytes)), dtype='<u2').copy().reshape(pixels.shape)

    def gpu_parameters(self, version):
        rect = 0x100d4000
        self.u.mem_write(rect, b'\0' * 32)
        self.u.mem_write(rect + 8, b'\1')
        self.u.mem_write(rect + 12, struct.pack('<4i', 0, 0, 17, 1))
        self.u.mem_write(FILTER + 0xec, bytes([version]))
        self.uniforms, self.texture_requests, self.dispatches = {}, [], []
        self.curve_textures, self.samplers = [], {}
        self.record_gpu = True
        self.call(GPU, (FILTER, 0x100c0000, rect, rect))
        self.record_gpu = False
        assert self.compute_name == 'Gradation'
        assert self.texture_requests == [8, 8] and self.dispatches == [[17, 1]]
        assert self.uniforms == {'uHasContrast': 1, 'uLumaPoints': 2, 'uVersion': version}
        return dict(self.uniforms), {n: self.curve_textures[i] for n, i in self.samplers.items()}


def default_curve():
    """Independent reconstruction for unedited SDR defaults only.

    Native highlight endpoint: 16383; 14-bit endpoint normalization: 255*64.
    Preserve intermediate float stores and integer LUT indexing.
    """
    i = np.arange(65536, dtype=float)
    high = 16383 / (255 * 64)
    gain = 1 / float(np.float32(high))
    extent = high * gain
    base = ((extent / 65535) * i).astype(np.float32)
    index = (((i * (1 / 65535)) * gain) * 65535 / extent).astype(np.int64)
    value = base[index].astype(float)
    return np.clip(np.floor(value * 65535 + .5), 0, 65535).astype(np.uint16)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    elf, _ = load_private(a.apk)
    r = GradationRunner(elf); r.defaults()
    tables = r.calculate()
    identity = np.arange(65536, dtype=np.uint16)
    oracle = default_curve()
    assert np.array_equal(tables[:2], np.stack([identity] * 2))
    assert np.array_equal(tables[2:], np.stack([oracle] * 3))
    table_check = delta(tables[2:], np.stack([oracle] * 3))
    default_difference = delta(tables[2:], np.stack([identity] * 3))
    print('Original default curves verified exactly against independent arithmetic', flush=True)
    # Change unrelated colour-selection inputs; no scene pixels enter this path.
    r2 = GradationRunner(elf); r2.defaults()
    for off, fmt, value in ((0xe4, '<i', 1), (0x29c, '<i', 6500), (0x2a0, '<d', .003), (0x2cc, '<i', 1)):
        r2.u.mem_write(CORR + off, struct.pack(fmt, value))
    second = r2.calculate()
    assert np.array_equal(tables, second)
    print('Colour-selection perturbation leaves all five gradation tables exact', flush=True)
    cube = np.rint(np.stack(np.meshgrid(*[np.linspace(0, 65535, 17)] * 3, indexing='ij'), -1).reshape(-1, 3)).astype(np.uint16)
    ramp = np.repeat(np.rint(np.linspace(0, 65535, 513)).astype(np.uint16)[:, None], 3, 1)
    pixels = np.vstack([cube, ramp])
    native_cpu = []
    for version in (0, 1):
        out = r.cpu(pixels, version)
        result = delta(out, oracle[pixels])
        assert result['max_abs_difference'] <= (0 if version == 0 else 1)
        native_cpu.append({'version': version, **result})
    print('Original CPU pixel consumers checked for both version flags', flush=True)
    uniforms, textures = r.gpu_parameters(0)
    assert set(textures) == {'uRgbCurve', 'uContrastCurve', 'uLumaUserCurve'}
    for name, t in textures.items():
        raw = tables[2:].T if name == 'uRgbCurve' else np.repeat(identity[:, None], 3, 1)
        expected = raw.astype(np.float32) * np.float32(1 / 65535)
        assert np.array_equal(t.reshape(-1, 4)[:, :3], expected)
        assert not np.count_nonzero(t[..., 3])
    r.call(TEXTURE, (15,)); assert r.u.reg_read(UC_ARM64_REG_X0) == 0x8814
    g = CurveGLES(); kernels = []
    fp = pixels.astype(np.float32) / np.float32(65535)
    # Both samplers are explicit test fixtures; live sampler state is unobserved.
    for linear in (False, True):
        for version in (0, 1):
            output = g.render_curves(shader(elf, 'gradation_fragmentShaderSource'), fp,
                {**uniforms, 'uVersion': version}, textures, linear)
            expected = oracle[pixels].astype(float) / 65535
            result = delta(encoded8(output), encoded8(expected))
            assert result['max_abs_difference'] <= 1
            kernels.append({'version': version, 'sampler_fixture': 'linear' if linear else 'nearest', **result})
    info = g.info; g.close()
    # Stage49 independently validated this native SDR CMM reconstruction.
    # This measures synthetic output sensitivity, not an end-to-end RAW render.
    converter = r.converter(0)
    matrix = r.doubles(converter + 0x20, 9).reshape(3, 3)
    transfer = struct.unpack('<di4xd', bytes(r.u.mem_read(converter + 8, 24)))
    displayed_before = cmm_oracle(pixels, matrix, transfer)
    displayed_after = cmm_oracle(oracle[pixels], matrix, transfer)
    output_difference = delta(encoded8(displayed_after.astype(float) / 65535),
                              encoded8(displayed_before.astype(float) / 65535))
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    r.check_guards(); r2.check_guards()
    receipt = {'schema': 'hasselblad-stage51-default-gradation-v1', 'status': 'PASS_BOUNDED_DEFAULT_GRADATION',
        'native_default_tool_code': 2, 'native_default_working_space': 0,
        'native_default_film_request': 4, 'film_request_4_meaning': 'inherit source film, established in Stage45',
        'default_contrast_and_luma_identity_values': 131072, 'default_luma_points': 2,
        'independent_rgb_curve': table_check, 'rgb_default_difference_from_identity': default_difference,
        'rgb_curve_maximum': int(oracle[-1]), 'rgb_curve_monotonic': bool(np.all(np.diff(oracle.astype(int)) >= 0)),
        'colour_selection_invariance': {'cases': 2, 'changed_working_space': 1, 'changed_temperature': 6500,
            'changed_tint': .003, 'changed_film': 1, 'exact_values': 5 * 65536},
        'synthetic_pixels_per_consumer': len(pixels), 'native_cpu_consumers': native_cpu,
        'native_gpu_texture_preparation_float_values_exact': 3 * 65536 * 4,
        'native_gpu_uniforms': uniforms, 'original_shader_runs': kernels, 'GLES': info,
        'synthetic_srgb_difference_with_default_gradation': output_difference,
        'synthetic_srgb_method': 'Stage49-validated CMM reconstruction, original native matrix and transfer parameters',
        'scope': {'original_default_and_curve_generation_bodies_executed': True,
            'original_cpu_pixel_body_executed': True, 'original_gpu_parameter_body_executed': True,
            'original_fragment_shader_executed': True, 'native_allocations_guarded': True,
            'fixture_calls': r.fixture_calls, 'app_configuration_fixtures': {'DumpCW': False, 'LogCW': 0},
            'gpu_handler_task_texture_ownership_are_recording_fixtures': True,
            'live_texture_sampler_observed': False, 'live_import_overrides_observed': False,
            'phone_gpu_executed': False, 'raw_pipeline_executed': False,
            'photograph_used_for_fitting': False, 'source_apk_unchanged': True,
            'app_renderer_changed': False, 'full_phocus_equivalence': False},
        'original_functions_executed': sorted(r.called | r2.called),
        'interpretation': 'Default post-film RGB gradation is a small equal-channel endpoint adjustment; contrast and luma curves are identity. The missing default stage is bounded and is not evidence for a large aesthetic tone correction.',
        'next': 'Verify RAW/import overrides and phone sensor adaptation before deploying general rendering changes.'}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'independent_rgb_values_exact': table_check['exact_channels'],
                      'rgb_default_max_difference_16bit': default_difference['max_abs_difference']}), flush=True)


if __name__ == '__main__': main()
