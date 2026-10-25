#!/usr/bin/env python3
import argparse,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'phocus_prep_stage78'))
from check78 import run as previous
from bridge79 import run as bridge
def run(work,jni,reuse=False):
 if not reuse:previous(work,jni)
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera'
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 sources=[java/'hasselblad'/name for name in ('HasselbladSceneRenderer79.java','HasselbladRawLayout79.java','HasselbladCaptureFiles79.java')]
 sources+=[java/'processing/encoder/ImageFormatConfig.java',HERE/'Stage79Check.java']
 subprocess.run(compiler+['--release','17','-cp',str(work/'classes'),'-d',str(work/'classes'),*map(str,sources)],check=True)
 subprocess.run(['java','-Xmx768m','-Djava.library.path='+str(work),'-cp',str(work/'classes'),'Stage79Check',str(work)],check=True)
 bridge(ROOT,work)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni',type=Path,required=True);p.add_argument('--reuse-baseline',action='store_true');a=p.parse_args();run(a.work.resolve(),a.jni.resolve(),a.reuse_baseline)
