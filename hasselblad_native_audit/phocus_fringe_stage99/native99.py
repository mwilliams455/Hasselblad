"""Native adapter plus independent NumPy oracle for every quality fixture."""
import ctypes as C
import numpy as np
from pathlib import Path
from reference99 import candidate as reference
U=C.POINTER(C.c_uint16);B=C.POINTER(C.c_uint8)
lib=None
max_reference_error=0

def configure(work):
 global lib
 lib=C.CDLL(str((Path(work)/'libhbfringe99.so').resolve()))
 lib.hb99_chroma_roi.argtypes=[U,C.c_size_t,B,C.c_size_t,C.c_int,C.c_int,C.c_double,C.c_double,U,C.c_size_t]

def candidate(rgb,n,**kwargs):
 global max_reference_error
 a=np.ascontiguousarray(np.pad(rgb,((15,15),(15,15),(0,0)),mode='symmetric'));flags=np.zeros(a.shape[:2],np.uint8);out=np.empty_like(rgb)
 assert lib.hb99_chroma_roi(a.ctypes.data_as(U),a.size,flags.ctypes.data_as(B),flags.size,a.shape[1],a.shape[0],n[0],n[2],out.ctypes.data_as(U),out.size)==0
 expected=reference(rgb,n)
 error=int(np.abs(out.astype(int)-expected.astype(int)).max());max_reference_error=max(max_reference_error,error)
 assert error<=1,('native reference',error)
 before=rgb/n;after=out/n
 dy=np.abs((after[:,:,0]+2*after[:,:,1]+after[:,:,2]-before[:,:,0]-2*before[:,:,1]-before[:,:,2])*.25)
 assert dy.max()<=.125*(1/n[0]+2+1/n[2])+1e-8
 return out
