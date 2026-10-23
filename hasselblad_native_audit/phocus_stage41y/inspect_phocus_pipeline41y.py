#!/usr/bin/env python3
"""Audit original Phocus RAW matrix composition and ordinary gradation.

Only aggregate evidence is exported. Vendor code and calibration are read from
an independently supplied, hash-pinned APK. Assertions must remain enabled.
"""
import sys
from pathlib import Path
for stage in ('phocus_stage41w', 'phocus_stage41x'):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / stage))
import argparse, collections, io, json, math, plistlib, struct, zipfile
from importlib.metadata import version
import numpy as np
from unicorn import UC_HOOK_BLOCK, UC_HOOK_CODE
from unicorn.arm64_const import *
from inspect_phocus_profiles41w import Elf, Native, APK_SHA, LIB_SHA, TARGET, DECODE, decrypt_blocks, sha
from inspect_phocus_temperature41x import Runner, ALLOWED as X_ALLOWED, PIXELS, matrix_oracle, lut_oracle, expand_oracle

RAW_MATRIX = '_ZN15CRawColorParams19GetRawRGB2XYZMatrixEi9eCCDTypes13eIRFilterTypei'
RAW_INIT = '_ZN19CRawColorCorrection23InitCRawColorCorrectionEv'
GM_CTOR = '_ZN17CGradationManagerC2E14eFilmCurveType11eCompanding'
CACHE = '_ZN15CRawColorParams3LUTE13uColorProfile'
DNG_MATRIX = '_ZNK7CXMLLut17GetColorMatrixDNGEv'
INITIALIZERS = {
    'local_raw_initializer': (0x34c83f8, 0x94),
    'local_gradation_manager_initializer': (0x3694960, 0xe8),
    'local_gradation_initializer': (0x36957f8, 0x68),
}
ALLOWED = {
    '_ZN10CGradationC1EbPdS0_ibb',
    '_ZN11CStreamableC2Ev',
    '_ZN11CStreamableD2Ev',
    '_ZN11Scaled2DLUT12FromCbCrDataEP5sCbCriiiii',
    '_ZN12CCubicSpline4initEPdS0_i',
    '_ZN12CCubicSpline6splineEPdS0_iddS0_',
    '_ZN12CCubicSpline6splintEPdS0_S0_idS0_',
    '_ZN12CCubicSplineC1Ev',
    '_ZN12CCubicSplineD1Ev',
    '_ZN12CImageSensor17FullPhocusSupportE9eCCDTypes',
    '_ZN12CUniqueImageIdLi2ENSt6__ndk110unique_ptrIA_d14AlignedDeleterIdEEEEC2Eiii',
    '_ZN15CRawColorParams11GetPtrOfLUTE9eCCDTypes13eIRFilterTypei',
    '_ZN15CRawColorParams19GetRawRGB2XYZMatrixEi9eCCDTypes13eIRFilterTypei',
    '_ZN15CRawColorParams7GetCPIDE9eCCDTypes13eIRFilterTypei',
    '_ZN16CColorCorrection7SetupCCE9Matrix3x3S0_P7CXMLLutibNSt6__ndk14spanIKfLm18446744073709551615EEEPttddbb',
    '_ZN17CGradationManager19InitGradationCurvesEv',
    '_ZN17CGradationManager20ReturnGradationCurveE14eFilmCurveType11eCompandingbdb',
    '_ZN17CGradationManagerC2E14eFilmCurveType11eCompanding',
    '_ZN19CRawColorCorrection23GetGradationCurveUpdateEv',
    '_ZN19CRawColorCorrection23InitCRawColorCorrectionEv',
    '_ZN19CRawColorCorrection25GetColorSpaceChangeMatrixE13eWorkingSpace',
    '_ZN6CXRectC1Eiiii',
    '_ZN6CXRectD1Ev',
    '_ZN7CXMLLut10DecodeFromEP9CKeyCoder',
    '_ZN7CXMLLut14InitializeLUTsEbii',
    '_ZN7CXMLLut20CalculateExpandedLUTE6CArrayIiLi2EiES1_ib',
    '_ZN9CGenImageC1Eiii12EelementType14EinitialActionPvi',
    '_ZN9CGenImageD1Ev',
    '_ZN9Matrix3x33SetEPKd',
    '_ZN9Matrix3x34CopyES_',
    '_ZN9Matrix3x3C1EPKd',
    '_ZN9Matrix3x3C1Ev',
    '_ZNK19CRawColorCorrection9GetXMLLutEv',
    '_ZNK7CXMLLut12CalculateLUTEib',
    '_ZNK7CXMLLut15CalculateMatrixEPdi',
    '_ZNK9Matrix3x33GetEPd',
    '_ZNK9Matrix3x36InvertEv',
    '_ZNK9Matrix3x3mlES_',
    '_ZNK9Matrix3x3mlEd',
    'local_gradation_initializer',
    'local_gradation_manager_initializer',
    'local_raw_initializer',
} | X_ALLOWED | {DNG_MATRIX}
DOUBLE_TOLERANCE = 1e-12
CURVE_TOLERANCE = 1
PIXEL_TOLERANCE = 1
RAW, CC, GM = 0x10030000, 0x10010000, 0x10020000


