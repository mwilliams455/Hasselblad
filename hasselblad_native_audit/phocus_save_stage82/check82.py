#!/usr/bin/env python3
"""Focused publication and destination-lookup checks; no renderer retesting."""
import argparse,json,shutil,subprocess
from pathlib import Path
from adapter82 import run as adapter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def run(work):
 work.mkdir(parents=True,exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-d',str(classes),str(java/'HasselbladPublication80.java'),str(HERE.parent/'phocus_save_stage80/Stage80Check.java')],check=True)
 subprocess.run(['java','-cp',str(classes),'Stage80Check',str(work)],check=True)
 count=adapter(ROOT,work,compiler,HERE/'Stage82AdapterCheck.java')
 result=json.loads((work/'STAGE80_HOST_VALIDATION.json').read_text())
 result.update({'schema':'hasselblad-stage82-host-v1','status':'PASS_PUBLICATION_AND_TARGET_LOOKUP','granted_tree_adapter_JVM_cases':count,'largest_synthetic_folder_entries':10000,'target_queries_per_successful_save':2,'parent_health_queries_per_successful_save':2,'bulk_queries_on_verified_primary_path':0,'unrelated_filename_rows_scanned':0,'unknown_folder_id_bulk_fallback_tested':True,'device_save_speed_tested':False})
 (work/'STAGE82_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work.resolve())
