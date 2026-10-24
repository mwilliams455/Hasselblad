#!/usr/bin/env python3
import argparse,hashlib,struct,sys,json
from pathlib import Path
import numpy as np
from reference56 import normalize,temperature,xy_from_temperature,matrix,solve,quantize,ROOT
sys.path.insert(0,str(ROOT/'phocus_boundaries_stage48'))
from make_metadata_fixtures48 import rational,write,mktags,CC,AB

def profile_extension(b,grids,temps):
    body=b'HB56LUT1'+b[8:-32]+struct.pack('<2i',1,3)
    for t,g in zip(temps,grids):body+=struct.pack('<i',int(t))+np.asarray(g,dtype='<f8').tobytes()
    return body+hashlib.sha256(body).digest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(56);rows=[];max_roundtrip=0
    for model in range(8):
        c1=normalize(np.eye(3)+rng.uniform(-.05,.2,(3,3)))
        c2=normalize(c1+rng.uniform(-.04,.04,(3,3)))
        cc=np.eye(3)+rng.uniform(-.015,.04,(3,3));ab=rng.uniform(.7,1.3,3)
        for k in (2000,2400,2850,3050,3550,4500,6500,8000,10000,15000):
            for tint in (-20,0,20):
                xy=xy_from_temperature(k,tint);expected,t=temperature(xy)
                n=matrix(c1,c2,cc,ab,6500,2850,expected)@np.r_[xy,1-xy.sum()]
                for scale in (.125,1,3.7):
                    actual,offset,_=solve(c1,c2,cc,ab,n*scale)
                    max_roundtrip=max(max_roundtrip,abs(actual-expected));assert abs(actual-expected)<1e-7
                    for reverse in (False,True):
                        row=(17,21,c2,c1) if reverse else (21,17,c1,c2)
                        rows.append(struct.pack('>2i',*row[:2])+np.r_[row[2].ravel(),row[3].ravel(),cc.ravel(),ab,n*scale,actual,offset].astype('>f8').tobytes()+struct.pack('>i',quantize(actual)))
    (a.out/'numeric.bin').write_bytes(struct.pack('>i',len(rows))+b''.join(rows))
    # Synthetic profile keeps existing legacy payload and adds synthetic route and LUT data.
    b=a.legacy.read_bytes();body=b'HB55LUT1'+b[8:-32]+struct.pack('<4i10d',1,0,2,1,*np.eye(3).ravel(),1)
    previous=body+hashlib.sha256(body).digest();(a.out/'synthetic55.hbc').write_bytes(previous)
    grids=np.arange(24,dtype=float).reshape(3,8)/8
    (a.out/'synthetic56.hbc').write_bytes(profile_extension(previous,grids,[3000,5500,9000]))
    c1=normalize(np.array([[.9,.1,.05],[.1,.85,.05],[.03,.15,.8]]));c2=normalize(c1+np.diag([.1,-.05,.06]));xy=xy_from_temperature(4000,0);neutral=np.rint(matrix(c1,c2,CC,AB,6500,2850,temperature(xy)[0])@np.r_[xy,1-xy.sum()]*1000)
    names=[]
    for name in ('valid','swapped','single','mismatch','missing','bad_count','bad_illuminant','third','short_neutral'):
        tags=mktags(False,False);tags[50713]=(3,2,struct.pack('<2H',2,2));tags[50714]=(3,4,struct.pack('<4H',64,64,64,64))
        tags[50721]=rational(c1);tags[50722]=rational(c2)
        tags[50723]=rational(CC);tags[50724]=rational(CC);tags[50727]=rational(AB,False);tags[50728]=rational(neutral,False)
        tags[50778]=(3,1,struct.pack('<H',21));tags[50779]=(3,1,struct.pack('<H',17))
        if name=='swapped':tags[50721],tags[50722]=tags[50722],tags[50721];tags[50778],tags[50779]=tags[50779],tags[50778]
        if name=='single':tags.pop(50722);tags.pop(50779)
        if name=='mismatch':tags[50931]=(2,2,b'a\0');tags[50932]=(2,2,b'b\0')
        if name=='missing':tags.pop(50721)
        if name=='bad_count':tags[50721]=rational([1,2,3])
        if name=='bad_illuminant':tags[50779]=(3,1,struct.pack('<H',255))
        if name=='third':tags[52529]=(3,1,struct.pack('<H',23))
        if name=='short_neutral':tags[50728]=(3,3,struct.pack('<3H',*neutral.astype(int)))
        write(a.out/(name+'.dng'),tags);names.append(name)
    (a.out/'FIXTURES56.json').write_text(json.dumps({'numeric_cases':len(rows),'synthetic_camera_encodings':8,'metadata_cases':names,'independent_bisection_max_kelvin_error':max_roundtrip,'synthetic_only':True},indent=2)+'\n')
if __name__=='__main__':main()
