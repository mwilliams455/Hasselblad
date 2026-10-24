#!/usr/bin/env python3
"""Bounded native RAW graph and highlight code-domain audit.

Original machine code and camera fallback levels are loaded only from a private
APK. Public output contains synthetic fixtures and aggregate assertions only.
Graph construction runs original code; graph storage, optional HDR metadata,
noise and lens service fixtures do not constitute a full RAW pixel replay.
"""
import argparse
import hashlib
import itertools
import json
import struct
import sys
import tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_highlight_stage53'))
from audit_highlight53 import HighlightRunner, Highlight, Portable, load_private, y, RECT
from audit_import52 import CORR, DESC, PARAMS, EMPTY, SHARED_DESC, RAW_BUILD
from unicorn.arm64_const import *

TRUNC = '_ZN19CHighlightRecoverer13GetTruncLevelE9eCCDTypes'
BASE = '_ZN12CCameraImage14AddBaseFiltersER15CImageProcessorP13CRawImageFilePK15sRawDescriptionbbP6CXRect'
HDR_HOOK = 0x30005000
OPCODES = '_ZN13CRawImageFile11OpcodeListsEv'
BLACK_CTOR = '_ZN26CBlackLevelSubstractFilterC1Eii'
BLACK_CPU = '_ZNK26CBlackLevelSubstractFilter12FilterResultE6CXRectS0_NSt6__ndk110unique_ptrI14CBufferedImageNS1_14default_deleteIS3_EEEES6_'


