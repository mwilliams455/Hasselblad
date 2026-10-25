#!/usr/bin/env python3
"""Independent Python arithmetic reference for synthetic YCC->linear RGB16.
No Phocus executable, DNG values or original image pixels in this test.
"""
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent

def signed32(value):
    value &= 0xffffffff
    return value-0x100000000 if value & 0x80000000 else value

def python_reference(y, a, b):
    yy=min(65534,y)
    fr=3*a-b+32768
    fb=3*b-a+32768
    rp=signed32((yy//2)*fr)
    bp=signed32((yy//2)*fb)
    # Arithmetic right shift, not C signed truncating division.
    rraw=rp >> 14
    braw=bp >> 14
    dif=signed32(yy*4-rraw-braw)
    graw=dif//2 if dif>=0 else -((-dif)//2)
    def clip(v):return max(0,min(65535,v))
    return (clip(rraw) if rp>=0 else 0,
            clip(graw) if dif>=0 else 0,
            clip(braw) if bp>=0 else 0)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'liboutput74.so'
        subprocess.run(['gcc','-O2','-std=c11','-fPIC','-shared','-Wall','-Wextra','-Werror',
                        '-fno-fast-math','-ffp-contract=off',str(HERE/'output74.c'),'-lm','-o',str(path)],
                       check=True,capture_output=True)
        lib=C.CDLL(str(path))
        fn=lib.hb74_ycc_to_rgb_pixel
        fn.argtypes=[C.c_uint16,C.c_int16,C.c_int16,C.c_double,C.c_void_p]
        fn.restype=C.c_int
        r=random.Random(74001025)
        values=[0,1,2,8191,8192,16383,16384,32767,32768,65533,65534,65535]
        signed=[-32768,-32767,-16384,-1,0,1,16384,32766,32767]
        cases=[(y,a,b) for y in values for a in signed for b in signed]
        cases.extend((r.randrange(65536),r.randrange(-32768,32768),r.randrange(-32768,32768))
                     for _ in range(50000))
        out=(C.c_uint16*3)()
        for y,a,b in cases:
            assert fn(y,a,b,1.0,out)==0
            expect=python_reference(y,a,b)
            assert tuple(out)==expect,(y,a,b,tuple(out),expect)
        print('STAGE74_PYTHON_C_YCC_CODES_EXACT',len(cases)*3,'cases',len(cases))

if __name__=='__main__': main()
