#!/usr/bin/env python3
"""Inspect a private Phocus APK and replay one bounded native pixel operator.

Exports own analysis, structural facts and synthetic aggregates only. Native
instructions are read from the separately supplied APK; no vendor bytes, shader
source, calibration tables, keys or photographs are included in the receipt.
"""
import argparse
import collections
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile
from importlib.metadata import version

import numpy as np
from loguru import logger
from androguard.core.apk import APK
from androguard.core.dex import DEX
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
    UC_ARM64_REG_X3, UC_ARM64_REG_X4, UC_ARM64_REG_X5, UC_ARM64_REG_X30,
    UC_ARM64_REG_SP, UC_ARM64_REG_PC, UC_ARM64_REG_CPACR_EL1)

APK_SHA = '5ee52bbb2b7a3fa708628ba251b409a551ae099697668427cf54b523328ccf68'
LIB_PATH = 'lib/arm64-v8a/libcrosssdk.so'
NAMES = {
 'pixels': '_ZN14CVectorMethods24ColorNormalCorrectPixelsEP16CColorCorrectionPtS2_ib',
 'matrix_index': '_ZNK9Matrix3x3ixEi',
 'matrix_multiply': '_ZNK9Matrix3x3mlE6CArrayIdLi3E23Matrix3x1InitializationE',
 'scaled_lookup': '_ZNK11Scaled2DLUT6LookupE6CArrayIdLi2EdEb',
 'lookup': '_ZNK11Scaled2DLUT11LookupIndexE6CArrayIdLi2EdEb',
 'gray_weight': '_ZNK16CColorCorrection19CalculateGrayWeightEddb',
}
GPU_FILTER = '_ZN19CColorCorrectFilter15FilterResultGpuER19CGpuPipelineManager6CXRectS2_'
JNI_RAW = 'Java_com_hasselblad_crosssdk_utils_RawUtil_getRawBitmapByRect'
SHADERS = ('color_correct_computeShaderSource', 'colorCorrectAll_fragmentShaderSource',
           'gamma_hasselblad_fragmentShaderSource', 'filmcurve_fragmentShaderSource')


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Binary:
    def __init__(self, data):
        self.data = data
        self.elf = ELFFile(io.BytesIO(data))
        assert self.elf['e_machine'] == 'EM_AARCH64'
        table = self.elf.get_section_by_name('.dynsym')
        self.symbols = {s.name: s for s in table.iter_symbols() if s.name and s['st_shndx'] != 'SHN_UNDEF'}
        self.segments = [s for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.plt = {}
        plt = self.elf.get_section_by_name('.plt')
        rel = self.elf.get_section_by_name('.rela.plt')
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        for i, relocation in enumerate(rel.iter_relocations()):
            address = plt['sh_addr'] + 32 + 16*i
            name = table.get_symbol(relocation['r_info_sym']).name
            ins = list(md.disasm(self.read(address, 16), address))
            assert [x.mnemonic for x in ins] == ['adrp', 'ldr', 'add', 'br']
            page = int(ins[0].op_str.split('#')[1], 16)
            offset = int(ins[2].op_str.split('#')[1], 16)
            assert page + offset == relocation['r_offset']
            self.plt[address] = name

    def read(self, address, length):
        for segment in self.segments:
            if segment['p_vaddr'] <= address and address+length <= segment['p_vaddr']+segment['p_filesz']:
                start = segment['p_offset'] + address-segment['p_vaddr']
                return self.data[start:start+length]
        raise ValueError(f'Unmapped file range {address:#x}+{length}')

    def function(self, name):
        symbol = self.symbols[name]
        assert symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_size'] > 0
        code = self.read(symbol['st_value'], symbol['st_size'])
        return symbol['st_value'], code

    def edges(self, name):
        address, code = self.function(name)
        edges = []
        for ins in Cs(CS_ARCH_ARM64, CS_MODE_ARM).disasm(code, address):
            word = struct.unpack_from('<I', code, ins.address-address)[0]
            if word & 0x7c000000 != 0x14000000:
                continue
            delta = word & 0x3ffffff
            if delta & 0x2000000:
                delta -= 0x4000000
            target = ins.address + 4*delta
            assert ins.mnemonic in ('b', 'bl') and int(ins.op_str[1:], 16) == target
            if target in self.plt:
                edges.append({'callsite': hex(ins.address), 'instruction': ins.mnemonic,
                              'plt_address': hex(target), 'callee': self.plt[target]})
        return edges

    def shader_records(self):
        slots = {self.symbols[n]['st_value']: n for n in SHADERS}
        pointers = {}
        for relocation in self.elf.get_section_by_name('.rela.dyn').iter_relocations():
            if relocation['r_offset'] in slots:
                assert relocation['r_info_type'] == 1027
                pointers[slots[relocation['r_offset']]] = relocation['r_addend']
        result = []
        for name in SHADERS:
            pointer = pointers[name]
            source = self.read(pointer, 16384).split(b'\0', 1)[0]
            assert source.startswith(b'#version') and b'void main()' in source
            result.append({'symbol': name, 'source_address': hex(pointer),
                           'bytes': len(source), 'sha256': sha(source),
                           'readable_complete_main_function': True})
        return result


def replay(binary):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    bodies = {name: binary.function(name) for name in NAMES.values()}
    pages = set()
    ranges = []
    for name, (address, code) in bodies.items():
        ranges.append((address,address+len(code)))
        for page in range(address & ~4095, (address+len(code)+4095)&~4095, 4096):
            if page not in pages:
                uc.mem_map(page,4096); pages.add(page)
        uc.mem_write(address,code)
    redirects = {p:bodies[n][0] for p,n in binary.plt.items() if n in bodies}
    for address in redirects:
        page = address & ~4095
        if page not in pages:
            uc.mem_map(page,4096); pages.add(page)
        uc.mem_write(address,binary.read(address,16))
    obj, lut, grad, inp, out = 0x10000000,0x10010000,0x10020000,0x10080000,0x10090000
    for address,size in [(obj,4096),(lut,4096),(grad,0x40000),(inp,0x10000),(out,0x10000),
                         (0x20000000,0x100000),(0x30000000,4096)]:
        uc.mem_map(address,size)
    uc.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
    sentinel=0x30000000
    visits=collections.Counter()
    def guard(cpu,address,size,user):
        if address==sentinel:
            cpu.emu_stop(); return
        if address in redirects:
            visits[binary.plt[address]]+=1
            cpu.reg_write(UC_ARM64_REG_PC,redirects[address]); return
        if not any(lo<=address<hi for lo,hi in ranges):
            raise AssertionError(f'Unexpected execution at {address:#x}')
    uc.hook_add(UC_HOOK_CODE,guard)
    rgb_to_ycc=np.array([[.25,.5,.25],[1.,-1.,0.],[0.,-1.,1.]],dtype='<f8')
    ycc_to_rgb=np.array([[1.,.75,-.25],[1.,-.25,-.25],[1.,-.25,.75]],dtype='<f8')
    rng=np.random.default_rng(410023)
    basis=np.array([[0,0,0],[65535,0,0],[0,65535,0],[0,0,65535],
                    [65535,65535,0],[65535,0,65535],[0,65535,65535],[65535]*3],dtype='<u2')
    ramps=np.repeat(np.array([1,2,7,255,256,1023,4095,16383,32767,65534],dtype='<u2')[:,None],3,axis=1)
    pixels=np.vstack([basis,ramps,rng.integers(0,65536,(256,3),dtype=np.uint16)]).astype('<u2')
    source=pixels.tobytes(); uc.mem_write(inp,source)
    table=np.arange(65536,dtype='<f4');uc.mem_write(grad,table.tobytes())
    rows=[]
    # Synthetic maps and thresholds are deliberate fixtures, not Hasselblad
    # profiles or camera calibration. A 1-code tolerance is fixed before replay
    # for floating-point evaluation-order effects at integer truncation edges.
    for mapping in ('identity','chroma_mix','curved'):
        grid=np.empty((9,9,2),dtype='<f8')
        for y in range(9):
            for x in range(9):
                cb,cr=x-4.,y-4.
                if mapping=='identity': result=(cb,cr)
                elif mapping=='chroma_mix': result=(.75*cb+.125*cr,-.125*cb+cr)
                else: result=(cb+.0625*cb*cr,cr+.03125*cb*cb)
                grid[y,x]=result
        for protection in ('off','gray_and_shadow'):
            state=bytearray(0x300)
            state[8:8+72]=rgb_to_ycc.tobytes();state[0x50:0x50+72]=ycc_to_rgb.tobytes()
            high,low=(0.,-1.) if protection=='off' else (.4,.1)
            struct.pack_into('<dd',state,0xe0,high,low)
            struct.pack_into('<QQiiii',state,0x138,lut,lut,9,9,18,2)
            struct.pack_into('<5d',state,0x158,4.,4.,1.,1.,1.)
            struct.pack_into('<QQQ',state,0x188,grad,grad+0x40000,grad+0x40000)
            struct.pack_into('<4d',state,0x1b8,16384.,0.,1./32768.,.25)
            uc.mem_write(obj,bytes(state));uc.mem_write(lut,grid.tobytes())
            uc.mem_write(out,b'\xa5'*32+b'\xcc'*len(source)+b'\xa5'*32)
            values=(0,obj,out+32,inp,len(pixels),int(protection=='off'))
            for register,value in zip((UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,
                    UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_X5),values):
                uc.reg_write(register,value)
            uc.reg_write(UC_ARM64_REG_SP,0x200ff000);uc.reg_write(UC_ARM64_REG_X30,sentinel)
            uc.emu_start(bodies[NAMES['pixels']][0],sentinel,count=1000000)
            assert uc.reg_read(UC_ARM64_REG_PC)==sentinel,'Execution budget exhausted'
            actual=np.frombuffer(bytes(uc.mem_read(out+32,len(source))),dtype='<u2').reshape(-1,3)
            expected=[]
            for rgb in pixels.astype(float):
                yy,cb,cr=rgb_to_ycc@rgb
                if yy<=0:
                    expected.append([0,0,0]);continue
                x,y=np.clip(np.array([cb/yy,cr/yy])+4,0,8)
                x0,y0=int(x),int(y);x1,y1=min(x0+1,8),min(y0+1,8)
                dx,dy=x-x0,y-y0
                chroma=((grid[y0,x0]*(1-dx)+grid[y0,x1]*dx)*(1-dy)
                         +(grid[y1,x0]*(1-dx)+grid[y1,x1]*dx)*dy)
                ratio=np.max(np.abs(rgb-rgb.mean()))/rgb.mean()
                weight=(ratio-low)/(high-low) if ratio<high else 1.
                if protection!='off':
                    weight=min(weight,1. if yy>16384. else yy/32768.+.25)
                weight=max(0.,weight)
                converted=ycc_to_rgb@np.array([yy,chroma[0]*yy*weight,chroma[1]*yy*weight])
                expected.append(np.clip(converted,0,65535).astype(np.uint16))
            expected=np.asarray(expected,dtype='<u2')
            delta=np.abs(actual.astype(np.int32)-expected.astype(np.int32))
            assert delta.max()<=1,(mapping,protection,int(delta.max()))
            assert bytes(uc.mem_read(out,32))==b'\xa5'*32
            assert bytes(uc.mem_read(out+32+len(source),32))==b'\xa5'*32
            assert bytes(uc.mem_read(inp,len(source)))==source
            assert bytes(uc.mem_read(obj,len(state)))==state
            assert bytes(uc.mem_read(lut,grid.nbytes))==grid.tobytes()
            assert bytes(uc.mem_read(grad,table.nbytes))==table.tobytes()
            rows.append({'map':mapping,'protection':protection,'pixels':len(pixels),
                'channels':actual.size,'exact_channels':int(np.count_nonzero(delta==0)),
                'max_abs_u16_difference':int(delta.max()),'black_outputs_zero':bool(np.all(actual[0]==0)),
                'output_guards_and_all_inputs_unchanged':True})
    assert set(visits)==set(NAMES.values())-{NAMES['pixels']}
    return {'cases':rows,'total_pixels':sum(r['pixels'] for r in rows),
        'max_allowed_u16_difference':1,'original_functions_executed':len(bodies),
        'original_helper_dispatch_counts':dict(visits),
        'arithmetic_or_lookup_functions_stubbed':False,
        'plt_calls_redirected_to_original_function_bodies':True,
        'real_camera_calibration_or_photo_pixels_used':False,
        'whole_app_or_complete_raw_pipeline_executed':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apk',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True);args=ap.parse_args()
    original=args.apk.read_bytes();assert sha(original)==APK_SHA
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        assert z.testzip() is None
        entries=z.infolist();assert len(entries)==len({x.filename for x in entries})
        lib=z.read(LIB_PATH);dex=z.read('classes.dex')
        native=[{'path':i.filename,'bytes':i.file_size,'sha256':sha(z.read(i.filename))}
            for i in entries if i.filename.startswith('lib/') and i.filename.endswith('.so')]
        assets={prefix:{'count':sum(i.filename.startswith(prefix) for i in entries),
            'bytes':sum(i.file_size for i in entries if i.filename.startswith(prefix))}
            for prefix in ('assets/Colormaps/','assets/GMaps/')}
    logger.remove()
    apk=APK(original,raw=True)
    dex_object=DEX(dex)
    metadata={'package':apk.get_package(),'version_name':apk.get_androidversion_name(),
        'version_code':apk.get_androidversion_code(),'manifest_min_sdk':apk.get_min_sdk_version(),
        'manifest_target_sdk':apk.get_target_sdk_version(),
        'application_class':apk.get_attribute_value('application','name'),
        'signature_schemes_present':{'v1':apk.is_signed_v1(),'v2':apk.is_signed_v2(),'v3':apk.is_signed_v3()},
        'certificate_sha256':[sha(c.dump()) for c in apk.get_certificates()],
        'signature_cryptographically_verified':False,'signer_independently_matched_to_vendor':False,
        'visible_dex_classes':len(dex_object.get_classes()),
        'raw_util_class_visible_in_dex':any('crosssdk/utils/RawUtil;' in c.get_name() for c in dex_object.get_classes())}
    binary=Binary(lib)
    selected=[JNI_RAW,GPU_FILTER,*NAMES.values()]
    functions=[]
    for name in selected:
        address,code=binary.function(name)
        functions.append({'name':name,'address':hex(address),'bytes':len(code),'sha256':sha(code),
                          'direct_plt_edges':binary.edges(name)})
    gpu_edges={r['callee'] for r in binary.edges(GPU_FILTER)}
    for prefix in ('_Z17CreateCCGradation','_Z18CreateCCGradationF','_Z13CreateCbCrLut',
                   '_ZN11ComputeTaskC1','_ZN11ComputeTask8Dispatch'):
        assert any(n.startswith(prefix) for n in gpu_edges)
    assert any(x['callee'].startswith('_Z30getSRGBDataFromFullSizeProcess') for x in binary.edges(JNI_RAW))
    for prefix in ('_ZNK11Scaled2DLUT6Lookup','_ZNK16CColorCorrection19CalculateGrayWeight'):
        assert any(x['callee'].startswith(prefix) for x in binary.edges(NAMES['pixels']))
    result={'schema':'hasselblad-stage41v-phocus-native-colour-discovery-v1',
        'apk_sha256':APK_SHA,'apk_bytes':len(original),'zip_entries':len(entries),
        'all_zip_crcs_pass':True,'apk_metadata':metadata,'native_libraries':native,'asset_groups':assets,
        'crosssdk_sha256':sha(lib),'crosssdk_bytes':len(lib),
        'arm64_native_colour_code_readable':True,'selected_functions':functions,
        'shader_records':binary.shader_records(),'synthetic_native_pixel_replay':replay(binary),
        'bounds':{'camera_main_isp_equivalence_proven':False,'phocus_x2dii_profile_selected':False,
            'complete_raw_photo_rendered':False,'local_raw_import_without_camera_verified':False,
            'apk_protection_removed':False,'camera_dsp_decrypted':False,'production_renderer_changed':False,
            'private_vendor_bytes_or_profiles_exported':False},
        'runtime':{p:version(p) for p in ('numpy','unicorn','capstone','pyelftools','androguard')}}
    assert sha(args.apk.read_bytes())==APK_SHA
    args.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'package':metadata['package'],'version':metadata['version_name'],
        'readable_colour_library':LIB_PATH,'synthetic_pixels':result['synthetic_native_pixel_replay']['total_pixels'],
        'replay_cases':result['synthetic_native_pixel_replay']['cases'],'camera_isp_equivalence':False}))


if __name__=='__main__':
    main()