class RawDomainRunner(HighlightRunner):
    def __init__(self, elf, profile):
        y.ALLOWED.update({TRUNC, BASE, OPCODES, BLACK_CTOR, BLACK_CPU})
        self.base_fixture = False
        self.opcode_fixture = False
        self.trunc_calls = 0
        super().__init__(elf, profile)

    def hook(self, cpu, address, size, user):
        name = self.e.plt.get(address, '')
        def reg(i): return cpu.reg_read(UC_ARM64_REG_X0+i)
        def finish(): cpu.reg_write(UC_ARM64_REG_PC, cpu.reg_read(UC_ARM64_REG_X30))
        if self.base_fixture and address == HDR_HOOK:
            self.u.mem_write(reg(8), b'\0'*0x40)
            finish(); return
        if self.opcode_fixture and name.startswith('_ZN14CRawTiffHeader6GetTagE'):
            self.opcode_queries.append({'ifd_index': reg(1), 'tag': reg(2)})
            self.put(reg(4), 0, '<I', 0)  # Explicit absent-tag fixture.
            cpu.reg_write(UC_ARM64_REG_X0, 0)
            finish(); return
        if self.raw_builder:
            if name == TRUNC:
                self.trunc_calls += 1  # Execute the original fallback function.
            if name.startswith('_ZN15CImageProcessor13EmplaceFilterI'):
                kind = name.split('EmplaceFilterI', 1)[1].split('J', 1)[0]
                event = {'filter': kind}
                if kind in ('26CBlackLevelSubstractFilter', '12CShiftFilter'):
                    event['amount'] = self.get(reg(1), 0, '<i')[0]
                elif kind == '36CHighlightReconstructionScalarFilter':
                    event['gains'] = self.doubles(reg(1), 3).tolist()
                    event['truncation'] = self.get(reg(2), 0, '<3H')
                self.raw_events.append(event)
                self.u.mem_write(reg(8), b'\0'*16)
                finish(); return
        return super().hook(cpu, address, size, user)

    def graph59(self, black, limit, gains, scalars, reference):
        corr, params = 0x100e4000, 0x100e5000
        self.u.mem_write(corr, bytes(self.u.mem_read(CORR, 0x460)))
        self.u.mem_write(params, bytes(self.u.mem_read(PARAMS, 0x1b0)))
        self.put(corr, 0x99, '<?', False)
        self.put(params, 0xe0, '<i', 0)
        self.put(params, 0x190, '<?', False)
        self.put(params, 0x58, '<3d', *gains)
        for off, value in zip((0x18, 0x40, 0x48, 0x50), scalars):
            self.put(DESC, off, '<d', value)
        self.put(DESC, 0x234, '<2i', 32, 32)
        self.put(DESC, 0x230, '<i', 1)
        self.put(DESC, 0x1e8, '<?', True)
        self.put(DESC, 0x1ec, '<4i', 0, 0, 32, 32)
        self.put(DESC, 0x130, '<i', black)
        self.put(DESC, 0x398, '<i', limit)
        self.put(EMPTY+0x100, 0, '<i', reference)
        frozen = bytes(self.u.mem_read(DESC, 0x408))
        frozen_corr = bytes(self.u.mem_read(corr, 0x460))
        self.raw_events = []
        self.trunc_calls = 0
        self.raw_builder = True
        try:
            self.call(RAW_BUILD, (0x100e6000, SHARED_DESC, 0, params, corr, EMPTY+0x100))
        finally:
            self.raw_builder = False
        assert frozen == bytes(self.u.mem_read(DESC, 0x408))
        assert frozen_corr == bytes(self.u.mem_read(corr, 0x460))
        assert self.get(EMPTY+0x100, 0, '<i') == (reference-black,)
        return self.raw_events

    def base59(self, bits):
        self.put(DESC, 0x39c, '<i', bits)
        self.put(DESC, 0x3a0, '<2B', 0, 0)  # Ordinary Bayer, no preprocessed RGB/YUV.
        self.put(DESC, 0x25c, '<h', 0)
        rawfile, vtable = 0x100ea000, 0x100eb000
        self.u.mem_write(rawfile, b'\0'*0x400)
        self.u.mem_write(vtable, b'\0'*0x300)
        self.put(rawfile, 0, '<Q', vtable)
        self.put(vtable, 0x230, '<Q', HDR_HOOK)
        frozen = bytes(self.u.mem_read(DESC, 0x408))
        self.raw_events = []
        self.base_fixture = self.raw_builder = True
        try:
            self.call(BASE, (0x100e6000, rawfile, DESC, 0, 0, 0))
        finally:
            self.base_fixture = self.raw_builder = False
        assert frozen == bytes(self.u.mem_read(DESC, 0x408))
        return self.raw_events

    def opcode59(self):
        rawfile = 0x100ea000
        outcomes = []
        for header_present in (False, True):
            self.u.mem_write(rawfile, b'\0'*0x400)
            self.put(rawfile, 0x50, '<Q', 0x100ec000 if header_present else 0)
            self.opcode_queries = []
            self.opcode_fixture = True
            try:
                self.call(OPCODES, (rawfile,))
            finally:
                self.opcode_fixture = False
            assert self.get(0x10002000, 0, '<3Q') == (0, 0, 0)
            assert self.opcode_queries == ([{'ifd_index': 1, 'tag': 51022}] if header_present else [])
            outcomes.append({'header_present': header_present, 'queries': self.opcode_queries})
        return {'cases': outcomes, 'method': 'CRawImageFile::OpcodeLists',
                'tag_data_absent_fixture': True, 'opcode_payload_parsed': False,
                'all_raw_decoder_paths_audited': False,
                'inference': 'This named accessor queries OpcodeList3; it does not establish the handling of phone OpcodeList2.'}

    def black59(self, values, black):
        """Run the original constructor and entire CPU black-subtraction body."""
        obj, data, ip, op, filt = 0x100d5000, 0x10100000, 0x100f4000, 0x100f4010, 0x100fc000
        values = np.ascontiguousarray(values, dtype='<u2')
        height, width, channels = values.shape
        self.u.mem_write(filt-16, b'\xa5'*16+b'\0'*0x50+b'\xa5'*16)
        self.call(BLACK_CTOR, (filt, black, 0))
        frozen = bytes(self.u.mem_read(filt-16, 0x70))
        self.u.mem_write(data-16, b'\xa5'*16+values.tobytes()+b'\xa5'*16)
        self.u.mem_write(obj, b'\0'*48)
        self.put(obj, 8, '<4i', width, height, channels, width*channels)
        self.put(obj, 0x20, '<Q', data)
        self.u.mem_write(RECT, b'\0'*32)
        self.put(RECT, 8, '<?', True)
        self.put(RECT, 12, '<4i', 0, 0, width, height)
        self.put(ip, 0, '<Q', obj); self.put(op, 0, '<Q', 0)
        self.cpu_fixture = True
        try:
            self.call(BLACK_CPU, (filt, RECT, RECT, ip, op))
        finally:
            self.cpu_fixture = False
        assert self.get(0x10002000, 0, '<Q') == (obj,)
        assert frozen == bytes(self.u.mem_read(filt-16, 0x70))
        assert bytes(self.u.mem_read(data-16, 16)) == bytes(self.u.mem_read(data+values.nbytes, 16)) == b'\xa5'*16
        return np.frombuffer(bytes(self.u.mem_read(data, values.nbytes)), dtype='<u2').reshape(values.shape).copy()


