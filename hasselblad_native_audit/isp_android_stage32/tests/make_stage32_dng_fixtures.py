#!/usr/bin/env python3
"""Create synthetic classic DNG-like RGGB TIFF fixtures; never upload photos."""
from __future__ import annotations
import argparse
import struct
from pathlib import Path

W=64; H=64
FMT={'B':1,'H':3,'I':4,'R':5,'S':10,'U':7}

def make_gains(reverse=False):
    chunks=[]
    for ry,rx,gain in [(0,0,2.0),(0,1,1.1),(1,0,1.2),(1,1,1.5)]:
        header=struct.pack('>10I4dI',ry,rx,H,W,0,1,2,2,2,2,
                           1.,1.,0.,0.,1)
        payload=header+struct.pack('>4f',*(gain for _ in range(4)))
        chunks.append(struct.pack('>I4sII',9,b'\x01\x03\x00\x00',0,len(payload))+payload)
    if reverse:chunks.reverse()
    return struct.pack('>I',len(chunks))+b''.join(chunks)

def mktags(gains=False,big_endian=False,bad_cfa=False,broken_strip=False,
           unknown_opcode=False,dual_mismatch=False):
    order='>' if big_endian else '<'
    def short(n):return struct.pack(order+'H',n)
    def longs(*vals):return struct.pack(order+str(len(vals))+'I',*vals)
    def rats(*vals):return b''.join(struct.pack(order+'ii',int(round(float(v)*10000)),10000) for v in vals)
    fm=[0.9642,0.,0.,0.,1.,0.,0.,0.,0.8249]
    second=fm.copy()
    if dual_mismatch:second[0]=0.90
    tags={
        256:(3,1,short(W)),257:(3,1,short(H)),258:(3,1,short(16)),
        259:(3,1,short(1)),262:(3,1,short(32803)),
        273:(4,1,longs(0)),277:(3,1,short(1)),
        278:(4,1,longs(H)),279:(4,1,longs(W*H*2)),
        284:(3,1,short(1)),
        33421:(3,2,short(2)+short(2)),
        33422:(1,4,bytes([0,1,1,2 if not bad_cfa else 1])),
        50706:(1,4,bytes([1,4,0,0])),
        50714:(5,4,b''.join(struct.pack(order+'II',v,1) for v in (64,65,66,67))),
        50717:(3,1,short(1023)),
        50964:(10,9,rats(*fm)),50965:(10,9,rats(*second)),
        50728:(5,3,b''.join(struct.pack(order+'II',1,1) for _ in range(3)))
    }
    if gains or unknown_opcode:
        op=bytearray(make_gains())
        if unknown_opcode: struct.pack_into('>I',op,4,12)
        tags[51009]=(7,len(op),bytes(op))
    return tags

def build(target:Path,**flags):
    target.parent.mkdir(parents=True,exist_ok=True)
    order='>' if flags.get('big_endian') else '<'
    def pack(fmt,*v):return struct.pack(order+fmt,*v)
    tags=mktags(**flags)
    ifd_start=8
    # layout: IFD and offset-backed values then strip
    n=len(tags)
    data_base=ifd_start+2+n*12+4
    payload=bytearray(); entries=[]
    for tag,(ty,count,val) in sorted(tags.items()):
        if len(val)<=4:
            field=val.ljust(4,b'\0')
        else:
            while (data_base+len(payload))%4:payload.append(0)
            field=pack('I',data_base+len(payload));payload.extend(val)
        entries.append([tag,ty,count,field])
    while (data_base+len(payload))%4:payload.append(0)
    strip_offset=data_base+len(payload)
    index=next(i for i,e in enumerate(entries) if e[0]==273)
    entries[index][3]=pack('I',strip_offset if not flags.get('broken_strip') else strip_offset+W*H*2*2)
    out=bytearray(b'MM' if flags.get('big_endian') else b'II')
    out.extend(pack('HI',42,ifd_start))
    out.extend(pack('H',len(entries)))
    for tag,ty,count,field in entries:
        out.extend(pack('HHI',tag,ty,count));out.extend(field)
    out.extend(pack('I',0));out.extend(payload)
    assert len(out)==strip_offset
    for y in range(H):
        for x in range(W):
            c=((y&1)<<1)|(x&1)
            v=(300,400,450,500)[c]
            out.extend(pack('H',v))
    target.write_bytes(out)
    return target

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    for k,f in {
        'plain':{},'gains':{'gains':True},
        'big':{'big_endian':True,'gains':True},
        'bad_cfa':{'bad_cfa':True},
        'bad_strip':{'broken_strip':True},
        'unsupported_opcode':{'unknown_opcode':True},
        'dual_mismatch':{'dual_mismatch':True},
    }.items():build(args.out/(k+'.dng'),**f)
    print('generated 7 synthetic fixtures; bytes=',sum(p.stat().st_size for p in args.out.glob('*.dng')))

if __name__=='__main__':main()
