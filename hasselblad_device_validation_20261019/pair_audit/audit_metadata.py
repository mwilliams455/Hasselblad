#!/usr/bin/env python3
"""Read-only TIFF/DNG and JPEG EXIF inventory; no pixel decoding or mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from PIL import ExifTags, Image, TiffTags

TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1,
              8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}
NAMES = dict(TiffTags.TAGS)
NAMES.update(ExifTags.TAGS)
NAMES.update({50706: 'DNGVersion', 50707: 'DNGBackwardVersion',
              50708: 'UniqueCameraModel', 50713: 'BlackLevelRepeatDim',
              50714: 'BlackLevel', 50717: 'WhiteLevel',
              50721: 'ColorMatrix1', 50722: 'ColorMatrix2',
              50723: 'CameraCalibration1', 50724: 'CameraCalibration2',
              50727: 'AnalogBalance', 50728: 'AsShotNeutral',
              50778: 'CalibrationIlluminant1', 50779: 'CalibrationIlluminant2',
              50829: 'ActiveArea', 50964: 'ForwardMatrix1', 50965: 'ForwardMatrix2',
              51009: 'OpcodeList2', 51041: 'NoiseProfile'})


def scalar_json(value):
    if isinstance(value, dict):
        return {str(k): scalar_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scalar_json(v) for v in value]
    if isinstance(value, bytes):
        try:
            return value.rstrip(b'\0').decode('utf-8')
        except UnicodeDecodeError:
            return {'bytes': len(value), 'hex': value.hex()}
    if hasattr(value, 'numerator') and hasattr(value, 'denominator') and not isinstance(value, int):
        return {'numerator': value.numerator, 'denominator': value.denominator,
                'decimal': float(value) if value.denominator else None}
    return value


def decode_tiff_value(blob, value_type, count, endian):
    if value_type == 2:
        return blob.rstrip(b'\0').decode('utf-8', errors='replace')
    if value_type == 7:
        return {'bytes': len(blob), 'hex': blob.hex()}
    if value_type in (5, 10):
        code = 'I' if value_type == 5 else 'i'
        vals = struct.unpack(endian + code * count * 2, blob)
        out = [{'numerator': vals[i], 'denominator': vals[i + 1],
                'decimal': vals[i] / vals[i + 1] if vals[i + 1] else None}
               for i in range(0, len(vals), 2)]
    else:
        code = {1: 'B', 3: 'H', 4: 'I', 6: 'b', 8: 'h', 9: 'i',
                11: 'f', 12: 'd', 13: 'I'}[value_type]
        out = list(struct.unpack(endian + code * count, blob))
    return out[0] if count == 1 else out


def read_dng(path):
    data = path.read_bytes()
    endian = '<' if data[:2] == b'II' else '>' if data[:2] == b'MM' else None
    assert endian is not None and struct.unpack_from(endian + 'H', data, 2)[0] == 42
    first = struct.unpack_from(endian + 'I', data, 4)[0]
    visited = set()
    directories = []

    def walk(offset, label):
        if not offset or offset in visited:
            return
        visited.add(offset)
        count = struct.unpack_from(endian + 'H', data, offset)[0]
        tags = []
        children = []
        for index in range(count):
            entry = offset + 2 + 12 * index
            tag, value_type, n = struct.unpack_from(endian + 'HHI', data, entry)
            size = TYPE_SIZES[value_type] * n
            pos = entry + 8 if size <= 4 else struct.unpack_from(endian + 'I', data, entry + 8)[0]
            assert pos + size <= len(data), (tag, pos, size)
            blob = data[pos:pos + size]
            value = decode_tiff_value(blob, value_type, n, endian)
            tags.append({'tag': tag, 'name': NAMES.get(tag, f'Tag{tag}'),
                         'type': value_type, 'count': n, 'value': value})
            if tag in (330, 34665, 34853):
                for child in value if isinstance(value, list) else [value]:
                    children.append((child, f'{label}/{NAMES.get(tag, tag)}'))
        directories.append({'label': label, 'offset': offset, 'tags': tags})
        for child, child_label in children:
            walk(child, child_label)
        next_offset = struct.unpack_from(endian + 'I', data, offset + 2 + 12 * count)[0]
        walk(next_offset, label + '/next')

    walk(first, 'IFD0')
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'byte_order': 'little' if endian == '<' else 'big', 'directories': directories}


def read_jpeg(path):
    data = path.read_bytes()
    with Image.open(path) as image:
        exif = image.getexif()
        directories = [{'label': 'IFD0', 'tags': [
            {'tag': k, 'name': NAMES.get(k, str(k)), 'value': scalar_json(v)}
            for k, v in sorted(exif.items())]}]
        for label, index in [('Exif', 34665), ('GPS', 34853), ('Interop', 40965)]:
            try:
                tags = exif.get_ifd(index)
            except (KeyError, TypeError, ValueError):
                continue
            if tags:
                directories.append({'label': label, 'tags': [
                    {'tag': k, 'name': NAMES.get(k, str(k)), 'value': scalar_json(v)}
                    for k, v in sorted(tags.items())]})
        return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'encoded_width': image.width, 'encoded_height': image.height,
                'mode': image.mode, 'directories': directories,
                'icc_profile_bytes': len(image.info.get('icc_profile', b'')),
                'icc_profile_sha256': hashlib.sha256(image.info['icc_profile']).hexdigest()
                    if image.info.get('icc_profile') else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dng', type=Path, required=True)
    parser.add_argument('--jpeg', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = {'dng': read_dng(args.dng.resolve()), 'jpeg': read_jpeg(args.jpeg.resolve())}
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    selected = {'ImageWidth', 'ImageLength', 'BitsPerSample', 'Compression', 'PhotometricInterpretation',
                'Make', 'Model', 'UniqueCameraModel', 'Software', 'DateTime', 'DateTimeOriginal',
                'DateTimeDigitized', 'SubsecTime', 'SubsecTimeOriginal', 'SubsecTimeDigitized',
                'ExposureTime', 'ISOSpeedRatings', 'PhotographicSensitivity', 'FNumber', 'FocalLength',
                'Orientation', 'ImageDescription', 'BlackLevel', 'WhiteLevel', 'AsShotNeutral',
                'ActiveArea', 'CFAPattern', 'StripByteCounts', 'StripOffsets', 'DefaultCropOrigin',
                'DefaultCropSize', 'NoiseProfile', 'ExifImageWidth', 'ExifImageHeight', 'ColorSpace'}
    for kind, result in results.items():
        print(kind.upper(), result['bytes'], result['sha256'])
        if kind == 'jpeg':
            print('encoded dimensions', result['encoded_width'], result['encoded_height'],
                  'ICC profile bytes', result['icc_profile_bytes'])
        for directory in result['directories']:
            for tag in directory['tags']:
                if tag['name'] in selected:
                    print(directory['label'], tag['tag'], tag['name'], tag['value'])
