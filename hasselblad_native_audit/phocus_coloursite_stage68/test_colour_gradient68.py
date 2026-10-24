#!/usr/bin/env python3
"""Independent spatial reference for colour-site raw16 directional gradients.
No vendor binary, private photographs, or instruction-list dependency.
"""
from pathlib import Path
import argparse
import ctypes as C
import json
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
PAIR_DIAGONALS=(
 (((-2,1),(-1,0)),((-2,2),(0,0)),((-1,0),(0,-1)),((-1,1),(1,-1)),((-1,2),(0,1)),((0,1),(1,0))),
 (((-1,-1),(1,1)),((-1,0),(0,1)),((0,-1),(1,0)),((0,0),(2,2)),((0,1),(1,2)),((1,0),(2,1))),
 (((-1,0),(0,-1)),((-1,1),(1,-1)),((0,-1),(1,-2)),((0,0),(2,-2)),((0,1),(1,0)),((1,0),(2,-1))),
 (((-2,-2),(0,0)),((-2,-1),(-1,0)),((-1,-2),(0,-1)),((-1,-1),(1,1)),((-1,0),(0,1)),((0,-1),(1,0))),
)
PRIMARY=(
 (((-2,0),(0,0)),((-1,0),(1,0))),
 (((0,-1),(0,1)),((0,0),(0,2))),
 (((-1,0),(1,0)),((0,0),(2,0))),
 (((0,-2),(0,0)),((0,-1),(0,1))),
)
PERIPHERAL=(
 (((-2,-1),(0,-1)),((-2,1),(0,1)),((-1,-1),(1,-1)),((-1,1),(1,1))),
 (((-1,-1),(-1,1)),((-1,0),(-1,2)),((1,-1),(1,1)),((1,0),(1,2))),
 (((-1,-1),(1,-1)),((-1,1),(1,1)),((0,-1),(2,-1)),((0,1),(2,1))),
 (((-1,-2),(-1,0)),((-1,-1),(-1,1)),((1,-2),(1,0)),((1,-1),(1,1))),
)
PAIRING=((0,1,2,3),(0,2,1,3),(0,1,2,3),(0,2,1,3))

def directions(a):
    sy,sx=a.shape;assert sy>=5 and sx>=5
    cy,cx=sy//2,sx//2
    def sample(pos):return int(a[cy+pos[0],cx+pos[1]])
    def diff(edge):return abs(sample(edge[0])-sample(edge[1]))
    output=[]
    for i in range(4):
        p=PRIMARY[i];d=PERIPHERAL[i];t=PAIRING[i]
        summed=sum(diff(e) for e in p)
        summed+=(diff(d[t[0]])+diff(d[t[1]]))//2
        summed+=(diff(d[t[2]])+diff(d[t[3]]))//2
        output.append(np.asarray((summed>>3)&65535,dtype=np.uint16).view(np.int16).item())
    for edges in PAIR_DIAGONALS:
        val=sum(diff(e) for e in edges)>>3
        output.append(np.asarray(val&65535,dtype=np.uint16).view(np.int16).item())
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--safe-receipt',type=Path,required=True)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    lib=a.work/'libcolour68.so'
    cmd=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fno-fast-math',
        '-ffp-contract=off','-shared','-fPIC',str(HERE/'colour_gradient68.c'),
        str(ROOT/'phocus_inline_stage67'/'raw_gradient67.c'),'-o',str(lib)]
    subprocess.run(cmd,check=True,capture_output=True)
    api=C.CDLL(str(lib)).hb_colour_raw_gradient68
    api.argtypes=[C.c_void_p,C.c_int,C.c_void_p];api.restype=C.c_int
    rng=np.random.default_rng(6806)
    cases=0;different_from_stage67=0
    for width in (9,17,23,41):
        patterns=[]
        for v in (0,1,255,10000,32767,65535):
            patterns.append(np.full((9,width),v,np.uint16))
        for row in range(2,7):
            for col in range(width//2-2,width//2+3):
                data=np.zeros((9,width),np.uint16);data[row,col]=65535;patterns.append(data)
        yy,xx=np.indices((9,width))
        patterns.append(np.where(xx<width//2,65535,0).astype(np.uint16))
        patterns.append(np.where(yy<4,0,65535).astype(np.uint16))
        patterns.extend(rng.integers(0,65536,(9,width),dtype=np.uint16) for _ in range(2000))
        for data in patterns:
            before=data.tobytes()
            storage=np.full(10,12345,np.int16)
            code=api(data.ctypes.data+(4*width+width//2)*2,width,storage[1:9].ctypes.data)
            assert code==0 and storage[0]==storage[-1]==12345
            expected=directions(data)
            assert storage[1:9].tolist()==expected,(width,cases,storage.tolist(),expected)
            assert data.tobytes()==before
            cases+=1
    receipt={'schema':'hasselblad-stage68-colour-gradient-host-v1',
       'status':'PASS_INDEPENDENT_PYTHON_C11', 'cases':cases,
       'exact_direction_codes':cases*8,'strides_tested':[9,17,23,41],
       'max_absolute_difference':0,'source_immutability_and_canaries':True,
       'colour_diagonal_differences_per_direction':6,
       'native_unicorn_executed':False,'device_execution_compared':False,
       'complete_demosaic_port':False,'scene_fitted_parameters':0}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
if __name__=='__main__':main()
