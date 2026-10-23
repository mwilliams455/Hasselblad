#!/usr/bin/env python3
"""Trace original MAIN gamma bindings and replay writes to synthetic ISP memory.

No camera, MMIO or vendor tuning is used. Firmware bytes are read locally and
never included in the receipt. This establishes loading/layout, not RGB math.
"""
import argparse,hashlib,io,json,lzma,struct,sys
from pathlib import Path
import numpy as np
from elftools.elf.elffile import ELFFile
from unicorn.arm64_const import (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,
    UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_X5,UC_ARM64_REG_SP,
    UC_ARM64_REG_LR,UC_ARM64_REG_PC,UC_ARM64_REG_W0)

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'isp_knee_stage41m'))
from replay_knee41m import Original,ARENA,STACK,STOP,PIN
from knee_math41m import knee_slopes

VIRTUAL=0x4000000
HARDWARE=0x4100000
PHYSICAL_BASE=0xf322e000
SENTINEL=0xa5a55a5a
REGS=[UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,
      UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_X5]
CHAIN=['DjiIsp_Reg_GetType','DjiIsp_Reg_GetGroupNum','DjiIsp_Reg_GetLut',
       'DjiIsp_Reg_Set','DjiIsp_Reg_Get','dcam_vreg_get_vreg_pointer',
       'isp_drv_reg_get_type','isp_drv_reg_get_group_num','isp_drv_reg_get_lut',
       'isp_drv_reg_set_value','isp_drv_reg_get_value','DjiAdj_Calc_LutMemCopy',
       'rcam_sys_mem_addr']
PREP_CHAIN=['_calc_knee_data','_Calc_GetLerpInfo','adj_calc_knee_kpx_data',
            'adj_plat_calc_knee_gain_over_isp_max','rcam_adj_calc_common','_Calc_SimpleLutMem']


def original_symbols(path):
    result={}
    with path.open('rb') as f:
        elf=ELFFile(f)
        tables=[elf.get_section_by_name(n) for n in ['.dynsym','.symtab']]
        debug=elf.get_section_by_name('.gnu_debugdata')
        if debug:
            limit=64*1024*1024
            dec=lzma.LZMADecompressor(memlimit=4*limit)
            raw=dec.decompress(debug.data(),max_length=limit+1)
            assert dec.eof and len(raw)<=limit
            mini=ELFFile(io.BytesIO(raw));tables.append(mini.get_section_by_name('.symtab'))
        for table in tables:
            if table is None:continue
            for s in table.iter_symbols():
                if s['st_shndx']!='SHN_UNDEF' and s['st_info']['type']=='STT_FUNC':
                    result[s.name]=(int(s['st_value']),int(s['st_size']))
    return result


def field_word(old,value,shift,mask):
    """Independently expressed masked update; descriptor width is not a scale."""
    return ((int(old)&~int(mask))|((int(value)<<int(shift))&int(mask)))&0xffffffff


