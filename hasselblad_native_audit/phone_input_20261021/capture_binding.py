"""Strict offline binding for the Native1C single, full-copy RAW16 sidecar.

This validates provenance; it does not supply an estimator calibration model.
No fallback to effective processing metadata for original camera identity.
"""
import copy
import hashlib
import importlib.util
import math
from pathlib import Path


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def bind_capture(j, black_source):
    require(j.get('schema') == 'hasselblad-photon-capture-evidence-v1', 'schema')
    require(j.get('input_frame_count') == 1, 'single frame required')
    require(j.get('calibration_evidence_usable') is True, 'metadata unusable')
    d = j['delivered_raw']; o = j['original_still']
    p = o['sensor_provenance']; r = o['selected_raw_sensor_result']
    c = o['selected_sensor_characteristics']; e = j['effective_photon_export']
    require(p.get('sensor_provenance_matched') is True and not p.get('unproven_reasons'), 'sensor provenance')
    require(p.get('request_targets_recorded_raw_surface') is True, 'RAW target')
    opened = p['opened_camera_id']; selected = p['selected_calibration_camera_id']
    require(isinstance(opened, str) and opened and isinstance(selected, str) and selected, 'camera ids')
    if p.get('stream_identity_source') == 'actual_OutputConfiguration_by_delivering_ImageReader_surface':
        require(p.get('configured_output_device_id') == opened and
                p.get('result_camera_id_matched') is True and
                p.get('selected_result_camera_id') == selected, 'configured/result camera')
    else:
        require(p['callback_session_device_id'] == opened, 'callback camera')
    explicit = p.get('explicit_raw_physical_id')
    if explicit is not None:
        require(isinstance(explicit, str) and explicit and selected == explicit, 'physical camera')
    else:
        require(selected == opened, 'direct camera')
        caps = c.get('android.request.availableCapabilities')
        require(isinstance(caps, list) and 3 in caps and 11 not in caps, 'direct RAW capability required; logical RAW needs explicit physical binding')
    stamp = int(d['sensor_timestamp_ns'])
    require(stamp > 0 and stamp == int(o['selected_sensor_timestamp_ns']) == int(r['android.sensor.timestamp']), 'timestamp')
    require(int(j['frame_number']) == int(o['selected_result_frame_number']), 'frame number')
    require(j.get('pairing_status') == 'image_timestamp_equals_selected_still_result_timestamp', 'pairing')
    w, h = int(d['delivered_width']), int(d['delivered_height'])
    require(64 <= w <= 65536 and 64 <= h <= 65536 and w*h <= 32000000 and not ((w|h)&1), 'geometry')
    require(d['format'] == 32 and d['binned'] is False, 'unbinned RAW_SENSOR required')
    require(d['image_crop_rect'] == [0, 0, w, h], 'full image crop required for this binder')
    require((d['copied_width'], d['copied_height'], d['copied_crop_x'], d['copied_crop_y'], d['copy_offset_bytes']) == (w, h, 0, 0, 0), 'full copy required')
    stride, pixel = int(d['row_stride_bytes']), int(d['pixel_stride_bytes'])
    require(2 <= pixel <= 65536 and (w-1)*pixel+2 <= stride <= 16777216, 'strides')
    require((h-1)*stride+(w-1)*pixel+2 <= int(d['original_buffer_capacity_bytes']), 'buffer extent')
    require(c.get('android.sensor.info.pixelArraySize') == [w, h], 'unmapped sensor crop/scale')
    caps = c.get('android.request.availableCapabilities')
    require(isinstance(caps, list) and 3 in caps, 'RAW capability required')
    ultra, remosaic = 16 in caps, 17 in caps
    require(not remosaic or ultra, 'inconsistent remosaic capabilities')
    mode = r.get('android.sensor.pixelMode')
    require((type(mode) is int and mode == 0) or (mode is None and not ultra), 'maximum-resolution mapping unverified')
    # Camera2 scopes rawBinningFactorUsed to UHR + REMOSAIC_REPROCESSING.
    # Other RAW devices have regular Bayer; preserve any out-of-scope flag in
    # original_sensor_metadata rather than treating it as a layout override.
    require(not (ultra and remosaic) or r.get('android.sensor.rawBinningFactorUsed') is False, 'non-Bayer or unknown binning')
    cfa = c['android.sensor.info.colorFilterArrangement']
    require(type(cfa) is int and 0 <= cfa <= 3, 'Bayer CFA')
    if black_source == 'exported':
        require(e['camera_id'] == selected and e['cfa_pattern'] == cfa, 'export camera/CFA')
        black, white = e['black_level_raw_counts'], e['white_level_raw_counts']
    elif black_source == 'dynamic':
        black, white = r['android.sensor.dynamicBlackLevel'], r['android.sensor.dynamicWhiteLevel']
    elif black_source == 'static':
        black, white = c['android.sensor.blackLevelPattern'], c['android.sensor.info.whiteLevel']
    else:
        raise ValueError('explicit black source required')
    require(type(white) is int and 0 < white <= 65535, 'white level')
    require(isinstance(black, list) and len(black) == 4, 'black levels')
    require(all(math.isfinite(x) and 0 <= x < white and float(x*65536).is_integer() for x in black), 'black Q16 representation')
    require(not o.get('required_metadata_missing_or_invalid') and not o.get('collection_errors'), 'original metadata errors')
    for stem in ['calibrationTransform', 'colorTransform', 'forwardMatrix']:
        for n in (1, 2):
            values = c['android.sensor.'+stem+str(n)]
            require(len(values) == 9 and all(type(x['numerator']) is int and type(x['denominator']) is int and x['denominator'] != 0 for x in values), 'original matrix')
    return {'width': w, 'height': h, 'row_stride_bytes': w*2, 'pixel_stride_bytes': 2,
            'crop': [0, 0, w, h], 'cfa': cfa, 'black_q16': [int(x*65536) for x in black],
            'white_code': white, 'black_source': black_source, 'physical_camera_id': selected,
            'sensor_timestamp_ns': str(stamp), 'frame_number': int(j['frame_number']),
            'original_delivered_layout': copy.deepcopy(d),
            'original_sensor_metadata': copy.deepcopy(r), 'original_characteristics': copy.deepcopy(c),
            'estimator_calibration_available': False, 'auxiliary_spectral_input': 'unavailable',
            'white_balance_applied': False, 'spatial_correction_applied': False,
            'vendor_e2_equivalence_proven': False}


