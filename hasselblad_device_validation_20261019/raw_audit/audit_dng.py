#!/usr/bin/env python3
"""Read-only replay of the original Native1 DNG/JPEG audit.

This small bounded TIFF reader deliberately supports the layout of the uploaded
development capture. It does not demosaic, render, edit or rewrite either input.
Its interpretation is specific to the two original files, whose hashes are
required. Use pair_audit/audit_metadata.py for basic metadata on a later capture.
Requires Python 3, NumPy and Pillow.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

TYPES = {1: ('BYTE', 'B', 1), 2: ('ASCII', None, 1),
         3: ('SHORT', 'H', 2), 4: ('LONG', 'I', 4),
         5: ('RATIONAL', 'II', 8), 6: ('SBYTE', 'b', 1),
         7: ('UNDEFINED', 'B', 1), 8: ('SSHORT', 'h', 2),
         9: ('SLONG', 'i', 4), 10: ('SRATIONAL', 'ii', 8),
         11: ('FLOAT', 'f', 4), 12: ('DOUBLE', 'd', 8),
         13: ('IFD', 'I', 4)}
NAMES = {
    254: 'NewSubfileType', 256: 'ImageWidth', 257: 'ImageLength',
    258: 'BitsPerSample', 259: 'Compression', 262: 'PhotometricInterpretation',
    270: 'ImageDescription', 271: 'Make', 272: 'Model', 273: 'StripOffsets',
    274: 'Orientation', 277: 'SamplesPerPixel', 278: 'RowsPerStrip',
    279: 'StripByteCounts', 282: 'XResolution', 283: 'YResolution',
    284: 'PlanarConfiguration', 296: 'ResolutionUnit', 305: 'Software',
    306: 'DateTime', 330: 'SubIFDs', 33421: 'CFARepeatPatternDim',
    33422: 'CFAPattern', 33434: 'ExposureTime', 33437: 'FNumber',
    34665: 'ExifIFD', 34853: 'GPSIFD', 34855: 'ISOSpeedRatings',
    36864: 'ExifVersion', 37386: 'FocalLength', 50706: 'DNGVersion',
    50707: 'DNGBackwardVersion', 50708: 'UniqueCameraModel',
    50710: 'CFAPlaneColor', 50711: 'CFALayout', 50712: 'LinearizationTable',
    50713: 'BlackLevelRepeatDim', 50714: 'BlackLevel',
    50715: 'BlackLevelDeltaH', 50716: 'BlackLevelDeltaV', 50717: 'WhiteLevel',
    50718: 'DefaultScale', 50719: 'DefaultCropOrigin', 50720: 'DefaultCropSize',
    50721: 'ColorMatrix1', 50722: 'ColorMatrix2',
    50723: 'CameraCalibration1', 50724: 'CameraCalibration2',
    50727: 'AnalogBalance', 50728: 'AsShotNeutral', 50730: 'BaselineExposure',
    50778: 'CalibrationIlluminant1', 50779: 'CalibrationIlluminant2',
    50829: 'ActiveArea', 50964: 'ForwardMatrix1', 50965: 'ForwardMatrix2',
    51008: 'OpcodeList1', 51009: 'OpcodeList2', 51022: 'OpcodeList3',
    51041: 'NoiseProfile',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


class TIFF:
    def __init__(self, data):
        self.data = data
        assert data[:2] in (b'II', b'MM'), 'TIFF byte order required'
        self.order = '<' if data[:2] == b'II' else '>'
        assert self.unpack('H', 2)[0] == 42, 'Only classic TIFF is supported'
        queue = [self.unpack('I', 4)[0]]
        self.ifds = []
        seen = set()
        while queue:
            offset = queue.pop(0)
            if not offset or offset in seen:
                continue
            seen.add(offset)
            count = self.unpack('H', offset)[0]
            self.read(offset + 2, count * 12 + 4)
            tags = {}
            for i in range(count):
                loc = offset + 2 + 12 * i
                tag, typ, n = self.unpack('HHI', loc)
                assert typ in TYPES, (tag, typ)
                type_name, fmt, size = TYPES[typ]
                size *= n
                ptr = loc + 8 if size <= 4 else self.unpack('I', loc + 8)[0]
                raw = self.read(ptr, size)
                if typ == 2:
                    value = raw.rstrip(b'\0').decode('utf-8', 'replace')
                elif size > 512 and typ == 7:
                    value = {'bytes': size, 'sha256': digest(raw)}
                else:
                    value = list(struct.unpack(self.order + fmt * n, raw))
                    if typ in (5, 10):
                        value = [value[j:j+2] for j in range(0, len(value), 2)]
                tags[tag] = {'tag': tag, 'name': NAMES.get(tag, str(tag)),
                             'type': type_name, 'type_id': typ, 'count': n,
                             'data_offset': ptr, 'byte_length': size, 'value': value}
                if tag in (330, 34665, 34853):
                    assert typ in (4, 13)
                    queue.extend(value)
            next_ifd = self.unpack('I', offset + 2 + count * 12)[0]
            queue.append(next_ifd)
            self.ifds.append({'offset': offset, 'entry_count': count,
                              'next_ifd': next_ifd, 'tags': tags})

    def read(self, offset, size):
        assert 0 <= offset <= len(self.data) and 0 <= size <= len(self.data) - offset
        return self.data[offset:offset+size]

    def unpack(self, fmt, offset):
        return struct.unpack(self.order + fmt, self.read(offset, struct.calcsize(self.order + fmt)))


def numeric(tag):
    if tag['type_id'] in (5, 10):
        assert all(denominator != 0 for _, denominator in tag['value'])
        return [numerator / denominator for numerator, denominator in tag['value']]
    return tag['value']


def stats(a, black, white):
    probabilities = [0, .01, .1, 1, 5, 25, 50, 75, 95, 99, 99.9, 99.99, 100]
    counts = {
        'zero': int(np.count_nonzero(a == 0)),
        'below_black': int(np.count_nonzero(a < black)),
        'equal_black': int(np.count_nonzero(a == black)),
        'at_or_above_white': int(np.count_nonzero(a >= white)),
        'above_white': int(np.count_nonzero(a > white)),
    }
    return {
        'sample_count': int(a.size), 'minimum': int(a.min()), 'maximum': int(a.max()),
        'mean': float(a.mean()), 'standard_deviation': float(a.std()),
        'percentiles': {str(p): float(v) for p, v in zip(probabilities, np.percentile(a, probabilities))},
        'counts': counts, 'percent_of_samples': {k: 100 * v / a.size for k, v in counts.items()},
        'declared_black': black, 'declared_white': white,
        'mean_black_subtracted': float(a.mean() - black),
        'mean_normalized_to_declared_range': float((a.mean() - black) / (white - black)),
    }


def gain_maps(data):
    assert len(data) >= 4
    count = struct.unpack_from('>I', data, 0)[0]
    offset = 4
    result = []
    for i in range(count):
        assert offset + 16 <= len(data)
        opcode, version, flags, length = struct.unpack_from('>IIII', data, offset)
        offset += 16
        assert offset + length <= len(data)
        payload = data[offset:offset+length]
        entry = {'index': i, 'opcode_id': opcode, 'minimum_version_hex': f'0x{version:08x}',
                 'flags': flags, 'payload_bytes': length, 'payload_sha256': digest(payload)}
        if opcode == 9:
            assert length >= 76
            area = struct.unpack_from('>8I', payload, 0)
            rows, cols = struct.unpack_from('>2I', payload, 32)
            spacing_v, spacing_h, origin_v, origin_h = struct.unpack_from('>4d', payload, 40)
            planes = struct.unpack_from('>I', payload, 72)[0]
            assert length == 76 + rows * cols * planes * 4
            gains = np.frombuffer(payload, '>f4', count=rows*cols*planes, offset=76).reshape(rows, cols, planes)
            entry.update({
                'name': 'GainMap',
                'area': dict(zip(('top', 'left', 'bottom', 'right', 'first_plane', 'planes', 'row_pitch', 'column_pitch'), area)),
                'map_rows': rows, 'map_columns': cols, 'map_planes': planes,
                'spacing_vertical': spacing_v, 'spacing_horizontal': spacing_h,
                'origin_vertical': origin_v, 'origin_horizontal': origin_h,
                'all_finite': bool(np.isfinite(gains).all()), 'all_positive': bool((gains > 0).all()),
                'minimum': float(gains.min()), 'maximum': float(gains.max()), 'mean': float(gains.mean()),
                'center': gains[rows//2, cols//2].tolist(),
                'corners_top_left_top_right_bottom_left_bottom_right': gains[[0, 0, -1, -1], [0, -1, 0, -1]].tolist(),
            })
        result.append(entry)
        offset += length
    assert offset == len(data)
    return {'opcode_count': count, 'parsed_bytes': offset, 'declared_bytes': len(data),
            'complete': True, 'opcodes': result,
            'interpretation': 'OpcodeList2 CFA lens-shading gain maps; separate from Ultra HDR JPEG gain maps. No gains were applied by this audit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dng', required=True, type=Path)
    parser.add_argument('--jpeg', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = args.dng.read_bytes()
    jpeg_data = args.jpeg.read_bytes()
    expected_dng = '5d17b2119c7eefa01823b66bab5ee4d4ad3d5685183460e94d39ac50e11c0fb5'
    expected_jpeg = '0f6e462d2b65f58cc2c9a42e187782e609c5df07588fdb81373bbe1409d62ea1'
    if digest(data) != expected_dng or digest(jpeg_data) != expected_jpeg:
        parser.error('This replay requires the original Native1 DNG/JPEG pair; its interpretation does not apply to another capture.')
    tiff = TIFF(data)
    raw_ifds = [i for i in tiff.ifds if i['tags'].get(262, {}).get('value') == [32803]]
    assert len(raw_ifds) == 1
    ifd = raw_ifds[0]
    tags = ifd['tags']
    value = lambda n: numeric(tags[n])
    width, height = value(256)[0], value(257)[0]
    assert value(258) == [16] and value(259) == [1] and value(277) == [1]
    offsets, lengths = value(273), value(279)
    assert len(offsets) == len(lengths)
    assert sum(lengths) == width * height * 2
    raw_bytes = b''.join(tiff.read(o, n) for o, n in zip(offsets, lengths))
    raw = np.frombuffer(raw_bytes, dtype=tiff.order+'u2').reshape(height, width)
    assert value(33421) == [2, 2] and value(33422) == [0, 1, 1, 2], 'This audit expects the supplied RGGB layout'
    assert value(50713) == [2, 2] and len(value(50714)) == 4
    blacks, whites = value(50714), value(50717)
    assert len(whites) == 1 and len(set(blacks)) == 1
    black, white = blacks[0], whites[0]
    channel_arrays = [('R', 0, 0), ('G_on_R_row', 0, 1), ('G_on_B_row', 1, 0), ('B', 1, 1)]
    channels = {name: {'row_parity': y, 'column_parity': x,
                       **stats(raw[y::2, x::2], blacks[2*y+x], white)} for name, y, x in channel_arrays}
    matrices = {}
    for tag_id in (50721, 50722, 50723, 50724, 50964, 50965):
        if tag_id in tags:
            matrix = np.array(value(tag_id), dtype=np.float64).reshape(3, 3)
            matrices[NAMES[tag_id]] = {'rational_pairs_row_major': tags[tag_id]['value'],
                                     'matrix': matrix.tolist(), 'determinant': float(np.linalg.det(matrix)),
                                     'condition_number_2norm': float(np.linalg.cond(matrix))}
    neutral = value(50728)
    with Image.open(io.BytesIO(jpeg_data)) as image:
        jpeg = {'filename': args.jpeg.name, 'bytes': len(jpeg_data), 'sha256': digest(jpeg_data),
                'width': image.width, 'height': image.height, 'mode': image.mode,
                'exif_entry_count': len(image.getexif())}
        profile_data = image.info.get('icc_profile')
        if profile_data:
            profile = ImageCms.ImageCmsProfile(io.BytesIO(profile_data))
            jpeg['icc_profile'] = {'bytes': len(profile_data), 'sha256': digest(profile_data),
                                   'description': ImageCms.getProfileDescription(profile).strip()}
    crop_ids = (50718, 50719, 50720)
    report = {
        'audit_method': 'Bounded classic-TIFF metadata parsing and direct NumPy decoding of the declared uncompressed CFA strip. No demosaicing, colour conversion, gain-map application or image rewriting.',
        'dng': {'filename': args.dng.name, 'bytes': len(data), 'sha256': digest(data),
                'byte_order': 'little-endian' if tiff.order == '<' else 'big-endian',
                'ifd_count': len(tiff.ifds), 'raw_ifd_offset': ifd['offset'],
                'width': width, 'height': height, 'sample_count': int(raw.size),
                'stored_bits_per_sample': 16, 'compression': 'none',
                'cfa': 'RGGB', 'cfa_repeat_dimensions': [2, 2],
                'orientation': value(274)[0], 'active_area_top_left_bottom_right': value(50829),
                'explicit_crop_tags': {NAMES[t]: value(t) for t in crop_ids if t in tags},
                'absent_crop_tags': [NAMES[t] for t in crop_ids if t not in tags],
                'black_repeat_dimensions': value(50713), 'black_levels': blacks,
                'white_level': white, 'white_level_tiff_type': tags[50717]['type'],
                'declared_signal_normalization': f'(sample - {black}) / ({white} - {black}) before optional clipping and subsequent processing',
                'as_shot_neutral': neutral,
                'reciprocal_neutral_relative_multipliers': [neutral[1] / v for v in neutral],
                'reciprocal_neutral_scope': 'Arithmetic reciprocals normalized to green, not a proved mapping to the recovered Hasselblad Q12 recalibration inputs or a measured phone colour calibration.',
                'calibration_illuminants': [{'tag': NAMES[t], 'value': value(t)[0],
                                             'name': {21: 'D65', 17: 'Standard light A'}.get(value(t)[0], 'other')} for t in (50778, 50779)],
                'exposure_time_seconds': value(33434)[0], 'f_number': value(33437)[0],
                'iso': value(34855)[0], 'focal_length_mm': value(37386)[0],
                'make': tags[271]['value'], 'model': tags[272]['value'],
                'capture_time_tag': tags[306]['value'],
                'software_tag': tags[305]['value'],
                'image_description': tags[270]['value'],
                'matrices': matrices, 'noise_profile': value(51041)},
        'raw_integrity': {
            'strip_offsets': offsets, 'strip_byte_counts': lengths,
            'expected_payload_bytes': width * height * 2, 'actual_payload_bytes': len(raw_bytes),
            'payload_sha256': digest(raw_bytes), 'all_strips_within_file': True,
            'strip_payload_exactly_matches_dimensions': True,
            'highest_set_bit_mask': hex(int(np.bitwise_or.reduce(raw.reshape(-1)))) ,
            'upper_six_bits_always_zero': bool((raw < 1024).all()),
            'distinct_sample_values': int(np.unique(raw).size),
            'bit_one_counts_0_through_15': [int(np.count_nonzero(raw & (1 << bit))) for bit in range(16)],
            'constant_rows': int(np.count_nonzero(raw.max(axis=1) == raw.min(axis=1))),
            'constant_columns': int(np.count_nonzero(raw.max(axis=0) == raw.min(axis=0))),
            'identical_adjacent_same_parity_rows': int(np.count_nonzero(np.all(raw[2:] == raw[:-2], axis=1))),
            'identical_adjacent_same_parity_columns': int(np.count_nonzero(np.all(raw[:, 2:] == raw[:, :-2], axis=0))),
            'observed_bit_scope': 'The stored codes fit ten bits and the file declares white at 1023. This does not establish the physical sensor ADC depth, upstream ISP operations or scene dynamic range.',
        },
        'raw_statistics': {'all_samples': stats(raw, black, white), 'cfa_channels': channels,
                           'green_mean_difference_codes': channels['G_on_R_row']['mean'] - channels['G_on_B_row']['mean'],
                           'scope': 'Statistics of stored mosaic codes before lens shading and white balance. Scene-dependent channel means are not estimates of white-balance accuracy.'},
        'opcode_list_2': gain_maps(tiff.read(tags[51009]['data_offset'], tags[51009]['byte_length'])),
        'jpeg': jpeg,
        'metadata_ifds': [{**i, 'tags': list(i['tags'].values())} for i in tiff.ifds],
        'interpretation': {
            'established': [
                'The supplied DNG contains a complete nonconstant 4096 by 3072 RGGB raw payload with declared black/white levels and usable per-capture colour metadata.',
                'The file capture description identifies one frame, camera ID 2 and version 0.1-hb-native1(27174).',
                'Both colour-matrix illuminants, calibration and forward matrices, as-shot neutral and four finite positive lens-shading grids are available as phone-side metadata inputs.',
                'The observed samples show no out-of-range-above-white values, no zero samples and no constant or duplicated same-parity rows or columns.'
            ],
            'not_established': [
                'A measured phone-to-Hasselblad sensor colour transform, correct HNCS pixel contract, or visual equivalence to an X2D II.',
                'Accuracy of the embedded matrices, neutral or lens-shading maps under this illumination, or their validity across other scenes, cameras or RAW modes.',
                'Physical sensor ADC precision, full-well capacity, scene dynamic range, absence of all upstream ISP processing, or the sensor binning/remosaic mechanism.',
                'A mapping of phone white-balance metadata to the recovered two-scalar Hasselblad Q12 recalibration primitive.',
                'Original full-size JPEG provenance or exact same-capture pairing from JPEG metadata: the uploaded JPEG has no EXIF.'
            ],
            'white_level_type_check': {
                'result': 'pass' if tags[50717]['type_id'] in (3, 4) else 'fail',
                'actual_type': tags[50717]['type'],
                'actual_value': tags[50717]['value'],
                'allowed_types': ['SHORT', 'LONG'],
                'reference': 'Adobe DNG Specification 1.7.1.0, printed page 29, WhiteLevel tag 50717',
                'reference_url': 'https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf',
                'scope': 'This is a concrete metadata type mismatch with possible strict-reader interoperability consequences. The stored raw array is readable and intact under this audit. It does not establish the cause of any upload/preprocessor error; original attachments were not changed.'
            },
            'software_metadata_finding': 'The Software tag says PhotonCamera v-1, whereas ImageDescription identifies version 0.1-hb-native1(27174); this is inconsistent writer-version metadata.'
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'dng_sha256': digest(data), 'raw_shape': list(raw.shape),
                      'raw_minimum': int(raw.min()), 'raw_maximum': int(raw.max()),
                      'clipped_samples': report['raw_statistics']['all_samples']['counts']['at_or_above_white'],
                      'clipped_percent': report['raw_statistics']['all_samples']['percent_of_samples']['at_or_above_white'],
                      'gain_maps': report['opcode_list_2']['opcode_count']}, indent=2))


if __name__ == '__main__':
    main()
