#!/usr/bin/env python3
"""Phone-specific temperature model: independent double oracle and ARM64 replay.

Full metadata, input models, gain loci, executable probes and logs stay private.
The public report contains aggregate results and identities only.
"""
import argparse
import copy
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess

import numpy as np
from temperature_binding import bind_temperature, rational32

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent/'awb_original_runtime_20261021'
REPO = HERE.parents[1]


class Anchor(C.Structure):
    _fields_ = [('kelvin', C.c_uint32), ('color', C.c_float*9), ('calibration', C.c_float*9)]


class Input(C.Structure):
    _fields_ = [('anchor', Anchor*2)]


class Gains(C.Structure):
    _fields_ = [('gain_q12', C.c_uint32*3)]


class Estimate(C.Structure):
    _fields_ = [('kelvin', C.c_float), ('tint', C.c_float), ('ratio_residual', C.c_float)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def descriptor(anchors):
    return Input((Anchor*2)(*[Anchor(a['kelvin'], (C.c_float*9)(*a['color']),
                                    (C.c_float*9)(*a['calibration'])) for a in anchors]))


def build(compiler, out, label, extra, shared=False):
    flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
             '-Wno-misleading-indentation', '-ffp-contract=off',
             '-ffunction-sections', '-fdata-sections', *extra]
    # Only these owned leaves are linked. Original runtime sources are hidden
    # so --gc-sections drops unrelated user/scene paths from the shared build.
    sources = [HERE/'hb_phone_temperature.c', RUNTIME/'hb_temperature.c',
               RUNTIME/'hb_user_controls.c', RUNTIME/'hb_scene_optimizer.c']
    objects = []
    for source in sources:
        obj = out/(label+'_'+source.stem+'.o'); objects.append(obj)
        subprocess.run([str(compiler), *[x for x in flags if not x.startswith('-Wl,')],
                        *(['-fvisibility=hidden'] if source.parent == RUNTIME else []),
                        '-c', str(source), '-o', str(obj)], check=True)
    target = out/('libphone_temperature.so' if shared else 'phone_temperature_'+label)
    subprocess.run([str(compiler), *flags, *(['-shared'] if shared else ['-pie', str(HERE/'phone_temperature_probe.c')]),
                    *map(str, objects), '-Wl,--gc-sections,-z,defs', '-lm', '-o', str(target)], check=True)
    return target, sources


