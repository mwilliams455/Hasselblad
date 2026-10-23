#!/usr/bin/env python3
"""Exact original SBPC-to-file source graph; no original instruction export."""
import argparse, hashlib, json, sys
from collections import Counter, deque
from pathlib import Path
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG, ARM64_OP_MEM
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'isp_liveview_stage41'))
from inspect_original_liveview_xrefs41b import symbols,code_slice,owner,require
from inspect_original_sbpc_processing41c import parse_plt

PIN={
 'camera/plugins/libdcam_plugins_AIO.so':'1924f9aca6d5f4f92ff482f6a864579d303a890fcef3427053f35d9b00bd4135',
 'libdcam_pp.so':'bacca08dcf56e4a599cbfdfa041baf60a43754ec5a1a9d23dab89bd129ea41e9',
 'libdcam_resource_package_util.so':'dd6ac4a2811a38c1e94431a47dd69a7607639035999abeb1277ac01b2f0a6c39',
 'libdcam_base.so':'8486fa7ce0b400992358ad92c445ad026a3784703accf2bae8a490ed10b2ff52',
 'libduml_hal.so':'adfb1cf834584d5c2d3e7b8a49c8ff78a919f007b4fe4ee5442a658dafc71d20',
}
SELECTED={
 'camera/plugins/libdcam_plugins_AIO.so':['_calculate_out_result_frame_buffer_info',
    '_process_on_buffer','_liveview_sbpc_enqueue_input_frame','_liveview_sbpc_dequeue_processed_result',
    '_draw_bad_pixel_in_liveview','_dump_yuv_with_bad_pixel','_dump_raw_with_bad_pixel','_draw_normal'],
 'libdcam_pp.so':['normal_liveview_sbpc_proc','proc_liveview_sbpc'],
 'libdcam_resource_package_util.so':['cam_dump_frame'],
 'libdcam_base.so':['dump_frame_to_file','_fwrite_data','frame_buffer_plane_info_generate'],
 'libduml_hal.so':['duss_hal_mem_map'],
}
FOCAL={'normal_liveview_sbpc_proc','proc_liveview_sbpc','_dump_yuv_with_bad_pixel',
       '_dump_raw_with_bad_pixel','_draw_bad_pixel_in_liveview','_draw_normal',
       'cam_dump_frame','dump_frame_to_file','_fwrite_data','fwrite',
       'duss_hal_mem_map','duss_hal_mem_sync','duss_hal_mem_sync_ext','duss_hal_mem_unmap',
       'frame_buffer_cp','cam_frame_buffer_alloc','cam_frame_buffer_free',
       'pp_get_duss_hal_mem_phys_addr','pp_get_duss_hal_mem_virt_addr','pp_map_ss_virt_addr',
       'frame_buffer_plane_info_generate','buffer_queue_enqueue','buffer_queue_dequeue_timeout'}


def reachable(insns,start,end,forbidden=()):
    by={i.address:i for i in insns}
    q=deque([start]);seen=set()
    while q:
        pc=q.popleft()
        if pc==end:return True
        if pc in seen or pc not in by or pc in forbidden:continue
        seen.add(pc);i=by[pc];m=i.mnemonic
        imm=[int(o.imm) for o in i.operands if o.type==ARM64_OP_IMM]
        if m in ('ret','br'):continue
        if m=='b':q.extend(imm[-1:])
        elif m.startswith('b.') or m in ('cbz','cbnz','tbz','tbnz'):
            q.extend(imm[-1:]);q.append(pc+4)
        else:q.append(pc+4)
    return False


