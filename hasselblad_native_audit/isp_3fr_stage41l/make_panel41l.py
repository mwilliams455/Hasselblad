#!/usr/bin/env python3
"""Private comparison figure for the completed Stage41L experiments."""
import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageCms


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--private-dir',type=Path,required=True)
    ap.add_argument('--names-json',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();receipt=json.loads(a.receipt.read_text());names=json.loads(a.names_json.read_text())
    font=lambda n,b=False:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if b else '')+'.ttf',n)
    cw=280;gap=18;left=28;width=1528
    rows=[]
    for f in receipt['folds']:
        with Image.open(a.private_dir/f"{f['heldout']}_reference.png") as im:rows.append(round(cw*im.height/im.width)+80)
    canvas=Image.new('RGB',(width,170+sum(rows)+170),'#101820');d=ImageDraw.Draw(canvas)
    d.text((left,20),'Smooth highlights improve; saturated reds expose a failed step',font=font(30,True),fill='white')
    d.text((left,66),'Each scene is excluded from shared-model training. References use the corrected P3-to-sRGB conversion.',font=font(18),fill='#c9d5df')
    variants=[('previous_tone','Previous tone'),('smooth_tone_clip','Smooth tone'),('smooth_tone_gamut','Gamut trial: red failure'),('smooth_tone_gamut_chroma','Gamut + colour trial'),('reference','Camera reference')]
    for i,(_,title) in enumerate(variants):d.text((left+i*(cw+gap),118),title,font=font(18,True),fill='#91c9ee')
    y=170
    for f,rh in zip(receipt['folds'],rows):
        label=f['heldout'];m=f['phases'][0]['regions']['all']['reference']
        old=m['previous_tone']['rgb_mae_8bit'];new=m['smooth_tone_clip']['rgb_mae_8bit']
        d.text((left,y),f"{label}  {names.get(label,label)}  |  primary RGB MAE, previous → smooth tone: {old:.2f} → {new:.2f} ({100*(1-new/old):.0f}% lower)",font=font(19,True),fill='white')
        for i,(suffix,_) in enumerate(variants):
            with Image.open(a.private_dir/f'{label}_{suffix}.png') as im:
                height=round(cw*im.height/im.width);canvas.paste(im.resize((cw,height),Image.Resampling.LANCZOS),(left+i*(cw+gap),y+37))
        y+=rh
    notes=[
        'The gamut trial more than doubles red-region RGB error; those clipped reference colours are outside the primary score.',
        'The colour trial helps sampled skin but worsens the light shirt and dark background. Smooth tone is the retained candidate.',
        'Exposure uses separate calibration tiles. No HNCS equivalence or phone rendering change is claimed.',
        'The display highlights cannot show recovered sensor clipping; these are single-RAW rendering comparisons.'
    ]
    for i,n in enumerate(notes):d.text((left,y+29*i),n,font=font(18),fill='#c9d5df')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(a.output,icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
    print(str(a.output))


if __name__=='__main__':main()
