#!/usr/bin/env python3
"""Audit the complete existing chain without fitting or changing its look.

Synthetic encodings carry equivalent D50 colours at each metadata white point.
Their common clipping ceiling is the current prepared-RGB convention; it is
not a claim about physical sensor saturation. Private arrays stay in --work.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'phocus_colour_stage44'),str(ROOT/'phocus_highlight_stage53'),str(ROOT/'phocus_post_stage55')]
from audit_colour44 import Core,trace,multiply
from highlight53 import Highlight,equal_lower_limit
from audit_post55 import port_library,cmm_oracle,load_private,delta
from audit_highlight53 import HighlightRunner
from prepare_preview42 import native_photo_sample

def rgb8(a):return ((a.astype(np.uint32)+128)//257).astype(np.uint8)
def metric(a,b):
 d=np.abs(a.astype(float)-b.astype(float))
 return {'channels':int(d.size),'max_abs_rgb8':float(d.max()),'mean_abs_rgb8':float(d.mean()),
         'p95_abs_rgb8':float(np.percentile(d,95)),'pixels_over_2_codes_pct':float(np.mean(d.max(-1)>2)*100)}

def unclipped_domain(source,p,grid):
 yc=multiply(source,p.first);Y=yc[:,0];coords=yc[:,1:]/np.where(Y>0,Y,1)[:,None]*32+[20,32]
 inside=(Y>0)&np.all((coords>0)&(coords<np.array([p.width-1,p.height-1])),axis=1)
 xy=np.clip(coords,0,[p.width-1,p.height-1]);x,y=xy.T;x0=x.astype(int);y0=y.astype(int)
 x1=np.minimum(x0+1,p.width-1);y1=np.minimum(y0+1,p.height-1);dx=(x-x0)[:,None];dy=(y-y0)[:,None]
 chroma=((grid[y0,x0]*(1-dx)+grid[y0,x1]*dx)*(1-dy)+(grid[y1,x0]*(1-dx)+grid[y1,x1]*dx)*dy)/32
 s=np.array(p.shadow);weight=np.clip(np.where(Y>s[0],1,(s[1]*Y+s[2])*Y+s[3]),0,1)
 chroma*=Y[:,None]*weight[:,None];K=np.array(p.second).reshape(3,3)
 linear=np.stack([(Y+K[c,1]*chroma[:,0])+K[c,2]*chroma[:,1] for c in range(3)],-1)
 return inside&np.all((linear>0)&(linear<65535),axis=1)

def profile(path):
 b=path.read_bytes();assert b[:8]==b'HB56LUT1' and hashlib.sha256(b[:-32]).digest()==b[-32:]
 w,h,manual,model,film,space=struct.unpack_from('<6i',b,8);assert (model,film,space)==(0,0,0)
 v=np.frombuffer(b,'<f8',38,32).copy();at=336+w*h*16;curve=np.frombuffer(b,'<f4',65536,at).copy();at+=65536*4
 assert struct.unpack_from('<4i',b,at)==(1,0,2,1)
 matrix=np.frombuffer(b,'<f8',9,at+16).reshape(3,3).copy();exponent=struct.unpack_from('<d',b,at+88)[0];at+=96
 assert struct.unpack_from('<2i',b,at)==(1,3);at+=8;temps=[];grids=[]
 for _ in range(3):
  temps.append(struct.unpack_from('<i',b,at)[0]);at+=4
  grids.append(np.frombuffer(b,'<f8',w*h*2,at).reshape(h,w,2).copy());at+=w*h*16
 assert at==len(b)-32
 def grid(k):
  k=max(2000,min(10000,k));i=0 if k<temps[1] else 1
  return grids[i]+(grids[i+1]-grids[i])*((k-temps[i])/(temps[i+1]-temps[i]))
 return v,curve,matrix,exponent,grid

def public_receipt(result,work):
 """Retain detailed diagnostic rows privately; publish compact aggregate evidence."""
 result=dict(result)
 if 'app_code_changed' in result:result['rendering_primitives_changed']=result.pop('app_code_changed')
 host=result['host_execution']
 if 'app_code_changed' in host:host['renderer_code_changed']=host.pop('app_code_changed')
 (work/'PRIVATE_GENERALISATION_FULL57.json').write_text(json.dumps(result,indent=2)+'\n')
 rows=result.pop('highlight_effects');neutrals=result.pop('neutral_ramps')
 result['highlight_effect_summary']={
  'all_cases_mean_abs_rgb8':float(np.mean([r['highlight_vs_no_highlight']['mean_abs_rgb8'] for r in rows])),
  'all_cases_pixels_over_two_codes_pct':float(np.mean([r['highlight_vs_no_highlight']['pixels_over_2_codes_pct'] for r in rows])),
  'largest_strictly_interior_rgb8_difference':max(r['gamut_interior_highlight_effect']['max_abs_rgb8'] for r in rows),
  'strict_interior_definition':'both outputs 8..247, both LUT coordinates strictly in bounds, both pre-film RGB strictly 0..65535'}
 result['neutral_ramp_summary']={'cases':len(neutrals),'without_highlight_max_channel_spread':max(r['plain_max_channel_spread'] for r in neutrals),
  'with_highlight_max_channel_spread':max(r['highlight_max_channel_spread'] for r in neutrals)}
 return result

def main():
 p=argparse.ArgumentParser()
 for n in ('fixtures','render','profile','work','safe-receipt'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--apk',type=Path);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
 before=hashlib.sha256(a.profile.read_bytes()).digest();v,curve,matrix,exponent,grid_at=profile(a.profile)
 fixture=json.loads((a.fixtures/'CASES57.json').read_text());cases=fixture['cases'];groups=np.fromfile(a.fixtures/'groups.bin','<i4')
 targets=np.fromfile(a.fixtures/'targets.bin','<f8').reshape(-1,3)
 core=Core(a.work/'core57.so');post,table=port_library(a.work)
 def read(case,name,dtype='<u2'):return np.fromfile(a.render/('case_%03d'%case['id'])/(name+'.bin'),dtype=dtype)
 outputs={};rows=[];highlight_max=0;trace_max=0;post_max=0;independent_output_max=0;channels=0;neutral_records=[];worst=None;interior_worst=None
 for case in cases:
  raw=read(case,'raw').reshape(-1,3);hi=read(case,'highlight_input').reshape(-1,3)
  n=np.array(case['neutral']);gains=n.min()/n;lim=np.sort(gains)[0]==np.sort(gains)[1]
  expected=equal_lower_limit(raw/65535,gains) if lim else Highlight.prepare(gains).convert(raw/65535)
  expected=np.floor(np.clip(expected,0,1)*65535+.5).astype(np.uint16)
  difference=int(np.max(np.abs(hi.astype(int)-expected.astype(int))));highlight_max=max(highlight_max,difference);assert difference<=1
  grid=grid_at(case['expected_lut_kelvin'])
  pair=[];domains=[]
  for name,source in (('plain',raw),('highlight',hi)):
   params=read(case,name+'_params','<f8');cp=core.params(params[:9].reshape(3,3),params[9:18].reshape(3,3),grid,False,curve,params[18:22])
   colour=read(case,name+'_colour').reshape(-1,3);traced,_,_=trace(source,cp,v[28:37].reshape(3,3),v[37])
   assert np.array_equal(colour,core.render(source,cp))
   err=int(np.max(np.abs(colour.astype(int)-traced.astype(int))));trace_max=max(trace_max,err);assert err==0
   grad=np.empty_like(colour);out=np.empty_like(colour)
   assert post.hb55_gradate(table,colour,len(colour),grad)==0
   assert post.hb55_output_rgb16(grad,len(grad),matrix,exponent,out)==0
   actual=read(case,name+'_finished').reshape(-1,3)
   err=int(np.max(np.abs(actual.astype(int)-out.astype(int))));post_max=max(post_max,err);assert err==0
   independent=cmm_oracle(grad,matrix,(1.,1,exponent));err=int(np.max(np.abs(actual.astype(int)-independent.astype(int))));independent_output_max=max(independent_output_max,err);assert err<=1
   channels+=colour.size;pair.append(rgb8(actual))
   domains.append(unclipped_domain(source,cp,grid))
  plain,highlight=pair;outputs[(case['nominal_white_point_kelvin'],case['encoding'])]=pair
  dd=np.abs(highlight.astype(int)-plain.astype(int));index=int(np.argmax(dd.max(-1)))
  if worst is None or dd[index].max()>worst['difference']:
   worst={'case':case,'pixel':index,'difference':int(dd[index].max()),'target_linear_rgb':targets[index].tolist(),
          'prepared_raw_rgb16':raw[index].astype(int).tolist(),'without_highlight_rgb8':plain[index].astype(int).tolist(),
          'with_highlight_rgb8':highlight[index].astype(int).tolist()}
  # Both outputs and intermediate table/film domains must remain interior.
  inside=np.all((plain>=8)&(plain<=247)&(highlight>=8)&(highlight<=247),axis=1)&domains[0]&domains[1]
  ix=int(np.argmax(np.where(inside,dd.max(-1),-1)))
  if interior_worst is None or dd[ix].max()>interior_worst['difference']:
   interior_worst={'case':case,'pixel':ix,'difference':int(dd[ix].max()),'target_linear_rgb':targets[ix].tolist(),
       'prepared_raw_rgb16':raw[ix].astype(int).tolist(),'without_highlight_rgb8':plain[ix].astype(int).tolist(),
       'with_highlight_rgb8':highlight[ix].astype(int).tolist()}
  rows.append({'id':case['id'],'nominal_white_point_kelvin':case['nominal_white_point_kelvin'],'encoding':case['encoding'],
    'lut_kelvin':case['expected_lut_kelvin'],'highlight_vs_no_highlight':metric(highlight,plain),
    'groups':{name:metric(highlight[groups==int(key)],plain[groups==int(key)]) for key,name in fixture['groups'].items()},
    'gamut_interior_pixels':int(inside.sum()),'gamut_interior_highlight_effect':metric(highlight[inside],plain[inside])})
  nm=groups==3
  neutral_records.append({'id':case['id'],'plain_max_channel_spread':int(np.ptp(plain[nm].astype(int),axis=1).max()),
                         'highlight_max_channel_spread':int(np.ptp(highlight[nm].astype(int),axis=1).max())})
 cross=[]
 for k in sorted({c['nominal_white_point_kelvin'] for c in cases}):
  pairs=[outputs[(k,i)] for i in range(8)];record={'nominal_white_point_kelvin':k,'groups':{}}
  for key,name in fixture['groups'].items():
   mask=groups==int(key);stacks=[np.stack([p[i][mask] for p in pairs]).astype(int) for i in (0,1)]
   ranges=[np.ptp(s,axis=0) for s in stacks]
   record['groups'][name]={'samples_per_encoding':int(mask.sum()),
    'without_highlight_max_cross_encoding_rgb8_range':int(ranges[0].max()),
    'with_highlight_max_cross_encoding_rgb8_range':int(ranges[1].max()),
    'without_highlight_mean_cross_encoding_rgb8_range':float(ranges[0].mean()),
    'with_highlight_mean_cross_encoding_rgb8_range':float(ranges[1].mean())}
  cross.append(record)
 native=[]
 if a.apk:
  original_hash=hashlib.sha256(a.apk.read_bytes()).digest();elf,private=load_private(a.apk);runner=HighlightRunner(elf,private)
  native_cases={c['id']:c for c in cases if c['nominal_white_point_kelvin']==3550 and c['encoding']!=0}
  for witness in (worst,interior_worst):native_cases[witness['case']['id']]=witness['case']
  for case in native_cases.values():
   raw=read(case,'raw').reshape(-1,3);hi=read(case,'highlight_input').reshape(-1,3);n=np.array(case['neutral']);g=n.min()/n
   plain,highlight=outputs[(case['nominal_white_point_kelvin'],case['encoding'])]
   special=[w['pixel'] for w in (worst,interior_worst) if w['case']['id']==case['id']]
   idx=np.unique(np.r_[np.linspace(0,len(raw)-1,64).astype(int),np.argmax(np.abs(highlight.astype(int)-plain.astype(int)).max(-1)),special]).astype(int)
   runner.prepare(g,(65535,)*3);original=runner.cpu16(raw[idx]);hcheck=delta(hi[idx],original);assert hcheck['max_abs_difference']==0
   params=read(case,'highlight_params','<f8');cp=core.params(params[:9].reshape(3,3),params[9:18].reshape(3,3),grid_at(case['expected_lut_kelvin']),False,curve,params[18:22])
   colour=native_photo_sample(elf,private,original,cp,case['expected_lut_kelvin']);ccheck=delta(read(case,'highlight_colour').reshape(-1,3)[idx],colour);assert ccheck['max_abs_difference']==0
   native.append({'encoding':case['encoding'],'lut_kelvin':case['expected_lut_kelvin'],'highlight':hcheck,'colour':ccheck})
  assert hashlib.sha256(a.apk.read_bytes()).digest()==original_hash
 assert hashlib.sha256(a.profile.read_bytes()).digest()==before
 # Only aggregate errors/indices go to public receipts. Derived RGB samples stay private.
 witnesses={'all_domains':worst,'strictly_interior':interior_worst}
 (a.work/'PRIVATE_SYNTHETIC_WITNESSES57.json').write_text(json.dumps(witnesses,indent=2)+'\n')
 summaries={name:{'case_id':w['case']['id'],'pixel_index':w['pixel'],'encoding':w['case']['encoding'],
   'lut_kelvin':w['case']['expected_lut_kelvin'],'max_abs_rgb8_difference':w['difference'],
   'max_prepared_input_fraction':max(w['prepared_raw_rgb16'])/65535} for name,w in witnesses.items()}
 result={'schema':'hasselblad-stage57-generalisation-audit-v1','status':'PASS_EXECUTION_WITH_OPEN_HIGHLIGHT_ADAPTATION_FINDING',
  'cases':len(cases),'synthetic_camera_encodings':8,'metadata_white_points':sorted({c['nominal_white_point_kelvin'] for c in cases}),
  'pixels_per_case':len(targets),'all_prepared_inputs_below_clipping':True,'maximum_prepared_input_code':max(c['max_prepared_code'] for c in cases),
  'host_execution':json.loads((a.render/'HOST_EXECUTION57.json').read_text()),'highlight_vs_numpy_max_rgb16_difference':highlight_max,
  'colour_vs_independent_trace_channels':channels,'colour_vs_independent_trace_max_difference':trace_max,
  'finishing_vs_host_c_max_difference':post_max,'output_vs_independent_all_max_difference':independent_output_max,
  'cross_encoding_results':cross,'highlight_effects':rows,'neutral_ramps':neutral_records,'counterexample_summaries':summaries,
  'original_cpu_samples':native,'reference_illumination_spectrum_simulated':False,'physical_camera_calibration_validated':False,
  'scene_fitted_parameters':0,'source_profile_unchanged':True,'original_source_unchanged':True,
  'rendering_primitives_changed':False,'capture_renderer_changed':False,'device_pixel_equivalence_compared':False,'full_phocus_equivalence':False}
 result=public_receipt(result,a.work)
 a.safe_receipt.parent.mkdir(parents=True,exist_ok=True);a.safe_receipt.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'cases':len(cases),'channels':channels,'counterexamples':summaries,'native_cases':len(native)}),flush=True)
if __name__=='__main__':main()
