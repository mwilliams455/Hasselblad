#!/usr/bin/env python3
"""Replay original gamma_ev selection, interpolation, slopes and publication.

Only synthetic configuration/state/tables are supplied. Original executable
bytes, disassembly, tuning arrays and camera input never enter the receipt.
"""
import argparse,hashlib,json,struct,sys
from importlib.metadata import version
from pathlib import Path
import numpy as np
from unicorn.arm64_const import (UC_ARM64_REG_X0,UC_ARM64_REG_X1,
    UC_ARM64_REG_X2,UC_ARM64_REG_SP,UC_ARM64_REG_LR,UC_ARM64_REG_PC,
    UC_ARM64_REG_W0)
HERE=Path(__file__).resolve().parent
for sibling in ['isp_knee_stage41m','isp_knee_stage41n']:
    sys.path.insert(0,str(HERE.parent/sibling))
from replay_main_gamma41n import GammaWrites,CHAIN,PREP_CHAIN,REGS,SENTINEL
from replay_knee41m import ARENA,STACK,STOP,PIN
from knee_math41m import knee_slopes,signed32
from gamma_axis_math41o import axis_coefficient,lerp_word,interpolate_banks

AXIS_CHAIN=['_Calc_GetCoeff','mm_get_coeff','mm_lerp','mm_mx_lerp_vec']


