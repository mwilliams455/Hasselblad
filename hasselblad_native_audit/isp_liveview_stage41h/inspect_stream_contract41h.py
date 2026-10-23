#!/usr/bin/env python3
"""Read only pinned stream topology and bounded frame-forwarding metadata."""
import argparse, configparser, hashlib, json, re, sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'isp_liveview_stage41'))
from inspect_original_liveview_xrefs41b import symbols, code_slice, require
from inspect_original_sbpc_processing41c import parse_plt

PIN = {
 'system/etc/imx861bqr_hb722.conf':'4d1db41c60d3eac1f989110de15335c91798bcca972e475558365d1989e49f6e',
 'system/etc/imx861bqr_hb722.sp':'590da76edce8bc81ba78c6d6ffa4effca0908926f44a31b2bf419a1e3d61810a',
 'system/etc/iq/hb722_config.json':'2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286',
 'system/lib64/camera/plugins/libdcam_plugins_AIO.so':'1924f9aca6d5f4f92ff482f6a864579d303a890fcef3427053f35d9b00bd4135',
 'system/lib64/libdcam_frwk.so':'5329c95d3c36775fbf1a93bbf1100a766b08bcf4504a2e3a6292bd3fcdb7bf88',
}
TOPO='TPLG_IMX861BQR_LIVEVIEW_12K_11BIT_60FPS'
SEGMENT='common_recording_still_10-sub_back-data_mux0-raw_bin-still'
MODES=['still_4x3_16bit','still_4x3_14bit','still_4x3_14bit_hs']
YUV='DUSS_PIXFMT_YUV8_SP420_YUV'


def pair(s):
    values=[int(x.strip()) for x in s.split(',')]
    require(len(values)==2, 'invalid_dimension_pair')
    return values


def configurations(root):
    c=configparser.ConfigParser(interpolation=None, strict=False)
    c.read(root/'system/etc/imx861bqr_hb722.conf')
    profile=json.loads((root/'system/etc/imx861bqr_hb722.sp').read_text())['stream_profile']
    groups=[g for g in profile['stream_groups'] if g['id']=='comm_still-template-01']
    require(len(groups)==1, 'stream_template_missing')
    g=groups[0];streams={s['id']:s for s in g['streams']}
    filt=[f for f in g['filters'] if f['id']=='liveview_sbpc']
    require(len(filt)==1 and filt[0]['type']=='liveview_sbpc', 'filter_type_changed')
    require(streams['liveview_raw_shadow']['source_filter']==dict(filter_id='shadow_liveview_4',port_index=0), 'raw_shadow_source_changed')
    require(dict(filter_id='shadow_liveview_4',port_index=0) in streams['liveview_rout0']['sink_filters'], 'raw_parent_edge_missing')
    require(streams['liveview_raw_shadow']['sink_filters']==[dict(filter_id='liveview_sbpc',port_index=0)], 'sbpc_input0_changed')
    require(streams['liveview_sout1']['sink_filters']==[dict(filter_id='liveview_sbpc',port_index=1)], 'sbpc_input1_changed')
    require(streams['liveview_after_sbpc']['source_filter']==dict(filter_id='liveview_sbpc',port_index=0), 'sbpc_output0_changed')
    require(streams['liveview_after_sbpc']['sink_filters']==[dict(filter_id='gdc_calc_liveview',port_index=0)], 'sbpc_downstream_changed')
    require(streams['liveview_mee']['source_filter']==dict(filter_id='shadow_mee',port_index=0), 'mee_shadow_changed')
    require(dict(filter_id='shadow_mee',port_index=0) in streams['liveview_sout2']['sink_filters'], 'mee_parent_changed')
    rows=[]
    for mode in MODES:
        require(c[mode+':basic']['template_id']==g['id'], 'mode_template_changed')
        map_section=c[mode+':tplgy_map']['tplgy_map[]']
        require(c[map_section]['repeating_tplgy_id']==TOPO, 'repeating_topology_changed')
        params=dict(x.split('=',1) for x in c[mode+':filter']['liveview_sbpc'].split(';') if x)
        require(params['normal_liveview_topo_id']==TOPO and params['is_bypass']=='false', 'sbpc_configuration_changed')
        desc={}
        for name in ('liveview_rout0','liveview_raw_shadow','liveview_sout1','liveview_after_sbpc','liveview_sout2'):
            sec=c[mode+':'+name]
            desc[name]=dict(default_dimensions=pair(sec['res']),alignment=pair(sec['alignment']),
                declared_format=sec['format'],variable_resolution='DCAM_STREAM_FLAG_VARIABLE_RES' in sec.get('flag',''))
            if 'physical_port' in sec:desc[name]['physical_port']=sec['physical_port']
        for name in ('liveview_sout1','liveview_after_sbpc'):
            require(desc[name]['declared_format']==YUV and desc[name]['default_dimensions']==[1600,1200]
                and desc[name]['alignment']==[256,1], 'YUV_stream_defaults_changed')
        require(desc['liveview_sout1']['physical_port']=='EAGLE2_PORT_SOUT1', 'YUV_physical_port_changed')
        require(desc['liveview_rout0']['declared_format']=='DUSS_PIXFMT_RAW16_OPAQUE', 'raw_parent_format_changed')
        require(desc['liveview_raw_shadow']['declared_format']==YUV, 'shadow_declaration_changed')
        rows.append(dict(mode=mode,template=g['id'],repeating_topology=TOPO,streams=desc))
    # Bound inspection to topology declarations, before tuning values.
    iq=(root/'system/etc/iq/hb722_config.json').read_text()
    module_area=iq[iq.index('topology: {'):iq.index('mode_map : [')]
    matches=re.findall(r'segment_name:\s*"'+re.escape(SEGMENT)+r'"\s*,\s*module:\s*\[([^]]*)\]',module_area)
    require(len(matches)==1, 'preview_module_declaration_ambiguous')
    modules=[x.strip() for x in matches[0].split(',') if x.strip()]
    mode_area=iq[iq.index('mode_map : ['):]
    match=re.search(r'topo_name:\s*"'+re.escape(TOPO)+r'"[^}]*segment_map:\s*\[\s*\{segment_name:\s*"([^"]+)"',mode_area)
    require(match and match[1]==SEGMENT, 'preview_segment_link_changed')
    subset={m:m in modules for m in ('SUB_DEMOSAIC','SUB_CC','SUB_GAMMA','SUB_YCC','MAIN_CCM','MAIN_HNCS','MAIN_3DLUT')}
    require(all(subset[m] for m in ('SUB_DEMOSAIC','SUB_CC','SUB_GAMMA','SUB_YCC')) and not subset['MAIN_CCM'], 'preview_module_membership_changed')
    selected=('liveview_rout0','liveview_raw_shadow','liveview_sout1','liveview_after_sbpc',
        'liveview_after_gdc_calc','liveview_after_gdc','liveview_after_mctf','liveview','liveview_sout2','liveview_mee')
    graph=[dict(stream=n,source=streams[n].get('source_filter'),sinks=streams[n].get('sink_filters',[])) for n in selected]
    return dict(modes=rows,declared_graph=graph,preview_segment=SEGMENT,
        selected_module_membership=subset,module_list_is_not_execution_order=True,
        configured_label_to_SBPC_filter_link_proven=True,
        camera_service_enum_to_running_stream_binding_proven=False,
        RAW_parent_and_shadow_have_different_declared_formats=True,
        actual_runtime_frame_layout_must_be_read=True,
        active_configuration_or_runtime_hardware_order_proven=False)


