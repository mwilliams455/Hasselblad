#!/usr/bin/env python3
"""Link Domain1 against the actual owned Hasselblad temperature leaves.

Public synthetic profiles only. This tests binary/API integration and per-point
classification, not camera calibration or neutral selection. Never use the HAL
neutral as a fitting input. No photograph data or private matrices are embedded.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent.parent
RUNTIME = HERE.parent / 'awb_original_runtime_20261021'

class Anchor(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('color', C.c_float * 9),
                ('calibration', C.c_float * 9)]

class Input(C.Structure):
    _fields_ = [('anchor', Anchor * 2)]

class Gains(C.Structure):
    _fields_ = [('gain_q12', C.c_uint32 * 3)]

class Request(C.Structure):
    _fields_ = [('first_kelvin', C.c_uint32), ('last_kelvin', C.c_uint32),
                ('kelvin_step', C.c_uint32), ('first_tint', C.c_int32),
                ('last_tint', C.c_int32), ('tint_step', C.c_uint32)]

class Point(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('tint', C.c_int32),
                ('exclusion', C.c_uint32), ('temperature_status', C.c_uint32),
                ('gain_q12', C.c_uint32 * 3)]

class Result(C.Structure):
    _fields_ = [('schema_version', C.c_uint32), ('requested', Request),
                ('kelvin_count', C.c_uint32), ('tint_count', C.c_uint32),
                ('point_count', C.c_uint32), ('representable', C.c_uint32),
                ('temperature_clipped', C.c_uint32),
                ('scene_signed_gain', C.c_uint32),
                ('adjacent_duplicate', C.c_uint32), ('points', Point * 729)]

GRID = Request(2000, 10000, 100, -100, 100, 25)
SOURCES = [HERE / 'hb_phone_domain.c', HERE / 'hb_phone_temperature.c',
           RUNTIME / 'hb_temperature.c', RUNTIME / 'hb_user_controls.c',
           RUNTIME / 'hb_scene_optimizer.c']

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(out, opt):
    stem = opt.replace('-', '')
    flags = ['-std=c11', opt, '-Wall', '-Wextra', '-Werror',
             '-Wno-misleading-indentation', '-ffp-contract=off',
             '-ffunction-sections', '-fdata-sections', '-fPIC']
    objs = []
    for source in SOURCES:
        obj = out / (stem + '_' + source.stem + '.o')
        command = ['cc', *flags]
        if source.parent == RUNTIME:
            command.append('-fvisibility=hidden')
        command += ['-c', str(source), '-o', str(obj)]
        subprocess.run(command, check=True)
        objs.append(obj)
    library = out / ('libphone_domain_real_' + stem + '.so')
    subprocess.run(['cc', *flags, '-shared', *map(str, objs),
                    '-Wl,--gc-sections,-z,defs', '-lm', '-o', str(library)],
                   check=True)
    return library


def open_native(path):
    lib = C.CDLL(str(path.resolve()))
    lib.hb_phone_domain_evaluate.argtypes = [C.POINTER(Input), C.POINTER(Request), C.POINTER(Result)]
    lib.hb_phone_domain_evaluate.restype = C.c_int
    lib.hb_phone_temperature_create.argtypes = [C.POINTER(Input), C.POINTER(C.c_void_p)]
    lib.hb_phone_temperature_create.restype = C.c_int
    lib.hb_phone_temperature_destroy.argtypes = [C.c_void_p]
    lib.hb_phone_temperature_to_gain.argtypes = [C.c_void_p, C.c_uint32, C.c_float, C.POINTER(Gains)]
    lib.hb_phone_temperature_to_gain.restype = C.c_int
    return lib


def profile(index):
    # Entirely synthetic, bounded, positive-determinant camera anchors.
    if index == 0:
        colors = [
            [1.02, -.02, 0.0, -.02, 1.07, -.05, -.01, .08, .93],
            [1.15, -.12, -.03, -.06, 1.12, -.06, -.02, .11, .91]]
        calibration = [
            [1.01, 0, 0, 0, 1, 0, 0, 0, 1.02],
            [1.02, 0, 0, 0, 1, 0, 0, 0, 1.01]]
    else:
        colors = [
            [1.2, -.13, -.07, -.09, 1.18, -.09, -.03, .04, .99],
            [1.08, -.1, .02, -.08, 1.12, -.04, -.02, .03, 1.06]]
        calibration = [
            [1.03, .01, 0, 0, .97, -.01, -.01, .02, 1.02],
            [1.01, -.01, 0, .01, 1.01, .02, 0, -.01, 1.03]]
    return Input((Anchor * 2)(
        Anchor(2856, (C.c_float * 9)(*colors[0]), (C.c_float * 9)(*calibration[0])),
        Anchor(6504, (C.c_float * 9)(*colors[1]), (C.c_float * 9)(*calibration[1]))))


def evaluate(lib, inp, request=GRID):
    result = Result()
    status = lib.hb_phone_domain_evaluate(C.byref(inp), C.byref(request), C.byref(result))
    assert status == 0, ('domain status', status)
    assert result.schema_version == 1
    assert result.point_count == result.kelvin_count * result.tint_count
    assert (result.representable + result.temperature_clipped +
            result.scene_signed_gain + result.adjacent_duplicate) == result.point_count
    assert not any(bytes(p).strip(b'\x00') for p in result.points[result.point_count:])
    return result


def check_output_nonmutation(lib, inp, request, code):
    out = Result()
    C.memset(C.byref(out), 0xA5, C.sizeof(out))
    before = C.string_at(C.byref(out), C.sizeof(out))
    actual = lib.hb_phone_domain_evaluate(C.byref(inp), C.byref(request), C.byref(out))
    assert actual == code, (actual, code)
    assert before == C.string_at(C.byref(out), C.sizeof(out))


def inspect_native(lib, inp):
    result = evaluate(lib, inp)
    native = C.c_void_p()
    assert lib.hb_phone_temperature_create(C.byref(inp), C.byref(native)) == 0
    counters = [0, 0, 0, 0]
    count = 0
    try:
        for ti, tint in enumerate(range(-100, 101, 25)):
            prev = None
            for ki, kelvin in enumerate(range(2000, 10001, 100)):
                entry = result.points[ti * 81 + ki]
                assert (entry.kelvin, entry.tint) == (kelvin, tint)
                gains = Gains()
                code = lib.hb_phone_temperature_to_gain(native, kelvin, float(tint), C.byref(gains))
                if code == 4:
                    reason = 1
                    prev = None
                else:
                    assert code == 0, ('Unexpected real temperature leaf status', code)
                    assert 4096 <= min(gains.gain_q12) and max(gains.gain_q12) < 40960
                    r = gains.gain_q12[0] * 4096 // gains.gain_q12[1]
                    b = gains.gain_q12[2] * 4096 // gains.gain_q12[1]
                    if not 0 < min(r, b) <= max(r, b) <= 32767:
                        reason = 2
                        prev = None
                    elif prev == (r, b):
                        reason = 3
                    else:
                        reason = 0
                        prev = (r, b)
                assert (entry.temperature_status, entry.exclusion) == (code, reason)
                assert list(entry.gain_q12) == ([r, 4096, b] if reason == 0 else [0, 0, 0])
                counters[reason] += 1
                count += 1
    finally:
        lib.hb_phone_temperature_destroy(native)
    assert count == 729
    assert counters == [result.representable, result.temperature_clipped,
                        result.scene_signed_gain, result.adjacent_duplicate]
    assert bytes(result) == bytes(evaluate(lib, inp)), 'non-deterministic domain output'
    return {'point_checks': count, 'counts': counters, 'record_sha256': hashlib.sha256(bytes(result)).hexdigest()}


def smoke_rejections(lib, inp):
    bad = [Request(2000, 2011, 100, 0, 0, 25),
           Request(2000, 10000, 1, -100, 100, 25),
           Request(2000, 10000, 100, -100, 100, 1),
           Request(2000, 10001, 100, 0, 0, 25),
           Request(2000, 2000, 0, 0, 0, 25),
           Request(2000, 2000, 100, -101, 0, 25),
           Request(1666, 2000, 100, 0, 0, 25)]
    for req in bad:
        check_output_nonmutation(lib, inp, req, 2)
    zero = profile(0)
    for k in range(9):
        zero.anchor[0].color[k] = 0
        zero.anchor[1].color[k] = 0
    check_output_nonmutation(lib, zero, GRID, 3)
    return {'bad_request_checks':len(bad), 'invalid_profile_checks':1}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    checks = []
    for opt in ('-O0', '-O2'):
        library = build(args.out, opt)
        lib = open_native(library)
        profiles = [inspect_native(lib, profile(i)) for i in range(2)]
        smoke = smoke_rejections(lib, profile(0))
        checks.append({'optimization': opt, 'profiles':profiles, **smoke,
                       'shared_object_sha256':sha(library)})
    for i in range(2):
        assert checks[0]['profiles'][i] == checks[1]['profiles'][i]
    report = {'status':'PASS', 'domain_schema':1, 'linked_temperature_leaf':'actual owned C source',
              'synthetic_profiles':2, 'native_per_point_checks':2 * 729,
              'builds':['O0','O2'], 'host_consistent': True,
              'camera_calibration_derived':False, 'render_applied':False,
              'full_phone_controller_initialized':False,
              'test_details':checks,
              'source_sha256':{str(x.relative_to(HERE.parent)):sha(x) for x in
                               [HERE/'hb_phone_domain.h', *SOURCES, Path(__file__)]}}
    (args.out / 'PHONE_DOMAIN_REAL_PUBLIC_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'native_per_point_checks':report['native_per_point_checks'],
                      'builds':report['builds'],'domain_counts':[[p['counts'] for p in b['profiles']] for b in checks]},indent=2))

if __name__ == '__main__':
    main()
