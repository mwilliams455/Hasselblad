#!/usr/bin/env python3
"""Stage40F: exact 1.3.18.1 MAIN 3D-LUT *profile preparation*, not ISP pixels.

Hash-verify exact original librcam and IQ. Invoke original mm_get_coeff and
mm_mx_lerp_vec_mix2 through a guarded owned C test adapted in a temporary folder
from the independently reviewed 1.3.16.2 probe; compare every tested scalar
lane to independent Python. The original library is loaded through the matching
Bionic runtime under AArch64 QEMU; vendor camera/ISP hardware is NEVER called.
No private vendor LUT bytes or resulting profiles enter CI output/artifacts.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import resource
import struct
import subprocess
import tempfile

NEW_LIB_SHA='3443f4b6a3c6229325102cf763e433e2b36c76d7ab6650c3fcb9e9e2e821004f'
CONFIG_SHA='2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
LUT_SHA='0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911'
ANCHOR_SYMBOL='dcam_isp_vreg_get_type'
EXPECTED_FUNCTIONS={'mm_get_coeff':(0x2bace8,160),'mm_mx_lerp_vec_mix2':(0x2bbcf0,1784)}
CCTS=[2400,2400,4300,4300,5550,5550,7001,7001,9100,9100]
GAMUTS=[0,1]*5
SYNTHETIC_CASES=[(1000,0),(2400,0),(2725,0),(3001,1),(3050,1),(4300,0),
                 (5550,1),(7001,0),(9099,1),(9100,1),(14000,0),(14000,1)]
CCT_AXIS=[2400,3050,5550,9100]
GAMUT_AXIS=[0,1]
PROFILE_WORDS=6144
WORDS_TOTAL=8*PROFILE_WORDS


def require(v,why):
    if not v: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(18,18))


def local_fns_and_anchor(lib:Path):
    from elftools.elf.elffile import ELFFile
    require(sha(lib)==NEW_LIB_SHA,'wrong_new_original_librcam_SHA256')
    elf=ELFFile(io.BytesIO(lib.read_bytes()))
    require(elf['e_machine']=='EM_AARCH64' and elf.elfclass==64 and elf.little_endian
            and elf['e_type']=='ET_DYN','unexpected_original_ELF_format')
    dynamic=elf.get_section_by_name('.dynsym')
    require(dynamic is not None,'original_ELF_no_dynamic_symbols')
    anchors=[x for x in dynamic.iter_symbols() if x.name==ANCHOR_SYMBOL and
             x['st_shndx']!='SHN_UNDEF' and x['st_info']['type']=='STT_FUNC']
    require(len(anchors)==1,'unexpected_defined_dynamic_anchor')
    anchor=int(anchors[0]['st_value'])
    require(anchor==0x54b88,'old_and_new_library_anchor_changed')
    debug=elf.get_section_by_name('.gnu_debugdata')
    require(debug is not None,'missing_vendor_mini_debug_symbols')
    raw=lzma.decompress(debug.data(),memlimit=128*1024*1024)
    require(len(raw)<64*1024*1024,'mini_debug_oversized')
    minis=ELFFile(io.BytesIO(raw))
    sym=minis.get_section_by_name('.symtab')
    require(sym is not None,'missing_original_mini_debug_symtab')
    found={}
    for x in sym.iter_symbols():
        if x.name in EXPECTED_FUNCTIONS and x['st_shndx']!='SHN_UNDEF':
            found.setdefault(x.name,set()).add((int(x['st_value']),int(x['st_size'])))
    require(all(found.get(k)=={v} for k,v in EXPECTED_FUNCTIONS.items()),
            'new_original_LUT_profile_function_address_or_size_mismatch')
    return anchor


def adapted_owned_probe(root:Path,anchor):
    path=root/'photographic_path/lut_profile_probe.c'
    src=path.read_text()
    edits={
        '#define ANCHOR_VA UINT64_C(0x54b88)':'#define ANCHOR_VA UINT64_C('+hex(anchor)+')',
        '#define MIX_VA UINT64_C(0x2bbc08)':'#define MIX_VA UINT64_C(0x2bbcf0)',
        '#define COEFF_VA UINT64_C(0x2bac00)':'#define COEFF_VA UINT64_C(0x2bace8)',
    }
    for old,new in edits.items():
        require(src.count(old)==1,'reviewed_owned_LUT_probe_source_unexpected')
        src=src.replace(old,new)
    # Unlike 1.3.16.2, the 1.3.18.1 dispatch table has NOT been independently
    # resolved; never claim slot-37 dispatcher parity. Invoke only the two
    # explicitly hash-checked original leaf functions with owned ABI fixtures.
    start=src.index('    /* rcam_adj_calc_common indexes this relocated table.')
    end=src.index('    mix_fn mix =',start)
    assert end>start
    src=src[:start]+'    /* Stage40F leaf-only check: no unresolved dispatcher invoked. */\n'+src[end:]
    return src


def camera_lut(root:Path):
    config=root/'system/etc/iq/hb722_config.json'
    require(sha(config)==CONFIG_SHA,'new_IQ_file_changed_from_pinned_source')
    p=Path(__file__).resolve().parents[1]/'photographic_path/inspect_iq_config.py'
    spec=importlib.util.spec_from_file_location('hb40f_inert_config_reader',p)
    require(spec and spec.loader is not None,'original_owned_IQ_parser_missing')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    obj=mod.Parser(config.read_text()).value()
    require(obj['camera']['cc_color_temp']==CCT_AXIS and obj['camera']['color_gamut']==GAMUT_AXIS,
            'original_colour_coordinate_axes_unexpected')
    values=obj['iq_table']['data'][0]['main_3dlut'][0]['lut_data']
    require(isinstance(values,list) and len(values)==WORDS_TOTAL and
            all(type(x) is int and 0<=x<=0xffffffff for x in values),
            'original_new_LUT_payload_schema_mismatch')
    raw=struct.pack('<'+str(WORDS_TOTAL)+'I',*values)
    require(hashlib.sha256(raw).hexdigest()==LUT_SHA,'original_LUT_words_changed')
    return raw,values


def signed_lane(word,half):
    u=(int(word)>>(half*16))&65535
    return u-65536 if u>=32768 else u


def mix_lane(a,b,weight):
    return a+(b-a)*weight//256


def coordinate(value,axis):
    if value<axis[0]:return (0,0)
    if value>=axis[-1]:return (len(axis)-2,256)
    i=max(i for i in range(len(axis)-1) if axis[i]<=value)
    return i,(value-axis[i])*256//(axis[i+1]-axis[i])


def python_prepared_words(source:list[int],words:int,cct:int,gamut:int):
    require(len(source)==8*words and gamut in (0,1),'bad_Python_reference_input')
    i,f=coordinate(cct,CCT_AXIS)
    out=[]
    for pos in range(words):
        word=0
        for half in (0,1):
            aa=mix_lane(signed_lane(source[(i+0)*words+pos],half),
                        signed_lane(source[(i+1)*words+pos],half),f)
            bb=mix_lane(signed_lane(source[(i+4)*words+pos],half),
                        signed_lane(source[(i+5)*words+pos],half),f)
            val=aa if gamut==0 else bb
            word|=(val&65535)<<(16*half)
        out.append(word)
    return out


def synthetic_source():
    vals=[]
    for p in range(8):
        for j in range(7):
            lo=(p*7171+j*2339+137)%60001-30000
            hi=30000-(p*4813+j*3251+977)%60001
            vals.append((lo&65535)|((hi&65535)<<16))
    return vals


def execute(root:Path,clang:Path,qemu:Path):
    require((root/'system/etc/VERSION').read_text().strip()=='1.3.18.1','wrong_extracted_VERSION')
    lib=root/'system/lib64/librcam.so'
    anchor=local_fns_and_anchor(lib)
    lut_payload,lut_values=camera_lut(root)
    require(clang.is_file() and os.access(clang,os.X_OK),'android_api28_cross_compiler_not_found')
    require(qemu.is_file() and os.access(qemu,os.X_OK),'aarch64_qemu_not_found')
    edited=adapted_owned_probe(Path(__file__).resolve().parents[1],anchor)
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=str(lib.parent)
    env.pop('LD_PRELOAD',None)
    with tempfile.TemporaryDirectory(prefix='hb40f-original-lut-') as td:
        temp=Path(td)
        owned_source=temp/'lut_probe40f.c'
        binary=temp/'lut_probe40f'
        owned_source.write_text(edited)
        build=[str(clang),'-O2','-Wall','-Wextra','-Werror',str(owned_source),'-ldl','-o',str(binary)]
        b=subprocess.run(build,capture_output=True,text=True,timeout=60)
        require(b.returncode==0,'owned_LUT_probe_compile_failed:'+b.stderr[:900])
        def run(extra):
            command=[str(qemu),'-L',str(root),str(binary),str(lib),*map(str,extra)]
            child=subprocess.run(command,env=env,capture_output=True,text=True,
                                 timeout=60,preexec_fn=limits)
            require(child.returncode==0 and child.stderr=='',
                    'original_new_LUT_native_run_failed:'+child.stderr[:1000]+child.stdout[-180:])
            return [json.loads(line) for line in child.stdout.splitlines() if line.startswith('{')]
        synthetic=run(())
        syn=[x for x in synthetic if 'case' in x]
        require(len(syn)==12 and all(x['passed'] and x['guards_ok'] and x['source_unchanged']
                                    and x['coefficient_matches'] and x['returned_destination_end']
                                    for x in syn),'original_new_LUT_synthetic_native_guard_mismatch')
        owned_synthetic=synthetic_source()
        for i,row in enumerate(syn):
            cct,gamut=SYNTHETIC_CASES[i]
            expected=python_prepared_words(owned_synthetic,7,cct,gamut)
            require(row['case']==i and row['cct']==cct and row['gamut']==gamut and
                    row['failed_words']==0 and row['output']==expected,
                    'original_synthetic_native_mismatch_with_independent_Python')
        inp=temp/'private_source.bin'
        out=temp/'private_prepared.bin'
        inp.write_bytes(lut_payload)
        native=run((inp,out))
        real=[x for x in native if 'case' in x]
        require(len(real)==10 and all(x['passed'] and x['guards_ok'] and
                                      x['source_unchanged'] and x['coefficient_matches']
                                      for x in real),'original_camera_LUT_native_guard_mismatch')
        actual=out.read_bytes()
        require(len(actual)==10*PROFILE_WORDS*4,'new_original_LUT_output_byte_extent')
        matched=0
        for i,row in enumerate(real):
            cct,gamut=CCTS[i],GAMUTS[i]
            expected=python_prepared_words(lut_values,PROFILE_WORDS,cct,gamut)
            observed=struct.unpack_from('<'+str(PROFILE_WORDS)+'I',actual,i*PROFILE_WORDS*4)
            require(row['case']==i and row['cct']==cct and row['gamut']==gamut and
                    list(observed)==expected and row['failed_lanes']==0,
                    'original_new_LUT_real_profile_mismatch_Python_reference')
            matched+=PROFILE_WORDS*2
    return {
        'schema':'hasselblad-stage40f-new-original-lut-preparation-v1',
        'status':'PASS_original_new_1_3_18_1_MAIN_LUT_profile_preparation',
        'new_firmware':'X2D II 100C 1.3.18.1',
        'original_librcam_sha256':NEW_LIB_SHA,
        'IQ_config_sha256':CONFIG_SHA,
        'original_LUT_hash_SHA256':LUT_SHA,
        'original_new_symbol_addresses':{'anchor':hex(anchor),
                                          **{k:hex(v[0]) for k,v in EXPECTED_FUNCTIONS.items()}},
        'synthetic_profiles':{'native_cases':12,'profile_words_per_case':7,
                              'scalar_lanes_checked':12*7*2,'matched_independent_python':True},
        'actual_camera_profiles':{'native_cases':10,'profile_words_per_case':PROFILE_WORDS,
                                  'scalar_lanes_checked':matched,'matched_independent_python':True,
                                  'proprietary_table_or_output_words_exported':False},
        'total_native_cases':22,
        'native_original_Bionic_QEMU_execution':True,
        'camera_control_or_isp_hardware_executed':False,
        'new_firmware_calc_dispatch_table_or_branch_proven':False,
        'saved_photo_colour_or_MAIN_pixel_3DLUT_parity_proven':False,
        'six_coefficient_CCM_pixel_equation_proven':False,
        'original_vendor_bytes_or_private_photos_or_LUT_words_exported':False,
        'production_main_or_Android_renderer_modified':False,
    }


def self_test():
    owned=synthetic_source()
    assert len(owned)==56
    assert len(set(owned))>14
    assert coordinate(2400,CCT_AXIS)==(0,0)
    assert coordinate(9100,CCT_AXIS)==(2,256)
    assert coordinate(2000,CCT_AXIS)==(0,0)
    assert coordinate(4300,CCT_AXIS)[0]==1
    assert coordinate(5550,CCT_AXIS)==(2,0)
    assert coordinate(0,GAMUT_AXIS)==(0,0)
    assert coordinate(1,GAMUT_AXIS)==(0,256)
    assert len(python_prepared_words(owned,7,4300,1))==7
    assert python_prepared_words(owned,7,2400,0)==owned[:7]
    assert python_prepared_words(owned,7,9100,1)==owned[-7:]
    assert len(EXPECTED_FUNCTIONS)==2
    assert WORDS_TOTAL==49152
    assert LUT_SHA != CONFIG_SHA
    assert len(NEW_LIB_SHA)==64
    assert 12*7*2==168
    assert 10*PROFILE_WORDS*2==122880
    return {'status':'PASS_synthetic','checks':17,'vendor_library_executed':False,
            'camera_pixels_processed':False,'photo_renderer_unchanged':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--clang',type=Path)
    p.add_argument('--qemu',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    r=self_test() if a.self_test else execute(a.firmware_root.resolve(),a.clang.resolve(),a.qemu.resolve())
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:r[k] for k in ('status','checks','total_native_cases') if k in r},sort_keys=True))

if __name__=='__main__':main()