class NativePipeline(Runner):
    def __init__(self, elf):
        # Block-entry guards make the repeated original spline calls tractable.
        original_machine = elf.machine
        def block_machine():
            u = original_machine()
            add = u.hook_add
            u.hook_add = lambda kind, *a, **kw: add(UC_HOOK_BLOCK if kind == UC_HOOK_CODE else kind, *a, **kw)
            return u
        elf.machine = block_machine
        try:
            super().__init__(elf)
        finally:
            elf.machine = original_machine
        self.pool = {}
        self.cache_calls = []
        self.math_calls = collections.Counter()
        self.external_calls = collections.Counter()
        self.reused_allocations = 0
        self.freed_allocations = 0
        for ptr, length in ((self.obj, 0x318), (CC, 0x298), (GM, 0xd0), (RAW, 0x260)):
            self.u.mem_write(ptr - 16, b'\xa5' * 16)
            self.u.mem_write(ptr + length, b'\xa5' * 16)
        # Only singleton/cache storage is supplied; selection and all math execute.
        ptr, _, _ = elf.relocation(0x37c63e8)
        self.u.mem_write(ptr, struct.pack('<Q', 0x10015000))

    def alloc(self, count):
        if self.pool.get(count):
            ptr = self.pool[count].pop()
            self.allocations.append((ptr, count))
            self.u.mem_write(ptr + 16, b'\xcc' * count)
            self.reused_allocations += 1
            return ptr + 16
        return super().alloc(count)

    def hook(self, cpu, address, size, user):
        if address in self.e.plt:
            name = self.e.plt[address]
            if name in ALLOWED:
                start, length = self.e.func[name]
                if (start, start + length) not in self.active:
                    self.active.append((start, start + length))
                self.called.add(name)
                cpu.reg_write(UC_ARM64_REG_PC, start)
                return
            self.external_calls[name] += 1
            if name in ('_ZdlPv', '_ZdaPv', 'free'):
                ptr = cpu.reg_read(UC_ARM64_REG_X0) - 16
                if ptr != -16:
                    row = next(r for r in self.allocations if r[0] == ptr)
                    assert bytes(cpu.mem_read(ptr, 16)) == bytes(cpu.mem_read(ptr + 16 + row[1], 16)) == b'\xa5' * 16
                    self.allocations.remove(row)
                    self.pool.setdefault(row[1], []).append(ptr)
                    self.freed_allocations += 1
            elif name == CACHE:
                cpid = cpu.reg_read(UC_ARM64_REG_X1)
                assert cpid == 0x616
                self.cache_calls.append(cpid)
                cpu.reg_write(UC_ARM64_REG_X0, self.obj)
            elif name == '__cxa_atexit':
                cpu.reg_write(UC_ARM64_REG_X0, 0)
            elif name in ('_ZNSt6__ndk15mutex4lockEv', '_ZNSt6__ndk15mutex6unlockEv'):
                pass  # Single-thread execution, no competing users of these caches.
            elif name in ('pow', 'powf'):
                single = name == 'powf'
                reg = UC_ARM64_REG_S0 if single else UC_ARM64_REG_D0
                fmt, integer = ('<f', '<I') if single else ('<d', '<Q')
                def value(i):
                    return struct.unpack(fmt, struct.pack(integer, cpu.reg_read(reg + i)))[0]
                result = math.pow(value(0), value(1))
                cpu.reg_write(reg, struct.unpack(integer, struct.pack(fmt, result))[0])
                self.math_calls[name] += 1
            else:
                return super().hook(cpu, address, size, user)
            cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
            return
        if address not in (0x30002000, 0x30003058, 0x30003080, 0x300030a0, 0x300030f0):
            assert any(lo <= address and address + size <= hi for lo, hi in self.active), ('Unexpected block', hex(address), size)
        super().hook(cpu, address, size, user)

    def check_guards(self):
        super().check_guards()
        for ptr, length in ((GM, 0xd0), (RAW, 0x260)):
            assert bytes(self.u.mem_read(ptr - 16, 16)) == bytes(self.u.mem_read(ptr + length, 16)) == b'\xa5' * 16

    def call(self, name, args=(), floats=(), ret=0x10002000):
        assert name in ALLOWED
        start, length = self.e.func[name]
        self.active = [(start, start + length)]
        self.called.add(name)
        self.u.mem_write(ret, b'\0' * 80)
        self.u.reg_write(UC_ARM64_REG_X8, ret)
        for i in range(8):
            value = args[i] if i < len(args) else 0
            self.u.reg_write(UC_ARM64_REG_X0 + i, value & 0xffffffffffffffff)
            value = floats[i] if i < len(floats) else 0.
            self.u.reg_write(UC_ARM64_REG_D0 + i, struct.unpack('<Q', struct.pack('<d', value))[0])
        self.u.mem_write(0x200ff000, b'\0' * 64)
        self.u.reg_write(UC_ARM64_REG_SP, 0x200ff000)
        self.u.reg_write(UC_ARM64_REG_X30, 0x30000000)
        self.u.emu_start(start, 0x30000000, count=100000000)
        assert self.u.reg_read(UC_ARM64_REG_PC) == 0x30000000, 'Instruction budget exhausted'
        self.check_guards()

    def doubles(self, ptr, count):
        return np.frombuffer(bytes(self.u.mem_read(ptr, count * 8)), dtype='<f8').copy()

    def curve(self):
        ptr = struct.unpack('<Q', bytes(self.u.mem_read(CC + 0x188, 8)))[0]
        return np.frombuffer(bytes(self.u.mem_read(ptr, 65536 * 4)), dtype='<f4').copy()


