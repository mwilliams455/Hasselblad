"""Build the independent, bounded ColorNoise C implementation.

This library links Stage64's independent YCC candidate; no vendor binary is
loaded here. Native CPU/Android parity require separate private suites.
"""
import ctypes as C
from pathlib import Path
import subprocess


class NoiseContext65(C.Structure):
    _fields_ = [('width', C.c_int), ('height', C.c_int), ('stride', C.c_int),
                ('flags', C.c_uint16), ('optimized_view', C.c_uint8),
                ('strength', C.c_int32),
                *[(field, C.c_void_p) for field in (
                    'red', 'green', 'blue', 'y', 'c1', 'c2', 'direction_mask',
                    'smooth_y', 'median_c1', 'median_c2', 'out_y', 'out_c1',
                    'out_c2', 'out_aux')]]


class NoiseCounters65(C.Structure):
    _fields_ = [(field, C.c_uint64) for field in (
        'converted_sites', 'clamped_sites', 'smoothing_rows', 'median_rows',
        'correction_sites', 'nonzero_mask_sites', 'median_selected_sites')]


class PortableNoise65:
    def __init__(self, work, compiler='gcc', sanitize=False):
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        here = Path(__file__).resolve().parent
        ycc = here.parent / 'phocus_colour_stage64' / 'ycc64.c'
        self.path = work / 'libcolour_noise65.so'
        command = [compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-fno-fast-math', '-ffp-contract=off', '-fPIC', '-shared']
        if sanitize:
            command += ['-fsanitize=undefined', '-fno-sanitize-recover=all']
        command += [str(here / 'noise65.c'), str(ycc), '-o', str(self.path)]
        subprocess.run(command, check=True, capture_output=True)
        self.lib = C.CDLL(str(self.path))
        self.lib.hb_color_noise65.argtypes = [C.POINTER(NoiseContext65), C.POINTER(NoiseCounters65)]
        self.lib.hb_color_noise65.restype = C.c_int
        for name in ('prepare', 'rows', 'correct'):
            f = getattr(self.lib, 'hb_color_noise_' + name + '65')
            f.argtypes = [C.POINTER(NoiseContext65), C.POINTER(NoiseCounters65)]
            f.restype = C.c_int

    @staticmethod
    def bind(arrays, width, height, flags, strength=0, optimized_view=0):
        import numpy as np
        required = ('red', 'green', 'blue', 'y', 'c1', 'c2', 'direction_mask',
                    'smooth_y', 'median_c1', 'median_c2', 'out_y', 'out_c1',
                    'out_c2', 'out_aux')
        assert set(arrays) == set(required)
        shape = next(iter(arrays.values())).shape
        assert len(shape) == 2 and shape[0] == height and shape[1] >= width
        for key, a in arrays.items():
            assert a.shape == shape and a.flags.c_contiguous
            dtype = '<u2' if key in ('red', 'green', 'blue', 'y', 'direction_mask',
                                     'smooth_y', 'out_y') else '<i2'
            assert a.dtype == np.dtype(dtype), (key, a.dtype, dtype)
        return NoiseContext65(width, height, shape[1], flags, optimized_view,
                              strength, *(arrays[key].ctypes.data for key in required))
