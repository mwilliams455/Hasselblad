#!/usr/bin/env python3
"""Experimental private DNG neutral reference renderer, NOT HNCS.

Owns no Hasselblad tuning. It joins verified Stage18/Stage19 math in the
Stage24 C core. A final sRGB preview clip/encoding is explicitly display-only.
DO NOT publish original DNG, matrix values, photos, previews or JSON to GitHub.
"""
from __future__ import annotations
import argparse,ctypes as C,hashlib,json,time,sys,subprocess
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image
import cv2

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]  # repository path .../hasselblad_native_audit/isp_colour_stage24/src/
MAX=1024
LIB_PATHS={
    'stage18':ROOT/'isp_dng_stage18/src',
    'stage19':ROOT/'isp_colour_stage19/src',
    'stage21':ROOT/'isp_main_stage21/src',
}
# Same script can run against the original locally preserved research workdirs.
if not LIB_PATHS['stage18'].is_dir():
    _base=HERE.parents[1]
    LIB_PATHS={
        'stage18':_base/'hb_stage18/src',
        'stage19':_base/'hb_stage19/src',
        'stage21':_base/'hb_stage21/src',
    }


class Context(C.Structure):
    _fields_=[('camera_to_xyz_d50',C.c_double*9),
              ('xyz_d50_to_linear_rgb',C.c_double*9),
              ('gamut',C.c_uint32),('schema',C.c_uint32)]
class Receipt(C.Structure):
    _fields_=[(name,C.c_uint32) for name in (
      'schema','pixel_count','display_gamut','pcs_normalized_neutral','output_linear_light',
      'uses_stage21_MAIN_hypothesis','true_hasselblad_ccm_pixel_proven',
      'true_hasselblad_gamma_pixel_proven','true_hasselblad_lut_pixel_proven',
      'true_hasselblad_wb_calibrated','photographic_render_authorized',
      'existing_phone_renderer_modified')]

def compile_shared(path:Path,cc='cc'):
    csrc=HERE/'hb24_renderer.c'
    dep=LIB_PATHS
    sources=[csrc,dep['stage18']/'hb_dng_pcs_bridge.c',dep['stage19']/'hb_colour_stage19.c',
       dep['stage21']/'hb_main_candidate21.c']
    headers=[HERE]+list(dep.values())
    if not all(f.is_file() for f in sources):
        raise FileNotFoundError(f'Source not checked out in repository: {sources!r}')
    cmd=[cc,'-std=c11','-O2','-shared','-fPIC','-Wall','-Wextra','-Werror']
    for p in headers:cmd.extend(['-I',str(p)])
    cmd+=list(map(str,sources))+['-lm','-o',str(path)]
    subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=30)
    return load(path)

def load(path):
    lib=C.CDLL(str(path.resolve()))
    P=C.POINTER(C.c_double)
    lib.hb24_build.argtypes=[P,P,P,P,P,P,C.c_int,C.POINTER(Context),C.POINTER(Receipt)]
    lib.hb24_build.restype=C.c_int
    lib.hb24_process.argtypes=[C.POINTER(Context),P,C.c_size_t,P,C.c_int,
       C.POINTER(C.c_uint32),C.c_size_t,C.POINTER(C.c_uint8),C.POINTER(C.c_uint8),
       C.c_int,C.POINTER(Receipt)]
    lib.hb24_process.restype=C.c_int
    return lib

def p(arr):return np.asarray(arr,dtype=np.float64).ctypes.data_as(C.POINTER(C.c_double))

def decode_rationals(value,n,tag):
    if value is None:return None
    flat=np.asarray(value,dtype=np.float64).ravel()
    if flat.size!=2*n or (flat[1::2]==0).any():raise ValueError(f'{tag} bad rational count')
    out=flat[::2]/flat[1::2]
    if not np.isfinite(out).all():raise ValueError(f'{tag} non-finite')
    return np.ascontiguousarray(out,dtype=np.float64)

