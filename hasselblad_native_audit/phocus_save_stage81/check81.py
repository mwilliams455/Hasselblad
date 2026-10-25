#!/usr/bin/env python3
"""Focused publication and query-count checks; no demosaic/colour retesting."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'phocus_save_stage80'))
from adapter80 import run as adapter
def run(work):
 work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-d',str(classes),str(java/'HasselbladPublication80.java'),str(HERE.parent/'phocus_save_stage80/Stage80Check.java')],check=True)
 subprocess.run(['java','-cp',str(classes),'Stage80Check',str(work)],check=True)
 count=adapter(ROOT,work,compiler,HERE/'Stage81AdapterCheck.java')
 result=json.loads((work/'STAGE80_HOST_VALIDATION.json').read_text())
 result.update({'schema':'hasselblad-stage81-host-v1','status':'PASS_PUBLICATION_AND_BULK_NAME_QUERY','granted_tree_adapter_JVM_cases':count,'largest_synthetic_folder_entries':10000,'collision_queries_per_successful_save':2,'per_child_filename_queries':0,'device_save_speed_tested':False})
 (work/'STAGE81_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work.resolve())