class GammaWrites(Original):
    def __init__(self,path):
        super().__init__(path)
        self.symbols=original_symbols(path)
        self.uc.mem_map(VIRTUAL,0x30000);self.uc.mem_map(HARDWARE,0x10000)
        self.u64(ARENA+0xf8,VIRTUAL)
        # Original rcam_sys_mem_addr then resolves descriptor addresses solely
        # into this emulator's synthetic hardware-memory region.
        self.u64(0x5b3810,HARDWARE);self.u64(0x5b3818,PHYSICAL_BASE)
        self.descriptor_base=self.read64(0x59e048)
        self.fields=self.bindings(path)

    def descriptor(self,rid):
        kind,parent,offset,arg2,arg3=struct.unpack('<HHIII',self.uc.mem_read(self.descriptor_base+16*rid,16))
        result={'register_id':hex(rid),'kind':kind,'virtual_offset':hex(offset)}
        if kind==1:result.update(hardware_address=hex(arg2),entries=arg3)
        elif kind==2:result.update(hardware_address=hex(arg2),group_count=arg3,parent_id=hex(parent))
        elif kind==3:
            result.update(parent_id=hex(parent),shift=arg2,mask=hex(arg3),field_bits=(arg3>>arg2).bit_length())
            assert (arg3>>arg2)==(1<<result['field_bits'])-1,'noncontiguous bitfield'
        else:raise ValueError('unexpected descriptor kind')
        return result

    def bindings(self,path):
        with path.open('rb') as f:
            e=ELFFile(f);sec=e.get_section_by_name('.data.rel.ro');data=sec.data();base=int(sec['sh_addr'])
        groups={}
        for group in ['normal','lowlight','ei','common']:
            prefix='DIQ_iq_main_gamma_'+group+'_';fields={}
            for name,(address,_) in self.symbols.items():
                if not name.startswith(prefix):continue
                needle=struct.pack('<Q',address)
                refs=[base+i for i in range(0,len(data)-7,8) if data[i:i+8]==needle]
                assert len(refs)==1,(name,refs)
                record=refs[0]-16
                pointer,count=struct.unpack('<QI',self.uc.mem_read(record,12))
                assert 1<=count<=8
                ids=struct.unpack('<'+'I'*count,self.uc.mem_read(pointer,4*count))
                fields[name[len(prefix):]]={'binding_record':hex(record),'accessor':name,
                    'registers':[self.descriptor(rid) for rid in ids]}
            assert fields;groups[group]=fields
        return groups

    def run_chain(self,name,args,preparation=False):
        self.allowed=[(self.symbols[n][0],sum(self.symbols[n])) for n in CHAIN+(PREP_CHAIN if preparation else [])]
        def memset():
            dest=self.uc.reg_read(UC_ARM64_REG_X0);value=self.uc.reg_read(UC_ARM64_REG_X1)&255;length=self.uc.reg_read(UC_ARM64_REG_X2)
            assert STACK<=dest and dest+length<=STACK+0x10000 and length==0x68
            self.uc.mem_write(dest,bytes([value])*length)
        self.callbacks={0x4a550:memset} if preparation else {};self.executed=0
        for reg,arg in zip(REGS,args):self.uc.reg_write(reg,int(arg)&0xffffffffffffffff)
        self.uc.reg_write(UC_ARM64_REG_SP,STACK+0x8000);self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        self.uc.emu_start(self.symbols[name][0],STOP,count=100000)
        assert self.uc.reg_read(UC_ARM64_REG_PC)==STOP,'instruction budget exhausted'
        return self.uc.reg_read(UC_ARM64_REG_W0)

    def hw_offset(self,descriptor):
        d=self.descriptor(int(descriptor['parent_id'],16)) if descriptor['kind']==3 else descriptor
        result=int(d['hardware_address'],16)-PHYSICAL_BASE
        assert 0<=result<0x10000
        return result

    def query_lut(self,rid):
        pointer=ARENA+0x800;count=ARENA+0x808
        assert self.run_chain('DjiIsp_Reg_GetLut',[ARENA,rid,pointer,count,0])==0
        return self.read64(pointer),self.output(count,1)[0]

    def copy_lut(self,rid,values,width=0,commit=1):
        d=self.descriptor(rid);n=d['entries'];assert n==len(values)
        ptr,count=self.query_lut(rid);assert ptr==VIRTUAL+int(d['virtual_offset'],16) and count==n
        hardware=HARDWARE+self.hw_offset(d)
        self.words(ptr,values);self.words(hardware-4,[SENTINEL]*(n+2))
        self.run_chain('DjiAdj_Calc_LutMemCopy',[rid,commit,width,ARENA,n,ptr])
        assert self.output(hardware-4,1)==[SENTINEL] and self.output(hardware+4*n,1)==[SENTINEL]
        assert self.output(ptr,n)==[int(v)&0xffffffff for v in values],'source changed'
        return self.output(hardware,n)

    def scalar(self,d,value,old,hardware_write):
        rid=int(d['register_id'],16);at=VIRTUAL+int(d['virtual_offset'],16);hw=HARDWARE+self.hw_offset(d)
        self.words(at,[old]);self.words(hw,[old])
        status=self.run_chain('DjiIsp_Reg_Set',[ARENA,rid,value,int(hardware_write),0]);assert status==0
        result=self.output(at,1)[0];hw_result=self.output(hw,1)[0]
        readback=ARENA+0x900;self.u32(readback,SENTINEL)
        assert self.run_chain('DjiIsp_Reg_Get',[ARENA,rid,readback,0,0])==0
        return result,hw_result,self.output(readback,1)[0]

    def prepare_knee(self,rid,values,keypoints):
        """Full original no-axis table-preparation path with synthetic metadata.

        Uses the normal tuning selector, mode-frame keypoint bank and real
        register descriptors. Only libc memset is intercepted. This does not
        exercise axis interpolation or assert a real capture's tuning choices.
        """
        assert rid in [0x10ad,0x10af] and len(values)==len(keypoints)==32
        self.uc.mem_write(ARENA,b'\0'*0xe000);self.u64(ARENA+0xf8,VIRTUAL)
        ctx=ARENA+0x1000;runtime=ARENA+0x2000;state=ARENA+0x6000;holder=ARENA+0x7000
        modroot=ARENA+0x8000;modnormal=ARENA+0x8100;kpx_config=ARENA+0x8200
        iqroot=ARENA+0x8300;bank_vector=ARENA+0x8400;iqnormal=ARENA+0x8500;kpx_vector=ARENA+0x8600
        input_config=ARENA+0x8700;axes=ARENA+0x9000;source=ARENA+0xa000
        def table(at,fields):
            size=max([4,*[slot+2 for slot in fields]])
            self.uc.mem_write(at-0x40,struct.pack('<HH',size,64))
            self.u32(at,0x40)
            for i,(slot,value) in enumerate(sorted(fields.items())):
                offset=4+4*i;self.uc.mem_write(at-0x40+slot,struct.pack('<H',offset))
                if isinstance(value,tuple):value=value[0]-(at+offset)
                self.u32(at+offset,value)
        # FlatBuffer vtable slots are read by the original helper. All table
        # values below are synthetic structural fixtures, not vendor tuning.
        table(modroot,{0x30:(modnormal,)})
        table(modnormal,{0x12:(kpx_config,)})
        table(kpx_config,{6:1,8:4})  # simple_lut_mem, mode_frame
        table(iqroot,{0x34:(bank_vector,)})
        self.words(bank_vector,[1,iqnormal-(bank_vector+4)])
        table(iqnormal,{0x12:(kpx_vector,)})
        self.words(kpx_vector,[32,*keypoints])
        table(input_config,{0x14:0,0x18:2})  # io32, memory cfgen 2
        self.u64(holder+0x30,modroot)
        self.u64(runtime+0xe8,state);self.u32(runtime+0xe0,1)
        self.u64(runtime+0x7c8,iqroot);self.u64(runtime+0x7e0,axes)
        self.u32(ctx,rid);self.u64(ctx+0x18,source);self.u32(ctx+0x34,32)
        self.u64(ctx+0x38,holder);self.u64(ctx+0x48,runtime);self.u64(ctx+0x50,axes);self.u64(ctx+0x58,ARENA)
        self.words(source,values)
        targets=[0x10ac,rid,rid+1]
        first=self.descriptor(0x10ac);vbase=VIRTUAL+int(first['virtual_offset'],16);hbase=HARDWARE+self.hw_offset(first)
        self.words(vbase-4,[SENTINEL]*162);self.words(hbase-4,[SENTINEL]*162)
        status=self.run_chain('_calc_knee_data',[input_config,ctx],preparation=True)
        result={};expected_region=[SENTINEL]*162
        for target in targets:
            d=self.descriptor(target);virt=self.output(VIRTUAL+int(d['virtual_offset'],16),32)
            hw=self.output(HARDWARE+self.hw_offset(d),32);assert virt==hw
            result[target]=virt
            offset=1+(int(d['virtual_offset'],16)-int(first['virtual_offset'],16))//4
            expected_region[offset:offset+32]=virt
        assert self.output(vbase-4,162)==expected_region and self.output(hbase-4,162)==expected_region,'unrelated table/guard changed'
        assert self.output(source,32)==[int(v)&0xffffffff for v in values]
        return status,result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();native=GammaWrites(a.library);rng=np.random.default_rng(41014)
    out={'schema':'hasselblad-stage41n-main-gamma-register-replay-v1','source_sha256':PIN,
        'synthetic_inputs_only':True,'physical_hardware_accessed':False,
        'rgb_pixel_equation_recovered':False,'production_photo_output_changed':False,
        'vendor_bytes_tuning_disassembly_exported':False,'bindings':native.fields}
    # The three tuning variants bind the same hardware register IDs, though
    # they may use different values and calculation dependencies.
    expected={k:v['registers'] for k,v in native.fields['normal'].items()}
    assert all({k:v['registers'] for k,v in native.fields[g].items()}==expected for g in ['lowlight','ei'])
    out['normal_lowlight_ei_share_register_destinations']=True
    out['functions']={n:{'start':hex(addr),'size':size,'code_sha256':hashlib.sha256(native.uc.mem_read(addr,size)).hexdigest()}
                      for n,(addr,size) in native.symbols.items() if n in CHAIN+PREP_CHAIN}
    lut_cases=0;lut_words=0;commit_skips=0
    for name,row in native.fields['normal'].items():
        for d in row['registers']:
            if d['kind']!=1:continue
            rid=int(d['register_id'],16);n=d['entries']
            assert native.run_chain('DjiIsp_Reg_GetType',[rid])==1
            widths=[w for w,div in [(0,1),(1,2),(2,4)] if n%div==0]
            patterns=[[0]*n,[0xffffffff]*n,list(range(n)),rng.integers(0,2**32,n,dtype=np.uint32).tolist()]
            if name in ['knee_gain','knee_saturation']:
                patterns.append(knee_slopes([4096-i*7 for i in range(n)],list(range(n))))
            for values in patterns:
                for width in widths:
                    actual=native.copy_lut(rid,values,width)
                    assert actual==[int(v)&0xffffffff for v in values],(name,width)
                    lut_cases+=1;lut_words+=n
            for commit in [0,2]:
                assert native.copy_lut(rid,list(range(n)),0,commit)==[SENTINEL]*n;commit_skips+=1
    scalar_cases=0
    for group in ['normal','common']:
        for name,row in native.fields[group].items():
            for d in row['registers']:
                if d['kind']!=3:continue
                mask=int(d['mask'],16);shift=d['shift'];limit=mask>>shift
                cases=[0,1,limit,limit+1,0xffffffff,*rng.integers(0,2**32,8,dtype=np.uint32).tolist()]
                for value in cases:
                    old=int(rng.integers(0,2**32,dtype=np.uint32));expected=field_word(old,value,shift,mask)
                    for hw in [False,True]:
                        actual,hactual,readback=native.scalar(d,value,old,hw)
                        assert actual==expected and hactual==(expected if hw else old)
                        assert readback==((expected&mask)>>shift)
                        scalar_cases+=1
    out['lut_copy']={'cases':lut_cases,'words_compared':lut_words,'bit_exact':True,
        'commit_disabled_cases':commit_skips,'valid_io_widths_tested':[32,64,128],
        'negative_slope_bits_preserved':True,'source_and_output_sentinels_checked':True,
        'scope':'Complete original copy/get-LUT/address-resolution chain; all destinations are synthetic emulator memory.'}
    out['scalar_registers']={'cases':scalar_cases,'bit_exact':True,
        'preserves_unrelated_bits':True,'oversized_values_masked_not_saturated':True,
        'hardware_mirror_write_enabled_and_disabled_tested':True,
        'scope':'Complete original set/get chain; register width does not establish numeric fixed-point units.'}
    prep_cases=0
    for rid in [0x10ad,0x10af]:
        for trial in range(32):
            keys=np.cumsum(rng.integers(1,4096,32)).tolist()
            values=rng.integers(-1000000,1000000,32).tolist() if trial else [4096-i*7 for i in range(32)]
            status,result=native.prepare_knee(rid,values,keys)
            assert status==4
            expected_values=[v&0xffffffff for v in values]
            expected_slopes=[v&0xffffffff for v in knee_slopes(values,keys)]
            assert result[0x10ac]==keys and result[rid]==expected_values and result[rid+1]==expected_slopes
            prep_cases+=1
    out['full_knee_preparation']={'cases':prep_cases,'words_compared_per_memory_view':prep_cases*96,
        'bit_exact':True,'virtual_and_synthetic_hardware_views_agree':True,
        'source_unchanged_output_guards_and_unrelated_tables_preserved':True,'sole_intercepted_dependency':'libc memset',
        'scope':'Entire _calc_knee_data and original keypoint selection, simple LUT calculation, slope calculation and copy chain; synthetic normal-selector/mode-frame keypoint bank with no interpolation axis. Other runtime branches remain untested.'}
    assert hashlib.sha256(a.library.read_bytes()).hexdigest()==PIN
    out['source_library_unchanged']=True
    out['status']='PASS_original_MAIN_gamma_register_contract'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':out['status'],'lut_cases':lut_cases,'lut_words':lut_words,'scalar_cases':scalar_cases,
        'full_preparation_cases':prep_cases,'three_tuning_variants_share_register_destinations':True}))


if __name__=='__main__':main()
