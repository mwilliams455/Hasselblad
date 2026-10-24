#!/usr/bin/env python3
import argparse,json,struct,sys
from pathlib import Path
import numpy as np
from reference58 import save_reference,COUNTERS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'isp_android_stage32/tests'))
from make_stage32_dng_fixtures import mktags

def make(path,case):
 big=case%2==1;order='>' if big else '<';pack=lambda fmt,*x:struct.pack(order+fmt,*x)
 tags=mktags(big_endian=big)
 black=[64,65,66,67] if case<4 else ([64]*4 if case<8 else [32,80,48,96])
 if case==11:
  black=[64];tags[50713]=(3,2,pack('2H',1,1))
 else:tags[50713]=(3,2,pack('2H',2,2))
 tags[50714]=(5,len(black),b''.join(pack('II',x,1) for x in black));tags[274]=(3,1,pack('H',(1,3,6,8)[case%4]))
 if case%4:
  chunks=[]
  for phase in range(4):
   grid=[.5,.75,1,1.25] if case%4==2 else [1.0,1.8,1.2,2.1-phase*.1]
   area=struct.pack('>10I4dI',phase//2,phase%2,64,64,0,1,2,2,2,2,1.,1.,0.,0.,1)
   payload=area+struct.pack('>4f',*grid)
   chunks.append(struct.pack('>I4sII',9,bytes([1,3,0,0]),0,len(payload))+payload)
  if case%4==3:
   # Repeated maps on the same site: clipping must precede later attenuation.
   for gain in (2.0,.5):
    payload=struct.pack('>10I4dI',0,0,64,64,0,1,2,2,1,1,1.,1.,0.,0.,1)+struct.pack('>f',gain)
    chunks.append(struct.pack('>I4sII',9,bytes([1,3,0,0]),0,len(payload))+payload)
  op=struct.pack('>I',len(chunks))+b''.join(chunks);tags[51009]=(7,len(op),op)
 raw=np.random.default_rng(5800+case).integers(0,1100,(64,64),dtype=np.uint16)
 # Boundary patches and impulses, independent of photographs.
 raw[:8,:8]=1023;raw[8:16,:8]=1024;raw[16:24,:8]=0;raw[24:32,:8]=1022
 raw[32:40,:8]=64;raw[40:48,:8]=63;raw[48:56,:8]=65;raw[56:,:8]=512
 rows=7 if big else 64;n=(64+rows-1)//rows
 tags[278]=(4,1,pack('I',rows));tags[273]=(4,n,bytes(n*4))
 sizes=[min(rows,64-i*rows)*128 for i in range(n)];tags[279]=(4,n,pack(str(n)+'I',*sizes))
 def layout():
  base=8+2+12*len(tags)+4;payload=bytearray();entries=[]
  for tag,(ty,count,val) in sorted(tags.items()):
   if len(val)<=4:field=val.ljust(4,b'\0')
   else:
    while (base+len(payload))%4:payload.append(0)
    field=pack('I',base+len(payload));payload.extend(val)
   entries.append(pack('HHI',tag,ty,count)+field)
  while (base+len(payload))%4:payload.append(0)
  return (b'MM' if big else b'II')+pack('HIH',42,8,len(tags))+b''.join(entries)+pack('I',0)+payload
 offset=len(layout());offsets=[]
 for size in sizes:offsets.append(offset);offset+=size+8
 tags[273]=(4,n,pack(str(n)+'I',*offsets));data=bytearray(layout())
 for i in range(n):data.extend(raw[i*rows:min((i+1)*rows,64)].astype(order+'u2').tobytes());data.extend(bytes(8))
 path.write_bytes(data)

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 cases=[]
 for i in range(12):
  name='case'+str(i);path=a.out/(name+'.dng');make(path,i)
  for limit in (4096,512,256,1):
   save_reference(path,a.out/(name+'-'+str(limit)),limit);cases.append((name,limit))
 (a.out/'CASES58.json').write_text(json.dumps({'cases':cases,'counters':COUNTERS})+'\n')
 print('Created 48 synthetic RAW-preparation cases')
if __name__=='__main__':main()
