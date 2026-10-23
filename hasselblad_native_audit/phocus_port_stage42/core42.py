"""Host binding for the same portable source compiled into the Android JNI lib."""
import ctypes as C
from pathlib import Path
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parent
class Params(C.Structure):
    _fields_=[('first',C.c_double*9),('second',C.c_double*9),
              ('shadow',C.c_double*4),('wb',C.c_double*3),('exposure',C.c_double),
              ('wb_owner',C.c_uint32),('width',C.c_uint32),('height',C.c_uint32),
              ('bias_x',C.c_double),('bias_y',C.c_double),
              ('grid',C.POINTER(C.c_double)),('grid_count',C.c_size_t),
              ('curve',C.POINTER(C.c_float)),('curve_count',C.c_size_t)]

class Core:
    def __init__(self,path,compiler='gcc'):
        path=Path(path).resolve()
        subprocess.run([compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror',
            '-ffp-contract=off','-shared','-fPIC',str(ROOT/'src/hb42_colour.c'),
            '-lm','-o',str(path)],check=True)
        self.lib=C.CDLL(str(path))
        self.lib.hb42_validate.argtypes=[C.POINTER(Params)]
        self.lib.hb42_render.argtypes=[C.POINTER(Params),C.c_void_p,C.c_size_t,C.c_void_p]
    @staticmethod
    def params(first,second,grid,expanded,curve,shadow,wb=(1,1,1),exposure=1,wb_owner=1):
        grid=np.ascontiguousarray(grid,dtype=np.float64)
        curve=np.ascontiguousarray(curve,dtype=np.float32)
        p=Params()
        for field,values in [('first',first),('second',second),('shadow',shadow),('wb',wb)]:
            getattr(p,field)[:]=np.asarray(values).ravel()
        p.exposure=exposure;p.wb_owner=wb_owner
        p.width=grid.shape[1];p.height=grid.shape[0]
        p.bias_x,p.bias_y=(25,39) if expanded else (20,32)
        p.grid=grid.ctypes.data_as(C.POINTER(C.c_double));p.grid_count=grid.size
        p.curve=curve.ctypes.data_as(C.POINTER(C.c_float));p.curve_count=curve.size
        p._arrays=(grid,curve)
        return p
    def render(self,pixels,p):
        pixels=np.ascontiguousarray(pixels,dtype=np.uint16)
        if pixels.ndim<2 or pixels.shape[-1]!=3:raise ValueError('RGB triplets required')
        out=np.empty_like(pixels)
        status=self.lib.hb42_render(C.byref(p),pixels.ctypes.data,pixels.size//3,out.ctypes.data)
        if status:raise ValueError(f'hb42_render rejected parameters: {status}')
        return out
