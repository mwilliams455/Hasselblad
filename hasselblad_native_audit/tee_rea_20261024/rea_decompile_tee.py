#!/usr/bin/env python3
"""Run optional REA/Ghidra against three original TEE client functions.

Runs in private ephemeral CI. Pseudocode, decompiled vendors' source, key
material and raw function bytes must not be written to published artifacts.
Only boolean parse status, function identity, and counts are retained.
"""
from __future__ import annotations
import argparse,json,os,shutil,subprocess
from pathlib import Path

FUNCS=("fw_util_verify","fw_util_load","fw_util_verify_init_ext")

def go(binary):
    rea=shutil.which("rea")
    result={"schema":"hasselblad-rea-ghidra-tee-function-dossiers-v1",
            "provider":"ghidra","original_input":True,
            "rea_cli_present":bool(rea),
            "ghidra_install_dir_present":bool(os.environ.get("GHIDRA_INSTALL_DIR") and
                                              Path(os.environ["GHIDRA_INSTALL_DIR"]).is_dir()),
            "functions":[],"vendor_code_in_report":False,
            "secure_world_decompiled":False,
            "keys_recovered":False}
    if not rea or not result["ghidra_install_dir_present"]:
        result["status"]="provider_unavailable"
        return result
    for fun in FUNCS:
        record={"name":fun,"cli_returncode":None,"json_parse_success":False,
                "source_function_identified":False,"direct_teec_named":False,
                "is_secure_world_code":False}
        try:
            p=subprocess.run([rea,"decompile",str(binary),fun,
                              "--provider","ghidra","--format","json"],
                             env=os.environ.copy(),timeout=340,capture_output=True)
            record["cli_returncode"]=p.returncode
            if p.returncode==0:
                try:
                    obj=json.loads(p.stdout)
                    record["json_parse_success"]=isinstance(obj,dict)
                    text=json.dumps(obj,ensure_ascii=False)
                    # These are merely lexical presence checks in private
                    # evidence, not independently verified call relationships.
                    record["source_function_identified"]=fun in text
                    record["direct_teec_named"]="TEEC_InvokeCommand" in text
                    record["text_contains_parameter_type_label"]="paramTypes" in text
                except (UnicodeDecodeError,ValueError):
                    pass
        except (subprocess.TimeoutExpired,OSError) as e:
            record["failure_type"]=type(e).__name__
        result["functions"].append(record)
    result["status"]="completed_with_status_checks"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=go(args.binary)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":report["status"],
        "ghidra_function_results":len(report["functions"]),
        "json_succeeded":sum(x["json_parse_success"] for x in report["functions"])}))

if __name__=="__main__":
    main()
