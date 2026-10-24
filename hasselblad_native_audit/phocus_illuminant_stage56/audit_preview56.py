#!/usr/bin/env python3
"""Private photograph is an execution fixture, never a parameter-fit target."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
import tifffile
from reference56 import ROOT,solve,quantize
sys.path[:0]=[str(ROOT/'phocus_colour_stage44'),str(ROOT/'phocus_post_stage55')]
from audit_colour44 import Core,trace,diff
from prepare_preview42 import native_photo_sample
from audit_post55 import load_private,Runner55,port_library,cmm_oracle,delta

def main():
 p=argparse.ArgumentParser()
 for n in ('apk','dng','profile','work','safe-receipt'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();paths=[a.apk,a.dng,a.profile];before=[hashlib.sha256(f.read_bytes()).digest() for f in paths]
 host=json.loads((a.work/'HOST_RENDER56.json').read_text())
 def read(name,dtype='<u2'):return np.fromfile(a.work/(name+'.bin'),dtype=dtype)
 with tifffile.TiffFile(a.dng) as doc:
  tags=doc.pages[0].tags
  def rational(code,default=None):
   if code not in tags:return default
   v=np.array(tags[code].value,float).reshape(-1,2);return v[:,0]/v[:,1]
  cc=rational(50723,np.eye(3).ravel()).reshape(3,3)
  sig=lambda code:tags[code].value if code in tags else ''
  if sig(50931)!=sig(50932):cc=np.eye(3)
  assert int(tags[50778].value)==21 and int(tags[50779].value)==17
  k,tint,xy=solve(rational(50721).reshape(3,3),rational(50722).reshape(3,3),cc,
      rational(50727,np.ones(3)),rational(50728))
 assert abs(k-host['metadata_kelvin'])<1e-5 and quantize(k)==host['lut_kelvin']
 b=a.profile.read_bytes();assert b[:8]==b'HB56LUT1' and hashlib.sha256(b[:-32]).digest()==b[-32:]
 w,h,manual,model,film,space=struct.unpack_from('<6i',b,8);assert (model,film,space)==(0,0,0)
 values=np.frombuffer(b,dtype='<f8',count=38,offset=32).copy()
 curve_at=32+304+w*h*16;curve=np.frombuffer(b,dtype='<f4',count=65536,offset=curve_at).copy()
 route_at=curve_at+65536*4
 assert struct.unpack_from('<4i',b,route_at)==(1,0,2,1)
 output_matrix=np.frombuffer(b,dtype='<f8',count=9,offset=route_at+16).reshape(3,3).copy()
 exponent=struct.unpack_from('<d',b,route_at+88)[0]
 params=read('params','<f8');grid=read('grid','<f8').reshape(h,w,2)
 raw=read('input_rgb16').reshape(-1,3);colour=read('auto_rgb16').reshape(-1,3)
 core=Core(a.work/'core56.so');cp=core.params(params[:9].reshape(3,3),params[9:18].reshape(3,3),grid,False,curve,params[18:22])
 traced,_,stats=trace(raw,cp,values[28:37].reshape(3,3),values[37])
 assert np.array_equal(colour,traced) and np.array_equal(colour,core.render(raw,cp))
 print('Whole-frame colour core exact',flush=True)
 elf,private=load_private(a.apk)
 indices=np.unique(np.r_[np.linspace(0,len(raw)-1,1024).astype(int),np.argmax(raw,axis=0)])
 native=native_photo_sample(elf,private,raw[indices],cp,host['lut_kelvin'])
 native_colour=delta(colour[indices],native);assert native_colour['max_abs_difference']==0
 c,table=port_library(a.work);grad=np.empty_like(colour);out=np.empty_like(colour)
 assert c.hb55_gradate(table,colour,len(colour),grad)==0
 assert c.hb55_output_rgb16(grad,len(grad),output_matrix,exponent,out)==0
 assert np.array_equal(grad,read('auto_gradation_rgb16').reshape(-1,3))
 assert np.array_equal(out,read('auto_finished_rgb16').reshape(-1,3))
 independent=delta(out,cmm_oracle(grad,output_matrix,(1.,1,exponent)));assert independent['max_abs_difference']<=1
 r=Runner55(elf,private);r.configure([1.4,1.,.7]);r.process();r.calculate()
 native_grad=r.cpu(colour[indices],1);native_out=r.convert(r.converter(0),native_grad)
 grad_check=delta(grad[indices],native_grad);out_check=delta(out[indices],native_out)
 assert grad_check['max_abs_difference']==0 and out_check['max_abs_difference']<=1
 rgb8=lambda a:((a.astype(np.uint32)+128)//257).astype(np.uint8)
 effect=diff(rgb8(out),rgb8(read('manual_finished_rgb16').reshape(-1,3)))
 for f,old in zip(paths,before):assert hashlib.sha256(f.read_bytes()).digest()==old
 receipt={'schema':'hasselblad-stage56-preview-integration-v1','status':'PASS_EXPERIMENTAL_METADATA_SELECTION',
  'private_host':host,'metadata_vs_independent_bisection_kelvin_error':abs(k-host['metadata_kelvin']),
  'colour_core_vs_independent_trace_exact_channels':int(colour.size),'colour_core_vs_original_cpu_sample':native_colour,
  'gradation_and_output_vs_host_c_exact_channels_each':int(out.size),'gradation_original_cpu_sample':grad_check,
  'output_original_cpu_sample':out_check,'output_independent_all':independent,
  'automatic_vs_manual_8bit_change_not_accuracy_score':effect,'automatic_colour_clipping':stats,
  'manual_temperature':manual,'metadata_temperature_is_physical_lamp_measurement':False,
  'white_balance_changed':False,'scene_fitted_parameters':0,'source_files_unchanged':True,
  'private_arrays_or_input_hashes_exported':False,'capture_renderer_changed':False,'device_tested':False,
  'physical_phone_colour_match_validated':False,'original_raw_graph_reproduced':False,'full_phocus_equivalence':False}
 a.safe_receipt.parent.mkdir(parents=True,exist_ok=True);a.safe_receipt.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
