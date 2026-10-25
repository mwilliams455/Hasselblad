#!/usr/bin/env python3
"""Privately compare actual assembled-band samples exported by the Stage76 Android APK."""
import argparse,json,sys,tempfile,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phocus_device_stage75'))
from device75 import host,render
import struct
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);a=p.parse_args()
with tempfile.TemporaryDirectory() as temp,zipfile.ZipFile(a.archive) as z:
 if sum(i.file_size for i in z.infolist())>64*1024*1024:raise ValueError('Export too large')
 if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate entries')
 report=json.loads(z.read('report.json'));assert report['schema']=='hasselblad-stage76-scene-v1'
 assert 1<=len(report['samples'])<=3
 dll=host(Path(temp));results=[]
 for item in report['samples']:
  assert item['cfa']=='RGGB' and item['halo']==32 and item['width']==64 and item['height']==64 and item['input_stride']==128
  prefix=item['prefix'];payload=z.read(prefix+'.input.u16le');actual=z.read(prefix+'.rgb.u16le')
  expected=render(dll,payload,64,64,128);assert len(actual)==len(expected)
  x=struct.unpack('<12288H',expected);y=struct.unpack('<12288H',actual);diff=[i for i,(a,b) in enumerate(zip(x,y)) if a!=b]
  results.append({'sample':prefix,'channels':len(x),'changed':len(diff),'max_difference':max(abs(a-b) for a,b in zip(x,y)),'first_channel_index':diff[0] if diff else None})
  if diff:break
 ok=all(r['changed']==0 for r in results) and len(results)==len(report['samples'])
 print(json.dumps({'status':'PASS_EXACT' if ok else 'FAIL','scope':'Exported assembled-band windows against unchanged Stage74 using identical Bayer bytes','results':results,'full_image_vendor_parity_proved':False},indent=2))
 sys.exit(0 if ok else 1)
