#!/usr/bin/env python3
"""Independent Python reference oracle for 32x32 weighted-mask component filtering.
This is not the original firmware, and original neighborhood topology is unknown.
"""
import ctypes
import json
import os
import random
import sys

root=os.path.dirname(os.path.dirname(__file__))
lib=ctypes.CDLL(os.path.join(root,'build','libhbstages.so'))
class Stats(ctypes.Structure):
    _fields_=[('groups_removed',ctypes.c_uint16),('groups_kept',ctypes.c_uint16),('blocks_removed',ctypes.c_uint16),('blocks_kept',ctypes.c_uint16)]
U8x1024=ctypes.c_uint8*1024
lib.hb_awb_prune_small_components.argtypes=(ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint8),ctypes.c_int,ctypes.POINTER(Stats))
lib.hb_awb_prune_small_components.restype=ctypes.c_int


def oracle(mask,adj):
    visited=set();result=[0]*1024; removed=kept=groups_removed=groups_kept=0
    for seed in range(1024):
        if seed in visited or not mask[seed]:continue
        visited.add(seed); q=[seed]
        for k in q:
            x,y=k%32,k//32
            offsets=[(-1,0),(1,0),(0,-1),(0,1)]
            if adj==8: offsets += [(-1,-1),(-1,1),(1,-1),(1,1)]
            for dx,dy in offsets:
                xx,yy=x+dx,y+dy
                if 0<=xx<32 and 0<=yy<32:
                    n=yy*32+xx
                    if n not in visited and mask[n]:q.append(n);visited.add(n)
        if len(q)<=3:removed+=len(q); groups_removed+=1
        else:
            kept+=len(q);groups_kept+=1
            for k in q:result[k]=1
    return result, (groups_removed,groups_kept,removed,kept)


def main():
    rng=random.Random(0x20261021);count=0
    patterns=[0,1,3,6,16,40,128,200,400,800,1024]
    for adj in (4,8):
        for density in patterns:
            for iteration in range(64):
                if density==1024: mask=[1]*1024
                else:
                    mask=[0]*1024
                    for i in rng.sample(range(1024),density):mask[i]=rng.choice([1,2,255])
                actual=U8x1024(*mask);destination=U8x1024(); st=Stats()
                assert lib.hb_awb_prune_small_components(actual,destination,adj,ctypes.byref(st))==0
                expected,stats=oracle(mask,adj)
                assert list(destination)==expected,('bitmap',adj,density,iteration)
                assert (st.groups_removed,st.groups_kept,st.blocks_removed,st.blocks_kept)==stats,(adj,density,iteration)
                count+=1
    print(json.dumps({'status':'PASS','oracle':'independent Python BFS, not vendor firmware','cases':count,'topologies':[4,8],'vendor_comparison':False}))
if __name__=='__main__': main()