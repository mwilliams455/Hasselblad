#!/usr/bin/env python3
"""Compare compiled portable C to the original function's ARM64 execution.

The original exact-hash ELF is an external input, never bundled in this project.
"""
from __future__ import annotations
import argparse
import ctypes as c
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path


class Pair(c.Structure):
    _fields_ = [('a',c.c_uint32),('b',c.c_uint32)]


class Result(c.Structure):
    _fields_ = [('adapter_status',c.c_int32),('original_status',c.c_uint32),('original_called',c.c_uint32),('output',Pair)]


Original = c.CFUNCTYPE(c.c_uint32,c.POINTER(c.c_uint32),c.POINTER(c.c_uint32),c.c_uint32,c.c_uint32)


def as_json(r):
    return {'adapter_status':r.adapter_status,'original_called':bool(r.original_called),'original_status':r.original_status if r.original_called else None,'output':[r.output.a,r.output.b]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_library',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--compiler',default='cc')
    a=p.parse_args()
    here=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('oracle',here.parent/'prove_awb_recalib_unit.py')
    oracle=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    code,_=oracle.audited_code(a.original_library)
    cases=[case for case in oracle.CASES if case[3] and case[4]]+[
        ('one_lsb',1,2,4096,4096),
        ('asymmetric_fraction',12345,23456,7000,3333),
        ('last_no_overflow_inputs',1048575,1048574,4096,4095),
        ('large_calibration',65535,4096,4294967295,16777216),
    ]
    comparisons=[]
    with tempfile.TemporaryDirectory(prefix='hb-awb-portable-') as tmp:
        shared=Path(tmp)/'libhb_awb_recalib.so'
        command=[a.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-pedantic','-fPIC','-shared',str(here/'hb_awb_recalib.c'),'-o',str(shared)]
        subprocess.run(command,check=True,capture_output=True,text=True)
        lib=c.CDLL(str(shared))
        lib.hb_awb_recalib_portable.argtypes=[Pair,Pair]
        lib.hb_awb_recalib_portable.restype=Result
        lib.hb_awb_recalib_original.argtypes=[Original,Pair,Pair]
        lib.hb_awb_recalib_original.restype=Result
        invocation_count=0
        @Original
        def bridge(pa,pb,ca,cb):
            nonlocal invocation_count
            invocation_count+=1
            result=oracle.execute_case(code,('callback_oracle',pa[0],pb[0],ca,cb))
            pa[0],pb[0]=result['output']
            return result['status']
        for case in cases:
            name,ga,gb,ca,cb=case
            machine=oracle.execute_case(code,case)
            portable=lib.hb_awb_recalib_portable(Pair(ga,gb),Pair(ca,cb))
            delegated=lib.hb_awb_recalib_original(bridge,Pair(ga,gb),Pair(ca,cb))
            assert portable.adapter_status==0 and not portable.original_called
            assert delegated.adapter_status==0 and delegated.original_called and delegated.original_status==0
            assert [portable.output.a,portable.output.b]==machine['output']
            assert [delegated.output.a,delegated.output.b]==machine['output']
            comparisons.append({'name':name,'input':[ga,gb],'calibration':[ca,cb],'original_machine_output':machine['output'],'portable':as_json(portable),'delegating_adapter':as_json(delegated),'result':'pass'})
        guarded=[]
        count_before=invocation_count
        for name,ga,gb,ca,cb,expected in [
            ('zero_a',4096,4096,0,4096,1),
            ('zero_b',4096,4096,4096,0,1),
            ('overflow_a',1048576,4096,4096,4096,2),
            ('overflow_b',4096,4294967295,4096,4096,2),
        ]:
            portable=lib.hb_awb_recalib_portable(Pair(ga,gb),Pair(ca,cb))
            delegated=lib.hb_awb_recalib_original(bridge,Pair(ga,gb),Pair(ca,cb))
            for result in (portable,delegated):
                assert result.adapter_status==expected and not result.original_called
                assert [result.output.a,result.output.b]==[ga,gb]
            guarded.append({'name':name,'result':'pass','portable':as_json(portable),'delegating_adapter':as_json(delegated)})
        assert invocation_count==count_before,'Invalid input reached original callback'
        missing=lib.hb_awb_recalib_original(Original(),Pair(4096,4096),Pair(4096,4096))
        assert missing.adapter_status==3 and not missing.original_called
        # Adapter error propagation uses a synthetic callback, clearly separate
        # from the original-function comparison. It simulates a nonzero status.
        @Original
        def rejected(pa,pb,ca,cb):
            pa[0],pb[0]=123,456
            return 89
        failure=lib.hb_awb_recalib_original(rejected,Pair(4096,8192),Pair(4096,4096))
        assert failure.adapter_status==4 and failure.original_called and failure.original_status==89
        assert [failure.output.a,failure.output.b]==[4096,8192]
        report={
            'library_sha256':oracle.LIB_SHA256,'firmware': 'X2D II 1.3.16.2','symbol':oracle.SYMBOL,
            'method':'Compiled portable C and guarded adapter compared against execution of exact original ARM64 instructions in Unicorn. Callback bridge transports inputs/outputs only; it does not replace original arithmetic.',
            'portable_source_sha256':hashlib.sha256((here/'hb_awb_recalib.c').read_bytes()).hexdigest(),
            'compiler':a.compiler,'compiler_flags':command[1:8],
            'differential_cases':comparisons,'guard_cases':guarded,
            'missing_original':as_json(missing),
            'synthetic_error_propagation':{'scope':'Adapter only; synthetic return89, not claimed as original execution','result':as_json(failure)},
            'differential_case_count':len(comparisons),'guard_case_count':len(guarded),'all_passed':True,
            'limits':'Only the audited Q12 calibration primitive. No input calibration inferred, no captured image transformed, no full AWB or HNCS implementation.'
        }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'differential_cases_passed':len(comparisons),'guard_cases_passed':len(guarded),'adapter_failure_propagation':'pass','all_passed':True,'output':str(a.output)}))


if __name__=='__main__':
    main()
