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
    p.add_argument('--pipeline',action='store_true',help='Compare the owned complete scene stage on seven synthetic native E2 frames')
    p.add_argument('--candidates',action='store_true',help='Compare candidate weighting, accumulation and normal scene control')
    p.add_argument('--temperature',action='store_true',help='Compare all temperature modes and their matrix/xy helpers')
    p.add_argument('--user-finish',action='store_true',help='Compare final user requests and the complete owned user stage')
    p.add_argument('--user-finish-entry',action='store_true',help='With --run-entry, replace the complete user stage')
    p.add_argument('--user-controls',action='store_true',help='Compare CT/tint/gain requests and inverse conversion')
    p.add_argument('--user-controls-entry',action='store_true',help='With --run-entry, replace CT/tint/gain requests')
    p.add_argument('--user-manual',action='store_true',help='Compare manual-sample selection and E-ND application')
    p.add_argument('--user-manual-entry',action='store_true',help='With --run-entry, replace manual-sample selection')
    p.add_argument('--user-e-nd',action='store_true',help='Compare E-ND temperature interpolation and user unit-calibration requests')
    p.add_argument('--user-e-nd-entry',action='store_true',help='With --run-entry, also replace the E-ND unit request helper')
    p.add_argument('--user-prepare-entry',action='store_true',help='With --run-entry, also replace the user calibration prefix after the white LUT')
    p.add_argument('--user-prepare',action='store_true',help='Compare user calibration import prefix, manual LUT and mode helper')
    p.add_argument('--white-lut',action='store_true',help='Compare white-reference expansion and E-ND preparation')
    p.add_argument('--white-lut-entry',action='store_true',help='With --run-entry, replace E-ND white-reference preparation before the original remainder')
    p.add_argument('--run-entry',action='store_true',help='Compare outer entry, fixed results and scheduling; continuation uses the original remainder')
    p.add_argument('--diagnostics',action='store_true',help='Compare diagnostic carry-forward, encoding, statistics packing and no-file userdump')
    p.add_argument('--diagnostics-pipeline',action='store_true',help='With --pipeline, replace diagnostic packing after owned passive REAWB')
    p.add_argument('--completion',action='store_true',help='Compare final copies, recovery, shading and bounded passive REAWB')
    p.add_argument('--completion-pipeline',action='store_true',help='With --pipeline, extend owned post through passive REAWB, shading and completion; debug remains original')
    p.add_argument('--post',action='store_true',help='Compare the post controller, publication, smoothing and inverse temperature')
    p.add_argument('--post-pipeline',action='store_true',help='With --pipeline, replace and compare the complete post stage')
    p.add_argument('--post-results',action='store_true',help='Compare post-result helpers and the complete mode-2 branch; full post remains original')
    p.add_argument('--atmosphere',action='store_true',help='Compare the atmosphere stage and correction helpers')
    p.add_argument('--history',action='store_true',help='Compare history processing and signed zone/temperature geometry')
    p.add_argument('--controller',action='store_true',help='Compare all four scene slots and special post-optimizer weighting')
    p.add_argument('--tail-baseline',action='store_true',help='With --pipeline, execute original downstream history/atmos/post/REAWB stages')
    p.add_argument('--history-pipeline',action='store_true',help='With --pipeline, compare owned history and continue original atmos/post/REAWB')
    p.add_argument('--post-results-pipeline',action='store_true',help='With --pipeline, replay post-result helpers from original golden snapshots; post controller remains original')
    p.add_argument('--atmosphere-pipeline',action='store_true',help='With --pipeline, compare owned scene/history/atmosphere before original post/REAWB')
    a=p.parse_args()
    if a.user_finish_entry:a.user_controls_entry=True
    if a.user_controls_entry:a.user_manual_entry=True
    if a.user_manual_entry:a.user_e_nd_entry=True
    if a.user_e_nd_entry:a.user_prepare_entry=True
    if a.user_prepare_entry:a.white_lut_entry=True
    if a.diagnostics_pipeline:a.completion_pipeline=True
    if a.completion_pipeline:a.post_pipeline=True
    if a.post_pipeline and a.post_results_pipeline:p.error('Choose full post replacement or snapshot replay')
    if a.post_pipeline:a.atmosphere_pipeline=True
    if a.post_results_pipeline:a.atmosphere_pipeline=True
    if a.atmosphere_pipeline:a.history_pipeline=True
    if a.history_pipeline:
        if not a.pipeline:p.error('--history-pipeline requires --pipeline')
        a.tail_baseline=True
    if sum([a.prepare,a.pipeline,a.candidates,a.temperature,a.controller,a.history,a.atmosphere,a.post_results,a.post,a.completion,a.diagnostics,a.run_entry,a.white_lut,a.user_prepare,a.user_e_nd,a.user_manual,a.user_controls,a.user_finish])>1:p.error('Choose one comparison mode')
    if a.white_lut_entry and not a.run_entry:p.error('--white-lut-entry requires --run-entry')
    if a.tail_baseline and not a.pipeline:p.error('--tail-baseline requires --pipeline')
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
    if a.temperature:sources.extend([HERE/'temperature_compare.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_filter.c',HERE/'hb_scene_optimizer.c'])
    if a.history or a.atmosphere:sources.extend([HERE/('atmosphere_compare.c' if a.atmosphere else 'history_compare.c'),HERE/'hb_history.c',HERE/'hb_scene_optimizer.c',HERE/'hb_scene_controller.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_filter.c',HERE/'hb_temperature.c'])
    if a.post_results:sources.extend([HERE/'post_results_compare.c',HERE/'hb_post_results.c',HERE/'hb_temperature.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_optimizer.c',HERE/'hb_scene_filter.c'])
    if a.post or a.completion:sources.extend([HERE/('completion_compare.c' if a.completion else 'post_compare.c'),HERE/'hb_post_controller.c',HERE/'hb_post_results.c',HERE/'hb_atmosphere.c',HERE/'hb_history.c',HERE/'hb_temperature.c',HERE/'hb_scene_controller.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_optimizer.c',HERE/'hb_scene_filter.c'])
    if a.user_finish:sources.append(HERE/'user_finish_compare.c')
    if a.user_finish or a.user_finish_entry:sources.append(HERE/'hb_user_finish.c')
    if a.user_controls:sources.append(HERE/'user_controls_compare.c')
    if a.user_controls or a.user_controls_entry or a.user_finish:sources.extend([HERE/'hb_user_controls.c',HERE/'hb_post_results.c',HERE/'hb_stat_prepare.c'])
    if a.user_manual:sources.append(HERE/'user_manual_compare.c')
    if a.user_manual or a.user_manual_entry or a.user_controls or a.user_finish:sources.extend([HERE/'hb_user_manual.c',HERE/'hb_temperature.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_optimizer.c',HERE/'hb_scene_filter.c'])
    if a.user_e_nd:sources.append(HERE/'user_e_nd_compare.c')
    if a.user_e_nd or a.user_e_nd_entry or a.user_manual or a.user_controls or a.user_finish:sources.append(HERE/'hb_user_e_nd.c')
    if a.user_prepare:sources.append(HERE/'user_prepare_compare.c')
    if a.user_prepare or a.user_prepare_entry or a.user_e_nd or a.user_manual or a.user_controls or a.user_finish:sources.extend([HERE/'hb_user_prepare.c',HERE/'user_entry.S'])
    if a.white_lut:sources.append(HERE/'white_lut_compare.c')
    if a.white_lut or a.white_lut_entry:sources.append(HERE/'hb_white_lut.c')
    if a.run_entry:sources.extend([HERE/'run_entry_compare.c',HERE/'hb_run_entry.c',HERE/'completion_entry.S'])
    if a.diagnostics:sources.append(HERE/'diagnostics_compare.c')
    if a.diagnostics or a.diagnostics_pipeline:sources.append(HERE/'hb_diagnostics.c')
    if a.completion or a.completion_pipeline:sources.extend([HERE/'hb_completion.c',HERE/'completion_entry.S'])
    if a.post_pipeline:sources.extend([HERE/'hb_post_controller.c',HERE/'hb_post_results.c'])
    if a.atmosphere:sources.append(HERE/'hb_atmosphere.c')
    if a.controller:sources.extend([HERE/'controller_compare.c',HERE/'hb_scene_controller.c',HERE/'hb_scene_candidates.c',HERE/'hb_scene_filter.c',HERE/'hb_scene_optimizer.c'])
    if a.pipeline or a.candidates or a.temperature or a.controller:sources.append(HERE/'hb_temperature.c')
    if a.pipeline:sources.append(HERE/'hb_scene_controller.c')
    if a.history_pipeline:sources.append(HERE/'hb_history.c')
    if a.post_results_pipeline:sources.append(HERE/'hb_post_results.c')
    if a.atmosphere_pipeline:sources.append(HERE/'hb_atmosphere.c')
    cmd=[str(compiler),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIE','-pie',
         '-ffp-contract=off','-Wl,-z,max-page-size=16384']
    if a.user_finish:cmd+=['-DHB_USER_FINISH_COMPARE=1']
    if a.user_finish_entry:cmd+=['-DHB_USER_FINISH_ENTRY=1']
    if a.user_controls:cmd+=['-DHB_USER_CONTROLS_COMPARE=1']
    if a.user_controls_entry:cmd+=['-DHB_USER_CONTROLS_ENTRY=1']
    if a.user_manual:cmd+=['-DHB_USER_MANUAL_COMPARE=1']
    if a.user_manual_entry:cmd+=['-DHB_USER_MANUAL_ENTRY=1']
    if a.user_e_nd:cmd+=['-DHB_USER_E_ND_COMPARE=1']
    if a.user_e_nd_entry:cmd+=['-DHB_USER_E_ND_ENTRY=1']
    if a.user_prepare_entry:cmd+=['-DHB_USER_PREPARE_ENTRY=1']
    if a.user_prepare:cmd+=['-DHB_USER_PREPARE_COMPARE=1']
    if a.white_lut:cmd+=['-DHB_WHITE_LUT_COMPARE=1']
    if a.white_lut_entry:cmd+=['-DHB_WHITE_LUT_ENTRY=1']
    if a.run_entry:cmd+=['-DHB_RUN_ENTRY_COMPARE=1']
    if a.diagnostics:cmd+=['-DHB_DIAGNOSTICS_COMPARE=1']
    if a.diagnostics_pipeline:cmd+=['-DHB_DIAGNOSTICS_PIPELINE=1']
    if a.completion:cmd+=['-DHB_COMPLETION_COMPARE=1']
    if a.completion_pipeline:cmd+=['-DHB_COMPLETION_PIPELINE=1']
    if a.post:cmd+=['-DHB_POST_COMPARE=1']
    if a.post_pipeline:cmd+=['-DHB_POST_PIPELINE=1']
    if a.prepare:cmd+=['-DHB_PREPARE_COMPARE=1']
    if a.pipeline:cmd+=['-DHB_SCENE_PIPELINE=1']
    if a.candidates:cmd+=['-DHB_CANDIDATES_COMPARE=1']
    if a.temperature:cmd+=['-DHB_TEMPERATURE_COMPARE=1']
    if a.post_results:cmd+=['-DHB_POST_RESULTS_COMPARE=1']
    if a.atmosphere:cmd+=['-DHB_ATMOSPHERE_COMPARE=1']
    if a.history:cmd+=['-DHB_HISTORY_COMPARE=1']
    if a.controller:cmd+=['-DHB_CONTROLLER_COMPARE=1']
    if a.post_results_pipeline:cmd+=['-DHB_POST_RESULTS_PIPELINE=1']
    if a.atmosphere_pipeline:cmd+=['-DHB_ATMOSPHERE_PIPELINE=1']
    if a.history_pipeline:cmd+=['-DHB_HISTORY_PIPELINE=1']
    if a.tail_baseline:cmd+=['-DHB_ORIGINAL_TAIL=1']
    cmd += [*map(str,sources),'-ldl','-lm','-o',str(probe)]
    built=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if built.returncode:raise RuntimeError(built.stderr)
    command=[str(a.qemu.resolve()),'-L',str(root),str(probe),
             str(root/'system/lib64/libaaa.so'),str(config),str(out)]
    r=subprocess.run(command,env={'PATH':'/usr/bin:/bin','LANG':'C','LD_LIBRARY_PATH':str(root/'system/lib64')},
                     capture_output=True,text=True,timeout=30,preexec_fn=limits)
    (out/'stdout.txt').write_text(r.stdout);(out/'stderr.txt').write_text(r.stderr)
    events=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')]
    ok=(r.returncode==0 and len(events)==(39 if a.tail_baseline else 11 if a.pipeline else 4 if (a.prepare or a.candidates or a.temperature or a.controller or a.history or a.atmosphere or a.post_results or a.post or a.completion or a.diagnostics or a.run_entry or a.white_lut or a.user_prepare or a.user_e_nd or a.user_manual or a.user_controls or a.user_finish) else 3)
        and [e.get('stage') for e in events[:2]]==['awb_cfg_load','awb_lib_init']
        and all(e.get('status')==0 for e in events[:2])
        and events[2].get('initialized_marker')==1 and events[2].get('e2_context_present') is True)
    if a.user_finish:ok &= events[-1].get('all_passed') is True
    if a.user_controls:ok &= events[-1].get('all_passed') is True
    if a.user_manual:ok &= events[-1].get('all_passed') is True
    if a.user_e_nd:ok &= events[-1].get('all_passed') is True
    if a.user_prepare:ok &= events[-1].get('all_passed') is True
    if a.white_lut:ok &= events[-1].get('all_passed') is True
    if a.prepare:ok &= events[-1].get('all_passed') is True
    if a.pipeline:ok &= events[-1].get('all_passed') is True
    if a.candidates:ok &= events[-1].get('all_passed') is True
    if a.temperature:ok &= events[-1].get('all_passed') is True
    if a.run_entry:ok &= events[-1].get('all_passed') is True
    if a.diagnostics:ok &= events[-1].get('all_passed') is True
    if a.completion:ok &= events[-1].get('all_passed') is True
    if a.post:ok &= events[-1].get('all_passed') is True
    if a.post_results:ok &= events[-1].get('all_passed') is True
    if a.atmosphere:ok &= events[-1].get('all_passed') is True
    if a.history:ok &= events[-1].get('all_passed') is True
    if a.controller:ok &= events[-1].get('all_passed') is True
    headers=[HERE/'hb_stat_prepare.h',HERE/'hb_scene_filter.h'] if (a.prepare or a.pipeline or a.candidates or a.temperature or a.controller) else []
    if a.pipeline or a.candidates or a.temperature or a.controller:headers.extend([HERE/'hb_scene_optimizer.h',HERE/'hb_scene_candidates.h',HERE/'hb_temperature.h'])
    if a.controller or a.pipeline:headers.append(HERE/'hb_scene_controller.h')
    if a.post_results:headers.extend([HERE/'hb_post_results.h',HERE/'hb_temperature.h',HERE/'hb_scene_candidates.h',HERE/'hb_scene_optimizer.h',HERE/'hb_scene_filter.h',HERE/'hb_stat_prepare.h'])
    if a.post or a.post_pipeline or a.completion:headers.extend([HERE/'hb_post_controller.h',HERE/'hb_post_results.h',HERE/'hb_history.h',HERE/'hb_temperature.h',HERE/'hb_scene_controller.h',HERE/'hb_scene_candidates.h',HERE/'hb_scene_optimizer.h',HERE/'hb_scene_filter.h',HERE/'hb_stat_prepare.h',HERE/'hb_atmosphere.h'])
    if a.atmosphere:headers.append(HERE/'hb_atmosphere.h')
    if a.history or a.atmosphere:headers.extend([HERE/'hb_history.h',HERE/'hb_scene_optimizer.h',HERE/'hb_scene_controller.h',HERE/'hb_scene_candidates.h',HERE/'hb_scene_filter.h',HERE/'hb_temperature.h',HERE/'hb_stat_prepare.h'])
    if a.post_results_pipeline:headers.append(HERE/'hb_post_results.h')
    if a.atmosphere_pipeline:headers.append(HERE/'hb_atmosphere.h')
    if a.history_pipeline:headers.append(HERE/'hb_history.h')
    if a.completion or a.completion_pipeline:headers.append(HERE/'hb_completion.h')
    if a.diagnostics or a.diagnostics_pipeline:headers.extend([HERE/'hb_diagnostics.h',HERE/'hb_stat_prepare.h'])
    if a.white_lut or a.white_lut_entry:headers.extend([HERE/'hb_white_lut.h',HERE/'hb_stat_prepare.h'])
    if a.user_controls or a.user_controls_entry or a.user_finish:headers.extend([HERE/'hb_user_controls.h',HERE/'user_controls_fixtures.h',HERE/'hb_post_results.h'])
    if a.user_manual or a.user_manual_entry or a.user_controls or a.user_finish:headers.extend([HERE/'hb_user_manual.h',HERE/'user_manual_fixtures.h',HERE/'hb_temperature.h',HERE/'hb_scene_candidates.h',HERE/'hb_scene_optimizer.h',HERE/'hb_scene_filter.h'])
    if a.user_e_nd or a.user_e_nd_entry or a.user_manual or a.user_controls or a.user_finish:headers.extend([HERE/'hb_user_e_nd.h',HERE/'user_e_nd_fixtures.h'])
    if a.user_prepare or a.user_prepare_entry or a.user_e_nd or a.user_manual or a.user_controls or a.user_finish:headers.extend([HERE/'hb_user_prepare.h',HERE/'hb_stat_prepare.h'])
    if a.run_entry:headers.extend([HERE/'hb_run_entry.h',HERE/'hb_stat_prepare.h'])
    if a.user_finish or a.user_finish_entry:headers.extend([HERE/'hb_user_finish.h',HERE/'user_finish_fixtures.h'])
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'all_passed':ok,'exit':r.returncode,
            'mode':'owned_entry_complete_user_original_outer_remainder' if a.user_finish_entry else 'owned_complete_user_stage' if a.user_finish else 'owned_entry_through_controls_original_remainder' if a.user_controls_entry else 'owned_user_ct_tint_gain_controls' if a.user_controls else 'owned_entry_through_manual_samples_original_remainder' if a.user_manual_entry else 'owned_manual_samples_and_e_nd_updates' if a.user_manual else 'owned_entry_user_calibration_and_unit_original_remainder' if a.user_e_nd_entry else 'owned_user_e_nd_unit_request' if a.user_e_nd else 'owned_entry_white_lut_user_prefix_original_remainder' if a.user_prepare_entry else 'owned_user_calibration_prefix' if a.user_prepare else 'owned_white_lut_prepare' if a.white_lut else 'owned_white_lut_and_entry_original_remainder' if a.white_lut_entry else 'owned_run_entry_original_remainder' if a.run_entry else 'owned_diagnostics_pipeline' if a.diagnostics_pipeline else 'owned_diagnostics_no_file' if a.diagnostics else 'owned_completion_pipeline' if a.completion_pipeline else 'owned_completion_and_passive_reawb' if a.completion else 'owned_post_pipeline' if a.post_pipeline else 'owned_post_controller' if a.post else 'post_result_snapshot_replay_pipeline' if a.post_results_pipeline else 'owned_post_result_helpers_and_mode2' if a.post_results else 'owned_scene_history_atmosphere_pipeline' if a.atmosphere_pipeline else 'owned_atmosphere' if a.atmosphere else 'owned_history_scene_pipeline' if a.history_pipeline else 'owned_history' if a.history else 'original_downstream_baseline' if a.tail_baseline else 'owned_scene_controller' if a.controller else 'owned_complete_scene_pipeline' if a.pipeline else 'calibrated_temperature' if a.temperature else 'candidate_weighting_accumulation' if a.candidates else 'preparation_classification_filter' if a.prepare else 'full_initialization',
            'events':events,'input_config_sha256':sha(config),'library_sha256':sha(root/'system/lib64/libaaa.so'),
            'linker_sha256':linker_sha,'dependency_count':len(closure),'qemu_sha256':sha(a.qemu),
            'compiler_version':subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0],
            'source_sha256':{str(s.relative_to(AUDIT)):sha(s) for s in [*sources,HERE/'run_full.py',HERE/'run_recalib.py',*headers]},
            'probe_sha256':sha(probe),'build_command':cmd,'run_command':command,
            'private_dump_metadata':{s.name:{'bytes':s.stat().st_size,'sha256':sha(s)} for s in out.glob('*.bin')},
            'original_library_patched':False,'dependency_stubs':False,
            'full_camera_device_calibration_recovered':False,'authentic_frame_replayed':False,
            'historical_seven_frame_chain_recovered':False,'full_awb_validated':False,
            'completion_suffix_owned':a.completion or a.completion_pipeline,'passive_reawb_owned':a.completion or a.completion_pipeline,
            'active_reawb_owned':False,'debug_stage_owned':a.diagnostics or a.diagnostics_pipeline,'debug_file_io_owned':False,'full_outer_controller_owned':False,
            'user_ct_tint_gain_owned':a.user_controls or a.user_controls_entry or a.user_finish,'inverse_temperature_conversion_owned':a.user_controls or a.user_controls_entry or a.user_finish,
            'manual_sample_selection_owned':a.user_manual or a.user_manual_entry or a.user_controls or a.user_finish,'e_nd_gain_updates_owned':a.user_manual or a.user_manual_entry or a.user_controls or a.user_finish,
            'user_unit_request_owned':a.user_e_nd or a.user_e_nd_entry or a.user_manual or a.user_controls or a.user_finish,'e_nd_temperature_gain_owned':a.user_e_nd or a.user_e_nd_entry or a.user_manual or a.user_controls or a.user_finish,
            'user_calibration_prefix_owned':a.user_prepare or a.user_prepare_entry or a.user_e_nd or a.user_manual or a.user_controls or a.user_finish,'user_mode_helper_owned':a.user_prepare or a.user_controls or a.user_controls_entry or a.user_finish,'full_user_stage_owned':a.user_finish or a.user_finish_entry,
            'user_remainder_entry':None if (a.user_finish or a.user_finish_entry) else '0x4b16d4' if (a.user_controls or a.user_controls_entry) else '0x4b16a8' if (a.user_manual or a.user_manual_entry) else '0x4b162c' if (a.user_e_nd or a.user_e_nd_entry) else '0x4b1624' if (a.user_prepare or a.user_prepare_entry) else None,
            'controller_remainder_after_user':'0x471e78' if a.user_prepare_entry else None,
            'prepared_entry_adapter_used':a.user_finish or a.user_controls or a.user_manual or a.user_e_nd or a.user_prepare or a.completion or a.completion_pipeline or a.run_entry,
            'white_lut_owned':a.white_lut or a.white_lut_entry,'white_lut_original_remainder_entry':'0x471e64' if (a.white_lut_entry and not a.user_prepare_entry) else None,
            'run_entry_owned':a.run_entry,'original_remainder_after_owned_entry':a.run_entry,
            'full_post_stage_owned':a.post or a.post_pipeline,'post_mode2_compared_and_owned':a.post_results or a.post,
            'post_research_abi_requires_initialized_bounded_tables':True,
            'post_all_branches_exhaustively_verified':False}
    if a.tail_baseline:
        deltas=[]
        for frame in range(7):
            before=out/f'frame_{frame:02d}_after_scene_full_owned.bin'
            for stage in ['scene_awb_hist_proc','scene_awb_atmos_proc','scene_awb_post_proc','scene_awb_reawb_proc']:
                after=out/f'frame_{frame:02d}_after_original_{stage}.bin'
                if not (before.exists() and after.exists()):break
                x=before.read_bytes();y=after.read_bytes()
                if len(x)!=len(y):raise ValueError('Mismatched downstream context sizes')
                deltas.append({'frame':frame,'stage':stage,'context_changed_bytes':sum(a!=b for a,b in zip(x,y))})
                before=after
        report['original_downstream_stage_deltas']=deltas
        report['active_reawb_output_parity_established']=False
        report['history_stage_compared_and_owned']=a.history_pipeline
        report['atmosphere_stage_compared_and_owned']=a.atmosphere_pipeline
        report['post_stage_compared_and_owned']=a.post_pipeline
        report['post_result_snapshot_replay_compared']=a.post_results_pipeline
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'all_passed':ok,'events':events,'exit':r.returncode}))
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