def main():
    parser = argparse.ArgumentParser()
    for name in ['capture', 'out', 'report', 'ndk', 'qemu', 'firmware-root']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    libpath, sources = build('cc', args.out, 'host', ['-fPIC'], shared=True)
    lib = C.CDLL(str(libpath.resolve()))
    create = lib.hb_phone_temperature_create; create.argtypes = [C.POINTER(Input), C.POINTER(C.c_void_p)]; create.restype = C.c_int
    destroy = lib.hb_phone_temperature_destroy; destroy.argtypes = [C.c_void_p]
    matrix = lib.hb_phone_temperature_matrix; matrix.argtypes = [C.c_void_p, C.c_float, C.POINTER(C.c_float)]; matrix.restype = C.c_int
    forward = lib.hb_phone_temperature_to_gain; forward.argtypes = [C.c_void_p, C.c_uint32, C.c_float, C.POINTER(Gains)]; forward.restype = C.c_int
    inverse = lib.hb_phone_temperature_from_gain; inverse.argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.POINTER(Estimate)]; inverse.restype = C.c_int
    # The oracle shares only the declared public numerical table. It uses
    # float64 vector algebra and numpy inversion, not the C operation order.
    source = (HERE/'hb_phone_temperature.c').read_text()
    body = source.split('isotemperature[31][4] = {', 1)[1].split('};', 1)[0]
    table = np.array([[float(x.rstrip('f')) for x in row.split(',')]
                      for row in re.findall(r'\{([^{}]+)\}', body)])
    assert table.shape == (31, 4) and table[19, 1] == .24702

    def oracle_matrix(inp, temperature):
        a, b = sorted(inp.anchor, key=lambda v: v.kelvin)
        low = np.array(a.calibration).astype(float).reshape(3, 3) @ np.array(a.color).astype(float).reshape(3, 3)
        high = np.array(b.calibration).astype(float).reshape(3, 3) @ np.array(b.color).astype(float).reshape(3, 3)
        weight = np.clip((1/temperature-1/b.kelvin)/(1/a.kelvin-1/b.kelvin), 0, 1)
        return weight*low+(1-weight)*high

    def oracle_xyz(temperature, tint):
        mired = 1e6/temperature
        i = int(np.clip(np.searchsorted(table[:, 0], mired, side='right')-1, 0, 29))
        a, b = table[i:i+2]; weight = (b[0]-mired)/(b[0]-a[0])
        vectors = np.column_stack([np.ones(2), [a[3], b[3]]])
        vectors /= np.linalg.norm(vectors, axis=1)[:, None]
        direction = weight*vectors[0]+(1-weight)*vectors[1]
        direction /= np.linalg.norm(direction)
        u, v = weight*a[1:3]+(1-weight)*b[1:3]-tint/3000*direction
        x, y = 1.5*u/(u-4*v+2), v/(u-4*v+2)
        return np.array([x, y, 1-x-y])

    j = json.loads(args.capture.read_text()); original = copy.deepcopy(j)
    models = []
    for black in ['exported', 'dynamic', 'static']:
        binding = bind_temperature(j, black)
        (args.out/('temperature_binding_'+black+'.json')).write_text(json.dumps(binding, indent=2)+'\n')
        models.append(descriptor(binding['anchors']))
    assert bytes(models[0]) == bytes(models[1]) == bytes(models[2]) and j == original
    neutral = [rational32(v) for v in j['original_still']['selected_raw_sensor_result']['android.sensor.neutralColorPoint']]
    hal_gain = (C.c_uint32*3)(*[int(4096/v) for v in neutral])
    # Two noncommuting products, distinct per-anchor calibration transforms;
    # each synthetic profile is independent of any private camera payload.
    rng = np.random.default_rng(20261021)
    cases = [('capture', models[0])]
    for i in range(16):
        anchors = []
        for ct in [2856, 6504]:
            color = np.eye(3)+rng.uniform(-.04, .04, (3, 3))
            calibration = np.diag([1.05, .98, 1.02])+rng.uniform(-.01, .01, (3, 3))
            anchors.append({'kelvin': ct, 'color': color.ravel(), 'calibration': calibration.ravel()})
        cases.append(('synthetic_'+str(i), descriptor(anchors)))
    totals = {'matrix_oracle_comparisons': 0, 'forward_gain_oracle_comparisons': 0,
              'roundtrips': 0, 'swapped_anchor_invariances': 0,
              'oracle_confirmed_clipped_samples': 0, 'inverse_rejected_samples': 0}
    maxima = {'matrix_abs': 0., 'gain_abs_q12': 0., 'roundtrip_kelvin': 0.,
              'roundtrip_tint': 0., 'inverse_xyz_residual': 0., 'reported_ratio_residual': 0.}
    selected = []
    for name, inp in cases:
        ptr = C.c_void_p(); before = bytes(inp)
        assert create(C.byref(inp), C.byref(ptr)) == 0
        swapped = Input((Anchor*2)(inp.anchor[1], inp.anchor[0])); other = C.c_void_p()
        assert create(C.byref(swapped), C.byref(other)) == 0
        private_rows = []
        try:
            for tint in [-25, 0, 25]:
                for ct in range(2000, 10001, 100):
                    m = (C.c_float*9)(); m2 = (C.c_float*9)()
                    assert matrix(ptr, ct, m) == matrix(other, ct, m2) == 0
                    assert bytes(m) == bytes(m2)
                    reference = oracle_matrix(inp, ct)
                    error = float(np.max(np.abs(np.array(m).reshape(3, 3)-reference)))
                    assert error < 5e-7, (name, ct, error)
                    maxima['matrix_abs'] = max(maxima['matrix_abs'], error)
                    totals['matrix_oracle_comparisons'] += 1
                    rgb = reference @ oracle_xyz(ct, tint)
                    expected = 4096*max(rgb)/rgb
                    g = Gains(); g2 = Gains()
                    st = forward(ptr, ct, tint, C.byref(g))
                    assert st == forward(other, ct, tint, C.byref(g2)), (name, ct, tint)
                    if st:
                        assert st == 4 and (min(rgb)<1e-5 or max(expected)>=40960), (name, ct, tint, st, expected)
                        assert bytes(g) == bytes(Gains()) and bytes(g2) == bytes(Gains())
                        totals['oracle_confirmed_clipped_samples'] += 1
                        continue
                    assert bytes(g) == bytes(g2)
                    error = float(max(abs(np.array(g.gain_q12)-expected)))
                    assert error < 1.2, (name, ct, tint, error)
                    maxima['gain_abs_q12'] = max(maxima['gain_abs_q12'], error)
                    totals['forward_gain_oracle_comparisons'] += 1
                    result = Estimate(); st = inverse(ptr, g.gain_q12, C.byref(result))
                    assert st == 0, (name, ct, tint, st)
                    # Independent inverse interpretation: solve XYZ from camera
                    # neutral, then compare against the public CT/tint locus.
                    xyz = np.linalg.solve(oracle_matrix(inp, result.kelvin), 1/np.array(g.gain_q12).astype(float))
                    xyz /= sum(xyz)
                    error_xyz = float(max(abs(xyz-oracle_xyz(result.kelvin, result.tint))))
                    assert error_xyz < 2e-4, (name, ct, tint, error_xyz)
                    assert abs(result.kelvin-ct) < 15 and abs(result.tint-tint) < .15
                    maxima['inverse_xyz_residual'] = max(maxima['inverse_xyz_residual'], error_xyz)
                    maxima['roundtrip_kelvin'] = max(maxima['roundtrip_kelvin'], abs(result.kelvin-ct))
                    maxima['roundtrip_tint'] = max(maxima['roundtrip_tint'], abs(result.tint-tint))
                    maxima['reported_ratio_residual'] = max(maxima['reported_ratio_residual'], result.ratio_residual)
                    totals['roundtrips'] += 1; totals['swapped_anchor_invariances'] += 1
                    private_rows.append({'kelvin': ct, 'tint': tint, 'gains': list(g.gain_q12),
                                         'recovered_kelvin': result.kelvin, 'recovered_tint': result.tint,
                                         'ratio_residual': result.ratio_residual})
            assert bytes(inp) == before
            if name in ['capture', 'synthetic_0', 'synthetic_15']:
                (args.out/(name+'.input')).write_bytes(bytes(inp)+bytes(hal_gain))
                (args.out/(name+'.locus.json')).write_text(json.dumps(private_rows, indent=2)+'\n')
                selected.append(name)
            if name == 'capture':
                result = Estimate(); assert inverse(ptr, hal_gain, C.byref(result)) == 0
                (args.out/'hal_interpretation.json').write_text(json.dumps({
                    'source': 'original HAL neutral, not a new automatic estimate',
                    'gain_q12': list(hal_gain), 'kelvin': result.kelvin,
                    'tint': result.tint, 'ratio_residual': result.ratio_residual,
                    'photographic_ground_truth': False}, indent=2)+'\n')
        finally:
            destroy(ptr); destroy(other)
    # Explicit cap rejection using a synthetic ill-scaled but nonsingular model.
    clipped = descriptor([{'kelvin': ct, 'color': [.001,0,0,0,2,0,0,0,2],
                           'calibration': np.eye(3).ravel()} for ct in [2856,6504]])
    ptr = C.c_void_p(); assert create(C.byref(clipped), C.byref(ptr)) == 0
    g = Gains(); C.memset(C.byref(g), 0xa5, C.sizeof(g)); before = bytes(g)
    assert forward(ptr, 5000, 0, C.byref(g)) == 4 and bytes(g) == before
    destroy(ptr)
    mutations = [
        ('missing matrix', lambda m: m['original_still']['selected_sensor_characteristics'].pop('android.sensor.colorTransform1')),
        ('zero denominator', lambda m: m['original_still']['selected_sensor_characteristics']['android.sensor.colorTransform1'][0].__setitem__('denominator', 0)),
        ('int32 range', lambda m: m['original_still']['selected_sensor_characteristics']['android.sensor.colorTransform1'][0].__setitem__('numerator', 1<<31)),
        ('unsupported illuminant', lambda m: m['original_still']['selected_sensor_characteristics'].__setitem__('android.sensor.referenceIlluminant1', 0)),
        ('duplicate illuminant', lambda m: m['original_still']['selected_sensor_characteristics'].__setitem__('android.sensor.referenceIlluminant1', 17)),
        ('unequal normalization', lambda m: m['effective_photon_export']['black_level_raw_counts'].__setitem__(0, 65)),
        ('mismatched sensor', lambda m: m['original_still']['sensor_provenance'].__setitem__('selected_calibration_camera_id', 'unmatched'))]
    for name, edit in mutations:
        bad = copy.deepcopy(j); edit(bad)
        try: bind_temperature(bad, 'exported')
        except (ValueError, KeyError, TypeError): pass
        else: raise AssertionError(name)
    effective = copy.deepcopy(j)
    # Render-owned matrices may differ; this binder MUST depend only on original.
    for key in ['colour_matrix_1', 'colour_matrix_2', 'calibration_transform_1', 'calibration_transform_2']:
        assert key in effective['effective_photon_export']
        effective['effective_photon_export'][key] = [999]*9
    assert bind_temperature(effective, 'exported')['anchors'] == bind_temperature(j, 'exported')['anchors']
    host, _ = build('cc', args.out, 'optimized', ['-fPIE'])
    sanitized, _ = build('cc', args.out, 'sanitized', ['-fPIE','-fsanitize=address,undefined','-fno-omit-frame-pointer'])
    compiler = args.ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang'
    android, _ = build(compiler, args.out, 'android28', ['-fPIE','-Wl,-z,max-page-size=16384'])
    comparisons = []
    for name in selected:
        expected = None
        for label, command in [('optimized',[str(host)]), ('sanitized',[str(sanitized)]),
                               ('android28',[str(args.qemu),'-L',str(args.firmware_root),str(android)])]:
            output = args.out/(name+'.'+label+'.bin')
            env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            run = subprocess.run([*command, str(args.out/(name+'.input')), str(output)],
                                 capture_output=True, text=True, timeout=60, env=env)
            (args.out/(name+'.'+label+'.log')).write_text(run.stdout+run.stderr)
            assert run.returncode == 0, (label, run.stderr)
            data = output.read_bytes(); assert struct.unpack_from('<3I',data) == (1,243,26)
            if expected is None: expected = data
            else:
                assert data == expected, (name, label)
                comparisons.append({'case':name,'runtime':label,'exact_bytes':len(data),'sha256':sha(output)})
    tracked = [*sources, HERE/'hb_phone_temperature.h', HERE/'phone_temperature_probe.c',
               HERE/'temperature_binding.py', HERE/'capture_binding.py', Path(__file__),
               *sorted(RUNTIME.glob('*.h'))]
    report = {'status':'PASS', 'real_metadata_variants':3, 'synthetic_profiles':16, **totals,
              'max_errors':maxima, 'native_probe_rejections_per_run':26,
              'explicit_clipping_rejections':1, 'metadata_rejections':len(mutations),
              'cross_runtime':comparisons,
              'source_sha256':{str(p.relative_to(REPO)):sha(p) for p in tracked},
              'input_sha256':{'capture':sha(args.capture)},
              'binary_sha256':{p.name:sha(p) for p in [libpath,host,sanitized,android]},
              'original_metadata_unchanged':j==original,
              'table_variant':'Public Adobe DNG SDK 1.4, u325=0.24702',
              'temperature_workspace_initialized_from_phone_metadata':True,
              'vendor_initializer_or_library_used':False,
              'full_automatic_profile_available':False,'automatic_controller_called':False,
              'hal_neutral_is_new_awb_result':False,'apk_built':False,
              'photographic_colour_validated':False,
              'sanitizers':{'address':True,'undefined':True,'leak':False,
                            'leak_limitation':'Executor denies /proc task inspection'}}
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','input_sha256','binary_sha256','cross_runtime']},indent=2))


if __name__ == '__main__': main()
