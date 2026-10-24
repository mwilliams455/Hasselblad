#!/usr/bin/env python3
"""Reconcile supplied Stage58 counters and inspect DNG opcode-list metadata.

No private image, hash, matrix or gain payload is written to the receipt.
Counter agreement is explicitly not a device pixel comparison.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import tifffile

COUNTERS = {
    'raw_decoded_sites': 'decoded_sites',
    'raw_sites_below_black': 'raw_below_black',
    'raw_sites_at_or_above_whitelevel': 'raw_at_or_above_white',
    'range_lower_clipped_sites': 'range_lower_clipped',
    'range_upper_clipped_sites': 'range_upper_clipped',
    'gainmap_upper_clip_events': 'gain_clip_events',
    'gainmap_upper_clipped_sites': 'gain_clipped_sites',
    'gainmap_clipped_sites_below_whitelevel': 'gain_clipped_below_white',
    'diagnostic_unclamped_negative_channels': 'unclamped_negative_channels',
    'diagnostic_unclamped_over_unity_channels': 'unclamped_over_unity_channels',
    'dng_preparation_changed_rgb16_channels': 'changed_prepared_channels'}


def inspect_lists(path):
    with tifffile.TiffFile(path) as f:
        pages = [p for p in f.pages if int(p.photometric) == 32803]
        assert len(pages) == 1, 'This saved-DNG audit expects one Bayer IFD'
        result = {}
        for tag_id in (51008, 51009, 51022):
            tag = pages[0].tags.get(tag_id)
            entry = {'present': tag is not None}
            if tag is not None:
                data = bytes(tag.value)
                assert len(data) >= 4
                count = struct.unpack_from('>I', data)[0]
                offset, ids = 4, []
                assert count <= (len(data)-4)//16
                for _ in range(count):
                    assert offset+16 <= len(data)
                    opcode, version, flags, size = struct.unpack_from('>4I', data, offset)
                    offset += 16+size
                    assert offset <= len(data)
                    ids.append(opcode)
                assert offset == len(data)
                entry.update(opcode_count=count, opcode_ids=ids)
            result[str(tag_id)] = entry
        return result


def main():
    p = argparse.ArgumentParser()
    for name in ('dng', 'device-report', 'host-report', 'safe-receipt'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = hashlib.sha256(a.dng.read_bytes()).digest()
    device, host = (json.loads(path.read_text()) for path in (a.device_report, a.host_report))
    for device_key, host_key in COUNTERS.items():
        assert device[device_key] == host['sampled_row_counters'][host_key], device_key
    assert device['displayed_preview'] == 'automatic_dng_preparation'
    assert device['displayed_lut_temperature'] == host['selected_lut_temperature']
    assert device['displayed_native_finishing'] and not device['displayed_highlight_reconstruction']
    assert device['dng_preparation_unequal_black_levels'] == host['unequal_black_levels']
    assert not device['host_reference_compared']
    opcodes = inspect_lists(a.dng)
    assert opcodes['51009']['opcode_ids'] == [9]*device['gainmap_count']
    assert not opcodes['51008']['present'] and not opcodes['51022']['present']
    assert hashlib.sha256(a.dng.read_bytes()).digest() == before
    receipt = {
        'schema': 'hasselblad-stage59-device-reconciliation-v1',
        'status': 'PASS_STAGE58_COUNTERS_AND_SELECTION',
        'matching_counter_fields': len(COUNTERS),
        'counter_domain': device['raw_audit_scope'],
        'displayed_preview': device['displayed_preview'],
        'displayed_lut_temperature': device['displayed_lut_temperature'],
        'device_pixel_reference_compared': False,
        'dng_opcode_lists': opcodes,
        'dng_inspection_scope': 'Bayer IFD opcode IDs only; no native DNG decode',
        'source_dng_modified': False,
        'device_timing_single_run_ms': {'raw_preparation': device['raw_preparation_milliseconds'],
                                      'total': device['total_milliseconds']},
        'timing_is_benchmark': False,
        'physical_camera_colour_match_validated': False,
        'scene_fitted_parameters': 0}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'status': receipt['status'], 'matching_counters': len(COUNTERS)}))


if __name__ == '__main__':
    main()
