#!/usr/bin/env python3
"""Audit private Phocus profile decoding and native selection without exporting calibration.

Requires the separately supplied, hash-pinned APK. Only structural metadata,
hashes and verification aggregates are written; no payloads or tuning arrays.
Run without -O: assertions are intentional verification gates.
"""
import argparse, collections, io, json, plistlib, struct, hashlib, zipfile
from importlib.metadata import version
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
import tifffile
from pathlib import Path
import numpy as np
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm64_const import *

class Elf:
    def __init__(self, data):
        self.data=data; self.e=ELFFile(io.BytesIO(data))
        assert self.e["e_machine"] == "EM_AARCH64"
        self.segs=[s for s in self.e.iter_segments() if s['p_type']=='PT_LOAD']
        self.sym=np.frombuffer(self.e.get_section_by_name('.dynsym').data(),dtype=[('name','<u4'),('info','u1'),('other','u1'),('sh','<u2'),('addr','<u8'),('size','<u8')])
        self.strings=self.e.get_section_by_name('.dynstr').data()
        self.rels=np.frombuffer(self.e.get_section_by_name('.rela.dyn').data(),dtype=[('offset','<u8'),('info','<u8'),('addend','<i8')])
        self.func={self.name(i):(int(s['addr']),int(s['size'])) for i,s in enumerate(self.sym) if (s['info']&15)==2 and s['sh']!=0 and s['size']>0}
        ps=self.e.get_section_by_name('.plt')['sh_addr']
        self.plt={ps+32+16*i:self.name(r['r_info_sym']) for i,r in enumerate(self.e.get_section_by_name('.rela.plt').iter_relocations())}
    def name(self,i):
        n=int(self.sym[i]['name']); return self.strings[n:self.strings.index(b'\0',n)].decode()
    def read(self,a,n):
        s=next(s for s in self.segs if s['p_vaddr']<=a and a+n<=s['p_vaddr']+s['p_filesz'])
        o=s['p_offset']+a-s['p_vaddr'];return self.data[o:o+n]
    def relocation(self,a):
        rows=self.rels[self.rels['offset']==a];assert len(rows)==1
        r=rows[0];typ=int(r['info'])&0xffffffff;idx=int(r['info'])>>32
        assert typ in (257,1025,1027)
        return int(r['addend'])+(int(self.sym[idx]['addr']) if typ in (257,1025) else 0),typ,self.name(idx)
    def machine(self):
        u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        for s in self.segs:
            start=s['p_vaddr']&~4095;end=(s['p_vaddr']+s['p_memsz']+4095)&~4095
            u.mem_map(start,end-start);u.mem_write(s['p_vaddr'],s.data())
        u.mem_map(0x10000000,0x1000000);u.mem_map(0x20000000,0x100000);u.mem_map(0x30000000,0x10000)
        u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20);u.reg_write(UC_ARM64_REG_TPIDR_EL0,0x30001000)
        return u

def gf(x,k):
    a=np.asarray(x,dtype=np.uint16);out=np.zeros_like(a)
    while k:
        if k&1:out^=a
        a=((a<<1)^np.where(a&128,0x11b,0)).astype(np.uint16)&255;k>>=1
    return out.astype(np.uint8)

def mix(state):
    a=state.reshape(-1,4,4);o=np.empty_like(a)
    for i in range(4):o[:,:,i]=gf(a[:,:,i],14)^gf(a[:,:,(i+1)%4],11)^gf(a[:,:,(i+2)%4],13)^gf(a[:,:,(i+3)%4],9)
    return o.reshape(-1,16)[:,[0,13,10,7,4,1,14,11,8,5,2,15,12,9,6,3]]

def decrypt_blocks(e,blocks):
    tables=np.frombuffer(e.read(0x37e4988,40960),dtype=np.uint8).reshape(10,16,256)
    perm=[0,13,10,7,4,1,14,11,8,5,2,15,12,9,6,3]
    s=tables[0,np.arange(16),blocks[:,perm]]
    for i in range(1,10):s=tables[i,np.arange(16),mix(s)]
    return s

APK_SHA='5ee52bbb2b7a3fa708628ba251b409a551ae099697668427cf54b523328ccf68'
LIB_SHA='d757237554529f8ab485f88f2c5e5399fbc8d56035c79b8e057b41a40fd055e4'
TARGET='bohnjuhtuvuvtxyydb56.dat'
FILENAME='_ZN7CXMLLut11GetFileNameE13uColorProfile'
CPID='_ZN15CRawColorParams7GetCPIDE9eCCDTypes13eIRFilterTypei'
DECODE='_ZN7CXMLLut10DecodeFromEP9CKeyCoder'
BACK='_ZN12CBodyAndBack21CameraBackModelStringE16eCameraBackModel9eCCDTypes'

