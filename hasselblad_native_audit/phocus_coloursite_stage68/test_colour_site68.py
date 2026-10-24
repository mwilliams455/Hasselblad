#!/usr/bin/env python3
"""Standalone Stage68 composition binding test using a labelled MOCK Stage63.
The stub records output arguments but does not implement green interpolation;
this is NOT an original-CPU or full demosaic pixel parity test.
"""
import argparse
import ctypes as C
from pathlib import Path
import numpy as np
import subprocess
import json
from test_colour_gradient68 import directions
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def signed_gradient(a):
    # Independent scalar formula for the already-validated Stage61 edge map.
    cy,cx=a.shape[0]//2,a.shape[1]//2
    def d(y0,x0,y1,x1):
        return abs(int(a[cy+y0,cx+x0])-int(a[cy+y1,cx+x1]))
    h=d(0,-1,0,0)+d(0,0,0,1)+(d(-1,-1,-1,0)+d(-1,0,-1,1)+d(1,-1,1,0)+d(1,0,1,1))//2
    v=d(-1,0,0,0)+d(0,0,1,0)+(d(-1,-1,0,-1)+d(0,-1,1,-1)+d(-1,1,0,1)+d(0,1,1,1))//2
    back=d(-1,-1,0,0)+d(0,0,1,1)+d(-1,0,0,1)+d(0,-1,1,0)
    slash=d(-1,1,0,0)+d(0,0,1,-1)+d(0,-1,-1,0)+d(0,1,1,0)
    result=[
        (v+d(-2,0,-1,0)+(d(-2,-1,-1,-1)+d(-2,1,-1,1))//2)//4,
        (h+d(0,2,0,1)+(d(-1,2,-1,1)+d(1,2,1,1))//2)//4,
        (v+d(2,0,1,0)+(d(2,-1,1,-1)+d(2,1,1,1))//2)//4,
        (h+d(0,-2,0,-1)+(d(-1,-2,-1,-1)+d(1,-2,1,-1))//2)//4,
        (slash+d(-1,1,-2,2)+(d(-1,0,-2,1)+d(0,1,-1,2))//2)//4,
        (back+d(1,1,2,2)+(d(0,1,1,2)+d(1,0,2,1))//2)//4,
        (slash+d(1,-1,2,-2)+(d(0,-1,1,-2)+d(1,0,2,-1))//2)//4,
        (back+d(-1,-1,-2,-2)+(d(-1,0,-2,-1)+d(0,-1,-1,-2))//2)//4,
    ]
    return [int(np.asarray(z&65535,dtype=np.uint16).view(np.int16)) for z in result]

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--work',type=Path,required=True)
 p.add_argument('--stage61-source',type=Path,default=ROOT/'phocus_gradient_stage61/gradient_maps61.c',
                help='Canonical Stage61 gradient source from the checked-out repository')
 a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
 so=a.work/'libcolour_site68_stub.so'
 sources=[HERE/'colour_gradient68.c',HERE/'colour_site68.c',
    ROOT/'phocus_inline_stage67/raw_gradient67.c',
    a.stage61_source,HERE/'mock_green_stage63_68.c']
 subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
    '-fno-fast-math','-ffp-contract=off','-fPIC','-shared',*[str(x) for x in sources],
    '-lm','-o',str(so)],check=True,capture_output=True)
 lib=C.CDLL(str(so))
 api=lib.hb_colour_site_green68;api.restype=C.c_int
 api.argtypes=[*([C.c_void_p]*5),C.c_int,C.c_int16,C.c_int16,
               C.c_void_p,C.c_void_p,C.c_void_p]
 read=lib.hb68_mock_read;read.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p]
 rng=np.random.default_rng(6807)
 count=0
 for width in (9,17,23,41):
  for i in range(512):
   raw=rng.integers(0,65536,(9,width),dtype=np.uint16)
   edge=rng.integers(-32768,32768,(9,width),dtype=np.int16)
   maps=[np.ones((9,width),np.float32) for _ in range(3)]
   y,x=4,width//2;offset=y*width+x
   before=(raw.tobytes(),edge.tobytes())
   out=[np.full(1,1234567,np.int32),np.full(1,1234567,np.int32),np.full(1,12345,np.int16)]
   floors=(50,400) if i%2 else (-100,100)
   actual=api(raw.ctypes.data+offset*2,edge.ctypes.data+offset*2,
      *[m.ctypes.data+offset*4 for m in maps],width,*floors,
      *[v.ctypes.data for v in out])
   assert actual==0
   first=np.empty(8,np.int16);second=np.empty(8,np.int16);got_floors=np.empty(2,np.int16)
   read(first.ctypes.data,second.ctypes.data,got_floors.ctypes.data)
   assert second.tolist()==directions(raw)
   assert first.tolist()==signed_gradient(edge)
   assert got_floors.tolist()==list(floors)
   assert [int(v[0]) for v in out]==[32100,0x511,234]
   assert before==(raw.tobytes(),edge.tobytes())
   # The Stage61 reference implementation is tested separately upstream;
   # this is a compositional contract check, not independent edge parity.
   count+=1
 assert lib.hb68_mock_calls()==count
 report={'schema':'hasselblad-stage68-colour-estimator-composition-host-v1',
     'status':'PASS_MOCK_ESTIMATOR_WIRING', 'cases':count,
     'second_operand_raw_gradient_codes':count*8,
     'stage61_edge_input_wired':True,'stage63_mock_called':count,
     'passed_original_stage63_green_output':False,
     'input_immutability':True,'device_parity':False}
 print(json.dumps(report))
 (a.work/'STAGE68_COLOUR_SITE_MOCK_WIRING.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
