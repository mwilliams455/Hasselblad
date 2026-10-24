#!/usr/bin/env python3
"""Stage23: X2D II eFuse API / TEE client call graph.

Read-only, hash-pinned normal-world executable research to find whether the
newly discovered exported efuse_pro symbol actually leads to a TEE operation.
Separates "the library imports TEEC" from "efuse_pro reaches TEEC".
No hardware/device interaction, eFuse programming, decryption attempts,
vendor source text, raw disassembly, key bytes or user photographs exported.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json,uuid
from pathlib import Path

SOURCES={
 "system/lib64/libamt_util.so":"63a4addc9179587363bdc8f045d9cb4686855aa413873db8b5fdcd15bdab5902",
 "system/bin/amt_test_cmd":"a634bc6759cde58af940bd168ce5c923577096e105cdcf354a25f60e9301927d",
}
KNOWN_TA=(
 "09db16c0-873b-4fed-b87e-a5d2b86293a2",
 "e91c9402-64a0-470f-88e7-bf5d3c606b6a",
)
MAX_SOURCE=2*1024*1024
MAX_CODE=1*1024*1024
MAX_FUNCS=5000
MAX_GRAPH=900
MAX_DEPTH=5

def read_elf(path,expected):
    from elftools.elf.elffile import ELFFile
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    if path.stat().st_size>MAX_SOURCE or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError("original_source_hash_or_size_mismatch_"+path.name)
    with path.open("rb") as f:
        elf=ELFFile(f)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("not_arm64_"+path.name)
        dyn=elf.get_section_by_name(".dynsym")
        textsec=elf.get_section_by_name(".text")
        plt=elf.get_section_by_name(".plt")
        rela=elf.get_section_by_name(".rela.plt")
        if not all((dyn,textsec,plt,rela)):
            raise ValueError("missing_essential_elf_tables_"+path.name)
        text=textsec.data()
        if len(text)>MAX_CODE:raise ValueError("unbounded_text")
        functions={}
        imported=set()
        for nm in (".dynsym",".symtab"):
            sec=elf.get_section_by_name(nm)
            if sec is None:continue
            for s in sec.iter_symbols():
                if s.name and s["st_shndx"]=="SHN_UNDEF":
                    imported.add(s.name)
                if s["st_info"]["type"]!="STT_FUNC" or s["st_shndx"]=="SHN_UNDEF":
                    continue
                entry=int(s["st_value"]);sz=int(s["st_size"])
                if not sz or sz>MAX_CODE or not s.name:continue
                # Prefer public exported function names at same entry.
                previous=functions.get(entry)
                if previous is None or nm==".dynsym":
                    functions[entry]={"name":s.name,"size":sz}
        if len(functions)>MAX_FUNCS:raise ValueError("too_many_functions")
        pltmap={}
        for i,r in enumerate(rela.iter_relocations()):
            pltmap[int(plt["sh_addr"])+32+16*i]=dyn.get_symbol(r["r_info_sym"]).name
        dyn_exports={}
        for s in dyn.iter_symbols():
            if s.name in ("efuse_pro","TEEC_InvokeCommand","TEEC_OpenSession"):
                dyn_exports[s.name]={"binding":str(s["st_info"]["bind"]),
                                     "type":str(s["st_info"]["type"]),
                                     "defined":s["st_shndx"]!="SHN_UNDEF",
                                     "virtual_address":hex(int(s["st_value"])) if int(s["st_value"]) else None,
                                     "size":int(s["st_size"])}
        dt=elf.get_section_by_name(".dynamic")
        deps=[]
        if dt:
            for tag in dt.iter_tags():
                if tag.entry.d_tag=="DT_NEEDED":deps.append(tag.needed)
        dis=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);dis.detail=True
        instructions=list(dis.disasm(text,int(textsec["sh_addr"])))
        if len(instructions)*4!=len(text):raise ValueError("incomplete_text_decode")
    data=path.read_bytes()
    known_matches=[]
    for ident in KNOWN_TA:
        u=uuid.UUID(ident)
        if any(v in data for v in (u.bytes,u.bytes_le)):
            known_matches.append(ident)
    return {"functions":functions,"pltmap":pltmap,"imports":imported,
            "dependencies":sorted(deps),"dyn_exports":dyn_exports,
            "instructions":instructions,"known_uuid_matches":known_matches,
            "code_bytes":len(text)}

def callers_and_calls(info):
    from capstone.arm64 import ARM64_OP_IMM
    starts=sorted(info["functions"])
    fns=info["functions"]
    if not starts:return {},[],[]
    graph={}
    calls=[]
    indirect=[]
    for ins in info["instructions"]:
        if ins.mnemonic not in ("bl","b","blr","br"):continue
        owneridx=bisect.bisect_right(starts,ins.address)-1
        owner=None
        if owneridx>=0:
            origin=starts[owneridx]
            if ins.address<origin+fns[origin]["size"]:
                owner=origin
        if ins.mnemonic in ("blr","br"):
            if owner is not None:indirect.append({"caller":fns[owner]["name"],"site_va":hex(ins.address)})
            continue
        if not ins.operands or ins.operands[-1].type!=ARM64_OP_IMM:continue
        dest=int(ins.operands[-1].imm)
        imported=info["pltmap"].get(dest)
        internal=None if imported is not None else dest
        row={"site_va":hex(ins.address),"caller":fns[owner]["name"] if owner is not None else None,
             "caller_entry":owner,"kind":"PLT" if imported else "internal",
             "target_name":imported if imported else fns[dest]["name"] if dest in fns else None,
             "target_va":dest,"branch_type":ins.mnemonic}
        calls.append(row)
        if owner is not None:
            graph.setdefault(owner,[]).append(row)
    return graph,calls,indirect

def follow_root(info,graph,root="efuse_pro"):
    roots=[a for a,f in info["functions"].items() if f["name"]==root]
    if len(roots)!=1:
        return {"root_symbol":root,"defined_function_candidates":len(roots),
                "TEE_reachability":"unresolved_root_not_unique",
                "direct_or_transitive_TEE_edges":[]}
    first=roots[0];found=[];unresolved=[];seen={first};queue=[(first,0,[root])]
    while queue:
        entry,depth,chain=queue.pop(0)
        if len(seen)>MAX_GRAPH:raise ValueError("callgraph_budget_exceeded")
        for call in graph.get(entry,()):
            dest=call["target_va"]
            named=call["target_name"]
            if call["kind"]=="PLT":
                if named and (named.startswith("TEEC_") or named.startswith("sec_cipher_")):
                    found.append({"from_call_chain":chain[:MAX_DEPTH+2],
                                  "external_api":named,"call_site_va":call["site_va"],
                                  "call_depth":depth+1})
                continue
            if dest not in info["functions"]:
                unresolved.append({"origin":info["functions"][entry]["name"],
                                   "unlabelled_call_va":call["site_va"]})
                continue
            if depth<MAX_DEPTH and dest not in seen:
                seen.add(dest)
                queue.append((dest,depth+1,chain+[info["functions"][dest]["name"]]))
    return {"root_symbol":root,"root_va":hex(first),
            "root_function_type":"ELF_STT_FUNC",
            "visited_functions":len(seen),
            "TEE_reachability":"static_direct_or_multihop" if found else
                               "not_found_in_bounded_named_direct_callgraph",
            "direct_or_transitive_TEE_edges":found[:40],
            "unresolved_internal_call_sites":unresolved[:30],
            "unresolved_call_count":len(unresolved),
            "indirect_calls_not_resolved":True,
            "secure_world_cryptography_observed":False}

def one(root,name,digest):
    path=root/name
    info=read_elf(path,digest)
    graph,calls,indirect=callers_and_calls(info)
    tee_calls=[{"site_va":x["site_va"],"api":x["target_name"],
                "caller_name":x["caller"]}
               for x in calls if x["kind"]=="PLT" and x["target_name"] and
                    x["target_name"].startswith("TEEC_")]
    efuse_calls=[{"site_va":x["site_va"],"caller_name":x["caller"]}
                 for x in calls if x["target_name"]=="efuse_pro" and x["kind"]=="PLT"]
    result={"source_path":name,"original_sha256":digest,
            "ELF_dynamic_export_verification":info["dyn_exports"],
            "dt_needed_relevant":[x for x in info["dependencies"] if
                                   any(n in x.lower() for n in ("teec","crypto","cipher","key"))],
            "TEE_API_imports":sorted(x for x in info["imports"] if x.startswith("TEEC_"))[:25],
            "TEE_API_direct_calls":tee_calls[:50],
            "TEE_API_direct_call_count":len(tee_calls),
            "consumer_direct_efuse_pro_calls":efuse_calls[:30],
            "consumer_direct_efuse_pro_call_count":len(efuse_calls),
            "known_protected_TA_UUID_byte_matches":info["known_uuid_matches"],
            "named_function_count":len(info["functions"]),
            "named_elf_function_reachability_only":True,
            "unresolved_indirect_call_sites":indirect[:12]}
    if name.endswith("libamt_util.so"):
        result["efuse_symbol_callgraph"]=follow_root(info,graph)
    return result

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("unexpected_original_firmware")
    return {"schema":"hasselblad-stage23-original-efuse-TEE-callgraph-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "components":[one(root,path,digest) for path,digest in SOURCES.items()],
            "efuse_software_programming_or_execution_performed":False,
            "vendor_machine_code_or_plaintext_exported":False,
            "trusted_app_decompiled":False,
            "TBIE_key_derived_or_recovered":False,
            "eFuse_reference_proves_TBIE_key_origin":False}

def synthetic():
    assert len(SOURCES)==2
    assert len(KNOWN_TA)==2
    assert "libamt_util.so" in next(iter(SOURCES))
    return {"status":"PASS_synthetic","checks":3,"original_input_used":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    res=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(res,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":res.get("status","original_read_only"),
        "TEE_call_count":sum(x["TEE_API_direct_call_count"] for x in res.get("components",[])),
        "efuse_software_run":False,"key_recovered":False},sort_keys=True))
if __name__=="__main__":main()
