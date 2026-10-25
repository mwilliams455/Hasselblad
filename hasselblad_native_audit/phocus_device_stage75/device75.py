#!/usr/bin/env python3
"""Build independent host Stage74 and generate synthetic fixtures or compare a private device ZIP.
The compare command reads exactly the exported prepared Bayer bytes. It does not establish
phone RAW preparation equivalence to Phocus. Never publish device ZIPs or their contents.
"""
import argparse,ctypes as c,json,os,re,struct,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Plan(c.Structure):
    _fields_=[(s,c.c_int) for s in ('output_width','output_height','source_width','source_height','work_width','work_height','work_stride','crop_x','crop_y','evidence_scope')]
class Settings(c.Structure):
    _fields_=[('cfa',c.c_int),('flags',c.c_uint),('scale_threshold',c.c_double),('edge_gradient_floor',c.c_int),('raw_gradient_floor',c.c_int),('alignment_tail_fill',c.c_uint16)]
def host(work):
    audit=ROOT/'hasselblad_native_audit';source=(audit/'phocus_output_stage74/run_host74.sh').read_text()
    paths=[audit/p for p in re.findall(r'"\$base/([^"\n]+\.c)"',source) if '/test_' not in p]
    paths=list(dict.fromkeys(paths));work.mkdir(parents=True,exist_ok=True);lib=work/'libhb75host.so'
    subprocess.run([os.environ.get('CC','cc'),'-std=c11','-O2','-fPIC','-shared','-fno-fast-math','-ffp-contract=off',*map(str,paths),'-lm','-o',str(lib)],check=True)
    dll=c.CDLL(str(lib));dll.hb73_plan.argtypes=[c.c_int,c.c_int,c.POINTER(Plan)]
    dll.hb74_render_final_bounded.argtypes=[c.POINTER(Plan),c.POINTER(Settings),c.POINTER(c.c_uint16),c.c_size_t,c.c_int,c.POINTER(c.c_uint16),c.c_size_t,c.c_void_p]
    return dll
def render(dll,payload,w,h,stride):
    plan=Plan();status=dll.hb73_plan(w,h,c.byref(plan))
    if status:raise ValueError('Unsupported geometry: '+str(status))
    if not plan.source_width<=stride<=4096 or len(payload)!=plan.source_height*stride*2:raise ValueError('Input contract/length mismatch')
    values=struct.unpack('<'+'H'*(len(payload)//2),payload);source=(c.c_uint16*len(values))(*values);original=bytes(source)
    out=(c.c_uint16*(w*h*3))();settings=Settings(0,0xffff,1.0,32,200,0)
    status=dll.hb74_render_final_bounded(c.byref(plan),c.byref(settings),source,len(values),stride,out,len(out),None)
    if status:raise ValueError('Host render rejected: '+str(status))
    assert bytes(source)==original
    return struct.pack('<'+'H'*len(out),*out)
def synthetic(name,w,h):
    values=[];state=75001
    for y in range(h+64):
        for x in range(w+64):
            if name=='neutral64':v=10000
            elif name=='colour64':
                phase=(y%2)*2+x%2
                v=([3000,16000,16000,44000][phase]+((x//9+y//11)%3)*4000+(x*91+y*37))&65535
            else:state=(1664525*state+1013904223)&0xffffffff;v=state>>16
            values.append(v)
    return struct.pack('<'+'H'*len(values),*values)
def fixtures(dll,dest,check=False):
    dest.mkdir(parents=True,exist_ok=True);items=[]
    for name,w,h in [('neutral64',64,64),('colour64',64,64),('random23',23,31)]:
        data=synthetic(name,w,h);out=render(dll,data,w,h,w+64)
        for suffix,payload in [('input.u16le',data),('rgb.u16le',out)]:
            path=dest/(name+'.'+suffix)
            if check:assert path.read_bytes()==payload,path
            else:path.write_bytes(payload)
        items.append({'name':name,'width':w,'height':h,'output_channels':w*h*3})
    return {'status':'PASS_HOST_FIXTURES','synthetic_only':True,'fixtures':items,'device_tested':False}
def compare(dll,archive):
    results=[]
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist())>4*1024*1024:raise ValueError('ZIP too large')
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate ZIP entries')
        report=json.loads(z.read('report.json'));assert report['schema']=='hasselblad-stage75-device-v1'
        saved='tiles' in report;cases=report.get('tiles',report.get('fixtures',[]));assert 0<len(cases)<=5
        for item in cases:
            prefix=item['prefix'] if saved else item['name'];w,h=item['width'],item['height'];stride=item.get('input_stride',w+64)
            if saved and (item['cfa']!='RGGB' or item['halo']!=32):raise ValueError('Unsupported CFA/halo')
            payload=z.read(prefix+'.input.u16le');actual=z.read(prefix+'.rgb.u16le')
            if not saved and payload!=synthetic(prefix,w,h):raise ValueError('Synthetic input mismatch before output comparison')
            expected=render(dll,payload,w,h,stride)
            if len(actual)!=len(expected):raise ValueError('RGB16 byte length mismatch')
            e=struct.unpack('<'+'H'*(len(expected)//2),expected);a=struct.unpack('<'+'H'*(len(actual)//2),actual)
            differences=[i for i,(x,y) in enumerate(zip(e,a)) if x!=y];first=differences[0] if differences else None
            results.append({'case':prefix,'input_bytes_replayed':len(payload),'channels':len(e),'changed_channels':len(differences),
                'max_difference':max((abs(x-y) for x,y in zip(e,a)),default=0),'first_pixel':None if first is None else first//3,
                'first_channel':None if first is None else 'RGB'[first%3]})
            if differences:break
    ok=all(r['changed_channels']==0 for r in results) and len(results)==len(cases)
    return {'schema':'hasselblad-stage75-host-compare-v1','status':'PASS_EXACT' if ok else 'FAIL',
        'same_exported_prepared_input_used':True,'saved_dng':saved,'input_preparation_independently_validated':False,
        'physical_colour_match_proved':False,'results':results}
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fixtures','check-fixtures','compare']);p.add_argument('path',type=Path);a=p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        dll=host(Path(d));result=compare(dll,a.path) if a.command=='compare' else fixtures(dll,a.path,a.command=='check-fixtures')
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['status'].startswith('PASS') else 1)
if __name__=='__main__':main()
