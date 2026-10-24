#!/usr/bin/env python3
"""Scene-independent colour-domain audit; no look/exposure fitting.

The enlarged-coordinate experiment is diagnostic, not a new Phocus mode.
Private profile values, matrices, input hashes and images stay in --out.
"""
import argparse
import ctypes as C
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phocus_room_stage46'))
from analyse_room46 import Core, read_profile, multiply, trace, srgb, diff, old, SRGB_ICC
from audit_colour44 import read_bundle
from inspect_phocus_temperature41x import expand_oracle

D50=np.array([.9642,1.,.8249])


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def standard_output():
    # Independently derive the standard display matrix using NumPy solves.
    prim=np.array([[.64/.33,.30/.60,.15/.06],[1,1,1],[.03/.33,.10/.60,.79/.06]])
    white=np.array([.3127/.329,1,.3583/.329])
    rgb_to_xyz=prim@np.diag(np.linalg.solve(prim,white))
    bradford=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
    adaptation=np.linalg.solve(bradford,np.diag((bradford@white)/(bradford@D50))@bradford)
    return np.linalg.solve(rgb_to_xyz,adaptation)


def independent_dng(fm,cc,ab,neutral):
    inverse=np.linalg.inv(np.diag(ab)@cc)
    reference=inverse@(neutral/max(neutral))
    return np.diag(D50/fm.sum(1))@fm@np.diag(1/reference)@inverse


def dng_matrix_tests(lib):
    rng=np.random.default_rng(4801);maximum=0.;white_error=0.
    for i in range(256):
        fm=rng.uniform(.01,1,(3,3))
        cc=np.eye(3)+rng.uniform(-.015,.015,(3,3))
        ab=rng.uniform(.6,1.6,3)
        n=rng.uniform(.3,1,3)*rng.uniform(.2,3)
        m={'fm1':fm.ravel(),'fm2':fm.ravel(),'cc1':cc.ravel(),'cc2':cc.ravel(),'ab':ab,'neutral':n}
        ctx=old.context(lib,m,0);actual=np.array(ctx.camera_to_xyz_d50).reshape(3,3)
        expected=independent_dng(fm,cc,ab,n)
        maximum=max(maximum,float(abs(actual-expected).max()))
        white_error=max(white_error,float(abs(actual@(n/max(n))-D50).max()))
    assert maximum<1e-11 and white_error<1e-11
    return {'synthetic_calibrations':256,'maximum_matrix_error':maximum,
            'maximum_normalized_neutral_to_D50_error':white_error,
            'non_diagonal_calibration_and_analog_balance_tested':True}


def coordinate_mask(rgb,first,expanded=False):
    yc=multiply(rgb.astype(float),first)
    coords=yc[...,1:]/np.where(yc[...,0:1]>0,yc[...,0:1],1)*32
    coords+=([25,39] if expanded else [20,32])
    bounds=[164,107] if expanded else [104,88]
    return (yc[...,0]>0)&np.all((coords>=0)&(coords<=bounds),axis=-1)


def run(core,rgb,v,grid,curve,camera,expanded=False,shadow=True,exposure=1):
    p=core.params(v[:9].reshape(3,3)@camera,v[9:18].reshape(3,3),grid,expanded,curve,
                  v[18:22] if shadow else [2,0,0,1],exposure=exposure)
    codes=core.render(rgb,p)
    other,image,stats=trace(rgb,p,v[28:37].reshape(3,3),v[37])
    assert np.array_equal(codes,other)
    return image,codes,stats,p


def colour_panel(target,current,extended,path):
    # An exact synthetic sweep, not a photographic edit or a brand reference.
    width=1100;bar=105
    out=Image.new('RGB',(width,510),(24,27,30));draw=ImageDraw.Draw(out)
    title=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',23)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    draw.text((18,12),'Saturated-blue boundary test / colour look and film tone disabled',font=title,fill='white')
    draw.text((18,48),'Synthetic linear-sRGB sweep; same input, white balance and display transfer',font=font,fill='#cbd0d4')
    for i,(label,rgb) in enumerate([
        ('Expected sRGB',target),('Current bounded identity-table control',current),
        ('Enlarged coordinate control / diagnostic only',extended)]):
        y=86+i*137;draw.text((18,y),label,font=font,fill='white')
        strip=np.repeat(rgb[None,:,:],bar,axis=0)
        out.paste(Image.fromarray(strip).resize((1064,bar),Image.Resampling.NEAREST),(18,y+27))
    out.save(path,icc_profile=SRGB_ICC)


