#!/usr/bin/env python3
"""Live selection and cache invalidation checks using actual store/controller/JNI code."""
import argparse,hashlib,importlib.util,json,shutil,struct,subprocess
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];AUDIT=HERE.parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path)
    p.add_argument('--private-pair',nargs=2,action='append',default=[]);a=p.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    src=ROOT/'HasselbladPhoton/app/src/main';java=src/'java/com/particlesdevs/photoncamera/hasselblad';classes=work/'classes';classes.mkdir(exist_ok=True)
    javac=shutil.which('javac');jdk=Path(javac or shutil.which('java')).resolve().parents[1];jni=a.jni_include or jdk/'include'
    compiler=[javac] if javac else ['java','com.sun.tools.javac.Main']
    units=['HasselbladLookStore84','HasselbladPreview90Controller','HasselbladPreview90Changes','HasselbladPreview90Cache','HasselbladLook84','HasselbladPreview89','HasselbladPreview89Loader','HasselbladPreview89Settings','HasselbladProfile43','HasselbladTone83','HasselbladRenderer42','HasselbladSharpen87Settings','HasselbladDiagnostics86']
    spec=importlib.util.spec_from_file_location('check84',AUDIT/'phocus_look_stage84/check84.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    stubs=work/'stubs';stubs.mkdir(exist_ok=True)
    context=(AUDIT/'phocus_capture_stage87/Context.java').read_text().replace('new HashMap<>()','new java.util.concurrent.ConcurrentHashMap<>()')
    context=context.replace('public final class Context {','public final class Context {\n    private final java.io.File files;\n    public Context(java.io.File files){this.files=files;files.mkdirs();}\n    public java.io.File getFilesDir(){return files;}')
    (stubs/'Context.java').write_text(context);(stubs/'AtomicFile.java').write_text(old.ATOMIC)
    subprocess.run(compiler+['--release','17','-d',str(classes),*[str(java/(n+'.java')) for n in units],str(stubs/'Context.java'),str(stubs/'AtomicFile.java'),str(HERE/'Stage90Check.java')],check=True)
    inc=[jni,jni/'linux',AUDIT/'phocus_port_stage42/src',AUDIT/'isp_dng_stage18/src',AUDIT/'isp_colour_stage19/src',AUDIT/'phocus_highlight_stage53',AUDIT/'phocus_post_stage55',AUDIT/'phocus_finish_stage88']
    sources=[src/'cpp/hasselblad/hb_renderer42_jni.c',AUDIT/'phocus_port_stage42/src/hb42_colour.c',AUDIT/'isp_dng_stage18/src/hb_dng_pcs_bridge.c',AUDIT/'isp_colour_stage19/src/hb_colour_stage19.c',AUDIT/'phocus_highlight_stage53/highlight53.c',AUDIT/'phocus_post_stage55/post55.c',AUDIT/'phocus_finish_stage88/finish88.c']
    subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off','-fPIC','-shared','-pthread',*['-I'+str(x) for x in inc],*map(str,sources),'-Wl,--no-undefined','-lm','-o',str(work/'libhasselblad_renderer42_jni.so')],check=True)
    x=np.arange(65536)/65535.;curves=[(np.sqrt(x)*65535).astype('<f4'),(x*x*65535).astype('<f4'),np.arange(65536,dtype='<f4')]
    data=b'HB56LUT1'+struct.pack('<6i',2,2,4000,0,1,0);values=[0.]*38
    for i in (0,4,8,9,13,17,18,21,22,23,24,25,28,32,36,37):values[i]=1.
    data+=struct.pack('<38d',*values)+bytes(64)+curves[1].tobytes()+struct.pack('<4i10d',1,0,2,1,1,0,0,0,1,0,0,0,1,2.2)+struct.pack('<2i',1,3)
    for t in (2500,5000,7500):data+=struct.pack('<i',t)+bytes(64)
    profile=work/'synthetic.hbc';profile.write_bytes(data+hashlib.sha256(data).digest())
    pack=b'HB83CRV1'+struct.pack('<i',3)
    for film,curve in zip((0,1,7),curves):pack+=struct.pack('<i',film)+curve.tobytes()
    packfile=work/'synthetic.hbt';packfile.write_bytes(pack+hashlib.sha256(pack).digest())
    args=[str(profile),str(packfile)]
    for pair in a.private_pair:args+=pair
    subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'com.particlesdevs.photoncamera.hasselblad.Stage90Check',str(work),*args],check=True)
    receipt=work/'STAGE90_HOST_VALIDATION.json';r=json.loads(receipt.read_text())
    r.update({'private_profile_sets_checked':len(a.private_pair),'storage_adapter':'JVM AtomicFile fault injection and concurrent preferences; actual production store and controller',
        'preview_pixel_math_changed':False,'demosaic_retested':False,'shader_math_retested':False,'stage89_shader_proof_retained':True})
    receipt.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