def check(actual, expected, tolerance=DOUBLE_TOLERANCE):
    assert actual.shape == expected.shape and np.isfinite(actual).all()
    delta = np.abs(actual.astype(float) - expected.astype(float))
    maximum = float(delta.max())
    assert maximum <= tolerance, maximum
    return {'values': actual.size, 'exact_values': int(np.count_nonzero(delta == 0)), 'max_abs_difference': maximum}



def curve_oracle(e,film,companding):
 def d(a):return np.frombuffer(e.read(a,8),dtype='<f8')[0]
 def ds(a,n):return np.frombuffer(e.read(a,8*n),dtype='<f8').copy()
 t=np.arange(65536)/65536.
 def encode(v):
  if companding==1:return v**d(0x306f9a0)
  return np.where(v>d(0x30705b8),v**(1/3)*d(0x306f9f8)+d(0x3070380),v*d(0x306f8c8)/100)
 if film==7:return np.clip(encode(t)*65536,0,65535).astype(np.uint16).astype(np.float32)
 if film==0 and companding==1:
  v=t**d(0x306fc08)*65536
  lo=v*v*d(0x306f6d0)/32768+v*d(0x3070298)
  diff=65536-v;hi=diff*d(0x306f6d0)+diff*diff*d(0x306f6c8)
  v=(v+np.where(v<32768,lo,hi))/65536
  return np.clip(v**d(0x306f748)*65536,0,65535).astype(np.uint16).astype(np.float32)
 # Piecewise gain stages and a private 1025-entry curve table.
 def piece(v,k,a,b,c):return np.where(v<=.25,v*k,(a+v*b)*v+c)
 v=piece(t,d(0x3070888),d(0x306f838),d(0x306ff78),d(0x306fcd0))
 v=piece(v,d(0x306f690),d(0x306fab8),d(0x3070890),d(0x30702a0))
 tab=ds(0x31871a8,1025);p=v*1024;idx=np.minimum(p.astype(np.int64),1023);frac=p-idx
 blend=tab[idx]*(1-frac)+tab[idx+1]*frac
 v=np.where(v>d(0x3070448),.75*v+.25*blend**d(0x3070798),0.)
 v=piece(v,d(0x3070110),d(0x306fc10),d(0x306fe88),d(0x3070898))
 v=v**d(0x306f9a0)
 # Natural cubic spline with the library's private default control points.
 xx=np.r_[0.,ds(0x306eea0,2),ds(0x306f300,2),1.]
 yy=np.r_[0.,ds(0x306e040,2),ds(0x306e3b0,2),1.]
 orig=xx.copy();xx[1:]=np.where(xx[1:]<d(0x3070628),xx[1:]*d(0x306fd60),d(0x3070440)+xx[1:]*d(0x306fde0))
 yy[1:]=xx[1:]*yy[1:]/orig[1:]
 assert d(0x306fab0)>d(0x3070620)
 h=np.diff(xx);mat=np.eye(6);rhs=np.zeros(6)
 for i in range(1,5):
  mat[i]=0;mat[i,i-1]=h[i-1];mat[i,i]=2*(h[i-1]+h[i]);mat[i,i+1]=h[i]
  rhs[i]=6*((yy[i+1]-yy[i])/h[i]-(yy[i]-yy[i-1])/h[i-1])
 second=np.linalg.solve(mat,rhs)
 ix=np.clip(np.searchsorted(xx,v,side='right')-1,0,4);width=xx[ix+1]-xx[ix]
 a=(xx[ix+1]-v)/width;b=(v-xx[ix])/width
 spline=a*yy[ix]+b*yy[ix+1]+((a*a*a-a)*second[ix]+(b*b*b-b)*second[ix+1])*width*width/6
 v=np.where(v>d(0x3070448),spline,0.)
 if companding!=1:v=encode(v**float.fromhex('0x1.1980000000000p+1'))
 return np.clip(v*65536,0,65535).astype(np.uint16).astype(np.float32)


