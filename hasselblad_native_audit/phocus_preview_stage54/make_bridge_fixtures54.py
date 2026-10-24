#!/usr/bin/env python3
"""Synthetic independent oracle fixtures for the actual Java/JNI bridge."""
import argparse
import itertools
import struct
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'phocus_highlight_stage53'))
from highlight53 import Highlight, equal_lower_limit


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(54)
    neutrals=[np.array(n) for n in itertools.permutations((.3,.7,1.))]
    neutrals += [np.array(n) for n in ((1.,1.,1.),(.5,1.,1.),(1.,.5,1.),(1.,1.,.5))]
    neutrals += [rng.uniform(.1,1.5,3) for _ in range(54)]
    levels=np.linspace(0,65535,9).round().astype(np.uint16)
    pixels=np.vstack([list(itertools.product(levels,repeat=3)),rng.integers(0,65536,(100,3))]).astype(np.uint16)
    data=bytearray(b'HB54TEST'+struct.pack('<ii',len(neutrals),len(pixels)))
    for n in neutrals:
        m=np.eye(3)+rng.uniform(-.2,.2,(3,3))
        gains=n.min()/n;after=m@np.diag(1/gains)
        singular=np.sort(gains)[0]==np.sort(gains)[1]
        output=equal_lower_limit(pixels/65535,gains) if singular else Highlight.prepare(gains).convert(pixels/65535)
        expected=np.floor(np.clip(output,0,1)*65535+.5).astype('<u2')
        for values in (n,m,gains,after):data.extend(np.asarray(values,dtype='<f8').tobytes())
        data.extend(pixels.astype('<u2').tobytes());data.extend(expected.tobytes())
    (a.out/'bridge54.bin').write_bytes(data)
    print('Created 64 synthetic Java/JNI cases with independent NumPy references')


if __name__=='__main__':main()
