#!/usr/bin/env python3
"""Bounded default SDR CPU finishing; original private code is the oracle."""
import argparse, ctypes, hashlib, json, struct, subprocess, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_import_stage52'))
from audit_import52 import ImportRunner, CORR, PARAMS, SHARED_DESC, load_private, delta, y
from audit_gradation51 import SHARED, default_curve
from audit_gpu50 import BUILD
from audit_output49 import cmm_oracle, independent_matrix
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X2, UC_ARM64_REG_PC, UC_ARM64_REG_X30

y.ALLOWED.update({'_ZNK16CImageCorrection13GetSaturationEv','_ZNK16CImageCorrection16GetUnsharpRadiusEv',
    '_ZNK16CImageCorrection20GetUnsharpNoiseLimitEv','_ZNK16CImageCorrection19GetUnsharpDarkLimitEv'})

class Runner55(ImportRunner):
    def hook(self,cpu,address,size,user):
        name=self.e.plt.get(address,'')
        if self.record_builder and name=='_ZN16CSharpnessFilterC1Eidiiidd':
            self.objects[cpu.reg_read(UC_ARM64_REG_X0)]='Sharpness'
            cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30));return
        if self.record_builder and name.startswith('_ZN15CImageProcessor13EmplaceFilterI16CGradationFilter'):
            self.gradation_flags.append(bytes(self.u.mem_read(cpu.reg_read(UC_ARM64_REG_X2),1))[0])
        return super().hook(cpu,address,size,user)
    def bind_graph(self):
        self.sequence,self.parameters,self.gradation_flags=[],[],[]
        self.flags=(0,0);self.record_builder=True
        self.call(BUILD,(0x100a5000,SHARED_DESC,PARAMS,CORR,SHARED,0,0,0))
        self.record_builder=False
        assert self.gradation_flags==[1]
        assert self.sequence==['ColorCorrectAll','FilmCurve','16CGradationFilter','Sharpness','ColorSpaceConvert']
        assert self.parameters==[[1,0,3]]
        return {'sdr_import_tool_version':4,'gradation_version':1,'sequence':self.sequence,
                'live_graph_output_parameters':self.parameters,'graph_ownership_fixture':True,'sharpness_constructor_fixture':True,'sharpness_ported':False}

def port_library(work):
    here=Path(__file__).resolve().parent;lib=work/'post55.so'
    subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Wconversion','-Werror','-ffp-contract=off',
                    '-shared','-fPIC',str(here/'post55.c'),'-lm','-o',str(lib)],check=True)
    c=ctypes.CDLL(str(lib));u16=np.ctypeslib.ndpointer(dtype=np.uint16,flags='C_CONTIGUOUS');d=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
    c.hb55_default_curve.argtypes=[u16];c.hb55_gradate.argtypes=[u16,u16,ctypes.c_size_t,u16]
    c.hb55_output_rgb16.argtypes=[u16,ctypes.c_size_t,d,ctypes.c_double,u16]
    table=np.empty(65536,np.uint16);assert c.hb55_default_curve(table)==0
    return c,table

