#!/usr/bin/env python3
import argparse,json,shutil,subprocess
from pathlib import Path
from adapter80 import run as adapter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def run(work):
 work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-d',str(classes),str(java/'HasselbladPublication80.java'),str(HERE/'Stage80Check.java')],check=True)
 subprocess.run(['java','-cp',str(classes),'Stage80Check',str(work)],check=True)
 count=adapter(ROOT,work,compiler)
 path=work/'STAGE80_HOST_VALIDATION.json';result=json.loads(path.read_text());result['granted_tree_adapter_JVM_cases']=count;path.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work.resolve())
