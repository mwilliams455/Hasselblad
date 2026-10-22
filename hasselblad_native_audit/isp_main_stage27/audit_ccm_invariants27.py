#!/usr/bin/env python3
"""Stage27 exact X2D II MAIN CCM anchor/group/bank invariants, NOT pixel math.

Loads transient, hash-pinned original IQ values; never publishes those values.
Verifies Stage17 componentwise Q8 profile preparation against Python and
constrains what Stage25's unknown 16-group selector can change. No HNCS claim.
"""
from __future__ import annotations
import argparse, ctypes as ct, hashlib, importlib.util, json, struct
from pathlib import Path
import subprocess, sys, tempfile

CONFIG_SHA='2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
PARSER_SHA='0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec'
TABLE_SHA='59d1b6c8a291280a8749f5ca190370e5dbff8ce0e6694a7da779ae5488ae641e'
AXIS=(2400,3050,5550,9100)
GROUPS=16
COEFFS=6
PROFILE=96
SOURCE=768

def require(condition,reason):
    if not condition: raise ValueError(reason)

def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def flags(data):
    require(len(data)==SOURCE,'wrong_source_length')
    require(all(isinstance(v,int) and -32768<=v<=32767 for v in data),'wrong_signed16_range')
    equal_groups=all(
        data[p*PROFILE+g*COEFFS:p*PROFILE+(g+1)*COEFFS]
        ==data[p*PROFILE:p*PROFILE+COEFFS]
        for p in range(8) for g in range(1,GROUPS))
    equal_banks=all(
        data[p*PROFILE:(p+1)*PROFILE]
        ==data[(p+4)*PROFILE:(p+5)*PROFILE]
        for p in range(4))
    return equal_groups,equal_banks

