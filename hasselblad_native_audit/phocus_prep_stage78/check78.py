#!/usr/bin/env python3
import argparse,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'phocus_speed_stage77'))
from check77 import run as previous
from fixtures78 import fixture
def run(work,jni,reuse=False):
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 original=subprocess.check_output(['git','show','023411cfb53e6c9189a9711e1b5bd5f623049d16:HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladDngTileReader.java'],cwd=ROOT)
 assert (java/'HasselbladDngTileReader.java').read_bytes().startswith(original.rsplit(b'\n}',1)[0]),'Original preparation code changed'
 if not reuse:previous(work,jni)
 fixtures=work/'fixtures'
 for i in range(10):fixture(fixtures/('prep78-'+str(i)+'.dng'),i)
 fixture(fixtures/'prep78-large.dng',2,True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 subprocess.run(compiler+['--release','17','-cp',str(work/'classes'),'-d',str(work/'classes'),str(java/'HasselbladDngTileReader.java'),str(HERE/'Stage78Check.java')],check=True)
 subprocess.run(['java','-Xmx768m','-Djava.library.path='+str(work),'-cp',str(work/'classes'),'Stage78Check',str(fixtures),str(work/'STAGE78_HOST_VALIDATION.json')],check=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni',type=Path,required=True);p.add_argument('--reuse-baseline',action='store_true');a=p.parse_args();run(a.work.resolve(),a.jni.resolve(),a.reuse_baseline)