def matrix_constants(elf):
    def matrix(address):
        return np.frombuffer(elf.read(address, 72), dtype='<f8').reshape(3, 3).copy()
    basis = matrix(0x314ed90)
    xyz_to_internal = matrix(0x3150f00)
    internal_to_xyz = matrix(0x314ed48)
    transforms = [np.eye(3),
        np.linalg.inv(matrix(0x3150de0)) @ internal_to_xyz,
        matrix(0x3150e28) @ internal_to_xyz,
        np.linalg.inv(matrix(0x3150e70)),
        np.linalg.inv(matrix(0x3150e70)) @ internal_to_xyz,
        np.linalg.inv(matrix(0x3150eb8)) @ internal_to_xyz]
    return basis, xyz_to_internal, transforms


def shadow_oracle(elf, model, gain):
    if model == 1:
        return np.array([2., 0., -0., 1.])
    # The limit numerator is an immediate double in the original Init function.
    limit = 15500. / gain
    amplitude = np.frombuffer(elf.read(0x306f810, 8), dtype='<f8')[0]
    return np.array([limit, amplitude / (limit * limit),
                     -2 * amplitude / limit, 1 + amplitude])


def pixel_oracle(pixels, first, second, grid, expanded, curve, shadow):
    height, width, _ = grid.shape
    bias = np.array([25., 39.]) if expanded else np.array([20., 32.])
    output = []
    for rgb in pixels.astype(float):
        yy, cb, cr = first @ rgb
        if yy <= 0:
            output.append([0, 0, 0])
            continue
        x, y = np.clip(np.array([cb, cr]) / yy * 32 + bias, [0, 0], [width - 1, height - 1])
        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, width - 1), min(y0 + 1, height - 1)
        dx, dy = x - x0, y - y0
        chroma = ((grid[y0, x0] * (1 - dx) + grid[y0, x1] * dx) * (1 - dy)
                  + (grid[y1, x0] * (1 - dx) + grid[y1, x1] * dx) * dy) / 32
        # Both native neutral thresholds are zero for the selected filter/model cases.
        limit, a, b, c = shadow
        weight = max(0., min(1., 1. if yy > limit else (a * yy + b) * yy + c))
        # ColorNormalCorrectPixels uses only the two chroma columns. Its
        # luminance contribution is Y directly, irrespective of column zero.
        rgb_out = yy + second[:, 1] * (chroma[0] * yy * weight) + second[:, 2] * (chroma[1] * yy * weight)
        indices = np.clip(rgb_out, 0, 65535).astype(np.int64)
        output.append(curve[indices].astype(np.uint16))
    return np.asarray(output, dtype='<u2')


