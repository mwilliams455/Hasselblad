#!/usr/bin/env python3
import argparse,json,subprocess,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args();w=a.work.resolve();here=Path(__file__).resolve().parent
 args=[sys.executable,str(ROOT/'hasselblad_native_audit/phocus_generalisation_stage57/check_host57.py'),'--work',str(w)]
 if a.jni_include:args+=['--jni-include',str(a.jni_include.resolve())]
 subprocess.run(args,check=True)
 subprocess.run([sys.executable,str(here/'make_fixtures58.py'),'--out',str(w/'fixtures58')],check=True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-cp',str(w/'classes'),'-d',str(w/'classes'),str(here/'Stage58Check.java'),str(here/'Stage58DngCheck.java')],check=True)
 output=subprocess.check_output(['java','-Djava.library.path='+str(w),'-cp',str(w/'classes'),'Stage58Check',str(w/'fixtures58'),str(w/'fixtures43')],text=True)
 result=json.loads(output);print('Stage58Check',output.strip(),flush=True)
 receipt={'schema':'hasselblad-stage58-host-suite-v1','status':'PASS','raw_preparation':result,
 'previous':json.loads((w/'STAGE57_HOST_SUITE.json').read_text()),'synthetic_only':True,'capture_renderer_changed':False,'device_tested':False}
 (w/'STAGE58_HOST_SUITE.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
