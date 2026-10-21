#!/usr/bin/env python3
"""Compare original Camera2 color metadata with its hash-bound exported DNG.

Reports differences rather than substituting export values into the original
model. A match establishes metadata transport consistency, not physical sensor
calibration. Capture-derived values are written only to the private output.
"""
import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path

from capture_binding import bind_capture, decode_bound_dng


def main():
    p = argparse.ArgumentParser()
    for name in ['capture', 'dng', 'private-report', 'public-report']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    capture_bytes = a.capture.read_bytes()
    j = json.loads(capture_bytes)
    binding = bind_capture(j, 'dynamic')
    decode_bound_dng(a.dng, j, binding)  # Existing strict identity/layout checks.
    here = Path(__file__).resolve().parent
    reader = here.parents[1] / 'hasselblad_device_validation_20261019/raw_audit/audit_dng.py'
    spec = importlib.util.spec_from_file_location('metadata_tiff', reader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tiff = module.TIFF(a.dng.read_bytes())
    tags = next(i['tags'] for i in tiff.ifds if i['tags'].get(262, {}).get('value') == [32803])
    chars = binding['original_characteristics']
    original = binding['original_sensor_metadata']
    pairs = [(50721, 'colorTransform1'), (50722, 'colorTransform2'),
             (50723, 'calibrationTransform1'), (50724, 'calibrationTransform2'),
             (50964, 'forwardMatrix1'), (50965, 'forwardMatrix2'),
             (50778, 'referenceIlluminant1'), (50779, 'referenceIlluminant2'),
             (50728, 'neutralColorPoint')]
    checks = []
    for tag_id, key in pairs:
        value = (original if key == 'neutralColorPoint' else chars)['android.sensor.' + key]
        expected = [Fraction(x['numerator'], x['denominator']) for x in value] if isinstance(value, list) else [Fraction(value)]
        tag = tags.get(tag_id)
        actual = None if tag is None else ([Fraction(*x) for x in tag['value']] if tag['type_id'] in (5, 10) else [Fraction(x) for x in tag['value']])
        checks.append({'tag': tag_id, 'name': key, 'coefficient_count': len(expected),
                       'exact_match': actual == expected,
                       'original': [str(x) for x in expected],
                       'dng': None if actual is None else [str(x) for x in actual]})
    report = {'status': 'MATCH' if all(x['exact_match'] for x in checks) else 'DIFFERENCE',
              'tags_compared': len(checks), 'coefficients_compared': sum(x['coefficient_count'] for x in checks),
              'matching_tags': sum(x['exact_match'] for x in checks),
              'frame_and_dng_binding_passed': True, 'physical_calibration_proven': False,
              'renderer_changed': False,
              'source_sha256': {str(f.relative_to(here.parents[1])): hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in [Path(__file__), here / 'capture_binding.py', reader]}}
    private = {'summary': report, 'capture_sha256': hashlib.sha256(capture_bytes).hexdigest(),
               'dng_sha256': j['dng']['sha256'], 'sensor_timestamp_ns': binding['sensor_timestamp_ns'],
               'frame_number': binding['frame_number'], 'checks': checks,
               'scope': 'Exact metadata transport comparison only. Differences may be deliberate export overrides; never replace original metadata silently.'}
    a.private_report.write_text(json.dumps(private, indent=2) + '\n')
    a.public_report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
