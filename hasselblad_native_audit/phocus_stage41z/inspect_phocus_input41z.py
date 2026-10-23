#!/usr/bin/env python3
"""Replay Phocus white-balance conversion and optional channel linearization.

Requires the independently supplied APK. No vendor arrays or photo metadata are
exported. This is a research audit, not an Android renderer implementation.
"""
import sys
from pathlib import Path
for stage in ('phocus_stage41w', 'phocus_stage41x', 'phocus_stage41y'):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / stage))
import argparse, io, json, plistlib, struct, zipfile
from importlib.metadata import version
import numpy as np
import tifffile
from unicorn.arm64_const import *
import inspect_phocus_pipeline41y as pipeline
from inspect_phocus_profiles41w import Elf, APK_SHA, LIB_SHA, TARGET, DECODE, decrypt_blocks, sha
from inspect_phocus_pipeline41y import NativePipeline, RAW, CC, check

GAIN_TO_TEMP = '_ZN20CColorTempConversion17GainToTempAndTintE9eCCDTypes13eIRFilterType6CArrayIdLi3E23Matrix3x1InitializationERiRdb'
TEMP_TO_GAIN = '_ZN20CColorTempConversion17TempAndTintToGainE9eCCDTypes13eIRFilterTypeid'
CONVERTER = '_ZN20CColorTempConversionC1E9eCCDTypes13eIRFilterType'
LINEARIZE = '_ZN19CRawColorCorrection22CalculateLinearizationEd'
APPLY = '_ZNK19CRawColorCorrection18ApplyLinearizationEPtiPf'
CREATE = '_ZN24ColorCorrectionAllFilter21CreateColorCorrectionEPK15sRawDescriptionPK16CImageCorrection'
SOURCE_GAIN = '_ZN24ColorCorrectionAllFilter18gainFromSourceInfoEPK15sRawDescriptionPK16CImageCorrection'
EXPOSURE = '_ZN24ColorCorrectionAllFilter7GetHrEVEPK16CImageCorrectionPK15sRawDescription'
FACTORY = '_ZN19CRawColorCorrection21NewRawColorCorrectionE9eCCDTypes13eIRFilterTypedd14eFilmCurveType11eColorModelPK14CCLCalibration13eWorkingSpacebd'
EXTRA_ALLOWED = {
    GAIN_TO_TEMP, TEMP_TO_GAIN, CONVERTER, LINEARIZE, APPLY, CREATE, SOURCE_GAIN, EXPOSURE,
    '_ZNK16CImageCorrection18EffectiveFilmCurveE14eFilmCurveType',
    '_ZNK20CColorTempConversion17GainToTempAndTintEdddRiRdb',
    '_ZNK20CColorTempConversion17TempAndTintToGainEid',
    '_ZN20CColorTempConversionD1Ev',
    '_ZN15CRawColorParams30GetXYZ2RawRGBNeutralizedMatrixE9eCCDTypes13eIRFilterType11eIlluminanti',
    '_ZN15CRawColorParams30GetXYZ2RawRGBNeutralizedMatrixE13uColorProfile11eIlluminant',
    '_ZNK7CXMLLut19GetColorMatrixFlashEv',
    '_ZNK7CXMLLut21GetNeutralVectorFlashEv',
    '_ZN9Matrix3x36ColumnEi',
    '_ZN9Matrix3x33SetEddddddddd',
    '_ZN9Matrix3x3C1E6CArrayIdLi3E23Matrix3x1InitializationES2_S2_',
    '_ZN16CColorCorrection22CalculateLinearizationEd',
}
# This explicit extension keeps the inherited original-function guard intact.
pipeline.ALLOWED = pipeline.ALLOWED | EXTRA_ALLOWED
CONV = 0x10040000
TEMP_OUT, TINT_OUT = 0x10050000, 0x10050010
DESCRIPTION, CORRECTION = 0x10060000, 0x10061000