def decode_bound_dng(path, j, binding):
    """Decode only the explicitly bound, uncompressed, full-copy CFA layout.

    OpcodeList2 remains metadata; no lens shading or other opcode is applied.
    This is an offline fixture reader, not the Android RAW buffer entry point.
    """
    path = Path(path); data = path.read_bytes(); identity = j['dng']
    require(path.name == identity['name'] and len(data) == identity['bytes'] and hashlib.sha256(data).hexdigest() == identity['sha256'], 'DNG identity')
    module_path = Path(__file__).resolve().parents[2]/'hasselblad_device_validation_20261019/raw_audit/audit_dng.py'
    spec = importlib.util.spec_from_file_location('hb_tiff', module_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    tiff = module.TIFF(data)
    pages = [x['tags'] for x in tiff.ifds if x['tags'].get(262, {}).get('value') == [32803]]
    require(len(pages) == 1, 'one CFA IFD')
    tags = pages[0]; value = lambda k: tags[k]['value']
    w, h = binding['width'], binding['height']
    require(value(256) == [w] and value(257) == [h] and value(258) == [16] and value(259) == [1] and value(277) == [1], 'DNG raw layout')
    require(value(33421) == [2, 2] and value(33422) == [[0,1,1,2],[1,0,2,1],[1,2,0,1],[2,1,1,0]][binding['cfa']], 'DNG CFA')
    require(value(50829) == [0, 0, h, w], 'DNG active area')
    require(not any(k in tags for k in [50712, 50715, 50716, 51008]), 'unhandled RAW corrections')
    require(module.numeric(tags[50714]) == j['effective_photon_export']['black_level_raw_counts'] and module.numeric(tags[50717]) == [j['effective_photon_export']['white_level_raw_counts']], 'DNG export levels')
    offsets, sizes = value(273), value(279); rows = value(278)[0]
    require(rows > 0 and len(offsets) == len(sizes) == (h+rows-1)//rows, 'strips')
    require(all(size == min(rows, h-i*rows)*w*2 for i, size in enumerate(sizes)), 'strip sizes')
    raw = b''.join(tiff.read(offset, size) for offset, size in zip(offsets, sizes))
    if tiff.order == '>':
        raw = b''.join(raw[i:i+2][::-1] for i in range(0, len(raw), 2))
    require(len(raw) == w*h*2, 'raw bytes')
    return raw
