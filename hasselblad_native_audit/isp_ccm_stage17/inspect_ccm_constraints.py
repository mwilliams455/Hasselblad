#!/usr/bin/env python3
"""Stage17 exact-source structural CCM investigation (no pixel renderer).

The original X2DII 1.3.16.2 IQ and vcam driver remain temporary; results exclude
vendor coefficient values, matrices, binaries, pixels, and instruction streams.

Source work: math reconstruction and bounded device/ELF inspection. Never call
this a proof of an RGB pixel equation or of ISP operation in live photography.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

CONFIG_SHA = "2a4fd76e5299937a6607da8454add17e9746347c54adcf5da1360799de634286"
DRIVER_SHA = "29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e"
RCAM_SHA = "3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66"
CCM_SOURCE_SHA = "59d1b6c8a291280a8749f5ca190370e5dbff8ce0e6694a7da779ae5488ae641e"
PARSER_SHA = "0d3c8a7c380502c2b904e380d64723523eb62060a2c4e31145104aa9445625ec"
KNOTS = (2400, 3050, 5550, 9100)
TEST_CCTS = (2000,2400,2725,3050,4300,5550,7001,9100,12000)
TEST_HISO_WEIGHTS = (0,64,128,192,256)


def require(ok: bool, reason: str):
    if not ok: raise ValueError(reason)


def sha(path: Path) -> str:
    with path.open("rb") as source: return hashlib.file_digest(source,"sha256").hexdigest()


def lerp(a: int,b: int,q8: int) -> int:
    return a + ((b-a)*q8//256)


def coeff(cct: int) -> tuple[int,int]:
    if cct<KNOTS[0]: return 0,0
    if cct>=KNOTS[-1]: return 2,256
    for k in range(3):
        if KNOTS[k]<=cct<KNOTS[k+1]:
            return k,((cct-KNOTS[k])*256)//(KNOTS[k+1]-KNOTS[k])
    raise AssertionError("unreachable")


def prepare(values: list[int], cct:int, hiso_weight:int) -> list[int]:
    require(len(values)==768,"bad_coefficients_shape")
    require(isinstance(hiso_weight,int) and 0<=hiso_weight<=256,"bad_hiso_weight")
    i,w=coeff(cct)
    r=[]
    for k in range(96):
        low=lerp(values[i*96+k],values[(i+1)*96+k],w)
        high=lerp(values[(i+4)*96+k],values[(i+5)*96+k],w)
        r.append(lerp(low,high,hiso_weight))
    return r


def identity_groups(sequences):
    classes=[]
    for i,a in enumerate(sequences):
        for cls in classes:
            if a==sequences[cls[0]]:
                cls.append(i);break
        else:classes.append([i])
    return classes


def data_summary(values:list[int], show_hidden_for_self_test:bool=False)->dict:
    """Source-conditioned relationships, NOT individual vendor coefficients."""
    require(type(values) is list and len(values)==768 and all(type(x) is int and -32768<=x<=32767 for x in values),"bad_768_signed16_ccm")
    profiles=[values[k*96:(k+1)*96] for k in range(8)]
    group_invariance=[all(q[k*6:(k+1)*6]==q[:6] for k in range(16)) for q in profiles]
    require(all(group_invariance),"unexpected_region_variation")
    require(profiles[:4]==profiles[4:],"unexpected_high_iso_bank_variation")
    primary=[p[:6] for p in profiles[:4]]
    cct_eq=identity_groups(primary)
    varying_mask=[len({p[j] for p in primary})>1 for j in range(6)]
    zero_masks=[[v==0 for v in p] for p in primary]
    signs=[["+" if v>0 else "-" if v<0 else "0" for v in p] for p in primary]
    derived=[]
    for c in TEST_CCTS:
        outputs=[prepare(values,c,w) for w in TEST_HISO_WEIGHTS]
        region_ok=all(all(output[6*k:6*k+6]==output[:6] for k in range(16)) for output in outputs)
        iso_equal=all(o==outputs[0] for o in outputs[1:])
        require(region_ok and iso_equal,"interpolation_invariance_failed")
        ci,w=coeff(c)
        derived.append({"cct_kelvin":c,"cct_pair_index":ci,"cct_fraction_q8":w,
                        "prepared_ccm_group_count":16,"prepared_ccm_unique_row_groups":1,
                        "hiso_weight_0_to_256_identical":iso_equal,
                        "status":"observed_from_original_input_reconstruction"})
    require(prepare(values,2400,0)==profiles[0],"anchor_mismatch")
    require(prepare(values,9100,256)==profiles[3],"last_anchor_mismatch")
    return {
        "physical_table":{"firmware":"Hasselblad X2D II 100C 1.3.16.2","ccm_source_values":768,
                          "source_profiles":8,"stored_regions_per_profile":16,"signed_parameters_per_region":6,
                          "source_profile_secondary_bank_count":2,
                          "all_eight_source_profiles_have_equal_16_six_value_rows":all(group_invariance),
                          "both_high_iso_source_banks_identical":profiles[:4]==profiles[4:],
                          "cct_anchors_k":list(KNOTS),"cct_anchor_profile_equal_index_groups":cct_eq,
                          "independent_group_positions_per_anchor":6,
                          "varying_coeff_positions_across_four_cct_anchors":varying_mask,
                          "zero_coeff_positions_per_cct_anchor":zero_masks,
                          "sign_class_per_cct_anchor":signs,
                          "absolute_coefficients_exported":False,
                          "vendor_color_matrix_payload_exported":False},
        "prepared_subsets":derived,
        "analysis_limits":[
            "Group coefficient equality does not prove that the ISP ignores the 16-region selector.",
            "Six stored values per region do not imply a 2x3, 3x2, 3x3, or other particular RGB matrix.",
            "The source high-ISO banks match; runtime overrides and other IQ data groups remain unverified.",
            "No coefficient Q scale, hue/channel selector, clipping, quantization or gamma/3D-LUT handoff has been established.",
            "Prepared SOURCE data is not a live ISP register dump or recorded photographic output." ]}


def self_test():
    # Every profile contains 16 identical 6-tuples but banks are equal.
    p=[]
    for bi in range(2):
        for cct_index in range(4):
            six=[(cct_index*31 + i*13)%200-100 for i in range(6)]
            p.extend(six*16)
    r=data_summary(p)
    assert r["physical_table"]["cct_anchor_profile_equal_index_groups"] == [[0],[1],[2],[3]]
    assert all(r["physical_table"]["varying_coeff_positions_across_four_cct_anchors"])
    assert all(x["hiso_weight_0_to_256_identical"] for x in r["prepared_subsets"])
    assert lerp(-30,7,128)==-12  # signed arithmetic uses floor
    assert len(prepare(p,4300,256))==96
    assert prepare(p,2400,0)==prepare(p,2400,256)
    assert prepare(p,5500,0)==prepare(p,5500,256)
    assert coeff(12000)==(2,256)
    assert coeff(-100)==(0,0)
    for index in (0,1):
        broken=p.copy(); broken[index*96+7]+=1
        try: data_summary(broken)
        except ValueError: pass
        else: raise AssertionError("region invariance gate failed")
    broken=p.copy();broken[4*96+0]+=1
    try: data_summary(broken)
    except ValueError: pass
    else: raise AssertionError("high iso mismatch not rejected")
    print(json.dumps({"status":"PASS","self_test":"synthetic_varying_CCT_duplicate_regions_and_two_equal_ISO_banks","positive_groups":9,"negative_inputs_rejected":3,
                      "vendor_assets_loaded":False,"photographic_renderer_implemented":False}))


def use_original(root:Path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    import sys
    root=root.resolve()
    lib=root/'system/lib64/librcam.so'
    config=root/'system/etc/iq/hb722_config.json'
    driver=root/'system/lib/modules/vcam_driver.ko'
    parser=Path(__file__).resolve().parents[1]/'photographic_path/inspect_iq_config.py'
    require(sha(lib)==RCAM_SHA and sha(config)==CONFIG_SHA and sha(driver)==DRIVER_SHA and sha(parser)==PARSER_SHA,"wrong_vendor_source_identity")
    spec=importlib.util.spec_from_file_location("stage17_pinned_iq_parser",parser)
    require(spec is not None and spec.loader is not None,"no_hash_pinned_parser")
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    conf=module.read_config(config)
    main=conf['iq_table']['data'][0]['main_ccm'][0]
    values=main['lmtx_fw']
    require(hashlib.sha256(struct.pack('<768i',*values)).hexdigest()==CCM_SOURCE_SHA,"coefficient_source_changed")
    require(conf['iq_table']['module']['main_ccm']['lmtx_fw']==
            {"type":"lerp_1d_lut_reg_idx_v5","group":"global_frame","axis":["cc_color_temp","color_hiso"],"total":16},"CCM_axes_changed")
    result=data_summary(values)
    data=conf['iq_table']['data']
    summary=[]
    for i,dat in enumerate(data):
        q=dat.get('main_ccm') if isinstance(dat,dict) else None
        if not isinstance(q,list): continue
        for ri,entry in enumerate(q):
            if not isinstance(entry,dict):continue
            keys=sorted(entry.keys())
            en={x:{"count":len(entry[x]),"all_zero":all(v==0 for v in entry[x])}
                for x in ('enable_lpf','enable_hue_mod','enable_desaturation','enable_level_ctrl')
                if isinstance(entry.get(x),list)}
            summary.append({"iq_data_index":i,"main_ccm_record_index":ri,"parameter_names":keys,
                            "selected_enable_flags":en,
                            "lmtx_fw_present":isinstance(entry.get('lmtx_fw'),list),
                            "lmtx_fw_count":len(entry.get('lmtx_fw',[])),
                            "lmtx_fw_values_exported":False})
    result['related_iq_ccm_modes']=summary
    fields=conf['iq_table']['module']['main_ccm']
    result['module_parameter_metadata']=[{"name":k,"type":v.get('type'),"group":v.get('group'),
                                         "axis":v.get('axis'),"total":v.get('total')}
                                         for k,v in sorted(fields.items()) if isinstance(v,dict)]
    # Validate targeted original code identities and distinguish register
    # submission routines from actual RGB multiply loops.
    planned={'ccm_set_fn0_config':(0x30e40,92),
             'ccm_set_ig0_config':(0x30e9c,1280),
             'ccm_set_fmt':(0x314c8,80)}
    with driver.open('rb') as fh:
        elf=ELFFile(fh)
        require(elf['e_type']=='ET_REL' and elf['e_machine']=='EM_AARCH64',"unexpected_kernel_module")
        txt=elf.get_section_by_name('.text').data()
        sec=elf.get_section_by_name('.symtab')
        sym={s.name:s for s in sec.iter_symbols()}
        for n,(off,size) in planned.items():
            require(n in sym and (sym[n]['st_value'],sym[n]['st_size'])==(off,size),"unexpected_original_ccm_function_"+n)
        interesting=['ccm_set_fn0_config','ccm_set_ig0_config','ccm_set_fmt','lite_ccm_set_info','ccm_get_dbg_info_by_mux']
        decoder=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
        exports=[]
        for n in interesting:
            s=sym.get(n)
            if s is None: continue
            off,size=int(s['st_value']),int(s['st_size'])
            require(0<size<10000 and off+size<=len(txt),"unexpected_ccm_function_extent_"+n)
            code=txt[off:off+size]
            ins=list(decoder.disasm(code,off))
            require(len(ins)*4==size,"could_not_decode_"+n)
            opcounts={m:sum(i.mnemonic==m for i in ins) for m in ('mul','madd','smaddl','fmul','fmadd','sdiv','udiv','bl','blr')}
            exports.append({"function":n,"text_offset_hex":hex(off),"instruction_count":len(ins),
                            "function_sha256":hashlib.sha256(code).hexdigest(),
                            "math_or_call_instruction_counts":opcounts,
                            "register_setter_or_debug_not_rgb_pixel_oracle":True})
        result['original_driver_functions']=exports
    result.update({"schema":"hasselblad-stage17-original-main-ccm-numeric-constraints-v1",
                   "status":"source_constraints_verified",
                   "source":"original_sha256_pinned_X2D_II_1.3.16.2_IQ_and_driver",
                   "original_librcam_sha256":RCAM_SHA,"original_vcam_driver_sha256":DRIVER_SHA,
                   "original_iq_config_sha256":CONFIG_SHA,
                   "vendor_firmware_executed":False,"vendor_instructions_exported":False,
                   "vendor_ccm_coefficient_bytes_exported":False,
                   "new_original_main_pixel_ccm_equation_proven":False,
                   "CCM_pixel_application_authorized":False,
                   "production_colour_still_photon":True})
    return result


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--self-test',action='store_true')
    a.add_argument('--firmware-root',type=Path)
    a.add_argument('--output',type=Path)
    z=a.parse_args()
    if z.self_test:
        self_test();return
    require(z.firmware_root is not None and z.output is not None,"firmware-root_and_output_required")
    result=use_original(z.firmware_root)
    z.output.parent.mkdir(parents=True,exist_ok=True)
    z.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({"status":result['status'],"profiles":len(result['physical_table']['cct_anchor_profile_equal_index_groups']),
          "CCM_mode_count":len(result['related_iq_ccm_modes']),
          "driver_functions":len(result['original_driver_functions']),
          "pixel_equation_verified":False}))

if __name__=='__main__':main()
