#!/usr/bin/env python3
"""Run exact X2D II display-HAL code on synthetic fixtures only, with guards."""
import argparse, hashlib, json, os, resource, subprocess
from pathlib import Path

LIB_SHA = 'adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root', required=True, type=Path)
    p.add_argument('--clang', required=True, type=Path)
    p.add_argument('--qemu', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    root = a.firmware_root.resolve()
    lib = root / 'system/lib64/libduml_hal.so'
    if sha(lib) != LIB_SHA:
        raise ValueError('Unsupported libduml_hal.so SHA256')
    source = Path(__file__).with_name('display_sampler_probe.c')
    binary = a.output.resolve().with_name('display_sampler_probe_android28_arm64')
    build = [str(a.clang.resolve()), '-O2', '-ffp-contract=off', '-Wall', '-Wextra',
             '-Werror', str(source), '-ldl', '-lm', '-o', str(binary)]
    built = subprocess.run(build, capture_output=True, text=True, timeout=30)
    if built.returncode:
        raise RuntimeError(built.stderr)
    argv = [str(a.qemu.resolve()), '-L', str(root), str(binary), str(lib)]
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(lib.parent)
    child = subprocess.run(argv, env=env, capture_output=True, text=True,
                           timeout=20, preexec_fn=limits)
    records = [json.loads(s) for s in child.stdout.splitlines() if s.startswith('{')]
    result = {
        'scope': 'Synthetic display-HAL format and sampler proof; no MAIN_3DLUT compatibility claim',
        'library_sha256': LIB_SHA, 'source_sha256': sha(source),
        'runner_sha256': sha(Path(__file__)), 'probe_sha256': sha(binary),
        'qemu_sha256': sha(a.qemu), 'build_command': build, 'run_command': argv,
        'exit': child.returncode, 'stdout': child.stdout, 'stderr': child.stderr,
        'records': records,
    }
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'exit': child.returncode, 'records': len(records),
                      'summaries': [r for r in records if r['test'] != 'synthetic_trilinear_case'],
                      'stderr': child.stderr, 'output': str(a.output)}))
    if child.returncode:
        raise SystemExit(child.returncode)

if __name__ == '__main__':
    main()
