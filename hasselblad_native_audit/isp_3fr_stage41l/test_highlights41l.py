#!/usr/bin/env python3
"""Offline smooth-highlight and regional-colour diagnostics on real 3FR caches.

All models are empirical research candidates. None is an original firmware
pixel equation. Shared fitting excludes the scored scene; exposure uses
separate reference-assisted calibration tiles, as in Stage41K.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
import cv2
from scipy.special import expit
from scipy.optimize import least_squares,minimize_scalar

HERE=Path(__file__).resolve().parent
for relative in ['isp_3fr_stage41k','isp_3fr_stage41j']:
    sys.path.insert(0,str(HERE.parent/relative))
from test_shared_render41k import (LUMA,ANCHOR,preview_to_srgb,y_to_lightness,
    split_masks,samples,robust_loss,to_lab,measurements,apply_chroma,render as old_render)
from compare_hasselblad_pairs41j import srgb_decode,srgb_encode,png

# Pixel coordinates refer to the already-inspected 576x768 portrait cache.
# They are reporting regions only, never fitting weights or skin detection.
PORTRAIT_BOXES={
    'forehead':(175,170,265,212),
    'left_cheek':(142,310,178,350),
    'right_cheek':(280,315,325,365),
    'neck':(220,500,265,535),
    'dark_background':(425,55,550,210),
    'shirt':(330,620,420,710),
}


def soft_curve(y,p):
    """The q->0 limit of Stage41K, extended continuously to all Y>=0.

    f(Y)=sigmoid(p log(Y/.18)+logit(.18)). Middle gray stays fixed,
    slope is positive, and white is approached asymptotically instead of
    forcing every gained input Y>=1 to display white.
    """
    assert p>0
    y=np.asarray(y,dtype=np.float64)
    z=p*np.log(np.maximum(y,1e-300)/ANCHOR)+np.log(ANCHOR/(1-ANCHOR))
    return np.where(y<=0,0,expit(z))


def neutral_axis_gamut(rgb):
    """Contract only overflowing RGB towards equal RGB at the same luminance.

    Deterministic, no learned coefficients. This preserves linear luminance
    and the direction from neutral, not necessarily perceptual Lab hue.
    """
    y=rgb@LUMA
    chroma=rgb-y[...,None]
    hi=np.max(chroma,axis=-1);lo=np.min(chroma,axis=-1)
    up=np.divide(1-y,hi,out=np.ones_like(y),where=hi>1e-12)
    down=np.divide(y,-lo,out=np.ones_like(y),where=lo < -1e-12)
    amount=np.clip(np.minimum(1,np.minimum(up,down)),0,1)
    return y[...,None]+chroma*amount[...,None],amount


def render_soft(linear,ev,p,gamut=True):
    rgb=np.asarray(linear,dtype=np.float64)*2**ev
    y=rgb@LUMA
    scale=np.divide(soft_curve(y,p),y,out=np.zeros_like(y),where=y>1e-12)
    mapped=rgb*scale[...,None]
    before=mapped
    if gamut:mapped,amount=neutral_axis_gamut(mapped)
    else:amount=np.ones_like(y)
    return srgb_encode(mapped).astype(np.float32),before,amount


def fit_ev(x,ref,p):
    y=x@LUMA;target=y_to_lightness(srgb_decode(ref)@LUMA)/100
    fun=lambda ev:robust_loss(y_to_lightness(soft_curve(y*2**ev,p))/100-target)
    fit=minimize_scalar(fun,bounds=(-4,4),method='bounded',options={'xatol':1e-7})
    assert fit.success and abs(fit.x)<3.99
    return float(fit.x)


def fit_tone(training):
    ys=[x@LUMA for x,ref in training]
    targets=[y_to_lightness(srgb_decode(ref)@LUMA)/100 for x,ref in training]
    initial=[fit_ev(x,ref,1.3) for x,ref in training]
    def residual(theta):
        p=np.exp(theta[0])
        return np.concatenate([y_to_lightness(soft_curve(y*2**ev,p))/100-t for y,t,ev in zip(ys,targets,theta[1:])])
    fit=least_squares(residual,[np.log(1.3),*initial],
        bounds=([np.log(.4),*([-4.]*len(training))],[np.log(2.5),*([4.]*len(training))]),
        loss='soft_l1',f_scale=.02,ftol=1e-9,xtol=1e-9,gtol=1e-9,max_nfev=200)
    assert fit.success
    p=float(np.exp(fit.x[0]))
    return p,fit.x[1:],{'success':bool(fit.success),'evaluations':int(fit.nfev),
        'shape_at_bound':bool(p<.40001 or p>2.49999),'training_exposure_at_bound':bool(np.any(abs(fit.x[1:])>3.999))}


def fit_chroma(training,p,evs):
    x=[];y=[]
    for (raw,ref),ev in zip(training,evs):
        pred,_,_=render_soft(raw,ev,p)
        x.append(to_lab(pred)[:,1:]/50);y.append(to_lab(ref)[:,1:]/50)
    x=np.vstack(x).astype(np.float64);y=np.vstack(y).astype(np.float64)
    gram=x.T@x;ridge=.05*np.trace(gram)/2
    assert ridge>0
    return np.linalg.solve(gram+ridge*np.eye(2),x.T@y+ridge*np.eye(2))


def roi_masks(data,score,label,phase=0):
    masks={'all':score,'bright_L80_plus':score&(to_lab(data['reference'])[...,0]>=80)}
    if label=='A':
        # Separate display-appearance diagnostic: retain clipped red reference
        # values that the primary quantitative mask intentionally excludes.
        # Never add these pixels to fitting or the primary score.
        ref=data['reference'];y=ref@LUMA
        grad=np.hypot(cv2.Sobel(y,cv2.CV_64F,1,0,ksize=3),cv2.Sobel(y,cv2.CV_64F,0,1,ksize=3))
        m=(ref[...,0]>1.5*ref[...,1])&(ref[...,0]>1.5*ref[...,2])&(ref.max(2)-ref.min(2)>.3)&(grad<.08)
        m &= (data['linear'].min(2)>.0002)&(data['linear'].max(2)<.98)
        yy,xx=np.indices(m.shape)
        m &= (xx%40>=5)&(xx%40<35)&(yy%40>=5)&(yy%40<35)&(((xx//40+yy//40+phase)%4)==2)
        m[:12,:]=False;m[-12:,:]=False;m[:,:12]=False;m[:,-12:]=False
        masks['red_display_appearance_including_reference_clipping']=m
    if label=='C':
        union=np.zeros(score.shape,bool)
        for name,(x0,y0,x1,y1) in PORTRAIT_BOXES.items():
            m=np.zeros(score.shape,bool);m[y0:y1,x0:x1]=True;m &= score
            masks[name]=m
            if name not in ['dark_background','shirt']:union |= m
        masks['skin_patches_union']=union
        masks['outside_skin_patches']=score&~union
    if label=='D':
        h,w=score.shape;m=np.zeros(score.shape,bool)
        m[round(.06*h):round(.23*h),round(.1*w):round(.85*w)]=True
        masks['clear_sky']=m&score
    return masks


def regional_measurements(predictions,data,score,label,phase=0):
    result={}
    for name,mask in roi_masks(data,score,label,phase).items():
        row={'pixels':int(mask.sum()),'sufficient_for_descriptive_score':bool(mask.sum()>=30)}
        if 'including_reference_clipping' in name:
            row['reference_clipped_fraction']=float(np.mean(data['reference'][mask].max(1)>=.98)) if mask.any() else None
            row['scope']='Post-hoc display-appearance diagnostic, excluded from model training and primary score; does not recover pre-clipping colour.'
        if mask.sum()>=30:
            for ref in ['reference','jpeg']:
                row[ref]={k:measurements(v,data[ref],mask) for k,v in predictions.items()}
        result[name]=row
    return result


def firmware_schema_check(root):
    schema=root/'system/etc/iq/config.fbs';config=root/'system/etc/iq/hb722_config.json'
    text=schema.read_text();data=config.read_text()
    required={'mod_main_gamma_common':['knee_en'],
        'mod_main_gamma_normal':['knee_clip','knee_y_coef','knee_blend_max_det_rate','gamma_lut','gamma_minus_lut','knee_kpx','knee_gain','knee_saturation'],
        'mod_main_autoknee':['enable','ev_adjust_max']}
    fields={}
    for table,expected in required.items():
        match=re.search(r'table\s+'+table+r'\s*\{([^}]+)\}',text)
        assert match
        keys=re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:',match[1],re.M)
        assert set(expected)<=set(keys)
        fields[table]=expected
    match=re.search(r'main_gamma_normal:\s*\{\s*gamma_lut:\s*\{type:\s*(\w+),\s*group:\s*(\w+)',data)
    assert match and match.groups()==('simple_lut_mem','mode_frame')
    return {'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
        'schema_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'checked_fields':fields,'gamma_lut_declared_type':match[1],'gamma_lut_declared_group':match[2],
        'scope':'Static schema/config ownership only. No tuning arrays exported, active bank inferred, or native pixel equation executed.'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache-dir',type=Path,required=True)
    ap.add_argument('--stage41k-models',type=Path,required=True)
    ap.add_argument('--private-dir',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--firmware-root',type=Path)
    a=ap.parse_args();a.private_dir.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(2)
    old=json.loads(a.stage41k_models.read_text())['models']
    data={};hashes={}
    for label in 'ABCD':
        path=a.cache_dir/f'{label}_analysis.npz';hashes[label]=hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path) as z:d={k:z[k] for k in z.files}
        d['reference']=preview_to_srgb(d['reference'],'DisplayP3')
        d['mask'] &= (d['reference'].min(2)>.02)&(d['reference'].max(2)<.98)
        data[label]=d
    out={'schema':'hasselblad-stage41l-smooth-highlight-regions-v1',
        'baseline':'41K corrected DisplayP3-to-sRGB references and original primary .4-bound model',
        'validation':'Conditional leave-one-scene-out shared shape/chroma; heldout exposure uses disjoint guarded calibration tiles. Two tile phases. Same four-image development set, not fresh unseen validation.',
        'new_tone':'q->0 limit of 41K extended to Y>=0; one positive exponent, middle-gray anchor, asymptotic white',
        'new_gamut':'Fixed neutral-axis contraction preserving linear luminance; only overflowing pixels affected; no new fitted parameters',
        'skin_regions_are_evaluation_only':True,'portrait_region_boxes_576x768':PORTRAIT_BOXES,
        'minimum_region_pixels':30,'main_ccm_equation_recovered':False,'production_photo_output_changed':False,
        'folds':[]}
    if a.firmware_root:out['firmware_gamma_schema']=firmware_schema_check(a.firmware_root)
    models={}
    for label,d in data.items():
        labels=[k for k in data if k!=label];assert label not in labels
        training=[samples(data[k],data[k]['mask']) for k in labels]
        p,evs,fit=fit_tone(training);chroma=fit_chroma(training,p,evs)
        models[label]={'shape':p,'training_EV':dict(zip(labels,evs.tolist())),'chroma_matrix':chroma.tolist(),'heldout_EV':{}}
        fold={'heldout':label,'training_labels':labels,'fit':fit,'phases':[]}
        for phase in [0,1]:
            cal,score=split_masks(d['mask'],phase);x,ref=samples(d,cal)
            ev=fit_ev(x,ref,p);models[label]['heldout_EV'][str(phase)]=ev
            previous,_=old_render(d['linear'],old[label]['heldout_exposure'][str(phase)]['tone'],old[label]['tone_shape'])
            previous_chroma=apply_chroma(previous,np.asarray(old[label]['chroma_matrix']))
            unclamped,before,amount=render_soft(d['linear'],ev,p,gamut=False)
            smooth,_,amount=render_soft(d['linear'],ev,p,gamut=True)
            corrected=apply_chroma(smooth,chroma)
            predictions={'previous_tone':previous,'previous_tone_chroma':previous_chroma,
                'smooth_tone_clip':unclamped,'smooth_tone_gamut':smooth,'smooth_tone_gamut_chroma':corrected}
            regions=regional_measurements(predictions,d,score,label,phase)
            entry={'phase':phase,'calibration_pixels':int(cal.sum()),'score_pixels':int(score.sum()),
                'gamut_contracted_fraction':float(np.mean(amount[score]<1-1e-10)),
                'pre_gamut_overflow_fraction':float(np.mean(np.any((before[score]<0)|(before[score]>1),axis=1))),
                'regions':regions}
            fold['phases'].append(entry)
            if phase==0:
                for name,image in {**predictions,'reference':d['reference']}.items():png(a.private_dir/f'{label}_{name}.png',image)
                np.savez_compressed(a.private_dir/f'{label}_diagnostic.npz',**predictions,reference=d['reference'],jpeg=d['jpeg'],score_mask=score)
        out['folds'].append(fold)
        scores=fold['phases'][0]['regions']['all']['reference']
        print(json.dumps({'heldout':label,'fit':fit,'RGB_MAE':{k:v['rgb_mae_8bit'] for k,v in scores.items()}}),flush=True)
    assert all(hashlib.sha256((a.cache_dir/f'{k}_analysis.npz').read_bytes()).hexdigest()==v for k,v in hashes.items())
    out['input_caches_unchanged']=True
    all_training=[samples(data[k],data[k]['mask']) for k in sorted(data)]
    all_p,all_ev,all_fit=fit_tone(all_training)
    models['all_four_tone_candidate']={'shape':all_p,'training_EV':dict(zip(sorted(data),all_ev.tolist())),
        'scope':'Offline research candidate fitted after cross-validation; no additional independent validation or Android deployment.'}
    out['all_four_tone_candidate_fit']=all_fit
    a.receipt.write_text(json.dumps(out,indent=2)+'\n')
    (a.private_dir/'private_fit_parameters.json').write_text(json.dumps({'source_cache_hashes':hashes,'models':models},indent=2)+'\n')


if __name__=='__main__':main()