def original_callbacks(root):
    selected={
      'system/lib64/camera/plugins/libdcam_plugins_AIO.so':[
       '_liveview_sbpc_enqueue_input_frame','_liveview_sbpc_dequeue_processed_result'],
      'system/lib64/libdcam_frwk.so':['cam_stream_filter_eng_process_bypass_v2']}
    reports={}; decoded={}
    for lib,names in selected.items():
        with (root/lib).open('rb') as f:
            e=ELFFile(f);sy=symbols(e);pl,valid=parse_plt(e);require(valid,'PLT_decode_failed')
            cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
            for n in names:
                a,z=sy[n];code=code_slice(e,a,z);ins=list(cs.disasm(code,a));require(len(ins)*4==z,'incomplete_decode')
                by={i.address:i for i in ins};decoded[n]=by
                sites=[dict(site=hex(i.address),callee=pl[int(i.operands[0].imm)]) for i in ins
                    if i.mnemonic=='bl' and pl.get(int(i.operands[0].imm)) in
                    ('normal_liveview_sbpc_proc','cam_stream_filter_eng_process_bypass_v2','buffer_queue_enqueue',
                     'buffer_queue_dequeue_timeout','memcpy','__memcpy_chk')]
                reports[n]=dict(library=lib,start=hex(a),size=z,sha256=hashlib.sha256(code).hexdigest(),selected_calls=sites)
    # Exact semantics at the pinned forwarding call: input bundle slot 1 -> output slot 0.
    en=decoded['_liveview_sbpc_enqueue_input_frame']
    expected={0x36128:('ldr','x0, [x21, #8]'),0x3612c:('add','x1, x21, #0xd8'),
       0x361a4:('ldrsw','x24, [x21, #0xc0]'),0x361ac:('ldr','w23, [x21, #0x198]')}
    for at,(mn,op) in expected.items():require((en[at].mnemonic,en[at].op_str)==(mn,op),'bundle_forward_contract_changed')
    fw=decoded['cam_stream_filter_eng_process_bypass_v2']
    expected={0x208dc4:('ldr','x23, [x1]'),0x208df4:('str','x19, [x23, #0x390]'),
       0x208eb8:('ldr','w8, [x19, #0x28]'),0x208ec0:('str','w8, [x23, #0x28]'),
       0x208efc:('ldr','x9, [x19, #0x20]'),0x208f08:('str','x9, [x23, #0x20]')}
    for at,(mn,op) in expected.items():require((fw[at].mnemonic,fw[at].op_str)==(mn,op),'shared_buffer_contract_changed')
    return dict(functions=reports,forwarded_input_bundle_slot=1,output_bundle_pointer_offset=0xd8,
       output_descriptor_parent_pointer_offset=0x390,shared_memory_handle_offset=0x20,
       output_format_overwritten_from_input=True,output_dimensions_overwritten_from_input=True,
       complete_SBPC_callback_executed=False)


def inspect(root):
    for rel,h in PIN.items():require(hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,'source_hash_mismatch:'+rel)
    return dict(schema='hasselblad-stage41h-stream-contract-v1',status='PASS_original_stream_contract',
        source_sha256=PIN,configuration=configurations(root),original_source=original_callbacks(root),
        actual_camera_pixels_obtained=False,isolated_MAIN_CCM_pixel_pair_proven=False,
        vendor_bytes_disassembly_or_tuning_values_exported=False,phone_app_or_main_changed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=inspect(a.root);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=r['status'],configured_modes=len(r['configuration']['modes']),actual_camera_pixels_obtained=False)))