class InputRunner(NativePipeline):
    def __init__(self, elf):
        super().__init__(elf)
        self.ccnc = False
        self.factory_calls = []
        self.linearization_arguments = []
        self.u.mem_write(CONV - 16, b'\xa5' * 16)
        self.u.mem_write(CONV + 0x98, b'\xa5' * 16)
        for ptr,length in ((DESCRIPTION,0x350),(CORRECTION,0x430)):
            self.u.mem_write(ptr-16,b'\xa5'*16)
            self.u.mem_write(ptr+length,b'\xa5'*16)

    def hook(self, cpu, address, size, user):
        if address == 0x30002000:
            key = self.getstr(cpu.reg_read(UC_ARM64_REG_X1))
            self.config_queries.append(key)
            cpu.reg_write(UC_ARM64_REG_X0, int(self.ccnc and key == 'CCNC'))
            cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
            return
        if address in self.e.plt:
            name = self.e.plt[address]
            if name == LINEARIZE:
                self.linearization_arguments.append(self.return_doubles(1)[0])
            elif name == FACTORY:
                # This is a caller-argument trace, not a new factory execution.
                self.factory_calls.append(([cpu.reg_read(UC_ARM64_REG_X0+i) for i in range(7)],
                                           self.return_doubles(3)))
                cpu.reg_write(UC_ARM64_REG_X0,RAW)
                cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))
                return
        super().hook(cpu, address, size, user)

    def return_doubles(self, count):
        return np.array([struct.unpack('<d', struct.pack('<Q', self.u.reg_read(UC_ARM64_REG_D0 + i)))[0]
                         for i in range(count)])

    def gain_to_temp(self, gains, quantize=False):
        self.u.mem_write(TEMP_OUT, b'\xcc' * 4)
        self.u.mem_write(TINT_OUT, b'\xcc' * 8)
        self.call(GAIN_TO_TEMP, (22, 6, TEMP_OUT, TINT_OUT, int(quantize)), gains)
        return (struct.unpack('<i', bytes(self.u.mem_read(TEMP_OUT, 4)))[0],
                self.doubles(TINT_OUT, 1)[0])

    def temp_to_gain(self, temperature, tint):
        self.call(TEMP_TO_GAIN, (22, 6, temperature), (tint,))
        return self.return_doubles(3)

    def check_guards(self):
        super().check_guards()
        if hasattr(self, 'ccnc'):
            assert bytes(self.u.mem_read(CONV - 16, 16)) == bytes(self.u.mem_read(CONV + 0x98, 16)) == b'\xa5' * 16
            for ptr,length in ((DESCRIPTION,0x350),(CORRECTION,0x430)):
                assert bytes(self.u.mem_read(ptr-16,16)) == bytes(self.u.mem_read(ptr+length,16)) == b'\xa5'*16


def temperature_table(elf):
    table = np.frombuffer(elf.read(0x3149960, 31 * 32), dtype='<f8').reshape(31, 4)
    assert np.all(np.diff(table[:, 0]) > 0)
    return table


def gain_to_temp_oracle(gains, matrix, table):
    xyz = matrix @ (np.min(gains) / np.asarray(gains))
    x, y = (xyz / xyz.sum())[:2]
    uv = np.array([2*x, 3*y]) / (1.5-x+6*y)
    normals = np.column_stack([np.ones(31), table[:, 3]])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    distances = (uv[1]-table[:, 2])*normals[:, 0] - (uv[0]-table[:, 1])*normals[:, 1]
    stops = np.flatnonzero(distances[2:] <= 0)
    i = int(stops[0] + 2) if len(stops) else 30
    selected = 1 if distances[1] <= 0 else i
    indices = {selected}
    # At an isotherm, tiny floating-point changes can select either adjacent
    # segment. The reversed normal weights make tint discontinuous there.
    # Preserve both mathematically admissible results only within this bound.
    near = np.flatnonzero(np.abs(distances[1:]) < 2e-14) + 1
    for index in near:
        indices.add(max(1, int(index)))
        if index < 30:
            indices.add(int(index)+1)
    candidates = []
    for i in sorted(indices):
        if i == 1:
            candidates.append((50000, float((uv-table[0, 1:3]) @ normals[1])))
            continue
        current = min(distances[i], 0.)
        blend = -current / (distances[i-1] - current)
        inverse_kelvin = table[i-1, 0]*blend + table[i, 0]*(1-blend)
        locus = table[i-1, 1:3]*blend + table[i, 1:3]*(1-blend)
        # Original direction-vector weights are reversed relative to the
        # locus-point weights. This differs from conventional interpolation.
        normal = normals[i-1]*(1-blend) + normals[i]*blend
        normal /= np.linalg.norm(normal)
        candidates.append((int(1e6/inverse_kelvin + .5), float((uv-locus) @ normal)))
    return candidates, bool(len(near))