def extract_metadata(t,strict=True):
    if t['CFAPattern'].value!=b'\x00\x01\x01\x02':raise ValueError('Only RGGB is supported')
    if t['CFARepeatPatternDim'].value!=(2,2):raise ValueError('Wrong CFA repeat')
    black=np.asarray(t['BlackLevel'].value,dtype=np.float64).ravel()
    if black.shape!=(4,) or not np.allclose(black,black[0],rtol=0,atol=0):
        raise ValueError('Unequal-site black level requires separately validated correction')
    white=float(t['WhiteLevel'].value)
    if white<=float(black[0]):raise ValueError('Invalid white level')
    fm1=decode_rationals(t['ForwardMatrix1'].value,9,'ForwardMatrix1')
    fm2=decode_rationals(t['ForwardMatrix2'].value,9,'ForwardMatrix2') if 'ForwardMatrix2' in t else None
    cc1=decode_rationals(t['CameraCalibration1'].value,9,'CameraCalibration1') if 'CameraCalibration1' in t else None
    cc2=decode_rationals(t['CameraCalibration2'].value,9,'CameraCalibration2') if 'CameraCalibration2' in t else None
    ab=decode_rationals(t['AnalogBalance'].value,3,'AnalogBalance') if 'AnalogBalance' in t else None
    neutral=decode_rationals(t['AsShotNeutral'].value,3,'AsShotNeutral')
    orientation=int(t['Orientation'].value) if 'Orientation' in t else 1
    if orientation not in (1,6):raise ValueError('Only orientation 1 or 6 is supported')
    opcodes=[n for n in ('OpcodeList1','OpcodeList2','OpcodeList3') if n in t]
    return {'fm1':fm1,'fm2':fm2,'cc1':cc1,'cc2':cc2,'ab':ab,'neutral':neutral,
            'black':float(black[0]),'white':white,'orientation':orientation,
            'unhandled_dng_opcodes':opcodes}

def context(lib,m,gamut):
    ctx=Context();rc=Receipt()
    status=lib.hb24_build(p(m['fm1']),p(m['fm2']) if m['fm2'] is not None else None,
      p(m['cc1']) if m['cc1'] is not None else None,p(m['cc2']) if m['cc2'] is not None else None,
      p(m['ab']) if m['ab'] is not None else None,p(m['neutral']),gamut,C.byref(ctx),C.byref(rc))
    if status:raise ValueError(f'Unsupported DNG colour profile, hb24_build status {status}')
    expected=np.asarray((.9642,1.0,.8249))
    mapped=np.asarray(list(ctx.camera_to_xyz_d50),dtype=np.float64).reshape(3,3)@m['neutral']
    if not np.allclose(mapped,expected,rtol=0,atol=1e-10):raise ValueError('Neutral does not map to ICC D50')
    assert rc.photographic_render_authorized==0
    return ctx

def demosaic(raw,black,white):
    # BayerRG2BGR is OpenCV's unintuitive alias that yields RGB order for a
    # top-left red RGGB input. Verified by an asymmetric red/green/blue fixture.
    bayer=np.empty((20,20),dtype=np.uint16)
    bayer[:,:]=200;bayer[::2,::2]=1000;bayer[1::2,1::2]=100
    test=cv2.cvtColor(bayer,cv2.COLOR_BayerRG2BGR)
    if tuple(map(int,test[10,10]))!=(1000,200,100):
        raise AssertionError('OpenCV channel order differs: refuse silent swap')
    raw_rgb=cv2.cvtColor(raw,cv2.COLOR_BayerRG2BGR)
    return raw_rgb

def stage30_opcode2_gainmap_reference(raw, metadata, opcode_blob):
    """Opt-in strictly GainMap-only Stage2 range-mapped Bayer correction.

    Neither the parser nor demosaic is the original phone/Hasselblad ISP.
    No RAW photos or calibration values are retained in public research.
    """
    sys.path.insert(0, str(ROOT/'isp_dng_stage30/src'))
    from dng_gainmap30 import (
        parse_opcode_list2, apply_gainmaps, demosaic_linear_rg_reference)
    if raw.dtype!=np.uint16 or raw.ndim!=2:
        raise ValueError('Stage30 requires uint16 single-plane Bayer input')
    gainmaps=parse_opcode_list2(opcode_blob,raw.shape)
    denom=metadata['white']-metadata['black']
    if not np.isfinite(denom) or denom<=0:
        raise ValueError('Stage30 invalid DNG black/white normalization')
    normalized=(raw.astype(np.float32)-metadata['black'])/denom
    normalized=np.ascontiguousarray(normalized,dtype=np.float32)
    corrected,receipt=apply_gainmaps(normalized,gainmaps)
    rgb=demosaic_linear_rg_reference(corrected)
    return rgb,receipt


