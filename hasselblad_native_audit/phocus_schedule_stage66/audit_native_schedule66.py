#!/usr/bin/env python3
"""Prepared original-CPU scheduler call-boundary audit (not yet executed).

Requires the original local private Phocus APK and the original Stage60-63
Unicorn/Capstone/ELF audit harness. Public receipts omit binary addresses,
private photograph content, calibration and input-file hashes.
"""
import argparse
from collections import Counter
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_green_stage63'))
from audit_integration63 import (GreenRunner, PortableMaps, PortableInterpolation,
                                 PortableGreen, load_private, synthetic_patterns,
                                 pad_bayer)
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X30
from test_schedule66 import Domain,Counts,build,COUNT_NAMES

RGB='_ZN20CGradientInterpolate14InterpolateRGBEPKtii'
SYMBOLS={
    'smooth_rows':'_ZN13FilterGeneric20Smooth3x3_Special121EPKtPtii',
    'edge_rows':'_ZN13FilterGeneric23Edge3x3_SpecialSobel121EPKtPsii',
    'scale_calls':'_ZN20CGradientInterpolate17CalculateScaleMapEPKtPfS2_iiiii',
    'midgreen_calls':'_ZN20CGradientInterpolate20CalculateMidGreenMapEPKtPKfS3_PfPtiiiii',
    'green_colour_estimates':'_ZN20CGradientInterpolate18GetGreenAtRedFirstEPKtPKfS3_S3_S1_iRiS4_PsS5_Rs',
    'blue_helper':'_ZN20CGradientInterpolate12GetBlueAtRedEPKtS1_ii',
    'green_site_masks':'_ZN20CGradientInterpolate15GetGradientMaskEPKsS1_',
    'rb_helper':'_ZN20CGradientInterpolate17GetRedBlueAtGreenEPKtS1_S1_RtS2_ii',
}

class ScheduleRunner66(GreenRunner):
    def __init__(self,elf,profile,maps,interpolation,green,lib):
        self.rgb_entry=elf.func[RGB][0]
        self.schedule_lib=lib
        self.current=None
        self.invocations=[]
        super().__init__(elf,profile,maps,interpolation,green)

    def hook(self,cpu,address,size,user):
        if self.gradient_active:
            if self.current is not None and address==self.current['return_pc']:
                item=self.current;self.current=None
                expected=item['expected']
                observed=item['observed']
                if expected is not None:
                    for key in ('smooth_rows','edge_rows','scale_calls','midgreen_calls',
                                'green_colour_estimates','green_site_masks'):
                        if observed[key]!=expected[key]:
                            raise AssertionError(('Stage66 native boundary mismatch',
                                key, observed[key],expected[key]))
                    if observed['blue_helper']>(expected['blue_at_red_candidates']+
                                                 expected['red_at_blue_candidates']):
                        raise AssertionError('Stage66 native blue calls exceed candidate sites')
                    if observed['rb_helper']>expected['red_blue_green_candidates']:
                        raise AssertionError('Stage66 native RB calls exceed green candidate sites')
                    item['supported_exact_required_boundaries']=True
                else:
                    item['supported_exact_required_boundaries']=False
                self.invocations.append(item)
            if address==self.rgb_entry:
                if self.current is not None:
                    raise AssertionError('Unexpected nested InterpolateRGB')
                reg=lambda i:cpu.reg_read(UC_ARM64_REG_X0+i)
                obj=reg(0)
                flags=self.get(obj,0x38,'<H')[0]
                stride=self.get(obj,0x3c,'<i')[0]
                width,height=[reg(i)&0xffffffff for i in (2,3)]
                if width>0x7fffffff or height>0x7fffffff:
                    raise AssertionError('Invalid signed native dimensions')
                n=Counts();d=Domain(width,height,stride,flags)
                status=self.schedule_lib.hb_schedule66(d,None,None,C.byref(n))
                expected=({key:int(getattr(n,key)) for key in COUNT_NAMES}
                          if status==0 else None)
                self.current={'mode':'substituted' if self.replace else 'original',
                              'width':width,'height':height,
                              'model_supported':status==0,
                              'expected':expected,
                              'observed':Counter(),
                              'return_pc':cpu.reg_read(UC_ARM64_REG_X30)}
            if self.current is not None:
                name=self.e.plt.get(address,'')
                if name in SYMBOLS.values():
                    label=next(k for k,v in SYMBOLS.items() if v==name)
                    self.current['observed'][label]+=1
        return super().hook(cpu,address,size,user)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    p.add_argument('--sanitize',action='store_true')
    args=p.parse_args()
    assert __debug__
    frozen=hashlib.sha256(args.apk.read_bytes()).digest()
    args.work.mkdir(parents=True,exist_ok=True)
    lib_path=args.work/'libstage66_schedule.so';build(lib_path)
    lib=C.CDLL(str(lib_path))
    lib.hb_schedule66.argtypes=[Domain,C.c_void_p,C.c_void_p,C.POINTER(Counts)]
    lib.hb_schedule66.restype=C.c_int
    r=ScheduleRunner66(*load_private(args.apk),
        PortableMaps(args.work/'maps',sanitize=args.sanitize),
        PortableInterpolation(args.work/'interpolation',sanitize=args.sanitize),
        PortableGreen(args.work/'green',sanitize=args.sanitize),lib)
    r.setup_graph()
    for name,mosaic in synthetic_patterns():
        if name in ('neutral','colour_edge','random_codes'):
            r.compare(pad_bayer(mosaic,32),name+'/native_schedule_probe')
    assert r.invocations and r.current is None
    for ptr,profile in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(profile)))==profile
    r.check_guards()
    assert hashlib.sha256(args.apk.read_bytes()).digest()==frozen
    supported=[x for x in r.invocations if x['model_supported']]
    bounded=[x for x in supported if x['supported_exact_required_boundaries']]
    report={'schema':'hasselblad-stage66-native-call-boundary-v1',
            'status':'PASS_EXACT_SUPPORTED_NATIVE_CALL_BOUNDARIES' if supported else 'NO_SUPPORTED_NATIVE_BOUNDARY',
            'original_interpolate_invocations':sum(x['mode']=='original' for x in r.invocations),
            'substituted_interpolate_invocations':sum(x['mode']=='substituted' for x in r.invocations),
            'supported_original_and_substituted_invocations':len(supported),
            'exact_supported_boundary_cases':len(bounded),
            'unsupported_geometry_or_flags_invocations':len(r.invocations)-len(supported),
            'supported_native_boundary_calls_exact':len(bounded)==len(supported),
            'source_and_memory_guards_pass':True,
            'original_executable_or_pixels_exported':False,
            'helper_pixel_equivalence_is_prior_stage63_scope_only':True,
            'inline_green_site_gradient_arithmetic_ported':False,
            'complete_demosaic_port':False,'device_execution_compared':False}
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'observed':len(r.invocations)}))

if __name__=='__main__':main()
