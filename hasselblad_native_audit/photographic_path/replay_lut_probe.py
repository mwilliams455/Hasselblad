#!/usr/bin/env python3
"""Build and run the bounded original X2D II profile-LUT native probe.

Requires user-supplied exact firmware, an Android NDK ARM64 compiler, QEMU user
mode and pyelftools. Vendor bytes are neither bundled nor downloaded. The child
loads the original library and therefore runs its initializers; it does not call
camera control, file conversion, device deployment or image capture APIs.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import tempfile

if Path('/tmp/hasselblad-audit-python').is_dir():
    sys.path.insert(0,'/tmp/hasselblad-audit-python')
from elftools.elf.elffile import ELFFile

LIB_SHA256 = '3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66'
SYMBOLS = {
    'dcam_isp_vreg_get_type': (0x54b88,4),
    'mm_get_coeff': (0x2bac00,160),
    'mm_mx_lerp_vec_mix2': (0x2bbc08,1784),
}

def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def inspect_exact_library(path):
    if sha256(path) != LIB_SHA256:
        raise ValueError('Library does not match the audited X2D II 1.3.16.2 SHA256')
    with path.open('rb') as f:
        elf=ELFFile(f)
        if elf['e_machine']!='EM_AARCH64' or elf.elfclass!=64 or not elf.little_endian:
            raise ValueError('Expected little-endian AArch64 ELF64')
        dynamic={s.name:s for s in elf.get_section_by_name('.dynsym').iter_symbols()}
        debug=ELFFile(io.BytesIO(lzma.decompress(elf.get_section_by_name('.gnu_debugdata').data())))
        local={s.name:s for s in debug.get_section_by_name('.symtab').iter_symbols()}
        result=[]
        for name,(va,size) in SYMBOLS.items():
            symbol=dynamic.get(name) or local.get(name)
            if symbol is None or (symbol['st_value'],symbol['st_size'])!=(va,size):
                raise ValueError(f'Unexpected symbol identity/extent: {name}')
            code=None
            for segment in elf.iter_segments():
                if segment['p_type']=='PT_LOAD' and segment['p_vaddr']<=va and va+size<=segment['p_vaddr']+segment['p_filesz']:
                    start=va-segment['p_vaddr']
                    code=segment.data()[start:start+size]
                    break
            if code is None: raise ValueError(f'No file-backed load segment for {name}')
            result.append({'name':name,'va':hex(va),'bytes':size,
                           'exported':name in dynamic,
                           'code_sha256':hashlib.sha256(code).hexdigest()})
        return result

def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root',type=Path,required=True,
                   help='Extracted root containing system/bin/linker64 and system/lib64')
    p.add_argument('--qemu',type=Path,required=True)
    p.add_argument('--clang',type=Path,required=True,help='aarch64-linux-android28-clang')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--config',type=Path,
                   help='Optional exact-hash hb722_config.json; runs full-size original camera profile tests instead of the synthetic fixture')
    args=p.parse_args()
    root=args.firmware_root.resolve()
    library=root/'system/lib64/librcam.so'
    identities=inspect_exact_library(library)
    source=Path(__file__).with_name('lut_profile_probe.c')
    binary=args.output.resolve().with_name('lut_profile_probe_android28_arm64')
    binary.parent.mkdir(parents=True,exist_ok=True)
    build=[str(args.clang.resolve()),'-O2','-Wall','-Wextra','-Werror',str(source),
           '-ldl','-o',str(binary)]
    subprocess.run(build,check=True,capture_output=True,text=True,timeout=30)
    argv=[str(args.qemu.resolve()),'-L',str(root),str(binary),str(library)]
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=str(library.parent)
    payload_metadata=None
    if args.config:
        from inspect_iq_config import read_config
        config=read_config(args.config)
        values=config['iq_table']['data'][0]['main_3dlut'][0]['lut_data']
        axis=config['camera']['cc_color_temp']
        if axis!=[2400,3050,5550,9100] or config['camera']['color_gamut']!=[0,1] or len(values)!=49152:
            raise ValueError('Unexpected photographic LUT axes or payload extent')
        source_payload=struct.pack('<49152I',*values)
        payload_sha=hashlib.sha256(source_payload).hexdigest()
        if payload_sha!='0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911':
            raise ValueError('Packed camera LUT payload mismatch')
        with tempfile.TemporaryDirectory(prefix='hb-native-lut-') as temp:
            input_path=Path(temp)/'camera_lut_words.bin'
            output_path=Path(temp)/'prepared_profiles.bin'
            input_path.write_bytes(source_payload)
            argv.extend([str(input_path),str(output_path)])
            child=subprocess.run(argv,env=env,capture_output=True,text=True,
                                 timeout=20,preexec_fn=limits)
            records=[json.loads(line) for line in child.stdout.splitlines() if line.startswith('{')]
            cases=[r for r in records if 'case' in r]
            outputs=output_path.read_bytes() if output_path.exists() else b''
            if len(outputs)!=10*6144*4:
                raise ValueError(f'Unexpected output length: {len(outputs)}')
            for k,case in enumerate(cases):
                payload=outputs[k*6144*4:(k+1)*6144*4]
                cct,gamut=case['cct'],case['gamut']
                interval=0 if cct<axis[0] else min(2,max(i for i,x in enumerate(axis) if x<=cct))
                fraction=0 if cct<axis[0] else 256 if cct>=axis[-1] else (cct-axis[interval])*256//(axis[interval+1]-axis[interval])
                reference=[]
                start=(interval+4*gamut)*6144
                for word_a,word_b in zip(values[start:start+6144],values[start+6144:start+12288]):
                    word=0
                    for shift in (0,16):
                        a=(word_a>>shift)&65535
                        b=(word_b>>shift)&65535
                        if a>=32768:a-=65536
                        if b>=32768:b-=65536
                        word|=((a+(b-a)*fraction//256)&65535)<<shift
                    reference.append(word)
                reference_payload=struct.pack('<6144I',*reference)
                case['output_sha256']=hashlib.sha256(payload).hexdigest()
                case['python_reference_sha256']=hashlib.sha256(reference_payload).hexdigest()
                case['python_reference_all_bytes_match']=payload==reference_payload
                case['passed']=case['passed'] and payload==reference_payload
            payload_metadata={'config_sha256':sha256(args.config),
                              'source_payload_words':49152,'source_payload_bytes':len(source_payload),
                              'source_payload_sha256':payload_sha,'output_words_per_case':6144,
                              'output_lanes_per_case':12288,'output_bytes_total':len(outputs),
                              'temporary_payload_files_deleted':True,
                              'photographic_payload_in_result':False}
        expected_cases=10
    else:
        child=subprocess.run(argv,env=env,capture_output=True,text=True,
                             timeout=20,preexec_fn=limits)
        records=[json.loads(line) for line in child.stdout.splitlines() if line.startswith('{')]
        cases=[r for r in records if 'case' in r]
        expected_cases=12
    passed=child.returncode==0 and len(cases)==expected_cases and all(c['passed'] for c in cases)
    result={
        'firmware':'Hasselblad X2D II 100C 1.3.16.2',
        'library':'librcam.so','library_sha256':LIB_SHA256,'symbols':identities,
        'method':'Original library functions through original Android 9 Bionic under QEMU user mode; no dependency stubs or replacement LUT function',
        'fixture':('Original camera LUT: eight profiles, each 6144 packed signed-16-pair words; four CCT knots and both gamuts' if args.config else 'Eight synthetic profiles, each seven packed signed-16-pair words; four CCT knots and two gamut selections'),
        'source_sha256':sha256(source),'probe_sha256':sha256(binary),
        'runner_sha256':sha256(Path(__file__)),
        'runtime_sha256':{'qemu':sha256(args.qemu),'linker64':sha256(root/'system/bin/linker64'),
                          'libc.so':sha256(root/'system/lib64/libc.so')},
        'build_command':build,'run_command':argv,
        'environment':{'LD_LIBRARY_PATH':env['LD_LIBRARY_PATH']},
        'bounds':{'wall_timeout_seconds':20,'cpu_limit_seconds':15,'core_limit_bytes':0},
        'exit':child.returncode,'stdout':child.stdout,'stderr':child.stderr,
        'cases':cases,'case_count':len(cases),'all_passed':passed,
        'photographic_lut_payload_used':bool(args.config),'real_asset_validation':payload_metadata,
        'per_pixel_colour_renderer_validated':False,
        'limitations':['Only the bounded two-axis, positive-word-count domain is established.',
                       'The LUT-generation callers and camera assets are identified statically; no complete capture pipeline is executed.',
                       'Successful matching-runtime execution does not establish normal app linker-namespace compatibility on a modern phone.'],
    }
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_count':len(cases),'all_passed':passed,'exit':child.returncode,
                      'output':str(args.output)}))
    if not passed: raise SystemExit(1)

if __name__=='__main__':
    main()