def render(lib,ctx,raw_rgb,black,white):
    h,w,_=raw_rgb.shape
    result=np.empty((h,w,3),dtype=np.float32)
    src=raw_rgb.reshape(-1,3)
    dst=result.reshape(-1,3)
    linear_min=np.full(3,np.inf);linear_max=np.full(3,-np.inf)
    neg=over=0
    tm=time.monotonic()
    for base in range(0,len(src),MAX):
        block=np.ascontiguousarray((src[base:base+MAX].astype(np.float64)-black)/(white-black))
        n=len(block)
        xyzout=np.empty_like(block)
        rc=Receipt()
        status=lib.hb24_process(C.byref(ctx),p(block),n,p(xyzout),0,None,0,None,None,0,C.byref(rc))
        if status or rc.photographic_render_authorized or rc.uses_stage21_MAIN_hypothesis or rc.existing_phone_renderer_modified:
            raise RuntimeError('Stage24 native uncalibrated PCS composition failed: '+str(status))
        dst[base:base+n]=xyzout.astype(np.float32)
        linear_min=np.minimum(linear_min,xyzout.min(axis=0))
        linear_max=np.maximum(linear_max,xyzout.max(axis=0))
        neg+=int((xyzout<0).sum());over+=int((xyzout>1).sum())
    return result,{'conversion_elapsed_seconds':round(time.monotonic()-tm,3),
       'linear_min_rgb':linear_min.tolist(),'linear_max_rgb':linear_max.tolist(),
       'negative_components_preserved_before_export':neg,
       'over_unity_components_preserved_before_export':over}

def srgb_preview(linear,exp_ev=0.0):
    # This is a separate display-only encoding and clipping operation.
    # Clipping is NOT performed inside the linear colour engine.
    s=np.clip(linear*np.exp2(exp_ev),0.0,1.0)
    encoded=np.where(s<=.0031308,12.92*s,1.055*np.power(s,1/2.4)-.055)
    return np.uint8(np.floor(np.clip(encoded,0.,1.)*255.+.5))

def as_oriented(img,orientation):
    if orientation==6:
        return cv2.rotate(img,cv2.ROTATE_90_CLOCKWISE)
    return img

def estimate_exposure_difference(reference_jpeg, linear_oriented):
    # Diagnostic measurement of *one scalar exposure difference* between two
    # different renderers. Cannot identify tone-curve, colour matrix or HNCS.
    ref = np.asarray(reference_jpeg.convert('RGB').resize((384,512)),dtype=np.float32)/255.
    ref_linear=np.where(ref<=.04045,ref/12.92,((ref+.055)/1.055)**2.4)
    predicted=cv2.resize(linear_oriented,(384,512),interpolation=cv2.INTER_AREA)
    weights=np.asarray([.2126,.7152,.0722],dtype=np.float64)
    luma_pred=predicted @ weights
    luma_ref=ref_linear @ weights
    mask=((luma_pred>.015)&(luma_pred<.6)&(luma_ref>.03)&(luma_ref<.75)
          & ((ref_linear.max(axis=2)-ref_linear.min(axis=2))<.16))
    n=int(mask.sum())
    if n<2000:raise ValueError('Insufficient reliable low-chroma midtone pixels for EV alignment')
    ratios=np.log2(luma_ref[mask]/luma_pred[mask])
    ev=float(np.median(ratios))
    if not np.isfinite(ev) or abs(ev)>3:raise ValueError('Invalid exposure-only difference')
    return ev,{'mask_pixels':n,'estimated_display_alignment_EV':ev,
               'log2_ratio_p10_p50_p90':list(map(float,np.quantile(ratios,[.1,.5,.9]))),
               'not_an_exposure_meter_calibration':True,
               'not_an_HNCS_tone_curve':True}