def check_temperature(actual, oracle):
    candidates, boundary = oracle
    compatible = [abs(actual[1]-tint) for temp,tint in candidates if temp == actual[0]]
    assert compatible and min(compatible) < 1e-12, (actual, candidates)
    return float(min(compatible)), boundary


def temp_to_gain_oracle(temperature, tint, matrix_inverse, table, elf):
    mired = 1e6 / temperature if temperature > 0 else 1e5
    i = int(np.clip(np.searchsorted(table[:, 0], mired, side='right')-1, 0, 29))
    low, high = table[i], table[i+1]
    blend = (high[0]-mired)/(high[0]-low[0])
    normals = np.array([[1., low[3]], [1., high[3]]])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    normal = normals[0]*blend + normals[1]*(1-blend)
    normal /= np.linalg.norm(normal)
    u, v = low[1:3]*blend + high[1:3]*(1-blend) + normal*tint
    xy = np.array([1.5*u, v])/(u-4*v+2)
    rgb = matrix_inverse @ np.r_[xy, 1-xy.sum()]
    epsilon = np.frombuffer(elf.read(0x3070650, 8), dtype='<f8')[0]
    return rgb.max()/np.maximum(rgb, epsilon)


def vector(runner, offset, values, reserve_only=False):
    ptr = runner.alloc(values.nbytes)
    runner.u.mem_write(ptr, values.tobytes())
    runner.u.mem_write(CC + offset, struct.pack('<QQQ', ptr,
        ptr if reserve_only else ptr + values.nbytes, ptr + values.nbytes))
    return ptr


def captured_gain_inputs(paths):
    result = []
    for path in paths:
        before = sha(path.read_bytes())
        with tifffile.TiffFile(path) as image:
            page = image.pages[0]
            assert page.tags['Model'].value == 'X2D II 100C'
            raw = np.asarray(page.tags['AsShotNeutral'].value, dtype=float).reshape(3, 2)
            neutral = raw[:, 0]/raw[:, 1]
            assert np.isfinite(neutral).all() and np.all(neutral > 0)
            result.append(1/neutral)
        assert sha(path.read_bytes()) == before
    return result


def android_static_edges(elf):
    edges = [
        (0x34bb618, '_ZN22CColorCorrectAllFilter16UpdateParametersEv'),
        (0x34c0dbc, CREATE),
        (0x34c0e8c, '_ZNK20CColorTempConversion17TempAndTintToGainEid'),
        (0x3279f94, FACTORY),
        (0x3279fb4, LINEARIZE),
    ]
    result=[]
    for site,callee in edges:
        word=struct.unpack('<I',elf.read(site,4))[0]
        assert word>>26==0b100101
        immediate=word & 0x3ffffff
        if immediate & 0x2000000:immediate-=0x4000000
        target=site+immediate*4
        assert elf.plt[target]==callee
        result.append({'call_site':hex(site),'callee':callee,'direct_call_verified':True})
    return result


