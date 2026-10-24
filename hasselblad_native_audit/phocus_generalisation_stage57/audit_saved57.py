#!/usr/bin/env python3
"""Independent same-DNG check of the new comparison; no visual parameter fit."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from audit_generalisation57 import profile,Core,trace,port_library,cmm_oracle

def main():
 p=argparse.ArgumentParser()
 for name in ('profile','room','work','safe-receipt'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
 receipt=json.loads((a.room/'SAVED_DNG57.json').read_text());v,curve,matrix,exponent,grid_at=profile(a.profile)
 read=lambda n,d='<u2':np.fromfile(a.room/(n+'.bin'),dtype=d)
 raw=read('raw').reshape(-1,3);params=read('params','<f8');actual=read('colour').reshape(-1,3)
 core=Core(a.work/'core57.so');cp=core.params(params[:9].reshape(3,3),params[9:18].reshape(3,3),grid_at(receipt['selected_lut_temperature']),False,curve,params[18:22])
 expected,_,_=trace(raw,cp,v[28:37].reshape(3,3),v[37]);assert np.array_equal(actual,expected)
 post,table=port_library(a.work);grad=np.empty_like(actual);output=np.empty_like(actual)
 assert post.hb55_gradate(table,actual,len(actual),grad)==0
 assert post.hb55_output_rgb16(grad,len(grad),matrix,exponent,output)==0
 assert np.array_equal(output,read('finished').reshape(-1,3))
 independent=cmm_oracle(grad,matrix,(1.,1,exponent));assert np.array_equal(output,independent)
 receipt.update({'colour_vs_independent_trace_exact_channels':int(actual.size),
  'finishing_vs_host_c_exact_channels':int(output.size),'output_vs_independent_exact_channels':int(output.size),
  'physical_camera_colour_match_validated':False,'source_dng_modified':False,'capture_renderer_changed':False})
 a.safe_receipt.parent.mkdir(parents=True,exist_ok=True);a.safe_receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