def graph_tests(r):
    r.configure((1., 1.4, 1.8))
    r.process()
    r.call(TRUNC, (22,))
    packed = struct.pack('<2Q', r.u.reg_read(UC_ARM64_REG_X0), r.u.reg_read(UC_ARM64_REG_X1))
    private_fallback = struct.unpack('<3i', packed[:12])
    # Do not serialize camera-specific fallback values.
    count = fallback_count = zero_level_cases = 0
    sequences = set()
    for black, limit, permutation, scalars, reference in itertools.product(
            (0, 64, 512, 4096), (-1, 0, 1, 64, 512, 4096, 16383, 65535, 70000),
            itertools.permutations((.5, .7, 1.)),
            ((1., 1., 1., 1.), (.5, 2., .75, 1.5)), (12000, 60000)):
        events = r.graph59(black, limit, permutation, scalars, reference)
        native = next(e for e in events if e['filter'] == '36CHighlightReconstructionScalarFilter')
        source = (limit,)*3 if limit > 0 else private_fallback
        expected = tuple(max(0, min(65535, v-black)) for v in source)
        assert native['truncation'] == expected
        assert np.array_equal(native['gains'], np.asarray(permutation)/max(permutation))
        assert r.trunc_calls == (1 if limit <= 0 else 0)
        fallback_count += r.trunc_calls
        zero_level_cases += int(0 in expected)
        kinds = tuple(e['filter'] for e in events)
        sequences.add(kinds)
        black_events = [e for e in events if e['filter'] == '26CBlackLevelSubstractFilter']
        assert black_events == ([{'filter': '26CBlackLevelSubstractFilter', 'amount': black}] if black else [])
        i = kinds.index('23CBayerFastInterpolation')
        assert kinds[i+1:i+3] == ('36CHighlightReconstructionScalarFilter', '18CMulti2BayerFilter')
        assert all(kinds.index(e['filter']) < i for e in black_events)
        assert next(e for e in events if e['filter'] == 'CDemosaicFilter')['gains'] == [1., 1., 1.]
        count += 1
    base_count = 0
    for bits in (8, 10, 12, 14, 15, 16):
        events = r.base59(bits)
        shifts = [e for e in events if e['filter'] == '12CShiftFilter']
        assert shifts == ([{'filter': '12CShiftFilter', 'amount': 16-bits}] if bits < 16 else [])
        base_count += 1
    return {'cases': count, 'fallback_cases': fallback_count,
            'zero_clipping_cases_not_sent_to_pixel_reconstruction': zero_level_cases,
            'base_builder_bit_depth_cases': base_count,
            'source_clipping_minus_black_exact': True,
            'clipping_independent_of_tested_source_scalars_and_reference': True,
            'reference_decremented_by_black_exact': True,
            'normalized_process_gains_exact': True,
            'demosaic_gains_unity': True,
            'original_base_builder_shift_16_minus_bits': True,
            'graph_sequences': [list(s) for s in sorted(sequences)],
            'graph_storage_mocked': True, 'optional_hdr_metadata_empty_fixture': True,
            'noise_and_lens_services_fixed_for_bounded_branch': True,
            'pixel_graph_executed': False, 'full_source_description_constructor_executed': False}


def scale_tests(r):
    """Test uniform code-unit conversion, distinct from changing sensor basis."""
    rng = np.random.default_rng(59)
    fractions = np.vstack((rng.uniform(0, 1.2, (80, 3)),
                           np.repeat(np.linspace(0, 1.1, 13)[:, None], 3, 1),
                           np.array(list(itertools.product((0., .5, 1.), repeat=3)))))
    gains_cases = list(itertools.permutations((.5, .7, 1.)))
    interior_errors, boundary_errors, oracle_errors, wrong_errors = [], [], [], []
    boundary_mask = np.any(fractions == 1., axis=1)
    witness = None
    cases = channels = 0
    for gains, limit in itertools.product(gains_cases, (4095, 12000, 32767, 60000)):
        # These are normalized *code* values; physical clipping is not measured.
        scale = limit/65535.
        source = fractions*scale
        r.prepare(gains, (limit,)*3)
        got = r.scalar(source)
        expected = Highlight.prepare(gains, (limit,)*3).convert(source)
        oracle_errors.extend(np.abs(got-expected).ravel())
        r.prepare(gains, (65535,)*3)
        normalized = r.scalar(fractions)*scale
        difference = np.abs(got-normalized)
        interior_errors.extend(difference[~boundary_mask].ravel())
        boundary_errors.extend(difference[boundary_mask].ravel())
        if witness is None and np.max(difference) > 1e-12:
            i = int(np.argmax(np.max(difference, axis=1)))
            witness = {'gains': list(gains), 'clipping_code': limit,
                       'input_as_fraction_of_clipping': fractions[i].tolist(),
                       'scale_times_reciprocal': scale*(1/scale),
                       'source_domain_output': got[i].tolist(),
                       'normalized_domain_output_rescaled': normalized[i].tolist()}
        # Negative control: change clipping units without changing pixel units.
        wrong = r.scalar(source)
        wrong_errors.extend(np.abs(got-wrong).ravel())
        assert np.isfinite(got).all()
        cases += 1; channels += got.size
    assert max(interior_errors) < 1e-12, max(interior_errors)
    # Preserve the observed original-code threshold exception, not a tolerance
    # increase disguising a failure of exact scale invariance at the boundary.
    assert witness is not None and max(boundary_errors) > .001
    assert max(oracle_errors) < 1e-12, max(oracle_errors)
    assert max(wrong_errors) > .01
    return {'cases': cases, 'channels': channels,
            'original_scalar_cpu_executed': True,
            'away_from_exact_clipping_max_absolute_error': float(max(interior_errors)),
            'exact_clipping_boundary_max_absolute_difference': float(max(boundary_errors)),
            'exact_clipping_boundary_witness': witness,
            'independent_equations_max_absolute_error': float(max(oracle_errors)),
            'mismatched_units_negative_control_max_absolute_difference': float(max(wrong_errors)),
            'precision': 'double scalar; RGB16 rounding and full graph not included',
            'camera_basis_equivalence_claimed': False,
            'spatial_gainmap_equivalence_claimed': False}