def audit(elf, profile):
    section = elf.e.get_section_by_name('.init_array')
    initializer_evidence = []
    for name, (address, length) in INITIALIZERS.items():
        rows = [r for r in elf.rels if r['addend'] == address and
                section['sh_addr'] <= r['offset'] < section['sh_addr'] + section['sh_size']]
        assert len(rows) == 1
        initializer_evidence.append({'label': name, 'init_array_slot': hex(int(rows[0]['offset']))})
        elf.func[name] = (address, length)
    runner = NativePipeline(elf)
    runner.profile = profile
    runner.call(DECODE, (runner.obj, runner.coder))
    runner.u.mem_write(runner.obj + 9, b'\1')
    frozen = [(runner.obj, bytes(runner.u.mem_read(runner.obj, 0x318)))]
    frozen += [(p + 16, bytes(runner.u.mem_read(p + 16, n))) for p, n in runner.allocations]
    raw_matrix_cases = []
    for temperature in (0, 2000, 4000, 9100, 10001):
        runner.call(RAW_MATRIX, (temperature, 22, 6, 0))
        expected = np.array(profile['mfd']) * .5 + 1 if temperature == 0 else matrix_oracle(profile, temperature)
        raw_matrix_cases.append({'temperature_argument': temperature,
            'dng_matrix_branch': temperature == 0, **check(runner.doubles(0x10002000, 9), expected)})
    for name in INITIALIZERS:
        runner.call(name)
    runner.call(GM_CTOR, (GM, 1, 1))
    print('Original initializers, gradation constructor and curve generation completed', flush=True)
    curve_cases, curves = [], {}
    for film, companding, address in ((0, 1, 0x4e53a34), (1, 1, 0x4e93a34),
            (1, 2, 0x4ed3a34), (7, 1, 0x4f13a34), (7, 2, 0x4f53a34)):
        actual = np.frombuffer(bytes(runner.u.mem_read(address, 65536 * 4)), dtype='<f4')
        expected = curve_oracle(elf, film, companding)
        result = check(actual, expected, CURVE_TOLERANCE)
        assert np.all(np.diff(actual) >= 0) and actual.min() >= 0 and actual.max() <= 65535
        curve_cases.append({'film_code': film, 'companding_code': companding, **result,
                            'finite_monotonic_and_bounded': True})
        curves[film, companding] = expected
    curves[0, 2] = curves[1, 2]
    print('Five complete curve tables verified against independent calculation', flush=True)
    runner.u.mem_write(RAW + 8, struct.pack('<Q', GM))
    runner.u.mem_write(RAW + 0xb0, struct.pack('<Q', CC))
    runner.u.mem_write(RAW + 0x250, struct.pack('<3i', 22, 6, 0))
    basis, xyz_to_internal, transforms = matrix_constants(elf)
    basis_inverse = np.linalg.inv(basis)
    rng = np.random.default_rng(410025)
    basis_pixels = [[0, 0, 0], [65535, 0, 0], [0, 65535, 0], [0, 0, 65535],
                    [65535, 65535, 0], [65535, 0, 65535], [0, 65535, 65535], [65535] * 3]
    ramps = np.repeat(np.array([1, 2, 7, 255, 256, 1023, 4095, 8191, 15500, 16383, 32767, 65534])[:, None], 3, axis=1)
    shadows = np.array([[2, 1, 1], [1, 2, 1], [1, 1, 2], [100, 50, 25],
                        [1000, 500, 250], [8000, 4000, 2000], [16000, 8000, 4000], [25, 50, 100]])
    pixels = np.vstack([basis_pixels, ramps, shadows, rng.integers(0, 65536, (256, 3))]).astype('<u2')
    source = pixels.tobytes()
    inp, out = 0x10080000, 0x10090000
    runner.u.mem_write(inp, source)
    cases = []
    for temperature, requested_film in ((2400, 0), (4000, 1), (9100, 7)):
        profile_matrix = matrix_oracle(profile, temperature).reshape(3, 3)
        for gains, gain in (([1., 1., 1.], 1.), ([1.8, 1., .7], 2.)):
            scaled = profile_matrix @ np.diag(gains)
            for model in (0, 1):
                q = 1.7 if model == 1 else 1.
                expected_first = basis @ xyz_to_internal @ scaled * q
                expected_shadow = shadow_oracle(elf, model, gain)
                for workspace in range(6):
                    runner.u.mem_write(GM + 4, struct.pack('<i', requested_film))
                    runner.u.mem_write(RAW + 0x20, struct.pack('<i', workspace))
                    runner.u.mem_write(RAW + 0x58, struct.pack('<i', model))
                    runner.u.mem_write(RAW + 0x1f0, struct.pack('<dd', float(temperature), gain))
                    runner.u.mem_write(RAW + 0x228, struct.pack('<3d', *gains))
                    runner.u.mem_write(RAW + 0x248, struct.pack('<d', gain))
                    runner.call(RAW_INIT, (RAW,))
                    expected_second = transforms[workspace] @ basis_inverse
                    first_result = check(runner.doubles(CC + 8, 9).reshape(3, 3), expected_first)
                    second_result = check(runner.doubles(CC + 0x50, 9).reshape(3, 3), expected_second)
                    check(runner.doubles(RAW + 0x60, 9).reshape(3, 3), scaled)
                    check(runner.doubles(CC + 0xf0, 9).reshape(3, 3), profile_matrix)
                    check(runner.doubles(CC + 0x1b8, 4), expected_shadow)
                    assert np.array_equal(runner.doubles(CC + 0xe0, 2), [0., 0.])
                    assert runner.u.mem_read(CC + 0x290, 1)[0] == model
                    grid, _ = runner.table(CC + 0x138)
                    expected_grid = lut_oracle(profile, temperature, bool(model))
                    if workspace:
                        expected_grid = expand_oracle(expected_grid)
                    check(grid, expected_grid)
                    film, companding = (7 if model else requested_film), (2 if workspace else 1)
                    curve = curves[film, companding]
                    curve_result = check(runner.curve(), curve, CURVE_TOLERANCE)
                    assert struct.unpack('<ii', bytes(runner.u.mem_read(GM, 8))) == (companding, film)
                    before = [(CC, bytes(runner.u.mem_read(CC, 0x298))), (inp, source)]
                    before += [(p + 16, bytes(runner.u.mem_read(p + 16, n))) for p, n in runner.allocations]
                    runner.u.mem_write(out, b'\xa5' * 32 + b'\xcc' * len(source) + b'\xa5' * 32)
                    runner.call(PIXELS, (0, CC, out + 32, inp, len(pixels), 0))
                    actual = np.frombuffer(bytes(runner.u.mem_read(out + 32, len(source))), dtype='<u2').reshape(-1, 3)
                    expected = pixel_oracle(pixels, expected_first, expected_second, expected_grid,
                                            bool(workspace), curve, expected_shadow)
                    pixel_result = check(actual, expected, PIXEL_TOLERANCE)
                    assert bytes(runner.u.mem_read(out, 32)) == bytes(runner.u.mem_read(out + 32 + len(source), 32)) == b'\xa5' * 32
                    assert all(bytes(runner.u.mem_read(p, len(v))) == v for p, v in before)
                    cases.append({'temperature': temperature, 'per_channel_gain_fixture': gains,
                        'scalar_gain_fixture': gain, 'color_model_code': model, 'working_space_code': workspace,
                        'requested_film_code': requested_film, 'selected_film_code': film,
                        'selected_companding_code': companding, 'reproduction_lut': bool(model),
                        'expanded_lut': bool(workspace), 'first_matrix': first_result,
                        'second_matrix': second_result, 'selected_curve': curve_result,
                        'pixels': len(pixels), 'pixel_channels': pixel_result,
                        'default_thresholds_verified': True, 'input_immutability_and_guards_pass': True})
        print(f'Native RAW initialization and pixel cases passed at {temperature} K', flush=True)
    assert all(bytes(runner.u.mem_read(p, len(v))) == v for p, v in frozen)
    runner.check_guards()
    return {'initializer_evidence': initializer_evidence, 'raw_matrix_cases': raw_matrix_cases,
        'curve_generation_cases': curve_cases, 'pipeline_cases': cases,
        'double_tolerance': DOUBLE_TOLERANCE, 'curve_code_tolerance': CURVE_TOLERANCE,
        'pixel_code_tolerance': PIXEL_TOLERANCE,
        'profile_cache_fixture_calls': len(runner.cache_calls), 'all_requested_cache_ids': ['0x0616'],
        'configuration_queries': sorted(set(runner.config_queries)),
        'external_host_calls': dict(sorted(runner.external_calls.items())),
        'host_math_calls': dict(runner.math_calls), 'allocations_reused': runner.reused_allocations,
        'allocations_checked_at_free': runner.freed_allocations, 'profile_unchanged': True,
        'object_allocation_and_output_guards_pass': True,
        'original_functions': [{'name': n, 'address': hex(elf.func[n][0]), 'bytes': elf.func[n][1],
                               'sha256': sha(elf.read(*elf.func[n]))} for n in sorted(runner.called)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__, 'Assertions must remain enabled'
    original = args.apk.read_bytes()
    assert sha(original) == APK_SHA
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        lib = archive.read('lib/arm64-v8a/libcrosssdk.so')
        data = archive.read('assets/Colormaps/' + TARGET)
    assert sha(lib) == LIB_SHA
    elf = Elf(lib)
    blocks = np.frombuffer(data, dtype=np.uint8).reshape(-1, 16)
    plain = (decrypt_blocks(elf, blocks[1:]) ^ blocks[:-1]).tobytes()
    padding = plain[-1]
    assert 1 <= padding <= 16 and plain[-padding:] == bytes([padding]) * padding
    plain = plain[:-padding]
    assert sha(plain) == 'c2b3d08e0d489eb852610c12a9b985e9d0340a4dd544f5b0b5b7a6a4f3427e95'
    profile = plistlib.loads(plain)
    result = {'schema': 'hasselblad-stage41y-native-matrix-gradation-v1',
        'apk_sha256': APK_SHA, 'library_sha256': LIB_SHA, 'profile_sha256': sha(plain),
        'selected_profile': TARGET, 'audit': audit(elf, profile),
        'fixtures': {'profile_cache': 'already loaded CPID 0x0616 returned after original selector',
            'configuration_service': 'all queried booleans false; live app settings unobserved',
            'object_lifecycle': 'parent RAW/correction objects initialized by harness; original RAW Init and SetupCC executed',
            'gradation_lifecycle': 'original constructor and three ELF init-array functions executed',
            'standard_math': 'host math.pow for pow; powf uses float inputs and float-rounded host math.pow',
            'allocation': 'guarded single-thread arena; guards checked before reuse',
            'mutex_and_destructor_registration': 'single-thread host no-op fixtures',
            'per_capture_state': 'explicit temperatures, numeric mode codes, channel gains and scalar gains',
            'input_pixels': 'synthetic RGB16; RAW decoding, linearization and demosaic not run'},
        'bounds': {'phocus_matrix_spline_lut_and_pixel_functions_replaced_by_oracle': False,
            'android_libm_binary_executed': False, 'identity_curve_or_synthetic_rgb_basis_used': False,
            'full_app_or_complete_raw_pipeline_executed': False, 'photo_pixels_processed': False,
            'camera_main_isp_equivalence_proven': False, 'phone_sensor_adaptation_verified': False,
            'production_renderer_changed': False, 'vendor_arrays_code_or_crypto_material_exported': False},
        'runtime': {p: version(p) for p in ('numpy', 'unicorn', 'capstone', 'pyelftools', 'tifffile')}}
    assert sha(args.apk.read_bytes()) == APK_SHA
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    a = result['audit']
    print(json.dumps({'curve_values': sum(r['values'] for r in a['curve_generation_cases']),
        'pipeline_cases': len(a['pipeline_cases']), 'pixels': sum(r['pixels'] for r in a['pipeline_cases']),
        'channels': sum(r['pixel_channels']['values'] for r in a['pipeline_cases']),
        'exact_channels': sum(r['pixel_channels']['exact_values'] for r in a['pipeline_cases']),
        'max_channel_difference': max(r['pixel_channels']['max_abs_difference'] for r in a['pipeline_cases']),
        'original_functions': len(a['original_functions']), 'full_raw_render': False}))


if __name__ == '__main__':
    main()
