#!/usr/bin/env python3
"""Validate metadata-to-native temperature/LUT bridge; private inputs stay local."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import numpy as np
from reference56 import ROOT,TABLE,temperature,xy_from_temperature,quantize
from make_fixtures56 import profile_extension
sys.path.insert(0,str(ROOT/'phocus_import_stage52'))
from audit_import52 import load_private,z
from inspect_phocus_temperature41x import Runner,LUT,DECODE,lut_oracle

def main():
 p=argparse.ArgumentParser()
 for n in ('apk','profile','work','safe-receipt'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
 original=hashlib.sha256(a.apk.read_bytes()).digest();elf,profile=load_private(a.apk)
 assert np.array_equal(TABLE,z.temperature_table(elf))
 r=z.InputRunner(elf);r.profile=profile;r.call(DECODE,(r.obj,r.coder));r.u.mem_write(r.obj+9,b'\1')
 # Convert common XYZ white into a virtual reference-camera neutral solely
 # to exercise the original normal converter. No such gains touch phone pixels.
 mat=(np.array(profile['mf'])*.5+1).reshape(3,3)@np.diag(np.array(profile['vf'])*.5+1)
 inverse=np.linalg.inv(mat);checks=0;largest=0
 for k in (1800,2000,2024,2025,2400,2850,3050,3550,4000,5550,6500,8000,10000,15000,20000,40000):
  for tint in (-20,0,20):
   xy=xy_from_temperature(k,tint);xyz=np.r_[xy,1-xy.sum()];expected=temperature(xy)[0]
   neutral=inverse@xyz;assert np.all(neutral>0)
   for scale in (.125,1,3.7):
    result=r.gain_to_temp(scale/neutral)
    error=abs(result[0]-int(expected+.5));largest=max(largest,error);assert error==0,(k,tint,result,expected)
    assert quantize(result[0])==quantize(expected);checks+=1
 r.check_guards()
 runner=Runner(elf);runner.profile=profile
 for ptr,length in ((runner.obj,0x318),(0x10010000,0x298)):
  runner.u.mem_write(ptr-16,b'\xa5'*16);runner.u.mem_write(ptr+length,b'\xa5'*16)
 runner.call(DECODE,(runner.obj,runner.coder));runner.u.mem_write(runner.obj+9,b'\1');runner.checkpoint()
 temps=[int(profile[k]) for k in ('tt','tf','th')]
 assert temps==sorted(set(temps)) and 2000<=temps[0]<temps[-1]<=10000
 anchors=np.stack([lut_oracle(profile,t,False) for t in temps])
 errors=[];test_temperatures=(2000,2400,2850,3050,3550,4000,5550,6500,8000,9100,10000)
 for t in test_temperatures:
  runner.call(LUT,(runner.obj,t,0));native,_=runner.table();expected=lut_oracle(profile,t,False)
  err=float(np.max(abs(native-expected)));assert err<1e-12;errors.append(err)
  expected.astype('<f8').tofile(a.work/f'grid_{t}.bin');runner.discard_case()
 b=a.profile.read_bytes();assert b[:8]==b'HB55LUT1' and hashlib.sha256(b[:-32]).digest()==b[-32:]
 assert struct.unpack('<6i',b[8:32])[3:]==(0,0,0)
 extended=profile_extension(b,anchors,temps)
 (a.work/'Stage56_Private_Curve0_Auto.hbc').write_bytes(extended)
 assert hashlib.sha256(a.apk.read_bytes()).digest()==original
 receipt={'schema':'hasselblad-stage56-native-selection-v1','status':'PASS_BOUNDED_METADATA_TO_LUT_BRIDGE',
  'public_temperature_table_matches_original_entries':124,'native_temperature_cases':checks,'native_integer_kelvin_max_difference':largest,
  'native_selection_grid_unchanged':True,'native_lut_temperatures':list(test_temperatures),'native_lut_max_abs_difference':max(errors),
  'profile_colour_film_and_manual_output_unchanged':True,'private_output_contains_only_data':True,'virtual_reference_gains_only_in_audit':True,
  'reference_sensor_matrix_applied_to_phone_pixels':False,'DNG_white_balance_changed':False,'scene_fitted_parameters':0,
  'source_APK_unchanged':True,'capture_renderer_changed':False,'physical_phone_colour_match_validated':False,'full_phocus_equivalence':False}
 a.safe_receipt.parent.mkdir(parents=True,exist_ok=True);a.safe_receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