def black_tests(r):
    rng = np.random.default_rng(5901)
    cases = channels = 0
    for black, channel_count in itertools.product((0, 1, 64, 512, 4096, 65535), (1, 3)):
        boundary = (0, max(0, black-1), black, min(65535, black+1), 65535)
        values = np.r_[boundary, rng.integers(0, 65536, 257)].astype('<u2')
        values = np.tile(values[:, None], (1, channel_count)).reshape(2, 131, channel_count)
        got = r.black59(values, black)
        expected = np.maximum(values.astype(np.int64)-black, 0).astype('<u2')
        assert np.array_equal(got, expected)
        cases += 1; channels += got.size
    return {'cases': cases, 'channels': channels, 'max_absolute_difference': 0,
            'original_cpu_filter_executed': True, 'inplace_buffer_ownership_fixture': True,
            'operation': 'max(sample_code - black_code, 0); no range normalization'}


def boundary_cpu_tests(r):
    """Recheck the existing C port at clipping and its immediate neighbours."""
    cases = channels = 0
    with tempfile.TemporaryDirectory(prefix='hb59-boundary-') as tmp:
        portable = Portable(tmp)
        for gains, limit in itertools.product(itertools.permutations((.5, .7, 1.)),
                                               (32767, 60000, 65535)):
            levels = (limit,)*3
            pixels = []
            for ch, offset in itertools.product(range(3), (-1, 0, 1)):
                p = [limit//2]*3
                p[ch] = min(65535, limit+offset)
                pixels.append(p)
            pixels = np.asarray(pixels, dtype='<u2')
            r.prepare(gains, levels)
            assert portable.prepare(gains, levels) == 0
            native = r.cpu16(pixels)
            port = portable.render(pixels)
            assert np.array_equal(native, port), (gains, limit, native.tolist(), port.tolist())
            cases += 1; channels += native.size
    return {'cases': cases, 'channels': channels, 'max_absolute_difference': 0,
            'original_cpu_rgb16_vs_existing_port_exact': True,
            'port_changed': False, 'boundary_sensitive_scalar_behavior_not_patched': True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk', type=Path, required=True)
    p.add_argument('--safe-receipt', type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.apk.read_bytes()).digest()
    elf, profile = load_private(a.apk)
    r = RawDomainRunner(elf, profile)
    graph = graph_tests(r)
    print(f"Native graph: {graph['cases']} RAW and {graph['base_builder_bit_depth_cases']} base cases passed", flush=True)
    scales = scale_tests(r)
    black = black_tests(r)
    boundary_cpu = boundary_cpu_tests(r)
    opcodes = r.opcode59()
    assert hashlib.sha256(a.apk.read_bytes()).digest() == before
    for address, frozen in r.frozen_profile:
        assert frozen == bytes(r.u.mem_read(address, len(frozen)))
    receipt = {'schema': 'hasselblad-stage59-raw-domain-v1', 'status': 'PASS_BOUNDED_NATIVE_AUDIT',
               'native_graph': graph, 'uniform_code_domain': scales,
               'black_subtraction': black, 'opcode_accessor': opcodes,
               'boundary_cpu_regression': boundary_cpu,
               'source_apk_modified': False, 'private_tables_exported': False,
               'scene_fitted_parameters': 0, 'capture_renderer_changed': False,
               'new_device_apk_built': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'status': receipt['status'], 'scalar_cases': scales['cases'],
                      'max_rescaling_error_away_from_boundary': scales['away_from_exact_clipping_max_absolute_error']}), flush=True)


if __name__ == '__main__':
    main()
