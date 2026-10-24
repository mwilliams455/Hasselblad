#!/usr/bin/env python3
"""Bounded native SDR graph selection and private original GLES kernels.

No live Android presentation or photographic equivalence is claimed. Source
shaders and recovered matrices remain private inputs; public output is aggregate.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / x) for x in ('phocus_output_stage49', 'phocus_boundaries_stage48')]
from audit_output49 import OutputRunner, load_private, read_profile, decode, delta, y
from audit_boundaries48 import standard_output
from prepare_preview42 import display, srgb
from unicorn.arm64_const import *
from gles50 import GLES

BUILD = '_ZN18CameraImageAndroid14AddHNCSFiltersEP15CImageProcessorNSt6__ndk110shared_ptrIK15sRawDescriptionEEP14sProcessParamsP16CImageCorrectionNS3_IK17CCalculatedCurvesEEbbfbbb'
INIT = '_ZN24CColorSpaceConvertFilter29InitBasicColorSpaceParametersE11eColorSpace16eWhitePointValue17eTransferFunction'
APPLY = '_ZNK24CColorSpaceConvertFilter25ApplyColorSpaceConversionERdS0_S0_'
SUPPORT = '_ZNK10CCustomCMM11SupportsGpuEv'
GPU_CMM = '_ZNK10CCustomCMM15FilterResultGpuER19CGpuPipelineManagerRK6CXRectS4_'
CHANNELS = ('_ZNK10CCustomCMM10ChannelsInEv', '_ZNK10CCustomCMM11ChannelsOutEv')
TEXTURE = '_Z23GetOpenGLInternalFormat17OpenGLTextureType'
CTOR_COLOUR = '_ZN22CColorCorrectAllFilterC1EPK15sRawDescriptionP16CImageCorrectionb'
CTOR_FILM = '_ZN16CFilmCurveFilterC1EPK15sRawDescriptionP16CImageCorrection'
CTOR_OUTPUT = '_ZN24CColorSpaceConvertFilterC1Ev'
y.ALLOWED.update({BUILD, INIT, APPLY, SUPPORT, GPU_CMM, TEXTURE, *CHANNELS,
    '_ZNK16CImageCorrection24EffectiveSharpnessAmountEdi',
    '_ZN24CColorSpaceConvertFilter14UpdateMatricesEv',
    '_ZN24CColorSpaceConvertFilter32ComputeChromaticAdaptationMatrixEv',
    '_ZNK24CColorSpaceConvertFilter21ApplyTransferFunctionERdS0_S0_',
    'stage50_output_initializer'})


class Runner(OutputRunner):
    def __init__(self, elf):
        super().__init__(elf)
        self.sequence, self.parameters, self.objects = [], [], {}
        self.flags = (0, 0)
        self.record_builder = False
        self.record_gpu = False
        self.uniforms, self.texture_requests, self.dispatches = {}, [], []

    def hook(self, cpu, address, size, user):
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0 + i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        # Original virtual channel-count implementations, not synthetic returns.
        for name in CHANNELS:
            start, length = self.e.func[name]
            if address == start:
                if (start, start + length) not in self.active:
                    self.active.append((start, start + length))
                self.called.add(name)
        # Logging only; no rendering/calculation is performed by these wrappers.
        if address in (0x36fa3fc, 0x3336fd8): finish(); return
        if self.record_gpu:
            name = self.e.plt.get(address, '')
            if name.startswith('_ZN19CGpuPipelineManager10GetHandlerE'):
                cpu.reg_write(UC_ARM64_REG_X0, 0x100c0000); finish(); return
            if name.startswith('_ZN10GpuHandler18GetTextureInFormatE'):
                assert reg(2) == 1
                self.texture_requests.append(struct.unpack('<i', bytes(self.u.mem_read(reg(1), 4)))[0])
                self.u.mem_write(reg(8), b'\0' * 48); finish(); return
            if name.startswith('_ZN10GpuHandler17MakeOutputTextureE'):
                self.texture_requests.append(reg(1))
                self.u.mem_write(reg(8), b'\0' * 48)
                self.u.mem_write(reg(8) + 20, struct.pack('<2i', reg(2), reg(3)))
                finish(); return
            if name.startswith('_ZN10GpuHandler7ComputeI'):
                self.compute_name = bytes(self.u.mem_read(reg(1), 128)).split(b'\0', 1)[0].decode()
                self.u.mem_write(reg(8), b'\0' * 48); finish(); return
            if name.startswith('_ZN11ComputeTask15SetUniformMat3F'):
                self.uniforms[self.getstr(reg(1))] = self.doubles(reg(2), 9).reshape(3, 3)
                finish(); return
            if name.startswith('_ZN11ComputeTask10SetUniformE'):
                key = self.getstr(reg(1))
                if name.endswith('f'):
                    value = struct.unpack('<f', struct.pack('<I', cpu.reg_read(UC_ARM64_REG_S0)))[0]
                elif name.endswith('i'): value = reg(2)
                else:
                    lo, hi, end = struct.unpack('<3Q', bytes(self.u.mem_read(reg(2), 24)))
                    assert hi - lo == 8 and end >= hi
                    value = tuple(np.frombuffer(bytes(self.u.mem_read(lo, 8)), dtype='<i4'))
                self.uniforms[key] = value; finish(); return
            if name.startswith('_ZN11ComputeTask8DispatchE'):
                self.dispatches.append([reg(1), reg(2)]); finish(); return
            if name.startswith(('_ZN10GpuHandler16SetOutputTextureE', '_ZN11ComputeTaskD1E', '_ZN13OpenGLTextureD1E')):
                finish(); return
        if self.record_builder:
            if address == self.e.func[BUILD][0]:
                self.u.mem_write(cpu.reg_read(UC_ARM64_REG_SP), struct.pack('<2Q', *self.flags))
            # Ownership fixture keeps recorded filter objects alive.
            if address in (0x3790b20, 0x3790b50):
                cpu.reg_write(UC_ARM64_REG_X0, 1); finish(); return
            name = self.e.plt.get(address, '')
            if name.startswith('_ZN15CImageProcessor13EmplaceFilterI'):
                self.sequence.append(name.split('EmplaceFilterI', 1)[1].split('J', 1)[0])
                self.u.mem_write(reg(8), struct.pack('<2Q', 0, 0)); finish(); return
            if name in (CTOR_COLOUR, CTOR_FILM, CTOR_OUTPUT):
                self.objects[reg(0)] = {CTOR_COLOUR: 'ColorCorrectAll', CTOR_FILM: 'FilmCurve', CTOR_OUTPUT: 'ColorSpaceConvert'}[name]
                finish(); return
            if name == '_ZN22CColorCorrectAllFilter16UpdateParametersEv':
                cpu.reg_write(UC_ARM64_REG_X0, 1); finish(); return
            if name.startswith('_ZN15CImageProcessor9AddFilterE'):
                obj, _ = struct.unpack('<2Q', bytes(self.u.mem_read(reg(1), 16)))
                self.sequence.append(self.objects[obj])
                self.u.mem_write(reg(8), struct.pack('<2Q', obj, 0)); finish(); return
            if name == INIT:
                self.parameters.append([reg(1), reg(2), reg(3)]); finish(); return
        return super().hook(cpu, address, size, user)

    def graph_cases(self):
        desc, shared, params, corr, curves, processor = [0x100a0000 + i * 0x1000 for i in range(6)]
        self.u.mem_write(shared, struct.pack('<2Q', desc, 0))
        self.u.mem_write(corr + 0x428, struct.pack('<i', 2))  # SDR tool fixture
        self.u.mem_write(corr + 0x91, b'\1')
        self.record_builder = True
        results = []
        for space in (0, 1):
            self.u.mem_write(corr + 0xe4, struct.pack('<i', space))
            for output_flag, skip_output in ((0, 0), (1, 0), (0, 1)):
                self.flags = output_flag, skip_output
                self.sequence, self.parameters = [], []
                before = bytes(self.u.mem_read(corr, 0x430))
                self.call(BUILD, (processor, shared, params, corr, curves, 0, 0, 0))
                expected = [] if skip_output else [[2, 0, 4] if output_flag else [1, 0, 3]]
                sequence = ['ColorCorrectAll', 'FilmCurve', '16CGradationFilter']
                if not skip_output: sequence.append('ColorSpaceConvert')
                assert self.parameters == expected and self.sequence == sequence
                assert bytes(self.u.mem_read(corr, 0x430)) == before
                results.append({'working_space': space, 'output_flag_fixture': output_flag,
                    'skip_output_fixture': skip_output, 'sequence': self.sequence.copy(),
                    'output_parameters': self.parameters.copy()})
        self.record_builder = False
        return results

    def output_parameters(self, space, transfer):
        obj = 0x100b0000
        self.u.mem_write(obj, b'\0' * 0x140)
        self.call(INIT, (obj, space, 0, transfer))
        source = self.doubles(obj + 0x48, 9).reshape(3, 3)
        target = self.doubles(obj + 0xa0, 9).reshape(3, 3)
        gamma = struct.unpack('<f', bytes(self.u.mem_read(obj + 0x13c, 4)))[0]
        return obj, {'uSrcToXYZMatrix': source, 'uXYZToDstMatrix': target,
            'uChromaOption': 0, 'uProcessHdr': 0, 'uHdrMaxGain': 1.,
            'uHdrLimitGain': 1., 'uGammaEncode': gamma, 'uTargetTF': transfer}

    def cpu_output(self, obj, pixels):
        out = []
        for pixel in np.asarray(pixels).reshape(-1, 3):
            self.u.mem_write(0x100b1000, np.asarray(pixel, dtype='<f8').tobytes())
            self.call(APPLY, (obj, 0x100b1000, 0x100b1008, 0x100b1010))
            out.append(self.doubles(0x100b1000, 3))
        return np.array(out).reshape(pixels.shape)

    def cmm_gpu_parameters(self, obj):
        rect = 0x100c1000
        self.u.mem_write(rect, b'\0' * 32)
        self.u.mem_write(rect + 8, b'\1')
        self.u.mem_write(rect + 12, struct.pack('<4i', 0, 0, 17, 1))
        self.uniforms, self.texture_requests, self.dispatches = {}, [], []
        self.record_gpu = True
        self.call(GPU_CMM, (obj, 0x100c0000, rect, rect))
        self.record_gpu = False
        assert self.texture_requests == [8, 8] and self.dispatches == [[17, 1]], (self.texture_requests, self.dispatches)
        return dict(self.uniforms)


def shader(elf, name):
    rows = [s for i, s in enumerate(elf.sym) if elf.name(i) == name]
    assert len(rows) == 1
    ptr = elf.relocation(int(rows[0]['addr']))[0]
    return elf.read(ptr, 32768).split(b'\0', 1)[0].decode()


def encoded8(rgb):
    return np.floor(np.clip(rgb, 0, 1) * 255 + .5).astype(np.uint8)


def cmm_expected(rgb, matrix, transfer):
    v = decode(rgb.astype(np.float16).astype(np.float32), transfer).astype(float) @ matrix.T
    v = v.astype(np.float32).astype(float)
    return np.where(v <= .0031308, v * 12.92, 1.055 * np.maximum(v, 0) ** (1 / 2.4) - .055)


def space_expected(rgb, uniforms, gamma):
    v = np.maximum(rgb.astype(np.float16).astype(float), 0) ** gamma
    v = v @ np.asarray(uniforms['uSrcToXYZMatrix']).T
    v = v @ np.asarray(uniforms['uXYZToDstMatrix']).T
    if uniforms['uTargetTF'] == 4: v = np.maximum(v, 0) ** (1 / 2.19921875)
    elif uniforms['uTargetTF'] == 1: return np.where(v <= .0031308, v * 12.92, 1.055 * np.maximum(v, 0) ** (1 / 2.4) - .055)
    return v


def main():
    parser = argparse.ArgumentParser()
    for name in ('apk', 'profile', 'safe-receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--room-java', type=Path)
    a = parser.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    elf, _ = load_private(a.apk)
    elf.func['stage50_output_initializer'] = (0x36fbd94, 0x4c)
    r = Runner(elf)
    graphs = r.graph_cases()
    r.call('stage50_output_initializer')
    formats = {}
    for code in (7, 8):
        r.call(TEXTURE, (code,)); formats[str(code)] = int(r.u.reg_read(UC_ARM64_REG_X0))
        assert formats[str(code)] == 0x881a  # GL_RGBA16F, not an sRGB format
    print('Original SDR graph selection and RGBA16F formats verified', flush=True)
    colours = np.stack(np.meshgrid(*[np.linspace(0, 1, 17)] * 3, indexing='ij'), -1).reshape(-1, 3)
    neutrals = np.repeat(np.linspace(0, 1, 513)[:, None], 3, axis=1)
    pixels = np.vstack([colours, neutrals]).astype(np.float32)
    cmm_shader = shader(elf, 'customCmm_fragmentShaderSource')
    space_shader = shader(elf, 'colorspaceconvert_fragmentShaderSource')
    g = GLES()
    cmm_results = []
    for source in (0, 1):
        converter = r.converter(source)
        r.call(SUPPORT, (converter,)); supported = bool(r.u.reg_read(UC_ARM64_REG_X0))
        assert supported
        matrix = r.doubles(converter + 0x20, 9).reshape(3, 3)
        transfer = struct.unpack('<di4xd', bytes(r.u.mem_read(converter + 8, 24)))
        uniforms = r.cmm_gpu_parameters(converter)
        assert np.array_equal(uniforms['uMat'], matrix)
        assert uniforms['uTransferIn'] == transfer[1] and uniforms['uTransferOut'] == 2
        assert uniforms['uGammaIn'] == transfer[2] and uniforms['uScaleIn'] == uniforms['uScaleOut'] == 1
        rendered = g.render(cmm_shader, pixels, uniforms)
        expected = cmm_expected(pixels, matrix, transfer)
        error = delta(rendered, expected)
        difference8 = delta(encoded8(rendered), encoded8(expected))
        if source == 0: assert error['max_abs_difference'] < .004 and difference8['max_abs_difference'] <= 1
        else: assert difference8['mean_abs_difference'] > 10
        cmm_results.append({'source_special_profile': source, 'destination_special_profile': 2,
            'native_SupportsGpu': supported, 'native_transfer_in_code': transfer[1],
            'native_GPU_parameter_body_executed': True, 'compute_key': r.compute_name,
            'pixels': len(pixels), 'float_difference_from_CPU_math': error,
            'display_code_difference': difference8, 'matches_CPU_transfer_semantics': source == 0})
    print('Original CMM shader executed; L* mismatch reproduced', flush=True)
    cases = []
    for space, transfer in ((1, 3), (2, 4), (0, 1)):
        obj, uniforms = r.output_parameters(space, transfer)
        selected = transfer != 1
        rendered = g.render(space_shader, pixels, uniforms)
        # Original shader's sRGB enum is a passthrough, unlike its CPU method.
        gpu_uniforms = dict(uniforms)
        if transfer == 1: gpu_uniforms['uTargetTF'] = 3
        predicted = space_expected(pixels, gpu_uniforms, 2.2)
        shader_check = delta(rendered, predicted)
        assert shader_check['max_abs_difference'] < .004
        index = np.linspace(0, len(pixels) - 1, 256).astype(int)
        quantized = pixels[index].astype(np.float16).astype(float)
        actual_cpu = r.cpu_output(obj, quantized)
        cpu_prediction = space_expected(pixels[index], uniforms, 2.19921875)
        # The sRGB diagnostic uses the native float/powf branch. The selected
        # SDR linear/power branches operate in double precision.
        cpu_tolerance = 5e-7 if transfer == 1 else 1e-12
        cpu_check = y.check(actual_cpu, cpu_prediction, cpu_tolerance)
        cpu_gpu = delta(encoded8(rendered[index]), encoded8(actual_cpu))
        if selected: assert cpu_gpu['max_abs_difference'] <= 1
        else: assert cpu_gpu['mean_abs_difference'] > 10
        cases.append({'target_space_code': space, 'transfer_code': transfer,
            'selected_in_tested_SDR_builder': selected, 'shader_math_check': shader_check,
            'native_CPU_sample_check': cpu_check, 'CPU_GPU_quantized_difference': cpu_gpu})
    # A labelled diagnostic adapter after the native linear-P3 boundary. This is
    # not a claim to have executed Android's final presentation/compositor.
    _, linear_p3 = r.output_parameters(1, 3)
    p3_to_xyz = np.linalg.inv(linear_p3['uXYZToDstMatrix'])
    x = standard_output()
    _, _, values, _, _ = read_profile(a.profile)
    room_results = {}
    if a.room_java:
        for label in ('curve0_3050', 'curve0_4000', 'curve1_4000'):
            codes = np.fromfile(a.room_java / (label + '_rgb16.bin'), dtype='<u2').reshape(768, 1024, 3)
            current = display(codes, values[28:37].reshape(3, 3), values[37])
            native_kernel = g.render(space_shader, codes.astype(np.float32) / 65535, linear_p3)
            diagnostic = srgb(native_kernel.astype(float) @ p3_to_xyz.T @ x.T)
            room_results[label] = delta(diagnostic, current)
        print('Three whole-room GPU output diagnostics completed', flush=True)
    info = g.info; g.close()
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    result = {'schema': 'hasselblad-stage50-sdr-gpu-boundary-v1',
        'status': 'PASS_BOUNDED_AUDIT_WITH_NATIVE_GPU_MISMATCHES',
        'SDR_graph_cases': graphs, 'OpenGL_internal_formats': formats,
        'native_graph_body_executed': True,
        'filter_construction_update_and_reference_ownership_are_recording_fixtures': True,
        'native_output_initializer_and_matrix_preparation_executed': True,
        'original_fragment_shaders_executed_unchanged': True,
        'CMM_GPU_task_and_texture_lifecycle_are_recording_fixtures': True,
        'CMM_shader_cases': cmm_results, 'HNCS_output_shader_cases': cases,
        'linear_P3_then_explicit_sRGB_diagnostic_vs_current': room_results,
        'GLES_environment': info, 'phone_GPU_tested': False,
        'live_app_flag_values_observed': False, 'final_Android_surface_and_compositor_verified': False,
        'phone_sensor_adaptation_validated': False, 'capture_renderer_changed': False,
        'full_phocus_equivalence': False, 'source_APK_unchanged': True,
        'native_functions_executed': sorted(r.called),
        'bounds': 'SDR tool2 with optional edits disabled and explicit output flags; two shader kernels on software GLES using RGBA16F textures; host math/allocation and logging fixtures. No complete RAW pipeline or live Android presentation.'}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'CMM_display_differences': [v['display_code_difference'] for v in cmm_results],
                      'room_diagnostics': room_results}), flush=True)


if __name__ == '__main__': main()
