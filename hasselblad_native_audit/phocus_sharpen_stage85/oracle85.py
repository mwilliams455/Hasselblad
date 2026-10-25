"""Execute separately supplied original ARM64 CPU routines. No pixels are exported."""
import math
import struct
import sys
from pathlib import Path
import numpy as np
from unicorn.arm64_const import UC_ARM64_REG_D0, UC_ARM64_REG_PC, UC_ARM64_REG_X0, UC_ARM64_REG_X30
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_stage41y'))
import inspect_phocus_pipeline41y as y
CTOR = '_ZN15CSharpenAndBlurC1Ejidiiddd'
SHARP = '_ZN15CSharpenAndBlur7SharpenEPKtPtPf'
DTOR = '_ZN15CSharpenAndBlurD1Ev'
OBJ = 0x100f0000


def setup_kernel(r):
    names = {n for n in r.e.func if 'CSharpenAndBlur' in n}
    y.ALLOWED.update(names)
    entries = {r.e.func[n][0]: n for n in names}
    for address in (0x37c5ac0, 0x37c5ac8, 0x37c5ad0):
        r.u.mem_write(address, struct.pack('<Q', r.e.relocation(address)[0]))
    vtable = r.e.relocation(0x37c5ac0)[0]
    for offset in (16, 24, 32, 40):
        r.u.mem_write(vtable + offset, struct.pack('<Q', r.e.relocation(vtable + offset)[0]))
    # Unrelated blur-conversion singleton is unused when blur == 0; no blur math is replaced.
    r.u.mem_write(r.e.relocation(0x37c5ac8)[0], struct.pack('<q', -1))
    r.u.mem_write(r.e.relocation(0x37c5ad0)[0], bytes(16))
    return entries


def math_fixture(r, cpu, address):
    name = r.e.plt.get(address, '')
    if name not in ('log', 'exp'):
        return False
    value = struct.unpack('<d', struct.pack('<Q', cpu.reg_read(UC_ARM64_REG_D0)))[0]
    cpu.reg_write(UC_ARM64_REG_D0, struct.unpack('<Q', struct.pack('<d', getattr(math, name)(value)))[0])
    cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
    return True


class KernelRunner(y.NativePipeline):
    def __init__(self, elf):
        super().__init__(elf)
        self.entries = setup_kernel(self)
        self.u.mem_write(OBJ - 16, b'\xa5' * 16)
        self.u.mem_write(OBJ + 0x200, b'\xa5' * 16)

    def hook(self, cpu, address, size, user):
        if address in getattr(self, 'entries', {}):
            name = self.entries[address]
            start, length = self.e.func[name]
            if (start, start + length) not in self.active:
                self.active.append((start, start + length))
            self.called.add(name)
        if math_fixture(self, cpu, address):
            return
        return super().hook(cpu, address, size, user)

    def get(self, offset, fmt):
        return struct.unpack(fmt, bytes(self.u.mem_read(OBJ + offset, struct.calcsize(fmt))))

    def init(self, width, amount, radius, noise, dark):
        self.u.mem_write(OBJ, bytes(0x200))
        self.call(CTOR, (OBJ, width, amount, noise, dark), (radius, 1., 1., 1.))
        assert self.get(0x180, '<d') == (0.,)  # No blur branch.
        taps, halo = self.get(0x170, '<B')[0], self.get(0x160, '<i')[0]
        def array(offset, count, dtype):
            pointer = self.get(offset, '<Q')[0]
            return np.frombuffer(bytes(self.u.mem_read(pointer, count * np.dtype(dtype).itemsize)), dtype=dtype).copy()
        return halo, array(0xb0, taps, '<u4'), array(0x10, 16384, '<i4'), array(0x168, 16384, 'u1')

    def rows(self, pixels, settings):
        halo, weights, amounts, noise = self.init(pixels.shape[1], *settings)
        original = pixels.tobytes()
        output = []
        # Explicit last-row replication fixture. First-row and horizontal extension execute natively.
        rows = list(pixels) + ([pixels[-1]] * halo if settings[0] else [])
        for row in rows:
            data = np.asarray(row, dtype='<u2').tobytes()
            ip, op = 0x10100000, 0x10110000
            self.u.mem_write(ip - 16, b'\xa5' * 16 + data + b'\xa5' * 16)
            self.u.mem_write(op - 16, b'\xa5' * 16 + b'\xcd' * len(data) + b'\xa5' * 16)
            self.call(SHARP, (OBJ, ip, op, 0))
            if self.u.reg_read(UC_ARM64_REG_X0):
                output.append(np.frombuffer(bytes(self.u.mem_read(op, len(data))), dtype='<u2').reshape(-1, 3).copy())
            assert bytes(self.u.mem_read(ip, len(data))) == data
            for ptr in (ip, op):
                assert bytes(self.u.mem_read(ptr - 16, 16)) == bytes(self.u.mem_read(ptr + len(data), 16)) == b'\xa5' * 16
        assert pixels.tobytes() == original
        assert bytes(self.u.mem_read(OBJ - 16, 16)) == bytes(self.u.mem_read(OBJ + 0x200, 16)) == b'\xa5' * 16
        self.call(DTOR, (OBJ,))
        result = np.asarray(output)
        assert result.shape == pixels.shape
        return result, weights, amounts, noise

