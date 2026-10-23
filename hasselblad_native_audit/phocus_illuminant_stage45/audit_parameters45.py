#!/usr/bin/env python3
"""Execute original Android colour parameter preparation with explicit fixtures.

The owner APK is a private, hash-pinned input. No vendor code, calibration arrays
or photographs are exported. Factory ownership and lens gain reduction are
fixtures; colour construction and the complete UpdateParameters body execute.
"""
import argparse,json,re,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/x) for x in ('phocus_stage41z','phocus_port_stage42')]
from prepare_preview42 import load_private,y
import inspect_phocus_input41z as z
from unicorn.arm64_const import *

UPDATE='_ZN22CColorCorrectAllFilter16UpdateParametersEv'
FILM_UPDATE='_ZN16CFilmCurveFilter16UpdateParametersEv'
EFFECTIVE='_ZNK16CImageCorrection18EffectiveFilmCurveE14eFilmCurveType'
REDUCTION='_Z22GetGainReductionFactorRK16CImageCorrectionRK15sRawDescription'
ADDITIONAL={UPDATE,FILM_UPDATE,
 '_ZN16CFilmCurveFilter17CreateLinearCurveEv',
 '_ZNK16CImageCorrection15GetHDRLimitGainEv',
 '_ZN19CRawColorCorrection17GetGradationCurveEv',
 '_ZN17CGradationManager17GetGradationCurveEv',
 '_ZN24ColorCorrectionAllFilterC1Ev','_ZN24ColorCorrectionAllFilterD1Ev',
 '_ZNK19CRawColorCorrection18GetColorCorrectionERP16CColorCorrection',
 '_ZN12CUniqueImageIfLi4ENSt6__ndk110unique_ptrIA_f14AlignedDeleterIfEEEEC2Eiii',
 '_ZNSt6__ndk16vectorIfNS_9allocatorIfEEE18__assign_with_sizeB8ne180000IPKfS6_EEvT_T0_l',
 '_ZN9Matrix3x33RowEi'}
y.ALLOWED |= ADDITIONAL
FILTER,FILM_FILTER,VTABLE,DELETE=0x10070000,0x10072000,0x10075000,0x30004000

def shader_facts(elf):
    rows=[s for i,s in enumerate(elf.sym) if elf.name(i)=='colorCorrectAll_fragmentShaderSource']
    assert len(rows)==1
    ptr=elf.relocation(int(rows[0]['addr']))[0]
    source=elf.read(ptr,16384).split(b'\0',1)[0]
    active=re.sub(r'/\*.*?\*/|//[^\n]*','',source.decode(),flags=re.S)
    main=active.split('void main()',1)[1]
    assert 'uniform vec4 uGain;' in active and 'uGain' not in main and 'applyLocalWB(' not in main
    return {'symbol':'colorCorrectAll_fragmentShaderSource','source_sha256':y.sha(source),
        'declares_gain_uniform':True,'active_main_references_gain_uniform':False,
        'active_main_calls_local_white_balance':False,'shader_executed':False,
        'upstream_white_balance_ownership_resolved':False}

class ParameterRunner(z.InputRunner):
    def __init__(self,elf):
        super().__init__(elf)
        self.reduction=1.;self.reduction_calls=0;self.delete_calls=0
        self.u.mem_write(FILTER-16,b'\xa5'*16)
        self.u.mem_write(FILTER+0x1f8,b'\xa5'*16)
        self.u.mem_write(FILM_FILTER-16,b'\xa5'*16)
        self.u.mem_write(FILM_FILTER+0x80,b'\xa5'*16)
        self.u.mem_write(z.RAW,struct.pack('<Q',VTABLE))
        self.u.mem_write(VTABLE+8,struct.pack('<Q',DELETE))
    def hook(self,cpu,address,size,user):
        if address==DELETE:
            assert cpu.reg_read(UC_ARM64_REG_X0)==z.RAW
            self.delete_calls+=1
        elif self.e.plt.get(address)==REDUCTION:
            assert [cpu.reg_read(UC_ARM64_REG_X0),cpu.reg_read(UC_ARM64_REG_X1)]==[z.CORRECTION,z.DESCRIPTION]
            self.reduction_calls+=1
            cpu.reg_write(UC_ARM64_REG_D0,struct.unpack('<Q',struct.pack('<d',self.reduction))[0])
        else:
            return super().hook(cpu,address,size,user)
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))
    def check_guards(self):
        super().check_guards()
        if hasattr(self,'reduction'):
            assert bytes(self.u.mem_read(FILTER-16,16))==bytes(self.u.mem_read(FILTER+0x1f8,16))==b'\xa5'*16
            assert bytes(self.u.mem_read(FILM_FILTER-16,16))==bytes(self.u.mem_read(FILM_FILTER+0x80,16))==b'\xa5'*16
    def floats(self,ptr,n):
        return np.frombuffer(bytes(self.u.mem_read(ptr,n*4)),dtype='<f4').copy()
    def vector(self,offset,n):
        lo,hi,end=struct.unpack('<3Q',bytes(self.u.mem_read(FILTER+offset,24)))
        assert hi-lo==n*4 and end>=hi
        return self.floats(lo,n)
    def put(self,ptr,offset,fmt,*values):
        self.u.mem_write(ptr+offset,struct.pack(fmt,*values))