def sha(data):
    return hashlib.sha256(data).hexdigest()

class Native:
    """Bounded native calls; host allocations and key-value getters are explicit fixtures."""
    def __init__(self,e):
        self.e=e;self.u=e.machine();self.heap=0x10400000
        self.active=[];self.called=set();self.allocations=[];self.mapping=[]
        self.config=False;self.config_queries=[];self.profile=None;self.reads=[]
        self.obj=0x10008000;self.coder=0x10009000
        self.u.mem_write(self.coder,struct.pack('<Q',0x10009100))
        for off in (0x58,0x80,0xa0,0xf0):
            self.u.mem_write(0x10009100+off,struct.pack('<Q',0x30003000+off))
        # A minimal app-service fixture supplies one boolean configuration query.
        for address,value in ((0x37c49e8,0x10005000),(0x10005000,0x10005100),
                              (0x10005100,0x10005200),(0x10005240,0x30002000)):
            self.u.mem_write(address,struct.pack('<Q',value))
        self.u.hook_add(UC_HOOK_CODE,self.hook)

    def alloc(self,n):
        p=self.heap;self.heap+=(n+47)&~15
        assert self.heap<0x11000000
        self.u.mem_write(p,b'\xa5'*16);self.u.mem_write(p+16+n,b'\xa5'*16)
        self.allocations.append((p,n));return p+16

    def getstr(self,p):
        b=bytes(self.u.mem_read(p,24))
        if b[0]&1:
            n,q=struct.unpack_from('<QQ',b,8)
            assert n<1000000
            return bytes(self.u.mem_read(q,n)).decode()
        return b[1:1+(b[0]>>1)].decode()

    def putstr(self,p,s):
        if len(s)<23:self.u.mem_write(p,bytes([len(s)*2])+s+b'\0'*(23-len(s)))
        else:
            q=self.alloc(len(s)+1);self.u.mem_write(q,s+b'\0')
            self.u.mem_write(p,struct.pack('<QQQ',((len(s)+16)&~15)|1,len(s),q))

    def hook(self,cpu,address,size,user):
        if address==0x3502b68:
            sp=cpu.reg_read(UC_ARM64_REG_SP)
            self.mapping=[{'cpid':hex(struct.unpack('<I',bytes(cpu.mem_read(sp+0x18+32*i,4)))[0]),
                           'file':self.getstr(sp+0x20+32*i)} for i in range(26)]
        if address==0x30002000:
            self.config_queries.append(self.getstr(cpu.reg_read(UC_ARM64_REG_X1)))
            cpu.reg_write(UC_ARM64_REG_X0,int(self.config))
            cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30));return
        if address in (0x30003058,0x30003080,0x300030a0,0x300030f0):
            x1,x2,x3=[cpu.reg_read(r) for r in (UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3)]
            key=self.getstr(x1);v=self.profile.get(key)
            if address==0x300030a0:cpu.reg_write(UC_ARM64_REG_X0,int(key in self.profile))
            elif address==0x30003058:cpu.reg_write(UC_ARM64_REG_X0,int(v or 0)&0xffffffff)
            elif address==0x30003080:self.putstr(cpu.reg_read(UC_ARM64_REG_X8),str(v or '').encode())
            else:
                capacity=struct.unpack('<Q',bytes(cpu.mem_read(x3,8)))[0]
                values=np.asarray(v or [],dtype='<f8')
                assert not x2 or len(values)<=capacity,(key,len(values),capacity)
                if x2 and len(values):cpu.mem_write(x2,values.tobytes())
                cpu.mem_write(x3,struct.pack('<Q',len(values)))
                cpu.reg_write(UC_ARM64_REG_X0,int(v is not None))
                self.reads.append({'key':key,'count':len(values),'length_query':x2==0,
                    'object_offset':hex(x2-self.obj) if self.obj<=x2<self.obj+0x318 else None})
            cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30));return
        if address in self.e.plt:
            name=self.e.plt[address]
            x0,x1,x2=[cpu.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2)]
            if name in ('_Znwm','_Znam'):cpu.reg_write(UC_ARM64_REG_X0,self.alloc(x0))
            elif name in ('_ZdlPv','_ZdaPv'):pass
            elif name in ('memmove','memcpy'):cpu.mem_write(x0,bytes(cpu.mem_read(x1,x2)))
            elif name=='memset':cpu.mem_write(x0,bytes([x1&255])*x2)
            elif any(t in name for t in ('__assign_no_alias','__assign_external','__init_copy_ctor_external')):
                self.putstr(x0,bytes(cpu.mem_read(x1,x2)))
            elif name in ('_ZN12CBodyAndBack15IsMultiShotBackE16eCameraBackModel',
                           '_ZN7CXMLLut14InitializeLUTsEbii'):
                a,n=self.e.func[name];self.active.append((a,a+n));self.called.add(name)
                cpu.reg_write(UC_ARM64_REG_PC,a);return
            else:raise AssertionError(('Unexpected external call',hex(address),name))
            cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30));return
        assert any(lo<=address<hi for lo,hi in self.active),('Unexpected code',hex(address))

    def run(self,name,args=(),string=False):
        a,n=self.e.func[name];self.active=[(a,a+n)];self.called.add(name)
        self.u.mem_write(0x10002000,b'\0'*64);self.u.reg_write(UC_ARM64_REG_X8,0x10002000)
        for reg,v in zip((UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2),args):self.u.reg_write(reg,v)
        self.u.reg_write(UC_ARM64_REG_SP,0x200ff000);self.u.reg_write(UC_ARM64_REG_X30,0x30000000)
        self.u.emu_start(a,0x30000000,count=3000000)
        assert self.u.reg_read(UC_ARM64_REG_PC)==0x30000000,'Instruction budget exhausted'
        for p,n in self.allocations:
            assert bytes(self.u.mem_read(p,16))==b'\xa5'*16
            assert bytes(self.u.mem_read(p+16+n,16))==b'\xa5'*16
        return self.getstr(0x10002000) if string else self.u.reg_read(UC_ARM64_REG_X0)