def android_caller_cases(runner, profile, table):
    """Original source-gain, scalar preparation and creation-argument routing."""
    runner.ccnc=False
    u=runner.u
    def put(ptr,offset,fmt,*values):u.mem_write(ptr+offset,struct.pack(fmt,*values))
    put(DESCRIPTION,0x344,'<ii',22,6)
    put(DESCRIPTION,0xb0,'<i',1)
    put(DESCRIPTION,0x18,'<d',1.25)
    put(DESCRIPTION,0x28,'<3d',2.1,1.,1.5)
    put(DESCRIPTION,0x40,'<d',.8)
    put(DESCRIPTION,0x50,'<d',1.1)
    put(CORRECTION,0x29c,'<i',5550)
    put(CORRECTION,0x2a0,'<d',.003)
    put(CORRECTION,0xe0,'<i',4000)
    put(CORRECTION,0xd8,'<d',-.002)
    put(CORRECTION,0x2a8,'<d',1.7)
    put(CORRECTION,0x428,'<i',2)
    put(RAW,0xb0,'<Q',CC)
    matrix=(np.array(profile['mf'])*.5+1).reshape(3,3) @ np.diag(np.array(profile['vf'])*.5+1)
    inverse=np.linalg.inv(matrix)
    sources=[]
    for source in ('current','alternate','capture_fallback'):
        put(CORRECTION,0xd4,'<B',source!='current')
        put(CORRECTION,0xe0,'<i',0 if source=='capture_fallback' else 4000)
        expected=(np.array([2.1,1.,1.5]) if source=='capture_fallback' else
            temp_to_gain_oracle(5550 if source=='current' else 4000,
                .003 if source=='current' else -.002,inverse,table,runner.e))
        runner.call(SOURCE_GAIN,(0,DESCRIPTION,CORRECTION))
        gain_result=check(runner.return_doubles(3),expected,1e-10)
        for gain_enabled in (False,True):
            put(CORRECTION,0x93,'<B',gain_enabled)
            runner.call(EXPOSURE,(0,CORRECTION,DESCRIPTION))
            expected_scalar=expected.max()*1.25*.8*1.1*(1.7 if gain_enabled else 1.)
            scalar_result=check(runner.return_doubles(2),np.array([1.,expected_scalar]),1e-10)
            sources.append({'source_fixture':source,'scalar_gain_enabled':gain_enabled,
                            'gain_result':gain_result,'scalar_result':scalar_result})
    put(CORRECTION,0xd4,'<B',0)
    creation=[]
    for enabled,model,space in ((False,1,4),(True,0,0),(True,0,4),(True,1,4)):
        put(CORRECTION,0x91,'<B',enabled)
        put(CORRECTION,0x2c8,'<i',model)
        put(CORRECTION,0x2cc,'<i',0)
        put(CORRECTION,0xe4,'<i',space)
        for gain_enabled in (False,True):
            put(CORRECTION,0x93,'<B',gain_enabled)
            before=[(DESCRIPTION,bytes(u.mem_read(DESCRIPTION,0x350))),
                    (CORRECTION,bytes(u.mem_read(CORRECTION,0x430)))]
            runner.call(CREATE,(0,DESCRIPTION,CORRECTION))
            ints,floats=runner.factory_calls[-1]
            film=7 if enabled and model==1 else (0 if enabled else 1)
            assert ints==[22,6,film,model if enabled else 0,0,space if enabled else 0,0]
            assert np.array_equal(floats,[5550.,1.,1.])
            assert runner.linearization_arguments[-1]==(1.7 if gain_enabled else 1.)
            assert struct.unpack('<Q',bytes(u.mem_read(0x10002000,8)))[0]==RAW
            assert all(bytes(u.mem_read(ptr,len(value)))==value for ptr,value in before)
            creation.append({'settings_enabled_fixture':enabled,'requested_model_code':model,
                'requested_space_code':space,'linearization_gain_enabled':gain_enabled,
                'selected_film_code':film,'factory_arguments_exact':True,
                'linearization_argument_exact':True,'input_unchanged':True})
    return {'source_gain_and_scalar_cases':sources,'creation_argument_cases':creation,
            'factory_is_recording_fixture':True,'HDR_flag_in_all_creation_cases':False}


