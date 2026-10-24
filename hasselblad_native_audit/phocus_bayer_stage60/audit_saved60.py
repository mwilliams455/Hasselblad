#!/usr/bin/env python3
"""Private DNG tile study of spatial routing, with aggregate-only output.

Preparation is the Stage58 phone bridge, not the original native DNG decoder.
No render parameter is fitted to this DNG. Differences are in linear RGB16,
before colour/film/display, and cannot establish a photographic colour match.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import tifffile
from audit_gradient60 import GradientRunner, load_private, difference
from reference60 import fast_bayer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'isp_dng_stage30/src'))
from dng_gainmap30 import parse_opcode_list2, apply_gainmaps


def numbers(tag):
    a = np.asarray(tag.value, np.float64).reshape(-1)
    return a[::2]/a[1::2] if int(tag.dtype) in (5, 10) else a


def prepare(path):
    with tifffile.TiffFile(path) as f:
        p = next(p for p in f.pages if int(p.photometric) == 32803)
        assert p.asarray().dtype == np.uint16
        raw = p.asarray(); h, w = raw.shape
        assert np.array_equal(p.tags[33422].value, bytes((0, 1, 1, 2)))
        black = numbers(p.tags[50714]); white = numbers(p.tags[50717])
        assert len(black) in (1, 4) and white.shape == (1,) and white[0] > black.max()
        neutral_tag = p.tags.get(50728) or f.pages[0].tags[50728]
        neutral = numbers(neutral_tag)
        assert neutral.shape == (3,) and np.all(neutral > 0) and np.isfinite(neutral).all()
        maps = parse_opcode_list2(p.tags[51009].value, (h, w))
    sites = np.full((h, w), black[0]) if len(black) == 1 else np.tile(black.reshape(2, 2), ((h+1)//2, (w+1)//2))[:h, :w]
    normalized = ((raw.astype(np.float64)-sites)/(white[0]-black.max())).astype(np.float32)
    bounded = np.clip(normalized, 0, 1)
    prepared, _ = apply_gainmaps(bounded, maps)
    codes = np.floor(prepared*np.float32(65535)).astype('<u2')
    return codes, neutral.min()/neutral, len(maps)


def main():
    p = argparse.ArgumentParser()
    for name in ('apk', 'dng', 'safe-receipt'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args(); assert __debug__
    before = [hashlib.sha256(path.read_bytes()).digest() for path in (a.apk, a.dng)]
    mosaic, gains, map_count = prepare(a.dng)
    assert np.sort(gains)[0] != np.sort(gains)[1], 'Equal lower WB gains outside native regular branch'
    h, w = mosaic.shape
    r = GradientRunner(*load_private(a.apk)); r.setup_graph()
    results = []
    # Fixed spatial grid; no ROI is selected from pixel brightness or colour.
    for gy, gx in ((1, 1), (1, 3), (3, 1), (3, 3)):
        top, left = (gy*h//4-16)//2*2, (gx*w//4-16)//2*2
        assert top >= 36 and left >= 36 and top+68 <= h and left+68 <= w
        patch = mosaic[top-36:top+68, left-36:left+68]
        fast = r.fast(patch)
        assert np.array_equal(fast, fast_bayer(patch))
        r.prepare(gains, (65535,)*3)
        highlighted = r.cpu16(fast.reshape(-1, 3)).reshape(fast.shape)
        recovered_mosaic = r.remosaic(highlighted)
        connected = r.demosaic(recovered_mosaic)
        no_highlight = r.demosaic(patch[4:-4, 4:-4])
        direct = highlighted[32:-32, 32:-32]
        direct_bypass = fast[32:-32, 32:-32]
        assert direct.shape == connected.shape == (32, 32, 3)
        results.append({
            'native_gradient_vs_integer_bilinear_highlights_off': difference(no_highlight, direct_bypass),
            'connected_highlight_bayer_gradient_vs_direct_highlight_rgb': difference(connected, direct),
            'highlight_effect_with_native_gradient': difference(connected, no_highlight)})
        print(json.dumps({'completed_fixed_grid_tiles': len(results)}), flush=True)
    assert before == [hashlib.sha256(path.read_bytes()).digest() for path in (a.apk, a.dng)]
    for ptr, frozen in r.frozen_profile:
        assert bytes(r.u.mem_read(ptr, len(frozen))) == frozen
    r.check_guards()
    result = {'schema': 'hasselblad-stage60-saved-dng-spatial-v1', 'status': 'EXECUTED_EXPERIMENTAL_NATIVE_CPU_TILES',
        'tiles': 4, 'pixels_per_comparison': 4096,
        'selection': 'fixed 2x2 spatial grid; even-aligned 32x32 interior tiles with 36-site halo',
        'gainmap_count': map_count,
        'input_domain': 'Stage58 common-range, 0..1 clipping and per-GainMap upper clamp; quantized to Bayer uint16 before interpolation',
        'input_is_stage58_device_rgb16_buffer': False,
        'highlight_clipping_source': 'prepared encoding ceiling, not measured sensor saturation',
        'highlight_wb_source': 'DNG AsShotNeutral; maximum-normalized reciprocal ratios',
        'unit': 'linear RGB16 before colour, film and display; not sRGB',
        'comparisons': results, 'difference_is_accuracy_score': False,
        'scene_fitted_parameters': 0, 'original_native_dng_decoder_executed': False,
        'native_gainmap_path_executed': False, 'source_dng_modified': False,
        'source_apk_modified': False, 'physical_camera_colour_match_validated': False,
        'phone_sensor_adaptation_experimental': True,
        'capture_renderer_changed': False, 'full_phocus_equivalence': False}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
