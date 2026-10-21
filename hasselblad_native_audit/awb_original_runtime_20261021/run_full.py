#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute original initialization and bounded preparation/pipeline comparisons."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from run_recalib import verify_runtime, sha, limits, HERE, AUDIT

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root',type=Path,required=True)
    p.add_argument('--ndk',type=Path,required=True)
    p.add_argument('--qemu',type=Path,required=True)
    p.add_argument('--private-output',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--prepare',action='store_true',help='Compare preparation, classification and connected-component filter')
    p.add_argument('--pipeline',action='store_true',help='Compare the owned normal scene body on seven synthetic native E2 frames')
    p.add_argument('--candidates',action='store_true',help='Compare candidate weighting, accumulation and normal scene control')
    a=p.parse_args()
    if sum([a.prepare,a.pipeline,a.candidates])>1:p.error('Choose one comparison mode')
    root=a.firmware_root.resolve();out=a.private_output.resolve()
    if out.is_relative_to(AUDIT.parent):
        raise ValueError('Private output must be outside the public repository')
    out.mkdir(parents=True,exist_ok=True)
    closure,linker_sha=verify_runtime(root)
    config=root/'system/etc/aaa/awb_imx861.bin'
    if sha(config)!='7fa13044a6c5453b67e4ae11bf8d07828de8e1c02aa915494fe5dad20930d435':
        raise ValueError('Wrong original AWB config')
    if '27.0.12077973' not in (a.ndk/'source.properties').read_text():
        raise ValueError('Expected NDK r27')
    compiler=a.ndk.resolve()/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android28-clang'
    probe=out/'full_probe_android28_arm64';sources=[HERE/'full_probe.c']
    if a.prepare:sources.extend([HERE/'prepare_compare.c',HERE/'hb_stat_prepare.c',HERE/'hb_scene_filter.c'])
    if a.pipeline:sources.extend([HERE/'scene_pipeline_compare.c',HERE/'hb_stat_prepare.c',HERE/'hb_scene_filter.c',HERE/'hb_scene_optimizer.c',HERE/'hb_scene_candidates.c'])
    if a.candidates:sources.extend([HERE/'candidates_compare.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_filter.c',HERE/'hb_scene_optimizer.c'])
    cmd=[str(compiler),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIE','-pie',
         '-ffp-contract=off','-Wl,-z,max-page-size=16384']
    if a.prepare:cmd+=['-DHB_PREPARE_COMPARE=1']
    if a.pipeline:cmd+=['-DHB_SCENE_PIPELINE=1']
    if a.candidates:cmd+=['-DHB_CANDIDATES_COMPARE=1']
    cmd += [*map(str,sources),'-ldl','-lm','-o',str(probe)]
    built=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if built.returncode:raise RuntimeError(built.stderr)
    command=[str(a.qemu.resolve()),'-L',str(root),str(probe),
             str(root/'system/lib64/libaaa.so'),str(config),str(out)]
    r=subprocess.run(command,env={'PATH':'/usr/bin:/bin','LANG':'C','LD_LIBRARY_PATH':str(root/'system/lib64')},
                     capture_output=True,text=True,timeout=30,preexec_fn=limits)
    (out/'stdout.txt').write_text(r.stdout);(out/'stderr.txt').write_text(r.stderr)
    events=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')]
    ok=(r.returncode==0 and len(events)==(11 if a.pipeline else 4 if (a.prepare or a.candidates) else 3)
        and [e.get('stage') for e in events[:2]]==['awb_cfg_load','awb_lib_init']
        and all(e.get('status')==0 for e in events[:2])
        and events[2].get('initialized_marker')==1 and events[2].get('e2_context_present') is True)
    if a.prepare:ok &= events[-1].get('all_passed') is True
    if a.pipeline:ok &= events[-1].get('all_passed') is True
    if a.candidates:ok &= events[-1].get('all_passed') is True
    headers=[HERE/'hb_stat_prepare.h',HERE/'hb_scene_filter.h'] if (a.prepare or a.pipeline or a.candidates) else []
    if a.pipeline or a.candidates:headers.extend([HERE/'hb_scene_optimizer.h',HERE/'hb_scene_candidates.h'])
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'all_passed':ok,'exit':r.returncode,
            'mode':'owned_normal_scene_pipeline' if a.pipeline else 'candidate_weighting_accumulation' if a.candidates else 'preparation_classification_filter' if a.prepare else 'full_initialization',
            'events':events,'input_config_sha256':sha(config),'library_sha256':sha(root/'system/lib64/libaaa.so'),
            'linker_sha256':linker_sha,'dependency_count':len(closure),'qemu_sha256':sha(a.qemu),
            'compiler_version':subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0],
            'source_sha256':{str(s.relative_to(AUDIT)):sha(s) for s in [*sources,HERE/'run_full.py',HERE/'run_recalib.py',*headers]},
            'probe_sha256':sha(probe),'build_command':cmd,'run_command':command,
            'private_dump_metadata':{s.name:{'bytes':s.stat().st_size,'sha256':sha(s)} for s in out.glob('*.bin')},
            'original_library_patched':False,'dependency_stubs':False,
            'full_camera_device_calibration_recovered':False,'authentic_frame_replayed':False,
            'historical_seven_frame_chain_recovered':False,'full_awb_validated':False}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'all_passed':ok,'events':events,'exit':r.returncode}))
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
