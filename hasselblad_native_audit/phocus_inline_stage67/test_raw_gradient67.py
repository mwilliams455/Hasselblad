#!/usr/bin/env python3
"""Portable C versus separately authored Python RAW-direction reference.

No original binary, disassembly, sensor profile or photograph required.
"""
import ctypes as C
import json
from pathlib import Path
import subprocess
import tempfile
import numpy as np

HERE=Path(__file__).resolve().parent

def reference(tile):
    """Explicit spatial formula. Input is a centered 5x5 RAW patch."""
    raw=np.asarray(tile,dtype=np.uint16)
    assert raw.shape==(5,5)
    def gap(a,b):
        return abs(int(raw[a[0]+2,a[1]+2])-int(raw[b[0]+2,b[1]+2]))
    def sep(*points):return gap(points[0],points[1])
    N=sep((-2,0),(0,0))+sep((-1,0),(1,0)) + (
      sep((-2,-1),(0,-1))+sep((-2,1),(0,1)))//2 +(
      sep((-1,-1),(1,-1))+sep((-1,1),(1,1)))//2
    E=sep((0,-1),(0,1))+sep((0,0),(0,2)) + (
      sep((-1,-1),(-1,1))+sep((1,-1),(1,1)))//2 + (
      sep((-1,0),(-1,2))+sep((1,0),(1,2)))//2
    S=sep((-1,0),(1,0))+sep((0,0),(2,0)) + (
      sep((-1,-1),(1,-1))+sep((-1,1),(1,1)))//2 + (
      sep((0,-1),(2,-1))+sep((0,1),(2,1)))//2
    W=sep((0,-2),(0,0))+sep((0,-1),(0,1)) + (
      sep((-1,-2),(-1,0))+sep((1,-2),(1,0)))//2 + (
      sep((-1,-1),(-1,1))+sep((1,-1),(1,1)))//2
    NE=sep((-2,1),(0,-1))+sep((-2,2),(0,0)) +sep((-1,1),(1,-1))+sep((-1,2),(1,0))
    SE=sep((-1,-1),(1,1))+sep((-1,0),(1,2)) +sep((0,-1),(2,1))+sep((0,0),(2,2))
    SW=sep((-1,0),(1,-2))+sep((-1,1),(1,-1)) +sep((0,0),(2,-2))+sep((0,1),(2,-1))
    NW=sep((-2,-2),(0,0))+sep((-2,-1),(0,1)) +sep((-1,-2),(1,0))+sep((-1,-1),(1,1))
    return [int(x>>3) for x in (N,E,S,W,NE,SE,SW,NW)]

def build(where):
    lib=Path(where)/'libraw_gradient67.so'
    cmd=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
         '-fno-fast-math','-ffp-contract=off','-fPIC','-shared',
         str(HERE/'raw_gradient67.c'),'-o',str(lib)]
    subprocess.run(cmd,check=True)
    return lib

def main():
    rng=np.random.default_rng(6711)
    result={'status':'PASS_PYTHON_C_RAW_GRADIENT', 'reference_fixtures':0,
            'exact_direction_codes':0,'strides':[9,17,23,41],
            'untouched_input_and_output_guards':True}
    with tempfile.TemporaryDirectory() as work:
        lib=C.CDLL(str(build(work)))
        f=lib.hb_inline_raw_gradient67
        f.argtypes=[C.c_void_p,C.c_int,C.c_void_p];f.restype=C.c_int
        for stride in result['strides']:
            for i in range(1200):
                matrix=rng.integers(0,65536,(9,stride),dtype=np.uint16)
                if i<10:matrix.fill([0,1,2,9,10000,32767,32768,65533,65534,65535][i])
                if 10<=i<18:
                    yy,xx=np.indices(matrix.shape)
                    boundary=[xx<stride//2,yy<4,xx+yy<stride//2+4,xx-yy<stride//2-4][(i-10)%4]
                    matrix[:]=np.where(boundary,65535 if i%2==0 else 0,0 if i%2==0 else 65535)
                if 18<=i<32:
                    matrix.fill(0);matrix[2+i%5,stride//2+(i%3)-1]=65535
                untouched=matrix.tobytes()
                output=np.full(10,-12345,np.int16)
                centre=matrix.ctypes.data+(4*stride+stride//2)*2
                assert f(centre,stride,output[1:9].ctypes.data)==0
                expect=reference(matrix[2:7,stride//2-2:stride//2+3])
                assert output[1:9].tolist()==expect,(stride,i,output[1:9],expect)
                assert output[0]==output[9]==-12345
                assert matrix.tobytes()==untouched
                result['reference_fixtures']+=1
                result['exact_direction_codes']+=8
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
