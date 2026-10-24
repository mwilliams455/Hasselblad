#!/usr/bin/env python3
"""Independent full-frame NumPy oracle; no profile data or photographic constants.

The proposed branch follows the DNG range/clipping model, retaining the existing
Stage30 interpolation convention (not a claim of SDK bit-exactness).
"""
from pathlib import Path
import sys
import numpy as np
import tifffile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'isp_dng_stage30/src'))
from dng_gainmap30 import parse_opcode_list2,demosaic_linear_rg_reference,apply_gainmaps
COUNTERS=('decoded_sites','raw_below_black','raw_at_or_above_white','range_lower_clipped','range_upper_clipped',
          'gain_clip_events','gain_clipped_sites','gain_clipped_below_white','unclamped_negative_channels',
          'unclamped_over_unity_channels','changed_prepared_channels')

def reference(path,max_pixels):
 with tifffile.TiffFile(path) as f:
  p=next(p for p in f.pages if int(p.photometric)==32803)
  raw=p.asarray();h,w=raw.shape
  tag=p.tags[50714];black=np.asarray(tag.value,dtype=np.float64).reshape(-1)
  if int(tag.dtype) in (5,10):black=black[::2]/black[1::2]
  white=float(np.asarray(p.tags[50717].value).reshape(-1)[0])
  opcode=p.tags.get(51009);maps=parse_opcode_list2(opcode.value,(h,w)) if opcode else ()
  black_plane=np.full((h,w),black[0]) if len(black)==1 else np.tile(black.reshape(2,2),((h+1)//2,(w+1)//2))[:h,:w]
 signed=((raw.astype(np.float64)-black_plane)/(white-black.max())).astype(np.float32)
 bounded=np.clip(signed,0,1);unlimited=signed.copy()
 legacy=(raw.astype(np.float32)-black_plane.astype(np.float32))/(np.float32(white)-black_plane.astype(np.float32))
 if maps:legacy,_=apply_gainmaps(legacy,maps)
 clip_events=np.zeros((h,w),np.int64)
 for g in maps:
  ys=np.arange(g.top,g.bottom,g.row_pitch);xs=np.arange(g.left,g.right,g.col_pitch)
  fy=np.clip(((ys+.5)/h-g.origin_v)/g.spacing_v,0,g.points_v-1)
  fx=np.clip(((xs+.5)/w-g.origin_h)/g.spacing_h,0,g.points_h-1)
  y0=fy.astype(int);x0=fx.astype(int);y1=np.minimum(y0+1,g.points_v-1);x1=np.minimum(x0+1,g.points_h-1)
  dy=(fy-y0)[:,None];dx=(fx-x0)[None,:]
  gain=g.gains[y0[:,None],x0]*(1-dy)*(1-dx)+g.gains[y1[:,None],x0]*dy*(1-dx)+g.gains[y0[:,None],x1]*(1-dy)*dx+g.gains[y1[:,None],x1]*dy*dx
  sel=np.ix_(ys,xs);product=bounded[sel].astype(np.float64)*gain
  clip_events[sel]+=(product>1)
  bounded[sel]=np.minimum(product,1).astype(np.float32)
  unlimited[sel]=(unlimited[sel].astype(np.float64)*gain).astype(np.float32)
 assert np.isfinite(unlimited).all()
 step=max(1,int(np.ceil(np.sqrt(w*h/max_pixels))))
 while ((w+step-1)//step)*((h+step-1)//step)>max_pixels:step+=1
 def sampled(m):return demosaic_linear_rg_reference(m)[::step,::step].copy()
 def encode(m):return np.floor(np.clip(m,0,1)*np.float32(65535)).astype('<u2')
 rgb=encode(sampled(bounded));old=encode(sampled(legacy));unclamped=sampled(unlimited)
 rows=np.unique(np.abs(np.arange(0,h,step)[:,None]+np.array([-1,0,1])))
 rows=np.unique(np.where(rows>=h,2*h-2-rows,rows))
 def counts(rows):
  r=raw[rows];b=black_plane[rows];s=signed[rows];c=clip_events[rows]
  return [int(r.size),int(np.count_nonzero(r<b)),int(np.count_nonzero(r>=white)),int(np.count_nonzero(s<0)),
          int(np.count_nonzero(s>1)),int(c.sum()),int(np.count_nonzero(c)),int(np.count_nonzero((c>0)&(r<white)))]
 counters=counts(rows)+[int(np.count_nonzero(unclamped<0)),int(np.count_nonzero(unclamped>1)),int(np.count_nonzero(rgb!=old))]
 return {'rgb16':rgb,'legacy':old,'unclamped':unclamped,'counters':np.asarray(counters,dtype='<i8'),
         'full_mosaic_counts':dict(zip(COUNTERS[:8],counts(np.arange(h)))),
         'step':step,'unequal_black':bool(np.any(black!=black[0]))}

def save_reference(path,out,max_pixels):
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);r=reference(path,max_pixels)
 for key in ('rgb16','legacy','unclamped','counters'):r[key].tofile(str(out)+'.'+key)
 return r
