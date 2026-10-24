#!/usr/bin/env python3
"""REA/Ghidra follow-through on original X2D II key-selection call chain.

No vendor pseudocode, raw firmware bytes, signature/key material or string
literal values leave ephemeral Actions runner. Signals are lexical only unless
independently proven by Capstone stage5 audit.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

CASES=(
 ("system/lib64/libfw_util_ca.so","fw_util_verify_init_ext"),
 ("system/lib64/libfw_util.so","plt_fw_verify_file"),
 ("system/lib64/libfw_verify_util.so","plt_fw_verify_file_soft"),
 ("system/lib64/libfw_util.so","dji_fw_verify_load2mem"),
 ("system/bin/dji_fw_verify","main"),
)

def run(root):
    exe=shutil.which("rea")
    ghidra=os.environ.get("GHIDRA_INSTALL_DIR")
    summary={"schema":"hasselblad-rea-stage5-key-selector-ghidra-v1",
             "ghidra_provider_requested":True,
             "rea_cli_available":bool(exe),
             "ghidra_dir_available":bool(ghidra and Path(ghidra).is_dir()),
             "functions":[],"original_firmware_code_executed":False,
             "TEE_decrypted":False,"secret_material_exported":False,
             "no_pseudocode_exported":True}
    if not exe or not summary["ghidra_dir_available"]:
        summary["status"]="no_provider"
        return summary
    for rel,name in CASES:
        item={"binary":rel,"symbol":name,"returncode":None,
              "evidence_json_parsed":False,"symbol_mentioned":False,
              "init_ext_reference_mentioned":False,
              "TEEC_InvokeCommand_reference_mentioned":False,
              "raw_pseudocode_not_published":True}
        try:
            p=subprocess.run([exe,"decompile",str(root/rel),name,
                              "--provider","ghidra","--format","json"],
                             capture_output=True,timeout=360)
            item["returncode"]=p.returncode
            if p.returncode==0:
                try:
                    data=json.loads(p.stdout)
                    item["evidence_json_parsed"]=isinstance(data,dict)
                    t=json.dumps(data,ensure_ascii=False)
                    item["symbol_mentioned"]=name in t
                    item["init_ext_reference_mentioned"]="fw_util_verify_init_ext" in t
                    item["TEEC_InvokeCommand_reference_mentioned"]="TEEC_InvokeCommand" in t
                except (UnicodeDecodeError,ValueError):
                    pass
        except (OSError,subprocess.TimeoutExpired) as e:
            item["failure_class"]=type(e).__name__
        summary["functions"].append(item)
    summary["status"]="completed"
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firmware-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=run(a.firmware_root)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],
                      "parsed_cases":sum(x["evidence_json_parsed"] for x in result["functions"])},sort_keys=True))

if __name__=="__main__":main()
