"""Public synthetic DNG fixtures for exact preparation scheduling comparisons."""
import array,math,random,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'isp_android_stage32/tests'))
from make_stage32_dng_fixtures import mktags

def fixture(path,case,large=False):
 w,h=(4096,3072) if large else [(128,128),(257,259),(322,194),(640,480),(8192,129)][case%5]
 big=bool(case%2);order='>' if big else '<';pack=lambda fmt,*v:struct.pack(order+fmt,*v)
 rng=random.Random(7800+case);tags=mktags(big_endian=big)
 tags[256]=(4,1,pack('I',w));tags[257]=(4,1,pack('I',h))
 identity=[1,0,0,0,1,0,0,0,1]
 for tag in (50721,50722):tags[tag]=(10,9,b''.join(pack('ii',v,1) for v in identity))
 tags[50778]=(3,1,pack('H',21));tags[50779]=(3,1,pack('H',17))
 black=[64.25,65.5,66.75,67.] if case%3 else [32.125]
 tags[50713]=(3,2,pack('2H',*( (1,1) if len(black)==1 else (2,2))))
 tags[50714]=(5,len(black),b''.join(pack('II',int(x*8),8) for x in black))
 tags[50717]=(4,1,pack('I',4095 if case%3 else 65535))
 tags[274]=(3,1,pack('H',[1,3,6,8][case%4]))
 chunks=[];count=4 if large else [0,4,6,8,64][case%5]
 for index in range(count):
  phase=index%4;top=phase//2;left=phase%2;bottom=h;right=w
  if index>=4 and index%3==0:top+=16;left+=10;bottom-=7;right-=9
  pv,ph=(13,17) if large else [(1,1),(2,3),(7,5),(3,1)][index%4]
  sv,sh=(1/(pv-1),1/(ph-1)) if large else [(1.,1.),(.17,.13),(4.,4.),(1e-300,1e-300)][index%4]
  ov,oh=(0.,0.) if large else [(-.3,.25),(0.,0.),(.9,-.8),(4.,-4.)][index%4]
  grid=[rng.uniform(.25,3.5) for _ in range(pv*ph)]
  if index>=4 and index%2:grid=[.25]*(pv*ph)
  payload=struct.pack('>10I4dI',top,left,bottom,right,0,1,2,2,pv,ph,sv,sh,ov,oh,1)+struct.pack('>'+str(len(grid))+'f',*grid)
  chunks.append(struct.pack('>I4sII',9,bytes([1,3,0,0]),0,len(payload))+payload)
 if chunks:
  op=struct.pack('>I',len(chunks))+b''.join(chunks);tags[51009]=(7,len(op),op)
 else:tags.pop(51009,None)
 rows=47 if large else (13 if big else h);n=(h+rows-1)//rows;sizes=[min(rows,h-i*rows)*w*2 for i in range(n)]
 tags[278]=(4,1,pack('I',rows));tags[273]=(4,n,bytes(n*4));tags[279]=(4,n,pack(str(n)+'I',*sizes))
 def layout():
  base=8+2+len(tags)*12+4;data=bytearray();entries=[]
  for tag,(ty,count,value) in sorted(tags.items()):
   if len(value)<=4:field=value.ljust(4,b'\0')
   else:
    while (base+len(data))%4:data.append(0)
    field=pack('I',base+len(data));data.extend(value)
   entries.append(pack('HHI',tag,ty,count)+field)
  return (b'MM' if big else b'II')+pack('HIH',42,8,len(tags))+b''.join(entries)+pack('I',0)+data
 cursor=len(layout());offsets=[]
 for size in sizes:offsets.append(cursor);cursor+=size+8
 tags[273]=(4,n,pack(str(n)+'I',*offsets))
 with path.open('wb') as f:
  f.write(layout())
  for strip in range(n):
   for y in range(strip*rows,min((strip+1)*rows,h)):
    values=array.array('H',((x*191+y*67+(x*y)%327)&65535 for x in range(w)))
    if (sys.byteorder=='big')!=big:values.byteswap()
    f.write(values.tobytes())
   f.write(bytes(8))