def audit(elf,profile):
    for name,pair in y.INITIALIZERS.items():elf.func[name]=pair
    r=ParameterRunner(elf);r.profile=profile
    r.call(y.DECODE,(r.obj,r.coder));r.u.mem_write(r.obj+9,b'\1')
    frozen=[(r.obj,bytes(r.u.mem_read(r.obj,0x318)))]+[(p+16,bytes(r.u.mem_read(p+16,n))) for p,n in r.allocations]
    for name in y.INITIALIZERS:r.call(name)
    r.call(y.GM_CTOR,(y.GM,1,1))
    r.put(y.RAW,8,'<Q',y.GM);r.put(y.RAW,0xb0,'<Q',y.CC)
    r.put(y.RAW,0x250,'<3i',22,6,0)
    r.put(y.RAW,0x228,'<3d',1.,1.,1.)
    r.put(y.RAW,0x248,'<d',1.)
    r.put(FILTER,0x68,'<2Q',z.DESCRIPTION,z.CORRECTION)
    r.put(FILM_FILTER,0x48,'<2Q',z.DESCRIPTION,z.CORRECTION)
    film_buffer=r.alloc(65536*4)
    r.put(FILM_FILTER,0x58,'<3Q',film_buffer,film_buffer+65536*4,film_buffer+65536*4)
    r.put(z.DESCRIPTION,0x344,'<2i',22,6)
    r.put(z.DESCRIPTION,0x18,'<d',1.25)
    r.put(z.DESCRIPTION,0x28,'<3d',2.1,1.,1.5)
    r.put(z.DESCRIPTION,0x40,'<d',.8)
    r.put(z.DESCRIPTION,0x50,'<d',1.1)
    r.put(z.CORRECTION,0x91,'<B',1)
    r.put(z.CORRECTION,0x428,'<i',2)
    B,A,W=y.matrix_constants(elf)
    wb_matrix=(np.array(profile['mf'])*.5+1).reshape(3,3)@np.diag(np.array(profile['vf'])*.5+1)
    table=z.temperature_table(elf)
    cases=[]
    # Every temperature is exercised with both curves and opposite tint values.
    for temp in (2400,2850,3050,3200,4000,5550):
        for film,tint in ((0,-.003),(1,.003)):
            for scalar in (1.,1.7):
                r.put(z.CORRECTION,0x29c,'<i',temp)
                r.put(z.CORRECTION,0x2a0,'<d',tint)
                r.put(z.CORRECTION,0x2cc,'<i',film)
                r.put(z.CORRECTION,0x93,'<B',scalar!=1)
                r.put(z.CORRECTION,0x2a8,'<d',scalar)
                r.put(y.GM,4,'<i',film)
                r.put(y.RAW,0x1f0,'<2d',float(temp),1.)
                r.call(y.RAW_INIT,(y.RAW,))
                source=[(p,bytes(r.u.mem_read(p,n))) for p,n in ((z.DESCRIPTION,0x350),(z.CORRECTION,0x430),(y.CC,0x298))]
                r.reduction=.8 if scalar!=1 else 1.
                r.call(UPDATE,(FILTER,))
                assert r.u.reg_read(UC_ARM64_REG_X0)==1
                ints,doubles=r.factory_calls[-1]
                assert ints==[22,6,film,0,0,0,0] and np.array_equal(doubles,[temp,1.,1.])
                gains=z.temp_to_gain_oracle(temp,tint,np.linalg.inv(wb_matrix),table,elf)
                expected_gain=np.r_[gains/gains.max(),1.].astype(np.float32)
                gain_check=y.check(r.vector(0x108,4),expected_gain,0)
                first=B@A@y.matrix_oracle(profile,temp).reshape(3,3)
                second=np.linalg.inv(B)
                emitted_first=np.stack([r.vector(o,4) for o in (0x78,0x90,0xa8)])
                emitted_second=np.stack([r.vector(o,4) for o in (0xc0,0xd8,0xf0)])
                first_check=y.check(emitted_first,np.c_[first,np.zeros(3)].astype(np.float32),0)
                second[:,1:]/=32
                second_check=y.check(emitted_second,np.c_[second,np.zeros(3)].astype(np.float32),0)
                ptr,buf,width,height,pitch,channels=struct.unpack('<2Q4i',bytes(r.u.mem_read(FILTER+0x48,32)))
                assert ptr==buf and (width,height,pitch,channels)==(105,89,420,4)
                actual=r.floats(ptr,height*pitch).reshape(height,width,4)
                grid=y.lut_oracle(profile,temp,False)
                lut_check=y.check(actual,np.concatenate([grid,np.zeros_like(grid)],axis=2).astype(np.float32),0)
                y.check(r.vector(0x120,2),np.array([-20,-32],np.float32),0)
                y.check(r.vector(0x138,2),np.array([104,88],np.float32),0)
                y.check(r.vector(0x170,4),y.shadow_oracle(elf,0,1).astype(np.float32),0)
                expected_scalar=np.float32(gains.max()*1.25*.8*1.1*scalar)
                y.check(r.floats(FILTER+0x188,1),np.array([expected_scalar]),0)
                y.check(r.floats(FILTER+0x18c,1),np.array([np.float32(gains.min()/gains.max())]),0)
                y.check(r.floats(FILTER+0x194,1),np.array([np.float32(r.reduction)]),0)
                y.check(r.floats(FILTER+0x198,2),np.array([temp,tint],np.float32),0)
                assert r.linearization_arguments[-1]==scalar
                r.call(FILM_UPDATE,(FILM_FILTER,))
                assert r.u.reg_read(UC_ARM64_REG_X0)==1
                expected_curve=y.curve_oracle(elf,film,1)*np.float32(1/65535)
                film_check=y.check(r.floats(film_buffer,65536),expected_curve,0)
                y.check(r.floats(FILM_FILTER+0x70,3),np.ones(3,np.float32),0)
                assert all(bytes(r.u.mem_read(p,len(b)))==b for p,b in source)
                cases.append({'temperature':temp,'tint_fixture':tint,'requested_film':film,'scalar_fixture':scalar,
                    'factory_temperature_exact':True,'gain_vector':gain_check,'input_matrix':first_check,
                    'output_matrix':second_check,'lut_float32':lut_check,'other_uniforms_exact':True,
                    'film_filter_normalized_curve':film_check,
                    'source_objects_unchanged':True})
        print(f'Original Android parameters verified at {temp} K',flush=True)
    # Exercise the inherited-source sentinel and reproduction-model override.
    films=[]
    for enabled in (False,True):
        for model in (0,1,4):
            for requested in (0,1,4,7):
                for captured in (0,1):
                    r.put(z.CORRECTION,0x91,'<B',enabled)
                    r.put(z.CORRECTION,0x2c8,'<i',model)
                    r.put(z.CORRECTION,0x2cc,'<i',requested)
                    r.call(EFFECTIVE,(z.CORRECTION,captured))
                    expected=captured if not enabled else 7 if model in (1,4) else captured if requested==4 else requested
                    assert r.u.reg_read(UC_ARM64_REG_X0)==expected
                    films.append({'enabled':enabled,'model':model,'requested_film':requested,'source_film':captured,'selected':expected})
    assert all(bytes(r.u.mem_read(p,len(b)))==b for p,b in frozen)
    r.check_guards()
    return {'schema':'hasselblad-stage45-android-parameters-v1','status':'PASS_BOUNDED_NATIVE_PARAMETERS',
        'parameter_cases':cases,'effective_film_cases':films,'original_functions_executed':sorted(r.called),
        'factory_is_argument_recording_fixture':True,'factory_returns_prepared_original_raw_object':True,
        'lens_gain_reduction_is_scalar_fixture':True,'destruction_is_ownership_fixture':True,
        'full_update_body_executed':True,'profile_and_source_immutability_pass':True,
        'film_filter_update_and_curve_preparation_executed':True,
        'static_shader_inspection':shader_facts(elf),
        'allocation_and_object_guards_pass':True,'live_android_settings_observed':False,
        'gpu_shader_executed':False,'phone_temperature_mapping_validated':False,'capture_renderer_changed':False,
        'full_phocus_equivalence':False,'bounds':'Sensor22/filter6, normal model, working space0, SDR tool code2; no live factory/lens/gain-map lifecycle or GPU dispatch.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--apk',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path)
    a=p.parse_args();assert __debug__
    before=y.sha(a.apk.read_bytes());elf,profile=load_private(a.apk)
    result=audit(elf,profile);assert y.sha(a.apk.read_bytes())==before
    a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'parameter_cases':len(result['parameter_cases']),'film_cases':len(result['effective_film_cases'])}))
if __name__=='__main__':main()
