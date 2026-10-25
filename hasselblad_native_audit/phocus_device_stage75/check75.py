#!/usr/bin/env python3
import argparse,importlib.util,os,shutil,struct,subprocess,sys,tempfile,zipfile,json,hashlib
from pathlib import Path
from device75 import ROOT,host,fixtures,render,compare,synthetic
AUDIT=ROOT/'hasselblad_native_audit';JAVA=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
sys.path.insert(0,str(AUDIT/'isp_android_stage32/tests'))
from make_stage32_dng_fixtures import mktags
F=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
def fixture(dest,case,bad=None):
    w,h=224,208;big=case%2==1;order='>' if big else '<';pack=lambda fmt,*v:struct.pack(order+fmt,*v)
    tags=mktags(big_endian=big);tags[256]=(4,1,pack('I',w));tags[257]=(4,1,pack('I',h))
    identity=[1,0,0,0,1,0,0,0,1]
    for tag in (50721,50722):tags[tag]=(10,9,b''.join(pack('ii',v,1) for v in identity))
    tags[50778]=(3,1,pack('H',21));tags[50779]=(3,1,pack('H',17))
    tags[50713]=(3,2,pack('2H',2,2));tags[274]=(3,1,pack('H',[1,3,6,8][case]));black=[64,65,66,67]
    if case==3:black=[32,80,48,96];tags[50714]=(5,4,b''.join(pack('II',v,1) for v in black))
    maps=[]
    if case:
        for phase in range(4):maps.append((phase,[F(.5+phase*.125),F(1.75),F(1.25),F(2.25)]))
        if case>=2:maps.extend([(0,[2.0]*4),(0,[.5]*4)])
        chunks=[]
        for phase,grid in maps:
            payload=struct.pack('>10I4dI',phase//2,phase%2,h,w,0,1,2,2,2,2,1.,1.,0.,0.,1)+struct.pack('>4f',*grid)
            chunks.append(struct.pack('>I4sII',9,bytes([1,3,0,0]),0,len(payload))+payload)
        op=struct.pack('>I',len(chunks))+b''.join(chunks);tags[51009]=(7,len(op),op)
    rows=13 if big else h;n=(h+rows-1)//rows;sizes=[min(rows,h-i*rows)*w*2 for i in range(n)]
    tags[278]=(4,1,pack('I',rows));tags[273]=(4,n,bytes(n*4));tags[279]=(4,n,pack(str(n)+'I',*sizes))
    if bad=='bad_cfa':tags[33422]=(1,4,bytes([2,1,1,0]))
    if bad=='compressed':tags[259]=(3,1,pack('H',7))
    if bad=='crop':tags[50829]=(4,4,pack('4I',2,2,h,w))
    if bad=='small':tags[256]=(4,1,pack('I',64))
    if bad=='opcode':tags[51009]=(7,20,struct.pack('>5I',1,12,0,0,0))
    if bad=='dual':tags[50965]=(10,9,pack('18i',1,1,0,1,0,1,0,1,1,1,0,1,0,1,0,1,1,1))
    if bad=='white':tags[50717]=(3,1,pack('H',10))
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
    tags[273]=(4,n,pack(str(n)+'I',*offsets));data=bytearray(layout())
    def raw(y,x):return (x*191+y*67+(x*y)%327)%1100
    for strip in range(n):
        for y in range(strip*rows,min((strip+1)*rows,h)):
            data.extend(pack(str(w)+'H',*[raw(y,x) for x in range(w)]))
        data.extend(bytes(8))
    name=bad or 'case'+str(case);(dest/(name+'.dng')).write_bytes(data[:100] if bad=='short_file' else data)
    if bad:return
    for region in range(5):
        x,y=((w-64)//2)&~1,((h-64)//2)&~1
        if region:x=32 if region in (1,3) else (w-96)&~1;y=32 if region in (1,2) else (h-96)&~1
        out=[]
        for yy in range(y-32,y+96):
            for xx in range(x-32,x+96):
                phase=(yy%2)*2+xx%2;v=max(0,min(1,F((raw(yy,xx)-black[phase])/(1023-max(black)))))
                for site,g in maps:
                    if site!=phase:continue
                    dy=(yy+.5)/h;dx=(xx+.5)/w
                    gain=g[0]*(1-dy)*(1-dx)+g[2]*dy*(1-dx)+g[1]*(1-dy)*dx+g[3]*dy*dx
                    v=F(min(v*gain,1))
                out.append(int(F(v*65535)))
        (dest/(name+'-'+str(region)+'.input.u16le')).write_bytes(struct.pack('<'+'H'*len(out),*out))
def run(work,jni):
    work.mkdir(parents=True,exist_ok=True);f=work/'fixtures';f.mkdir(exist_ok=True)
    for i in range(4):fixture(f,i)
    for bad in ('bad_cfa','compressed','crop','short_file','small','opcode','dual','white'):fixture(f,0,bad)
    # Public synthetic profile mirrors the existing Stage43/56 regression fixture format.
    params=[0.0]*38;params[1]=1
    for i in (9,13,17):params[i]=999
    params[18]=2
    for i in range(21,26):params[i]=1
    for i in (28,32,36,37):params[i]=1
    body=b'HB56LUT1'+struct.pack('<6i',2,2,4000,0,1,0)+struct.pack('<38d',*params)+bytes(64)
    body+=struct.pack('<65536f',*[min(i+.25,65535) for i in range(65536)])
    body+=struct.pack('<4i10d',1,0,2,1,1,0,0,0,1,0,0,0,1,1)+struct.pack('<2i',1,3)
    for anchor,t in enumerate((3000,5500,9000)):body+=struct.pack('<i8d',t,*[(anchor*8+i)/8 for i in range(8)])
    (f/'synthetic75.hbc').write_bytes(body+hashlib.sha256(body).digest())
    dll=host(work);assets=ROOT/'HasselbladPhoton/app/src/main/assets/stage75';fixtures(dll,assets,True)
    # Same source graph as host74 plus the exact JNI bridge.
    import re
    paths=list(dict.fromkeys(AUDIT/p for p in re.findall(r'"\$base/([^"\n]+\.c)"',(AUDIT/'phocus_output_stage74/run_jni_host74.sh').read_text())))
    subprocess.run(['cc','-std=c11','-O2','-shared','-fPIC','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror','-I'+str(jni),'-I'+str(jni/'linux'),*map(str,paths),'-lm','-o',str(work/'libhbfinal74.so')],check=True)
    compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
    classes=work/'classes';classes.mkdir(exist_ok=True)
    subprocess.run(compiler+['--release','17','-d',str(classes),*[str(JAVA/n) for n in ['HasselbladFinalRaw74.java','HasselbladDevice75Buffers.java','HasselbladDngTileReader.java']],str(Path(__file__).with_name('Stage75Check.java'))],check=True)
    subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'Stage75Check',str(assets),str(f)],check=True)
    colour_sources=['phocus_port_stage42/src/hb42_colour.c','phocus_highlight_stage53/highlight53.c',
        'phocus_post_stage55/post55.c','isp_dng_stage18/src/hb_dng_pcs_bridge.c','isp_colour_stage19/src/hb_colour_stage19.c']
    includes=[jni,jni/'linux',*[AUDIT/Path(path).parent for path in colour_sources]]
    subprocess.run(['cc','-std=c11','-O2','-shared','-fPIC','-ffp-contract=off','-Wall','-Wextra','-Werror',
        *['-I'+str(p) for p in includes],str(ROOT/'HasselbladPhoton/app/src/main/cpp/hasselblad/hb_renderer42_jni.c'),
        *[str(AUDIT/p) for p in colour_sources],'-lm','-o',str(work/'libhasselblad_renderer42_jni.so')],check=True)
    subprocess.run(compiler+['--release','17','-cp',str(classes),'-d',str(classes),
        *[str(JAVA/(name+'.java')) for name in ('HasselbladRenderer42','HasselbladProfile43','HasselbladIlluminant56')],
        str(Path(__file__).with_name('Stage75ColourCheck.java'))],check=True)
    subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'Stage75ColourCheck',str(f)],check=True)
    # Verify the downstream comparator detects corruption, including unsigned high-bit channels.
    item={'name':'colour64','width':64,'height':64};source=synthetic('colour64',64,64);rgb=render(dll,source,64,64,128)
    for corrupt in (False,True):
        archive=work/('corrupt.zip' if corrupt else 'exact.zip')
        data=bytearray(rgb)
        if corrupt:data[3]^=128
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('report.json',json.dumps({'schema':'hasselblad-stage75-device-v1','fixtures':[item]}));z.writestr('colour64.input.u16le',source);z.writestr('colour64.rgb.u16le',data)
        result=compare(dll,archive);assert result['status']==('FAIL' if corrupt else 'PASS_EXACT')
        if corrupt:assert result['results'][0]['first_pixel']==0 and result['results'][0]['first_channel']=='G'
    print('STAGE75_COMPARATOR_EXACT_AND_CORRUPTION_PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni',type=Path,required=True);a=p.parse_args();run(a.work.resolve(),a.jni.resolve())
