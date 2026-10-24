#!/usr/bin/env python3
"""Replay native colour routes and the built-in SDR output converter.

Private APK/profile data and optional photograph samples stay in --out.
Only aggregate evidence is written to --safe-receipt. No look is fitted.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / x) for x in ('phocus_illuminant_stage45', 'phocus_room_stage46')]
import audit_parameters45 as a45
from analyse_room46 import read_profile
from prepare_preview42 import load_private, y, display
from unicorn.arm64_const import UC_ARM64_REG_D0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

PRIMARIES = '_Z19PrimariesForProfile15SpecialProfiles'
TRANSFER = '_Z19TransferFromSpecial15SpecialProfiles'
WHITE = '_Z20WhitePointForProfile15SpecialProfiles'
MATRIX = '_ZN10CCustomCMM18GetMatrixTransformE15SpecialProfilesS0_'
CREATE = '_ZN10CCustomCMM9CreateCCME15SpecialProfilesS0_'
SHORT = '_ZNK10CCustomCMM7ConvertE13CImageViewAnyIKtES0_ItE'
FLOAT = '_ZNK10CCustomCMM7ConvertE13CImageViewAnyIKfES0_IfE'
y.ALLOWED.update({PRIMARIES, TRANSFER, WHITE, MATRIX, CREATE, SHORT, FLOAT,
    '_Z21ConvertColorPrimaries6CArrayIS_IdLi2EdELi3ES0_ES_IdLi3EdES1_S2_',
    '_ZNK9Matrix3x3mlE6CArrayIdLi3E23Matrix3x1InitializationE',
    '_ZN10CCustomCMMC1E18TransferDefinition9Matrix3x3S0_',
    '_ZNK10CCustomCMM13ConvertByLineItEEv13CImageViewAnyIKT_ES1_IS2_E',
    '_Z9LinearizeILi3EEv10CImageViewIKfXT_EES0_IfXT_EE18TransferDefinition',
    '_Z6EncodeILi3EEv10CImageViewIfXT_EE18TransferDefinition',
    '_ZN18TransferDefinition12linear2sRgbFEf',
    '_ZN18TransferDefinition13lstar2linearFEf'})


class OutputRunner(y.NativePipeline):
    """Original CMM, with the existing host allocation/libm fixtures."""
    def hook(self, cpu, address, size, user):
        # The original uint16 wrapper dispatches its float converter virtually.
        if address == self.e.func[FLOAT][0]:
            start, length = self.e.func[FLOAT]
            if (start, start + length) not in self.active:
                self.active.append((start, start + length))
            self.called.add(FLOAT)
        if self.e.plt.get(address) == 'pow':
            def value(i):
                return struct.unpack('<d', struct.pack('<Q', cpu.reg_read(UC_ARM64_REG_D0 + i)))[0]
            try:
                result = math.pow(value(0), value(1))
            except ValueError:
                # The sRGB primitive evaluates its unused power branch even for
                # negative inputs. libm returns NaN; the linear branch wins.
                result = float('nan')
            cpu.reg_write(UC_ARM64_REG_D0, struct.unpack('<Q', struct.pack('<d', result))[0])
            self.math_calls['pow'] += 1
            cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
            return
        return super().hook(cpu, address, size, user)

    def converter(self, source):
        self.call(CREATE, (source, 2))
        ptr = struct.unpack('<Q', bytes(self.u.mem_read(0x10002000, 8)))[0]
        assert ptr
        return ptr

    def convert(self, obj, pixels):
        pixels = np.ascontiguousarray(pixels, dtype='<u2').reshape(-1, 3)
        assert pixels.nbytes < 0x80000
        inp, out, iv, ov = 0x10100000, 0x10200000, 0x10005000, 0x10006000
        source = pixels.tobytes()
        self.u.mem_write(inp - 16, b'\xa5' * 16 + source + b'\xa5' * 16)
        self.u.mem_write(out - 16, b'\xa5' * 16 + b'\xcc' * len(source) + b'\xa5' * 16)
        for ptr, buf in ((iv, inp), (ov, out)):
            self.u.mem_write(ptr, struct.pack('<Q4i', buf, len(pixels), 1, len(pixels) * 3, 3))
        before = bytes(self.u.mem_read(obj, 0x80))
        self.call(SHORT, (obj, iv, ov))
        assert bytes(self.u.mem_read(obj, 0x80)) == before
        assert bytes(self.u.mem_read(inp, len(source))) == source
        for ptr in (inp, out):
            assert bytes(self.u.mem_read(ptr - 16, 16)) == bytes(self.u.mem_read(ptr + len(source), 16)) == b'\xa5' * 16
        return np.frombuffer(bytes(self.u.mem_read(out, len(source))), dtype='<u2').copy().reshape(-1, 3)


def delta(actual, expected):
    d = np.abs(actual.astype(float) - expected.astype(float))
    return {'channels': d.size, 'max_abs_difference': float(d.max()),
            'mean_abs_difference': float(d.mean()), 'exact_channels': int(np.count_nonzero(d == 0))}


def decode(values, transfer):
    gain, code, exponent = transfer
    assert gain == 1 and code in (1, 5)
    if code == 1:
        return (values.astype(float) ** exponent).astype(np.float32)
    v = values.astype(float)
    return np.where(v > .08, ((v + .16) / 1.16) ** 3, v * 100 / (24389 / 27)).astype(np.float32)


def cmm_oracle(pixels, matrix, transfer):
    values = np.asarray(pixels, np.float32) / np.float32(65535)
    linear = decode(values, transfer).astype(float) @ matrix.T
    # Original converter stores the matrix output as float before encoding.
    linear = linear.astype(np.float32).astype(float)
    encoded = np.where(linear <= .0031308, linear * 12.92,
                       1.055 * np.maximum(linear, 0) ** (1 / 2.4) - .055).astype(np.float32)
    scaled = encoded * np.float32(65535)
    return np.clip(np.floor(scaled.astype(float) + .5), 0, 65535).astype(np.uint16)


def independent_matrix(r, source, target):
    def definition(code):
        r.call(PRIMARIES, (code,))
        assert r.u.mem_read(0x10002030, 1)[0]
        xy = r.doubles(0x10002000, 6).reshape(3, 2)
        r.call(WHITE, (code,))
        white = np.array([struct.unpack('<d', struct.pack('<Q', r.u.reg_read(UC_ARM64_REG_D0 + i)))[0] for i in range(3)])
        prim = np.vstack([xy[:, 0] / xy[:, 1], np.ones(3), (1 - xy.sum(1)) / xy[:, 1]])
        return prim @ np.diag(np.linalg.solve(prim, white)), white
    src, sw = definition(source)
    dst, dw = definition(target)
    bradford = np.array([[.8951, .2664, -.1614], [-.7502, 1.7135, .0367], [.0389, -.0685, 1.0296]])
    adaptation = np.linalg.solve(bradford, np.diag((bradford @ dw) / (bradford @ sw)) @ bradford)
    return np.linalg.solve(dst, adaptation @ src)


def android_routes(elf, profile):
    for name, pair in y.INITIALIZERS.items(): elf.func[name] = pair
    r = a45.ParameterRunner(elf)
    r.profile = profile
    r.call(y.DECODE, (r.obj, r.coder)); r.u.mem_write(r.obj + 9, b'\1')
    for name in y.INITIALIZERS: r.call(name)
    r.call(y.GM_CTOR, (y.GM, 1, 1))
    for ptr, offset, fmt, values in (
        (y.RAW, 8, '<Q', (y.GM,)), (y.RAW, 0xb0, '<Q', (y.CC,)),
        (y.RAW, 0x250, '<3i', (22, 6, 0)), (y.RAW, 0x228, '<3d', (1., 1., 1.)),
        (y.RAW, 0x248, '<d', (1.,)),
        (a45.FILTER, 0x68, '<2Q', (a45.z.DESCRIPTION, a45.z.CORRECTION)),
        (a45.FILM_FILTER, 0x48, '<2Q', (a45.z.DESCRIPTION, a45.z.CORRECTION)),
        (a45.z.DESCRIPTION, 0x344, '<2i', (22, 6)),
        (a45.z.DESCRIPTION, 0x18, '<d', (1.,)),
        (a45.z.DESCRIPTION, 0x28, '<3d', (1., 1., 1.)),
        (a45.z.DESCRIPTION, 0x40, '<d', (1.,)),
        (a45.z.DESCRIPTION, 0x50, '<d', (1.,)),
        (a45.z.CORRECTION, 0x91, '<B', (1,)),
        (a45.z.CORRECTION, 0x428, '<i', (2,))):
        r.put(ptr, offset, fmt, *values)
    film_buffer = r.alloc(65536 * 4)
    r.put(a45.FILM_FILTER, 0x58, '<3Q', film_buffer, film_buffer + 65536 * 4, film_buffer + 65536 * 4)
    B, A, W = y.matrix_constants(elf)
    cases = []
    for temperature in (2850, 4000, 5550):
        for space in range(6):
            for film in (0, 1):
                for ptr, off, fmt, values in (
                    (a45.z.CORRECTION, 0x29c, '<i', (temperature,)),
                    (a45.z.CORRECTION, 0x2cc, '<i', (film,)),
                    (a45.z.CORRECTION, 0xe4, '<i', (space,)),
                    (y.GM, 4, '<i', (film,)), (y.RAW, 0x20, '<i', (space,)),
                    (y.RAW, 0x1f0, '<2d', (float(temperature), 1.))):
                    r.put(ptr, off, fmt, *values)
                r.call(y.RAW_INIT, (y.RAW,))
                assert struct.unpack('<2i', bytes(r.u.mem_read(y.GM, 8))) == (2 if space else 1, film)
                frozen = [(p, bytes(r.u.mem_read(p, n))) for p, n in (
                    (a45.z.DESCRIPTION, 0x350), (a45.z.CORRECTION, 0x430), (y.CC, 0x298))]
                r.call(a45.UPDATE, (a45.FILTER,))
                ints, doubles = r.factory_calls[-1]
                assert ints == [22, 6, film, 0, 0, space, 0]
                assert np.array_equal(doubles, [temperature, 1., 1.])
                first = B @ A @ y.matrix_oracle(profile, temperature).reshape(3, 3)
                second = W[space] @ np.linalg.inv(B); second[:, 1:] /= 32
                m1 = y.check(np.stack([r.vector(o, 4) for o in (0x78, 0x90, 0xa8)]), np.c_[first, np.zeros(3)].astype(np.float32), 0)
                m2 = y.check(np.stack([r.vector(o, 4) for o in (0xc0, 0xd8, 0xf0)]), np.c_[second, np.zeros(3)].astype(np.float32), 0)
                grid = y.lut_oracle(profile, temperature, False)
                if space: grid = y.expand_oracle(grid)
                height, width = grid.shape[:2]
                ptr, buf, w, h, pitch, channels = struct.unpack('<2Q4i', bytes(r.u.mem_read(a45.FILTER + 0x48, 32)))
                assert ptr == buf and (w, h, pitch, channels) == (width, height, width * 4, 4)
                lut = y.check(r.floats(ptr, height * pitch).reshape(height, width, 4),
                              np.concatenate([grid, np.zeros_like(grid)], axis=2).astype(np.float32), 0)
                y.check(r.vector(0x120, 2), np.array([-25, -39] if space else [-20, -32], np.float32), 0)
                y.check(r.vector(0x138, 2), np.array([width - 1, height - 1], np.float32), 0)
                r.call(a45.FILM_UPDATE, (a45.FILM_FILTER,))
                curve = y.curve_oracle(elf, film, 2 if space else 1) * np.float32(1 / 65535)
                tone = y.check(r.floats(film_buffer, 65536), curve, 0)
                if film == 0:
                    previous_curve = r.floats(film_buffer, 65536)
                elif space:
                    assert np.array_equal(previous_curve, r.floats(film_buffer, 65536))
                assert all(bytes(r.u.mem_read(p, len(v))) == v for p, v in frozen)
                cases.append({'temperature': temperature, 'space': space, 'film': film,
                    'companding_code': 2 if space else 1, 'grid_width': width, 'grid_height': height,
                    'input_matrix': m1, 'output_matrix': m2, 'LUT': lut, 'film_curve': tone,
                    'factory_arguments_exact': True, 'source_unchanged': True})
        print(f'Android route parameters verified at {temperature} K', flush=True)
    r.check_guards()
    return {'cases': cases, 'factory_returns_prepared_native_RAW_object': True,
            'curve0_and_curve1_exact_alias_in_nonzero_spaces': True,
            'lens_reduction_and_destruction_are_fixtures': True,
            'original_functions_executed': sorted(r.called), 'GPU_dispatched': False}


def main():
    p = argparse.ArgumentParser()
    for name in ('apk', 'profile', 'out', 'safe-receipt'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--room-java', type=Path)
    a = p.parse_args(); assert __debug__
    a.out.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    elf, profile = load_private(a.apk)
    routes = android_routes(elf, profile)
    r = OutputRunner(elf)
    _, _, v, _, _ = read_profile(a.profile)
    cube = np.stack(np.meshgrid(*[np.linspace(0, 65535, 17)] * 3, indexing='ij'), -1).reshape(-1, 3)
    ramp = np.repeat(np.linspace(0, 65535, 513)[:, None], 3, axis=1)
    pixels = np.rint(np.vstack([cube, ramp])).astype(np.uint16)
    results, matrices, transfers, converters = [], [], [], []
    for code in (0, 1):
        r.call(MATRIX, (code, 2)); assert r.u.mem_read(0x10002048, 1)[0]
        matrix = r.doubles(0x10002000, 9).reshape(3, 3)
        matrix_check = y.check(matrix, independent_matrix(r, code, 2), 1e-12)
        r.call(TRANSFER, (code,))
        transfer = struct.unpack('<di4xd', bytes(r.u.mem_read(0x10002000, 24)))
        converter = r.converter(code)
        actual = r.convert(converter, pixels)
        expected = cmm_oracle(pixels, matrix, transfer)
        check = y.check(actual, expected, 1)
        results.append({'source_special_profile': code, 'destination_special_profile': 2,
                        'pixels': len(pixels), 'independent_matrix_composition': matrix_check,
                        'independent_uint16_conversion': check})
        matrices.append(matrix); transfers.append(transfer); converters.append(converter)
    assert transfers[0] == (1., 1, v[37]) and transfers[1] == (1., 5, 1.)
    old = display(pixels, v[28:37].reshape(3, 3), v[37])
    actual = r.convert(converters[0], pixels)
    native8 = np.floor(actual.astype(float) * 255 / 65535 + .5).astype(np.uint8)
    comparisons = {'synthetic_encoded_cube_and_neutrals': delta(native8, old)}
    if a.room_java:
        for label in ('curve0_3050', 'curve0_4000', 'curve1_4000'):
            codes = np.fromfile(a.room_java / (label + '_rgb16.bin'), dtype='<u2').reshape(-1, 3)
            current = display(codes, v[28:37].reshape(3, 3), v[37])
            predicted = cmm_oracle(codes, matrices[0], transfers[0])
            index = np.linspace(0, len(codes) - 1, 4096).astype(int)
            replay = r.convert(converters[0], codes[index])
            check = y.check(replay, predicted[index], 1)
            output8 = np.floor(predicted.astype(float) * 255 / 65535 + .5).astype(np.uint8)
            comparisons[label] = {'whole_frame_difference': delta(output8, current),
                                  'native_replay_sample': check, 'sample_pixels': len(index)}
    B, A, W = y.matrix_constants(elf)
    np.savez(a.out / 'Stage49_Private_Output_Reference.npz', basis=B, xyz_to_internal=A,
             working_transforms=np.array(W), cmm_to_srgb=np.array(matrices),
             transfer_definitions=np.array(transfers), raw_input_normalizer=np.array(65535))
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    result = {'schema': 'hasselblad-stage49-native-output-v1', 'status': 'PASS_BOUNDED_NATIVE_OUTPUT',
        'android_parameters': routes, 'native_output': results, 'current_adapter_comparison': comparisons,
        'input_decode_exponent_matches_current_profile': True,
        'native_uint16_normalizer': 65535, 'current_adapter_normalizer': 65536,
        'native_output_matrix_vs_current_max_abs': float(abs(matrices[0] - v[28:37].reshape(3, 3)).max()),
        'output_functions_executed': sorted(r.called), 'host_libm_fixture': True,
        'input_and_output_guards_pass': True, 'source_APK_unchanged': True,
        'output_scope': 'Original CCustomCMM special profiles 0 and 1 to 2, uint16 CPU conversion; original Android colour/film parameter preparation for spaces 0 through 5.',
        'complete_live_display_chain_verified': False, 'GPU_shader_executed': False,
        'phone_sensor_adaptation_validated': False, 'working_space_UI_names_bound': False,
        'photographic_appearance_reference_matched': False,
        'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'adapter_comparison': comparisons}), flush=True)


if __name__ == '__main__': main()
