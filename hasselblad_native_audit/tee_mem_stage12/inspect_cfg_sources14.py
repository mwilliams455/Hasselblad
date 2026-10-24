#!/usr/bin/env python3
"""Stage14: branch-sensitive input-register provenance for X2D II command 6.

The predecessor Stage13 identified 3 original encrypted-input shared buffers,
but text-order register scans could not resolve every input because other
branches redefine the same registers. Stage14 performs a bounded native
instruction CFG fixed-point dataflow for callee-saved inputs x21/x22/x23 and
value words w20/w19, and checks original incoming ABI register liveness.

Original normal-world ELF only; never executes original code, TA or DSP.
No raw vendor instructions, bytes, signatures, key material, or photographs
are emitted. An unresolved origin remains unresolved rather than guessed.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SOURCE="system/lib64/libfw_util_ca.so"
SHA="96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b"
FUNCTION="fw_util_verify_init_ext"
TARGETS=(
 ("copy0",0x1d8c,"x23"),
 ("copy1",0x1df0,"x22"),
 ("copy2",0x1e98,"x21"),
 ("param3_a",0x1ef0,"w20"),
 ("param3_b",0x1ef4,"w19"),
)
MAX_DEFS=20

def canon(s):
    if s and s[0] in "wx" and s[1:].isdigit():return int(s[1:])
    return None

def original_insns(path):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN
    from elftools.elf.elffile import ELFFile
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise ValueError("original_sha_mismatch")
    with path.open("rb") as fh:
        elf=ELFFile(fh)
        if elf["e_machine"]!="EM_AARCH64":raise ValueError("wrong_machine")
        dyn=elf.get_section_by_name(".dynsym")
        sym=[s for s in dyn.iter_symbols() if s.name==FUNCTION and s["st_shndx"]!="SHN_UNDEF"]
        if len(sym)!=1:raise ValueError("missing_original_function")
        va=int(sym[0]["st_value"]);size=int(sym[0]["st_size"])
        sec=elf.get_section_by_name(".text")
        off=va-int(sec["sh_addr"])
        if not 0<size<4096 or off<0 or off+size>len(sec.data()):
            raise ValueError("invalid_symbol_range")
        md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);md.detail=True
        insns=list(md.disasm(sec.data()[off:off+size],va))
        if len(insns)*4!=size:raise ValueError("AArch64_decode_gap")
        return insns

def cfg(insns):
    from capstone.arm64 import ARM64_OP_IMM
    addr={ins.address for ins in insns}
    edges={}
    for ins in insns:
        m=ins.mnemonic
        forward=ins.address+4
        if m in ("ret","eret","br","braa","brab"):
            to=[]
        elif m=="b":
            op=ins.operands[-1] if ins.operands else None
            to=[int(op.imm)] if op and op.type==ARM64_OP_IMM and int(op.imm) in addr else []
        elif m.startswith("b.") or m in ("cbz","cbnz","tbz","tbnz"):
            op=ins.operands[-1]
            to=[int(op.imm)] if op.type==ARM64_OP_IMM and int(op.imm) in addr else []
            if forward in addr:to.append(forward)
        else:
            to=[forward] if forward in addr else []
        edges[ins.address]=sorted(set(to))
    return edges

def is_written(ins,rnum):
    try:_,wr=ins.regs_access()
    except Exception:return False
    return any(canon(ins.reg_name(k))==rnum for k in wr)

def reaching_definitions(insns,edges,rnum):
    """Each node receives the *set* of possible latest definitions.
    -1 means original function entry value. Only reachable nodes processed.
    BL follows AAPCS64; all x19-x28 must be callee-preserved by callees.
    """
    by={x.address:x for x in insns}
    entry=insns[0].address
    ins={entry:{-1}}
    pending=[entry]
    steps=0
    while pending:
        a=pending.pop()
        incoming=ins[a]
        outs={a} if is_written(by[a],rnum) else incoming
        if len(outs)>MAX_DEFS:raise ValueError("excess_reaching_definitions")
        for dest in edges[a]:
            if dest not in ins:
                ins[dest]=set(outs);pending.append(dest)
            elif not outs.issubset(ins[dest]):
                ins[dest].update(outs)
                if len(ins[dest])>MAX_DEFS:raise ValueError("definition_union_limit")
                pending.append(dest)
        steps+=1
        if steps>len(insns)*80:raise ValueError("CFG_fixpoint_over_budget")
    return ins

def def_origin(insns,site,reg,flows):
    """Determine an incoming argument only if the register definition is
    MOV from an ABI argument still holding its function-entry value.
    """
    from capstone.arm64 import ARM64_OP_REG
    r=canon(reg)
    defs=flows[r].get(site,set())
    by={i.address:i for i in insns}
    candidates=[]
    for va in sorted(defs):
        if va==-1:
            candidates.append({"definition":"entry","incoming_argument":r if r is not None and r<=7 else None})
            continue
        ins=by[va]
        item={"definition":hex(va),"instruction_class":ins.mnemonic,
              "incoming_argument":None}
        if ins.mnemonic=="mov" and len(ins.operands)>=2 and ins.operands[1].type==ARM64_OP_REG:
            src=canon(ins.reg_name(ins.operands[1].reg))
            if src is not None:
                item["source_register"]=src
                src_defs=flows[src].get(va,set())
                if src<=7 and src_defs=={-1}:
                    item["incoming_argument"]=src
                    item["source_unchanged_at_definition"]=True
                elif src_defs=={-1} and src>7:
                    item["source_unchanged_at_definition"]=True
        candidates.append(item)
    proved={x["incoming_argument"] for x in candidates}
    unique=len(defs)>0 and len(proved)==1 and None not in proved
    return {"source_reg":reg,"at_va":hex(site),"reaching_defs":len(defs),
            "candidate_definitions":candidates[:MAX_DEFS],
            "unique_incoming_ABI_argument_proven":unique,
            "incoming_argument_index":next(iter(proved)) if unique else None}

def audit(path):
    insns=original_insns(path)
    graph=cfg(insns)
    used={canon(r) for _,_,r in TARGETS}
    # Follow all argument registers too, avoiding accidental "incoming"
    # identifications after overwrites or external calls.
    used.update(range(8))
    flows={r:reaching_definitions(insns,graph,r) for r in used}
    reachable=flows[0]
    results=[]
    for label,site,reg in TARGETS:
        if site not in reachable:raise ValueError("requested_site_unreachable_"+label)
        row=def_origin(insns,site,reg,flows);row["purpose"]=label
        results.append(row)
    return {"schema":"hasselblad-stage14-original-command6-branch-reaching-definitions-v1",
            "original_firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":SHA,
            "analyzed_instructions":len(insns),
            "control_flow_edges":sum(len(v) for v in graph.values()),
            "sites":results,
            "all_original_executable_data_retained_private":True,
            "key_values_or_decrypted_TA_or_DSP_recovered":False,
            "original_vendor_code_executed":False,
            "CFG_proves_runtime_TEE_acceptance":False}

def synthetic():
    assert canon("w20")==canon("x20")==20
    assert canon("sp") is None
    assert len(TARGETS)==5
    return {"status":"PASS_synthetic","checks":3,"original_firmware_used":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    result=synthetic() if a.self_test else audit(a.firmware_root/SOURCE)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result.get("status","original_audit"),
       "resolved_sites":sum(x["unique_incoming_ABI_argument_proven"] for x in result.get("sites",[])),
       "input_sites":len(result.get("sites",[])),"key_exported":False},sort_keys=True))
if __name__=="__main__":main()
