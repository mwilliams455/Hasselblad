#!/usr/bin/env python3
"""Stage22: original X2D II normal-world key-provisioning evidence inventory.

Purpose: test whether *readable* original X2D II system/vendor binaries contain
CryptoCell, eFuse, key-ladder or TEE driver/provisioning evidence. Source
assertions are bounded per-file marker/symbol presence, not code-flow or
actual hardware cryptographic key derivation. Do not confuse DJI research
background with proven Hasselblad SoC behavior.

Never execute manufacturer software, extract plaintext, export proprietary
code/strings/key bytes, modify a camera, or claim secret recovery.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FIRMWARE="1.3.16.2"
MARKERS={
  "cryptocell":(b"cryptocell",b"crypto cell"),
  "arm_cc_family":(b"cc312",b"cc310",b"cc630",b"cc712"),
  "efuse":(b"efuse",b"e-fuse",b"e_fuse"),
  "otp":(b"otp_read",b"otp_write",b"otp_key",b"otp_fuse"),
  "key_ladder":(b"keyladder",b"key_ladder",b"key ladder"),
  "root_key":(b"rootkey",b"root_key",b"hbk_",b"hardware_bound_key"),
  "keymaster":(b"keymaster",b"keymint"),
  "trusted_os":(b"trustzone",b"op-tee",b"tee_supplicant",b"trusted_execution_environment"),
  "secure_tee_device":(b"/dev/tee",b"/dev/teec",b"/dev/qseecom"),
  "secure_crypto_device":(b"/dev/crypto",b"/dev/efuse",b"/dev/otp",b"/dev/cryptocell"),
  "key_derivation_api":(b"hkdf_",b"kbkdf_",b"cmac_kdf",b"derive_key"),
}
PRIMARY={"cryptocell","arm_cc_family","efuse","otp","key_ladder",
         "secure_crypto_device"}
API_PREFIX=(
 "TEEC_","sec_cipher_","crypto_","cc_","cryptocell_","efuse_",
 "otp_","keymaster_","keymint_","hkdf_","hbk_","kdf_",
)
MAX_PER=64*1024*1024
MAX_TOTAL=1000*1024*1024
MAX_FILES=3000
MAX_ROWS=72
MAX_SYMBOLS=35

def classify(data:bytes)->str:
    if data.startswith(b"\x7fELF"):return "ELF"
    if data.startswith(b"IM*H"):return "IMAH_envelope"
    if data.startswith(b"ANDROID!"):return "Android_boot"
    if data.startswith(b"\xd0\x0d\xfe\xed"):return "FDT"
    return "other"

def classify_markers(data:bytes)->list[str]:
    lower=data.lower()
    found=[]
    for k,needles in MARKERS.items():
        if k=="efuse":
            # 'refuse' contains 'efuse' and caused dozens of false positives.
            if re.search(rb"(?<![a-z])efuse",lower) or b"e-fuse" in lower or b"e_fuse" in lower:
                found.append(k)
        elif any(n in lower for n in needles):
            found.append(k)
    return sorted(found)

def elf_metadata(path):
    from elftools.elf.elffile import ELFFile
    with path.open("rb") as f:
        elf=ELFFile(f)
        imports=set();exports=set();deps=set()
        for sname in (".dynsym",):  # prevent unbounded debug symbol indexing
            tab=elf.get_section_by_name(sname)
            if tab is None:continue
            for s in tab.iter_symbols():
                n=s.name
                if not n or len(n)>180 or not n.startswith(API_PREFIX):continue
                if s["st_shndx"]=="SHN_UNDEF":imports.add(n)
                else:exports.add(n)
        dyn=elf.get_section_by_name(".dynamic")
        if dyn:
            for x in dyn.iter_tags():
                if x.entry.d_tag=="DT_NEEDED":deps.add(x.needed)
        return {"machine":str(elf["e_machine"]),
                "TEE_imports":sorted(n for n in imports if n.startswith("TEEC_"))[:MAX_SYMBOLS],
                "security_named_imports":sorted(n for n in imports if not n.startswith("TEEC_"))[:MAX_SYMBOLS],
                "security_named_exports":sorted(exports)[:MAX_SYMBOLS],
                "needed_teec_library":"libteec.so" in deps,
                "needed_security_library_names":sorted(n for n in deps if any(q in n.lower()
                    for q in ("crypto","tee","security","cipher","key")))[:20]}

def audit(root:Path):
    version=root/"system/etc/VERSION"
    if not version.is_file() or version.read_text().strip()!=FIRMWARE:
        raise ValueError("firmware_version_mismatch")
    files=[]
    for sub in ("system","vendor"):
        folder=root/sub
        if not folder.is_dir():raise ValueError("partition_missing_"+sub)
        files.extend(p for p in folder.rglob("*") if p.is_file() and not p.is_symlink())
    if len(files)>MAX_FILES:raise ValueError("original_file_budget")
    size_scanned=0
    skipped=[]
    matches=[]
    primary=[]
    format_counts={}
    marker_counts={k:0 for k in MARKERS}
    security_module_paths=[]
    for f in sorted(files):
        rel=f.relative_to(root).as_posix()
        if len(rel)>250 or ".." in rel.split("/"):continue
        size=f.stat().st_size
        if size>MAX_PER or size_scanned+size>MAX_TOTAL:
            skipped.append({"path":rel,"bytes":size,"reason":"budget"})
            continue
        raw=f.read_bytes()
        size_scanned+=len(raw)
        kind=classify(raw[:64])
        format_counts[kind]=format_counts.get(kind,0)+1
        hits=classify_markers(raw)
        for h in hits:marker_counts[h]+=1
        module_candidate=f.suffix in (".ko",".ta") or kind=="FDT" or (
            any(t in f.name.lower() for t in
                ("crypto","secure","efuse","trust","tee","keymaster","otp")))
        if module_candidate and len(security_module_paths)<100:
            security_module_paths.append({"path":rel,"format":kind,"bytes":size})
        if not hits:continue
        details={"path":rel,"bytes":size,"format":kind,
                 "marker_families":hits,
                 "source_sha256":hashlib.sha256(raw).hexdigest()}
        if kind=="ELF" and any(k in PRIMARY or k in ("trusted_os","secure_tee_device") for k in hits):
            try: details["ELF"]=elf_metadata(f)
            except (ValueError,OverflowError,IndexError,KeyError) as err:
                details["ELF_parse_outcome"]=type(err).__name__
        if any(h in PRIMARY for h in hits):primary.append(details)
        matches.append(details)
    # Rank truly security-specific matches over generic keymaster or TEE strings
    match_rank=lambda x:(-len(PRIMARY.intersection(x["marker_families"])),
                         -len(x["marker_families"]),x["path"])
    selected=sorted(matches,key=match_rank)
    top=selected[:MAX_ROWS]
    return {"schema":"hasselblad-stage22-original-key-provisioning-surface-v1",
            "original_firmware":"X2D II 100C 1.3.16.2",
            "files_total":len(files),
            "files_scanned":sum(format_counts.values()),
            "scan_bytes":size_scanned,
            "files_not_scanned_due_to_bounds":skipped[:35],
            "scan_includes_all_binaries":len(skipped)==0,
            "format_counts":format_counts,
            "marker_count_by_file":marker_counts,
            "file_count_with_security_markers":len(matches),
            "file_count_with_primary_hardware_key_markers":len(primary),
            "file_rows":top,
            "file_row_count_published":len(top),
            "file_rows_truncated":len(matches)>len(top),
            "candidate_security_module_inventory":security_module_paths,
            "candidate_security_module_rows_truncated":len(security_module_paths)>=100,
            "hardware_key_derivation_proven":False,
            "normal_world_symbol_name_proves_TEE_behavior":False,
            "cryptographic_keys_found_or_exported":False,
            "encrypted_TA_or_DSP_decrypted":False,
            "original_vendor_code_executed":False,
            "vendor_instruction_bytes_or_private_strings_exported":False}

def synthetic():
    assert "cryptocell" in classify_markers(b"note CRYPTOCELL input")
    assert "efuse" in classify_markers(b"EFuse control")
    assert "efuse" not in classify_markers(b"please refuse request")
    assert "key_ladder" in classify_markers(b"key_ladder")
    assert classify(b"IM*H\x00\x00")=="IMAH_envelope"
    assert "cryptocell" not in classify_markers(b"not related")
    return {"status":"PASS_synthetic","checks":6,"original_firmware_used":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--firmware-root",type=Path)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if not args.self_test and not args.firmware_root:
        ap.error("--firmware-root required without --self-test")
    data=synthetic() if args.self_test else audit(args.firmware_root)
    args.output.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":data.get("status","original_firmware_scanned"),
                      "files_scanned":data.get("files_scanned"),
                      "hardware_marker_files":data.get("file_count_with_primary_hardware_key_markers"),
                      "crypto_keys_recovered":False},sort_keys=True))

if __name__=="__main__":main()
