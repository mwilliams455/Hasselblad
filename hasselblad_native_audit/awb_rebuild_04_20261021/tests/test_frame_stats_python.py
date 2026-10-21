#!/usr/bin/env python3
"""Independent C-vs-Python oracle, plus optional private Native1C DNG fixture.

Source-backed: 32x32=1024 and brightness preservation, original RAW black.
NOT source-backed: bin mapping, provisional Bayer aggregation or weighting.
No captured RAW/stat arrays are stored in the repository or stdout.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
LIB=ctypes.CDLL(str(ROOT/'build/libhbstages.so'))

class Frame(ctypes.Structure):
    _fields_=[('width',ctypes.c_uint32),('height',ctypes.c_uint32),
              ('row_stride_bytes',ctypes.c_uint32),('pixel_stride_bytes',ctypes.c_uint32),
              ('left',ctypes.c_uint32),('top',ctypes.c_uint32),
              ('right',ctypes.c_uint32),('bottom',ctypes.c_uint32),
              ('cfa',ctypes.c_int),('black_q16',ctypes.c_int64*4),('white_code',ctypes.c_uint16)]
class Block(ctypes.Structure):
    _fields_=[('site_sum_q16',ctypes.c_int64*4),('site_count',ctypes.c_uint32*4),
              ('raw_brightness_sum_q16',ctypes.c_int64),('sample_count',ctypes.c_uint32),
              ('at_or_above_white_count',ctypes.c_uint32),('above_white_count',ctypes.c_uint32),
              ('at_or_below_black_count',ctypes.c_uint32),
              ('min_sample',ctypes.c_uint16),('max_sample',ctypes.c_uint16)]
class Stats(ctypes.Structure):
    _fields_=[('blocks',Block*1024),('input_sample_count',ctypes.c_uint64),
              ('vendor_e2_equivalence_proven',ctypes.c_uint8)]
LIB.hb_awb_raw_to_block_stats.argtypes=(ctypes.POINTER(ctypes.c_uint8),ctypes.c_size_t,
                                          ctypes.POINTER(Frame),ctypes.POINTER(Stats))
LIB.hb_awb_raw_to_block_stats.restype=ctypes.c_int

MAP=((0,1,2,3),(1,0,3,2),(2,3,0,1),(3,2,1,0))

def calc_oracle(raw,frame):
    # Independent full reference, indexing Bayer quads directly. This reference
    # is NOT Hasselblad's original E2 statistics manager.
    x0,y0,x1,y1=frame.left,frame.top,frame.right,frame.bottom
    hh,ww=(y1-y0)//2,(x1-x0)//2
    xb=np.array([(i*ww+31)//32 for i in range(32)],dtype=int)
    yb=np.array([(i*hh+31)//32 for i in range(32)],dtype=int)
    output={'sum':np.zeros((1024,4),np.int64), 'count':np.zeros((1024,4),np.int64),
            'atwhite':np.zeros(1024,np.int64), 'above':np.zeros(1024,np.int64),
            'below':np.zeros(1024,np.int64),'min':np.full(1024,65535,np.uint16),
            'max':np.zeros(1024,np.uint16)}
    def reduce32(arr):
        return np.add.reduceat(np.add.reduceat(arr,yb,axis=0),xb,axis=1).reshape(-1)
    for dy in range(2):
        for dx in range(2):
            physical=((y0+dy)&1)*2+((x0+dx)&1)
            colour=MAP[frame.cfa][physical]
            site=raw[y0+dy:y1:2,x0+dx:x1:2]
            assert site.shape==(hh,ww)
            signed=site.astype(np.int64)*65536-frame.black_q16[physical]
            output['sum'][:,colour]=reduce32(signed)
            output['count'][:,colour]=reduce32(np.ones((hh,ww),np.int64))
            output['atwhite']+=reduce32((site>=frame.white_code).astype(np.int64))
            output['above']+=reduce32((site>frame.white_code).astype(np.int64))
            output['below']+=reduce32((site.astype(np.int64)*65536<=frame.black_q16[physical]).astype(np.int64))
            # Reduce min/max on each 32x32 bounded block.
            for by in range(32):
                for bx in range(32):
                    idx=by*32+bx
                    tile=site[yb[by]:yb[by+1] if by<31 else hh,
                              xb[bx]:xb[bx+1] if bx<31 else ww]
                    output['min'][idx]=min(output['min'][idx],np.min(tile))
                    output['max'][idx]=max(output['max'][idx],np.max(tile))
    return output


def check(arr,black,white,cfa,crop,pixel_stride=2,pad=0):
    h,w=arr.shape
    stride=w*pixel_stride+pad
    row_data=np.zeros((h,stride),dtype=np.uint8)
    row_data[:,0:w*pixel_stride:pixel_stride]=(arr&255).astype(np.uint8)
    row_data[:,1:w*pixel_stride:pixel_stride]=(arr>>8).astype(np.uint8)
    f=Frame(w,h,stride,pixel_stride,*crop,cfa,(ctypes.c_int64*4)(*black),white)
    obj=Stats()
    backing=(ctypes.c_uint8*row_data.nbytes).from_buffer(row_data)
    assert LIB.hb_awb_raw_to_block_stats(backing,row_data.nbytes,ctypes.byref(f),ctypes.byref(obj))==0
    assert obj.input_sample_count==(crop[2]-crop[0])*(crop[3]-crop[1])
    assert obj.vendor_e2_equivalence_proven==0
    expected=calc_oracle(arr,f)
    got_sums=np.array([list(b.site_sum_q16) for b in obj.blocks],np.int64)
    got_counts=np.array([list(b.site_count) for b in obj.blocks],np.int64)
    assert np.array_equal(got_sums,expected['sum']), 'colour site Q16 sums'
    assert np.array_equal(got_counts,expected['count']), 'site counts'
    assert np.array_equal(np.array([b.raw_brightness_sum_q16 for b in obj.blocks],np.int64),
                          expected['sum'].sum(axis=1)), 'brightness preserved'
    assert np.array_equal(np.array([b.sample_count for b in obj.blocks],np.int64),
                          expected['count'].sum(axis=1)), 'pixel counts'
    for label,field in [('atwhite','at_or_above_white_count'),('above','above_white_count'),('below','at_or_below_black_count'),
                        ('min','min_sample'),('max','max_sample')]:
        assert np.array_equal(np.array([getattr(b,field) for b in obj.blocks]),expected[label]),label
    return obj


def run():
    p=argparse.ArgumentParser()
    p.add_argument('--private-dng',default=None)
    p.add_argument('--report',default=None)
    args=p.parse_args()
    rng=np.random.default_rng(20261021)
    cases=0
    for i in range(64):
        w=int(rng.integers(34,83))*2
        h=int(rng.integers(34,73))*2
        crop_left=int(rng.integers(0,2))*2
        crop_top=int(rng.integers(0,2))*2
        x1=w-int(rng.integers(0,2))*2
        y1=h-int(rng.integers(0,2))*2
        if x1-crop_left<64 or y1-crop_top<64:continue
        data=rng.integers(0,1400,size=(h,w),dtype=np.uint16)
        blacks=[int(rng.integers(55,80))*65536+int(rng.integers(0,16))*4096 for _ in range(4)]
        check(data,blacks,1023,i%4,(crop_left,crop_top,x1,y1),pixel_stride=2+(i%3),pad=i%7)
        cases+=1
    real=None
    if args.private_dng:
        import tifffile
        path=Path(args.private_dng)
        with tifffile.TiffFile(path) as t:
            pg=t.pages[0]
            arr=pg.asarray()
            assert arr.dtype==np.uint16 and arr.ndim==2
            assert bytes(pg.tags['CFAPattern'].value)==bytes([0,1,1,2])
            black=tuple(int(v)*65536 for v in pg.tags['BlackLevel'].value)
            white=int(pg.tags['WhiteLevel'].value)
            assert len(black)==4
            crop=(0,0,arr.shape[1],arr.shape[0])
            check(arr,black,white,0,crop)
            real={'fixture':'Native1C private capture DNG','capture_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'dimensions':[arr.shape[1],arr.shape[0]],'raw_sites':int(arr.size),'grid':[32,32],
                  'blocks_independently_compared':1024,'all_four_channel_sums_exact':True,
                  'brightness_and_guard_counts_exact':True,'white_code':white,
                  'black_level_codes':[v//65536 for v in black],
                  'pixel_data_in_report':False}
    result={'checkpoint':'AWB_REBUILD_02','host_synthetic_random_frames':cases,
            'oracle':'independent NumPy integer reduction and min/max, NOT vendor AWB',
            'real_capture':real,'original_firmware_compared':False,
            'vendor_E2_equivalence_proven':False,'status':'PASS'}
    if args.report:Path(args.report).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':run()