def inspect(root):
    reports={};private={}
    for lib,chosen in SELECTED.items():
        path=root/lib
        require(hashlib.sha256(path.read_bytes()).hexdigest()==PIN[lib], 'source_hash_mismatch_'+lib)
        with path.open('rb') as stream:
            e=ELFFile(stream);sy=symbols(e);pl,ok=parse_plt(e);require(ok,'plt_mapping_failed')
            by={}
            for n,(a,z) in sy.items():by.setdefault(a,[]).append((n,z))
            cs=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);cs.detail=True
            rows={}
            for name in chosen:
                require(name in sy,'selected_function_missing_'+name)
                a,z=sy[name];code=code_slice(e,a,z);ins=list(cs.disasm(code,a))
                require(len(ins)*4==z,'incomplete_decode')
                calls=Counter();sites=[];indirect=[];allcalls=[]
                for i in ins:
                    if i.mnemonic=='bl':
                        dst=int(i.operands[0].imm);n=pl.get(dst) or owner(dst,by)
                        calls[n]+=1;allcalls.append((i.address,n))
                        if n in FOCAL:sites.append(dict(site=hex(i.address),callee=n,
                                                       linkage='PLT' if dst in pl else 'local'))
                    elif i.mnemonic in ('blr','br'):indirect.append(dict(site=hex(i.address),kind=i.mnemonic))
                rows[name]=dict(start=hex(a),bytes=z,sha256=hashlib.sha256(code).hexdigest(),
                                direct_call_count=sum(calls.values()),focal_call_sites=sites,
                                focal_counts={n:c for n,c in calls.items() if n in FOCAL},
                                indirect_transfers=indirect)
                private[(lib,name)]=(ins,allcalls)
            reports[lib]=dict(sha256=PIN[lib],functions=rows)
    aio='camera/plugins/libdcam_plugins_AIO.so'
    ins,calls=private[(aio,'_liveview_sbpc_enqueue_input_frame')]
    proc=[a for a,n in calls if n=='normal_liveview_sbpc_proc']
    dumps=[a for a,n in calls if n=='_dump_yuv_with_bad_pixel']
    require(len(proc)==1 and len(dumps)==2,'sbpc_callsite_contract_changed')
    require(dumps[0]<proc[0]<dumps[1],'unexpected_sbpc_site_order')
    require(reachable(ins,dumps[0],proc[0]) and reachable(ins,proc[0],dumps[1]),
            'before_after_source_path_not_reachable')
    by={i.address:i for i in ins}
    # Verify the shared frame carrier, without relying on a nearby function name.
    frame_load=by[0x35a18]
    require(frame_load.mnemonic=='ldr' and frame_load.reg_name(frame_load.operands[0].reg)=='x19'
            and frame_load.reg_name(frame_load.operands[1].mem.base)=='x21'
            and frame_load.operands[1].mem.disp==8,'input_frame_slot_changed')
    for at in (0x35b7c,0x36190):
        i=by[at]
        require(i.mnemonic=='mov' and i.reg_name(i.operands[0].reg)=='x1'
                and i.reg_name(i.operands[1].reg)=='x19','dump_frame_argument_changed')
    carrier_writes=[]
    for i in ins:
        _,writes=i.regs_access()
        if any(i.reg_name(r)=='x19' for r in writes):carrier_writes.append(hex(i.address))
    clobbers={int(pc,16) for pc in carrier_writes}
    require(reachable(ins,dumps[0],proc[0],clobbers)
            and reachable(ins,proc[0],dumps[1],clobbers),'shared_frame_carrier_path_not_proven')
    # The parameter structure is passed at SP+0x48 and receives RAW/YUV pointers at +0x78/+0x80.
    st=by[0x35fd8]
    require(st.mnemonic=='stp' and [st.reg_name(o.reg) for o in st.operands[:2]]==['x23','x19']
            and st.operands[2].mem.disp==0xc0,'processor_frame_parameters_changed')
    read=reports[aio]['functions']['_calculate_out_result_frame_buffer_info']
    require(read['focal_counts'].get('duss_hal_mem_map')==1,'small_result_map_edge_missing')
    for name in ('_dump_yuv_with_bad_pixel','_dump_raw_with_bad_pixel'):
        din,dcalls=private[(aio,name)]
        sites={n:[at for at,callee in dcalls if callee==n]
               for n in ('frame_buffer_cp','_draw_normal','cam_dump_frame')}
        require(all(len(v)==1 for v in sites.values()),'diagnostic_clone_draw_export_changed')
        cp,draw,export=(sites[n][0] for n in ('frame_buffer_cp','_draw_normal','cam_dump_frame'))
        require(cp<draw<export and reachable(din,cp,draw) and reachable(din,draw,export),
                'diagnostic_draw_path_not_reachable')
    return dict(schema='hasselblad-stage41g-original-sbpc-pixel-route-v1',
                status='PASS_original_SBPC_pixel_export_source_graph',sources=reports,
                sbpc_frame_path=dict(before_dump_site=hex(dumps[0]),processor_site=hex(proc[0]),
                    after_dump_site=hex(dumps[1]),static_control_flow_reachable=True,
                    call_returns_assumed_for_static_reachability=True,
                    frame_bundle_pointer_offset=8,shared_frame_carrier='x19',
                    static_path_preserving_frame_carrier_exists=True,
                    carrier_write_sites=carrier_writes,processor_parameter_raw_pointer_offset=0x78,
                    processor_parameter_yuv_pointer_offset=0x80,
                    runtime_branch_execution_proven=False),
                diagnostic_dump_helpers_can_draw_on_copied_pixels=True,
                diagnostic_dump_helpers_are_pristine_pixel_references=False,
                generic_exporter_available_without_diagnostic_draw=True,
                actual_camera_pixels_obtained=False,
                link_to_camera_service_stream_name_table_proven=False,
                isolated_MAIN_CCM_before_after_proven=False,
                vendor_instruction_bytes_or_disassembly_exported=False,
                camera_hardware_accessed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lib-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=inspect(a.lib_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'selected_libraries':len(r['sources']),
                      'actual_camera_pixels_obtained':False}))

if __name__=='__main__':main()
