"""Compile independent YCC C candidate without loading any vendor library."""
import ctypes as C
from pathlib import Path
import subprocess


class PortableYCC:
    def __init__(self, work, compiler='gcc', sanitize=False):
        work=Path(work);work.mkdir(parents=True,exist_ok=True)
        self.path=work/'libhb_directional_ycc64.so'
        here=Path(__file__).resolve().parent
        flags=['-std=c11','-O2','-Wall','-Wextra','-Werror',
               '-fno-fast-math','-ffp-contract=off','-fPIC','-shared']
        if sanitize:
            flags+=['-fsanitize=undefined','-fno-sanitize-recover=all']
        self.command=[compiler,*flags,str(here/'ycc64.c'),'-o',str(self.path)]
        subprocess.run(self.command,check=True,capture_output=True)
        self.lib=C.CDLL(str(self.path))
        self.lib.hb_directional_ycc64.argtypes=[C.c_uint32]+[C.c_void_p]*10+[C.c_int]
        self.lib.hb_directional_ycc64.restype=C.c_int