# Imported lazily by the audit caller: this harness needs original import defaults,
# but the row oracle above has no dependency on private calibration decoding.
def graph_runner_type():
    sys.path.insert(0, str(ROOT / 'phocus_post_stage55'))
    from audit_post55 import Runner55, CORR, PARAMS, SHARED_DESC, SHARED, BUILD
    from audit_import52 import ImportRunner, DESC
    sharp_ctor = '_ZN16CSharpnessFilterC1Eidiiidd'
    full_filter = '_ZNK16CSharpnessFilter12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'
    from unicorn.arm64_const import UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X8

    class GraphRunner(Runner55):
        def __init__(self, elf, profile):
            names = {n for n in elf.func if any(k in n for k in (
                'CSharpenAndBlur', 'CSharpnessFilter', 'CShiftFilter', 'CImageViewItLi3EEC'))}
            y.ALLOWED.update(names | {'_ZN12CImageFilterD2Ev'})
            super().__init__(elf, profile)
            self.entries.update({elf.func[n][0]: n for n in names})
            self.entries.update(setup_kernel(self))
            self.arguments = []
            self.inplace_ownership_calls = 0

        def hook(self, cpu, address, size, user):
            name = self.e.plt.get(address, '')
            if math_fixture(self, cpu, address): return
            if name.startswith('_ZN12CImageFilter15SetupForInplaceE'):
                # Actual shifts execute; only unique_ptr transfer is supplied.
                ip, op, ret = [cpu.reg_read(reg) for reg in (UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_X8)]
                obj = bytes(self.u.mem_read(ip, 8))
                self.u.mem_write(ip, bytes(8)); self.u.mem_write(op, bytes(8)); self.u.mem_write(ret, obj)
                self.inplace_ownership_calls += 1
                cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30)); return
            if self.record_builder and name == sharp_ctor:
                self.objects[cpu.reg_read(UC_ARM64_REG_X0)] = 'Sharpness'
                self.arguments.append({
                    'integers': [cpu.reg_read(UC_ARM64_REG_X0+i) for i in range(1, 5)],
                    'doubles': [struct.unpack('<d', struct.pack('<Q', cpu.reg_read(UC_ARM64_REG_D0+i)))[0] for i in range(3)]})
                # Bypass Stage55's constructor fixture: execute the original constructor.
                return ImportRunner.hook(self, cpu, address, size, user)
            return super().hook(cpu, address, size, user)

        def graph85(self):
            self.configure([1.4, 1., .7]); self.process()
            self.put(DESC, 0x234, '<2i', 64, 64)
            self.sequence, self.parameters, self.gradation_flags = [], [], []
            self.flags = (0, 0); self.record_builder = True
            # AAPCS float scale argument is S0 (not a double 1.0 in D0).
            float_one = struct.unpack('<d', struct.pack('<fI', 1., 0))[0]
            self.call(BUILD, (0x100a5000, SHARED_DESC, PARAMS, CORR, SHARED, 0, 0, 0), (float_one,))
            self.record_builder = False
            assert self.arguments == [{'integers':[100, 0, 10, 64], 'doubles':[1., 1., 1.]}]
            assert self.gradation_flags == [1]
            assert self.sequence == ['ColorCorrectAll', 'FilmCurve', '16CGradationFilter', 'Sharpness', 'ColorSpaceConvert']
            return {'sequence':self.sequence, 'gradation_version':1, 'full_resolution_sdr_settings':{
                'amount':100,'radius':1.,'noise_limit':0,'dark_limit':10,'scale':1.,'normalization':1.},
                'original_sharpness_constructor_executed':True, 'graph_ownership_fixture':True,
                'raw_description_fixture':{'sensor_codes':[22,6],'width':64,'height':64,
                    'baseline_sharpness_field':0.,'sharpness_compensation_field':0},
                'phone_specific_sharpness_calibration_established':False}

        def full(self, pixels, settings=(100, 1., 0, 10)):
            h, w = pixels.shape[:2]
            assert 9 <= w <= 128 and 9 <= h <= 128
            data, output = 0x10100000, 0x10200000
            inp, out, ip, op, rect, dest, obj = 0x100f2000, 0x100f2100, 0x100f2200, 0x100f2210, 0x100f2300, 0x100f2340, 0x100f4000
            for ptr, ww, hh, buf in ((inp,w,h,data),(out,w-8,h-8,output)):
                self.u.mem_write(ptr, bytes(0x40))
                self.u.mem_write(ptr+8, struct.pack('<4i', ww, hh, 3, ww*3))
                self.u.mem_write(ptr+0x20, struct.pack('<Q', buf))
                self.u.mem_write(ptr+0x30, struct.pack('<i', 3))
            nbytes = (w-8)*(h-8)*6
            self.u.mem_write(data-16, b'\xa5'*16 + pixels.astype('<u2').tobytes() + b'\xa5'*16)
            self.u.mem_write(output-16, b'\xa5'*16 + b'\xcd'*nbytes + b'\xa5'*16)
            for ptr, coords in ((rect,(0,0,w,h)),(dest,(4,4,w-4,h-4))):
                self.u.mem_write(ptr, bytes(32)); self.u.mem_write(ptr+8, b'\1')
                self.u.mem_write(ptr+12, struct.pack('<4i', *coords))
            self.u.mem_write(ip, struct.pack('<Q', inp)); self.u.mem_write(op, struct.pack('<Q', out))
            self.u.mem_write(obj-16, b'\xa5'*16 + bytes(0x78) + b'\xa5'*16)
            amount, radius, noise, dark = settings
            self.call(sharp_ctor, (obj,amount,noise,dark,w), (radius,1.,1.))
            before = self.inplace_ownership_calls
            self.call(full_filter, (obj,rect,dest,ip,op))
            assert self.inplace_ownership_calls-before == 2
            assert struct.unpack('<Q', bytes(self.u.mem_read(0x10002000, 8)))[0] == out
            assert bytes(self.u.mem_read(data, pixels.nbytes)) == (pixels >> 2).astype('<u2').tobytes()
            for ptr, size in ((data,pixels.nbytes),(output,nbytes),(obj,0x78)):
                assert bytes(self.u.mem_read(ptr-16,16)) == bytes(self.u.mem_read(ptr+size,16)) == b'\xa5'*16
            return np.frombuffer(bytes(self.u.mem_read(output,nbytes)),dtype='<u2').copy().reshape(h-8,w-8,3)
    return GraphRunner
