#!/usr/bin/env python3
"""Equivalent colour encodings, not measurements of physical sensors or lamps."""
import argparse,json,struct,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'phocus_illuminant_stage56')]
from reference56 import xy_from_temperature,normalize,temperature,quantize
D50=np.array([.9642,1.,.8249])

def standard_output():
 prim=np.array([[.64/.33,.30/.60,.15/.06],[1,1,1],[.03/.33,.10/.60,.79/.06]])
 white=np.array([.3127/.329,1,.3583/.329]);rgb_to_xyz=prim@np.diag(np.linalg.solve(prim,white))
 bradford=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
 adaptation=np.linalg.solve(bradford,np.diag((bradford@white)/(bradford@D50))@bradford)
 return np.linalg.solve(rgb_to_xyz,adaptation)

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 out=standard_output();rgb_to_xyz=np.linalg.inv(out)
 bradford=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
 mix1=np.array([[.8,.1,.1],[.05,.9,.05],[.1,.1,.8]])
 mix2=np.array([[.9,.06,.04],[.1,.8,.1],[.08,.12,.8]])
 encodings=[(np.array(n),np.eye(3)) for n in ((1,1,1),(.5,1,.3),(.8,1,.6),(.3,1,.8),(.4,.65,1),(.9,.7,1))]
 encodings += [(np.array([.3,1,.8]),mix1),(np.array([.8,1,.6]),mix2)]
 temps=[2400,2850,3550,4000,5550,6500,9100,15000]
 cube=np.stack(np.meshgrid(*[np.linspace(.01,1,9)]*3,indexing='ij'),-1).reshape(-1,3)
 targets=np.vstack([cube*p for p in (.12,.6,.95)]+[np.repeat(np.linspace(.0001,.95,129)[:,None],3,1)])
 groups=np.r_[np.repeat(np.arange(3),len(cube)),np.full(129,3)]
 targets.astype('<f8').tofile(a.out/'targets.bin');groups.astype('<i4').tofile(a.out/'groups.bin')
 records=[]
 with (a.out/'cases.bin').open('wb') as f:
  f.write(b'HB57TEST'+struct.pack('<2i',len(temps)*len(encodings),len(targets)))
  for k in temps:
   xy=xy_from_temperature(k,0);white=np.r_[xy,1-xy.sum()]/xy[1]
   adapt=np.linalg.solve(bradford,np.diag((bradford@D50)/(bradford@white))@bradford)
   for encoding,(neutral,mix) in enumerate(encodings):
    cm=np.diag(neutral)@mix@out@adapt
    fm=rgb_to_xyz@np.linalg.inv(mix)
    camera_to_d50=fm@np.diag(1/neutral)
    raw=targets@mix.T*neutral
    assert np.min(raw)>0 and np.max(raw)<1
    codes=np.floor(raw*65535).astype('<u2')
    selected_xyz=np.linalg.solve(normalize(cm),neutral);selected_xy=selected_xyz[:2]/selected_xyz.sum()
    expected=temperature(selected_xy)[0];lut=max(2000,min(10000,quantize(expected)))
    assert lut==max(2000,min(10000,quantize(k)))
    case_id=len(records)
    f.write(struct.pack('<3idi',case_id,k,encoding,expected,lut))
    for array in (cm,fm,neutral,camera_to_d50):f.write(np.asarray(array,dtype='<f8').tobytes())
    f.write(codes.tobytes())
    records.append({'id':case_id,'nominal_white_point_kelvin':k,'encoding':encoding,'expected_metadata_kelvin':expected,
     'expected_lut_kelvin':lut,'neutral':neutral.tolist(),'color_matrix':cm.tolist(),'forward_matrix':fm.tolist(),
     'camera_to_d50':camera_to_d50.tolist(),'max_prepared_code':int(codes.max()),'min_prepared_code':int(codes.min())})
 (a.out/'CASES57.json').write_text(json.dumps({'cases':records,'pixels_per_case':len(targets),
  'groups':{'0':'low_range_up_to_0.12','1':'mid_range_up_to_0.6','2':'high_range_up_to_0.95','3':'neutral_ramp'},
  'physical_sensors_or_lamps':False,'parameters_fitted_to_photographs':False},indent=2)+'\n')
 print(json.dumps({'cases':len(records),'pixels_per_case':len(targets),'max_input':float(targets.max()),'synthetic_only':True}))
if __name__=='__main__':main()
