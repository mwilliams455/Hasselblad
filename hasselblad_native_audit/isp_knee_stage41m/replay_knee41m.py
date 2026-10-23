#!/usr/bin/env python3
"""Synthetic, bounded replay of original X2D II knee preparation instructions.

Read firmware locally, pin its SHA256, execute selected original instructions
in Unicorn and export aggregate results only. No camera data, tuning arrays,
ELF bytes or disassembly are written to the evidence receipt.
"""
import argparse,hashlib,json,re,struct
from pathlib import Path
import numpy as np
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,
    UC_ARM64_REG_X3,UC_ARM64_REG_SP,
    UC_ARM64_REG_PC,UC_ARM64_REG_LR,UC_ARM64_REG_W0,UC_ARM64_REG_W8,
    UC_ARM64_REG_TPIDR_EL0,UC_ARM64_REG_CPACR_EL1)
from knee_math41m import knee_slopes,fusion_table

PIN='3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66'
ARENA=0x1000000
STACK=0x2000000
STOP=0x3000000
FUNCTIONS={
    'main_gamma_calc_frame':(0x35c710,144),
    '_calc_knee_data':(0x3bf218,1328),
    'adj_calc_knee_kpx_data':(0x366ca8,2200),
    'adj_plat_calc_knee_fusion':(0x371678,1044),
    'adj_plat_calc_gamma_lut_compensate_ev':(0x371590,8),
    'adj_plat_calc_knee_gain_over_isp_max':(0x371588,8),
    'rcam_adj_calc_common':(0x3b3e98,660),
}
CALLBACKS={0x3a1630:'common',0x3a2df8:'normal',0x3a7b58:'ei',0x3a5358:'lowlight'}


def configuration_evidence(native,config_path,schema_path):
    pins={'config':'2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286',
          'schema':'59ec3b0d019b9e8873f3d005c041b4e3ca1a2b930c503c110c51531f8bd30e40'}
    for name,path in [('config',config_path),('schema',schema_path)]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==pins[name],name+' hash mismatch'
    config=config_path.read_text();schema=schema_path.read_text()
    enum=re.search(r'enum calc:\s*int\s*\{([^}]+)',schema)[1]
    enum=re.sub(r'//[^\n]*','',enum);enums={};index=-1
    for item in enum.split(','):
        item=item.strip()
        if not item:continue
        name,*value=item.split('=');index=int(value[0]) if value else index+1
        enums[name.strip()]=index
    expected={'calc_knee_data':0x3bf218,'simple_lut_mem_gamma_compensate_ev':0x3bfc38,
              'index_1d_lut_mem_gamma_compensate_ev':0x3bfc68,
              'lerp_1d_lut_mem_gamma_compensate_ev':0x3bfc98,
              'knee_fusion':0x3bfe10,'knee_fusion_index':0x3bff88}
    routes={}
    for name,target in expected.items():
        index=enums[name];actual=native.read64(0x59c240+8*index);assert actual==target
        routes[name]={'schema_enum':index,'original_dispatch_target':hex(target)}
    modules={}
    for name in ['main_gamma_normal','main_gamma_lowlight','main_gamma_ei','sub_gamma_normal','sub_gamma_ei']:
        match=re.search(r'\b'+name+r'\s*:\s*\{',config);assert match
        start=match.end();depth=1;end=start
        while depth:
            if config[end]=='{':depth+=1
            elif config[end]=='}':depth-=1
            end+=1
        fields={}
        for field,body in re.findall(r'(\w+)\s*:\s*\{([^{}]*)\}',config[start:end-1]):
            values={}
            for key in ['type','group']:
                m=re.search(r'\b'+key+r'\s*:\s*(\w+)',body)
                if m:values[key]=m[1]
            for key in ['axis','dep_axis']:
                m=re.search(r'\b'+key+r'\s*:\s*\[([^]]*)\]',body)
                if m:values[key]=[s.strip() for s in m[1].split(',') if s.strip()]
            fields[field]=values
        assert fields;modules[name]=fields
    assert modules['main_gamma_normal']['knee_gain']['type']=='calc_knee_data'
    assert modules['main_gamma_normal']['knee_saturation']['type']=='calc_knee_data'
    assert all(modules['sub_gamma_normal'][c+'_lut']['type']=='knee_fusion' for c in 'rgb')
    assert all(modules[m]['gamma_lut']['type']!='knee_fusion' for m in ['main_gamma_normal','main_gamma_lowlight','main_gamma_ei'])
    return {'source_sha256':pins,'registered_module_fields':modules,'calculator_dispatch':routes,
            'named_gamma_compensation_type_occurrences_in_config':len(re.findall('gamma_compensate_ev',config)),
            'scope':'Original registration declarations and calculator pointer table; tuning values and runtime bank contents are excluded.'}