class GammaAxis(GammaWrites):
    def __init__(self,path):
        super().__init__(path)
        self.pending=None;self.hits={};self.memset_calls=0

    def _hook(self,uc,address,size,userdata):
        if hasattr(self,'entry_names') and address in self.entry_names:
            n=self.entry_names[address];self.hits[n]=self.hits.get(n,0)+1
        super()._hook(uc,address,size,userdata)

    def table(self,at,fields,back=0x40):
        size=max([4,*[slot+2 for slot in fields]])
        assert size<=back
        self.uc.mem_write(at-back,bytes(back+64))
        self.uc.mem_write(at-back,struct.pack('<HH',size,64));self.u32(at,back)
        for i,(slot,value) in enumerate(sorted(fields.items())):
            offset=4+4*i
            self.uc.mem_write(at-back+slot,struct.pack('<H',offset))
            self.u32(at+offset,value[0]-(at+offset) if isinstance(value,tuple) else value)

    def inject_axis_fixture(self):
        axis,banks,value=self.pending
        config=ARENA+0x8700;axis_ids=ARENA+0x8800
        axes=ARENA+0x9000;axis_values=ARENA+0x9400;source=ARENA+0xa000
        # calc_axis.gamma_ev = 50; its axis table field has vtable slot 0x5a.
        self.table(config,{0x14:0,0x18:2,0x20:(axis_ids,)})
        self.words(axis_ids,[1,50])
        self.table(axes,{0x5a:(axis_values,)},back=0x80)
        self.words(axis_values,[len(axis),*axis])
        flat=[v for bank in banks for v in bank]
        assert len(flat)<=1024
        self.words(source-4,[SENTINEL,*flat,SENTINEL])
        self.u32(ARENA+0x1000+0x34,len(flat))
        # _Calc_GetCoeff reads runtime->state->gamma_ev at state + 0xcc.
        self.u32(ARENA+0x6000+0xcc,value)

    def run_chain(self,name,args,preparation=False):
        if preparation and name=='_calc_knee_data' and self.pending:
            self.inject_axis_fixture()
        names=CHAIN+PREP_CHAIN+AXIS_CHAIN
        self.allowed=[(self.symbols[n][0],sum(self.symbols[n])) for n in names]
        self.entry_names={self.symbols[n][0]:n for n in names}
        def memset():
            dest=self.uc.reg_read(UC_ARM64_REG_X0)
            val=self.uc.reg_read(UC_ARM64_REG_X1)&255
            count=self.uc.reg_read(UC_ARM64_REG_X2)
            assert STACK<=dest and dest+count<=STACK+0x10000 and count==0x68
            self.uc.mem_write(dest,bytes([val])*count);self.memset_calls+=1
        self.callbacks={0x4a550:memset} if preparation else {}
        self.executed=0
        for reg,arg in zip(REGS,args):self.uc.reg_write(reg,int(arg)&0xffffffffffffffff)
        self.uc.reg_write(UC_ARM64_REG_SP,STACK+0x8000)
        self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        self.uc.emu_start(self.symbols[name][0],STOP,count=100000)
        assert self.uc.reg_read(UC_ARM64_REG_PC)==STOP,'instruction budget exhausted'
        return self.uc.reg_read(UC_ARM64_REG_W0)

    def coefficient(self,axis,value):
        at=ARENA+0xb800
        if axis:self.words(at,axis)
        self.run_chain('mm_get_coeff',[at,len(axis),value&0xffffffff])
        pair=self.uc.reg_read(UC_ARM64_REG_X0)
        return signed32(pair),signed32(pair>>32)

    def scalar_lerp(self,a,b,q):
        at=ARENA+0xb800;pair=ARENA+0xb900
        self.words(at,[a,b]);self.words(pair,[0,q])
        return signed32(self.run_chain('mm_lerp',[at,pair]))

    def vector_lerp(self,banks,i,q):
        at=ARENA+0xa000;pair=ARENA+0xb100;strides=ARENA+0xb200;out=ARENA+0xb300
        n=len(banks[0]);flat=[v for b in banks for v in b]
        assert len(flat)<=1024 and n<=128
        self.words(at,flat);self.words(pair,[i,q]);self.words(strides,[len(banks)])
        self.words(out-4,[SENTINEL]*(n+2))
        self.run_chain('mm_mx_lerp_vec',[at,n,pair,strides,1,out])
        assert self.output(out-4,1)==[SENTINEL] and self.output(out+4*n,1)==[SENTINEL]
        assert self.output(at,len(flat))==[v&0xffffffff for v in flat]
        return self.output(out,n,signed=True)

    def prepare_axis(self,axis,banks,value,keypoints):
        assert 1<=len(axis)==len(banks)<=32
        assert all(len(b)==32 for b in banks)
        self.pending=(axis,banks,value)
        try:
            status,result=super().prepare_knee(0x10ad,banks[0],keypoints)
        finally:self.pending=None
        flat=[v for b in banks for v in b];source=ARENA+0xa000
        assert self.output(source-4,len(flat)+2)==[SENTINEL,*[v&0xffffffff for v in flat],SENTINEL]
        assert self.output(ARENA+0x9400,len(axis)+1)==[len(axis),*[v&0xffffffff for v in axis]]
        assert self.output(ARENA+0x6000+0xcc,1)==[value&0xffffffff]
        return status,result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--library',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();native=GammaAxis(a.library);rng=np.random.default_rng(41015)
    coefficient_cases=scalar_cases=vector_cases=vector_words=full_cases=0
    axes=[[],[7],[-7,3],[-100,0,27,300],[-7,-7,3,3],
          [-2147483648,2147483647],[-10000000,0,10000000]]
    axes += [np.cumsum(rng.integers(1,3000,int(rng.integers(2,25)))).tolist() for _ in range(64)]
    for axis in axes:
        values=[-2147483648,2147483647,-1,0,1]
        values += [signed32(x+d) for x in axis for d in [-1,0,1]]
        values += rng.integers(-20000,20000,20).tolist()
        for value in values:
            assert native.coefficient(axis,value)==axis_coefficient(axis,value),(axis,value)
            coefficient_cases+=1
    witnesses=[(10,9,1),(0,10000000,256),(100,200,85)]
    for _ in range(512):
        witnesses.append((*rng.integers(-(2**31),2**31,2).tolist(),int(rng.integers(0,257))))
    for low,high,q in witnesses:
        assert native.scalar_lerp(low,high,q)==lerp_word(low,high,q)
        scalar_cases+=1
    for n in [1,2,7,32,33,127]:
        for q in [0,1,85,127,128,255,256]:
            banks=rng.integers(-(2**31),2**31,(4,n)).tolist()
            for i in [0,1,2]:
                expected=[lerp_word(x,y,q) for x,y in zip(banks[i],banks[i+1])]
                assert native.vector_lerp(banks,i,q)==expected
                vector_cases+=1;vector_words+=n
    # Complete normal-selector gamma_ev path, with actual original helpers.
    # Both physical-range-like values and deliberate arithmetic stress inputs
    # are synthetic; neither establishes the real tuning's allowed range.
    full_axes=[[7],[-200,0,333],[-7,-7,3,3],[-10000000,0,10000000]]
    full_axes += [np.cumsum(rng.integers(1,300,int(rng.integers(2,12)))).tolist() for _ in range(24)]
    before=dict(native.hits);before_memset=native.memset_calls
    for trial,axis in enumerate(full_axes):
        if trial%4==0:banks=rng.integers(-(2**31),2**31,(len(axis),32)).tolist()
        else:banks=rng.integers(0,65536,(len(axis),32)).tolist()
        keys=np.cumsum(rng.integers(1,1000,32)).tolist()
        values=[axis[0]-1,axis[0],axis[-1],axis[-1]+1]
        values += [x+(y-x)//3 for x,y in zip(axis,axis[1:])]
        values += axis[1:-1]
        for value in values:
            expected=interpolate_banks(banks,axis,value)
            status,result=native.prepare_axis(axis,banks,value,keys)
            assert status==4
            for rid,values_expected in [(0x10ac,keys),(0x10ad,expected),(0x10ae,knee_slopes(expected,keys))]:
                assert result[rid]==[v&0xffffffff for v in values_expected],(trial,value,hex(rid))
            full_cases+=1
    calls={k:v-before.get(k,0) for k,v in native.hits.items() if v-before.get(k,0)}
    for n in ['_Calc_GetCoeff','mm_get_coeff','mm_mx_lerp_vec','adj_calc_knee_kpx_data']:
        assert calls[n]==full_cases,(n,calls[n],full_cases)
    assert hashlib.sha256(a.library.read_bytes()).hexdigest()==PIN
    out={'schema':'hasselblad-stage41o-gamma-axis-replay-v1','source_sha256':PIN,
        'runtime':{'python':sys.version.split()[0],**{n:version(n) for n in ['numpy','pyelftools','unicorn']}},
        'synthetic_inputs_only':True,'physical_hardware_accessed':False,
        'rgb_pixel_equation_recovered':False,'production_photo_output_changed':False,
        'vendor_bytes_tuning_disassembly_exported':False,
        'gamma_ev_contract':{'axis_enum':50,'axis_vtable_slot':'0x5a','runtime_state_pointer_offset':'0xe8',
            'state_value_offset':'0xcc','weight_denominator':256,
            'state_units_established':False,'single_axis_only':True},
        'coefficient':{'cases':coefficient_cases,'bit_exact':True,'signed32_overflow_tested':True},
        'scalar_lerp':{'cases':scalar_cases,'bit_exact':True},
        'vector_lerp':{'cases':vector_cases,'words_compared':vector_words,'bit_exact':True},
        'complete_preparation':{'cases':full_cases,'table_words_compared_per_memory_view':full_cases*96,
            'bit_exact':True,'memory_views':['virtual','emulated_hardware'],
            'original_function_calls':calls,'only_interception':'libc memset',
            'memset_calls':native.memset_calls-before_memset,
            'input_and_axis_unchanged':True,'guards_and_unrelated_tables_unchanged':True},
        'synthetic_rounding_witnesses':[
            {'lower':lo,'upper':hi,'weight':q,'actual':native.scalar_lerp(lo,hi,q)}
            for lo,hi,q in witnesses[:3]],
        'functions':{n:{'start':hex(native.symbols[n][0]),'size':native.symbols[n][1],
            'code_sha256':hashlib.sha256(native.uc.mem_read(*native.symbols[n])).hexdigest()}
            for n in AXIS_CHAIN+['_Calc_GetLerpInfo','_calc_knee_data']},
        'limits':['Synthetic normal-selector path only; real capture axis state and tuning banks not established.',
                  'Multi-axis and dependency override branches are not exercised.',
                  'Firmware 1.3.16.2 differs from the source captures firmware 1.1.6.3.',
                  'This prepares tables; RGB mixing, gain/saturation units, clipping and hardware gamma interpolation remain unresolved.',
                  'Earlier MAIN-linked positive gamma coordinate construction remains verified; this stage does not replace it.',
                  'Earlier static ordinary/enhanced still mappings have knee disabled; this replay does not prove knee active in a capture.']}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['coefficient','scalar_lerp','vector_lerp','complete_preparation']},indent=2))


if __name__=='__main__':main()
