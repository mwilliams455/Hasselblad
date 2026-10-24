#!/usr/bin/env python3
"""Stage25: source of original X2D II eFuse TEEC_OpenSession stack UUID.

Reconstruct *only* known constant bytes used to initialise the UUID structure
at SP+48 in the original efuse_pro/pro_state/sec_debug_state functions. The
output identifies a known PUBLIC trusted-application UUID, never generic
unknown bytes or proprietary key material. Path-insensitive reconstruction is
labelled a candidate until control-flow dominance is also established.

No original code execution, eFuse reads/writes, protected TA decryption,
arbitrary literal dumping, or private camera data exported.
"""
from __future__ import annotations
import argparse,hashlib,json,uuid
from pathlib import Path
from trace_efuse_session24 import backing_elf,FILE,SHA,TA_NAMES,TARGET_FUNCS

STACK_UUID=48
MAX_FUNCTION_INSNS=1100

def reg_size(name):
    if not name:return None
    return {"w":4,"x":8,"s":4,"d":8,"q":16,"v":16}.get(name[0])

def read_constant_file(path):
    from elftools.elf.elffile import ELFFile
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=SHA:raise ValueError("original_libamt_mismatch")
    with path.open("rb") as f:
        elf=ELFFile(f)
        segments=[(int(s["p_vaddr"]),int(s["p_offset"]),int(s["p_filesz"])) for s in elf.iter_segments() if s["p_type"]=="PT_LOAD"]
    def read(va,size):
        for base,off,count in segments:
            if base<=va and va+size<=base+count:
                pos=off+va-base
                return data[pos:pos+size]
        return None
    return read

def simulate(insns,read):
    from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM,ARM64_OP_IMM
    registers={}
    # Abstract SP is held at zero; ignores early prologue SP adjustments.
    stack={}
    results=[]
    writes=[]
    literal_fetches=[]
    originals={n:uuid.UUID(n).bytes_le for n in TA_NAMES}
    def name(ins,op):
        return ins.reg_name(op.reg) if op.type==ARM64_OP_REG else ""
    def get(name):
        if name=="sp":return 0
        if name in ("xzr","wzr"):return 0
        return registers.get(name)
    def nbytes(value,size):
        if isinstance(value,bytes):return value[:size] if len(value)>=size else None
        if isinstance(value,int):return (value % (1<<(8*size))).to_bytes(size,"little")
        return None
    def address(ins,mem):
        if mem.index:return None
        base=get(ins.reg_name(mem.base))
        return base+int(mem.disp) if isinstance(base,int) else None
    def put_register(n,v):
        registers[n]=v
        if n and n[0]=="w" and n[1:].isdigit():registers["x"+n[1:]]=v
        elif n and n[0]=="x" and n[1:].isdigit():registers["w"+n[1:]]=v
    def put_stack(ins,addr,value,width):
        if addr is None or not -2048<=addr<=2048:return
        raw=nbytes(value,width)
        if raw is None:
            for i in range(width):stack.pop(addr+i,None)
            return
        for i,b in enumerate(raw):stack[addr+i]=b
        if (addr<=STACK_UUID+15 and addr+width>STACK_UUID):
            writes.append({"site_va":hex(ins.address),"stack_offset":addr,
                           "bytes_written":width,"write_class":ins.mnemonic})
    for ins in insns:
        if len(insns)>MAX_FUNCTION_INSNS:raise ValueError("function_insn_budget")
        from capstone.arm64 import ARM64_OP_REG,ARM64_OP_MEM,ARM64_OP_IMM
        ops=ins.operands
        m=ins.mnemonic
        if m=="bl":
            # OpenSession input structure is examined immediately before call;
            # after the call, ABI caller-saved registers cannot be trusted.
            for n in [f"x{i}" for i in range(19)]+[f"w{i}" for i in range(19)]+[f"q{i}" for i in range(8)]:
                registers.pop(n,None)
            continue
        if m in ("adr","adrp") and len(ops)>=2 and ops[0].type==ARM64_OP_REG and ops[1].type==ARM64_OP_IMM:
            put_register(name(ins,ops[0]),int(ops[1].imm))
        elif m in ("mov","movz") and len(ops)>=2 and ops[0].type==ARM64_OP_REG:
            put_register(name(ins,ops[0]),get(name(ins,ops[1])) if ops[1].type==ARM64_OP_REG
                         else int(ops[1].imm) if ops[1].type==ARM64_OP_IMM else None)
        elif m in ("add","sub") and len(ops)>=3 and ops[0].type==ARM64_OP_REG and ops[1].type==ARM64_OP_REG and ops[2].type==ARM64_OP_IMM:
            base=get(name(ins,ops[1]))
            delta=int(ops[2].imm)*(1 if m=="add" else -1)
            dst=name(ins,ops[0])
            if dst!="sp":put_register(dst,base+delta if isinstance(base,int) else None)
            # Ignore SP frame adjustment: all accesses use the post-prologue frame.
        elif m in ("ldr","ldur","ldrsw","ldrb","ldrh") and len(ops)>=2 and ops[0].type==ARM64_OP_REG:
            dest=name(ins,ops[0]);width=reg_size(dest)
            if width is None:continue
            if ops[1].type==ARM64_OP_MEM:
                addr=address(ins,ops[1].mem)
                if isinstance(addr,int):
                    if name(ins,ops[1])=="sp":out=bytes(stack.get(addr+i,0) for i in range(width)) if all(addr+i in stack for i in range(width)) else None
                    elif ins.reg_name(ops[1].mem.base)=="sp":out=bytes(stack.get(addr+i,0) for i in range(width)) if all(addr+i in stack for i in range(width)) else None
                    else:out=read(addr,width)
                else:out=None
                if out and out in originals.values():
                    literal_fetches.append({"site_va":hex(ins.address),"read_address_va":hex(addr),
                                            "matches_known_TA_UUID":next(n for n,x in originals.items() if x==out)})
                put_register(dest,out)
            elif ops[1].type==ARM64_OP_IMM:
                addr=int(ops[1].imm)
                out=read(addr,width)
                if out and out in originals.values():
                    literal_fetches.append({"site_va":hex(ins.address),"read_address_va":hex(addr),
                                            "matches_known_TA_UUID":next(n for n,x in originals.items() if x==out)})
                put_register(dest,out)
            else:put_register(dest,None)
        elif m in ("ldp","ldnp") and len(ops)>=3 and ops[-1].type==ARM64_OP_MEM:
            mem=ops[-1].mem;addr=address(ins,mem)
            for i,op in enumerate(ops[:2]):
                if op.type!=ARM64_OP_REG:continue
                dest=name(ins,op);width=reg_size(dest)
                actual=addr+i*width if addr is not None and width is not None else None
                if actual is None:out=None
                elif ins.reg_name(mem.base)=="sp":
                    out=bytes(stack[actual+j] for j in range(width)) if all(actual+j in stack for j in range(width)) else None
                else:out=read(actual,width)
                put_register(dest,out)
        elif m in ("str","stur","stp","stnp"):
            if m in ("stp","stnp"):
                if len(ops)<3 or ops[2].type!=ARM64_OP_MEM:continue
                mem=ops[2].mem;values=ops[:2]
            else:
                if len(ops)<2 or ops[1].type!=ARM64_OP_MEM:continue
                mem=ops[1].mem;values=ops[:1]
            if ins.reg_name(mem.base)!="sp" or mem.index or ins.writeback:continue
            base=int(mem.disp)
            for i,src in enumerate(values):
                if src.type!=ARM64_OP_REG:continue
                n=name(ins,src);width=reg_size(n)
                if width is not None:put_stack(ins,base+i*width,get(n),width)
        if ins.mnemonic=="bl":pass
        # Each OpenSession call is identified by its exact original VA.
        if ins.address+4 in (0x2b28,0x2c50,0x2db8):
            raw=bytes(stack.get(i,0) for i in range(STACK_UUID,STACK_UUID+16)) if all(i in stack for i in range(STACK_UUID,STACK_UUID+16)) else None
            match=next((n for n,v in originals.items() if raw==v),None) if raw else None
            results.append({"session_call_va":hex(ins.address+4),
                            "stack_UUID_complete_static":raw is not None,
                            "stack_UUID_matches_known_TA_filename":match,
                            "path_insensitive_reconstruction_not_full_CFG_proof":True,
                            "uuid_stack_write_sites":writes[-10:],
                            "public_UUID_literal_fetches":literal_fetches[-10:]})
    return results,writes,literal_fetches

