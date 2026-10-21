#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fresh original/owned leaf comparison using the original Android 9 runtime.

Requires privately extracted firmware, Android NDK r27 and QEMU AArch64.
Never downloads or publishes firmware. No stubs or rewritten original code.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent
LIB_SHA = '7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))

def verify_runtime(root):
    manifest = json.loads((AUDIT/'firmware/manifests/extraction_manifest.json').read_text())
    expected = {f'{partition}/{r["path"]}': r['sha256']
                for partition, data in manifest['partitions'].items()
                for r in data['records'] if r['kind']=='file'}
    libs = root/'system/lib64'
    pending, seen = ['libaaa.so'], {}
    while pending:
        name = pending.pop()
        if name in seen: continue
        path = libs/name
        digest = sha(path)
        if digest != expected[str(path.relative_to(root))]:
            raise ValueError('Runtime provenance mismatch: '+name)
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            if elf['e_machine'] != 'EM_AARCH64': raise ValueError('Not ARM64: '+name)
            needed = [t.needed for t in elf.get_section_by_name('.dynamic').iter_tags()
                      if t.entry.d_tag=='DT_NEEDED']
        seen[name] = {'sha256':digest,'needed':needed}
        pending.extend(needed)
    linker=root/'system/bin/linker64'
    if sha(linker)!=expected['system/bin/linker64']: raise ValueError('Linker provenance mismatch')
    if sha(libs/'libaaa.so')!=LIB_SHA: raise ValueError('Wrong original library')
    props = dict(line.split('=',1) for line in (root/'system/build.prop').read_text().splitlines()
                 if '=' in line and not line.startswith('#'))
    if props.get('ro.build.version.sdk')!='28' or props.get('ro.build.version.release')!='9':
        raise ValueError('Runtime is not Android 9/API28')
    with (libs/'libaaa.so').open('rb') as stream:
        elf=ELFFile(stream)
        sym=elf.get_section_by_name('.dynsym').get_symbol_by_name('scene_awb_result_recalib_unit')
        if not sym or sym[0]['st_value']!=0x4a39a0 or sym[0]['st_size']!=56:
            raise ValueError('Original symbol ABI provenance mismatch')
    return seen, sha(linker)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root',type=Path,required=True)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--qemu',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    root=a.firmware_root.resolve(); ndk=a.ndk.resolve(); qemu=a.qemu.resolve()
    output=a.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    closure, linker_sha=verify_runtime(root)
    compiler=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang'
    if '27.0.12077973' not in (ndk/'source.properties').read_text():
        raise ValueError('Expected NDK 27.0.12077973')
    # Rebuild05 in GitHub is incremental; inherited recalibration lives in 04.
    core=AUDIT/'awb_rebuild_04_20261021/src'
    build=output/'build';build.mkdir(exist_ok=True)
    probe=build/'recalib_compare_android28_arm64'
    sources=[HERE/'recalib_compare.c', HERE/'hb_recalib_exact.c',core/'hb_awb_recalib.c']
    cmd=[str(compiler),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIE','-pie',
         '-Wl,-z,max-page-size=16384','-I',str(core), *map(str,sources),'-ldl','-o',str(probe)]
    compiled=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if compiled.returncode:
        raise RuntimeError('Compilation failed:\n'+compiled.stderr)
    command=[str(qemu),'-L',str(root),str(probe),str(root/'system/lib64/libaaa.so')]
    env={'PATH':'/usr/bin:/bin','LANG':'C','LD_LIBRARY_PATH':str(root/'system/lib64')}
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30,preexec_fn=limits)
    events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    ok=(result.returncode==0 and len(events)==1 and events[0].get('failed')==0
        and events[0].get('original_calls')==27588)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),
            'execution':'Original Android 9 Bionic linker and vendor dependency closure under QEMU user AArch64',
            'firmware':'X2D II 100C 1.3.16.2','original_library_sha256':LIB_SHA,
            'linker_sha256':linker_sha,'dependencies':closure,
            'qemu_sha256':sha(qemu),'qemu_version':subprocess.check_output([str(qemu),'--version'],text=True).splitlines()[0],
            'compiler_version':subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0],
            'probe_sha256':sha(probe),
            'source_sha256':{str(s.relative_to(AUDIT)):sha(s) for s in [*sources,HERE/'hb_recalib_exact.h',HERE/'run_recalib.py',core/'hb_awb_recalib.h']},
            'build_command':cmd,'run_command':command,'exit':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,'events':events,'all_passed':ok,
            'original_library_patched':False,'dependency_stubs':False,
            'inputs':'Synthetic integer fixtures, not authentic camera frames',
            'full_awb_initialization_verified':False,'scene_optimizer_verified':False,
            'seven_frame_parity_verified':False,'phone_tested':False}
    (output/'RECALIB_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'all_passed':ok,'events':events,'exit':result.returncode,'stderr':result.stderr}))
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
