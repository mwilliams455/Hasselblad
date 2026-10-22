#!/usr/bin/env python3
"""Bounded original X2D 1.3.16.2 main/SCAP/HDR LUT preparation inspection.

Reads exact-hash vendor files from a *temporary* local extraction. Retains only
structural metadata and code-flow summaries, NEVER firmware bytes, tuning data,
raw instructions or disassembled function bodies. Does not execute vendor code
or make any claim about actual per-frame hardware submission.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
import lzma
import re
from pathlib import Path

EXPECTED_LIB='3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66'
EXPECTED_IQ='2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
KNOWN_FUNCS={
'main_3dlut_calc_frame':(0x39ce88,2148),
'post_scap3_calc_3dlut':(0x2f2d08,820),
'post_hdr_calc_3dlut':(0x301b00,820),
'_Calc_LerpLutMem3d':(0x3b8c78,408),
'_calc_lerp_lut_mem3d_enh':(0x3c3948,208),
}
KNOWN_CALLS={
 'rcam_adj_calc_common':0x3b3e98,
 'DjiIsp_Reg_Set':0x251a68,
 'mm_mx_lerp_vec_mix2':0x2bbc08,
 'DjiIsp_Reg_GetLut':0x251a18,
 'DjiAdj_Calc_LutMemCopy':0x3b30b0,
 'DjiIsp_Reg_Get':0x251a18,
}

def require(x,why):
    if not x:raise ValueError(why)

def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def config_analysis(conf):
    require(isinstance(conf,dict) and isinstance(conf.get('iq_table'),dict),'unexpected_iq_config')
    iq=conf['iq_table']
    data=iq.get('data')
    require(isinstance(data,list) and len(data)>0 and isinstance(data[0],dict),'unknown_data_group')
    main=data[0].get('main_3dlut')
    require(isinstance(main,list) and len(main)>0 and isinstance(main[0],dict),'main_lut_data_not_present')
    main_words=main[0].get('lut_data')
    require(isinstance(main_words,list) and len(main_words)==49152 and all(type(x) is int and 0<=x<=4294967295 for x in main_words),'main_3dlut_wrong_words')
    require(hashlib.sha256(__import__('struct').pack('<49152I',*main_words)).hexdigest()=='0e54912107eed71195a7231ab57ba3116ec469a9a70e05ad4889802c77247911','main_lut_payload_hash_wrong')
    inventory=[]
    # Actively examine all fields in each *global* IQ data group, without
    # leaking their tuning values or assuming a post mode has a full-size LUT.
    for group_index,group in enumerate(data):
        if not isinstance(group,dict): continue
        for key,v in sorted(group.items()):
            lower=key.lower()
            if any(s in lower for s in ('3dlut','post_hdr','post_scap3','scap3','hdr')):
                summary={'source_path':f'iq_table.data[{group_index}].{key}',
                         'top_level_type':type(v).__name__}
                if isinstance(v,list):
                    summary['record_count']=len(v)
                    summary['record_keys']=[sorted(entry.keys()) for entry in v[:2] if isinstance(entry,dict)]
                    for index,entry in enumerate(v):
                        if not isinstance(entry,dict):continue
                        for param,item in sorted(entry.items()):
                            if isinstance(item,list) and len(item)>=33 and all(isinstance(n,int) for n in item):
                                summary.setdefault('numeric_table_lengths',[]).append({'parameter_name':param,'count':len(item)})
                elif isinstance(v,dict):summary['record_keys']=[sorted(v.keys())]
                inventory.append(summary)
    metadata=iq.get('module',{})
    modules=[]
    if isinstance(metadata,dict):
        for name,mod in sorted(metadata.items()):
            if any(s in name.lower() for s in ('3dlut','post_hdr','post_scap3','scap3','hdr')):
                val={'module_name':name,'record_type':type(mod).__name__}
                entries=mod if isinstance(mod,list) else [mod]
                val['records']=[]
                for entry in entries[:5]:
                    if not isinstance(entry,dict):continue
                    d={'parameters':sorted(entry.keys())}
                    for k,p in entry.items():
                        if isinstance(p,dict):
                            d.setdefault('parameter_metadata',[]).append({'parameter':k,
                              'type':p.get('type'),'group':p.get('group'),
                              'axis':p.get('axis'),'mem_cfgen':p.get('mem_cfgen')})
                    val['records'].append(d)
                modules.append(val)
    # Recompute the original camera's per-6144-word source-profile classes
    # without exporting actual vendor tuning values or bytes.
    raw_profiles=[]
    import struct
    for block in ('main_3dlut','lcdc_3dlut0','lcdc_3dlut1',
                  'pyra_3dlut0','pyra_3dlut1','pyra_3dlut2'):
        entries=data[0].get(block,[])
        if not isinstance(entries,list) or len(entries)!=1 or not isinstance(entries[0],dict):continue
        key='lut_data' if block=='main_3dlut' else 'tlut'
        values=entries[0].get(key)
        if not isinstance(values,list) or len(values)%6144 or not values:continue
        require(all(type(n) is int and 0<=n<=4294967295 for n in values),
                'not_uint32_lut_'+block)
        profilehashes=[]
        for offset in range(0,len(values),6144):
            buf=struct.pack('<6144I',*values[offset:offset+6144])
            profilehashes.append(hashlib.sha256(buf).hexdigest())
        classes=[]
        for h in dict.fromkeys(profilehashes):
            classes.append([i for i,x in enumerate(profilehashes) if x==h])
        raw_profiles.append({'block':block,'profile_count':len(profilehashes),
                             'distinct_hashes':len(classes),
                             'equal_profile_index_groups':classes,
                             'sha256_per_profile':profilehashes})
    camera=conf.get('camera',{})
    # This is publicly named IQ-axis metadata, not sensor calibration/tuning.
    reg={}
    if isinstance(camera,dict):
        for key in ('cc_color_temp','color_gamut','liveview_scenario','lut3d',
                    'local_lut3d_num','color_temp'):
            v=camera.get(key)
            if isinstance(v,list):
                record={'present':True,'count':len(v)}
                if len(v)<=32 and all(type(i) in (int,str,bool) for i in v):
                    record['declared_axis_values']=v
            elif type(v) in (int,str,bool):
                record={'present':True,'scalar':v}
            else:record={'present':False,'python_type':type(v).__name__}
            reg[key]=record
    related_camera_key_names=sorted(k for k in camera if
        any(x in k.lower() for x in ('lut3d','scenario','mode'))) if isinstance(camera,dict) else []
    return {'source':'exact_HASH_pinned_original_hb722_config.json',
            'scan_scope':'Named top-level IQ data/modules containing 3dlut/post_hdr/post_scap3/scap3/hdr; numeric values deliberately excluded',
            'data_group_count':len(data),
            'camera_axis_registry':reg,
            'related_camera_key_names':related_camera_key_names,
            'independent_original_6144_word_profile_identity_groups':raw_profiles,
            'matching_data_groups':inventory,
            'matching_module_descriptors':modules}

def code_analysis(lib):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    from elftools.elf.elffile import ELFFile
    with lib.open('rb') as inp:
        elf=ELFFile(inp)
        require(elf['e_machine']=='EM_AARCH64' and elf.elfclass==64,'wrong_library_arch')
        segments=[seg for seg in elf.iter_segments() if seg['p_type']=='PT_LOAD']
        disasm=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
        result=[]
        for name,(va,nbytes) in KNOWN_FUNCS.items():
            owned=None
            for seg in segments:
                if seg['p_vaddr']<=va and va+nbytes<=seg['p_vaddr']+seg['p_filesz']:
                    offset=va-seg['p_vaddr']+seg['p_offset']
                    inp.seek(offset);owned=inp.read(nbytes);break
            require(owned is not None and len(owned)==nbytes,'missing_pinned_function_'+name)
            instructions=list(disasm.disasm(owned,va))
            require(len(instructions)==nbytes//4,'bad_disassembly_'+name)
            calls=[]
            for i,ins in enumerate(instructions):
                if ins.mnemonic!='bl':continue
                m=re.fullmatch(r'#?0x([0-9a-f]+)',ins.op_str.strip())
                target=int(m.group(1),16) if m else None
                symbolic=next((k for k,v in KNOWN_CALLS.items() if v==target),'other')
                # Emit ONLY derived categories / addresses of known CALL sites.
                window=instructions[max(0,i-12):i]
                classifications={'memory_loads':sum(q.mnemonic.startswith(('ldr','ldp','ldur')) for q in window),
                                 'constant_address_builders':sum(q.mnemonic in ('adrp','adr','add','mov','movk') for q in window),
                                 'conditional_branches':sum(q.mnemonic.startswith(('b.','cbz','cbnz','tbz','tbnz')) for q in window)}
                calls.append({'site_va':hex(ins.address),'target_va':hex(target) if target is not None else None,
                              'target_symbol_if_pinned':symbolic,
                              'preceding_12_instructions_category_counts':classifications})
            result.append({'function':name,'va':hex(va),'size_bytes':nbytes,
                           'instruction_count':len(instructions),
                           'original_code_sha256':hashlib.sha256(owned).hexdigest(),
                           'known_direct_adjustment_calls':[c for c in calls if c['target_symbol_if_pinned']=='rcam_adj_calc_common'],
                           'known_direct_register_set_calls':[c for c in calls if c['target_symbol_if_pinned']=='DjiIsp_Reg_Set'],
                           'known_direct_mix_helper_calls':[c for c in calls if c['target_symbol_if_pinned']=='mm_mx_lerp_vec_mix2'],
                           'direct_call_summary':{s:sum(c['target_symbol_if_pinned']==s for c in calls)
                               for s in sorted({c['target_symbol_if_pinned'] for c in calls})},
                           'register_argument_values_proven':False,
                           'IQ_source_pointer_identity_proven':False,
                           'register_2998_submission_proven_for_function':False})
    # We know original stored ELF identities; verify a subset of explicit sites.
    exp={
      'main_3dlut_calc_frame':['0x39d30c','0x39d61c'],
      'post_scap3_calc_3dlut':['0x2f2f34','0x2f301c'],
      'post_hdr_calc_3dlut':['0x301d2c','0x301e14'],
    }
    for item in result:
        if item['function'] in exp:
            require([c['site_va'] for c in item['known_direct_adjustment_calls']]==exp[item['function']],
                    'historical_original_code_call_site_differs_'+item['function'])
    return result

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--firmware-root',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True)
    z=a.parse_args();root=z.firmware_root.resolve()
    lib=root/'system/lib64/librcam.so';iq=root/'system/etc/iq/hb722_config.json'
    require(lib.is_file() and iq.is_file(),'missing_original_extraction')
    require(digest(lib)==EXPECTED_LIB and digest(iq)==EXPECTED_IQ,'unexpected_original_firmware_hash')
    # Import exact original bounded inert parser, never vendor code.
    parser_path=Path(__file__).resolve().parents[1]/'photographic_path/inspect_iq_config.py'
    spec=importlib.util.spec_from_file_location('pinned_original_IQ_parser',parser_path)
    require(spec is not None and spec.loader is not None,'parser_unavailable')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    conf=module.read_config(iq)
    report={ 'schema':'hasselblad-stage13-original-firmware-mode-iq-static-v1',
       'status':'completed_static_original_IQ_and_ELF_inspection',
       'original_librcam_sha256':EXPECTED_LIB,'original_iq_config_sha256':EXPECTED_IQ,
       'vendor_binary_executed':False,'original_machine_instructions_exported':False,
       'vendor_tuning_payload_exported':False,
       'IQ_source_and_modes':config_analysis(conf),
       'native_function_direct_calls':code_analysis(lib),
       'mode_condition_same_LUT_proven':False,
       'MAIN_photographic_pixel_sampler_proven':False,
       'run_time_original_context_or_ISP_proven':False,
       'phone_photographic_render_unchanged':True }
    z.output.parent.mkdir(parents=True,exist_ok=True)
    z.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],
      'config_IQ_data_match_count':len(report['IQ_source_and_modes']['matching_data_groups']),
      'modules_described':len(report['IQ_source_and_modes']['matching_module_descriptors']),
      'functions_inspected':len(report['native_function_direct_calls']),
      'new_LUT_mode_switch_proven':False}))
if __name__=='__main__': main()
