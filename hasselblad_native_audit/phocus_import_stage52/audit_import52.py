#!/usr/bin/env python3
"""Bounded native RAW-import defaults and white-balance parameter routing.

Reads original code/calibration from a separately supplied private APK. Only
independent source and aggregate results are suitable for publication.
"""
import argparse
import hashlib
import itertools
import json
import math
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_gradation_stage51'))
from audit_gradation51 import GradationRunner, CORR, default_curve, load_private, y, delta
from audit_parameters45 import z
from unicorn.arm64_const import *

CONFIGURE = '_Z24configureImageCorrectionP16CImageCorrectionPK15sRawDescriptionb'
UPDATE = '_ZN12CCameraImage19UpdateProcessParamsENSt6__ndk110shared_ptrIK15sRawDescriptionEEP14sProcessParamsP13CRawImageFileP16CImageCorrectionPK17CImageDescriptionNS1_I11CClarifyMapEE'
RAW_BUILD = '_ZN12CCameraImage23AddSingleshotRawFiltersEP15CImageProcessorNSt6__ndk110shared_ptrIK15sRawDescriptionEEP13CRawImageFileP14sProcessParamsPK16CImageCorrectionRi'
DEMOSAIC = '_ZN15CDemosaicFilterC1E6CArrayIdLi3E23Matrix3x1InitializationEdidd9eCCDTypes7CXPoint'
HR_CTOR = '_ZN30CHighlightReconstructionScalarC1E6CArrayIdLi3EdES0_ItLi3EtE'
HR_CONVERT = '_ZNK30CHighlightReconstructionScalar7ConvertE6CArrayIdLi3EdE'
DESC, SHARED_DESC, PARAMS, EMPTY = 0x100e0000, 0x100e1000, 0x100e2000, 0x100e3000
EXTRA = {CONFIGURE, UPDATE, RAW_BUILD, DEMOSAIC,
    '_ZN12CCameraImage14GetRedPositionERK15sRawDescriptionb',
    '_ZN23CRawImageProviderFilter7RawCropERK15sRawDescription',
    '_ZNK6CXRectdvEd', '_ZN7CXPointC1Eii',
    '_ZN11CSensorArea12GetPixelSizeE9eCCDTypesi',
    '_ZN12CImageSensor10PixelPitchE9eCCDTypesi',
    '_ZN12CImageSensor4CMosE9eCCDTypes',
    '_ZNK16CImageCorrection12LayersAffectE15eAdjustmentType',
    '_Z12ReverseOrder6CArrayIiLi3EiE',
    '_ZN7CXPointD1Ev', '_ZN15CNoiseInterface15AdditionalRgbNrEdddd9eCCDTypesiRd',
    '_ZN16CImageCorrection16SetUnsharpAmountEs',
    '_ZNK16CImageCorrection24GetApplyColorNoiseFilterEv',
    '_ZN8CGainMap20HasBlueCornerSupportEPK15sRawDescriptionb',
    '_ZNK15sRawDescription27GetTotalExtensionTubeLengthEv',
    '_ZNK15sRawDescription26GetAppliedVignettingAmountEv',
    '_ZNK16CImageCorrection40EffectiveVignetteAmountWithAppliedAmountEi',
    '_ZNK16CImageCorrection15GetMoireRemovalEv'}


def quantize(temperature, tint):
    """Independent piecewise Kelvin grid and signed tint rounding."""
    t = max(2000, min(50000, temperature))
    for low, high, step in ((2000, 8000, 50), (8000, 10000, 100),
                            (10000, 20000, 1000), (20000, 50000, 5000)):
        if t <= high:
            t = low + int(float(np.float32((t-low)/step)) + .5) * step
            break
    display_tint = max(-150., min(150., tint * -3000.))
    rounded = math.trunc(display_tint + (.5 if display_tint >= 0 else -.5))
    return t, rounded * (-1 / 3000) if rounded else 0.


