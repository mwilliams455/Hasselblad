#!/usr/bin/env python3
"""Controlled highlight adapters around an unchanged, validated colour stage.

This is our SDR experiment, not recovered Hasselblad highlight processing.
Private photographs, profiles, hashes and intermediates stay in --out. Only
--safe-receipt is suitable for public evidence. No parameters are scene-fitted.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'phocus_room_stage46'))
from analyse_room46 import (Core, SRGB_ICC, diff, masks, multiply, orient,
                            panel, read_profile, render, srgb, stage_stats)
from audit_colour44 import read_bundle

INTERNAL_KNEE = .75
DISPLAY_KNEE = .85
LUMA = np.array([.2126, .7152, .0722])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shoulder(rgb, knee):
    """Scale all components together above the maximum-channel knee.

    For m > k, f(m) = k + (m-k)/(1 + (m-k)/(1-k)).
    Identity below k, unit derivative at k, asymptote 1. This retains RGB
    component ratios in this domain; it is not a perceptual hue guarantee.
    Negative components retain their sign; this is not full gamut mapping.
    """
    a = np.asarray(rgb, dtype=np.float64)
    if not 0 < knee < 1 or a.shape[-1] != 3 or not np.isfinite(a).all():
        raise ValueError('Expected finite RGB and a knee strictly between 0 and 1')
    maximum = np.maximum(a.max(axis=-1), 0)
    delta = np.maximum(maximum - knee, 0)
    target = np.where(maximum > knee,
                      knee + delta / (1 + delta / (1 - knee)), maximum)
    scale = np.divide(target, maximum, out=np.ones_like(maximum), where=maximum > 0)
    return a * scale[..., None]


def encode(internal, curve, valid):
    codes = curve[np.clip(internal, 0, 65535).astype(int)].astype(np.uint16)
    codes[~valid] = 0
    return codes


def decoded(codes, v):
    return multiply((codes.astype(float) / 65536) ** v[37], v[28:37].reshape(3, 3))


def evaluate(core, rgb, v, grid, curve):
    baseline, internal, linear, _, p, codes = render(core, rgb, v, grid, curve)
    valid = multiply(rgb.astype(float) * np.array(p.wb) * p.exposure,
                     np.array(p.first))[..., 0] > 0
    assert np.array_equal(encode(internal, curve, valid), codes)
    compressed = shoulder(internal / 65535, INTERNAL_KNEE) * 65535
    early_codes = encode(compressed, curve, valid)
    early_linear = decoded(early_codes, v)
    return {
        'current': (baseline, internal, linear),
        'output_only': (srgb(shoulder(linear, DISPLAY_KNEE)), internal,
                        shoulder(linear, DISPLAY_KNEE)),
        'early_and_output': (srgb(shoulder(early_linear, DISPLAY_KNEE)), compressed,
                             shoulder(early_linear, DISPLAY_KNEE)),
    }, codes


def checks(curve, v):
    rng = np.random.default_rng(47)
    probes = np.r_[rng.uniform(-.5, 8, (2048, 3)),
                   [[0, 0, 0], [-1, -2, -3], [1, .5, .25]]]
    results = {}
    for knee in (INTERNAL_KNEE, DISPLAY_KNEE):
        actual = shoulder(probes, knee)
        expected = []
        for pixel in probes:
            m = max(float(max(pixel)), 0.)
            f = m if m <= knee else 1 - (1 - knee) ** 2 / (m + 1 - 2 * knee)
            expected.append(pixel if m == 0 else pixel * (f / m))
        assert np.allclose(actual, expected, rtol=0, atol=3e-15)
        untouched = np.maximum(probes.max(-1), 0) <= knee
        assert np.array_equal(actual[untouched], probes[untouched])
        assert np.all(actual.max(-1) <= 1)
        # Scaling must preserve component ratios, including negative signs.
        assert np.max(abs(np.cross(actual, probes))) < 2e-14
        ramp = np.unique(np.r_[np.linspace(0, 16, 200001), knee])
        values = shoulder(np.repeat(ramp[:, None], 3, axis=1), knee)[:, 0]
        assert np.all(np.diff(values) >= 0)
        assert abs(shoulder(np.ones((1, 3)), knee)[0, 0] - (1 + knee) / 2) < 1e-15
        h = 1e-7
        near = shoulder(np.repeat(np.array([knee-h, knee, knee+h])[:, None], 3, axis=1), knee)[:, 0]
        assert np.allclose(np.diff(near) / h, 1, rtol=0, atol=2e-6)
        results[str(knee)] = {'independent_scalar_samples': len(probes),
                             'identity_below_knee_exact': True,
                             'component_ratios_preserved': True,
                             'monotonic_ramp_samples': len(ramp),
                             'continuous_unit_slope_at_knee': True}
    invalid_rejected = 0
    for bad in (np.nan, np.inf, -np.inf):
        try:
            shoulder(np.array([[bad, 0, 0]]), DISPLAY_KNEE)
        except ValueError:
            invalid_rejected += 1
    assert invalid_rejected == 3
    ramp = np.linspace(0, 8, 100001)
    source = np.repeat(ramp[:, None], 3, axis=1)
    early = shoulder(source, INTERNAL_KNEE) * 65535
    linear = shoulder(decoded(encode(early, curve, ramp > 0), v), DISPLAY_KNEE)
    luminance = linear @ LUMA
    assert np.min(np.diff(luminance)) >= -1e-12
    results['neutral_through_actual_curve'] = {
        'samples': len(ramp), 'luminance_monotonic': True,
        'nonfinite_inputs_rejected': invalid_rejected}
    return results


def measurements(variants, regions):
    baseline = variants['current'][0]
    baseline_luma = variants['current'][2] @ LUMA
    result = {}
    for name, (image, internal, linear) in variants.items():
        stats = stage_stats(image, internal, linear, regions)
        for region, mask in regions.items():
            stats[region].pop('mean_rgb8')
            delta = diff(orient(image)[mask], orient(baseline)[mask])
            equal = np.all(orient(image)[mask] == orient(baseline)[mask], axis=-1)
            stats[region]['difference_from_current'] = delta
            stats[region]['pixels_exactly_unchanged_pct'] = float(equal.mean() * 100)
        midtones = ((baseline_luma > .02) & (baseline_luma < .5)
                    & np.all(variants['current'][2] >= 0, axis=-1))
        y = (linear @ LUMA)[midtones]
        stats['midtone_luminance'] = {
            'pixels': int(midtones.sum()),
            'median_absolute_change_stops': float(np.median(abs(np.log2(
                np.maximum(y, 1e-12) / baseline_luma[midtones])))),
            'p99_absolute_change_stops': float(np.percentile(abs(np.log2(
                np.maximum(y, 1e-12) / baseline_luma[midtones])), 99))}
        result[name] = stats
    return result


def comparison(variants, path, crop=None, previous_scene=False):
    keys = ['current', 'output_only', 'early_and_output']
    labels = ['Current image 3', 'Gentle output-only trial', 'Earlier + output trial']
    if previous_scene:
        labels[0] = 'Current curve0 rendering'
    if crop is None:
        panel([variants[k][0] for k in keys], path, labels,
              'Earlier indoor scene / regression check' if previous_scene else 'Highlight handling / same room brightness',
              'Curve0 / 4000K LUT / fixed WB and exposure; experimental adapters')
        return
    w, h = 390, 470
    out = Image.new('RGB', (w * 3, h + 95), (24, 27, 30))
    draw = ImageDraw.Draw(out)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
    draw.text((14, 12), 'TV highlight comparison / source RAW already has clipped channels', font=font, fill='white')
    for i, key in enumerate(keys):
        draw.text((i*w+14, 48), labels[i], font=font, fill='white')
        im = Image.fromarray(orient(variants[key][0])).crop(crop)
        im = im.resize((w-10, h-10), Image.Resampling.NEAREST)
        out.paste(im, (i*w+5, 85))
    out.save(path, quality=95, icc_profile=SRGB_ICC)


def main():
    ap = argparse.ArgumentParser()
    for name in ('dng', 'java', 'profile', 'comparison-bundle', 'out', 'safe-receipt'):
        ap.add_argument('--' + name, type=Path, required=True)
    a = ap.parse_args()
    assert __debug__
    a.out.mkdir(parents=True, exist_ok=True)
    inputs = [a.dng, a.profile, a.comparison_bundle,
              a.java/'camera_rgb16.bin', a.java/'curve0_4000_params.bin',
              a.java/'curve0_4000_rgb16.bin', a.java/'curve0_4000.png']
    before = {str(p): sha(p) for p in inputs}
    temperature, film, pv, grid, curve = read_profile(a.profile)
    assert (temperature, film) == (4000, 0)
    rgb = np.fromfile(a.java/'camera_rgb16.bin', dtype='<u2').reshape(768, 1024, 3)
    v = np.fromfile(a.java/'curve0_4000_params.bin', dtype='<f8')
    assert np.array_equal(v[9:], pv[9:])
    core = Core(a.out/'private-core47.so')
    variants, codes = evaluate(core, rgb, v, grid, curve)
    assert np.array_equal(codes, np.fromfile(a.java/'curve0_4000_rgb16.bin', dtype='<u2').reshape(rgb.shape))
    assert np.array_equal(orient(variants['current'][0]), np.array(Image.open(a.java/'curve0_4000.png')))
    synthetic = checks(curve, v)
    room = measurements(variants, masks(768, 1024))
    for name in ('output_only', 'early_and_output'):
        for patch in ('skin_patch', 'wood', 'blue_wall', 'sofa', 'carpet'):
            assert room[name][patch]['pixels_exactly_unchanged_pct'] == 100
        assert room[name]['whole_image']['display_linear_any_above_one_pct'] == 0
    # A previously retained independent scene is a regression check, not a
    # Hasselblad reference or an independently calibrated colour validation.
    b = a.comparison_bundle.read_bytes()
    assert hashlib.sha256(b[:-32]).digest() == b[-32:]
    assert struct.unpack_from('<10i', b, 8) == (1024, 768, 105, 89, 1, 6, 4000, 0, 0, 0)
    other_rgb, _, other_v, other_grid, other_curve, digest, orientation = read_bundle(a.comparison_bundle)
    assert np.array_equal(other_grid, grid) and np.array_equal(other_curve, curve)
    other, other_codes = evaluate(core, other_rgb, other_v, other_grid, other_curve)
    assert hashlib.sha256(other_codes.astype('<u2').tobytes()).digest() == digest
    previous_scene = measurements(other, {'whole_image': np.ones((1024, 768), dtype=bool)})
    for key, data in variants.items():
        Image.fromarray(orient(data[0])).save(a.out/('Stage47_'+key+'.png'), icc_profile=SRGB_ICC)
    comparison(variants, a.out/'Stage47_Room_Highlight_Comparison.jpg')
    comparison(variants, a.out/'Stage47_TV_Highlight_Comparison.jpg', (190, 120, 352, 315))
    comparison(other, a.out/'PRIVATE_Previous_Scene_Comparison.jpg', previous_scene=True)
    assert all(sha(Path(p)) == digest for p, digest in before.items())
    (a.out/'PRIVATE_INPUT_LEDGER.json').write_text(json.dumps(before, indent=2)+'\n')
    result = {
        'schema': 'hasselblad-stage47-highlight-trial-v1',
        'status': 'PASS_CONTROLLED_EXPERIMENT_NOT_DEPLOYED',
        'room_baseline_matches_stage46_Java_RGB16_and_display_exact': True,
        'previous_scene_baseline_matches_saved_RGB16_reference_exact': True,
        'synthetic_checks': synthetic,
        'engineering_parameters_not_scene_fitted': {
            'internal_max_channel_knee': INTERNAL_KNEE, 'linear_sRGB_max_channel_knee': DISPLAY_KNEE,
            'shoulder': 'Identity below k; above k, k+(m-k)/(1+(m-k)/(1-k)); common RGB scale'},
        'room': room, 'previous_indoor_scene': previous_scene,
        'visual_assessment': {
            'output_only': 'Gentler brightest output, visually close to image 3; cannot recover variation already lost before this stage.',
            'early_and_output': 'Stronger TV colour variation, including pronounced pink and cyan; no reference establishes whether these colours are correct.',
            'decision': 'Retain output-only as the conservative visual candidate. Neither trial is promoted to an app default.'},
        'input_files_unchanged': True, 'exposure_changed': False, 'WB_changed': False,
        'LUT_changed': False, 'film_curve_table_changed': False,
        'portable_C_core_changed': False, 'production_renderer_changed': False,
        'experimental_adapter_is_recovered_Hasselblad_processing': False,
        'source_RAW_saturation_recovered': False, 'phone_sensor_calibration_validated': False,
        'full_Phocus_equivalence': False,
        'limitations': [
            'A shoulder produces fewer upper-limit values by construction; that does not establish colour accuracy or recovered detail.',
            'RGB ratios are retained within each shoulder domain; the nonlinear film curve and colour-space conversion can still change perceptual hue.',
            'Negative out-of-gamut channels still use the existing final lower clamp; this is not full gamut mapping.',
            'The earlier trial inserts a new operation before the finite film lookup, so its output is not claimed to match original ARM64 rendering.',
            'These are sampled development previews, not full-resolution production JPEGs.',
            'The two indoor scenes are not a broad validation set or matched Hasselblad references.']}
    a.safe_receipt.parent.mkdir(parents=True, exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'room': {
        k: {'unchanged_pixels_pct': value['whole_image']['pixels_exactly_unchanged_pct'],
            'TV_near_white_pct': value['television']['display_rgb8_all_at_least_250_pct'],
            'TV_mean_abs_RGB8_change': value['television']['difference_from_current']['mean_abs_rgb8'],
            'midtone_change_stops': value['midtone_luminance']}
        for k, value in room.items()}, 'synthetic': synthetic}), flush=True)


if __name__ == '__main__':
    main()