def main():
    p=argparse.ArgumentParser()
    for n in ('apk','profile','work','safe-receipt'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--prepared',type=Path)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    before=hashlib.sha256(a.apk.read_bytes()).digest()
    elf,private=load_private(a.apk);r=Runner55(elf,private)
    r.configure([1.4,1.,.7]);r.process();native_tables=r.calculate();graph=r.bind_graph()
    c,table=port_library(a.work)
    assert np.array_equal(table,default_curve()) and np.array_equal(native_tables[2:],np.stack([table]*3))
    print('Default tables exact; actual SDR import selects gradation version 1',flush=True)
    cube=np.rint(np.stack(np.meshgrid(*[np.linspace(0,65535,17)]*3,indexing='ij'),-1).reshape(-1,3)).astype(np.uint16)
    ramp=np.repeat(np.arange(0,65536,32,dtype=np.uint16)[:,None],3,1)
    edges=np.array([[0,0,0],[65535]*3,[1,1,1],[65534]*3,[0,1,65535],[65535,0,1],[1,65535,0]],np.uint16)
    random=np.random.default_rng(55).integers(0,65536,(4096,3),dtype=np.uint16)
    pixels=np.ascontiguousarray(np.vstack([cube,ramp,edges,random]))
    actual=np.empty_like(pixels);assert c.hb55_gradate(table,pixels,len(pixels),actual)==0
    native=r.cpu(pixels,1);gradation=delta(actual,native)
    print('Gradation',gradation,flush=True)
    if gradation['max_abs_difference']:
        np.savez(a.work/'gradation_debug.npz',input=pixels,actual=actual,native=native,table=table)
    assert gradation['max_abs_difference']==0
    converter=r.converter(0);matrix=r.doubles(converter+0x20,9).reshape(3,3)
    transfer=struct.unpack('<di4xd',bytes(r.u.mem_read(converter+8,24)))
    assert transfer[:2]==(1.,1) and np.max(abs(matrix-independent_matrix(r,0,2)))<1e-12
    output=np.empty_like(actual);assert c.hb55_output_rgb16(actual,len(actual),matrix,transfer[2],output)==0
    native_output=r.convert(converter,native);output_check=delta(output,native_output)
    print('Output',output_check,flush=True);assert output_check['max_abs_difference']<=1
    independent=delta(output,cmm_oracle(actual,matrix,transfer));assert independent['max_abs_difference']<=1
    # Data-only extension: same colour/LUT/film payload; native output matrix stays private.
    profile=a.profile.read_bytes();assert profile[:8]==b'HB43LUT1'
    assert hashlib.sha256(profile[:-32]).digest()==profile[-32:]
    extension=struct.pack('<4i10d',1,0,2,1,*matrix.ravel(),transfer[2])
    body=b'HB55LUT1'+profile[8:-32]+extension
    extended=body+hashlib.sha256(body).digest()
    _,_,temperature,_,film,space=struct.unpack('<6i',profile[8:32]);assert space==0
    (a.work/f'Stage55_Private_Curve{film}_{temperature}K.hbc').write_bytes(extended)
    room=None
    if a.prepared:
        codes=np.fromfile(a.prepared/'highlight_rgb16.bin',dtype='<u2').reshape(-1,3)
        grad=np.empty_like(codes);out=np.empty_like(codes)
        assert c.hb55_gradate(table,codes,len(codes),grad)==0
        assert c.hb55_output_rgb16(grad,len(grad),matrix,transfer[2],out)==0
        index=np.unique(np.r_[np.linspace(0,len(codes)-1,1024).astype(int),np.argmax(codes,axis=0)])
        native_grad=r.cpu(codes[index],1);native_out=r.convert(converter,native_grad)
        room={'pixels':len(codes),'gradation_native_sample':delta(grad[index],native_grad),
              'output_native_sample':delta(out[index],native_out),'independent_output_all':delta(out,cmm_oracle(grad,matrix,transfer))}
        assert room['gradation_native_sample']['max_abs_difference']==0
        assert room['output_native_sample']['max_abs_difference']<=1
        assert room['independent_output_all']['max_abs_difference']<=1
        grad.tofile(a.work/'gradation_rgb16.bin');out.tofile(a.work/'output_rgb16.bin')
        old=np.fromfile(a.prepared/'display_argb.bin',dtype='<u4').reshape(2,-1)[1]
        old=np.stack([(old>>s)&255 for s in (16,8,0)],1)
        new=np.floor(out.astype(float)/257+.5).astype(np.uint8)
        room['display_effect_8bit']=delta(new,old)
        room['fraction_pixels_over_two_codes']=float(np.mean(np.max(abs(new.astype(int)-old.astype(int)),axis=1)>2))
        print('Photographic measurement',room,flush=True)
    assert hashlib.sha256(a.apk.read_bytes()).digest()==before
    result={'schema':'hasselblad-stage55-native-post-v1','status':'PASS_BOUNDED_CPU_FINISHING',
       'graph_binding':graph,'default_curve_entries_exact':65536,'synthetic_pixels':len(pixels),
       'gradation_native':gradation,'output_native':output_check,'output_independent':independent,
       'photographic_measurement':room,'scene_fitted_parameters':0,'profile_colour_payload_unchanged':True,
       'output_route':{'source_special_profile':0,'destination_special_profile':2,'normalizer':65535},
       'host_libm_fixture':True,'input_APK_unchanged':True,'original_live_display_reproduced':False,
       'phone_sensor_adaptation_experimental':True,'capture_renderer_changed':False,'full_phocus_equivalence':False}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
