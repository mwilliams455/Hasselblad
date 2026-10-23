#!/usr/bin/env python3
"""Stage40E: execute exact new X2D II librcam CCM interpolation under Bionic/QEMU.

Adapt the unchanged, reviewed Stage17 original *owned* C harness to the new
firmware's independently verified symbol virtual addresses; exercise original
vendor functions with owned synthetic fixtures and the privately held exact IQ
CCM table. No proprietary input/output arrays or original vendor binary bytes
are written into public reports. No camera service or ISP hardware is used.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import tempfile
import io
import lzma

EXPECTED_LIB='3443f4b6a3c6229325102cf763e433e2b36c76d7ab6650c3fcb9e9e2e821004f'
EXPECTED_CONFIG='2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
EXPECTED_CCMPROFILE='59d1b6c8a291280a8749f5ca190370e5dbff8ce0e6694a7da779ae5488ae641e'
EXPECTED_FUNCTIONS={'mm_get_coeff':(0x2bace8,160),'mm_mx_lerp_gap':(0x2bb220,1228)}
CCT=[2000,2400,3001,3050,4300,5550,7001,9100,10000]
WEIGHTS=[0,1,64,128,255,256]
AXIS=[2400,3050,5550,9100]
STRIDE=96


def require(ok,msg):
    if not ok:raise ValueError(msg)


def file_sha(p:Path):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))


def symbol_identity(path:Path):
    from elftools.elf.elffile import ELFFile
    require(file_sha(path)==EXPECTED_LIB,'wrong_original_new_librcam_sha256')
    with path.open('rb') as f:
        data=f.read()
    elf=ELFFile(io.BytesIO(data))
    require(elf['e_machine']=='EM_AARCH64' and elf.elfclass==64 and elf.little_endian
            and elf['e_type']=='ET_DYN','unexpected_new_elf')
    sym=elf.get_section_by_name('.dynsym')
    require(sym is not None,'new_ELF_missing_dynamic_symbols')
    anchors=[s for s in sym.iter_symbols() if s.name=='dcam_isp_vreg_get_type'
             and s['st_shndx']!='SHN_UNDEF']
    require(len(anchors)==1,'missing_or_ambiguous_new_lib_export')
    anchor=int(anchors[0]['st_value'])
    require(0<anchor<0x1000000,'original_new_export_out_of_range')
    compressed=elf.get_section_by_name('.gnu_debugdata')
    require(compressed is not None,'original_new_lib_debug_symbols_not_available')
    debugdata=lzma.decompress(compressed.data(),memlimit=128*1024*1024)
    require(len(debugdata)<64*1024*1024,'debug_symbols_oversize')
    inner=ELFFile(io.BytesIO(debugdata))
    section=inner.get_section_by_name('.symtab')
    require(section is not None,'original_mini_debug_symtab_missing')
    found={}
    for s in section.iter_symbols():
        if s.name in EXPECTED_FUNCTIONS and s['st_shndx']!='SHN_UNDEF':
            found.setdefault(s.name,set()).add((int(s['st_value']),int(s['st_size'])))
    require(all(found.get(name)=={pair} for name,pair in EXPECTED_FUNCTIONS.items()),
            'original_new_CCM_function_addresses_or_extents_changed')
    return anchor


def original_source(root:Path,anchor:int)->tuple[str,Path,Path]:
    original=root/'main_colour_20261019/ccm'
    source=(original/'ccm_prepare_probe.c').read_text()
    patches={
      'uintptr_t bias=(uintptr_t)anchor-UINT64_C(0x54b88);':
       'uintptr_t bias=(uintptr_t)anchor-UINT64_C('+hex(anchor)+');',
      'GetCoeff get_coeff=(GetCoeff)(bias+UINT64_C(0x2bac00));':
       'GetCoeff get_coeff=(GetCoeff)(bias+UINT64_C(0x2bace8));',
      'LerpGap lerp_gap=(LerpGap)(bias+UINT64_C(0x2bb138));':
       'LerpGap lerp_gap=(LerpGap)(bias+UINT64_C(0x2bb220));',
    }
    for before,after in patches.items():
        require(source.count(before)==1,'original_owned_C_probe_layout_changed')
        source=source.replace(before,after)
    return source,original/'ccm_prepare.c',original/'ccm_prepare.h'


def profile_from_inert_IQ(root:Path)->list[int]:
    source=root/'system/etc/iq/hb722_config.json'
    require(file_sha(source)==EXPECTED_CONFIG,'new_version_IQ_config_does_not_match_pinned_old')
    parser_path=Path(__file__).resolve().parents[1]/'photographic_path/inspect_iq_config.py'
    spec=importlib.util.spec_from_file_location('hb40e_inert_iq_parser',parser_path)
    mod=importlib.util.module_from_spec(spec)
    require(spec.loader is not None,'missing_owned_IQ_parser')
    spec.loader.exec_module(mod)
    parsed=mod.Parser(source.read_text()).value()
    values=parsed['iq_table']['data'][0]['main_ccm'][0]['lmtx_fw']
    require(isinstance(values,list) and len(values)==768 and
            all(isinstance(v,int) and -32768<=v<=32767 for v in values),
            'new_version_original_global_CCM_profile_shape_changed')
    payload=struct.pack('<768i',*values)
    require(hashlib.sha256(payload).hexdigest()==EXPECTED_CCMPROFILE,
            'new_firmware_original_camera_CCM_table_changed')
    return values


def cct_coordinate(cct:int)->tuple[int,int]:
    if cct<AXIS[0]:return 0,0
    if cct>=AXIS[-1]:return 2,256
    index=max(i for i in range(len(AXIS)-1) if AXIS[i]<=cct)
    return index,(cct-AXIS[index])*256//(AXIS[index+1]-AXIS[index])


def python_reference(values,cct,weight):
    index,fraction=cct_coordinate(cct)
    def lerp(a,b,w):return a+(b-a)*w//256
    out=[]
    for k in range(96):
        a=index*96+k
        low=lerp(values[a],values[a+96],fraction)
        high=lerp(values[a+384],values[a+480],fraction)
        out.append(lerp(low,high,weight))
    return struct.pack('<96i',*out)


def inspect(root:Path,clang:Path,qemu:Path)->dict:
    require((root/'system/etc/VERSION').read_text().strip()=='1.3.18.1',
            'new_firmware_version_missing')
    lib=root/'system/lib64/librcam.so'
    anchor=symbol_identity(lib)
    probe_source,portable_c,header=original_source(Path(__file__).resolve().parents[1],anchor)
    values=profile_from_inert_IQ(root)
    require(clang.is_file() and os.access(clang,os.X_OK),'missing_android_arm64_clang')
    require(qemu.is_file() and os.access(qemu,os.X_OK),'missing_aarch64_qemu')
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=str(lib.parent)
    env.pop('LD_PRELOAD',None)
    fixtures={
     'synthetic_dense_signed':[(p*19073+k*1297+p*k*173)%65001-32500
                               for p in range(8) for k in range(96)],
     'synthetic_signed_limits':[(-32768 if (p+k)%2 else 32767)
                                for p in range(8) for k in range(96)],
     'original_global_still_CCM_private':values,
    }
    records=[]
    with tempfile.TemporaryDirectory(prefix='hb40e-original-ccm-') as td:
        temp=Path(td)
        rewritten=temp/'ccm_probe40e.c'
        rewritten.write_text(probe_source)
        binary=temp/'ccm_probe40e'
        build=[str(clang),'-O2','-Wall','-Wextra','-Werror',
               '-I',str(header.parent),str(rewritten),str(portable_c),'-ldl','-o',str(binary)]
        cp=subprocess.run(build,capture_output=True,text=True,timeout=60)
        require(cp.returncode==0,'original_C_probe_cross_compile_failed:'+cp.stderr[:800])
        for name,fixture in fixtures.items():
            inputpath=temp/'input.bin'
            outpath=temp/'output.bin'
            payload=struct.pack('<768i',*fixture)
            inputpath.write_bytes(payload)
            argv=[str(qemu),'-L',str(root),str(binary),str(lib),str(inputpath),str(outpath)]
            child=subprocess.run(argv,env=env,capture_output=True,text=True,
                                 timeout=45,preexec_fn=limits)
            require(child.returncode==0 and child.stderr=='',
                    f'original_new_runtime_execution_failed_{name}:'+child.stderr[:900])
            calls=[json.loads(line) for line in child.stdout.splitlines() if line.startswith('{')]
            require(len(calls)==54 and all(c.get('pass') and c.get('guards_ok') and c.get('inputs_unchanged')
                                           for c in calls),'owned_C_or_original_function_check_failed')
            raw=outpath.read_bytes()
            require(len(raw)==54*96*4,'original_aggregate_output_extent_changed')
            successes=0
            for n,case in enumerate(calls):
                cct=CCT[n//6];weight=WEIGHTS[n%6]
                expected=python_reference(fixture,cct,weight)
                actual=raw[n*384:(n+1)*384]
                require(case['cct']==cct and case['secondary_weight_q8']==weight and
                        case['mismatches']==0 and actual==expected,
                        'original_native_result_differs_from_independent_Python')
                successes+=96
            records.append({'fixture':name,'native_cases':54,'scalar_outputs_checked':successes,
                            'all_native_and_independent_Python_outputs_match':True,
                            'original_vendor_coefficient_values_exported':False})
    return {
      'schema':'hasselblad-stage40e-new-original-ccm-native-arithmetic-v1',
      'status':'PASS_original_new_1_3_18_1_CCM_preparation_162_cases',
      'original_firmware_version':'1.3.18.1',
      'new_librcam_sha256':EXPECTED_LIB,
      'original_global_IQ_sha256':EXPECTED_CONFIG,
      'vendor_CCM_table_identity_sha256':EXPECTED_CCMPROFILE,
      'original_new_symbol_addresses':{'anchor':hex(anchor),
           **{k:hex(v[0]) for k,v in EXPECTED_FUNCTIONS.items()}},
      'fixture_reports':records,
      'total_cases':sum(x['native_cases'] for x in records),
      'total_scalar_outputs_checked':sum(x['scalar_outputs_checked'] for x in records),
      'all_results_original_native_equal_portable_C_and_independent_Python':True,
      'Android_Bionic_original_library_executed_under_QEMU':True,
      'native_initializers_may_run':True,
      'camera_control_or_hardware_registers_called':False,
      'saved_image_colour_or_original_CCM_pixel_operator_proven':False,
      'original_vendor_instruction_or_tuning_values_or_images_exported':False,
      'photographic_renderer_modified':False,
      'main_branch_modified':False,
    }


def synthetic():
    xs=[(p*19073+k*1297+p*k*173)%65001-32500
        for p in range(8) for k in range(96)]
    assert len(xs)==768
    assert all(-32768<=x<=32767 for x in xs)
    assert cct_coordinate(2000)==(0,0)
    assert cct_coordinate(2400)==(0,0)
    assert cct_coordinate(3050)==(1,0)
    assert cct_coordinate(9100)==(2,256)
    assert cct_coordinate(10000)==(2,256)
    assert 0<cct_coordinate(4300)[1]<256
    a=python_reference(xs,4300,128)
    assert len(a)==384
    assert len(struct.unpack('<96i',a))==96
    assert python_reference(xs,2400,0)==struct.pack('<96i',*xs[:96])
    assert python_reference(xs,9100,256)==struct.pack('<96i',*xs[672:768])
    assert len(EXPECTED_LIB)==64
    assert len(EXPECTED_CONFIG)==64
    assert len(EXPECTED_CCMPROFILE)==64
    assert len(EXPECTED_FUNCTIONS)==2
    assert 54*96*3==15552
    return {'status':'PASS_synthetic','checks':16,
            'original_vendor_code_executed':False,'camera_pixels_processed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--clang',type=Path)
    p.add_argument('--qemu',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.self_test:r=synthetic()
    else:
        require(a.firmware_root is not None and a.clang is not None and a.qemu is not None and a.output is not None,
                'new_firmware_root_compiler_qemu_and_receipt_required')
        r=inspect(a.firmware_root.resolve(),a.clang.resolve(),a.qemu.resolve())
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:r[k] for k in ('status','checks','total_cases','total_scalar_outputs_checked') if k in r},sort_keys=True))

if __name__=='__main__':main()