class Original:
    def __init__(self,path):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==PIN,'source hash mismatch'
        self.uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        with path.open('rb') as f:
            elf=ELFFile(f)
            assert elf['e_machine']=='EM_AARCH64'
            segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
            end=max(int(s['p_vaddr'])+int(s['p_memsz']) for s in segs)
            self.uc.mem_map(0,(end+4095)&~4095)
            for s in segs:self.uc.mem_write(int(s['p_vaddr']),s.data())
        self.uc.mem_map(ARENA,0x10000)
        self.uc.mem_map(STACK,0x10000)
        self.uc.mem_map(STOP,0x1000)
        self.uc.reg_write(UC_ARM64_REG_TPIDR_EL0,ARENA+0xf000)
        self.uc.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
        self.allowed=[];self.callbacks={};self.trace=[];self.executed=0
        self.uc.hook_add(UC_HOOK_CODE,self._hook)

    def _hook(self,uc,address,size,_):
        self.executed+=1
        if address in self.callbacks:
            self.callbacks[address]()
            uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
        elif not any(lo<=address<hi for lo,hi in self.allowed):
            raise RuntimeError('unexpected execution outside bounded original block: '+hex(address))

    def u32(self,a,v):self.uc.mem_write(a,struct.pack('<I',int(v)&0xffffffff))
    def u64(self,a,v):self.uc.mem_write(a,struct.pack('<Q',int(v)))
    def read64(self,a):return struct.unpack('<Q',self.uc.mem_read(a,8))[0]
    def words(self,a,v):self.uc.mem_write(a,struct.pack('<'+'I'*len(v),*[int(x)&0xffffffff for x in v]))
    def output(self,a,n,signed=False):return list(struct.unpack('<'+('i' if signed else 'I')*n,self.uc.mem_read(a,4*n)))

    def run(self,start,end,callbacks=None):
        self.allowed=[(start,end)];self.callbacks=callbacks or {};self.executed=0
        self.uc.reg_write(UC_ARM64_REG_SP,STACK+0x8000)
        self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        self.uc.emu_start(start,end,count=100000)
        pc=self.uc.reg_read(UC_ARM64_REG_PC)
        assert pc in [end,STOP],('instruction budget exhausted',hex(pc))

    def run_function(self,name,callbacks=None):
        start,size=FUNCTIONS[name]
        self.allowed=[(start,start+size)];self.callbacks=callbacks or {};self.executed=0
        self.uc.reg_write(UC_ARM64_REG_SP,STACK+0x8000)
        self.uc.reg_write(UC_ARM64_REG_LR,STOP)
        self.uc.emu_start(start,STOP,count=100000)
        assert self.uc.reg_read(UC_ARM64_REG_PC)==STOP,'instruction budget exhausted'

    def slopes(self,values,keypoints):
        n=len(values);assert n==len(keypoints) and 2<=n<=512
        values_at=ARENA+0x1000;keys_at=ARENA+0x2000;out_at=ARENA+0x3000;sp=STACK+0x8000
        self.words(values_at,values);self.words(keys_at,keypoints)
        self.words(out_at,[0x55aa55aa]*(n+2))
        self.u64(sp+0x18,keys_at);self.u64(sp+0x20,values_at);self.u64(sp+0x10,out_at)
        self.u32(sp+0x2c,n)
        # Execute the original contiguous slope block, stopping before publish.
        self.run(0x3bf500,0x3bf55c)
        assert self.output(out_at+4*n,2)==[0x55aa55aa]*2,'output overrun'
        return self.output(out_at,n,signed=True)

    def dispatch(self,ei,lowlight):
        self.uc.mem_write(ARENA,b'\0'*0x8000)
        self.u64(ARENA+0x10,ARENA+0x1000)
        self.u64(ARENA+0x1000+0xe8,ARENA+0x5000)
        self.u32(ARENA+0x5000+0x18,ei)
        self.uc.mem_write(ARENA+0x1000+0x3440,bytes([lowlight]))
        self.uc.reg_write(UC_ARM64_REG_X0,ARENA)
        self.uc.reg_write(UC_ARM64_REG_X1,0x1234)
        self.uc.reg_write(UC_ARM64_REG_X2,0x5678)
        calls=[]
        def callback(name):
            def call():
                assert [self.uc.reg_read(r) for r in [UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2]]==[ARENA,0x1234,0x5678]
                calls.append(name);self.uc.reg_write(UC_ARM64_REG_W0,0)
            return call
        self.run_function('main_gamma_calc_frame',{a:callback(n) for a,n in CALLBACKS.items()})
        assert self.uc.reg_read(UC_ARM64_REG_W0)==0
        return calls

    def fusion(self,source,knee_map,gain):
        self.uc.mem_write(ARENA,b'\0'*0x8000)
        context=ARENA;config=ARENA+0x1000;runtime=ARENA+0x2000;state=ARENA+0x3000
        table=ARENA+0x4000;out=ARENA+0x5000;vtable=ARENA+0x6000
        # Minimal synthetic FlatBuffer: the field is absent. The sole tuning
        # lookup is intercepted and supplies only the synthetic knee_map.
        self.u64(context+0x38,config);self.u64(context+0x48,runtime)
        self.u64(config+0x30,vtable+0x100);self.u32(vtable+0x100,0x100)
        self.uc.mem_write(vtable,struct.pack('<HH',4,4))
        self.u64(runtime+0xe8,state);self.u32(state+0xdc,gain)
        self.words(table,source);self.words(out,[0x55aa55aa]*259)
        calls=[]
        def memset():
            dest=self.uc.reg_read(UC_ARM64_REG_X0);val=self.uc.reg_read(UC_ARM64_REG_X1)&255;n=self.uc.reg_read(UC_ARM64_REG_X2)
            assert n==1028 and STACK<=dest<STACK+0x10000
            self.uc.mem_write(dest,bytes([val])*n);calls.append('memset')
        def lookup():
            descriptor=self.uc.reg_read(UC_ARM64_REG_X2)
            assert self.output(descriptor,1)==[257]
            dest=self.read64(descriptor+8);assert STACK<=dest<STACK+0x10000
            self.words(dest,knee_map);calls.append('synthetic_knee_map_lookup')
            self.uc.reg_write(UC_ARM64_REG_W0,1)
        for reg,val in [(UC_ARM64_REG_X0,context),(UC_ARM64_REG_X1,table),(UC_ARM64_REG_X2,out),(UC_ARM64_REG_X3,257)]:self.uc.reg_write(reg,val)
        self.run_function('adj_plat_calc_knee_fusion',{0x4a550:memset,0x3b4130:lookup})
        assert calls==['memset','synthetic_knee_map_lookup']
        assert self.output(out+1028,2)==[0x55aa55aa]*2,'output overrun'
        return self.output(out,257)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--library',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--config',type=Path,required=True);ap.add_argument('--schema',type=Path,required=True)
    args=ap.parse_args();native=Original(args.library);rng=np.random.default_rng(41013)
    out={'schema':'hasselblad-stage41m-original-knee-synthetic-replay-v1','source_sha256':PIN,
         'synthetic_inputs_only':True,'real_camera_pipeline_executed':False,
         'production_photo_output_changed':False,'firmware_bytes_tables_disassembly_exported':False}
    out['functions']={n:{'start':hex(a),'size':s,'code_sha256':hashlib.sha256(native.uc.mem_read(a,s)).hexdigest()} for n,(a,s) in FUNCTIONS.items()}
    out['configuration']=configuration_evidence(native,args.config,args.schema)
    dispatch=[]
    for ei,low in [(0,0),(0,1),(1,0),(1,1),(2,255)]:
        actual=native.dispatch(ei,low);expected=['common','ei' if ei else 'lowlight' if low else 'normal'];assert actual==expected
        dispatch.append({'synthetic_ei_flag':ei,'synthetic_lowlight_flag':low,'callback_sequence':actual})
    out['dispatch']={'cases':dispatch,'whole_dispatcher_executed':True,'selected_callbacks_intercepted':True,'flags_in_real_captures_known':False}
    slope_cases=[([0,1],[0,3]),([4,1],[0,2]),([1,10],[7,7]),([0,524288],[0,1]),([0,-524288],[0,-1])]
    for _ in range(256):
        n=int(rng.integers(2,65));keys=np.cumsum(rng.integers(1,8192,n)).tolist();values=rng.integers(-1000000,1000000,n).tolist();slope_cases.append((values,keys))
    entries=0
    for vals,keys in slope_cases:
        assert native.slopes(vals,keys)==knee_slopes(vals,keys),'slope reconstruction mismatch';entries+=len(vals)
    out['slopes']={'cases':len(slope_cases),'entries_compared':entries,'exact_matches':True,'original_block_start':'0x3bf500','original_block_end_exclusive':'0x3bf55c','scale':4096,'arithmetic':'signed 32-bit difference, wrapping left shift 12, signed divide truncating toward zero; final entry zero','scope':'Contiguous original arithmetic block with synthetic pointers; not the whole _calc_knee_data function or an RGB pixel equation.'}
    fusion_cases=[]
    for gain in [0,1,512,1024,2048,4096]:fusion_cases.append((list(range(257)),list(range(257)),gain))
    # This synthetic interpolation distinguishes exact operation-order float32
    # from a tempting float64 rewrite (6234 versus 6233 after truncation).
    sensitive=[0]*257;sensitive[65]=37392;sensitive[66]=-31519
    fusion_cases.append((sensitive,[99]*257,677))
    for trial in range(64):
        map_max=513 if trial%2 else 65536
        fusion_cases.append((rng.integers(-65535,65536,257).tolist(),rng.integers(0,map_max,257).tolist(),int(rng.integers(0,4097))))
    for source,mapping,gain in fusion_cases:assert native.fusion(source,mapping,gain)==fusion_table(source,mapping,gain),'fusion reconstruction mismatch'
    out['fusion']={'cases':len(fusion_cases),'entries_compared':257*len(fusion_cases),'exact_matches':True,'whole_helper_executed':True,'tuning_lookup_intercepted':True,'table_entries':257,'index_scale_denominator':1024,'float32_sensitive_synthetic_result':6234,'float64_alternative_result':6233,'scope':'Original full helper with synthetic knee-map lookup; no claim that this path is active in supplied captures.'}
    noops=[]
    for name in ['adj_plat_calc_gamma_lut_compensate_ev','adj_plat_calc_knee_gain_over_isp_max']:
        before=bytes(native.uc.mem_read(ARENA,0x8000));native.uc.reg_write(UC_ARM64_REG_X0,ARENA)
        native.run_function(name)
        assert native.uc.reg_read(UC_ARM64_REG_W0)==0 and bytes(native.uc.mem_read(ARENA,0x8000))==before
        assert native.executed==2;noops.append(name)
    out['platform_noop_hooks']=noops
    out['status']='PASS_bounded_original_knee_preparation'
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':out['status'],'dispatch_cases':len(dispatch),'slope_cases':len(slope_cases),'fusion_cases':len(fusion_cases),'original_instruction_and_reconstruction_agree':True}))


if __name__=='__main__':main()
