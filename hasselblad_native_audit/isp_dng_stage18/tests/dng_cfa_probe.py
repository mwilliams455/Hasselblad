#!/usr/bin/env python3
"""Stage18 CFA/Bayer site diagnostic. Synthetic self-test is public.
Private mode samples an existing user DNG into the Stage18 nonrendering D50 bridge.
No JPEG output, colour look, lens shading, exposure/clip/tone or private uploads.
"""
from __future__ import annotations
import argparse,hashlib,json,tempfile
from pathlib import Path
import numpy as np
from test_dng_pcs_bridge import load_compiled, pa, cp


def reconstruct_rg_at(raw, black, white, y, x):
    """Bilinear RGGB at interior location; NOT the Photon/ISP demosaic."""
    h,w=raw.shape
    if not (2 <= y < h-2 and 2 <= x < w-2):
        raise ValueError('requires_margin_2')
    if black.shape != (4,) or not np.isfinite(black).all() or not white > float(max(black)):
        raise ValueError('invalid_levels')
    def site(yy,xx):
        siteid=((yy&1)*2)+(xx&1)
        return (float(raw[yy,xx])-float(black[siteid]))/(white-float(black[siteid]))
    if (y%2,x%2)==(0,0):
        red=site(y,x)
        green=sum(site(yy,xx) for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)))/4
        blue=sum(site(yy,xx) for yy,xx in ((y-1,x-1),(y-1,x+1),(y+1,x-1),(y+1,x+1)))/4
    elif (y%2,x%2)==(1,1):
        blue=site(y,x)
        green=sum(site(yy,xx) for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)))/4
        red=sum(site(yy,xx) for yy,xx in ((y-1,x-1),(y-1,x+1),(y+1,x-1),(y+1,x+1)))/4
    elif y%2==0:
        green=site(y,x)
        red=(site(y,x-1)+site(y,x+1))/2
        blue=(site(y-1,x)+site(y+1,x))/2
    else:
        green=site(y,x)
        red=(site(y-1,x)+site(y+1,x))/2
        blue=(site(y,x-1)+site(y,x+1))/2
    return np.asarray((red,green,blue),dtype=np.float64)


def synthetic():
    c=(350.,560.,820.)
    raw=np.empty((22,22),dtype=np.uint16)
    for y in range(22):
        for x in range(22):raw[y,x]=int(c[0] if y%2==0 and x%2==0 else c[2] if y%2==1 and x%2==1 else c[1])
    black=pa((64,64,64,64));expected=(np.array(c)-64)/(1023-64)
    n=0
    for y in range(2,20):
        for x in range(2,20):
            actual=reconstruct_rg_at(raw,black,1023,y,x)
            assert np.allclose(actual,expected,atol=1e-15,rtol=0),(y,x,actual,expected)
            n+=1
    try:reconstruct_rg_at(raw,black,1023,0,0)
    except ValueError:pass
    else:raise AssertionError('margin control broken')
    try:reconstruct_rg_at(raw,black,64,5,5)
    except ValueError:pass
    else:raise AssertionError('white-level guard broken')
    return {'status':'PASS','synthetic_cfa_sites':n,'channel_orientation':'RGGB','negative_guard_cases':2,'does_not_render_photos':True}


def actual(dng,private_matrix_report):
    import tifffile
    m=json.loads(Path(private_matrix_report).read_text())
    with tifffile.TiffFile(dng) as f:
        page=f.pages[0];t=page.tags
        assert t['CFAPattern'].value==b'\x00\x01\x01\x02'
        raw=page.asarray()
        black=pa(t['BlackLevel'].value)
        white=float(t['WhiteLevel'].value)
    dig=hashlib.sha256(Path(dng).read_bytes()).hexdigest()
    assert m['original_dng_sha256']==dig
    mat=pa(m['camera_to_xyz_d50']).reshape(3,3)
    h,w=raw.shape
    xs=np.linspace(5,w-6,32,dtype=np.int32)
    ys=np.linspace(5,h-6,32,dtype=np.int32)
    samples=pa(np.asarray([reconstruct_rg_at(raw,black,white,int(y),int(x)) for y in ys for x in xs]))
    with tempfile.TemporaryDirectory() as temp:
        lib=load_compiled('gcc',Path(temp))
        result=pa(np.full_like(samples,100500.))
        status=lib.hb_dng_pcs_apply(cp(mat),cp(samples),samples.shape[0],cp(result))
        assert status==0
    numpy_expected=samples@mat.T
    err=float(np.max(np.abs(result-numpy_expected)))
    assert err<1e-12
    def stat(a):
        return {'minimum_per_component':a.min(axis=0).tolist(),'maximum_per_component':a.max(axis=0).tolist(),
            'negative_component_count':int((a<0).sum()),'greater_than_one_component_count':int((a>1).sum())}
    return {'schema':'stage18-private-raw-pixel-xyz-probe-v1','status':'PASS',
       'dng_sha256':dig,'width':w,'height':h,
       'black_level':black.tolist(),'white_level':white,
       'samples_per_frame':len(samples),'camera_linear_samples':stat(samples),
       'xyz_d50_linear_samples':stat(result),
       'xyz_f64_le_sha256':hashlib.sha256(result.astype('<f8').tobytes()).hexdigest(),
       'c_vs_independent_numpy_max_error':err,
       'no_clipping_or_tonemapping':True,'diagnostic_demosaic_only_not_photon_renderer':True,
       'no_colorimetric_accuracy_proven':True,'hasselblad_ccm_equation_still_unknown':True,
       'photographic_render_applied':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--private-dng',type=Path)
    p.add_argument('--private-matrix-report',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    check=synthetic()
    if a.private_dng:
        assert a.private_matrix_report is not None and a.output is not None
        result=actual(a.private_dng,a.private_matrix_report)
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'scope':'PRIVATE_original_DNG_1024_linear_RGB_samples','status':result['status'],'samples':result['samples_per_frame'],'max_numerical_error':result['c_vs_independent_numpy_max_error'],'no_photo_render':True}))
    else:print(json.dumps(check))
if __name__=='__main__':main()
