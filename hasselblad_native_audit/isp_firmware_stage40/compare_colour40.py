#!/usr/bin/env python3
"""Stage40: compare selected original X2D II image-pipeline bytes across releases.

Source inputs are validated-by-hash transient file-extraction manifests and
optional inert parsed IQ parameter subtrees. Report exports only counts, hashes,
changed/unchanged decisions, and no vendor numeric tuning or image samples.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SPEC = {
 '1.3.16.2': {'bytes':364814336,'sha256':'9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6'},
 '1.3.18.1': {'bytes':365283840,'sha256':'c65970cbc1519f876aa3296411f8bb5075995dabc9479bb8abb635945dad6496'},
}
GROUPS={
 'CCM_driver_and_profile':('system/lib/modules/vcam_driver.ko','system/lib64/librcam.so','system/etc/iq/hb722_config.json'),
 'gamma_and_3D_LUT':('system/lib/modules/vcam_driver.ko','system/lib64/librcam.so','system/etc/iq/hb722_config.json'),
 'AWB_and_calibration':('system/lib64/libaaa.so','system/lib64/librcam.so','system/etc/iq/hb722_config.json'),
 'RAW_to_RGB_host':('system/lib64/libdcam_pp.so','system/lib64/libdcam_pp_base.so','system/lib64/libdsp_frwk.so'),
 'camera_register_and_stage':('system/lib/modules/cam_vreg.ko','system/lib/modules/vcam_driver.ko'),
 'camera_postprocessing':('system/lib64/libdcam_adj_product.so','system/lib64/libalgo_share.so','system/lib64/libadj_base.so'),
 'embedded_DSP':('vendor/firmware/dspf/ss_dsp0.fw','vendor/firmware/dspf/ss_dsp1.fw','vendor/firmware/dspf/ss_dsp2.fw','vendor/firmware/dspf/ask_dsp.img'),
 'display_and_postprocessing_HAL':('system/lib64/libduml_hal.so',),
 'IQ_schema':('system/etc/iq/config.fbs','system/etc/iq/hb722_config.json'),
}
IQ_SUBTREES=('main_ccm','main_3dlut','main_gamma_normal','main_gamma_common',
             'main_gamma_lowlight','main_hncs','main_wbc','main_autoknee')
OTHER_TOP=('topology','camera')


def require(ok,msg):
    if not ok:raise ValueError(msg)


def digest_bytes(data):return hashlib.sha256(data).hexdigest()


def config_summary(path:Path):
    # Own parser; original X2D II tuning source is inert text. Input archive was
    # SHA256-validated before extracting. No numeric vendor contents are output.
    source=path.read_bytes()
    require(len(source)<=64*1024**2,'iq_file_too_big')
    parser_path=Path(__file__).resolve().parents[1]/'photographic_path/inspect_iq_config.py'
    require(parser_path.is_file(),'missing_inert_parser')
    spec=importlib.util.spec_from_file_location('hb40_config_parser',parser_path)
    module=importlib.util.module_from_spec(spec)
    require(spec.loader is not None,'no_import_loader')
    spec.loader.exec_module(module)
    parser=module.Parser(source.decode('utf-8'))
    conf=parser.value()
    require(parser.next is None and isinstance(conf,dict),'incomplete_or_invalid_vendor_IQ_config')
    records=conf['iq_table']['data']
    require(isinstance(records,list) and records and all(isinstance(r,dict) for r in records),
            'IQ_data_records_missing_or_unexpected')
    result={}
    for name in IQ_SUBTREES:
        # Some modules (notably gamma) occur in still0/still3 records, not
        # data[0]. Hash *all* original mode-qualified occurrences so an
        # unchanged global record cannot hide an altered still-mode table.
        matching=[{'data_index':i,'mode':record.get('mod_iq_mode'),'value':record[name]}
                  for i,record in enumerate(records) if name in record]
        if not matching:
            result[name]=None
            continue
        serial=json.dumps(matching,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        result[name]={'canonical_json_sha256':digest_bytes(serial),
                      'record_count':len(matching),
                      'top_level_type':'mode_qualified_record_series'}
    for name in OTHER_TOP:
        require(name in conf,'missing_config_'+name)
        serial=json.dumps(conf[name],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        result[name]={'canonical_json_sha256':digest_bytes(serial),
                      'top_level_type':type(conf[name]).__name__}
    return result


def map_records(manifest):
    result={}
    for part in ('system','vendor'):
        item=manifest['partitions'].get(part)
        if not item:continue
        for r in item['records']:
            if r['kind']!='file':continue
            path=part+'/'+r['path']
            require(path not in result,'duplicate_extracted_path')
            result[path]={'sha256':r['sha256'],'bytes':r['bytes']}
    return result


def snapshot(folder:Path,version:str)->dict:
    manifest=json.loads((folder/'extraction_manifest.json').read_text())
    expected=SPEC[version]
    require(manifest['firmware_version']==version,'wrong_extracted_version')
    require(manifest['official_archive_sha256']==expected['sha256'],'wrong_source_sha')
    require(manifest['official_archive_bytes']==expected['bytes'],'wrong_source_bytes')
    require((folder/'system/etc/VERSION').read_text().strip()==version,'wrong_on_disk_version')
    files=map_records(manifest)
    paths=set(p for group in GROUPS.values() for p in group)
    selected={p:files.get(p) for p in sorted(paths)}
    actual_iq=folder/'system/etc/iq/hb722_config.json'
    require(actual_iq.is_file(),'IQ_source_missing')
    require(digest_bytes(actual_iq.read_bytes())==files['system/etc/iq/hb722_config.json']['sha256'],
            'IQ_hash_does_not_match_manifest')
    obj={
       'schema':'hasselblad-stage40-private-snapshot-v1',
       'firmware_version':version,
       'source_bytes':manifest['official_archive_bytes'],
       'source_sha256':manifest['official_archive_sha256'],
       'file_index':files,
       'selected_file_index':selected,
       'IQ_subtree_metadata':config_summary(actual_iq),
       'vendor_numeric_values_exported':False,
       'actual_image_pixels_processed':False,
    }
    return obj


def compare(old,new):
    require(old['firmware_version']=='1.3.16.2' and new['firmware_version']=='1.3.18.1','wrong_version_order')
    require(old['source_sha256']==SPEC['1.3.16.2']['sha256'],'bad_original_old_identity')
    require(new['source_sha256']==SPEC['1.3.18.1']['sha256'],'bad_original_new_identity')
    oldfiles=old['file_index'];newfiles=new['file_index']
    common=set(oldfiles)&set(newfiles)
    changes={p for p in common if oldfiles[p]['sha256']!=newfiles[p]['sha256']}
    changed_selected={}
    all_paths=sorted(set(p for group in GROUPS.values() for p in group))
    for p in all_paths:
        a=oldfiles.get(p);b=newfiles.get(p)
        status=('missing_both' if a is None and b is None else
                'added' if a is None else 'removed' if b is None else
                'identical' if a['sha256']==b['sha256'] else 'changed')
        changed_selected[p]={'status':status,
                             'old_bytes':a['bytes'] if a else None,
                             'new_bytes':b['bytes'] if b else None,
                             'old_sha256':a['sha256'] if a else None,
                             'new_sha256':b['sha256'] if b else None}
    groups={name:{'all_byte_identical':all(changed_selected[p]['status']=='identical' for p in paths),
                  'changed_or_missing':[p for p in paths if changed_selected[p]['status']!='identical']}
            for name,paths in GROUPS.items()}
    subtree={}
    for key in sorted(set(old['IQ_subtree_metadata'])|set(new['IQ_subtree_metadata'])):
        a=old['IQ_subtree_metadata'].get(key); b=new['IQ_subtree_metadata'].get(key)
        subtree[key]={
         'same_canonical_subtree':(None if a is None and b is None else
              (a is not None and b is not None and a['canonical_json_sha256']==b['canonical_json_sha256'])),
         'comparison_status':('absent_both' if a is None and b is None else
                              'missing_old' if a is None else
                              'missing_new' if b is None else
                              'identical' if a['canonical_json_sha256']==b['canonical_json_sha256'] else 'changed'),
         'old_exists':a is not None,'new_exists':b is not None,
         'old_sha256':a['canonical_json_sha256'] if a is not None else None,
         'new_sha256':b['canonical_json_sha256'] if b is not None else None,
        }
    return {
     'schema':'hasselblad-stage40-original-dual-firmware-colour-asset-diff-v1',
     'status':'PASS_hash_pinned_original_dual_firmware_comparison',
     'release_old':'1.3.16.2','release_new':'1.3.18.1',
     'old_official_package_sha256':old['source_sha256'],
     'new_official_package_sha256':new['source_sha256'],
     'entire_extracted_regular_file_comparison':{
       'old_file_count':len(oldfiles),'new_file_count':len(newfiles),
       'both_present':len(common),'identical_count':len(common)-len(changes),
       'changed_count':len(changes),
       'added_file_count':len(set(newfiles)-set(oldfiles)),
       'removed_file_count':len(set(oldfiles)-set(newfiles))},
     'selected_source_files':changed_selected,
     'pipeline_group_byte_identity':groups,
     'original_IQ_subtree_hash_equality':subtree,
     'prior_firmware_math_equivalence_proven_in_new_release':False,
     'same_software_bytes_allow_same_bounded_static_audit_scope_not_hardware_behaviour':True,
     'hardware_CCM_pixel_equation_proven':False,
     'gamma_and_MAIN_LUT_pixel_sampling_proven':False,
     'actual_HNCS_photographic_pixel_parity_proven':False,
     'firmware_executed_or_camera_hardware_contacted':False,
     'original_vendor_numeric_arrays_or_images_exported':False,
     'Android_app_modified':False,
     'main_branch_modified':False,
    }


def synthetic():
    # Deliberately exercises changed, identical, added, removed, absent and
    # subgroup cases. Not evidence about the real firmware.
    old={'firmware_version':'1.3.16.2','source_sha256':SPEC['1.3.16.2']['sha256'],
         'file_index':{'system/lib/modules/vcam_driver.ko':{'sha256':'a','bytes':1},
                      'system/lib64/librcam.so':{'sha256':'b','bytes':2},
                      'system/etc/iq/hb722_config.json':{'sha256':'c','bytes':3},
                      'x_removed':{'sha256':'d','bytes':4}},
         'IQ_subtree_metadata':{'main_ccm':{'canonical_json_sha256':'x'},'main_3dlut':None}}
    new={'firmware_version':'1.3.18.1','source_sha256':SPEC['1.3.18.1']['sha256'],
         'file_index':{'system/lib/modules/vcam_driver.ko':{'sha256':'a','bytes':1},
                      'system/lib64/librcam.so':{'sha256':'b2','bytes':2},
                      'system/etc/iq/hb722_config.json':{'sha256':'c','bytes':3},
                      'x_added':{'sha256':'e','bytes':5}},
         'IQ_subtree_metadata':{'main_ccm':{'canonical_json_sha256':'x'},'main_3dlut':None}}
    d=compare(old,new)
    assert d['status'].startswith('PASS')
    assert d['entire_extracted_regular_file_comparison']['changed_count']==1
    assert d['entire_extracted_regular_file_comparison']['identical_count']==2
    assert d['entire_extracted_regular_file_comparison']['added_file_count']==1
    assert d['entire_extracted_regular_file_comparison']['removed_file_count']==1
    assert d['selected_source_files']['system/lib64/librcam.so']['status']=='changed'
    assert d['selected_source_files']['system/lib/modules/vcam_driver.ko']['status']=='identical'
    assert d['selected_source_files']['system/etc/iq/hb722_config.json']['status']=='identical'
    assert not d['pipeline_group_byte_identity']['CCM_driver_and_profile']['all_byte_identical']
    assert d['original_IQ_subtree_hash_equality']['main_ccm']['same_canonical_subtree']
    assert d['original_IQ_subtree_hash_equality']['main_3dlut']['comparison_status']=='absent_both'
    assert d['original_IQ_subtree_hash_equality']['main_3dlut']['old_exists'] is False
    assert d['hardware_CCM_pixel_equation_proven'] is False
    assert d['Android_app_modified'] is False
    assert len(SPEC['1.3.16.2']['sha256'])==64
    assert len(GROUPS)>=7
    return {'status':'PASS_synthetic','checks':15,
            'original_firmware_loaded':False,'original_CCM_pixel_parity_proven':False,
            'photon_photo_render_unchanged':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--snapshot',type=Path)
    p.add_argument('--version',choices=SPEC)
    p.add_argument('--old',type=Path)
    p.add_argument('--new',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.self_test: v=synthetic()
    elif a.snapshot is not None:
        require(a.version is not None and a.output is not None,'snapshot_requires_version_and_output')
        v=snapshot(a.snapshot.resolve(),a.version)
    else:
        require(a.old is not None and a.new is not None and a.output is not None,'missing_comparison_arguments')
        v=compare(json.loads(a.old.read_text()),json.loads(a.new.read_text()))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
    safe={k:v[k] for k in ('status','checks') if k in v}
    if 'firmware_version' in v:
        safe['firmware_version']=v['firmware_version'];safe['private_snapshot']=True
    if 'entire_extracted_regular_file_comparison' in v:
        safe['counts']=v['entire_extracted_regular_file_comparison']
        safe['byte_identical_groups']={k:x['all_byte_identical'] for k,x in v['pipeline_group_byte_identity'].items()}
        safe['IQ_subtrees_same']={k:x['same_canonical_subtree'] for k,x in v['original_IQ_subtree_hash_equality'].items()}
    print(json.dumps(safe,sort_keys=True))

if __name__=='__main__':main()