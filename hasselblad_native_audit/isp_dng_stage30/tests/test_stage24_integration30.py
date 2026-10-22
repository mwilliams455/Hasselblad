#!/usr/bin/env python3
"""Stage30 hosted, synthetic-only test of Stage24's optional real-RAW adapter."""
from __future__ import annotations
import sys,json,struct
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
AUDIT=HERE.parents[1]
sys.path.insert(0,str(AUDIT/'isp_colour_stage24/src'))
sys.path.insert(0,str(HERE))
from offline_render24 import stage30_opcode2_gainmap_reference, demosaic
from test_gainmap30 import envelope, make_gainmap


def main():
    h,w=22,26
    black=64.;white=1023.
    # Source RAW is packed scene values at the four RGGB sites. These numbers
    # are wholly synthetic, not extracted from an actual phone/DNG frame.
    src=np.empty((h,w),dtype=np.uint16)
    src[::2,::2]=255
    src[::2,1::2]=420
    src[1::2,::2]=420
    src[1::2,1::2]=680
    k=[1.2,1.1,.9,.75]
    op=[]
    for (ry,rx),factor in zip(((0,0),(0,1),(1,0),(1,1)),k):
        op.append((9,b'\x01\x03\0\0',0,
                   make_gainmap(shape=(h,w),region=(ry,rx,h,w),pitch=(2,2),
                       gain_values=np.full((2,2),factor,dtype=np.float32))))
    blob=envelope(op)
    meta={'black':black,'white':white}
    frame,receipt=stage30_opcode2_gainmap_reference(src,meta,blob)
    red=(255-black)/(white-black)*k[0]
    green=(420-black)/(white-black)
    blue=(680-black)/(white-black)*k[3]
    assert frame.shape==(h,w,3) and frame.dtype==np.float32
    roi=frame[2:-2,2:-2]
    assert np.allclose(roi[:,:,0],red,atol=2e-6)
    assert np.allclose(roi[:,:,2],blue,atol=2e-6)
    assert np.allclose(roi[::2,::2,1],green*(k[1]+k[2])/2,atol=2e-6)
    assert np.allclose(roi[1::2,1::2,1],green*(k[1]+k[2])/2,atol=2e-6)
    assert np.allclose(roi[::2,1::2,1],green*k[1],atol=2e-6)
    assert np.allclose(roi[1::2,::2,1],green*k[2],atol=2e-6)
    assert receipt['gainmap_count']==4
    assert receipt['gain_applied_before_demosaic'] is True
    assert receipt['SDK_bit_exact_parity_proven'] is False
    # Baseline code remains callable and returns uint16 samples unchanged.
    baseline=demosaic(src,black,white)
    assert baseline.dtype==np.uint16 and baseline.shape==(h,w,3)
    assert np.array_equal(src[::2,::2],np.full((h//2,w//2),255,np.uint16))
    msg={'schema':'hasselblad-stage30-stage24-integration-synthetic-v1',
         'status':'PASS', 'checks_passed':7, 'real_dng_processed':False,
         'stage24_original_demosaic_untouched':True,
         'original_x2d_isp_equivalence':False,'original_phone_JPEG_modified':False,
         'gainmap_applied_before_float_demosaic':True}
    print(json.dumps(msg,sort_keys=True))
    return msg

if __name__=='__main__':main()
