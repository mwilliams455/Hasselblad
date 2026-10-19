#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replay original CCM preparation and relocated metadata with exact Android9 ELF.

Requires user-supplied exact firmware, API28 ARM64 NDK clang, QEMU user-mode,
pyelftools and capstone. Only own source and metadata are retained. All probe
binaries and coefficient inputs/outputs are confined to a temporary directory.
No camera control, pixel rendering or device deployment API is invoked.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from inspect_ccm import inspect, sha, LIB_SHA

CCTS = [2000, 2400, 3001, 3050, 4300, 5550, 7001, 9100, 10000]
WEIGHTS = [0, 1, 64, 128, 255, 256]
AXIS = [2400, 3050, 5550, 9100]


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))


def coefficient(cct):
    if cct < AXIS[0]:
        return 0, 0
    if cct >= AXIS[-1]:
        return 2, 256
    index = max(i for i, knot in enumerate(AXIS) if knot <= cct)
    return index, (cct - AXIS[index])*256 // (AXIS[index+1] - AXIS[index])


def reference(values, cct, weight):
    index, fraction = coefficient(cct)
    def lerp(a, b, w):
        return a + (b-a)*w // 256
    out = []
    for k in range(96):
        a = index*96 + k
        low = lerp(values[a], values[a+96], fraction)
        high = lerp(values[a+384], values[a+480], fraction)
        out.append(lerp(low, high, weight))
    return struct.pack('<96i', *out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    root = args.firmware_root.resolve()
    output_dir = args.output_directory.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    static, real_values = inspect(root)
    here = Path(__file__).resolve().parent
    lib = root / 'system/lib64/librcam.so'
    expected_runtime = {
        'system/bin/linker64': '313d7a6d94cdeb9e2b2adb4be98a8b18240b08012b22f922acea7984f42ff35d',
        'system/lib64/libc.so': '1af0737faf17f3589eb72e03efd31dc1316560b6c14b4c4e2f503d24287d13e4'}
    if any(sha(root/path) != digest for path, digest in expected_runtime.items()):
        raise ValueError('Unsupported original Android9 linker/libc identity')
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(lib.parent)
    env.pop('LD_PRELOAD', None)
    fixtures = {
        'synthetic_dense_signed': [(p*19073+k*1297+p*k*173) % 65001 - 32500
                                   for p in range(8) for k in range(96)],
        'synthetic_signed_limits': [(-32768 if (p+k) % 2 else 32767)
                                    for p in range(8) for k in range(96)],
        'original_global_still_ccm': real_values
    }
    common = {'firmware': static['firmware'], 'library_sha256': LIB_SHA,
              'runner_sha256': sha(Path(__file__)),
              'runtime_sha256': {'qemu': sha(args.qemu),
                                 'linker64': sha(root/'system/bin/linker64'),
                                 'libc.so': sha(root/'system/lib64/libc.so')},
              'bounds': {'wall_timeout_seconds': 20, 'cpu_limit_seconds': 15, 'core_limit_bytes': 0},
              'environment': {'LD_LIBRARY_PATH': str(lib.parent)},
              'original_library_initializers_executed': True,
              'camera_control_functions_explicitly_invoked': False,
              'pixel_renderer_validated': False}
    builds, binaries, results = {}, {}, []
    with tempfile.TemporaryDirectory(prefix='hb-ccm-probe-') as temp_name:
        temp = Path(temp_name)
        for name, sources in {
                'metadata': ['inspect_ccm_metadata.c'],
                'prepare': ['ccm_prepare_probe.c', 'ccm_prepare.c']}.items():
            binary = temp / name
            build = [str(args.clang.resolve()), '-O2', '-Wall', '-Wextra', '-Werror']
            build += [str(here/source) for source in sources]
            build += ['-ldl', '-o', str(binary)]
            subprocess.run(build, check=True, capture_output=True, text=True, timeout=30)
            builds[name] = {'command': build, 'binary_sha256': sha(binary),
                            'source_sha256': {source: sha(here/source) for source in sources}}
            binaries[name] = binary

        def run(binary, extra=()):
            argv = [str(args.qemu.resolve()), '-L', str(root), str(binary), str(lib), *map(str, extra)]
            child = subprocess.run(argv, env=env, capture_output=True, text=True,
                                   timeout=20, preexec_fn=limits)
            if child.returncode or child.stderr:
                raise RuntimeError(f'Original probe failed ({child.returncode}): {child.stderr[:2000]}')
            records = [json.loads(line) for line in child.stdout.splitlines()]
            return argv, records

        metadata_command, metadata = run(binaries['metadata'])
        ccm_registers = [r for r in metadata if r.get('iq_getter_va') == '0x33f960']
        if (len(metadata) != 46 or not metadata[0]['matches'] or
                [r['register_id'] for r in ccm_registers] != list(range(4126, 4172, 3)) or
                any(r['type'] != 3 or r['group_num'] != 6 or r['descriptor_word3'] != 65535
                    for r in ccm_registers)):
            raise ValueError('CCM relocated metadata contract mismatch')
        for name, values in fixtures.items():
            input_path, output_path = temp/'input.bin', temp/'output.bin'
            payload = struct.pack('<768i', *values)
            input_path.write_bytes(payload)
            command, cases = run(binaries['prepare'], (input_path, output_path))
            native = output_path.read_bytes()
            if len(cases) != 54 or len(native) != 54*96*4:
                raise ValueError('Unexpected original output extent')
            for n, case in enumerate(cases):
                cct, weight = CCTS[n//len(WEIGHTS)], WEIGHTS[n % len(WEIGHTS)]
                if (case['case'], case['cct'], case['secondary_weight_q8']) != (n, cct, weight):
                    raise ValueError('Unexpected native case order')
                expected = reference(values, cct, weight)
                actual = native[n*96*4:(n+1)*96*4]
                index, fraction = coefficient(cct)
                passed = (case['pass'] and actual == expected and
                          (case['cct_index'], case['cct_fraction_q8']) == (index, fraction))
                case.update({'output_sha256': hashlib.sha256(actual).hexdigest(),
                             'python_reference_sha256': hashlib.sha256(expected).hexdigest(),
                             'python_all_bytes_match': actual == expected, 'pass': passed})
            results.append({'fixture': name, 'input_values': 768, 'input_sha256': hashlib.sha256(payload).hexdigest(),
                            'run_command': command, 'cases': cases,
                            'scalar_outputs_checked': 54*96, 'all_passed': all(c['pass'] for c in cases)})

    static_name, metadata_name, execution_name = ('ccm_static_evidence.json',
                                                 'ccm_metadata_original_execution.json',
                                                 'ccm_prepare_original_execution.json')
    metadata_result = dict(common, method='Read bounded original linker-relocated metadata; wrapper not invoked',
                           build=builds['metadata'], run_command=metadata_command, records=metadata,
                           register_families=16, components_per_family=6, prepared_coefficients=96,
                           all_passed=True)
    result = dict(common, method='Original mm_get_coeff and mm_mx_lerp_gap under matching Android9 Bionic/QEMU; compare every scalar to portable C and independent Python',
                  build=builds['prepare'], header_sha256=sha(here/'ccm_prepare.h'),
                  functions=[r for r in static['functions'] if r['name'] in ('mm_get_coeff', 'mm_mx_lerp_gap')],
                  fixtures=results, case_count=162, scalar_outputs_checked=162*96,
                  all_passed=all(r['all_passed'] for r in results),
                  temporary_binaries_and_payloads_deleted=True, coefficient_payloads_published=False,
                  limitations=['Two-dimensional coefficient preparation only; not per-pixel CCM application.',
                               'Portable contract accepts signed16 source coefficients and Q8 bank weights 0..256.',
                               'Does not claim arbitrary int32 equivalence outside this no-overflow domain.',
                               'Original high-ISO gain-to-weight branch was inspected statically; the probe supplies weights explicitly.'])
    for name, value in ((static_name, static), (metadata_name, metadata_result), (execution_name, result)):
        (output_dir/name).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'metadata_records': len(metadata), 'cases': 162,
                      'scalar_outputs_checked': 162*96, 'all_passed': result['all_passed'],
                      'output_directory': str(output_dir)}))
    if not result['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
