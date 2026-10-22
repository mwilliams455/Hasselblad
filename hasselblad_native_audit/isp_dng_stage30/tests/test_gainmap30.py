#!/usr/bin/env python3
"""Independent, synthetic-only Stage30 opcode and RGGB lens shading tests."""
from __future__ import annotations
import json, pathlib, struct, sys
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dng_gainmap30 import (GainMap, apply_gainmaps, demosaic_linear_rg_reference,
                            parse_opcode_list2, AREA_AND_GRID)


def envelope(opcodes):
    result=struct.pack('>I',len(opcodes))
    for oid,version,flags,params in opcodes:
        result+=struct.pack('>I4sII',oid,version,flags,len(params))+params
    return result


def make_gainmap(shape=(18,24),region=(0,0,18,24),pitch=(1,1),gain_values=None,plane=0,planes=1,map_planes=1):
    if gain_values is None: gain_values=np.asarray([[1.,1.],[1.,1.]],np.float32)
    g=np.asarray(gain_values,dtype=np.float32)
    if g.ndim==2: g=g[:,:,None]
    top,left,bottom,right=region
    ver=AREA_AND_GRID.pack(top,left,bottom,right,plane,planes,pitch[0],pitch[1],
                           g.shape[0],g.shape[1],1/max(1,g.shape[0]-1),1/max(1,g.shape[1]-1),
                           0,0,map_planes)
    return ver+g.astype('>f4').tobytes()


def verify_reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Invalid opcode accepted')


def scalar_gain(m,row,col,height,width):
    fy=max(0,min(m.points_v-1,((row+.5)/height-m.origin_v)/m.spacing_v))
    fx=max(0,min(m.points_h-1,((col+.5)/width-m.origin_h)/m.spacing_h))
    y0=int(np.floor(fy));x0=int(np.floor(fx))
    y1=min(y0+1,m.points_v-1);x1=min(x0+1,m.points_h-1)
    dy=fy-y0;dx=fx-x0
    return (float(m.gains[y0,x0])*(1-dy)*(1-dx)
            +float(m.gains[y1,x0])*dy*(1-dx)
            +float(m.gains[y0,x1])*(1-dy)*dx
            +float(m.gains[y1,x1])*dy*dx)


def reference_apply(source,maps):
    dest=source.copy();height,width=dest.shape
    for m in maps:
        for row in range(m.top,m.bottom,m.row_pitch):
            for col in range(m.left,m.right,m.col_pitch):
                dest[row,col]=min(float(dest[row,col])*scalar_gain(m,row,col,height,width),1.0)
    return dest


