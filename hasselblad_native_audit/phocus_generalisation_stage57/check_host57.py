#!/usr/bin/env python3
"""CI uses synthetic profile data only. Private photographic audits stay local."""
import argparse,json,subprocess,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args();w=a.work.resolve();here=Path(__file__).resolve().parent
 args=[sys.executable,str(ROOT/'hasselblad_native_audit/phocus_illuminant_stage56/check_host56.py'),'--work',str(w)]
 if a.jni_include:args+=['--jni-include',str(a.jni_include.resolve())]
 subprocess.run(args,check=True)
 subprocess.run([sys.executable,str(here/'make_cases57.py'),'--out',str(w/'fixtures57')],check=True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-cp',str(w/'classes'),'-d',str(w/'classes'),str(here/'Stage57Check.java'),str(here/'Stage57DngCheck.java')],check=True)
 output=subprocess.check_output(['java','-Djava.library.path='+str(w),'-cp',str(w/'classes'),'Stage57Check',
     str(w/'fixtures57'),str(w/'fixtures56/synthetic56.hbc'),str(w/'render57')],text=True)
 result=json.loads(output);print('Stage57Check',output.strip(),flush=True)
 receipt={'schema':'hasselblad-stage57-host-suite-v1','status':'PASS','combined_synthetic_execution':result,
     'previous':json.loads((w/'STAGE56_HOST_SUITE.json').read_text()),'synthetic_only':True,
     'capture_renderer_changed':False,'device_tested':False}
 (w/'STAGE57_HOST_SUITE.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
