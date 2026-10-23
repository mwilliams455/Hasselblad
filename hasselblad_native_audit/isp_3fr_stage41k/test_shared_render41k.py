#!/usr/bin/env python3
"""Conditional leave-one-scene-out tone/chroma experiment on private Stage41J caches.

The held-out scene never trains shared tone/chroma. Its scalar exposure uses
separate calibration tiles, and evaluation uses disjoint guarded tiles. This
is reference-assisted model diagnosis, not a blind camera rendering test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import cv2
from scipy.optimize import least_squares, minimize_scalar
from scipy.special import expit

# Works beside the Stage41J source locally and in the versioned research tree.
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'isp_3fr_stage41j'))
from compare_hasselblad_pairs41j import srgb_encode, srgb_decode, metric, png

LUMA=np.array([.2126,.7152,.0722],dtype=np.float64)
ANCHOR=.18
SAMPLE_COUNT=8192


def rgb_to_xyz_matrix(primaries):
    p=np.asarray(primaries,dtype=np.float64)
    basis=np.stack([p[:,0]/p[:,1],np.ones(3),(1-p.sum(1))/p[:,1]])
    white=np.array([.3127/.329,1,(1-.3127-.329)/.329])
    return basis@np.diag(np.linalg.solve(basis,white))


def preview_to_srgb(encoded, source):
    # Standard fixed primaries/transfer curves, no data-derived coefficients.
    primaries={'sRGB':[(.64,.33),(.30,.60),(.15,.06)],
        'DisplayP3':[(.68,.32),(.265,.69),(.15,.06)],
        'AdobeRGB':[(.64,.33),(.21,.71),(.15,.06)]}
    if source=='sRGB':return np.asarray(encoded,np.float32).copy()
    srgb=rgb_to_xyz_matrix(primaries['sRGB'])
    source_matrix=rgb_to_xyz_matrix(primaries[source])
    linear=np.asarray(encoded,dtype=np.float64)**(563/256) if source=='AdobeRGB' else srgb_decode(np.asarray(encoded,dtype=np.float64))
    return srgb_encode(linear@(np.linalg.inv(srgb)@source_matrix).T).astype(np.float32)


def reference_encoding_check(data):
    result={}
    for source in ['sRGB','DisplayP3','AdobeRGB']:
        converted=preview_to_srgb(data['reference'],source)
        result[source]={}
        for phase in [0,1]:
            _,mask=split_masks(data['mask'],phase)
            result[source][str(phase)]=metric(converted,data['jpeg'],mask)
    return result


def y_to_lightness(y):
    y=np.maximum(y,0)
    f=np.where(y > (6/29)**3,np.cbrt(y),y/(3*(6/29)**2)+4/29)
    return 116*f-16


def curve(y, pars):
    """Two positive shape parameters; identity at (1,1), fixes 0,.18,1.

    logit(f(y)) = p*log(y/.18)-q*log((1-y)/.82)+logit(.18).
    Derivative of logit(f) is p/y+q/(1-y)>0 in the open interval.
    """
    p,q=np.asarray(pars)
    assert p>0 and q>0
    v=np.clip(y,1e-12,1-1e-12)
    z=p*np.log(v/ANCHOR)-q*np.log((1-v)/(1-ANCHOR))+np.log(ANCHOR/(1-ANCHOR))
    out=expit(z)
    return np.where(y<=0,0,np.where(y>=1,1,out))


def render(linear, ev, pars):
    rgb=np.asarray(linear,dtype=np.float64)*2**ev
    y=rgb@LUMA
    scale=np.divide(curve(y,pars),y,out=np.zeros_like(y),where=y>1e-12)
    mapped=rgb*scale[...,None]
    return srgb_encode(mapped).astype(np.float32),mapped


def split_masks(mask, phase=0):
    yy,xx=np.indices(mask.shape)
    inside=(xx%40>=5)&(xx%40<35)&(yy%40>=5)&(yy%40<35)
    code=(xx//40+yy//40+phase)%4
    cal=mask&inside&(code==0)
    score=mask&inside&(code==2)
    assert not np.any(cal&score)
    assert cal.sum()>2000 and score.sum()>2000
    return cal,score


def samples(data, mask, count=SAMPLE_COUNT):
    index=np.flatnonzero(mask)
    take=np.linspace(0,len(index)-1,min(count,len(index)),dtype=int)
    chosen=index[take]
    x=data['linear'].reshape(-1,3)[chosen].astype(np.float64)
    ref=data['reference'].reshape(-1,3)[chosen].astype(np.float64)
    return x,ref


def robust_loss(errors):
    # Same soft-L1 scale (.02 in normalized L*) as the shared model fit.
    return float(np.mean(2*.02**2*(np.sqrt(1+(errors/.02)**2)-1)))


def fit_exposure(x, ref, pars):
    y=x@LUMA
    target=y_to_lightness(srgb_decode(ref)@LUMA)/100
    objective=lambda ev:robust_loss(y_to_lightness(curve(y*2**ev,pars))/100-target)
    fit=minimize_scalar(objective,bounds=(-4,4),method='bounded',options={'xatol':1e-7})
    assert fit.success and abs(fit.x)<3.99
    return float(fit.x)


def fit_shared_tone(training, shape_floor=.4):
    # Equal sample counts per training scene prevent a large sky from getting
    # more total training weight simply because its mask contains more pixels.
    ys=[]; ls=[]; initial=[]
    for x,ref in training:
        ys.append(x@LUMA);ls.append(y_to_lightness(srgb_decode(ref)@LUMA)/100)
        initial.append(fit_exposure(x,ref,(1,1)))
    def residual(theta):
        pars=np.exp(theta[:2])
        return np.concatenate([y_to_lightness(curve(y*2**ev,pars))/100-target for y,target,ev in zip(ys,ls,theta[2:])])
    fit=least_squares(residual,np.array([0.,0.,*initial]),
        bounds=([np.log(shape_floor),np.log(shape_floor),*([-4.]*len(training))],
                [np.log(2.5),np.log(2.5),*([4.]*len(training))]),
        loss='soft_l1',f_scale=.02,ftol=1e-9,xtol=1e-9,gtol=1e-9,max_nfev=200)
    assert fit.success and np.all(np.isfinite(fit.x))
    pars=np.exp(fit.x[:2]);evs=fit.x[2:]
    return pars,evs,{'success':bool(fit.success),'evaluations':int(fit.nfev),'shape_lower_bound':shape_floor,'at_shape_bound':bool(np.any((pars<shape_floor+.00001)|(pars>2.49999)))}


def to_lab(rgb):
    shape=rgb.shape
    a=cv2.cvtColor(np.asarray(rgb,np.float32).reshape(-1,1,3),cv2.COLOR_RGB2Lab)
    return a.reshape(shape)


def fit_chroma(training, pars, evs):
    # A deliberately small diagnostic model: neutral-preserving 2x2 Lab a/b
    # transform, zero offset, ridge-to-identity. It is not a camera CCM.
    xs=[];ys=[]
    for (raw,ref),ev in zip(training,evs):
        pred,_=render(raw,ev,pars)
        xs.append(to_lab(pred)[:,1:]/50)
        ys.append(to_lab(ref)[:,1:]/50)
    x=np.vstack(xs).astype(np.float64);y=np.vstack(ys).astype(np.float64)
    gram=x.T@x
    ridge=.05*np.trace(gram)/2
    matrix=np.linalg.solve(gram+ridge*np.eye(2),x.T@y+ridge*np.eye(2))
    assert np.isfinite(matrix).all()
    return matrix


def apply_chroma(rgb, matrix):
    lab=to_lab(rgb)
    lab[...,1:]=lab[...,1:]@matrix
    out=cv2.cvtColor(lab.reshape(-1,1,3),cv2.COLOR_Lab2RGB).reshape(rgb.shape)
    return out


def measurements(pred,ref,mask):
    result=metric(pred,ref,mask)
    lp=to_lab(pred)[mask];lr=to_lab(ref)[mask]
    result['mean_abs_deltaL']=float(np.abs(lp[:,0]-lr[:,0]).mean())
    result['mean_ab_distance']=float(np.linalg.norm(lp[:,1:]-lr[:,1:],axis=1).mean())
    return result


def train_fold(data, heldout):
    labels=sorted(k for k in data if k!=heldout)
    assert heldout not in labels and len(labels)==len(data)-1
    training=[samples(data[k],data[k]['mask']) for k in labels]
    assert len(set(len(x) for x,_ in training))==1
    pars,evs,info=fit_shared_tone(training)
    chroma=fit_chroma(training,pars,evs)
    return labels,pars,evs,chroma,info


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache-dir',type=Path,required=True)
    ap.add_argument('--private-dir',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--preview-space',choices=['sRGB','DisplayP3'],default='DisplayP3')
    a=ap.parse_args();a.private_dir.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(2)
    data={}; hashes={}
    for label in 'ABCD':
        path=a.cache_dir/f'{label}_analysis.npz'
        hashes[label]=hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path) as cache:data[label]={k:cache[k] for k in cache.files}
    encoding_checks={label:reference_encoding_check(d) for label,d in data.items()}
    original_counts={k:int(d['mask'].sum()) for k,d in data.items()}
    for d in data.values():
        d['reference']=preview_to_srgb(d['reference'],a.preview_space)
        d['mask'] &= (d['reference'].min(2)>.02)&(d['reference'].max(2)<.98)
    out={'schema':'hasselblad-stage41k-conditional-scene-holdout-v1',
        'baseline_stage':'41J','shared_model_training_excludes_heldout_scene':True,
        'preview_source_encoding':a.preview_space,
        'encoding_basis':'Empirical fixed-standard conversion check against all four independently sRGB-tagged JPEGs; not proof of an embedded ICC profile. Parent 3FR Exif ColorSpace=1 does not explain the observed embedded-preview encoding.',
        'fixed_reference_encoding_checks':encoding_checks,
        'stage41j_original_mask_counts':original_counts,
        'mask_further_excludes_reference_values_near_clipping_after_conversion':True,
        'heldout_exposure_uses_reference_calibration_tiles':True,
        'heldout_scoring_tiles_disjoint_from_exposure_tiles':True,
        'alignment_and_initial_masks_from_reference_assisted_stage41j':True,
        'evaluation_scope':'Conditional, reference-assisted diagnostic on four scenes. Not a blind exposure or HNCS renderer.',
        'tone_model':'two-parameter monotonic luminance curve fixed at 0,0.18,1; multiply linear RGB by mapped_Y/Y; clip for display',
        'colour_model':'ridge-to-identity 2x2 Lab a/b transform with zero offset, no L modification before output gamut clipping; not MAIN CCM',
        'sample_count_per_training_scene':SAMPLE_COUNT,
        'training_loss':'soft-L1 on L*/100, f_scale=0.02; shape bounds [0.4,2.5]; exposure bounds +/-4 EV',
        'calibration_and_score_layout':'40px tiles, 5px inset; (tile_x+tile_y+phase)%4 == 0 for exposure, ==2 for scoring',
        'phase_sensitivity':[0,1],
        'main_ccm_equation_recovered':False,'production_photo_output_changed':False,'folds':[]}
    models={}
    for heldout in sorted(data):
        labels,pars,evs,chroma,fit_info=train_fold(data,heldout)
        d=data[heldout];fold={'heldout':heldout,'training_labels':labels,'fit':fit_info,'evaluations':[]}
        models[heldout]={'tone_shape':pars.tolist(),'training_EV':dict(zip(labels,evs.tolist())),'chroma_matrix':chroma.tolist(),'heldout_exposure':{}}
        # The initial fit reaches its lower shape bound. A wider-bound fit is a
        # labelled sensitivity check, never selected using held-out scores.
        training=[samples(data[k],data[k]['mask']) for k in labels]
        wide,wide_evs,wide_info=fit_shared_tone(training,shape_floor=.1)
        models[heldout]['wider_bound_tone_shape']=wide.tolist()
        fold['wider_bound_sensitivity']={'fit':wide_info,'selection':'diagnostic only; primary model stays at prespecified .4 lower bound'}
        for phase in [0,1]:
            cal,score=split_masks(d['mask'],phase)
            x,ref=samples(d,cal)
            base_ev=fit_exposure(x,ref,(1,1));curve_ev=fit_exposure(x,ref,pars)
            baseline,base_linear=render(d['linear'],base_ev,(1,1))
            toned,tone_linear=render(d['linear'],curve_ev,pars)
            coloured=apply_chroma(toned,chroma)
            evinfo={'phase':phase,'calibration_pixels':int(cal.sum()),'score_pixels':int(score.sum()),
                'brightness_only_EV':base_ev,'shared_tone_EV':curve_ev,'score_vs_preview':{},'score_vs_tagged_jpeg':{},
                'tone_before_clip_out_of_gamut_fraction':float(np.mean(np.any((tone_linear[score]<0)|(tone_linear[score]>1),axis=1))),
                'baseline_before_clip_out_of_gamut_fraction':float(np.mean(np.any((base_linear[score]<0)|(base_linear[score]>1),axis=1)))}
            for name,pred in [('brightness_only',baseline),('shared_tone',toned),('shared_tone_chroma',coloured)]:
                evinfo['score_vs_preview'][name]=measurements(pred,d['reference'],score)
                evinfo['score_vs_tagged_jpeg'][name]=measurements(pred,d['jpeg'],score)
                if phase==0:png(a.private_dir/f'{heldout}_{name}.png',pred)
            if phase==0:
                png(a.private_dir/f'{heldout}_reference.png',d['reference'])
                np.savez_compressed(a.private_dir/f'{heldout}_holdout.npz',baseline=baseline,tone=toned,chroma=coloured,reference=d['reference'],jpeg=d['jpeg'],score_mask=score,calibration_mask=cal)
                wide_ev=fit_exposure(x,ref,wide)
                wide_image,_=render(d['linear'],wide_ev,wide)
                fold['wider_bound_sensitivity']['score_vs_preview']=measurements(wide_image,d['reference'],score)
                models[heldout]['wider_bound_heldout_EV']=wide_ev
            models[heldout]['heldout_exposure'][str(phase)]={'baseline':base_ev,'tone':curve_ev}
            fold['evaluations'].append(evinfo)
        out['folds'].append(fold)
        e=fold['evaluations'][0]['score_vs_preview']
        print(json.dumps({'heldout':heldout,'fit':fit_info,'RGB_MAE':{k:v['rgb_mae_8bit'] for k,v in e.items()},'L_MAE':{k:v['mean_abs_deltaL'] for k,v in e.items()},'ab_mean':{k:v['mean_ab_distance'] for k,v in e.items()}}),flush=True)
    out['input_caches_unchanged']=all(hashlib.sha256((a.cache_dir/f'{k}_analysis.npz').read_bytes()).hexdigest()==v for k,v in hashes.items())
    assert out['input_caches_unchanged']
    all_training=[samples(data[k],data[k]['mask']) for k in sorted(data)]
    all_pars,all_evs,all_info=fit_shared_tone(all_training)
    models['all_four_research_candidate']={'tone_shape':all_pars.tolist(),'training_EV':dict(zip(sorted(data),all_evs.tolist())),'evaluation':'trained on all four; no new independent validation'}
    out['all_four_tone_candidate_fitted_after_cross_validation']=all_info
    a.receipt.write_text(json.dumps(out,indent=2)+'\n')
    (a.private_dir/'private_fit_parameters.json').write_text(json.dumps({'source_cache_hashes':hashes,'models':models},indent=2)+'\n')


if __name__=='__main__':main()
