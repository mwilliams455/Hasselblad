"""Build and guarded ABI checks for the independently written C primitive."""
import ctypes as C
import subprocess
from pathlib import Path
import numpy as np


class Params(C.Structure):
    _fields_ = [('order', C.c_int*3), ('undo', C.c_int*3), ('limit_mode', C.c_int)] + [
        (n, C.c_double*3) for n in ('limits', 'weights', 'middle', 'full', 'projection', 'red_projection')]


class Portable:
    def __init__(self, directory):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).with_name('highlight53.c')
        path = directory/'highlight53.so'
        subprocess.run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Wconversion', '-Werror',
                        '-ffp-contract=off', '-shared', '-fPIC', str(source), '-lm', '-o', str(path)], check=True)
        self.compiler = subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0]
        self.lib = C.CDLL(str(path.resolve()))
        self.lib.hb_highlight53_prepare.argtypes = [C.POINTER(Params), C.c_void_p, C.c_void_p, C.c_int]
        self.lib.hb_highlight53_prepare.restype = C.c_int
        for name in ('hb_highlight53_rgb16', 'hb_highlight53_float'):
            fn = getattr(self.lib, name)
            fn.argtypes = [C.POINTER(Params), C.c_void_p, C.c_void_p, C.c_size_t]
            fn.restype = C.c_int
        self.p = Params()

    def prepare(self, gains, truncation, limit=False):
        g = np.ascontiguousarray(gains, dtype=np.float64)
        t = np.ascontiguousarray(truncation, dtype=np.uint16)
        assert g.shape == t.shape == (3,)
        return self.lib.hb_highlight53_prepare(C.byref(self.p), g.ctypes.data, t.ctypes.data, int(limit))

    def render(self, pixels, inplace=False):
        pixels = np.ascontiguousarray(pixels)
        assert pixels.dtype in (np.dtype('uint16'), np.dtype('float32')) and pixels.shape[-1] == 3
        floating = pixels.dtype == np.float32
        fn = self.lib.hb_highlight53_float if floating else self.lib.hb_highlight53_rgb16
        before = bytes(self.p)
        source = np.full(pixels.size+32, 12345, dtype=pixels.dtype)
        source[16:-16] = pixels.ravel()
        target = source if inplace else np.full_like(source, 12345)
        assert fn(C.byref(self.p), source[16:].ctypes.data, target[16:].ctypes.data, pixels.size//3) == 0
        for arr in (source, target): assert np.all(arr[:16] == 12345) and np.all(arr[-16:] == 12345)
        assert bytes(self.p) == before
        if not inplace: assert np.array_equal(source[16:-16], pixels.ravel())
        return target[16:-16].copy().reshape(pixels.shape)

    def check_rejections(self):
        """Rejected inputs must leave prepared parameters/output untouched."""
        assert self.prepare((1, 1.4, 1.8), (65535,)*3) == 0
        frozen = bytes(self.p)
        count = 0
        for gains, levels, expected in (
                ((0, 1, 2), (65535,)*3, -1),
                ((-1, 1, 2), (65535,)*3, -1),
                ((float('nan'), 1, 2), (65535,)*3, -1),
                ((float('inf'), 1, 2), (65535,)*3, -1),
                ((1e-12, 2e-12, 3e-12), (65535,)*3, -1),
                ((1, 1.4, 1.8), (0, 65535, 65535), -1),
                ((1, 1, 2), (65535,)*3, -2)):
            assert self.prepare(gains, levels) == expected and bytes(self.p) == frozen
            count += 1
        for bad in (float('nan'), float('inf'), -1.):
            # Put invalid data last to catch partial writes during a scan.
            source = np.ones((10, 3), dtype=np.float32); source[-1, -1] = bad
            target = np.full_like(source, 12345)
            assert self.lib.hb_highlight53_float(C.byref(self.p), source.ctypes.data, target.ctypes.data, 10) == -1
            assert np.all(target == 12345) and bytes(self.p) == frozen
            before = source.tobytes()
            assert self.lib.hb_highlight53_float(C.byref(self.p), source.ctypes.data, source.ctypes.data, 10) == -1
            assert source.tobytes() == before
            count += 2
        target = np.full(3, 12345, dtype=np.uint16)
        for params, source, dest, pixels in ((None, target.ctypes.data, target.ctypes.data, 1),
                (C.byref(self.p), None, target.ctypes.data, 1),
                (C.byref(self.p), target.ctypes.data, None, 1),
                (C.byref(self.p), target.ctypes.data, target.ctypes.data, C.c_size_t(-1).value)):
            assert self.lib.hb_highlight53_rgb16(params, source, dest, pixels) == -1
            assert np.all(target == 12345)
            count += 1
        return count