def audit(elf, profile, capture_gains):
    runner = InputRunner(elf)
    runner.profile = profile
    runner.call(DECODE, (runner.obj, runner.coder))
    runner.u.mem_write(runner.obj + 9, b'\1')
    frozen_profile = [(runner.obj, bytes(runner.u.mem_read(runner.obj, 0x318)))]
    frozen_profile += [(p + 16, bytes(runner.u.mem_read(p + 16, n))) for p, n in runner.allocations]
    table = temperature_table(elf)
    ctor_cases, forward_cases, inverse_cases, capture_cases = [], [], [], []
    fixed_gains = [[1., 1., 1.], [1.8, 1., .7], [.7, 1., 2.], [4., 1., 1.2]]
    for ccnc in (False, True):
        runner.ccnc = ccnc
        runner.call(CONVERTER, (CONV, 22, 6))
        matrix = (np.array(profile['mf'])*.5+1).reshape(3, 3) @ np.diag(np.array(profile['vf'])*.5+1) if not ccnc else np.eye(3)
        inverse = np.linalg.inv(matrix)
        ctor_cases.append({'CCNC_fixture': ccnc,
            'forward_matrix': check(runner.doubles(CONV+8, 9).reshape(3,3), matrix),
            'inverse_matrix': check(runner.doubles(CONV+0x50, 9).reshape(3,3), inverse)})
        gains_list = list(fixed_gains)
        for temperature in (2000, 2400, 3050, 4000, 5550, 8000, 9100, 10000, 20000, 50000):
            for tint in (-.01, 0., .01):
                actual = runner.temp_to_gain(temperature, tint)
                expected = temp_to_gain_oracle(temperature, tint, inverse, table, elf)
                inverse_cases.append({'CCNC_fixture': ccnc, 'temperature': temperature, 'tint_fixture': tint,
                                      **check(actual, expected, 1e-10)})
                gains_list.append(expected)
        for gains in gains_list:
            expected = gain_to_temp_oracle(gains, matrix, table)
            actual = runner.gain_to_temp(gains)
            error, boundary = check_temperature(actual, expected)
            scaled = runner.gain_to_temp(np.asarray(gains)*3.7)
            scaled_error, scaled_boundary = check_temperature(scaled,
                gain_to_temp_oracle(np.asarray(gains)*3.7, matrix, table))
            assert scaled[0] == actual[0]
            if not boundary and not scaled_boundary:
                assert abs(scaled[1]-actual[1]) < 1e-12
            forward_cases.append({'CCNC_fixture': ccnc, 'temperature_exact': True,
                'tint_abs_difference': error, 'scaled_tint_abs_difference': scaled_error,
                'near_isotherm_boundary': boundary or scaled_boundary,
                'common_scale_temperature_invariant': True,
                'common_scale_tint_difference': float(abs(scaled[1]-actual[1]))})
        for gains in capture_gains:
            actual = runner.gain_to_temp(gains)
            expected = gain_to_temp_oracle(gains, matrix, table)
            error, boundary = check_temperature(actual, expected)
            capture_cases.append({'CCNC_fixture': ccnc, 'temperature_exact': True,
                'tint_abs_difference': error, 'near_isotherm_boundary': boundary})
        print(f'White-balance conversion verified with CCNC={ccnc}', flush=True)
    callers=android_caller_cases(runner,profile,table)
    print('Android source-gain/scalar helpers and SDR creation argument routing verified',flush=True)
    runner.ccnc = False
    runner.u.mem_write(RAW + 0xb0, struct.pack('<Q', CC))
    # Original no-table path returns without modifying the correction object.
    before = bytes(runner.u.mem_read(CC, 0x298))
    runner.call(LINEARIZE, (RAW,), (1.7,))
    assert bytes(runner.u.mem_read(CC, 0x298)) == before
    x = np.arange(65536, dtype=np.uint64)
    # These deliberately distinct tables are owned fixtures, not calibration.
    source_tables = [x.astype('<u2'), ((x*x)//65535).astype('<u2'),
                     np.minimum(65535, x+x//7).astype('<u2')]
    source_ptrs = [vector(runner, offset, values) for offset, values in zip((0x1e0,0x1f8,0x210),source_tables)]
    output_ptrs = [vector(runner, offset, np.zeros(65536,dtype='<u2'), True) for offset in (0x240,0x258,0x270)]
    linear_cases, apply_cases = [], []
    rng = np.random.default_rng(410026)
    samples = np.vstack([np.repeat(np.array([0,1,2,7,255,1023,32767,65534,65535])[:,None],3,axis=1),
                         rng.integers(0,65536,(503,3))]).astype('<u2')
    input_ptr = 0x10080020
    for gain in (.5, 1., 1.7, 4.):
        runner.call(LINEARIZE, (RAW,), (gain,))
        index = np.minimum(x/gain,65535).astype(np.int64)
        expected = np.stack([np.minimum(values[index]*gain,65535).astype('<u2') for values in source_tables])
        actual = np.stack([np.frombuffer(bytes(runner.u.mem_read(ptr,131072)),dtype='<u2') for ptr in output_ptrs])
        linear_cases.append({'gain_fixture':gain, **check(actual,expected,0)})
        # Apply requires a non-null closed-loop calibration pointer. This fixture
        # exercises that documented gate; no calibration object is dereferenced.
        for enabled in (False, True):
            runner.u.mem_write(RAW+0x28,struct.pack('<Q',0x10060000 if enabled else 0))
            runner.u.mem_write(input_ptr-32,b'\xa5'*32+samples.tobytes()+b'\xa5'*32)
            runner.call(APPLY,(RAW,input_ptr,len(samples),0))
            got=np.frombuffer(bytes(runner.u.mem_read(input_ptr,samples.nbytes)),dtype='<u2').reshape(-1,3)
            want=np.column_stack([expected[i,samples[:,i]] for i in range(3)]) if enabled else samples
            apply_cases.append({'gain_fixture':gain,'closed_loop_pointer_fixture':enabled,**check(got,want,0)})
            assert bytes(runner.u.mem_read(input_ptr-32,32)) == bytes(runner.u.mem_read(input_ptr+samples.nbytes,32)) == b'\xa5'*32
        assert all(bytes(runner.u.mem_read(p,v.nbytes))==v.tobytes() for p,v in zip(source_ptrs,source_tables))
        print(f'All three full linearization tables and pixel application verified at gain={gain}',flush=True)
    assert all(bytes(runner.u.mem_read(p,len(v)))==v for p,v in frozen_profile)
    runner.check_guards()
    return {'converter_constructor_cases':ctor_cases,'temperature_to_gain_cases':inverse_cases,
        'gain_to_temperature_cases':forward_cases,'capture_metadata_cases':capture_cases,
        'linearization_cases':linear_cases,'linearization_apply_cases':apply_cases,
        'android_caller_contract':callers,
        'android_static_call_edges':android_static_edges(elf),
        'empty_linearization_no_op_verified':True,'source_tables_and_profile_unchanged':True,
        'guards_pass':True,'configuration_queries':sorted(set(runner.config_queries)),
        'profile_cache_fixture_calls':len(runner.cache_calls),'host_math_calls':dict(runner.math_calls),
        'original_functions':[{'name':n,'address':hex(elf.func[n][0]),'bytes':elf.func[n][1],
            'sha256':sha(elf.read(*elf.func[n]))} for n in sorted(runner.called)]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apk',type=Path,required=True)
    parser.add_argument('--raw',type=Path,action='append',default=[])
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    assert __debug__
    original=args.apk.read_bytes();assert sha(original)==APK_SHA
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        lib=archive.read('lib/arm64-v8a/libcrosssdk.so')
        data=archive.read('assets/Colormaps/'+TARGET)
    assert sha(lib)==LIB_SHA
    elf=Elf(lib)
    blocks=np.frombuffer(data,dtype=np.uint8).reshape(-1,16)
    plain=(decrypt_blocks(elf,blocks[1:])^blocks[:-1]).tobytes()
    padding=plain[-1];assert 1<=padding<=16 and plain[-padding:]==bytes([padding])*padding
    plain=plain[:-padding]
    assert sha(plain)=='c2b3d08e0d489eb852610c12a9b985e9d0340a4dd544f5b0b5b7a6a4f3427e95'
    result={'schema':'hasselblad-stage41z-input-preparation-v1','apk_sha256':APK_SHA,'library_sha256':LIB_SHA,
        'audit':audit(elf,plistlib.loads(plain),captured_gain_inputs(args.raw)),
        'raw_metadata_files_read':len(args.raw),
        'bounds':{'CCNC_live_setting_observed':False,'capture_AsShotNeutral_to_Phocus_filter_binding_verified':False,
            'manufacturer_closed_loop_calibration_used':False,'per_pixel_gain_map_branch_executed':False,
            'raw_object_factory_executed':False,'Android_UpdateParameters_or_GPU_executed':False,
            'quantized_temperature_tint_branch_executed':False,
            'full_raw_decode_or_render_executed':False,'production_renderer_changed':False,
            'vendor_arrays_code_crypto_or_capture_metadata_exported':False},
        'fixtures':{'configuration':'CCNC tested both ways, other queried booleans false',
            'cache':'already loaded CPID 0x0616 after original selector',
            'raw_object_factory':'records arguments and returns harness object; no constructor execution',
            'white_balance_boundary':'adjacent segment candidates allowed only within 2e-14 of an isotherm',
            'linearization':'three distinct synthetic UINT16 tables with guarded reserved output capacity',
            'capture_input':'reciprocal TIFF AsShotNeutral, not verified as the app filter argument',
            'apply':'non-null calibration pointer only tests gate; calibration content not dereferenced'},
        'runtime':{p:version(p) for p in ('numpy','unicorn','capstone','pyelftools','tifffile')}}
    assert sha(args.apk.read_bytes())==APK_SHA
    args.receipt.write_text(json.dumps(result,indent=2)+'\n')
    a=result['audit']
    print(json.dumps({'original_functions':len(a['original_functions']),
        'white_balance_cases':len(a['temperature_to_gain_cases'])+len(a['gain_to_temperature_cases']),
        'capture_metadata_cases':len(a['capture_metadata_cases']),
        'linearization_entries':sum(v['values'] for v in a['linearization_cases']),
        'linearization_exact_entries':sum(v['exact_values'] for v in a['linearization_cases']),
        'application_channels':sum(v['values'] for v in a['linearization_apply_cases'])}))


if __name__=='__main__':main()