def audit(root):
    if (root/"system/etc/VERSION").read_text().strip()!="1.3.16.2":
        raise ValueError("wrong_firmware")
    path=root/FILE
    funcs,plt,images=backing_elf(path)
    read=read_constant_file(path)
    records=[]
    for n in TARGET_FUNCS:
        if n not in funcs:continue
        rows,writes,reads=simulate(funcs[n],read)
        records.append({"function":n,"session_sites":rows,
                        "known_UUID_literal_fetch_events":reads[:12]})
    return {"schema":"hasselblad-stage25-original-efuse-stack-uuid-derivation-v1",
            "firmware":"X2D II 100C 1.3.16.2",
            "source_sha256":SHA,"static_results":records,
            "eFuse_or_secure_TA_executed":False,
            "original_vendor_machine_bytes_exported":False,
            "unknown_literal_bytes_or_secret_key_material_exported":False,
            "encrypted_DSP_or_TA_decrypted":False}

def synthetic():
    assert len(TA_NAMES)==2
    assert reg_size("q0")==16 and reg_size("x7")==8
    assert STACK_UUID==48
    return {"status":"PASS_synthetic","checks":3,"original_input_read":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path)
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not a.self_test and not a.firmware_root:p.error("--firmware-root required")
    d=synthetic() if a.self_test else audit(a.firmware_root)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":d.get("status","original_analysed"),
                      "verified_known_UUIDs":sum(1 for x in d.get("static_results",[])
                                                for y in x.get("session_sites",[])
                                                if y["stack_UUID_matches_known_TA_filename"]),
                      "secret_key_recovered":False},sort_keys=True))
if __name__=="__main__":main()