def main():
    ap=argparse.ArgumentParser()
    for name in ('dng','java','profile0','profile1','bundle','out','safe-receipt'):
        ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();assert __debug__;a.out.mkdir(parents=True,exist_ok=True)
    files=[a.dng,a.profile0,a.profile1,a.bundle,a.java/'camera_to_d50.bin',a.java/'xyz_to_srgb.bin',a.java/'camera_rgb16.bin']
    before={str(p):digest(p) for p in files}
    _,_,v,grid,curve0=read_profile(a.profile0)
    _,_,v1,g1,curve1=read_profile(a.profile1)
    assert np.array_equal(v,v1) and np.array_equal(grid,g1)
    output=standard_output()
    stored=np.fromfile(a.java/'xyz_to_srgb.bin',dtype='<f8').reshape(3,3)
    assert np.allclose(output,stored,rtol=0,atol=2e-14)
    camera=np.fromfile(a.java/'camera_to_d50.bin',dtype='<f8').reshape(3,3)
    pcs=old.compile_shared(a.out/'private-pcs48.so');core=Core(a.out/'private-core48.so')
    random_dng=dng_matrix_tests(pcs)
    with tifffile.TiffFile(a.dng) as tf:
        tags=tf.pages[0].tags;m=old.extract_metadata(tags)
        selected_tags={name:name in tags for name in ['BaselineExposure','ProfileBaselineExposureOffset',
            'CameraCalibrationSignature','ProfileCalibrationSignature','ColorimetricReference',
            'ProfileHueSatMapData1','ProfileLookTableData','AsShotICCProfile']}
    independent=independent_dng(m['fm1'].reshape(3,3),np.eye(3) if m['cc1'] is None else m['cc1'].reshape(3,3),
                                np.ones(3) if m['ab'] is None else m['ab'],m['neutral'])
    assert np.allclose(camera,independent,rtol=0,atol=1e-12)
    Q=v[:9].reshape(3,3);S=v[9:18].reshape(3,3);D=v[28:37].reshape(3,3)
    actual_S=S.copy();actual_S[:,0]=1 # Verified pixel routine adds Y directly.
    matrix_checks={'standard_sRGB_matrix_max_error':float(abs(stored-output).max()),
        'room_DNG_matrix_max_error':float(abs(camera-independent).max()),
        'stored_matrix_closure_max_error':float(abs(D@S@Q-output).max()),
        'effective_unit_Y_reconstruction_closure_max_error':float(abs(D@actual_S@Q-output).max()),
        'effective_unit_Y_white_max_error':float(abs(D@actual_S@Q@D50-1).max())}
    assert matrix_checks['stored_matrix_closure_max_error']<1e-12
    # The identity control must include a companding-only table to cancel the
    # display decode. It intentionally removes LUT look, film tone and shadow.
    y,x=np.mgrid[:89,:105];identity=np.stack([x-20,y-32],-1).astype(float)
    no_film=np.clip((np.arange(65536)/65536)**(1/v[37])*65536,0,65535).astype(np.uint16).astype(np.float32)
    levels=np.linspace(.005,.9,17)
    intended=np.stack(np.meshgrid(levels,levels,levels,indexing='ij'),-1).reshape(-1,3)
    xyz=intended@np.linalg.inv(output).T
    unquantized=xyz@np.linalg.inv(camera).T
    assert np.all((unquantized>=0)&(unquantized<=1))
    rgb=np.floor(unquantized*65535).astype(np.uint16)
    direct=srgb(multiply(rgb.astype(float)/65535,output@camera))
    base,_,base_stats,p=run(core,rgb,v,identity,no_film,camera,shadow=False)
    enlarged,_,wide_stats,_=run(core,rgb,v,expand_oracle(identity),no_film,camera,True,False)
    inside=coordinate_mask(rgb,Q@camera)
    control={'samples':len(rgb),'base_coordinate_clipped_samples':int((~inside).sum()),
        'base_all':diff(base,direct),'base_inside':diff(base[inside],direct[inside]),
        'base_outside':diff(base[~inside],direct[~inside]),
        'enlarged_all':diff(enlarged,direct),'enlarged_coordinate_clipped_samples':wide_stats['lut_coordinate_clamped_pixels'],
        'in_range_outputs_unchanged_exact':bool(np.array_equal(base[inside],enlarged[inside]))}
    assert control['base_inside']['max_abs_rgb8']<=1 and control['enlarged_all']['max_abs_rgb8']<=1
    assert control['base_outside']['max_abs_rgb8']>20 and control['enlarged_coordinate_clipped_samples']==0
    assert control['in_range_outputs_unchanged_exact']
    # Controls with intentional boundary mistakes must be detected.
    encoded=core.render(rgb,p).astype(float)/65536
    mutants={
        'missing_internal_transfer_decode':srgb(multiply(encoded,D)),
        'transposed_output_matrix':srgb(multiply(encoded**v[37],D.T)),
        'duplicate_white_balance':run(core,rgb,v,identity,no_film,
            camera@np.diag(1/(m['neutral']/max(m['neutral']))),shadow=False)[0]}
    mutation_results={k:diff(im[inside],direct[inside]) for k,im in mutants.items()}
    assert all(r['mean_abs_rgb8']>2 for r in mutation_results.values())
    # Two real metadata transforms and six different synthetic camera encodings
    # represent the SAME XYZ targets. The latter are not real camera calibrations.
    b=a.bundle.read_bytes();assert hashlib.sha256(b[:-32]).digest()==b[-32:]
    other_rgb,_,other_v,_,_,_,_=read_bundle(a.bundle)
    cameras=[camera,np.linalg.solve(Q,other_v[:9].reshape(3,3))]
    rng=np.random.default_rng(48)
    for i in range(6):
        mix=np.eye(3)+rng.uniform(.01,.12,(3,3));mix/=mix.sum(1)[:,None]
        n=rng.uniform(.3,1,3);n/=n.max()
        cameras.append(np.linalg.inv(output)@np.linalg.inv(np.diag(n)@mix))
    encodings=[xyz@np.linalg.inv(c).T for c in cameras]
    common=np.logical_and.reduce([np.all((x>=0)&(x<=1),axis=1) for x in encodings])
    assert common.sum()>4000
    camera_agreement={}
    for film,curve in ((0,curve0),(1,curve1)):
        outputs=[]
        for c,enc in zip(cameras,encodings):
            px=np.floor(enc[common]*65535).astype(np.uint16)
            outputs.append(run(core,px,v,grid,curve,c)[0])
        differences=[diff(im,outputs[0]) for im in outputs[1:]]
        camera_agreement[str(film)]={'cameras':len(cameras),'common_XYZ_samples':int(common.sum()),
            'maximum_mean_abs_RGB8_difference':max(d['mean_abs_rgb8'] for d in differences),
            'maximum_channel_difference':max(d['max_abs_rgb8'] for d in differences)}
        assert camera_agreement[str(film)]['maximum_channel_difference']<=3
    # Exposure is an explicit pre-colour scalar in this port. Power-of-two
    # placement tests are exact and do not infer missing vendor exposure state.
    test=rng.integers(1,16000,(4096,3),dtype=np.uint16)
    zero=run(core,test,v,grid,curve0,camera,exposure=2)[1]
    doubled=run(core,(test*2).astype(np.uint16),v,grid,curve0,camera)[1]
    assert np.array_equal(zero,doubled)
    neutrals=np.linspace(.002,.9,512)[:,None]*(m['neutral']/max(m['neutral']))
    nrgb=np.floor(neutrals*65535).astype(np.uint16)
    neutral_results={}
    for film,curve in ((0,curve0),(1,curve1)):
        image,_,_,_=run(core,nrgb,v,grid,curve,camera)
        neutral_results[str(film)]={'samples':len(nrgb),'max_display_channel_spread':int(np.ptp(image.astype(int),axis=1).max()),
                                  'mean_display_channel_spread':float(np.ptp(image.astype(int),axis=1).mean())}
        assert neutral_results[str(film)]['max_display_channel_spread']<=2
    # Coverage measurements on retained photos, without parameter fitting.
    photo_coverage={}
    room_rgb=np.fromfile(a.java/'camera_rgb16.bin',dtype='<u2').reshape(768,1024,3)
    for name,px,c in [('room',room_rgb,cameras[0]),('previous_indoor',other_rgb,cameras[1])]:
        current,codes,stats,_=run(core,px,v,grid,curve0,c)
        wide,_,ws,_=run(core,px,v,expand_oracle(grid),curve0,c,True)
        photo_coverage[name]={'pixels':int(px.size//3),'base_coordinate_clamps':stats['lut_coordinate_clamped_pixels'],
            'enlarged_coordinate_clamps':ws['lut_coordinate_clamped_pixels'],
            'diagnostic_difference':diff(wide,current)}
    sweep=np.c_[np.full(256,.005),np.full(256,.005),np.linspace(.005,.9,256)]
    src=sweep@np.linalg.inv(output).T@np.linalg.inv(camera).T
    sp=np.floor(src*65535).astype(np.uint16)
    ref=srgb(multiply(sp.astype(float)/65535,output@camera))
    a0=run(core,sp,v,identity,no_film,camera,shadow=False)[0]
    a1=run(core,sp,v,expand_oracle(identity),no_film,camera,True,False)[0]
    colour_panel(ref,a0,a1,a.out/'Stage48_Synthetic_Blue_Boundary.png')
    assert all(digest(Path(p))==h for p,h in before.items())
    (a.out/'PRIVATE_INPUT_LEDGER.json').write_text(json.dumps(before,indent=2)+'\n')
    result={'schema':'hasselblad-stage48-colour-boundaries-v1','status':'PASS_AUDIT_WITH_OPEN_GAMUT_FINDING',
        'independent_DNG_matrix_tests':random_dng,'matrix_checks':matrix_checks,
        'identity_control':control,'intentional_error_detection':mutation_results,
        'equivalent_colour_across_camera_encodings':camera_agreement,'neutral_ramps':neutral_results,
        'pre_colour_exposure_placement_exact_channels':int(zero.size),
        'room_relevant_metadata_present':selected_tags,'retained_photo_coordinate_coverage':photo_coverage,
        'parameters_fitted_to_photos':False,'look_or_exposure_changes_deployed':False,
        'expanded_coordinate_control_is_verified_Phocus_mode':False,
        'original_APK_replayed_this_stage':False,'input_files_unchanged':True,
        'phone_spectral_colour_accuracy_validated':False,'full_Phocus_equivalence':False,
        'limitations':[
            'Equivalent XYZ through synthetic camera matrices tests composition and quantization, not real sensor spectral accuracy under different lights.',
            'The enlarged grid uses the previously verified expansion operation but retains the current space0 output path; that combination is a diagnostic, not a recovered native mode.',
            'The bounded normal table is itself recovered behaviour. Its clipping is a limitation of the present adaptation, not evidence that the recovered C routine is incorrect.',
            'The small effective neutral/basis error comes from the verified implicit unit-Y reconstruction and finite curve encoding; no proprietary coefficient is altered.',
            'Current reader still requires an equal/single ForwardMatrix branch and rejects differing dual-illuminant forward/calibration matrices.',
            'BaselineExposure/profile offsets and upstream Phocus gain state are not calibrated across cameras; the room omits these exposure-offset tags.',
            'Two retained indoor phone scenes and earlier camera JPEG pairs are not known-settings Phocus validation across illuminants.']}
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
    a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
