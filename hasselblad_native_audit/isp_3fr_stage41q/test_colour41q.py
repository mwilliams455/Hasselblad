#!/usr/bin/env python3
"""Isolate empirical colour correction from the rejected Stage41L gamut step.

Private real-image inputs and fitted coefficients must not be committed.
The aggregate receipt and this independently written code may be committed.
No formula here is claimed to be an Eagle2 MAIN instruction or HNCS equation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
for adjacent in ('isp_3fr_stage41j', 'isp_3fr_stage41k', 'isp_3fr_stage41l'):
    sys.path.insert(0, str(HERE.parent / adjacent))
from test_highlights41l import render_soft, fit_tone, fit_ev, roi_masks
from test_shared_render41k import preview_to_srgb, samples, split_masks, to_lab, measurements
from compare_hasselblad_pairs41j import png

MODES = ('global', 'protected', 'lightness')
RIDGE = .05
CHROMA_SCALE = 12.0


def colour_gate(lab, mode):
    """Fixed empirical gate, not selected by held-out scores or image labels."""
    if mode == 'global':
        return np.ones(lab.shape[:-1], dtype=np.float64)
    if mode not in ('protected', 'lightness'):
        raise ValueError(mode)
    chroma2 = np.sum(np.asarray(lab[..., 1:], np.float64) ** 2, axis=-1)
    lightness = np.clip(lab[..., 0] / 100, 0, 1)
    return (chroma2 / (chroma2 + CHROMA_SCALE**2)) * (4 * lightness * (1 - lightness))


def colour_features(lab, mode):
    base = lab[..., 1:].astype(np.float64) / 50 * colour_gate(lab, mode)[..., None]
    if mode == 'lightness':
        return np.concatenate([base, base * (2 * lab[..., :1] / 100 - 1)], axis=-1)
    return base


def fit_colour(predictions, references, mode):
    """Ridge-to-zero residual relative to unchanged a/b; four/eight coefficients.

    The same ungated feature energy sets the penalty for both candidates.
    Training scenes contribute equal sample counts, as in Stage41L.
    """
    assert len(predictions) == len(references) and predictions
    assert len(set(len(p) for p in predictions)) == 1
    xs, features, targets = [], [], []
    for pred, ref in zip(predictions, references):
        lab = to_lab(pred)
        x = lab[:, 1:].astype(np.float64) / 50
        xs.append(x)
        features.append(colour_features(lab, mode))
        targets.append((to_lab(ref)[:, 1:].astype(np.float64) - lab[:, 1:]) / 50)
    x, f, target = np.vstack(xs), np.vstack(features), np.vstack(targets)
    ridge = RIDGE * np.trace(x.T @ x) / 2
    if ridge <= 0:
        return np.zeros((f.shape[1], 2)), {'degenerate_neutral_training': True}
    regularized = f.T @ f + ridge * np.eye(f.shape[1])
    delta = np.linalg.solve(regularized, f.T @ target)
    assert np.isfinite(delta).all()
    return delta, {'degenerate_neutral_training': False,
                   'regularized_condition_number': float(np.linalg.cond(regularized))}


def apply_colour(rgb, delta, mode):
    """Apply a Lab a/b residual after smooth tone and ordinary channel clipping.

    Subtract the unchanged Lab-to-RGB roundtrip so zero correction is exactly
    identity. Final RGB clipping can still affect luminance and hue.
    """
    rgb = np.asarray(rgb, np.float32)
    delta = np.asarray(delta, np.float64)
    expected = (4, 2) if mode == 'lightness' else (2, 2)
    if delta.shape != expected or not np.isfinite(delta).all():
        raise ValueError(f'Expected finite {expected} residual coefficients')
    lab = to_lab(rgb)
    adjusted = lab.copy()
    if mode == 'lightness':
        adjusted[..., 1:] += (colour_features(lab, mode) @ delta * 50).astype(np.float32)
    else:
        adjusted[..., 1:] += ((lab[..., 1:] @ delta) * colour_gate(lab, mode)[..., None]).astype(np.float32)
    base = cv2.cvtColor(lab.reshape(-1, 1, 3), cv2.COLOR_Lab2RGB).reshape(rgb.shape)
    changed = cv2.cvtColor(adjusted.reshape(-1, 1, 3), cv2.COLOR_Lab2RGB).reshape(rgb.shape)
    return np.clip(rgb + changed - base, 0, 1)


def region_scores(predictions, data, score, label, phase):
    regions = roi_masks(data, score, label, phase)
    lab = to_lab(data['reference'])
    # Diagnostic appearance classes, not assertions that any surface is a
    # calibrated neutral. These masks are never used as fitting weights.
    regions['low_chroma_C12_or_less'] = score & (np.linalg.norm(lab[..., 1:], axis=-1) <= CHROMA_SCALE)
    regions['dark_L20_or_less'] = score & (lab[..., 0] <= 20)
    out = {}
    for name, mask in regions.items():
        row = {'pixels': int(mask.sum()), 'sufficient_for_descriptive_score': bool(mask.sum() >= 30)}
        if mask.sum() >= 30:
            for target in ('reference', 'jpeg'):
                row[target] = {model: measurements(pred, data[target], mask) for model, pred in predictions.items()}
        out[name] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache-dir', type=Path, required=True)
    ap.add_argument('--private-dir', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--stage41l-receipt', type=Path, required=True)
    args = ap.parse_args()
    args.private_dir.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(2)
    previous = json.loads(args.stage41l_receipt.read_text())
    previous = {f['heldout']: f for f in previous['folds']}
    data, hashes = {}, {}
    for label in 'ABCD':
        path = args.cache_dir / f'{label}_analysis.npz'
        hashes[label] = hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path) as z:
            d = {k: z[k] for k in z.files}
        d['reference'] = preview_to_srgb(d['reference'], 'DisplayP3')
        d['mask'] &= (d['reference'].min(2) > .02) & (d['reference'].max(2) < .98)
        data[label] = d
    receipt = {
        'schema': 'hasselblad-stage41q-isolated-colour-v1',
        'baseline': 'Stage41L smooth luminance curve plus ordinary channel clipping; no neutral-axis gamut contraction',
        'validation': 'Conditional leave-one-scene-out on the existing four-scene development set; held-out exposure uses guarded calibration tiles disjoint from score tiles; two tile phases; not blind independent validation.',
        'candidates': {
            'global': 'Four-coefficient Lab a/b residual, zero at a=b=0',
            'protected': 'Same residual multiplied by C^2/(C^2+12^2) * 4*(L/100)*(1-L/100)',
            'lightness': 'Exploratory eight-coefficient extension: protected residual coefficients vary affinely with 2*L/100-1',
        },
        'ridge_multiplier': RIDGE,
        'gate_is_empirical_not_firmware': True,
        'primary_global_and_protected_gate_and_regularization_fixed_before_scoring': True,
        'lightness_extension_added_after_inspecting_primary_shirt_failure': True,
        'reference_encoding': 'Fixed empirical DisplayP3-to-sRGB conversion from Stage41K; separately scored tagged sRGB JPEGs',
        'fit_excludes_heldout_scene': True,
        'production_photo_output_changed': False,
        'main_ccm_equation_recovered': False,
        'private_fitted_coefficients_exported': False,
        'folds': [],
    }
    models = {}
    max_baseline_delta = 0.0
    for heldout, d in data.items():
        labels = sorted(k for k in data if k != heldout)
        assert heldout not in labels and len(labels) == 3
        training = [samples(data[k], data[k]['mask']) for k in labels]
        p, evs, tone_info = fit_tone(training)
        train_predictions = [render_soft(x, ev, p, gamut=False)[0] for (x, ref), ev in zip(training, evs)]
        targets = [ref for x, ref in training]
        coefficients, fit_info = {}, {}
        for mode in MODES:
            coefficients[mode], fit_info[mode] = fit_colour(train_predictions, targets, mode)
        models[heldout] = {'shape': p, 'training_EV': dict(zip(labels, evs.tolist())),
            'delta_ab': {mode: c.tolist() for mode, c in coefficients.items()}, 'heldout_EV': {}}
        fold = {'heldout': heldout, 'training_labels': labels, 'tone_fit': tone_info, 'colour_fit': fit_info, 'phases': []}
        for phase in (0, 1):
            cal, score = split_masks(d['mask'], phase)
            ev = fit_ev(*samples(d, cal), p)
            models[heldout]['heldout_EV'][str(phase)] = ev
            baseline = render_soft(d['linear'], ev, p, gamut=False)[0]
            predictions = {'smooth_tone': baseline}
            predictions.update({mode: apply_colour(baseline, coefficients[mode], mode) for mode in MODES})
            regions = region_scores(predictions, d, score, heldout, phase)
            # Verify every baseline metric for every already-defined region,
            # both references and both tile phases, against the frozen receipt.
            prior_regions = previous[heldout]['phases'][phase]['regions']
            for region, prior_row in prior_regions.items():
                assert regions[region]['pixels'] == prior_row['pixels']
                if not prior_row['sufficient_for_descriptive_score']:
                    continue
                for target in ('reference', 'jpeg'):
                    for metric, value in prior_row[target]['smooth_tone_clip'].items():
                        delta = abs(regions[region][target]['smooth_tone'][metric] - value)
                        max_baseline_delta = max(max_baseline_delta, delta)
                        assert delta < 2e-5, (heldout, phase, region, target, metric, delta)
            fold['phases'].append({'phase': phase, 'calibration_pixels': int(cal.sum()),
                                  'score_pixels': int(score.sum()), 'regions': regions})
            if phase == 0:
                for mode, im in {**predictions, 'reference': d['reference']}.items():
                    png(args.private_dir / f'{heldout}_{mode}.png', im)
                np.savez_compressed(args.private_dir / f'{heldout}_diagnostic.npz', **predictions,
                                    reference=d['reference'], jpeg=d['jpeg'], score_mask=score)
        receipt['folds'].append(fold)
        print(json.dumps({'heldout': heldout, 'phase0_rgb_mae': {
            name: metrics['rgb_mae_8bit'] for name, metrics in fold['phases'][0]['regions']['all']['reference'].items()}}), flush=True)
    assert all(hashlib.sha256((args.cache_dir / f'{k}_analysis.npz').read_bytes()).hexdigest() == v for k, v in hashes.items())
    receipt['input_caches_unchanged'] = True
    receipt['stage41l_baseline_max_metric_delta'] = max_baseline_delta
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    (args.private_dir / 'private_fit_parameters.json').write_text(json.dumps({'source_cache_hashes': hashes, 'models': models}, indent=2) + '\n')


if __name__ == '__main__':
    main()
