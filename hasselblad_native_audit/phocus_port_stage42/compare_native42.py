#!/usr/bin/env python3
"""Repeat the existing 72 original-code cases with the portable core comparator.
No vendor code, arrays or photographic pixels are exported. No tolerance widening.
"""
import argparse,sys,json
from pathlib import Path
import numpy as np
from core42 import Core
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'phocus_stage41y'))
import inspect_phocus_pipeline41y as y

def main():
    a=argparse.ArgumentParser();a.add_argument('--apk',required=True,type=Path)
    a.add_argument('--receipt',required=True,type=Path);a.add_argument('--build-dir',required=True,type=Path)
    args=a.parse_args();args.build_dir.mkdir(parents=True,exist_ok=True)
    assert __debug__
    core=Core(args.build_dir/'libhb42.so')
    oracle=y.pixel_oracle;counts=[]
    def compare(pixels,first,second,grid,expanded,curve,shadow):
        expected=oracle(pixels,first,second,grid,expanded,curve,shadow)
        p=core.params(first,second,grid,expanded,curve,shadow)
        actual=core.render(pixels,p)
        diff=np.abs(actual.astype(int)-expected.astype(int))
        counts.append({'channels':int(actual.size),'different':int(np.count_nonzero(diff)),
                       'max_difference':int(diff.max())})
        # Original native output is then compared directly to this returned array.
        return actual
    y.pixel_oracle=compare;y.PIXEL_TOLERANCE=0
    original_argv=sys.argv
    try:
        sys.argv=['stage41y','--apk',str(args.apk),'--receipt',str(args.receipt)]
        y.main()
    finally:sys.argv=original_argv;y.pixel_oracle=oracle
    result=json.loads(args.receipt.read_text())
    result['schema']='hasselblad-stage42-port-vs-original-arm64-v1'
    result['portable_comparator']={'configurations':len(counts),
        'channels':sum(c['channels'] for c in counts),
        'differing_from_python_oracle':sum(c['different'] for c in counts),
        'max_python_difference':max(c['max_difference'] for c in counts),
        'original_arm64_tolerance':0,'source':'phocus_port_stage42/src/hb42_colour.c',
        'compiler':'gcc -O2 -ffp-contract=off','android_device_tested':False}
    args.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['portable_comparator']),flush=True)
if __name__=='__main__':main()