def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--dng',type=Path,required=True)
    a.add_argument('--out-directory',type=Path,required=True)
    a.add_argument('--gamut',choices=('srgb','p3'),default='srgb')
    a.add_argument('--accept-unhandled-dng-opcodes',action='store_true')
    a.add_argument('--apply-supported-dng-gainmaps',action='store_true',
        help='Offline opt-in: require OpcodeList2 GainMap-only DNG, run Bayer shading then float demosaic; not HNCS')
    a.add_argument('--preview-exposure-ev',type=float,default=0.)
    a.add_argument('--linear-tiff',action='store_true',help='Emit 32-bit scene-linear TIFF; no clipping')
    a.add_argument('--reference-jpeg',type=Path,help='Optional private JPEG for labelled visual comparison')
    a.add_argument('--match-display-exposure',action='store_true',
        help='With --reference-jpeg, output a separate scalar EV-matched diagnostic (NOT HNCS)')
    a.add_argument('--verify-private-matrix',type=Path,help='Stage18 private receipt, not uploaded publicly')
    args=a.parse_args(argv)
    if args.apply_supported_dng_gainmaps and args.accept_unhandled_dng_opcodes:
        raise ValueError('Do not combine GainMap correction with unhandled-opcode acceptance')
    if args.match_display_exposure and args.reference_jpeg is None:
        raise ValueError('Matching display exposure requires a reference JPEG')
    if not np.isfinite(args.preview_exposure_ev) or abs(args.preview_exposure_ev)>3:
        raise ValueError('Preview exposure EV out of supported test range')
    dest=args.out_directory;dest.mkdir(parents=True,exist_ok=True)
    if not args.dng.is_file():raise ValueError('Missing DNG')
    source_hash=hashlib.file_digest(args.dng.open('rb'),'sha256').hexdigest()
    with tifffile.TiffFile(args.dng) as doc:
        pg=doc.pages[0];m=extract_metadata(pg.tags)
        listed=m['unhandled_dng_opcodes']
        opcode2_blob=None
        if args.apply_supported_dng_gainmaps:
            if listed!=['OpcodeList2']:
                raise ValueError('Stage30 requires only OpcodeList2; OpcodeList1/3 or absent GainMaps are unsupported')
            opcode2_blob=bytes(pg.tags['OpcodeList2'].value)
        elif listed and not args.accept_unhandled_dng_opcodes:
            raise ValueError('Original DNG contains opcodes; enable explicit GainMap correction or diagnostic-only acceptance')
        raw=pg.asarray()
    if raw.dtype!=np.uint16 or raw.ndim!=2:raise ValueError('Unsupported DNG Bayer image type')
    if m['white']>np.iinfo(raw.dtype).max:raise ValueError('Bad DNG white')
    # Use exact C Stage18/19 mathematical transforms; no assumed vendor maths.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        lib=compile_shared(Path(td)/'hb24.so')
        ctx=context(lib,m,0 if args.gamut=='srgb' else 1)
        if args.verify_private_matrix:
            prev=json.loads(args.verify_private_matrix.read_text())
            if prev['original_dng_sha256']!=source_hash:raise ValueError('Prior DNG hash mismatch')
            mat=np.asarray(list(ctx.camera_to_xyz_d50),dtype=np.float64).reshape(3,3)
            if not np.allclose(mat,np.asarray(prev['camera_to_xyz_d50']),rtol=0,atol=1e-13):
                raise ValueError('Stage18 matrix no longer agrees with private reference')
        correction=None
        if args.apply_supported_dng_gainmaps:
            # Stage30 already black/white range maps the Bayer values.
            dem,correction=stage30_opcode2_gainmap_reference(raw,m,opcode2_blob)
            input_black,input_white=0.,1.
        else:
            dem=demosaic(raw,m['black'],m['white'])
            input_black,input_white=m['black'],m['white']
        del raw
        linear,stats=render(lib,ctx,dem,input_black,input_white)
        del dem
    if args.linear_tiff:
        tifffile.imwrite(dest/'Stage24_NeutralReference_linear_RGB_float32.tif',
            linear,photometric='rgb',description='Stage24 camera DNG to display-primary scene-linear; not HNCS, not Phocus')
    ev_diagnostic=None
    if args.gamut=='srgb':
        out=as_oriented(srgb_preview(linear,args.preview_exposure_ev),m['orientation'])
        picture=Image.fromarray(out,'RGB')
        # Match the current phone JPEG comparison dimensions if supplied.
        if args.reference_jpeg is not None:
            im=Image.open(args.reference_jpeg).convert('RGB')
            picture=picture.resize(im.size,Image.Resampling.LANCZOS)
            comp=Image.new('RGB',(im.width*2,im.height))
            comp.paste(im,(0,0));comp.paste(picture,(im.width,0))
            comp.save(dest/'Stage24_PhotonJPEG_vs_NeutralReference.jpg',quality=92,subsampling=0)
            if args.match_display_exposure:
                estimated,ev_diagnostic=estimate_exposure_difference(im,as_oriented(linear,m['orientation']))
                adjusted=as_oriented(srgb_preview(linear,estimated),m['orientation'])
                matched=Image.fromarray(adjusted,'RGB').resize(im.size,Image.Resampling.LANCZOS)
                matched.save(dest/'Stage24_NeutralReference_ExposureMatchedOnly.jpg',quality=92,subsampling=0)
                pair=Image.new('RGB',(im.width*2,im.height))
                pair.paste(im,(0,0));pair.paste(matched,(im.width,0))
                pair.save(dest/'Stage24_Photon_vs_ExposureMatchedNeutral.jpg',quality=92,subsampling=0)
        picture.save(dest/'Stage24_NeutralReference_preview.jpg',quality=92,subsampling=0)
    # Float TIFF is the only P3 data product; ordinary JPEG without ICC is sRGB only.
    report={
      'schema':'hasselblad-stage24-neutral-photo-software-isp-v1',
      'status':'PASS_private_native_full_frame_reference',
      'source_dng_sha256_PRIVATE':source_hash,
      'source_raw_size_wh':[int(linear.shape[1]),int(linear.shape[0])],
      'orientation':m['orientation'],'input_cfa':'RGGB',
      'output_gamut':args.gamut,'native_pipeline':'C Stage18 camera→D50→C Stage19 linear display RGB',
      'demosaic':('Stage30 float32 RGGB bilinear diagnostic, not Photon/ISP demosaic'
          if args.apply_supported_dng_gainmaps else
          'OpenCV BayerRG2BGR diagnostic, not Photon/ISP demosaic'),
      'lens_shading_correction_applied':bool(correction),
      'lens_shading_correction_scope':('DNG OpcodeList2 GainMap-only, Bayer stage2; independent mathematical reference'
          if correction else 'none; unhandled if accepted'),
      'dng_opcode_state':{
          'present':m['unhandled_dng_opcodes'],
          'applied':bool(correction),
          'applied_opcode_IDs':([9]*correction['gainmap_count'] if correction else []),
          'explicitly_accepted_unhandled':args.accept_unhandled_dng_opcodes,
          'stage30_details':correction,
          'stage30_SDK_bit_exact_parity_proven':False},
      'white_balance':'DNG AsShotNeutral, phone HAL; not original calibrated Hasselblad',
      'preview_encoding':'display-only sRGB OETF and clip; no HNCS tone/colour',
      'preview_exposure_ev':args.preview_exposure_ev,
      'reference_exposure_only_diagnostic':ev_diagnostic,
      'vendor_main_ccm_equation_applied':False,'vendor_main_gamma_applied':False,
      'vendor_main_lut_applied':False,'vendor_postprocessing_applied':False,
      'stage21_candidate_applied':False,'phone_photographic_renderer_unchanged':True,
      'photographic_render_equivalence_proven':False,
      'linear_tiff_emitted':args.linear_tiff,'linear_rgb_statistics':stats,
    }
    (dest/'Stage24_Private_Result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'file_count':len(list(dest.iterdir())),
       'dimensions':report['source_raw_size_wh'],'linear':stats,
       'vendor_color_applied':False,'outputs':[p.name for p in dest.iterdir()]}))

if __name__=='__main__':main()
