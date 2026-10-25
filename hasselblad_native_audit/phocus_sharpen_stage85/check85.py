#!/usr/bin/env python3
"""Focused portable-kernel checks. No vendor payload or demosaic regression is needed."""
import argparse
import ctypes
import json
import subprocess
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
DEFAULT = (100, 1., 0, 10)
SETTINGS = [DEFAULT, (0, 1., 0, 10), (1, .5, 0, 0), (50, 1.5, 2, 5),
            (250, 2., 10, 20), (1000, 3., 255, 255), (500, 4., 128, 0), (1000, 1., 0, 10)]


class Port:
    def __init__(self, work):
        work.mkdir(parents=True, exist_ok=True)
        lib = work / 'sharpen85.so'
        subprocess.run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Wconversion', '-Werror',
                        '-ffp-contract=off', '-shared', '-fPIC', str(HERE/'sharpen85.c'), '-lm', '-o', str(lib)], check=True)
        self.c = ctypes.CDLL(str(lib.resolve()))
        self.c.hb85_tables.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_int] + [ctypes.c_void_p]*4
        self.c.hb85_sharpen14.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                                        ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_int]

    def tables(self, settings):
        at, nt, weights = np.empty(16384, np.int32), np.empty(16384, np.uint8), np.empty(9, np.uint32)
        count = ctypes.c_int()
        assert self.c.hb85_tables(*settings, at.ctypes.data, nt.ctypes.data, weights.ctypes.data, ctypes.byref(count)) == 0
        return weights[:count.value], at, nt

    def render(self, pixels, settings=DEFAULT, inplace=False):
        pixels = np.ascontiguousarray(pixels, dtype=np.uint16)
        out = pixels.copy() if inplace else np.empty_like(pixels)
        source = out if inplace else pixels
        assert self.c.hb85_sharpen14(source.ctypes.data, out.ctypes.data, pixels.shape[1], pixels.shape[0], *settings) == 0
        return out


def patterns(width=33, height=19):
    rng = np.random.default_rng(85)
    y, x = np.indices((height, width))
    ramp = np.rint(np.linspace(0, 16383, width)).astype(np.uint16)
    neutral = np.broadcast_to(ramp[None, :, None], (height, width, 3)).copy()
    impulse = np.zeros_like(neutral); impulse[height//2, width//2] = 16383
    step = np.where(x < width//2, 4096, 12288).astype(np.uint16)
    return {'neutral_ramp': neutral, 'impulse': impulse,
            'step': np.repeat(step[..., None], 3, axis=2),
            'colour_edges': np.stack([x%2*16383, y%2*16383, (x+y)%2*16383], axis=2).astype(np.uint16),
            'random': rng.integers(0, 16384, (height, width, 3), dtype=np.uint16),
            'near_black': rng.integers(0, 1000, (height, width, 3), dtype=np.uint16),
            'near_white': rng.integers(15384, 16384, (height, width, 3), dtype=np.uint16),
            'constant_colour': np.tile(np.array([2000, 8000, 14000], np.uint16), (height, width, 1))}


def host_checks(port):
    cases = seam_checks = 0
    for width, height in ((1, 1), (2, 3), (7, 9), (8, 8), (9, 17), (33, 19), (65, 71)):
        for settings in SETTINGS:
            p = patterns(width, height)['random']
            out = port.render(p, settings)
            assert out.min() >= 0 and out.max() <= 16383
            assert np.array_equal(out, port.render(p, settings, inplace=True))
            if settings[0] == 0: assert np.array_equal(out, p)
            halo = len(port.tables(settings)[0]) // 2
            chunks = []
            for first in range(0, height, 7):
                last = min(height, first + 7)
                lo, hi = max(0, first-halo), min(height, last+halo)
                chunks.append(port.render(p[lo:hi], settings)[first-lo:last-lo])
            assert np.array_equal(out, np.concatenate(chunks))
            seam_checks += 1
            cases += 1
    for settings in SETTINGS:
        for value in (0, 1, 640, 8192, 16383):
            p = np.full((17, 17, 3), value, np.uint16)
            assert np.array_equal(port.render(p, settings), p)
            cases += 1
    p = patterns()['random']; out = np.full_like(p, 54321)
    invalid = [(-1,1.,0,10),(1001,1.,0,10),(100,float('nan'),0,10),(100,float('inf'),0,10),
               (100,.49,0,10),(100,4.01,0,10),(100,1.,-1,10),(100,1.,256,10),
               (100,1.,0,-1),(100,1.,0,256)]
    for settings in invalid:
        assert port.c.hb85_sharpen14(p.ctypes.data, out.ctypes.data, 33, 19, *settings) == -1
        assert np.all(out == 54321)
    for w, h in ((0,1),(1,0),(8193,1),(1,8193),(8192,8192)):
        assert port.c.hb85_sharpen14(p.ctypes.data, out.ctypes.data, w, h, *DEFAULT) == -1
    for ip, op in ((None, out.ctypes.data),(p.ctypes.data,None)):
        assert port.c.hb85_sharpen14(ip, op,33,19,*DEFAULT)==-1
    p[0,0,0]=16384
    assert port.c.hb85_sharpen14(p.ctypes.data,out.ctypes.data,33,19,*DEFAULT)==-1
    assert np.all(out==54321)
    return {'portable_cases':cases,'halo_partition_exact_cases':seam_checks,'invalid_input_cases':18,
            'inplace_exact':True,'default_settings':list(DEFAULT)}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--work',required=True,type=Path)
    a=parser.parse_args(); assert __debug__
    result={'schema':'hasselblad-stage85-host-v1','status':'PASS_PORTABLE_SHARPENING',**host_checks(Port(a.work)),
            'android_integrated':False,'demosaic_retested':False}
    (a.work/'STAGE85_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__': main()
