#!/usr/bin/env python3
"""Observe actual ColorNoise branch contract from the Stage63 graph.

This is an execution fixture requiring locally supplied private Phocus APK,
Stage63 dependencies, and no public export of executable bytes or photographs.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_green_stage63'))
from audit_integration63 import (GreenRunner,PortableMaps,PortableInterpolation,
                                 PortableGreen,load_private,synthetic_patterns,pad_bayer)
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2
COLOR_NOISE='_ZN20CGradientInterpolate10ColorNoiseEii'
DIRECTIONAL_YCC='_Z29DirectionalColorCorrectionYCCiPKtPKsS2_S0_S2_S2_RtRsS4_S4_i'

class NoiseGraphObserver(GreenRunner):
    def __init__(self,*args):
        self.observed=Counter();self.ycc_called=Counter()
        super().__init__(*args)
        self.noise_entry=self.e.func[COLOR_NOISE][0]
        self.ycc_entry=self.e.func[DIRECTIONAL_YCC][0]

    def hook(self,cpu,address,size,user):
        if self.gradient_active:
            if address==self.noise_entry:
                obj=cpu.reg_read(UC_ARM64_REG_X0)
                width=cpu.reg_read(UC_ARM64_REG_X1)&0xffffffff
                height=cpu.reg_read(UC_ARM64_REG_X2)&0xffffffff
                flags=self.get(obj,0x38,'<H')[0]
                optimized=self.get(obj,0x8,'<B')[0]
                strength=self.get(obj,0x28,'<i')[0]
                route=('extended_unported' if (flags&0x40 and not optimized and strength>0)
                       else 'bounded_supported')
                self.observed[(route,flags,optimized, 1 if strength>0 else 0,
                               width,height,self.replace)] += 1
            elif address==self.ycc_entry:
                self.ycc_called['substituted' if self.replace else 'original']+=1
        return super().hook(cpu,address,size,user)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',required=True,type=Path)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--safe-receipt',required=True,type=Path)
    p.add_argument('--sanitize',action='store_true')
    args=p.parse_args();assert __debug__
    original=hashlib.sha256(args.apk.read_bytes()).digest()
    r=NoiseGraphObserver(*load_private(args.apk),
          PortableMaps(args.work/'maps',sanitize=args.sanitize),
          PortableInterpolation(args.work/'interpolation',sanitize=args.sanitize),
          PortableGreen(args.work/'green',sanitize=args.sanitize))
    r.setup_graph()
    for name,bayer in synthetic_patterns():
        if name in ('neutral','colour_edge','random_codes'):
            r.compare(pad_bayer(bayer,32),name+'/stage63_graph_contract')
    assert r.observed
    for ptr,frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr,len(frozen)))==frozen
    r.check_guards()
    assert hashlib.sha256(args.apk.read_bytes()).digest()==original
    rows=[{'route':route,'flags':flags,'optimized_view':bool(optimized),
           'positive_strength':bool(positive),'width':width,'height':height,
           'original_or_substituted':'substituted' if replace else 'original',
           'native_calls':count}
          for (route,flags,optimized,positive,width,height,replace),count in sorted(r.observed.items())]
    receipt={'schema':'hasselblad-stage65-colour-noise-graph-branch-v1',
       'status':'ORIGINAL_GRAPH_BRANCHES_OBSERVED',
       'native_colornoise_configurations':rows,
       'native_directional_ycc_call_counts':dict(r.ycc_called),
       'original_executable_or_source_pixels_exported':False,
       'graph_mode_capture_and_source_apk_unchanged':True,
       'full_independent_demosaic':False}
    args.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    args.safe_receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'configurations':len(rows)}),flush=True)

if __name__=='__main__':main()
