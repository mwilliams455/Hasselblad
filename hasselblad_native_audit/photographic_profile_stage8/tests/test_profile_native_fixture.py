#!/usr/bin/env python3
"""Independent C vs original native librcam.so OUTPUTS (previously captured).

Source: photographic_path/lut_profile_native_execution.json, twelve cases
executed under firmware-matching Android9/Bionic QEMU before Stage8. The
source uses a deterministic synthetic 8x7 packed signed-lane fixture and no
proprietary profile data. Not a pixel sampler or production rendering test.
"""
import ctypes as C
import hashlib
import json
import pathlib
import random
import subprocess
import tempfile

HERE=pathlib.Path(__file__).resolve().parent
SRC=HERE.parent/'src'/'hb_main_lut_profile.c'
ORIG=HERE/'original_native_12_cases.json'

class Receipt(C.Structure):
    _fields_=[('schema',C.c_uint32),('cct_first_index',C.c_uint32),('cct_fraction_q8',C.c_uint32),
              ('gamut_index',C.c_uint32),('gamut_fraction_q8',C.c_uint32),('words_written',C.c_uint32),
              ('pixel_sampler_verified',C.c_uint32),('photographic_render_authorized',C.c_uint32)]

def pack(low,high):return (low&65535)|((high&65535)<<16)
def component(word,lane):
    v=(word>>(16*lane))&65535
    return v-65536 if v>=32768 else v

def mix(a,b,f):return a+((b-a)*f//256) # Python floor division

def get_coeff(cct):
    knots=[2400,3050,5550,9100]
    if cct<knots[0]:return 0,0
    if cct>=knots[-1]:return 2,256
    for i in range(3):
        if cct<knots[i+1]:return i,(cct-knots[i])*256//(knots[i+1]-knots[i])
    assert False

def python_oracle(source,w,cct,gamut):
    c,f=get_coeff(cct)
    out=[]
    for j in range(w):
        l=[]
        for half in range(2):
            a=mix(component(source[c*w+j],half),component(source[(c+1)*w+j],half),f)
            b=mix(component(source[(c+4)*w+j],half),component(source[(c+5)*w+j],half),f)
            l.append(mix(a,b,256*gamut))
        out.append(pack(l[0],l[1]))
    return out

def synthetic(w):
    return [pack((p*7171+j*2339+137)%60001-30000,
                 30000-(p*4813+j*3251+977)%60001)
            for p in range(8) for j in range(w)]

def native_call(lib, source, words, cct, gamut, invalid=False):
    A=(C.c_uint32*len(source))(*source)
    guard=(C.c_uint32*(words+8))(*([0xA5A5A5A5]*(words+8)))
    dst=C.cast(C.byref(guard,4*C.sizeof(C.c_uint32)),C.POINTER(C.c_uint32))
    receipt=Receipt()
    C.memset(C.byref(receipt),0xA5,C.sizeof(receipt))
    original_receipt=bytes(receipt)
    before=list(A)
    result=lib.hb_main_lut_prepare(A,len(source),words,cct,gamut,dst,words,C.byref(receipt))
    assert list(A)==before,'source_mutated'
    assert list(guard[:4])==[0xA5A5A5A5]*4 and list(guard[4+words:])==[0xA5A5A5A5]*4
    if invalid:
        assert result!=0 and bytes(receipt)==original_receipt and list(guard)==[0xA5A5A5A5]*(words+8)
        return None
    assert result==0, result
    assert receipt.schema==1 and receipt.words_written==words
    assert not receipt.pixel_sampler_verified and not receipt.photographic_render_authorized
    assert (receipt.cct_first_index,receipt.cct_fraction_q8)==get_coeff(cct)
    assert (receipt.gamut_index,receipt.gamut_fraction_q8)==(0,256*gamut)
    return list(guard[4:words+4])

def run():
    cases=json.loads(ORIG.read_text())
    assert len(cases['cases'])==12
    with tempfile.TemporaryDirectory() as tmp:
        out=pathlib.Path(tmp)/'libstage8_profile.so'
        subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-Wpedantic',
                        '-fPIC','-shared',str(SRC),'-o',str(out)],check=True)
        lib=C.CDLL(str(out))
        lib.hb_main_lut_prepare.argtypes=[C.POINTER(C.c_uint32),C.c_size_t,C.c_size_t,
                                          C.c_int32,C.c_int32,C.POINTER(C.c_uint32),C.c_size_t,
                                          C.POINTER(Receipt)]
        lib.hb_main_lut_prepare.restype=C.c_int
        words=7; src=synthetic(words)
        for test in cases['cases']:
            actual=native_call(lib,src,words,test['cct'],test['gamut'])
            assert actual==test['output']==python_oracle(src,words,test['cct'],test['gamut']),test['case']
            assert [list(get_coeff(test['cct'])),[0,256*test['gamut']]]==test['coefficients']
        # Reproduce the 6144-word camera-sized contract using ONLY synthetic words.
        rng=random.Random(20261022)
        cam=[pack(rng.randint(-32768,32767),rng.randint(-32768,32767)) for _ in range(8*6144)]
        count=0
        for gamut in (0,1):
            for cct in (0,2399,2400,2725,3050,4300,5550,7001,9099,9100,25000):
                actual=native_call(lib,cam,6144,cct,gamut)
                assert actual==python_oracle(cam,6144,cct,gamut),(cct,gamut)
                count+=1
        # Size/shape/gamut invalidity must leave all output bytes unchanged.
        for gamut in (-1,2,3): native_call(lib,src,words,4300,gamut,True)
        # Reject overlap (including source==destination) without output mutation.
        a=(C.c_uint32*56)(*src)
        r=Receipt();C.memset(C.byref(r),0xA5,C.sizeof(r))
        before=list(a);receipt_before=bytes(r)
        status=lib.hb_main_lut_prepare(a,56,7,4300,0,a,7,C.byref(r))
        assert status==4 and list(a)==before and bytes(r)==receipt_before
        # Explicit wrong geometry and destination capacity.
        for size in (0,6145):
            A=(C.c_uint32*56)(*src)
            result=(C.c_uint32*10)(*([0xA5A5A5A5]*10))
            receipt=Receipt(); C.memset(C.byref(receipt),0xA5,C.sizeof(receipt))
            status=lib.hb_main_lut_prepare(A,56,size,4300,0,result,10,C.byref(receipt))
            assert status==2 and list(result)==[0xA5A5A5A5]*10
        report={'schema':'hasselblad-stage8-portable-profile-validation-v1',
                'firmware_reference':'X2D II 100C 1.3.16.2 librcam.so',
                'reference_native_execution':'12 cases from previously captured original functions',
                'native_function_outputs_compared':12*7,
                'synthetic_full_profile_cases':count,
                'synthetic_full_profile_lane_comparisons':count*6144*2,
                'native_fixture_cases_passed':12,
                'status':'PASS',
                'shape':'8 profiles x 6144 packed two-int16 words; tests use synthetic values',
                'photographic_lut_payload_present':False,
                'pixel_colour_sampler_implemented':False,
                'hasselblad_awb_calibrated':False,
                'photographic_render_authorized':False,
                'production_photon_unchanged':True,
                'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest()}
        path=HERE.parent/'reports'/'STAGE8_PUBLIC_TEST_RESULT.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
if __name__=='__main__':run()
