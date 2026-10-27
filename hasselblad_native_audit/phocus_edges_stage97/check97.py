#!/usr/bin/env python3
"""Compile actual kernels/adapters, exercise JNI, and retain capture/failure checks."""
import argparse,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;AUDIT=HERE.parent;ROOT=AUDIT.parent

def run(args):
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
    sources=[AUDIT/p for p in re.findall(r'"\$base/([^"\n]+\.c)"',(AUDIT/'phocus_output_stage74/run_host74.sh').read_text()) if '/test_' not in p]
    sources=list(dict.fromkeys(sources))+[AUDIT/'phocus_speed_stage77/frame77.c',AUDIT/'phocus_chroma_stage96/frame96.c',HERE/'frame97.c',HERE/'chroma97.c']
    flags=['gcc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-pthread']
    subprocess.run(flags+['-fsanitize=address,undefined','-fno-sanitize-recover=all',*map(str,sources),str(HERE/'test_frame97.c'),'-lm','-o',str(work/'native97')],check=True)
    subprocess.run([str(work/'native97')],check=True,env={**os.environ,'ASAN_OPTIONS':os.environ.get('ASAN_OPTIONS','detect_leaks=1')})
    jni=args.jni or Path(os.environ['JAVA_HOME'])/'include'
    subprocess.run(flags+['-shared','-fPIC','-I'+str(jni),'-I'+str(jni/'linux'),*map(str,sources),str(AUDIT/'phocus_speed_stage77/jni77.c'),str(HERE/'jni97.c'),'-lm','-o',str(work/'libhbframe97.so')],check=True)
    other=work/'libhbframe77.so'
    if not other.exists():other.symlink_to('libhbframe97.so')
    java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
    # Frame76 is compiled to satisfy the unchanged Frame77 reference self-check.
    names=['HasselbladDevice75Buffers','HasselbladFinalRaw74','HasselbladFrame76','HasselbladFrame77','HasselbladFrame97']
    classes=work/'classes';classes.mkdir(exist_ok=True)
    compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
    subprocess.run(compiler+['--release','17','-d',str(classes),*[str(java/(n+'.java')) for n in names],str(HERE/'Frame97Check.java')],check=True)
    subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'com.particlesdevs.photoncamera.hasselblad.Frame97Check'],check=True)
    sys.path.insert(0,str(AUDIT/'phocus_motion_stage95'));import check95
    stub=check95.P+'.hasselblad.HasselbladSceneRenderer79'
    check95.check94.STUBS[stub]=check95.check94.STUBS[stub].replace('public boolean sharpeningApplied=true;','public boolean sharpeningApplied=true;public double[] chromaNeutral={.5,1,.7};')
    check95.check94.STUBS[check95.P+'.BuildConfig']=check95.check94.STUBS[check95.P+'.BuildConfig'].replace('0.1-hb-motion95','0.1-hb-edges97').replace('27234','27236')
    # Publication fixtures create files with no overwrite, like production.
    # A fresh case directory makes a repeated host run independent of old saves.
    capture=Path(tempfile.mkdtemp(prefix='capture-run-',dir=work))
    check95.check94.run(capture,check95.extra,'Stage95Check','STAGE97_CAPTURE_VALIDATION.json')
    (work/'capture').mkdir(exist_ok=True)
    shutil.copyfile(capture/'STAGE97_CAPTURE_VALIDATION.json',work/'capture/STAGE97_CAPTURE_VALIDATION.json')
    subprocess.run([sys.executable,str(HERE/'quality97.py'),str(work)],check=True)
    print('PASS Stage97 host validation; phone validation remains required')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni',type=Path);run(p.parse_args())
