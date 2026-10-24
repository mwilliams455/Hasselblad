"""Build and call the independent C prepasses; does not load a vendor binary."""
import ctypes as C
from pathlib import Path
import subprocess
import numpy as np


class PortableMaps:
    def __init__(self, work, compiler='gcc', sanitize=False):
        work = Path(work); work.mkdir(parents=True, exist_ok=True)
        self.path = work / 'libgradient_maps61.so'
        flags = ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-fno-fast-math', '-ffp-contract=off', '-fPIC', '-shared']
        if sanitize:
            flags += ['-fsanitize=undefined', '-fno-sanitize-recover=all']
        self.command = [compiler, *flags, str(Path(__file__).with_name('gradient_maps61.c')),
                        '-lm', '-o', str(self.path)]
        subprocess.run(self.command, check=True, capture_output=True)
        self.lib = C.CDLL(str(self.path))
        ptr = C.c_void_p
        self.lib.hb_gradient_scale61.argtypes = [ptr, *([C.c_int]*7), C.c_double, ptr, ptr]
        self.lib.hb_gradient_green61.argtypes = [ptr, *([C.c_int]*7), ptr, ptr, ptr, ptr]
        self.lib.hb_gradient_scale61.restype = self.lib.hb_gradient_green61.restype = C.c_int
        for name in ('smooth', 'edge', 'median'):
            f = getattr(self.lib, 'hb_gradient_'+name+'_row61')
            f.argtypes = [ptr, ptr, C.c_int, C.c_int]; f.restype = C.c_int
        self.lib.hb_gradient_directions61.argtypes = [ptr, C.c_int, ptr]
        self.lib.hb_gradient_directions61.restype = C.c_int
        self.lib.hb_gradient_mask61.argtypes = [ptr, ptr, C.c_int16, C.c_int16]
        self.lib.hb_gradient_mask61.restype = C.c_uint16

    @staticmethod
    def checked(a, dtype):
        assert a.ndim == 2 and a.dtype == np.dtype(dtype) and a.flags.c_contiguous
        return a.ctypes.data

    def scale(self, raw, horizontal, vertical, bounds, threshold, width=None):
        h, stride = raw.shape
        assert horizontal.shape == vertical.shape == raw.shape
        return self.lib.hb_gradient_scale61(self.checked(raw, '<u2'), width or stride, h, stride,
                    *bounds, threshold, self.checked(horizontal, '<f4'), self.checked(vertical, '<f4'))

    def green(self, raw, horizontal, vertical, scale, green, bounds, width=None):
        h, stride = raw.shape
        assert horizontal.shape == vertical.shape == scale.shape == green.shape == raw.shape
        return self.lib.hb_gradient_green61(self.checked(raw, '<u2'), width or stride, h, stride,
                    *bounds, self.checked(horizontal, '<f4'), self.checked(vertical, '<f4'),
                    self.checked(scale, '<f4'), self.checked(green, '<u2'))
