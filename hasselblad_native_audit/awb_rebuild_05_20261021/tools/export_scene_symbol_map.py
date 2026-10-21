#!/usr/bin/env python3
"""Export public source-preserved ELF symbol metadata, NOT vendor executable bytes.
The input is Native1A's preexisting JSON inventory created during earlier audit.
An entrypoint/size lookup is not a recovered instruction stream or ABI proof.
"""
from pathlib import Path
import argparse,hashlib,json
PINNED_ELF_SHA='7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba'
NAMES=[
 'scene_awb_lib_init','scene_awb_lib_run','scene_awb_set_calib_info','scene_awb_lib_set_statcfg',
 'scene_awb_scene_init','scene_awb_scene_proc','scene_awb_scene_compute_scene_weight',
 'scene_awb_scene_block_filter','scene_awb_scene_compute_scene_rbgain',
 'scene_awb_scene_opt','scene_awb_scene_compute_parsing_block_weight_ct',
 'scene_awb_scene_compute_blend_weight_ct','scene_awb_scene_illum_condition_check',
 'scene_awb_hist_init','scene_awb_hist_proc','scene_awb_atmos_proc',
 'scene_awb_stat_calib_proc','scene_awb_stat_awb_info','scene_awb_stat_ae_info',
 'scene_awb_post_proc','scene_awb_post_init','scene_awb_post_smooth',
 'scene_awb_color_temperature_compute','scene_awb_ct_tint_to_gain',
 'scene_awb_result_recalib_unit','scene_awb_get_result','scene_awb_get_recalib_res',
 'scene_awb_reawb_proc','scene_awb_reawb_save_res','scene_awb_calc_shading_ct_proc',
 'scene_awb_copy_result_to_confirm_result','scene_awb_copy_confirm_result_to_result',
 'scene_awb_copy_ref_result_to_result','scene_awb_copy_ref_result_to_confirm_result',
 'scene_awb_post_get_light_source','scene_awb_reawb_filter_proc',
 'scene_awb_result_normalise_all','scene_awb_debug_proc','scene_awb_debug_userdump',
]

def extract(inventory:Path)->dict:
    original=json.loads(inventory.read_text())
    entries=[x for x in original['libraries'] if x['path']=='system/lib64/libaaa.so']
    if len(entries)!=1:raise ValueError('libaaa inventory missing or ambiguous')
    record=entries[0]
    if record['sha256']!=PINNED_ELF_SHA or record['machine']!='EM_AARCH64':
        raise ValueError('inventory ELF provenance mismatch')
    mapping={}
    for name in NAMES:
        matches=[x for x in record['colour_symbols'] if x['name']==name and x['type']=='STT_FUNC']
        if not matches:raise ValueError('missing symbol '+name)
        # Each symbol must resolve to one recorded (address,length) pair.
        coords={(x['va'],x['bytes']) for x in matches}
        if len(coords)!=1:raise ValueError('ambiguous symbol '+name)
        va,size=coords.pop()
        if size<=0:raise ValueError('missing function size '+name)
        mapping[name]={'address':f'0x{va:x}','byte_count':size,'exclusive_end':f'0x{va+size:x}',
                       'source':'preserved Native1A ELF symbol inventory'}
    checks={
        'scene_awb_scene_proc':'0x4a7560',
        'scene_awb_scene_compute_scene_weight':'0x4a7d00',
        'scene_awb_scene_block_filter':'0x4a8548',
        'scene_awb_scene_opt':'0x4a8c48',
        'scene_awb_hist_proc':'0x49ba40',
        'scene_awb_lib_run':'0x471a38'
    }
    for name,va in checks.items():
        if mapping[name]['address']!=va:raise ValueError('source inventory symbol drift '+name)
    return {'source':'Native1A preserved inventory.json',
            'source_inventory_sha256':hashlib.sha256(inventory.read_bytes()).hexdigest(),
            'original_elf_expected_sha256':PINNED_ELF_SHA,
            'original_elf_bytes_available_now':False,
            'symbol_addresses_are_historical_not_fresh_vendor_comparison':True,
            'count':len(mapping),'symbols':mapping}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    x=p.parse_args()
    result=extract(x.inventory)
    x.out.parent.mkdir(parents=True,exist_ok=True)
    x.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('SYMBOL EXPORT OK',result['count'],'entries; original lib not re-opened')
if __name__=='__main__':main()