#!/usr/bin/env python3
"""Stage26: verify second TA UUID truly reaches original eFuse TEE session.

Independent bounded AArch64 CFG dominance check for each already validated
literal-UUID load -> 16-byte SP+48 store -> TEEC_OpenSession chain.
No original binary instructions/pseudocode or unknown literals exported.
No eFuse, TEE or camera operation executed; no TBIE key or plaintext exposed.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

from trace_efuse_session24 import backing_elf,FILE,SHA
from trace_stack_uuid25 import audit as audit25,STACK_UUID
from trace_efuse_session24 import audit as audit24

EXPECTED={
 "efuse_pro":{"load":0x2ae4,"store":0x2ae8,"open":0x2b28},
 "pro_state":{"load":0x2c0c,"store":0x2c10,"open":0x2c50},
 "sec_debug_state":{"load":0x2d70,"store":0x2d74,"open":0x2db8},
}
TA_ID="e91c9402-64a0-470f-88e7-bf5d3c606b6a"

def successors(insns):
    from capstone.arm64 import ARM64_OP_IMM
    addresses={x.address for x in insns}
    edges={}
    for ins in insns:
        a=ins.address;m=ins.mnemonic
        ft=a+4
        if m in ("ret","eret","br","braa","brab"):
            targets=[]
        elif m=="b":
            if ins.operands and ins.operands[-1].type==ARM64_OP_IMM:
                t=int(ins.operands[-1].imm)
                targets=[t] if t in addresses else []
            else:targets=[]
        elif m.startswith("b.") or m in ("cbz","cbnz","tbz","tbnz"):
            if not ins.operands or ins.operands[-1].type!=ARM64_OP_IMM:
                targets=[ft] if ft in addresses else []
            else:
                t=int(ins.operands[-1].imm)
                targets=([t] if t in addresses else [])+([ft] if ft in addresses else [])
        else:
            targets=[ft] if ft in addresses else []
        edges[a]=sorted(set(targets))
    return edges

def reachable(graph,start,end,remove=None):
    if start==remove:return False
    queue=[start];visited=set()
    while queue:
        a=queue.pop()
        if a==end:return True
        if a in visited or a==remove:continue
        visited.add(a)
        if len(visited)>1000:raise ValueError("CFG_node_budget")
        queue.extend(x for x in graph.get(a,[]) if x!=remove)
    return False

def touching_uuid_stack(ins):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM
    if ins.mnemonic not in ("str","stur","stp","stnp"):return False
    ops=ins.operands
    if ins.mnemonic in ("stp","stnp"):
        if len(ops)<3 or ops[2].type!=ARM64_OP_MEM:return False
        mem=ops[2].mem; src=ops[0]
        total_width=2*(16 if src.type==ARM64_OP_REG and ins.reg_name(src.reg).startswith("q") else
                       8 if src.type==ARM64_OP_REG and ins.reg_name(src.reg).startswith("x") else 4)
    else:
        if len(ops)<2 or ops[1].type!=ARM64_OP_MEM:return False
        mem=ops[1].mem; src=ops[0]
        n=ins.reg_name(src.reg) if src.type==ARM64_OP_REG else ""
        total_width=16 if n.startswith("q") else 8 if n.startswith("x") else 4
    if ins.reg_name(mem.base)!="sp" or mem.index or ins.writeback:return False
    offset=int(mem.disp)
    return offset<STACK_UUID+16 and offset+total_width>STACK_UUID

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("wrong_firmware")
    funcs,plt,uuidbytes=backing_elf(root/FILE)
    prior25=audit25(root)
    prior24=audit24(root)
    old25={x["function"]:x for x in prior25["static_results"]}
    old24={x["function"]:x for x in prior24["resolved_relevant_tee_calls"] if x["api"]=="TEEC_OpenSession"}
    from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
    result=[]
    for func,p in EXPECTED.items():
        insns=funcs.get(func)
        if not insns:raise ValueError("original_function_missing_"+func)
        by={x.address:x for x in insns}
        if not all(v in by for v in p.values()):raise ValueError("missing_original_site_"+func)
        load,store,open_at=(by[p[k]] for k in ("load","store","open"))
        if load.mnemonic not in ("ldr","ldur") or store.mnemonic not in ("str","stur") or open_at.mnemonic!="bl":
            raise ValueError("original_load_store_open_site_mnemonic_changed")
        if len(load.operands)<2 or len(store.operands)<2 or load.operands[0].type!=ARM64_OP_REG or store.operands[0].type!=ARM64_OP_REG:
            raise ValueError("original_UUID_copy_operands_changed")
        register=load.reg_name(load.operands[0].reg)
        if not register.startswith("q") or store.reg_name(store.operands[0].reg)!=register:
            raise ValueError("original_UUID_16byte_value_copy_reg_changed")
        if not touching_uuid_stack(store):
            raise ValueError("original_16byte_uuid_store_target_changed")
        if not open_at.operands or open_at.operands[0].type!=ARM64_OP_IMM:
            raise ValueError("original_OpenSession_call_unresolved")
        if plt.get(int(open_at.operands[0].imm))!="TEEC_OpenSession":
            raise ValueError("original_session_symbol_changed")
        edges=successors(insns);entry=insns[0].address
        load_dom=reachable(edges,entry,p["store"]) and not reachable(edges,entry,p["store"],remove=p["load"])
        store_dom=reachable(edges,entry,p["open"]) and not reachable(edges,entry,p["open"],remove=p["store"])
        overwrite=[hex(i.address) for i in insns if
                   p["store"]<i.address<p["open"] and touching_uuid_stack(i)]
        rec25=old25[func]["session_sites"]
        rec24=old24[func]["static_register_provenance"]
        static_uuid=any(x.get("session_call_va")==hex(p["open"]) and
            x.get("stack_UUID_matches_known_TA_filename")==TA_ID for x in rec25)
        sp_pointer=rec24.get("stack_based_argument") is True and rec24.get("offset")==STACK_UUID
        result.append({"function":func,
            "public_known_TA_filename_UUID":TA_ID,
            "load_16byte_uuid_at_va":hex(p["load"]),
            "store_16byte_uuid_at_va":hex(p["store"]),
            "open_session_va":hex(p["open"]),
            "static_byte_match_to_known_TA":static_uuid,
            "literal_load_dominates_uuid_store":load_dom,
            "uuid_store_dominates_OpenSession":store_dom,
            "overlapping_uuid_stack_stores_between_store_and_OpenSession":overwrite,
            "OpenSession_uuid_argument_is_sp_plus_48":sp_pointer,
            "exact_static_uuid_to_session_interface_proven":
                all((static_uuid,load_dom,store_dom,sp_pointer,not overwrite)),
            "secure_world_session_executed":False})
    return {"schema":"hasselblad-stage26-original-efuse-TEE-UUID-CFG-proof-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "original_source_sha256":SHA,
            "functions":result,
            "full_original_TEE_key_derivation_proven":False,
            "encrypted_protected_TA_decompiled":False,
            "eFuse_or_firmware_operations_executed":False,
            "vendor_instructions_or_raw_secret_bytes_exported":False}

def synthetic():
    g={0:[4,8],4:[12],8:[12],12:[16],16:[]}
    assert reachable(g,0,16)
    assert not reachable(g,0,16,remove=12)
    assert reachable(g,0,16,remove=4)
    assert len(EXPECTED)==3
    return {"status":"PASS_synthetic","checks":4,"original_firmware_read":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_hash_pinned_verified"),
        "TA_session_chains_proven":sum(x["exact_static_uuid_to_session_interface_proven"]
             for x in d.get("functions",[])),"secret_key_recovered":False},sort_keys=True))
if __name__=="__main__":main()
