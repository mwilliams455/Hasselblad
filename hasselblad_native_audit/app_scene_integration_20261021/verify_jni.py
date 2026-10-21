#!/usr/bin/env python3
"""Actual app Java/JNI consumer vs separately established native API, private inputs.
No Android camera/SAF/device performance claim is made by this host test.
"""
import argparse,copy,ctypes as C,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
PHONE=HERE.parent/'phone_input_20261021';sys.path.insert(0,str(PHONE))
from verify_phone_scene import build,Policy,Result,Input,Grid,Frame,raw_descriptor,temperature_descriptor
from capture_binding import bind_capture,decode_bound_dng
from temperature_binding import bind_temperature
from verify_phone_raw import frame_from_binding

def main():
 p=argparse.ArgumentParser()
 for n in ['capture','dng','out','jdk','json-jar']:p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 base=json.loads(a.capture.read_text());bound=bind_capture(base,'dynamic');raw=decode_bound_dng(a.dng,base,bound)
 modern=copy.deepcopy(base);provenance=modern['original_still']['sensor_provenance']
 provenance['configured_output_device_id']=provenance.pop('callback_session_device_id')
 provenance['stream_identity_source']='actual_OutputConfiguration_by_delivering_ImageReader_surface'
 provenance['result_camera_id_matched']=True
 provenance['selected_result_camera_id']=provenance['selected_calibration_camera_id']
 assert bind_capture(modern,'dynamic')==bound
 for key,value in [('configured_output_device_id','mismatch'),('selected_result_camera_id','mismatch'),('result_camera_id_matched',False)]:
  bad=copy.deepcopy(modern);bad['original_still']['sensor_provenance'][key]=value
  try:bind_capture(bad,'dynamic')
  except ValueError:pass
  else:raise AssertionError('new provenance guard '+key)

 (a.out/'input.raw').write_bytes(raw)
 libpath,sources=build('cc',a.out,'reference',['-fPIC'],True);lib=C.CDLL(str(libpath))
 native=a.out/'libhasselblad_scene_jni.so'
 app=REPO/'HasselbladPhoton/app/src/main'
 subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffp-contract=off','-ffunction-sections','-fdata-sections','-fPIC','-fvisibility=hidden','-shared',
  '-I'+str(a.jdk/'include'),'-I'+str(a.jdk/'include/linux'),'-I'+str(PHONE),str(app/'cpp/hasselblad/hb_phone_scene_jni.c'),*[str(s) for s in sources],'-Wl,--gc-sections,-z,defs','-lm','-o',str(native)],check=True)
 grid=Grid();f=frame_from_binding(bound);buf=C.create_string_buffer(raw)
 lib.hb_phone_raw_build.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Frame),C.c_int,C.POINTER(Grid)]
 assert lib.hb_phone_raw_build(buf,len(raw),C.byref(f),0,C.byref(grid))==0
 inp=temperature_descriptor(bind_temperature(base,'dynamic')['anchors'])
 lib.hb_phone_scene_create.argtypes=[C.POINTER(Input),C.POINTER(Policy),C.POINTER(C.c_void_p)]
 lib.hb_phone_scene_run.argtypes=[C.c_void_p,C.POINTER(Grid),C.POINTER(Result)]
 lib.hb_phone_scene_destroy.argtypes=[C.c_void_p]
 expected=[]
 for radius in [128,256,512,1024,2048,4096]:
  policy=Policy(0,radius,2,16,.005,.9);handle=C.c_void_p();r=Result()
  assert lib.hb_phone_scene_create(C.byref(inp),C.byref(policy),C.byref(handle))==0
  assert lib.hb_phone_scene_run(handle,C.byref(grid),C.byref(r))==0;lib.hb_phone_scene_destroy(handle)
  candidate=r.decision==1
  expected.append(dict(radius_q12=radius,adapter_status=0,decision=['no_candidate','diagnostic_candidate','temperature_rejected'][r.decision],native_status=r.native_status,
    raw_valid_blocks=r.raw_valid,admitted_blocks=r.admitted,classified_blocks=r.classified,retained_blocks=r.retained,
    gain_q12=list(r.gain_q12) if candidate else None,neutral_green_normalized=list(r.neutral) if candidate else None,
    temperature_kelvin_tint_residual=list(r.temperature) if candidate else None,
    raw_rejected_blocks=sum(t.reason==1 for t in r.blocks),brightness_rejected_blocks=sum(t.reason==2 for t in r.blocks),
    signed_gain_rejected_blocks=sum(t.reason==3 for t in r.blocks),outside_locus_blocks=r.admitted-r.classified,component_removed_blocks=r.classified-r.retained))
 (a.out/'input.json').write_text(json.dumps(dict(capture=base,width=f.width,height=f.height,expected=expected)))
 shim=a.out/'shim/com/particlesdevs/photoncamera/processing/ImageFrame.java';shim.parent.mkdir(parents=True,exist_ok=True)
 shim.write_text('''package com.particlesdevs.photoncamera.processing;
public class ImageFrame {public java.nio.ByteBuffer buffer;public long rawSensorTimestampNs;
public int width,height,sourceRawWidth,sourceRawHeight,sourceRowStride,sourcePixelStride,sourceCopyOffsetBytes,cropOriginX,cropOriginY,packedBits;
public boolean fp16,sourceBinned;}''')
 classes=a.out/'classes';classes.mkdir(exist_ok=True)
 subprocess.run([str(a.jdk/'bin/javac'),'-cp',str(a.json_jar),'-d',str(classes),str(shim),str(app/'java/com/particlesdevs/photoncamera/hasselblad/HasselbladSceneDiagnostics.java'),str(HERE/'SceneJniHarness.java')],check=True)
 run=subprocess.run([str(a.jdk/'bin/java'),'-Xcheck:jni','-Djava.library.path='+str(a.out),'-cp',str(classes)+os.pathsep+str(a.json_jar),'SceneJniHarness',str(a.out/'input.json'),str(a.out/'input.raw'),str(a.out/'private_diagnostics.json')],text=True,capture_output=True)
 (a.out/'jvm_stdout.txt').write_text(run.stdout);(a.out/'jvm_stderr.txt').write_text(run.stderr)
 if run.returncode:raise RuntimeError(run.stdout+run.stderr)
 print(run.stdout.strip());assert not run.stderr,run.stderr
 result=json.loads(run.stdout);result.update(android_device_tested=False,host_jvm_jni_checked=True,offline_provenance_checks=4)
 (a.out/'JNI_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
