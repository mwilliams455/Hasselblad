#!/usr/bin/env python3
import argparse,json,subprocess,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args();w=a.work.resolve();here=Path(__file__).resolve().parent
 args=[sys.executable,str(ROOT/'hasselblad_native_audit/phocus_post_stage55/check_host55.py'),'--work',str(w)]
 if a.jni_include:args+=['--jni-include',str(a.jni_include.resolve())]
 subprocess.run(args,check=True)
 subprocess.run([sys.executable,str(here/'make_fixtures56.py'),'--out',str(w/'fixtures56'),'--legacy',str(w/'fixtures43/synthetic.hbc')],check=True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 tests=[here/'Stage56Smoke.java']
 if (here/'Stage56PrivateCheck.java').exists():tests.append(here/'Stage56PrivateCheck.java')
 subprocess.run(compiler+['--release','17','-cp',str(w/'classes'),'-d',str(w/'classes'),*[str(t) for t in tests]],check=True)
 output=subprocess.check_output(['java','-Djava.library.path='+str(w),'-cp',str(w/'classes'),'Stage56Smoke',str(w/'fixtures56')],text=True)
 result=json.loads(output);print('Stage56Smoke',output.strip(),flush=True)
 receipt={'schema':'hasselblad-stage56-host-suite-v1','status':'PASS','selector':result,'fixtures':json.loads((w/'fixtures56/FIXTURES56.json').read_text()),'previous':json.loads((w/'STAGE55_HOST_SUITE.json').read_text()),'capture_renderer_changed':False,'device_tested':False}
 (w/'STAGE56_HOST_SUITE.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