def lerp(a,b,weight):
    return a + ((b-a)*weight//256)

def prepare_python(data,cct,weight):
    require(0<=weight<=256,'invalid_weight')
    if cct<AXIS[0]: i,f=0,0
    elif cct>=AXIS[3]: i,f=2,256
    else:
        i=next(k for k in range(3) if cct<AXIS[k+1])
        f=(cct-AXIS[i])*256//(AXIS[i+1]-AXIS[i])
    out=[]
    for k in range(PROFILE):
        low=lerp(data[i*PROFILE+k],data[(i+1)*PROFILE+k],f)
        high=lerp(data[(i+4)*PROFILE+k],data[(i+5)*PROFILE+k],f)
        out.append(lerp(low,high,weight))
    return out

def cct_samples():
    values={-200000,0,2399,*AXIS,9101,200000,2401,3049,3051,5549,5551,9099}
    values.update(2200+67*i for i in range(129))
    return sorted(values)

def test_owned_portable_c(data,root,compiler):
    cfile=root/'hasselblad_native_audit/main_colour_20261019/ccm/ccm_prepare.c'
    require(cfile.is_file(),'missing_stage17_ccm_source')
    samples=cct_samples()
    rates=(0,1,17,85,128,239,255,256)
    with tempfile.TemporaryDirectory(prefix='hb27_') as td:
        so=Path(td)/'libhb27_ccm.so'
        subprocess.run([compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror',
                        '-fPIC','-shared',str(cfile),'-o',str(so)],
                       stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
        lib=ct.CDLL(str(so))
        func=lib.hb_ccm_prepare
        I=ct.c_int32
        func.argtypes=[ct.POINTER(I),ct.c_size_t,I,I,ct.POINTER(I),ct.c_size_t]
        func.restype=ct.c_int
        source=(I*SOURCE)(*data)
        target=(I*PROFILE)()
        count=0
        for cct in samples:
            for rate in rates:
                require(func(source,SOURCE,cct,rate,target,PROFILE)==0,'stage17_C_rejected_valid')
                require(list(target)==prepare_python(data,cct,rate),
                        'stage17_C_vs_independent_Python_mismatch')
                count+=PROFILE
    return len(samples),len(rates),count

def assert_symmetry_survives(data):
    for cct in cct_samples():
        base=prepare_python(data,cct,0)
        for rate in (0,1,17,85,128,239,255,256):
            prepared=prepare_python(data,cct,rate)
            require(prepared==base,'bank_invariance_broken')
            require(all(prepared[g*COEFFS:(g+1)*COEFFS]==prepared[:COEFFS]
                        for g in range(GROUPS)),'group_invariance_broken')

def synthetic(root,compiler):
    source=[]
    for bank in range(2):
        for cct in range(4):
            six=[-1136+213*cct,1423-153*cct,386+32*cct,
                 -716+233*cct,2446-171*cct,-849+51*cct]
            source.extend(six*GROUPS)
    require(flags(source)==(True,True),'synthetic_symmetric_fixture_rejected')
    altered_group=source.copy()
    for bank in (0,1):
        altered_group[(bank*4+1)*PROFILE+2*COEFFS+2]+=1
    require(flags(altered_group)==(False,True),'group_counterexample_not_rejected')
    altered_bank=source.copy()
    for group in range(GROUPS):
        altered_bank[4*PROFILE+group*COEFFS+3]+=1
    require(flags(altered_bank)==(True,False),'bank_counterexample_not_rejected')
    assert_symmetry_survives(source)
    c,w,n=test_owned_portable_c(source,root,compiler)
    return {'schema':'stage27-main-ccm-synthetic-v1',
            'status':'PASS_synthetic_controls','synthetic_fixture':True,
            'adversarial_group_counterexample_detected':True,
            'adversarial_bank_counterexample_detected':True,
            'sampled_CCTs':c,'sampled_Q8_weights':w,
            'C_vs_independent_Python_scalars_compared':n,
            'pixel_equation_proven':False,'camera_renderer_modified':False}

def exact_values(root,firmware):
    config=firmware/'system/etc/iq/hb722_config.json'
    parser=root/'hasselblad_native_audit/photographic_path/inspect_iq_config.py'
    require(sha(config)==CONFIG_SHA,'unexpected_X2DII_config_hash')
    require(sha(parser)==PARSER_SHA,'unexpected_iq_parser_hash')
    spec=importlib.util.spec_from_file_location('stage27_iq_parser',parser)
    require(spec is not None and spec.loader is not None,'parser_import_error')
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    sys.dont_write_bytecode=True
    spec.loader.exec_module(mod)
    doc=mod.read_config(config)
    declared=doc['iq_table']['module']['main_ccm']['lmtx_fw']
    require(declared=={'type':'lerp_1d_lut_reg_idx_v5','group':'global_frame',
                       'axis':['cc_color_temp','color_hiso'],'total':16},
            'wrong_original_CCM_parameter_contract')
    require(doc['iq_table']['data'][0]['mode_axis']['cc_color_temp']==list(AXIS),
            'wrong_CCT_knots')
    data=doc['iq_table']['data'][0]['main_ccm'][0]['lmtx_fw']
    require(len(data)==SOURCE,'wrong_source_values')
    require(hashlib.sha256(struct.pack('<768i',*data)).hexdigest()==TABLE_SHA,
            'wrong_exact_main_CCM_table_hash')
    return data

def exact(root,firmware,compiler):
    values=exact_values(root,firmware)
    equal_groups,equal_banks=flags(values)
    require(equal_groups and equal_banks,'original_table_not_symmetric')
    assert_symmetry_survives(values)
    c,w,n=test_owned_portable_c(values,root,compiler)
    # Because Stage17's original-verified interpolation acts identically
    # componentwise, matching source groups/banks imply invariant prepared
    # groups/banks for any allowed CCT and Q8 bank weight, not just these samples.
    return {'schema':'stage27-X2DII-1_3_16_2-main-CCM-static-invariants-v1',
            'status':'PASS_exact_table_invariants','original_table_hash_matched':True,
            'original_source_profiles':8,'region_groups':16,
            'coefficients_per_group':6,'all_source_groups_equal':equal_groups,
            'all_source_high_ISO_banks_equal':equal_banks,
            'prepared_groups_equal_for_all_CCTs':True,
            'prepared_coefficients_independent_of_bank_weight_for_all_CCTs':True,
            'scope':'hash-pinned global still main_ccm.lmtx_fw static table',
            'scope_does_not_exclude_dynamic_runtime_overrides':True,
            'sampled_CCTs':c,'sampled_Q8_weights':w,
            'C_vs_independent_Python_scalars_compared':n,
            'six_coefficient_pixel_equation_proven':False,
            'pixel_coefficient_scale_proven':False,
            'region_selector_recovered':False,
            'photographic_render_authorized':False,
            'vendor_tuning_values_exported':False,
            'phone_renderer_modified':False,
            'next_hard_gate':'Eagle2_MAIN_pixel_operation_or_controlled_hardware_oracle'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--repo-root',type=Path,default=Path.cwd())
    ap.add_argument('--firmware-root',type=Path)
    ap.add_argument('--compiler',default='cc')
    ap.add_argument('--output',type=Path)
    a=ap.parse_args()
    root=a.repo_root.resolve()
    report=synthetic(root,a.compiler) if a.self_test else exact(
        root, a.firmware_root.resolve() if a.firmware_root else
        (_ for _ in ()).throw(ValueError('exact_firmware_root_required')),a.compiler)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'
')
    print(json.dumps(report,sort_keys=True))

if __name__=='__main__': main()
