#!/usr/bin/env python3
"""Stage62 boundary study: observe original CPU red/blue helper calls.

This is NOT an independent red/blue helper implementation and is NOT an APK.
Original Phocus APK and optional photograph stay local. Only aggregate counts
can be placed in --safe-receipt; pointer/pixel probes stay in --work.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'phocus_gradient_stage61'))
from audit_integration61 import (SubstitutionRunner, PortableMaps, load_private,
                                  synthetic_patterns, pad_bayer, prepare_private_dng)
from helper_trace62 import BLUE, RED_BLUE, LABELS, HelperTrace62
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30


class HelperBoundaryRunner(SubstitutionRunner):
    def __init__(self, elf, profile, portable, limit):
        entries = {elf.func[symbol][0]: label for symbol, label in LABELS.items()}
        if len(entries) != 2:
            raise AssertionError('Unexpected native helper entry alias')
        self.helper_trace62 = HelperTrace62(entries, limit)
        super().__init__(elf, profile, portable)

    def hook(self, cpu, address, size, user):
        if self.gradient_active and not self.replace:
            self.helper_trace62.observe(
                address, lambda i: cpu.reg_read(UC_ARM64_REG_X0+i),
                lambda: cpu.reg_read(UC_ARM64_REG_X30),
                lambda ptr, n: cpu.mem_read(ptr, n))
        return super().hook(cpu, address, size, user)

    def compare(self, mosaic, label):
        self.helper_trace62.start_fixture(label)
        result = super().compare(mosaic, label)
        self.helper_trace62.end_fixture()
        return result


def digest(path):
    # Local immutability check only. No user-file digest in public evidence.
    return hashlib.sha256(path.read_bytes()).digest()


def private_write(path, payload):
    # Creation fails if a file with this name already exists. Do not overwrite
    # local private captures by accident, and never put their bytes in git.
    data = (json.dumps(payload, separators=(',', ':')) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk', type=Path, required=True, help='Locally supplied private Phocus APK')
    p.add_argument('--dng', type=Path, help='Optional existing private DNG fixture')
    p.add_argument('--work', type=Path, required=True, help='Scratch folder OUTSIDE repo')
    p.add_argument('--safe-receipt', type=Path, required=True)
    p.add_argument('--sanitize', action='store_true')
    p.add_argument('--private-traces', action='store_true',
                   help='Store private RAW samples/pointers exclusively in --work')
    p.add_argument('--sample-limit', type=int, default=16,
                   help='Private samples per helper per fixture (default 16)')
    a = p.parse_args()
    assert __debug__, 'Run without -O; assertions are validation gates'
    work = a.work.resolve()
    if work == REPO or REPO in work.parents:
        p.error('--work must be outside git repository (private payload protection)')
    if a.sample_limit < 0 or a.sample_limit > 256:
        p.error('--sample-limit must be 0..256')
    work.mkdir(parents=True, exist_ok=True)
    paths = [a.apk] + ([a.dng] if a.dng else [])
    frozen = [digest(path) for path in paths]
    portable = PortableMaps(work, sanitize=a.sanitize)
    r = HelperBoundaryRunner(*load_private(a.apk), portable, a.sample_limit)
    r.setup_graph()

    synthetic, saved = [], []
    for name, mosaic in synthetic_patterns():
        synthetic.append(r.compare(pad_bayer(mosaic, 32), name+'/highlight_bypass'))
        corrected = r.black59(mosaic[..., None], 512)[..., 0]
        fast = r.fast(pad_bayer(corrected, 36))
        r.prepare((.5, .7, 1.), (65023,)*3)
        highlighted = r.cpu16(fast.reshape(-1, 3)).reshape(fast.shape)
        synthetic.append(r.compare(r.remosaic(highlighted), name+'/highlight_bayer_chain'))
        print(json.dumps({'fixture': name, 'stage61_substitution': 'PASS_EXACT'}), flush=True)
    if a.dng:
        mosaic, gains, maps = prepare_private_dng(a.dng)
        h, w = mosaic.shape
        for number, (gy, gx) in enumerate(((1, 1), (1, 3), (3, 1), (3, 3)), 1):
            top, left = (gy*h//4-16)//2*2, (gx*w//4-16)//2*2
            patch = mosaic[top-36:top+68, left-36:left+68]
            assert patch.shape == (104, 104)
            saved.append(r.compare(patch[4:-4, 4:-4],
                                   'fixed_grid_'+str(number)+'/highlight_bypass'))
            fast = r.fast(patch)
            r.prepare(gains, (65535,)*3)
            highlighted = r.cpu16(fast.reshape(-1, 3)).reshape(fast.shape)
            saved.append(r.compare(r.remosaic(highlighted),
                                   'fixed_grid_'+str(number)+'/highlight_bayer_chain'))
            print(json.dumps({'fixed_grid_tile': number,
                              'stage61_substitution': 'PASS_EXACT'}), flush=True)

    r.check_guards()
    assert all(r.replacements.values()) and len(r.replacements) == 7
    for ptr, frozen_bytes in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen_bytes))) == frozen_bytes
    assert [digest(path) for path in paths] == frozen
    summary = r.helper_trace62.public_summary()
    if a.private_traces:
        private_path = work / 'STAGE62_LOCAL_HELPER_TRACES.private.json'
        private_write(private_path, r.helper_trace62.private_payload())
    called = summary['native_entry_counts']
    returned = summary['native_return_counts']
    helper_observed = all(called.get(name, 0) > 0 for name in LABELS.values())
    helper_returned = all(called.get(name, 0) == returned.get(name, 0)
                          for name in LABELS.values())
    assert helper_returned and summary['all_helper_calls_returned']

    report = {
        'schema': 'hasselblad-stage62-native-helper-boundary-probe-v1',
        'status': ('OBSERVED_BOTH_NATIVE_HELPER_BOUNDARIES' if helper_observed
                   else 'INCOMPLETE_HELPER_CALL_COVERAGE'),
        'observations_only_no_stage62_interpolation_substitution': True,
        'verified_independent_stage61_kernels': 7,
        'stage61_synthetic_rgb16_exact_channels': sum(x['exact_rgb16_channels'] for x in synthetic),
        'stage61_private_dng_rgb16_exact_channels': sum(x['exact_rgb16_channels'] for x in saved),
        'stage61_substitution_differences': 0,
        'stage62_native_helper_trace': summary,
        'native_helpers_observed': helper_observed,
        'all_native_helper_calls_returned': helper_returned,
        'pointer_and_return_register_interpretation': 'HYPOTHESIS_REQUIRES_NATIVE_BINARY_VERIFICATION',
        'independent_red_blue_helper_implementations': 0,
        'new_native_equivalence_claim': False,
        'private_traces_exported_to_public_receipt': False,
        'saved_dng_included': bool(a.dng),
        'original_apk_modified': False,
        'original_dng_modified': False,
        'normal_capture_renderer_changed': False,
        'device_execution_compared': False,
        'complete_demosaic_port': False,
        'full_phocus_equivalence': False,
    }
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'stage62_probe_status': report['status'],
                      'independent_stage62_helpers': 0,
                      'device_apk_changed': False}), flush=True)


if __name__ == '__main__':
    main()