class ImportRunner(GradationRunner):
    def __init__(self, elf, profile):
        self.raw_builder = False
        self.raw_events = []
        y.ALLOWED.update(EXTRA)
        y.ALLOWED.update(n for n in elf.func if any(k in n for k in (
            '30CHighlightReconstructionScalar', '28CHighlightReconstructionInfo')))
        super().__init__(elf)
        self.profile = profile
        self.call(y.DECODE, (self.obj, self.coder))
        self.u.mem_write(self.obj + 9, b'\1')
        self.defaults()
        for ptr, length in ((DESC, 0x408), (PARAMS, 0x1b0)):
            self.u.mem_write(ptr-16, b'\xa5'*16)
            self.u.mem_write(ptr+length, b'\xa5'*16)
        self.u.mem_write(SHARED_DESC, struct.pack('<2Q', DESC, 0))
        self.u.mem_write(EMPTY, b'\0'*16)
        self.import_guards = True
        self.frozen_profile = [(self.obj, bytes(self.u.mem_read(self.obj, 0x318)))]
        self.frozen_profile += [(p+16, bytes(self.u.mem_read(p+16, n))) for p, n in self.allocations]

    def check_guards(self):
        super().check_guards()
        if getattr(self, 'import_guards', False):
            for ptr, length in ((DESC, 0x408), (PARAMS, 0x1b0)):
                assert bytes(self.u.mem_read(ptr-16, 16)) == bytes(self.u.mem_read(ptr+length, 16)) == b'\xa5'*16

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0+i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        if address == 0x30002000 and self.getstr(reg(1)) in (
                ('NoBluecornerCorrection', 'nonr') if self.raw_builder else ('NoBluecornerCorrection',)):
            self.config_queries.append(self.getstr(reg(1)))
            cpu.reg_write(UC_ARM64_REG_X0, 1)
            finish(); return
        if self.raw_builder:
            if name.startswith('_ZN14CBlackStdCache11GetInstanceE'):
                cpu.reg_write(UC_ARM64_REG_X0, 0x100e7000); finish(); return
            if name.startswith('_ZN23CRawImageProviderFilter14DecodeCallbackE'):
                self.u.mem_write(reg(8), b'\0'*48); finish(); return
            if name.startswith('_ZN14CBlackStdCache13FetchBlackStdE'):
                cpu.reg_write(UC_ARM64_REG_D0, struct.unpack('<Q', struct.pack('<d', 1.))[0])
                finish(); return
            if name.startswith('_ZN15CImageProcessor13EmplaceFilterI'):
                kind = name.split('EmplaceFilterI', 1)[1].split('J', 1)[0]
                event = {'filter': kind}
                if kind == '36CHighlightReconstructionScalarFilter':
                    event['gains'] = self.doubles(reg(1), 3).tolist()
                    event['truncation'] = self.get(reg(2), 0, '<3H')
                self.raw_events.append(event)
                self.u.mem_write(reg(8), b'\0'*16); finish(); return
            if name == DEMOSAIC:
                self.raw_events.append({'filter': 'CDemosaicFilter', 'gains': [
                    struct.unpack('<d', struct.pack('<Q', cpu.reg_read(UC_ARM64_REG_D0+i)))[0]
                    for i in range(3)]})
                # The original constructor runs; only graph ownership is replaced.
            if name.startswith('_ZN15CImageProcessor9AddFilterE'):
                self.u.mem_write(reg(8), bytes(self.u.mem_read(reg(1), 16)))
                finish(); return
        if name == 'exp2':
            value = struct.unpack('<d', struct.pack('<Q', cpu.reg_read(UC_ARM64_REG_D0)))[0]
            cpu.reg_write(UC_ARM64_REG_D0, struct.unpack('<Q', struct.pack('<d', math.exp2(value)))[0])
            self.math_calls[name] += 1
            cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30)); return
        return super().hook(cpu, address, size, user)

    def put(self, ptr, off, fmt, *v):
        self.u.mem_write(ptr+off, struct.pack(fmt, *v))

    def get(self, ptr, off, fmt):
        return struct.unpack(fmt, bytes(self.u.mem_read(ptr+off, struct.calcsize(fmt))))

    def configure(self, gains, exposure=0., adjustments=(0, 0), present=(False, False, False)):
        assert np.isfinite(gains).all() and np.all(np.asarray(gains) > 0)
        self.u.mem_write(DESC, b'\0'*0x408)
        self.put(DESC, 0x28, '<3d', *gains)
        self.put(DESC, 0x344, '<2i', 22, 6)
        self.put(DESC, 0xb0, '<i', 1)
        self.put(DESC, 0x3c8, '<d', exposure)
        self.put(DESC, 0x3d0, '<?', present[0])
        self.put(DESC, 0x3d8, '<i', adjustments[0])
        self.put(DESC, 0x3dc, '<?', present[1])
        self.put(DESC, 0x3e0, '<i', adjustments[1])
        self.put(DESC, 0x3e4, '<?', present[2])
        before = bytes(self.u.mem_read(DESC, 0x408))
        self.call(CONFIGURE, (CORR, DESC, 0))
        assert before == bytes(self.u.mem_read(DESC, 0x408))
        assert self.get(CORR, 0x428, '<i') == (4,)
        assert self.get(CORR, 0x2b0, '<?') == (False,)
        assert self.get(CORR, 0x2a8, '<d') == (math.exp2(exposure if present[0] else 0.),)
        assert self.get(CORR, 0x324, '<i') == (adjustments[0] if present[1] else 0,)
        assert self.get(CORR, 0x32c, '<i') == (adjustments[1] if present[2] else 0,)
        for ch in (1, 2, 3):
            for n, value in (('11GetShadow14', 0), ('14GetHighlight14', 16383)):
                self.call('_ZNK16CImageCorrection'+n+'E10eColorType', (CORR, ch))
                assert self.u.reg_read(UC_ARM64_REG_X0) == value
        return self.get(CORR, 0x29c, '<i')[0], self.get(CORR, 0x2a0, '<d')[0]

    def process(self):
        self.u.mem_write(PARAMS, b'\0'*0x1b0)
        before = bytes(self.u.mem_read(CORR, 0x460))
        desc_before = bytes(self.u.mem_read(DESC, 0x408))
        self.call(UPDATE, (SHARED_DESC, PARAMS, 0, CORR, 0, EMPTY))
        assert before == bytes(self.u.mem_read(CORR, 0x460))
        assert desc_before == bytes(self.u.mem_read(DESC, 0x408))
        assert self.get(PARAMS, 0x70, '<d') == self.get(CORR, 0x2a8, '<d')
        assert self.get(PARAMS, 0xb8, '<3i') == (0, 1, 0)
        assert self.get(PARAMS, 0x1a8, '<i') == (4,)
        assert self.get(PARAMS, 0x1ad, '<?') == (False,)
        return self.doubles(PARAMS+0x58, 3)

    def graph(self):
        """Original builder with explicit noise/lens/graph-storage fixtures."""
        corr, params = 0x100e4000, 0x100e5000
        self.u.mem_write(corr, bytes(self.u.mem_read(CORR, 0x460)))
        self.u.mem_write(params, bytes(self.u.mem_read(PARAMS, 0x1b0)))
        self.put(corr, 0x99, '<?', False)  # Lens corrections disabled in fixture.
        self.put(params, 0xe0, '<i', 0)  # No moire-removal request.
        self.put(params, 0x190, '<?', False)  # No green-green correction.
        for off in (0x18, 0x40, 0x48, 0x50):
            self.put(DESC, off, '<d', 1.)
        self.put(DESC, 0x234, '<2i', 32, 32)
        self.put(DESC, 0x230, '<i', 1)
        self.put(DESC, 0x1e8, '<?', True)
        self.put(DESC, 0x1ec, '<4i', 0, 0, 32, 32)
        self.put(DESC, 0x398, '<i', 65535)
        self.put(EMPTY+0x100, 0, '<i', 65535)
        self.raw_events = []
        self.raw_builder = True
        self.call(RAW_BUILD, (0x100e6000, SHARED_DESC, 0, params, corr, EMPTY+0x100))
        self.raw_builder = False
        return self.raw_events

    def reconstruct(self, gains, pixels):
        obj = 0x100e8000
        self.u.mem_write(obj-16, b'\xa5'*16)
        self.u.mem_write(obj+0xc0, b'\xa5'*16)
        self.call(HR_CTOR, (obj, 0xffffffffffff), gains)
        frozen = bytes(self.u.mem_read(obj, 0xc0))
        output = []
        for p in pixels:
            self.call(HR_CONVERT, (obj,), p)
            output.append([struct.unpack('<d', struct.pack('<Q', self.u.reg_read(UC_ARM64_REG_D0+i)))[0]
                           for i in range(3)])
        assert bytes(self.u.mem_read(obj, 0xc0)) == frozen
        assert bytes(self.u.mem_read(obj-16, 16)) == bytes(self.u.mem_read(obj+0xc0, 16)) == b'\xa5'*16
        output = np.asarray(output)
        assert np.isfinite(output).all()
        assert output.min() >= -1e-12 and output.max() <= 1+1e-12
        return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    elf, profile = load_private(a.apk)
    r = ImportRunner(elf, profile)
    matrix = (np.array(profile['mf'])*.5+1).reshape(3, 3) @ np.diag(np.array(profile['vf'])*.5+1)
    inverse, table = np.linalg.inv(matrix), z.temperature_table(elf)
    temperatures = (1800, 2000, 2024, 2026, 2850, 4123, 5555, 7974, 7976,
                    8049, 8051, 9951, 10499, 10501, 19499, 19501, 22499, 22501, 50000)
    tints, scales = (-.0117, 0., .0021), (.125, 1., 3.7)
    parameter_errors, tint_errors, graph_errors = [], [], []
    scale_invariant_groups = 0
    for temp, tint in itertools.product(temperatures, tints):
        gains = z.temp_to_gain_oracle(temp, tint, inverse, table, elf)
        reference = None
        for scale in scales:
            scaled = gains*scale
            actual = r.configure(scaled)
            candidates, _ = z.gain_to_temp_oracle(scaled, matrix, table)
            possible = [quantize(*c) for c in candidates]
            errors = [abs(actual[1]-q[1]) for q in possible if q[0] == actual[0]]
            assert errors and min(errors) < 1e-14, (temp, tint, scale, actual, possible)
            tint_errors.append(min(errors))
            got = r.process()
            expected = z.temp_to_gain_oracle(*actual, inverse, table, elf)
            parameter_errors.extend(np.abs(got-expected))
            assert np.max(np.abs(got-expected)) < 1e-10
            state = (actual, got)
            if reference is None: reference = state
            else:
                assert reference[0] == state[0]
                assert np.array_equal(reference[1], state[1])
        scale_invariant_groups += 1
    print(f'Original import and process preparation: {len(tint_errors)} synthetic WB cases passed', flush=True)
    for tint in (-.08, -.06, .06, .08):
        gains = z.temp_to_gain_oracle(4000, tint, inverse, table, elf)
        actual = r.configure(gains)
        candidates, _ = z.gain_to_temp_oracle(gains, matrix, table)
        assert actual in [quantize(*c) for c in candidates]
        assert abs(actual[1]-math.copysign(.05, tint)) < 1e-15
    metadata_cases = 0
    for exposure, present in itertools.product((-2., .5, 2.), itertools.product((False, True), repeat=3)):
        gains = z.temp_to_gain_oracle(4123, .0021, inverse, table, elf)
        actual = r.configure(gains, exposure, (12, -7), present)
        got = r.process()
        expected = z.temp_to_gain_oracle(*actual, inverse, table, elf)
        assert np.max(np.abs(got-expected)) < 1e-10
        assert r.get(PARAMS, 0xf0, '<i') == (12 if present[1] else 0,)
        assert r.get(PARAMS, 0xf4, '<i') == (-7 if present[2] else 0,)
        metadata_cases += 1
    print(f'Exposure/adjustment metadata presence gates: {metadata_cases} cases passed', flush=True)
    sequences = []
    for temp, tint, scale, exposure in itertools.product((2850, 4123, 6500), (-.0021, .0021), (.125, 3.7), (-2., 2.)):
        gains = z.temp_to_gain_oracle(temp, tint, inverse, table, elf)*scale
        r.configure(gains, exposure, present=(True, False, False))
        got = r.process()
        events = r.graph()
        sequence = [e['filter'] for e in events]
        assert sequence == ['18COrientationFilter', '23CBayerFastInterpolation',
            '36CHighlightReconstructionScalarFilter', '18CMulti2BayerFilter', 'CDemosaicFilter']
        e = events[2]
        err = np.abs(np.asarray(e['gains'])-got/got.max())
        graph_errors.extend(err)
        assert err.max() < 1e-12 and e['truncation'] == (65535,)*3
        assert events[4]['gains'] == [1., 1., 1.]
        sequences.append(sequence)
    print(f'Original single-shot builder WB routing: {len(sequences)} fixture cases passed', flush=True)
    # Recalculate the original complete curves after actual SDR import (tool 4).
    r.configure(z.temp_to_gain_oracle(4123, .0021, inverse, table, elf))
    tables = r.calculate()
    identity = np.arange(65536, dtype=np.uint16)
    expected_tables = np.stack([identity, identity, *([default_curve()]*3)])
    assert np.array_equal(tables, expected_tables)
    print('All five native post-import gradation tables match Stage51 arithmetic exactly', flush=True)
    # This is a sensitivity diagnostic, not an independent reconstruction oracle.
    # Synthetic gain ratios are explicitly chosen; no private calibration output
    # or photographic samples are serialized.
    cube = np.stack(np.meshgrid(*[np.linspace(0, 1, 9)]*3, indexing='ij'), -1).reshape(-1, 3)
    ramp = np.repeat(np.linspace(0, 1, 257)[:, None], 3, 1)
    pixels = np.vstack([cube, ramp])
    highlight = []
    for synthetic_gains in ((1.8, 1., 1.4), (1., 2.2, 1.5), (1.4, 1.8, 1.)):
        g = np.asarray(synthetic_gains)
        output = r.reconstruct(g, pixels)
        scaled = r.reconstruct(g*3.7, pixels)
        assert np.max(np.abs(output-scaled)) < 1e-12
        assert np.array_equal(output[-1], np.ones(3))
        comparison = delta(output, pixels*(g/g.max()))
        assert comparison['max_abs_difference'] > .1
        highlight.append({'synthetic_gain_ratio': list(synthetic_gains),
            'pixels': len(pixels), 'simple_max_normalized_gain_difference_linear01': comparison,
            'gain_scale_invariance_max_abs': float(np.max(np.abs(output-scaled))),
            'sensor_white_maps_to_neutral_white': True})
    print('Original highlight reconstruction differs from simple WB on synthetic inputs', flush=True)
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    receipt = {
        'schema': 'hasselblad-stage52-native-import-wb-v1',
        'status': 'PASS_BOUNDED_IMPORT_AND_WB_ROUTING',
        'import': {'synthetic_wb_cases': len(tint_errors), 'scale_invariant_groups': scale_invariant_groups,
            'temperature_candidates_exact': True, 'maximum_tint_error': float(max(tint_errors)),
            'metadata_presence_cases': metadata_cases, 'tool_version_after_import': 4,
            'tint_clamp_cases': 4,
            'sdr_requested': True, 'gradation_endpoints_unchanged_all_cases': True,
            'process_gain_channels': len(parameter_errors), 'maximum_process_gain_error': float(max(parameter_errors)),
            'temperature_grid_kelvin': [[2000, 8000, 50], [8000, 10000, 100], [10000, 20000, 1000], [20000, 50000, 5000]],
            'tint_quantum': 1/3000, 'tint_limits': [-.05, .05]},
        'gradation_after_import': delta(tables, expected_tables),
        'raw_builder': {'cases': len(sequences), 'sequence': sequences[0],
            'highlight_reconstruction_receives_max_normalized_process_gains': True,
            'maximum_gain_argument_error': float(max(graph_errors)), 'demosaic_receives_unity_gains': True,
            'pixel_filters_executed_in_builder': False, 'original_demosaic_constructor_executed': True},
        'highlight_diagnostic': {'original_scalar_constructor_and_convert_executed': True,
            'independent_math_or_gpu_equivalence_validated': False, 'cases': highlight,
            'difference_is_accuracy_error': False, 'output_domain': 'linear sensor RGB before colour and film'},
        'fixtures': {'profile_cache': 'one already decoded private CCD22/IR6 profile',
            'process_preparation': 'null RAW file/image description, empty clarify map; NoBluecornerCorrection enabled',
            'raw_builder': 'nonr enabled; lens, moire, green-green disabled; black standard deviation 1; source scalar fields 1; 32x32 crop; truncation 65535',
            'graph_storage': 'EmplaceFilter records arguments and returns empty shared pointers; AddFilter ownership recorded',
            'other_services': 'host allocation/libm/configuration/file-name and shared ownership fixtures inherited from Stage51'},
        'source_apk_and_profile_unchanged': True, 'scene_pixels_used': False,
        'scene_specific_tuning': False, 'phone_sensor_adaptation_validated': False,
        'android_live_graph_or_gpu_tested': False, 'capture_renderer_changed': False,
        'new_apk_built': False, 'full_phocus_equivalence': False,
        'next_boundary': 'independent CPU/GPU reconstruction of native highlight processing and its exposure/phone-sensor domain mapping'}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(receipt, indent=2)+'\n')
    print(receipt['status'], flush=True)


if __name__ == '__main__':
    main()