def main():
    n=0;wh=(18,24)
    identity_blob=envelope([(9,b'\x01\x03\x00\x00',0,make_gainmap())])
    identity=parse_opcode_list2(identity_blob,wh)
    assert len(identity)==1 and identity[0].points_v==2; n+=1
    rng=np.random.default_rng(20261022)
    raw=rng.uniform(-.1,.9,wh).astype(np.float32)
    output,details=apply_gainmaps(raw,identity)
    assert np.array_equal(raw,output) and details['CFA_site_value_changes']==0; n+=1
    assert not np.shares_memory(raw,output);n+=1

    # Four independently corrected RGGB CFA sites, varying gain by position.
    op=[]
    for (y,x),idx in zip(((0,0),(0,1),(1,0),(1,1)),range(4)):
        g=np.asarray([[1+idx*.15,1.1+idx*.15],[1.2+idx*.15,1.4+idx*.15]],np.float32)
        op.append((9,b'\x01\x03\x00\x00',0,make_gainmap(region=(y,x,18,24),pitch=(2,2),gain_values=g)))
    maps=parse_opcode_list2(envelope(op),wh)
    got,receipt=apply_gainmaps(raw,maps)
    expected=reference_apply(raw,maps)
    assert np.max(abs(got.astype('float64')-expected))<1e-6;n+=1
    assert receipt['covered_CFA_site_writes']>0 and receipt['gainmap_count']==4;n+=1
    assert not receipt['SDK_bit_exact_parity_proven'];n+=1

    # An explicit large gain may saturate the DNG Stage2 sample at unity.
    clipped=np.ones(wh,np.float32)*.9
    one=parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',1,
                    make_gainmap(gain_values=np.ones((2,2),np.float32)*2))]),wh)
    applied,_=apply_gainmaps(clipped,one)
    assert applied.max()==1 and applied.min()==1;n+=1
    assert clipped.max()==.9;n+=1

    # A map's pitch touches exactly the correct Bayer photosites.
    pitch_maps=parse_opcode_list2(envelope([op[0]]),wh)
    arr=np.ones(wh,np.float32)*.2
    a,_=apply_gainmaps(arr,pitch_maps)
    assert np.all(a[1::2,:]==.2) and np.all(a[::2,1::2]==.2);n+=1

    # Nonuniform grid sample positions, optional flags, big-endian codec.
    near=parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',2,
                   make_gainmap(gain_values=np.asarray([[.8,1.1],[1.2,1.8]],np.float32)))]),wh)
    assert near[0].spacing_v==1 and near[0].map_planes==1;n+=1

    # The parser does not silently skip unknown *optional* opcodes either.
    verify_reject(lambda:parse_opcode_list2(envelope([(8,b'\x01\x03\x00\x00',1,b'\0'*76)]),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(envelope([(17,b'\x01\x07\x00\x00',0,b'')]),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(identity_blob[:-1],wh));n+=1
    verify_reject(lambda:parse_opcode_list2(identity_blob+b'\0',wh));n+=1
    verify_reject(lambda:parse_opcode_list2(identity_blob[:4]+b'\0'*16,wh));n+=1
    verify_reject(lambda:parse_opcode_list2(b'',wh));n+=1
    verify_reject(lambda:parse_opcode_list2(struct.pack('>I',99999),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',0,
                        make_gainmap(plane=1))]),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',0,
                        make_gainmap(map_planes=2))]),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',0,
                        make_gainmap(gain_values=np.ones((2,2),np.float32)*1000))]),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',0,
                        make_gainmap(region=(0,0,100,24)))]),wh));n+=1
    verify_reject(lambda:parse_opcode_list2(envelope([(9,b'\x01\x03\x00\x00',0,
                        make_gainmap(gain_values=np.asarray([[np.nan,1],[1,1]],np.float32)))]),wh));n+=1

    # Independent low-variance fixture for RGGB channel-identity and precision.
    flat=np.empty(wh,np.float32)
    flat[::2,::2]=.75;flat[1::2,1::2]=.125
    flat[::2,1::2]=.32;flat[1::2,::2]=.32
    rgb=demosaic_linear_rg_reference(flat)
    assert np.allclose(rgb[2:-2,2:-2],np.asarray([.75,.32,.125]),atol=3e-6);n+=1
    assert rgb.dtype==np.float32 and rgb.shape==(*wh,3);n+=1
    # Bilinear demosaic must not change the recorded green sites when the two
    # green photosite classes have different shading gains.
    split_green=flat.copy()
    split_green[::2,1::2]=.52
    split_green[1::2,::2]=.21
    parsed=demosaic_linear_rg_reference(split_green)
    assert np.array_equal(parsed[::2,1::2,1],split_green[::2,1::2])
    assert np.array_equal(parsed[1::2,::2,1],split_green[1::2,::2]);n+=1
    verify_reject(lambda:demosaic_linear_rg_reference(flat.astype(np.float64)));n+=1
    verify_reject(lambda:apply_gainmaps(np.zeros((18,24),dtype=np.uint16),maps));n+=1
    assert len(maps)==4;n+=1

    result={"schema":"hasselblad-stage30-dng-gainmap-synthetic-v1", "status":"PASS",
        "checks_passed":n,"real_dng_tested":False,"vendor_hncs_equivalence":False,
        "vendor_tables_included":False,"photographic_renderer_modified":False,
        "supported_opcode_id":9,"supported_cfa":"RGGB", "sampled_gainmap_plane_count":1,
        "supports_four_independent_Bayer_gainmaps":True,"unknown_optional_opcodes_rejected":True,
        "sdk_bit_exact_parity_proven":False,
        "max_scalar_vs_vector_difference":float(np.max(abs(got.astype('float64')-expected)))}
    print(json.dumps(result,sort_keys=True))
    return result

if __name__=='__main__':main()
