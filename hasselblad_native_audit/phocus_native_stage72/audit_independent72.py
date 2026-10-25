#!/usr/bin/env python3
"""Stage72 private-run audit: replace native InterpolateRGB and ColorNoise with independent C.

Never publish original APK, raw image, original ABI pointers, or local pixel dumps.
Original CPU handles setup and subsequent output/crop; independent C supplies the
entire pixel-loop's R/G/B and packed direction-mask planes.
"""
import argparse,ctypes as C,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X30,UC_ARM64_REG_PC
ROOT=Path(__file__).resolve().parents[1]
for p in ('phocus_native_stage71','phocus_colour_stage64','phocus_gradient_stage61','phocus_bayer_stage60'):
 sys.path.insert(0,str(ROOT/p))
from audit_colornoise_substitution71 import ColorNoiseRunner71, COLOR_NOISE
from audit_integration64 import PortableMaps,PortableInterpolation,PortableGreen,PortableYCC,load_private,synthetic_patterns,pad_bayer,prepare_private_dng
from portable65 import PortableNoise65
from audit_gradient60 import difference

RGB='_ZN20CGradientInterpolate14InterpolateRGBEPKtii'
SOURCE_FILES=[
'phocus_gradient_stage61/gradient_maps61.c','phocus_interpolation_stage62/interpolation62.c',
'phocus_green_stage63/green63.c','phocus_inline_stage67/raw_gradient67.c',
'phocus_inline_stage67/green_site_mask67.c','phocus_coloursite_stage68/colour_gradient68.c',
'phocus_coloursite_stage68/colour_site68.c','phocus_schedule_stage66/schedule66.c',
'phocus_schedule_stage66/wiring66.c','phocus_integrated_stage69/interpolate69.c']

class Domain(C.Structure):_fields_=[(x,C.c_int) for x in ('width','height','stride','flags')]
class Planes(C.Structure):_fields_=[('domain',Domain),('raw',C.c_void_p),('red',C.c_void_p),('green',C.c_void_p),('blue',C.c_void_p),('mask',C.c_void_p)]
class Scratch(C.Structure):_fields_=[(x,C.c_void_p) for x in ('smooth','edge','horizontal','vertical','scale','midgreen')]
class Params(C.Structure):_fields_=[('threshold',C.c_double),('edge_floor',C.c_int16),('raw_floor',C.c_int16)]

class C72:
 def __init__(self,work,sanitize=False):
  work.mkdir(parents=True,exist_ok=True)
  path=work/'libstage72_interpolate.so'
  cmd=['gcc','-std=c11','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off']
  if sanitize: cmd += ['-fsanitize=undefined','-fno-sanitize-recover=all']
  cmd += [str(ROOT/f) for f in SOURCE_FILES]+['-lm','-o',str(path)]
  subprocess.run(cmd,check=True,capture_output=True)
  self.lib=C.CDLL(str(path))
  self.lib.hb_interpolate69.argtypes=[C.POINTER(Planes),C.POINTER(Scratch),Params,C.c_void_p]
  self.lib.hb_interpolate69.restype=C.c_int
 def calculate(self,raw,width,height,stride,flags,threshold,floors):
  assert raw.shape==(height,stride) and raw.dtype==np.dtype('<u2') and raw.flags.c_contiguous
  outs={n:np.zeros((height,stride),dtype='<u2') for n in ('red','green','blue','mask')}
  scratch={n:np.zeros((height,stride),dtype=('<f4' if n in ('horizontal','vertical','scale') else '<i2' if n=='edge' else '<u2')) for n in ('smooth','edge','horizontal','vertical','scale','midgreen')}
  planes=Planes(Domain(width,height,stride,flags),raw.ctypes.data,*[outs[n].ctypes.data for n in ('red','green','blue','mask')])
  s=Scratch(*[scratch[n].ctypes.data for n in ('smooth','edge','horizontal','vertical','scale','midgreen')])
  res=C.create_string_buffer(2048)
  status=self.lib.hb_interpolate69(C.byref(planes),C.byref(s),Params(threshold,*floors),res)
  if status!=0:raise AssertionError(('Portable Interpolate rejected native graph',status))
  return outs

