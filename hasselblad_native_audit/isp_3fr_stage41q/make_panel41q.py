#!/usr/bin/env python3
"""Arrange measured outputs and references; never publish this private panel."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageCms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--private-dir', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    data = json.loads(args.receipt.read_text())
    font = lambda size, bold=False: ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans' + ('-Bold' if bold else '') + '.ttf', size)
    cw, gap, margin = 300, 18, 28
    width = margin * 2 + 4 * cw + 3 * gap
    labels = {'A': 'Red car', 'B': 'Tower', 'C': 'Portrait', 'D': 'St Paul\u2019s'}
    variants = [('smooth_tone', 'Retained tone'), ('global', 'Global colour trial'),
                ('protected', 'Protected colour trial'), ('reference', 'Camera reference')]
    rows = []
    for fold in data['folds']:
        with Image.open(args.private_dir / f"{fold['heldout']}_reference.png") as im:
            rows.append(round(cw * im.height / im.width) + 73)
    canvas = Image.new('RGB', (width, 165 + sum(rows) + 140), '#101820')
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 20), 'Colour correction improves; the light shirt still regresses', font=font(28, True), fill='white')
    draw.text((margin, 64), 'Four-scene development comparison: each image is excluded from its shared-model fit.', font=font(19), fill='#c9d5df')
    draw.text((margin, 92), 'All candidates use the same smooth tone and ordinary clipping. No gamut-contraction step.', font=font(18), fill='#c9d5df')
    for i, (_, title) in enumerate(variants):
        draw.text((margin + i * (cw + gap), 130), title, font=font(18, True), fill='#91c9ee')
    y = 165
    for fold, row_height in zip(data['folds'], rows):
        label = fold['heldout']
        metrics = fold['phases'][0]['regions']['all']['reference']
        before, after = [metrics[k]['rgb_mae_8bit'] for k in ('smooth_tone', 'protected')]
        draw.text((margin, y), f"{labels[label]}  |  RGB MAE: {before:.2f} \u2192 {after:.2f} ({100 * (1 - after / before):.1f}% lower)", font=font(19, True), fill='white')
        for i, (suffix, _) in enumerate(variants):
            with Image.open(args.private_dir / f'{label}_{suffix}.png') as im:
                canvas.paste(im.resize((cw, round(cw * im.height / im.width)), Image.Resampling.LANCZOS), (margin + i * (cw + gap), y + 33))
        y += row_height
    notes = [
        'Protected trial: sampled skin and sky improve; low-chroma portrait background is preserved.',
        'Light shirt still worsens. Saturated-red RGB error improves in one tile phase and slightly worsens in the other.',
        'Exposure uses separate reference-assisted calibration tiles. These are not blind new-scene results.',
        'Empirical colour research only; no exact Eagle2 MAIN equivalence or Android rendering change.'
    ]
    for i, note in enumerate(notes):
        draw.text((margin, y + 28 * i), note, font=font(17), fill='#c9d5df')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    print(str(args.output))


if __name__ == '__main__':
    main()
