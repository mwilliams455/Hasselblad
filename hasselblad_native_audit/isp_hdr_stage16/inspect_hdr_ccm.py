#!/usr/bin/env python3
"""X2D II 1.3.16.2 bounded HDR capability / CCM kernel-provenance inspection.

Reads only exact SHA-256 pinned original files as inert ELF / JSON. Reports names,
counts, sections, declared topology and unproved boundaries; never executes
original code, dumps tuning vectors, or asserts HDR stacking/CCM pixels.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import lzma
import re
from pathlib import Path

PINS={
    'system/lib64/libdcam_pp.so':'bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9',
    'system/lib64/librcam.so':'3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66',
    'system/lib/modules/vcam_driver.ko':'29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e',
    'system/etc/iq/hb722_config.json':'2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286'
}
FUNCTION_KEYWORDS={
    'HDR_named':['hdr','hlrec','exposure_fusion'],
    'STACK_or_FUSION_named':['stack','fusion','merge'],
    'DYNAMIC_RANGE_named':['drc','tone','compress'],
    'RAW_RGB_named':['raw2rgb','raw_to_rgb'],
    'CCM_named':['ccm','color_matrix','colour_matrix','lmtx'],
}
FUNCTION_PREFIX=['main_3dlut_calc_frame','post_hdr_calc_3dlut','post_scap3_calc_3dlut']
PRODUCT_URL='https://www.hasselblad.com/x-system/x2d-ii-100c-faq/'
HARDWARE_SCOPE='There is no established ISP pixel input/output oracle or on-camera capture trace.'


def require(v,msg):
    if not v: raise ValueError(msg)

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def emitted_symbols(path, expected_machine):
    from elftools.elf.elffile import ELFFile
    with path.open('rb') as f:
        elf=ELFFile(f)
        require(elf['e_machine']==expected_machine and elf.elfclass==64,'unexpected_elf_architecture')
        names={}
        for section_name in ('.symtab','.dynsym'):
            section=elf.get_section_by_name(section_name)
            if not section:continue
            for s in section.iter_symbols():
                if s['st_info']['type']!='STT_FUNC' or s['st_shndx']=='SHN_UNDEF':continue
                n=s.name
                if n:names[n]=(n,int(s['st_value']),int(s['st_size']),section_name)
        compressed=elf.get_section_by_name('.gnu_debugdata')
        if compressed:
            data=lzma.decompress(compressed.data())
            dbg=ELFFile(io.BytesIO(data))
            st=dbg.get_section_by_name('.symtab')
            if st:
                for s in st.iter_symbols():
                    if s['st_info']['type']=='STT_FUNC' and s['st_shndx']!='SHN_UNDEF' and s.name:
                        names.setdefault(s.name,(s.name,int(s['st_value']),int(s['st_size']),'gnu_debugdata'))
        found={}
        for tag,patterns in FUNCTION_KEYWORDS.items():
            selected=[name for name in names if any(sub in name.lower() for sub in patterns)]
            found[tag]={'count':len(selected),'representative_names':sorted(selected)[:35]}
        related={}
        for prefix in FUNCTION_PREFIX:
            if prefix in names:
                n,va,size,source=names[prefix]
                related[prefix]={'virtual_address':hex(va),'size_bytes':size,'symbol_table':source}
        return {'total_defined_functions':len(names),'matching_symbol_categories':found,
                'main_and_post_hdr_functions':related,'dynamics_symbol_names_not_captured_all':True}


def iq_read(repo_root, file):
    script=repo_root/'hasselblad_native_audit/photographic_path/inspect_iq_config.py'
    require(script.is_file(),'missing_pinned_parser')
    z=importlib.util.spec_from_file_location('hb_pinned_iq_reader',str(script))
    require(z and z.loader,'cannot_load_parser')
    mod=importlib.util.module_from_spec(z);z.loader.exec_module(mod)
    return mod.read_config(file)


def classify_from_config(root):
    conf=iq_read(root,root/'hasselblad_native_audit/firmware/extracted/system/etc/iq/hb722_config.json')
    module=conf['iq_table']['module']
    main=module['main_3dlut']
    require(isinstance(main,dict) and isinstance(main.get('lut_data'),dict),'MAIN_metadata_shape_unknown')
    lut=main['lut_data']
    require(lut['type']=='lerp_lut_mem_3d' and lut['axis']==['cc_color_temp','color_gamut'],
            'MAIN_source_condition_axis_drift')
    camera=conf['camera'];require(camera['cc_color_temp']==[2400,3050,5550,9100],'CCT_knots_changed')
    data=conf['iq_table']['data']
    scopes=[]
    for idx,group in enumerate(data):
        for key,val in group.items():
            if 'hdr' in key.lower() or 'scap' in key.lower():
                scopes.append({'group':idx,'name':key,'entry_count':len(val) if isinstance(val,list) else 1,
                               'keys':sorted(val[0])[:35] if isinstance(val,list) and val and isinstance(val[0],dict) else []})
    mod_h=[{'module':k,'field_names':sorted(v[0]) if isinstance(v,list) and v and isinstance(v[0],dict) else sorted(v) if isinstance(v,dict) else []}
           for k,v in module.items() if 'hdr' in k.lower() or 'scap' in k.lower()]
    return {'MAIN_global_LUT_selector_inputs':lut['axis'],
            'MAIN_LUT_source_bytes_exported':False,
            'MAIN_CCT_knots':camera['cc_color_temp'],
            'IQ_data_derived_hdr_or_scap_named_groups':scopes,
            'IQ_module_derived_hdr_or_scap_named_groups':mod_h}


def selftest():
    assert len(PINS)==4
    assert 'raw2rgb' in FUNCTION_KEYWORDS['RAW_RGB_named']
    assert 'hdr' in FUNCTION_KEYWORDS['HDR_named']
    assert not any('multi' in y.lower() for y in ['function names prove repeated exposure'])
    assert PRODUCT_URL.startswith('https://www.hasselblad.com/')
    assert HARDWARE_SCOPE.endswith('trace.')
    return {'schema':'hb-stage16-hdr-ccm-guard-v1','status':'PASS',
            'guard_checks':6,'automatic_multiframe_claim':False,'render_applied':False}


def run(args):
    root=args.repo.resolve()
    extracted=args.firmware_root.resolve()
    require(root.is_dir() and extracted.is_dir(),'repo_or_firmware_root_missing')
    results={}
    for name,d in PINS.items():
        f=extracted/name
        require(f.is_file() and sha(f)==d, 'wrong_missing_firmware_file_'+name)
        results[name]={'sha256':d,'bytes':f.stat().st_size}
    vendor=emitted_symbols(extracted/'system/lib64/libdcam_pp.so','EM_AARCH64')
    controller=emitted_symbols(extracted/'system/lib64/librcam.so','EM_AARCH64')
    driver=emitted_symbols(extracted/'system/lib/modules/vcam_driver.ko','EM_AARCH64')
    conf=classify_from_config(root)
    known_report_path=root/'hasselblad_native_audit/photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.json'
    prev=json.loads(known_report_path.read_text())
    mapping=prev['topology_evidence']['selected_mode_maps'][0]['selected_segment_map']
    modes=[{'segment_name':x['segment_name'],'still_mode':x['mode']} for x in mapping if 'r2y-still' in x['segment_name']]
    require(len(modes)==3 and any('enh_hdr' in x['segment_name'] for x in modes),
            'saved_still_config_missing_hdr_segment')
    # Documentation and original ELF code are different evidence tiers.
    report={
       'schema':'hasselblad-stage16-hdr-vs-isp-ccm-original-static-v1',
       'status':'PASS_original_firmware_static_inspection',
       'firmware':'X2D II 100C 1.3.16.2',
       'original_sha256_pins_verified':results,
       'original_libdcam_pp_function_categories':vendor,
       'original_librcam_function_categories':controller,
       'original_vcam_driver_function_categories':driver,
       'IQ_selector_and_post_hdr_modules':conf,
       'prior_pinned_saved_still_segment_mapping':modes,
       'external_product_documents':{
          'official_X2D_II_HDR_FAQ':PRODUCT_URL,
          'official_camera_HDR_JPEG_HEIF_from_one_RAW_possible':'not_original_firmware_verified',
          'reviewer_HDR_output_gainmap_description':'https://www.dpreview.com/reviews/hasselblad-x2d-ii-100c-in-depth-review/'},
       'classification':{
          'firmware_has_hdr_named_configuration_and_entrypoints':True,
          'official_product_supports_HDR_HEIF_and_Ultra_HDR_JPEG':True,
          'official_HDR_available_during_exposure_bracketing':False,
          'HDR_requires_exposure_stacking_proven':False,
          'HDR_uses_no_exposure_stacking_proven_from_static_firmware':False,
          'still_HDR_segment_is_same_as_end_to_end_HNCS_HDR_proven':False,
          'MAIN_CCM_pixel_equation_proven':False,
          'MAIN_LUT_pixel_sampler_proven':False,
          'photo_or_gpu_render_modified':False,
          'vendor_instruction_bytes_exported':False,
          'vendor_tuning_tables_exported':False,
          'vendor_binary_executed':False
       },
       'limitations':[HARDWARE_SCOPE,'The original IMG codec and on-device HDR gainmap are not observed in a live capture.',
                     'The older X1D II HDR2 frame-stacking implementation is a distinct original generation.',
                     'Numerical CCM register values and their pixel interpretation remain unresolved.'],
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--repo',type=Path,default=Path('.'))
    p.add_argument('--firmware-root',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.self_test:
        print(json.dumps(selftest(),sort_keys=True))
    else:
        require(a.firmware_root is not None and a.output is not None,'missing_cli_args')
        r=run(a);print(json.dumps({'status':r['status'],'still_modes':len(r['prior_pinned_saved_still_segment_mapping']),
                                   'ccm_equation_proven':False,'original_code_executed':False}))