class NativeReplacement72(ColorNoiseRunner71):
 def __init__(self,elf,profile,maps,interp,green,ycc,noise,portable):
  self.rgblib=portable
  self.rgb_entry=elf.func[RGB][0]
  self.independent_rgb_calls=0
  self.native_parameters=[]
  super().__init__(elf,profile,maps,interp,green,ycc,noise)
 def hook(self,cpu,address,size,user):
  if self.gradient_active and address==self.rgb_entry:
   if self.replace:
    reg=lambda i:cpu.reg_read(UC_ARM64_REG_X0+i)
    obj,rawp=reg(0),reg(1)
    width,height=reg(2)&0xffffffff,reg(3)&0xffffffff
    stride=self.get(obj,0x3c,'<i')[0]
    flags=self.get(obj,0x38,'<H')[0]
    threshold=self.get(obj,0x30,'<d')[0]
    floors=self.get(obj,0xe8,'<2h')
    assert (width,height) in ((128,128),(96,96),(88,80),(104,88)) and stride==1024, (width,height,stride)
    assert flags==65535 and threshold==1.0 and floors==(32,200)
    assert width%8==height%8==0 and width>24 and height>24
    source=self.array(rawp,(height,stride),'<u2')
    old=source.tobytes()
    out=self.rgblib.calculate(source,width,height,stride,flags,threshold,floors)
    assert source.tobytes()==old
    p={n:self.get(obj,o,'<Q')[0] for n,o in [('red',0xb0),('green',0xb8),('blue',0xc0),('mask',0xc8)]}
    lengths=[(ptr,ptr+height*stride*2) for ptr in p.values()]
    assert all(a<=d or c<=b for i,(a,b) in enumerate(lengths) for (c,d) in lengths[i+1:])
    assert all(end<=rawp or rawp+height*stride*2<=start for start,end in lengths), 'source/working plane overlap'
    for n in ('red','green','blue','mask'):
     assert p[n] > 0
     cpu.mem_write(p[n],out[n].tobytes())
    self.independent_rgb_calls+=1
    self.native_parameters.append((width,height,stride,flags,threshold,floors))
    cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_X30))
    return
  return super().hook(cpu,address,size,user)


