"""Compile independent interpolation primitives; no vendor code is loaded."""
import ctypes as C
from pathlib import Path
import subprocess


class PortableInterpolation:
    def __init__(self, work, compiler='gcc', sanitize=False):
        work = Path(work); work.mkdir(parents=True, exist_ok=True)
        self.path = work / 'libinterpolation62.so'
        flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-fno-fast-math', '-ffp-contract=off', '-fPIC', '-shared']
        if sanitize:
            flags += ['-fsanitize=undefined', '-fno-sanitize-recover=all']
        self.command = [compiler, *flags, str(Path(__file__).with_name('interpolation62.c')),
                        '-o', str(self.path)]
        subprocess.run(self.command, check=True, capture_output=True)
        self.lib = C.CDLL(str(self.path))
        self.lib.hb_blue_at_red62.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32, C.c_int]
        self.lib.hb_blue_at_red62.restype = C.c_int32
        self.lib.hb_red_blue_at_green62.argtypes = [C.c_void_p]*5 + [C.c_uint32, C.c_int]
        self.lib.hb_red_blue_at_green62.restype = None
