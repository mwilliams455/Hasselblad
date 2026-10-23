#!/usr/bin/env python3
"""Summarize cached private comparisons and make a labelled scientific contact sheet."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageCms
from compare_hasselblad_pairs41j import srgb_encode, metric


def region_diagnostic(cache, pair, box, name):
    pred=srgb_encode(cache['linear']*2**pair['exposure_fit_EV'])
    h,w=pred.shape[:2]
    x0,y0,x1,y1=box
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    mask=np.zeros((h,w),bool)
    mask[round(y0*h):round(y1*h),round(x0*w):round(x1*w)]=True
    mask &= cache['mask']
    assert mask.sum() >= 1000
    result={'label':pair['label'],'region':name,'normalized_box_xyxy':box,'pixels':int(mask.sum())}
    lp=cv2.cvtColor(pred,cv2.COLOR_RGB2Lab)
    for key in ['reference','jpeg']:
        ref=cache[key]
        lr=cv2.cvtColor(ref,cv2.COLOR_RGB2Lab)
        delta=lp[mask]-lr[mask]
        result[key]={'metrics':metric(pred,ref,mask),
            'median_signed_delta_Lab':np.median(delta,axis=0).tolist(),
            'median_chroma_difference':float(np.median(np.linalg.norm(lp[mask,1:],axis=1)-np.linalg.norm(lr[mask,1:],axis=1)))}
    return result


def panel(result, private_dir, path, names):
    def font(n,bold=False):
        p=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf')
        return ImageFont.truetype(str(p),n) if p.exists() else ImageFont.load_default(size=n)
    colw=360; gap=24; margin=30
    width=3*colw+2*gap+2*margin
    rowheights=[]
    for p in result['pairs']:
        w,h=p['analysis_size'];rowheights.append(round(colw*h/w)+78)
    height=166+sum(rowheights)+90
    image=Image.new('RGB',(width,height),'#101820');draw=ImageDraw.Draw(image)
    draw.text((margin,22),'First RAW rendering baseline',font=font(32,True),fill='white')
    draw.text((margin,68),'Four X2D II captures | conventional LibRaw rendering compared with embedded previews',font=font(18),fill='#c9d5df')
    for i,title in enumerate(['Fixed RAW baseline','Brightness adjusted only','Embedded Hasselblad preview']):
        draw.text((margin+i*(colw+gap),116),title,font=font(18,True),fill='#91c9ee')
    y=166
    for p,rh in zip(result['pairs'],rowheights):
        label=p['label']; ev=p['exposure_fit_EV']; reduction=p['exposure_only_rgb_mae_reduction_percent']
        draw.text((margin,y),f"{label}  {names.get(label,'')}   |   fitted {ev:+.2f} EV   |   RGB difference reduced {reduction:.0f}%",font=font(18,True),fill='white')
        for i,suffix in enumerate(['baseline','exposure','reference']):
            with Image.open(private_dir/f'{label}_{suffix}.png') as im:
                h=round(colw*im.height/im.width)
                image.paste(im.resize((colw,h),Image.Resampling.LANCZOS),(margin+i*(colw+gap),y+36))
        y+=rh
    draw.text((margin,y+3),'Brightness was fitted separately for each scene. No learned colour transform or HNCS port is applied.',font=font(17),fill='#c9d5df')
    draw.text((margin,y+32),'Capture firmware 1.1.6.3. Preview sRGB is assumed; tagged JPEGs were measured separately.',font=font(17),fill='#c9d5df')
    path.parent.mkdir(parents=True,exist_ok=True)
    profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    image.save(path,icc_profile=profile)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--private-dir',type=Path,required=True)
    ap.add_argument('--panel',type=Path,required=True)
    ap.add_argument('--names-json',type=Path)
    ap.add_argument('--region-label')
    ap.add_argument('--region-box',type=float,nargs=4)
    ap.add_argument('--region-name',default='manually inspected region')
    a=ap.parse_args(); result=json.loads(a.receipt.read_text())
    for p in result['pairs']:
        p['exposure_only_rgb_mae_reduction_percent']=100*(1-p['exposure_only_vs_preview']['rgb_mae_8bit']/p['baseline_vs_preview']['rgb_mae_8bit'])
    if a.region_label:
        p=next(p for p in result['pairs'] if p['label']==a.region_label)
        with np.load(a.private_dir/f"{p['label']}_analysis.npz") as cache:
            result['sky_diagnostic']=region_diagnostic(cache,p,a.region_box,a.region_name)
    names=json.loads(a.names_json.read_text()) if a.names_json else {}
    panel(result,a.private_dir,a.panel,names)
    a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'panel':str(a.panel),'pairs':len(result['pairs']),'region_pixels':result.get('sky_diagnostic',{}).get('pixels')}))


if __name__=='__main__':main()