def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--apk',type=Path,required=True)
 ap.add_argument('--dng',type=Path)
 ap.add_argument('--work',type=Path,required=True)
 ap.add_argument('--safe-receipt',type=Path,required=True)
 ap.add_argument('--fixture',default='neutral',choices=('neutral','flat_colour','ramp','colour_edge','red_impulse','random_codes','dng1','dng2','dng3','dng4','held1','held2','held3','held4','rectangle_16x24','rectangle_18x34','all'))
 ap.add_argument('--mode',choices=('bypass','highlight','both'),default='bypass')
 ap.add_argument('--sanitize',action='store_true')
 a=ap.parse_args();assert __debug__
 initial=[hashlib.sha256(f.read_bytes()).digest() for f in ([a.apk]+([a.dng] if a.dng else []))]
 portable=C72(a.work/'portable72',a.sanitize)
 r=NativeReplacement72(*load_private(a.apk),
   PortableMaps(a.work/'maps',sanitize=a.sanitize),
   PortableInterpolation(a.work/'interp',sanitize=a.sanitize),
   PortableGreen(a.work/'green',sanitize=a.sanitize),
   PortableYCC(a.work/'ycc',sanitize=a.sanitize),
   PortableNoise65(a.work/'noise',sanitize=a.sanitize),portable)
 r.setup_graph()
 checked=[]
 def check(label,mosaic):
  before_rgb=r.independent_rgb_calls
  before_noise=r.noise_replacements
  r.replace=False;native=r.demosaic(mosaic)
  r.replace=True;independent=r.demosaic(mosaic)
  diff=difference(native,independent)
  item={'fixture':label,**diff,'independent_rgb_calls':r.independent_rgb_calls-before_rgb,
        'independent_noise_calls':r.noise_replacements-before_noise}
  print('FULL_NATIVE_REPLACEMENT',json.dumps(item),flush=True)
  checked.append(item)
 extra_rng=np.random.default_rng(6202)
 patterns=synthetic_patterns()+[('rectangle_16x24',extra_rng.integers(0,65536,(16,24),dtype=np.uint16)),('rectangle_18x34',extra_rng.integers(0,65536,(18,34),dtype=np.uint16))]
 for name,bayer in patterns:
  if a.fixture not in ('all',name):continue
  if a.mode in ('bypass','both'):
   check(name+'/highlight_bypass',pad_bayer(bayer,32))
  if a.mode in ('highlight','both'):
   corrected=r.black59(bayer[...,None],512)[...,0]
   fast=r.fast(pad_bayer(corrected,36));r.prepare((.5,.7,1.),(65023,)*3)
   highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
   check(name+'/highlight_bayer_chain',r.remosaic(highlighted))
  if a.fixture!='all':break
 if a.fixture.startswith(('dng','held')) or (a.fixture=='all' and a.dng):
  assert a.dng is not None
  mosaic,gains,_=prepare_private_dng(a.dng)
  h,w=mosaic.shape
  selections=[('dng',32,32,((1,1),(1,3),(3,1),(3,3))),
              ('held',16,24,((1,2),(2,1),(2,3),(3,2)))]
  for prefix,th,tw,grid in selections:
   for idx,(gy,gx) in enumerate(grid,1):
    if a.fixture not in ('all',prefix+str(idx)):continue
    top,left=(gy*h//4-th//2)//2*2,(gx*w//4-tw//2)//2*2
    patch=mosaic[top-36:top+th+36,left-36:left+tw+36]
    assert patch.shape==(th+72,tw+72)
    if a.mode in ('bypass','both'):
     check(('fixed' if prefix=='dng' else 'additional')+'_private_dng_'+str(idx)+'/highlight_bypass',patch[4:-4,4:-4])
    if a.mode in ('highlight','both'):
     fast=r.fast(patch);r.prepare(gains,(65535,)*3)
     highlighted=r.cpu16(fast.reshape(-1,3)).reshape(fast.shape)
     check(('fixed' if prefix=='dng' else 'additional')+'_private_dng_'+str(idx)+'/highlight_bayer_chain',r.remosaic(highlighted))
 r.check_guards()
 for ptr,frozen in r.frozen_profile:assert bytes(r.u.mem_read(ptr,len(frozen)))==frozen
 assert initial==[hashlib.sha256(f.read_bytes()).digest() for f in ([a.apk]+([a.dng] if a.dng else []))]
 assert checked and all(x['max_absolute_rgb16_difference']==0 and x['changed_pixels']==0 for x in checked)
 assert r.independent_rgb_calls==len(checked) and r.noise_replacements==len(checked)
 assert RGB not in r.original_entries_when_replaced
 assert COLOR_NOISE not in r.original_entries_when_replaced
 report={'schema':'hasselblad-stage72-full-interpolate-original-cpu-v1',
 'status':'PASS_EXACT_FULL_PIXEL_LOOP_AND_COLORNOISE',
 'cases':checked,'independent_rgb_calls':r.independent_rgb_calls,
 'independent_colornoise_calls':r.noise_replacements,
 'observed_working_contracts':[{'width':w,'height':h,'stride':d,'flags':flags,
   'scale_threshold':threshold,'direction_threshold_floors':list(floors)} for w,h,d,flags,threshold,floors in sorted(set(r.native_parameters))],
 'original_pixel_helpers_executed_during_replacement':sorted(set(r.original_entries_when_replaced).intersection({RGB,COLOR_NOISE})),
 'remaining_original_graph_entry_names':sorted(r.original_entries_when_replaced),
 'original_rgb_loop_body_skipped_in_independent_graph':r.independent_rgb_calls==len(checked),
 'privacy_private_apk_dng_pixels_outside_public_artifacts':True,
 'device_pixel_parity':False,'full_frame_alignment_validated':False}
 a.safe_receipt.parent.mkdir(parents=True,exist_ok=True)
 a.safe_receipt.write_text(json.dumps(report,indent=2)+'\n')
 print('FINAL_PRIVATE_STATUS',json.dumps({'status':report['status'],'cases':len(checked),'redacted':True}),flush=True)
if __name__=='__main__':main()
