#!/usr/bin/env python3
"""Run the existing synthetic suite plus actual Stage55 JNI and profile checks."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args()
    a.work=a.work.resolve();previous=ROOT/'hasselblad_native_audit/phocus_preview_stage54/check_host54.py'
    args=[sys.executable,str(previous),'--work',str(a.work)]
    if a.jni_include:args+=['--jni-include',str(a.jni_include.resolve())]
    subprocess.run(args,check=True)
    compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
    here=Path(__file__).resolve().parent;classes=a.work/'classes'
    subprocess.run(compiler+['--release','17','-cp',str(classes),'-d',str(classes),str(here/'Stage55Smoke.java'),str(here/'Stage55PrivateCheck.java')],check=True)
    result=subprocess.check_output(['java','-Djava.library.path='+str(a.work),'-cp',str(classes),'Stage55Smoke',str(a.work/'fixtures43')],text=True)
    print('Stage55Smoke',result.strip(),flush=True)
    receipt={'schema':'hasselblad-stage55-host-suite-v1','status':'PASS','previous':json.loads((a.work/'STAGE54_HOST_SUITE.json').read_text()),
             'finishing':json.loads(result),'synthetic_only':True,'device_tested':False,'capture_renderer_changed':False}
    (a.work/'STAGE55_HOST_SUITE.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
