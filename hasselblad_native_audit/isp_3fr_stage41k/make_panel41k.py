#!/usr/bin/env python3
"""Create a private photographic comparison from completed held-out results."""
import argparse
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageCms


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--private-dir',type=Path,required=True)
    ap.add_argument('--names-json',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();r=json.loads(a.receipt.read_text());names=json.loads(a.names_json.read_text())
    def font(n,bold=False):
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',n)
    cw=360;gap=24;left=30;width=1188
    heights=[]
    for f in r['folds']:
        with Image.open(a.private_dir/f"{f['heldout']}_reference.png") as im:heights.append(round(cw*im.height/im.width)+78)
    y=180;canvas=Image.new('RGB',(width,y+sum(heights)+140),'#101820');d=ImageDraw.Draw(canvas)
    d.text((left,22),'Shared tone: testing on a scene left out of training',font=font(29,True),fill='white')
    d.text((left,68),'Embedded previews converted from inferred Display P3 to sRGB; supplied JPEGs agree.',font=font(19),fill='#c9d5df')
    for i,name in enumerate(['Brightness only','Shared tone curve','Corrected camera reference']):
        d.text((left+i*(cw+gap),124),name,font=font(20,True),fill='#91c9ee')
    for f,rh in zip(r['folds'],heights):
        lab=f['heldout'];m=f['evaluations'][0]['score_vs_preview'];b=m['brightness_only']['rgb_mae_8bit'];t=m['shared_tone']['rgb_mae_8bit']
        d.text((left,y),f"{lab}  {names.get(lab,lab)}   |   RGB difference {b:.2f} → {t:.2f}   |   {100*(1-t/b):.0f}% reduction",font=font(18,True),fill='white')
        for i,suffix in enumerate(['brightness_only','shared_tone','reference']):
            with Image.open(a.private_dir/f'{lab}_{suffix}.png') as im:
                h=round(cw*im.height/im.width);canvas.paste(im.resize((cw,h),Image.Resampling.LANCZOS),(left+i*(cw+gap),y+36))
        y+=rh
    for offset,text in enumerate([
        'Each row uses a curve trained on the OTHER three scenes. No chroma correction is shown.',
        'Brightness uses separate calibration patches; reported differences use disjoint scoring patches.',
        'Research baseline only. Capture firmware 1.1.6.3; no HNCS or phone rendering change.'
    ]):d.text((left,y+offset*29),text,font=font(18),fill='#c9d5df')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(a.output,icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    print(str(a.output))


if __name__=='__main__':main()