def verify_blocks(e,assets):
    """Compare an independent vectorized decoder with original native blocks."""
    u=e.machine()
    for address,k in zip(range(0x37c6ec0,0x37c6ee0,8),(14,11,13,9)):
        p,typ,name=e.relocation(address);u.mem_write(address,struct.pack('<Q',p))
        assert np.array_equal(np.frombuffer(e.read(p,256),dtype=np.uint8),gf(np.arange(256),k))
    def hook(cpu,a,size,user):
        if a==0x37a5fa0:cpu.reg_write(UC_ARM64_REG_PC,0x3658580)
        else:assert 0x3658b50<=a<0x3658e38 or 0x3658580<=a<0x3658888,hex(a)
    u.hook_add(UC_HOOK_CODE,hook)
    random=np.random.default_rng(410024).integers(0,256,(32,16),dtype=np.uint8)
    selected=[]
    for data in assets.values():
        blocks=np.frombuffer(data,dtype=np.uint8).reshape(-1,16)
        selected.extend(blocks[i] for i in (1,2,len(blocks)//2,len(blocks)-1))
    samples=np.vstack([random,selected]);expected=decrypt_blocks(e,samples)
    for row,oracle in zip(samples,expected):
        u.mem_write(0x10000000,row.tobytes());u.mem_write(0x10001000,b'\xa5'*48)
        u.reg_write(UC_ARM64_REG_X0,0x10000000);u.reg_write(UC_ARM64_REG_X1,0x10001010)
        u.reg_write(UC_ARM64_REG_SP,0x200ff000);u.reg_write(UC_ARM64_REG_X30,0x30000000)
        u.emu_start(0x3658e2c,0x30000000,count=100000)
        assert u.reg_read(UC_ARM64_REG_PC)==0x30000000
        assert bytes(u.mem_read(0x10001010,16))==oracle.tobytes()
        assert bytes(u.mem_read(0x10000000,16))==row.tobytes()
        assert bytes(u.mem_read(0x10001000,16))==bytes(u.mem_read(0x10001020,16))==b'\xa5'*16
    return {'synthetic_blocks':32,'asset_blocks':len(selected),'exact_blocks':len(samples),
            'input_unchanged_and_output_guards_pass':True,'crypto_rounds_stubbed':False}

def inspect_profile(e,profile):
    native=Native(e);native.profile=profile
    # DecodeFrom operates on an initially zeroed object with a key-value facade.
    # Python parses XML; the original native function constructs profile fields.
    native.u.mem_write(native.obj-16,b'\xa5'*16)
    native.u.mem_write(native.obj+0x318,b'\xa5'*16)
    native.run(DECODE,(native.obj,native.coder))
    assert bytes(native.u.mem_read(native.obj-16,16))==b'\xa5'*16
    assert bytes(native.u.mem_read(native.obj+0x318,16))==b'\xa5'*16
    arrays=[]
    for r in native.reads:
        if r['object_offset']:
            actual=np.frombuffer(bytes(native.u.mem_read(native.obj+int(r['object_offset'],16),8*r['count'])),dtype='<f8')
            expected=np.asarray(profile[r['key']],dtype='<f8')*.5+1
            assert np.array_equal(actual,expected),r['key']
            arrays.append({'key':r['key'],'count':r['count'],'object_offset':r['object_offset'],
                           'stored_times_half_plus_one_exact':True})
    keys=('LUTTableFlashStd','LUTTableTSStd','LUTTableHTStd','LUTTableFlashRepro','LUTTableTSRepro','LUTTableHTRepro')
    tables=[]
    for off,key in zip(range(0x2a0,0x2d0,8),keys):
        p=struct.unpack('<Q',bytes(native.u.mem_read(native.obj+off,8)))[0]
        expected=np.asarray(profile[key],dtype='<f8').tobytes()
        assert len(expected)==18690*8
        assert bytes(native.u.mem_read(p,len(expected)))==expected,key
        tables.append({'key':key,'double_count':18690,'pointer_offset':hex(off),'all_doubles_exact':True})
    assert len(arrays)==7 and sum(r['count'] for r in arrays)==51
    return {'original_decode_from_executed':True,'original_initialize_luts_executed':True,
            'native_xml_parser_executed':False,'object_initialization':'zeroed complete-input fixture',
            'xml_parsing_and_key_value_getters':'Python facade; native array conversion and table construction',
            'arrays':arrays,'tables':tables,'allocation_and_object_guards_pass':True,
            'native_functions':sorted(native.called),'read_requests':native.reads}

def raw_records(paths):
    result=[]
    for path in paths:
        with tifffile.TiffFile(path) as t:
            page=t.pages[0];mn=page.tags['ExifTag'].value['MakerNote']
            count=struct.unpack_from('<H',mn)[0];assert 2+12*count<=len(mn)
            tags={}
            for i in range(count):
                key,kind,n,value=struct.unpack_from('<HHII',mn,2+12*i)
                if key in (0x11,0x12,0x16):
                    assert kind==4 and n==1;tags[key]=value
            assert set(tags)=={0x11,0x12,0x16}
            result.append({'sample':len(result)+1,'model':str(page.tags['Model'].value),
                'sensor_tag_0x11':tags[0x11],'back_tag_0x12':tags[0x12],'filter_tag_0x16':tags[0x16]})
    return result

def static_evidence(e):
    wanted=(FILENAME,CPID,DECODE,'_ZN7CXMLLutC2E13uColorProfilei',
        '_ZN15CRawColorParams11GetPtrOfLUTE9eCCDTypes13eIRFilterTypei',
        '_ZN15CRawColorParams3LUTE13uColorProfile',BACK,
        '_ZN17CRawImageFileData7CCDTypeEP14CRawTiffHeader',
        '_ZN17CRawImageFileData12GetBackModelEP14CRawTiffHeader',
        '_ZN17CRawImageFileData9SetIrTypeEP14CRawTiffHeader13eIRFilterType')
    records=[]
    for name in wanted:
        a,n=e.func[name];code=e.read(a,n);edges=[]
        for ins in Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(code,a):
            word=struct.unpack_from('<I',code,ins.address-a)[0]
            if word&0x7c000000==0x14000000:
                delta=word&0x3ffffff
                if delta&0x2000000:delta-=0x4000000
                target=ins.address+4*delta
                assert ins.mnemonic in ('b','bl') and int(ins.op_str[1:],16)==target
                if target in e.plt:edges.append({'site':hex(ins.address),'callee':e.plt[target]})
        records.append({'name':name,'address':hex(a),'bytes':n,'sha256':sha(code),'direct_plt_edges':edges})
    vt,typ,name=e.relocation(0x37c6408);target,typ,method=e.relocation(vt+0x10+0x38)
    assert name=='_ZTV7CXMLLut' and method==DECODE and target==e.func[DECODE][0]
    edges={r['name']:{x['callee'] for x in r['direct_plt_edges']} for r in records}
    ctor=edges['_ZN7CXMLLutC2E13uColorProfilei']
    assert FILENAME in ctor and any('HBCryptoNameSpace7decrypt' in n for n in ctor)
    assert CPID in edges['_ZN15CRawColorParams11GetPtrOfLUTE9eCCDTypes13eIRFilterTypei']
    return {'functions':records,'constructor_vtable_slot_0x38_resolves_to_decode_from':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apk',type=Path,required=True)
    ap.add_argument('--raw',type=Path,nargs='*',default=[]);ap.add_argument('--receipt',type=Path,required=True)
    args=ap.parse_args();original=args.apk.read_bytes();assert sha(original)==APK_SHA
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        lib=z.read('lib/arm64-v8a/libcrosssdk.so');assert sha(lib)==LIB_SHA
        assets={Path(n).name:z.read(n) for n in sorted(z.namelist()) if n.startswith('assets/Colormaps/') and n.endswith('.dat')}
    assert len(assets)==26;e=Elf(lib)
    block_result=verify_blocks(e,assets);print('Native block comparison passed',flush=True)
    profiles=[];target=None
    for name,data in assets.items():
        assert len(data)>=32 and len(data)%16==0
        blocks=np.frombuffer(data,dtype=np.uint8).reshape(-1,16)
        plain=(decrypt_blocks(e,blocks[1:])^blocks[:-1]).tobytes();padding=plain[-1]
        assert 1<=padding<=16 and plain[-padding:]==bytes([padding])*padding
        plain=plain[:-padding];profile=plistlib.loads(plain);assert isinstance(profile,dict)
        arrays={k:len(v) for k,v in profile.items() if isinstance(v,list)}
        assert all(np.isfinite(np.asarray(v,dtype=float)).all() for v in profile.values() if isinstance(v,list))
        profiles.append({'file':name,'ciphertext_sha256':sha(data),'decoded_sha256':sha(plain),
            'decoded_bytes':len(plain),'valid_padding':True,'xml_plist_parsed':True,
            'profile_version':profile.get('Version'),'array_lengths':arrays,
            'reference_temperatures':{k:profile[k] for k in ('tf','tt','tlt','th') if k in profile}})
        if name==TARGET:target=profile
    assert target is not None
    print('All 26 colour maps parsed',flush=True)
    native=Native(e);native.run(FILENAME,(0,),True);mapping=native.mapping.copy()
    for row in mapping:assert native.run(FILENAME,(int(row['cpid'],16),),True)==row['file']
    native.config=False;cpid=native.run(CPID,(22,6,0));assert cpid==0x616
    selected=native.run(FILENAME,(cpid,),True);assert selected==TARGET
    label=native.run(BACK,(71,22),True);assert label=='Hasselblad X2D II 100C'
    # Exercise the configuration branch as a boundary, without assuming its UI default.
    native.config=True;alternate=native.run(CPID,(22,6,0));assert alternate==0x10616
    raw=raw_records(args.raw)
    assert all(r['model']=='X2D II 100C' and (r['sensor_tag_0x11'],r['back_tag_0x12'],r['filter_tag_0x16'])==(22,71,6) for r in raw)
    loaded=inspect_profile(e,target)
    result={'schema':'hasselblad-stage41w-phocus-x2dii-profile-v1','apk_sha256':APK_SHA,'library_sha256':LIB_SHA,
        'asset_count':len(assets),'native_block_replay':block_result,'profiles':profiles,
        'native_profile_filename_mapping':mapping,'native_mapping_roundtrips':len(mapping),
        'selection':{'sensor':22,'filter':6,'back':71,'native_back_label':label,
            'config_queries':sorted(set(native.config_queries)),'config_boolean_fixture':False,
            'normal_cpid':hex(cpid),'selected_file':selected,'alternate_boolean_true_cpid':hex(alternate),
            'actual_running_app_config_observed':False},'raw_metadata_samples':raw,
        'native_profile_load':loaded,'static_evidence':static_evidence(e),
        'bounds':{'camera_firmware_decrypted':False,'camera_main_isp_equivalence_proven':False,
            'full_app_or_end_to_end_raw_pipeline_executed':False,'complete_raw_photo_rendered':False,
            'production_renderer_changed':False,'calibration_arrays_or_crypto_tables_exported':False},
        'runtime':{p:version(p) for p in ('numpy','unicorn','capstone','pyelftools','tifffile')}}
    assert sha(args.apk.read_bytes())==APK_SHA
    args.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'assets_decoded':26,'native_block_matches':block_result['exact_blocks'],
        'native_profile_cpid':hex(cpid),'selected_asset':selected,'real_raw_metadata_samples':len(raw),
        'native_matrices_loaded':5,'native_chroma_tables_loaded':6,'end_to_end_raw_render':False}))

if __name__=='__main__':main()

