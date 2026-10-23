#!/usr/bin/env python3
"""Synthetic DNG fixtures plus independent Stage30 full-frame references."""
import argparse,struct,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'isp_android_stage32/tests'))
sys.path.insert(0,str(ROOT/'isp_dng_stage30/src'))
from make_stage32_dng_fixtures import mktags
from dng_gainmap30 import parse_opcode_list2,apply_gainmaps,demosaic_linear_rg_reference

def build(dest,name,big=False,gains=False,strips=False,orientation=1,mutation=None):
    order='>' if big else '<'
    def pack(fmt,*v):return struct.pack(order+fmt,*v)
    tags=mktags(gains=gains,big_endian=big)
    tags[50713]=(3,2,pack('2H',2,2));tags[274]=(3,1,pack('H',orientation))
    if gains:
        # Spatially varying gain, so ordering/interpolation errors are visible.
        op=bytearray(tags[51009][2]);at=4
        for i in range(4):
            size=struct.unpack_from('>I',op,at+12)[0]
            struct.pack_into('>4f',op,at+16+76,1.+i*.1,1.8,1.2,2.1-i*.1);at+=16+size
        tags[51009]=(7,len(op),bytes(op))
    rows=7 if strips else 64;num=(64+rows-1)//rows
    tags[278]=(4,1,pack('I',rows));tags[273]=(4,num,bytes(num*4))
    sizes=[min(rows,64-i*rows)*128 for i in range(num)]
    tags[279]=(4,num,pack(str(num)+'I',*sizes))
    if mutation=='compressed':tags[259]=(3,1,pack('H',7))
    if mutation=='bad_cfa':tags[33422]=(1,4,bytes([2,1,1,0]))
    if mutation=='crop':tags[50829]=(4,4,pack('4I',2,2,64,64))
    if mutation=='dual':tags[50965]=(10,9,pack('18i',9000,10000,0,1,0,1,0,1,1,1,0,1,0,1,0,1,8249,10000))
    if mutation=='opcode':
        op=bytearray(tags[51009][2]);struct.pack_into('>I',op,4,12);tags[51009]=(7,len(op),bytes(op))
    if mutation=='black_repeat':tags[50713]=(3,2,pack('2H',1,1))
    if mutation=='neutral':tags[50728]=(5,3,pack('6I',0,1,1,1,1,1))
    if mutation=='linearization':tags[50712]=(3,2,pack('2H',0,1023))
    if mutation=='layout':tags[50711]=(3,1,pack('H',2))
    def layout(tags):
        base=8+2+len(tags)*12+4;payload=bytearray();entries=[]
        for tag,(ty,count,val) in sorted(tags.items()):
            if len(val)<=4:field=val.ljust(4,b'\0')
            else:
                while (base+len(payload))%4:payload.append(0)
                field=pack('I',base+len(payload));payload.extend(val)
            entries.append(pack('HHI',tag,ty,count)+field)
        while (base+len(payload))%4:payload.append(0)
        return (b'MM' if big else b'II')+pack('HIH',42,8,len(entries))+b''.join(entries)+pack('I',0)+payload
    head=layout(tags);start=len(head)
    offsets=[];cursor=start
    for size in sizes:offsets.append(cursor);cursor+=size+8
    if mutation=='strip':offsets[-1]=cursor+100
    tags[273]=(4,num,pack(str(num)+'I',*offsets));head=layout(tags)
    raw=np.random.default_rng(43).integers(0,1100,(64,64),dtype=np.uint16)
    data=bytearray(head)
    for i in range(num):data.extend(raw[i*rows:min((i+1)*rows,64)].astype(order+'u2').tobytes());data.extend(bytes(8))
    (dest/(name+'.dng')).write_bytes(data)
    if mutation is None:
        black=np.tile(np.array([[64,65],[66,67]],np.float32),(32,32))
        normalized=(raw.astype(np.float32)-black)/(1023-black)
        if gains:normalized,_=apply_gainmaps(normalized,parse_opcode_list2(tags[51009][2],raw.shape))
        rgb=demosaic_linear_rg_reference(normalized)
        for limit,step in ((4096,1),(512,3)):
            pixels=np.floor(np.clip(rgb[::step,::step],0,1)*65535).astype('<u2')
            (dest/(name+'-'+str(limit)+'.rgb16')).write_bytes(pixels.tobytes())

def profile():
    p=np.zeros(38);p[1]=1;p[9]=p[13]=p[17]=999;p[18]=2;p[21:26]=1
    p[28]=p[32]=p[36]=p[37]=1
    curve=np.arange(65536,dtype='<f4')+.25;curve[-1]=65535
    b=b'HB43LUT1'+struct.pack('<6i',2,2,4000,0,1,0)+p.astype('<f8').tobytes()+bytes(64)+curve.tobytes()
    return b+hashlib.sha256(b).digest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    for name,args in {'plain':{},'gains':{'gains':True},'big_multistrip':{'big':True,'strips':True,'gains':True,'orientation':8},'rotate3':{'orientation':3},'rotate6':{'orientation':6}}.items():build(a.out,name,**args)
    for bad in ('compressed','bad_cfa','crop','dual','opcode','black_repeat','neutral','linearization','layout','strip'):
        build(a.out,'bad_'+bad,gains=True,mutation=bad)
    (a.out/'synthetic.hbc').write_bytes(profile())
    print('Created synthetic Stage43 fixtures; no photo or private profile data')
if __name__=='__main__':main()
