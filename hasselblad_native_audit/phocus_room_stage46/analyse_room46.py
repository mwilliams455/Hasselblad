#!/usr/bin/env python3
"""Private same-DNG colour/tone and stage-specific clipping investigation.

No camera colour coefficients are fitted. A scalar exposure fit is a labelled
comparison only. Public output is limited to the requested aggregate receipt.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
import tifffile,cv2
from PIL import Image,ImageDraw,ImageFont,ImageCms
from scipy.optimize import minimize_scalar
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'phocus_colour_stage44'),str(ROOT/'isp_dng_stage30/src')]
from audit_colour44 import Core,trace,multiply,diff
from prepare_preview42 import old,srgb
from dng_gainmap30 import parse_opcode_list2,apply_gainmaps,demosaic_linear_rg_reference
SRGB_ICC=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()

# Reporting patches selected on the upright 768x1024 preview; no neutral/skin
# truth is assumed, and these regions are not colour-fit targets.
POLYGONS={
 'television':[(204,145),(337,185),(337,296),(204,274)],
 'blinds':[(425,45),(700,45),(700,265),(425,265)],
 'white_frame':[(415,400),(690,400),(690,415),(415,415)],
 'blue_wall':[(295,25),(340,25),(340,100),(295,100)],
 'wood':[(30,420),(110,420),(110,545),(30,545)],
 'skin_patch':[(447,622),(478,616),(490,639),(466,656),(450,641)],
 'sofa':[(570,850),(625,850),(625,900),(570,900)],
 'carpet':[(335,950),(390,950),(390,975),(335,975)]}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def orient(a):return np.rot90(a,-1)
def masks(w,h,scale=1):
    result={'whole_image':np.ones((h,w),bool)}
    for key,points in POLYGONS.items():
        im=Image.new('1',(w,h));ImageDraw.Draw(im).polygon([(x*scale,y*scale) for x,y in points],fill=1)
        result[key]=np.array(im,dtype=bool)
    return result
def percentage(mask):return float(np.mean(mask)*100)
def read_profile(path):
    b=path.read_bytes();assert b[:8]==b'HB43LUT1' and hashlib.sha256(b[:-32]).digest()==b[-32:]
    w,h,t,model,film,space=struct.unpack_from('<6i',b,8);assert (w,h,model,space)==(105,89,0,0)
    v=np.frombuffer(b,dtype='<f8',count=38,offset=32).copy();at=32+304
    grid=np.frombuffer(b,dtype='<f8',count=w*h*2,offset=at).reshape(h,w,2).copy();at+=w*h*16
    curve=np.frombuffer(b,dtype='<f4',count=65536,offset=at).copy()
    return t,film,v,grid,curve
def gain_trace(raw,m,entries):
    normalized=(raw.astype(np.float32)-m['black'])/(m['white']-m['black'])
    result=normalized.copy();raised=np.zeros(raw.shape,bool);H,W=raw.shape
    for g in entries:
        rows=np.arange(g.top,g.bottom,g.row_pitch,dtype=float);cols=np.arange(g.left,g.right,g.col_pitch,dtype=float)
        yy=np.clip(((rows+.5)/H-g.origin_v)/g.spacing_v,0,g.points_v-1)
        xx=np.clip(((cols+.5)/W-g.origin_h)/g.spacing_h,0,g.points_h-1)
        y0=yy.astype(int);x0=xx.astype(int);y1=np.minimum(y0+1,g.points_v-1);x1=np.minimum(x0+1,g.points_h-1)
        dy=(yy-y0)[:,None];dx=(xx-x0)[None,:]
        gain=(g.gains[y0[:,None],x0[None,:]]*(1-dy)*(1-dx)+g.gains[y1[:,None],x0[None,:]]*dy*(1-dx)
            +g.gains[y0[:,None],x1[None,:]]*(1-dy)*dx+g.gains[y1[:,None],x1[None,:]]*dy*dx)
        sl=np.s_[g.top:g.bottom:g.row_pitch,g.left:g.right:g.col_pitch]
        candidate=result[sl].astype(float)*gain
        raised[sl]|=(candidate>1)&(result[sl]<1)
        result[sl]=np.minimum(candidate,1).astype(np.float32)
    expected,_=apply_gainmaps(normalized,entries);assert np.array_equal(result,expected)
    return result,raised
def intermediate(rgb,p,D,exponent):
    """Expose pre-curve and post-display arrays; verify outputs via existing trace."""
    grid,curve=p._arrays
    yc=multiply(rgb.astype(float)*np.array(p.wb)*p.exposure,np.array(p.first));Y=yc[...,0]
    xy=np.clip(yc[...,1:]/np.where(Y>0,Y,1)[...,None]*32+[p.bias_x,p.bias_y],[0,0],[p.width-1,p.height-1])
    x,y=xy[...,0],xy[...,1];x0=x.astype(int);y0=y.astype(int);x1=np.minimum(x0+1,p.width-1);y1=np.minimum(y0+1,p.height-1)
    dx=(x-x0)[...,None];dy=(y-y0)[...,None]
    c=((grid[y0,x0]*(1-dx)+grid[y0,x1]*dx)*(1-dy)+(grid[y1,x0]*(1-dx)+grid[y1,x1]*dx)*dy)/32
    s=np.array(p.shadow);weight=np.clip(np.where(Y>s[0],1,(s[1]*Y+s[2])*Y+s[3]),0,1)
    c=(c*Y[...,None])*weight[...,None];k=np.array(p.second).reshape(3,3)
    internal=np.stack([(Y+k[i,1]*c[...,0])+k[i,2]*c[...,1] for i in range(3)],-1)
    encoded=curve[np.clip(internal,0,65535).astype(int)].astype(np.uint16);encoded[Y<=0]=0
    linear=multiply((encoded.astype(float)/65536)**exponent,D)
    return encoded,internal,linear
def render(core,rgb,v,grid,curve,exposure=1):
    p=core.params(v[:9].reshape(3,3),v[9:18].reshape(3,3),grid,False,curve,v[18:22],exposure=exposure)
    codes=core.render(rgb,p);traced,image,stats=trace(rgb,p,v[28:37].reshape(3,3),v[37])
    extra,internal,linear=intermediate(rgb,p,v[28:37].reshape(3,3),v[37])
    assert np.array_equal(codes,traced) and np.array_equal(codes,extra) and np.array_equal(image,srgb(linear))
    return image,internal,linear,stats,p,codes
def stage_stats(image,internal,linear,regions):
    im=orient(image);lin=orient(linear);inter=None if internal is None else orient(internal)
    result={}
    for name,mask in regions.items():
        x=im[mask];l=lin[mask]
        r={'pixels':len(x),'mean_rgb8':x.mean(0).tolist(),
           'display_linear_any_above_one_pct':percentage(np.any(l>1,axis=-1)),
           'display_linear_any_below_zero_pct':percentage(np.any(l<0,axis=-1)),
           'display_rgb8_any_255_pct':percentage(np.any(x==255,axis=-1)),
           'display_rgb8_all_at_least_250_pct':percentage(np.all(x>=250,axis=-1))}
        if inter is not None:r['pre_curve_any_above_65535_pct']=percentage(np.any(inter[mask]>65535,axis=-1))
        result[name]=r
    return result
def panel(images,path,labels,heading,subtitle):
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
    small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    width=360;out=Image.new('RGB',(width*len(images),580),(24,27,30));d=ImageDraw.Draw(out)
    d.text((16,12),heading,font=font,fill='white');d.text((16,45),subtitle,font=small,fill='#cbd0d4')
    for i,(im,label) in enumerate(zip(images,labels)):
        d.text((i*width+15,85),label,font=small,fill='white')
        pic=Image.fromarray(orient(im));pic.thumbnail((width-20,456))
        out.paste(pic,(i*width+(width-pic.width)//2,115))
    out.save(path,quality=95,icc_profile=SRGB_ICC)

def main():
    ap=argparse.ArgumentParser()
    for x in ('dng','java','out','safe-receipt'):ap.add_argument('--'+x,type=Path,required=True)
    ap.add_argument('--profile',type=Path,action='append',required=True)
    a=ap.parse_args();assert __debug__;a.out.mkdir(parents=True,exist_ok=True)
    before={str(p):sha(p) for p in [a.dng,*a.profile]}
    with tifffile.TiffFile(a.dng) as doc:
        pg=doc.pages[0];raw=pg.asarray();m=old.extract_metadata(pg.tags)
        assert raw.shape==(3072,4096) and m['orientation']==6
        entries=parse_opcode_list2(bytes(pg.tags['OpcodeList2'].value),raw.shape)
    mosaic,raised=gain_trace(raw,m,entries);dem=demosaic_linear_rg_reference(mosaic)
    small=dem[::4,::4];rgb=np.floor(np.clip(small,0,1)*65535).astype(np.uint16)
    java_input=np.fromfile(a.java/'camera_rgb16.bin',dtype='<u2').reshape(rgb.shape)
    assert np.array_equal(rgb,java_input)
    ctx=old.context(old.compile_shared(a.out/'private-pcs46.so'),m,0)
    camera=np.asarray(ctx.camera_to_xyz_d50).reshape(3,3);xyz_srgb=np.asarray(ctx.xyz_d50_to_linear_rgb).reshape(3,3)
    assert np.array_equal(camera.ravel(),np.fromfile(a.java/'camera_to_d50.bin',dtype='<f8'))
    Dbase=np.array([[(xyz_srgb[i,0]*camera[0,j]+xyz_srgb[i,1]*camera[1,j])+xyz_srgb[i,2]*camera[2,j] for j in range(3)] for i in range(3)])
    baseline_linear=multiply(rgb.astype(float)/65535,Dbase);baseline=srgb(baseline_linear)
    assert np.array_equal(orient(baseline),np.array(Image.open(a.java/'baseline.png')))
    regions=masks(768,1024);full_regions=masks(3072,4096,4)
    cfa=np.empty(raw.shape,np.uint8);cfa[::2,::2]=0;cfa[::2,1::2]=1;cfa[1::2,::2]=2;cfa[1::2,1::2]=3
    rawo=orient(raw);cfao=orient(cfa);raisedo=orient(raised)
    raw_stats={}
    for name,mask in full_regions.items():
        row={'CFA_sites':int(mask.sum()),'raw_sites_at_white_pct':percentage(rawo[mask]>=m['white']),
             'gainmap_newly_above_unity_pct':percentage(raisedo[mask])}
        row['raw_at_white_by_CFA_pct']={ch:percentage(rawo[mask&(cfao==i)]>=m['white']) for i,ch in enumerate(['R','G1','G2','B'])}
        raw_stats[name]=row
    core=Core(a.out/'private-core46.so')
    results={};images={'baseline':baseline};linear={};params={}
    baseline_stats=stage_stats(baseline,None,baseline_linear,regions)
    for path in a.profile:
        temp,film,v,grid,curve=read_profile(path);name=f'curve{film}_{temp}'
        ba=v[:9].reshape(3,3).copy()
        first=np.array([[(ba[i,0]*camera[0,j]+ba[i,1]*camera[1,j])+ba[i,2]*camera[2,j] for j in range(3)] for i in range(3)])
        v[:9]=first.ravel();assert np.array_equal(v,np.fromfile(a.java/(name+'_params.bin'),dtype='<f8'))
        im,inter,lin,stats,p,codes=render(core,rgb,v,grid,curve)
        assert np.array_equal(codes,np.fromfile(a.java/(name+'_rgb16.bin'),dtype='<u2').reshape(rgb.shape))
        assert np.array_equal(orient(im),np.array(Image.open(a.java/(name+'.png'))))
        images[name]=im;linear[name]=lin;params[name]=(v,grid,curve)
        results[name]={'clipping':stats,'regions':stage_stats(im,inter,lin,regions),
            'host_Java_RGB16_and_display_exact':True,'original_ARM64_replayed_on_this_DNG':False}
        Image.fromarray(orient(im)).save(a.out/(name+'.png'))
        print(name,'host Java/C and independent trace checks passed',flush=True)
    # LUT-only control at the same exposure and curve.
    v,grid,curve=params['curve0_4000'];gy,gx=np.mgrid[:89,:105];identity=np.stack([gx-20,gy-32],-1).astype(float)
    tone=render(core,rgb,v,identity,curve)[0]
    effects={'LUT_4000_to_3050_curve0':diff(images['curve0_3050'],images['curve0_4000']),
             'LUT_vs_identity_curve0':diff(images['curve0_4000'],tone),
             'curve0_vs_curve1_4000_fixed_exposure':diff(images['curve0_4000'],images['curve1_4000'])}
    region_effects={name:{
        'LUT_4000_to_3050_curve0':diff(orient(images['curve0_3050'])[mask],orient(images['curve0_4000'])[mask]),
        'LUT_vs_identity_curve0':diff(orient(images['curve0_4000'])[mask],orient(tone)[mask])}
        for name,mask in regions.items()}
    # Brightness-only fit. Checkerboard calibration tiles exclude saturated and
    # near-black baseline samples; remaining tiles are reported independently.
    Y=baseline_linear@np.array([.2126,.7152,.0722]);yy,xx=np.indices(Y.shape)
    valid=(Y>.015)&(Y<.5)&np.all((baseline_linear>0)&(baseline_linear<.9),axis=-1)
    cal=valid&(((yy//32+xx//32)%2)==0);held=valid&~cal
    reference=linear['curve1_4000']@np.array([.2126,.7152,.0722])
    sample_rgb=rgb[cal][::16];target=reference[cal][::16]
    def objective(ev):
        p=core.params(v[:9].reshape(3,3),v[9:18].reshape(3,3),grid,False,curve,v[18:22],exposure=float(2**ev))
        codes=core.render(sample_rgb,p)
        lum=multiply((codes.astype(float)/65536)**v[37],v[28:37].reshape(3,3))@np.array([.2126,.7152,.0722])
        return float(np.median(abs(np.log2(np.maximum(lum,1e-8)/target))))
    fit=minimize_scalar(objective,bounds=(-2,0),method='bounded',options={'xatol':1e-5})
    matched,inter,lin,stats,_,_=render(core,rgb,v,grid,curve,2**fit.x)
    images['curve0_brightness_matched']=matched
    results['curve0_brightness_matched']={'exposure_EV':float(fit.x),'clipping':stats,
        'regions':stage_stats(matched,inter,lin,regions),
        'calibration_median_absolute_log_luma_stops':float(fit.fun),
        'held_tiles_median_absolute_log_luma_stops':float(np.median(abs(np.log2(np.maximum((lin@np.array([.2126,.7152,.0722]))[held],1e-8)/reference[held]))))}
    for name,mask in regions.items():
        region_effects[name]['curve0_brightness_matched_vs_curve1']=diff(orient(matched)[mask],orient(images['curve1_4000'])[mask])
    Image.fromarray(orient(matched)).save(a.out/'curve0_brightness_matched.png')
    panel([images[k] for k in ['baseline','curve1_4000','curve0_4000','curve0_3050']],a.out/'Stage46_Room_Profile_Comparison.jpg',
        ['Same RAW baseline','Curve1 / 4000K','Curve0 / 4000K','Curve0 / 3050K'],'Actual tungsten room DNG','Fixed DNG white balance and exposure; only the selected profile changes')
    panel([images['curve1_4000'],images['curve0_4000'],matched],a.out/'Stage46_Room_Brightness_Matched.jpg',
        ['Curve1 / original exposure','Curve0 / original exposure',f'Curve0 / {fit.x:+.2f} EV'],
        'Separate brightness from colour', 'One global exposure fit; no white-balance, saturation or hue adjustment')
    # TV crops include the reporting polygon and surrounding context.
    tv=[np.array(Image.fromarray(orient(images[k])).crop((190,120,352,315)).resize((324,390),Image.Resampling.NEAREST)) for k in ['baseline','curve1_4000','curve0_4000','curve0_brightness_matched']]
    out=Image.new('RGB',(1296,445),(24,27,30));draw=ImageDraw.Draw(out);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    for i,(im,label) in enumerate(zip(tv,['Baseline','Curve1','Curve0',f'Curve0 / {fit.x:+.2f} EV'])):
        draw.text((i*324+12,14),label,fill='white',font=font);out.paste(Image.fromarray(im),(i*324,50))
    out.save(a.out/'Stage46_TV_Highlight_Comparison.jpg',quality=95,icc_profile=SRGB_ICC)
    overlay=Image.fromarray(orient(images['curve0_4000']));draw=ImageDraw.Draw(overlay)
    for name,polygon in POLYGONS.items():draw.line(polygon+[polygon[0]],fill='#ff50e2',width=2);draw.text(polygon[0],name,fill='white')
    overlay.save(a.out/'Stage46_Reporting_Regions.png')
    assert all(sha(Path(p))==digest for p,digest in before.items())
    private={'input_hashes':before,'metadata':{k:x.tolist() if isinstance(x,np.ndarray) else x for k,x in m.items()}}
    (a.out/'PRIVATE_INPUT_LEDGER.json').write_text(json.dumps(private,indent=2)+'\n')
    result={'schema':'hasselblad-stage46-room-dng-audit-v1','status':'PASS_EXACT_HOST_PREPARATION_AND_RENDER',
        'raw_dimensions':[4096,3072],'preview_dimensions':[1024,768],'orientation':6,'gainmap_count':len(entries),
        'independent_prepared_channels_exact':int(rgb.size),'input_negative_channels':int((small<0).sum()),
        'input_over_unity_channels':int((small>1).sum()),'raw_region_statistics':raw_stats,'baseline_regions':baseline_stats,
        'profiles':results,'isolated_effects':effects,'regional_effects':region_effects,'brightness_fit_is_diagnostic_only':True,
        'gainmap_upper_clamp_specification':'Adobe DNG 1.7.1.0, Opcode List Processing, printed page 105',
        'specification_url':'https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf#page=105',
        'source_DNG_unchanged':True,'source_profiles_unchanged':True,'WB_changed':False,
        'phone_calibration_fitted':False,'production_renderer_changed':False,'full_Phocus_equivalence':False,
        'limitations':['No matched Hasselblad/Phocus capture of this room.','Screenshot scaling is not a bit-exact device-output receipt.',
        'Original APK is no longer local; this stage uses the previously validated private profiles and portable renderer, without a new ARM64 vendor replay.',
        'Selected object patches are reporting regions, not known colour targets.','Brightness fit is scene-specific and is not a deployed exposure rule.']}
    (a.out/'STAGE46_PRIVATE_ROOM_ANALYSIS.json').write_text(json.dumps(result,indent=2)+'\n')
    # Public evidence excludes even the region mean RGB values; photo/metadata
    # payloads and the complete private analysis remain outside the repository.
    def public(value):
        if isinstance(value,dict):return {k:public(v) for k,v in value.items() if k!='mean_rgb8'}
        if isinstance(value,list):return [public(v) for v in value]
        return value
    a.safe_receipt.parent.mkdir(parents=True,exist_ok=True);a.safe_receipt.write_text(json.dumps(public(result),indent=2)+'\n')
    print(json.dumps({'effects':effects,'brightness_fit_EV':float(fit.x),'TV_raw':raw_stats['television']}),flush=True)
if __name__=='__main__':main()
