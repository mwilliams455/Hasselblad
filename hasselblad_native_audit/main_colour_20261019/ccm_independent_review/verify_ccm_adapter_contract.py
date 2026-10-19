#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build independent host contract tests with ASan/UBSan; no vendor execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc",default="cc")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    ccm=here.parent/"ccm"
    source=here/"ccm_adapter_contract.c"
    environment=os.environ.copy()
    # The workspace restricts /proc thread enumeration used by LeakSanitizer.
    # This adapter allocates no heap memory; retain ASan memory and UBSan checks.
    environment["ASAN_OPTIONS"]="detect_leaks=0:halt_on_error=1"
    environment["UBSAN_OPTIONS"]="halt_on_error=1"
    with tempfile.TemporaryDirectory(prefix="hb-ccm-adapter-contract-") as directory:
        binary=Path(directory)/"contract"
        build=[args.cc,"-std=c11","-O2","-Wall","-Wextra","-Werror",
               "-fsanitize=address,undefined","-fno-sanitize-recover=all","-I",str(ccm),
               str(source),str(ccm/"ccm_prepare.c"),"-o",str(binary)]
        subprocess.run(build,capture_output=True,text=True,check=True,timeout=30)
        child=subprocess.run([str(binary)],capture_output=True,text=True,env=environment,timeout=10)
        if child.returncode or child.stderr:
            raise RuntimeError("Contract executable failed: exit=%d stderr=%r"%(child.returncode,child.stderr))
        cases=[json.loads(line) for line in child.stdout.splitlines()]
        if len(cases)!=20 or not all(case["pass"] for case in cases):
            raise AssertionError("Adapter contract did not pass all20 cases")
        result={"result":"pass","method":"Independent owned synthetic data; host GCC address/undefined-behavior sanitizers; no original firmware execution",
                "build_command":build,"compiler_version":subprocess.run([args.cc,"--version"],capture_output=True,text=True,check=True,timeout=10).stdout.splitlines()[0],
                "binary_sha256":sha(binary),"source_sha256":{p.name:sha(p) for p in (source,ccm/"ccm_prepare.c",ccm/"ccm_prepare.h",Path(__file__))},
                "cases":cases,"case_count":len(cases),"exit":child.returncode,"stderr":child.stderr,
                "sanitizer_options":{"ASAN_OPTIONS":environment["ASAN_OPTIONS"],"UBSAN_OPTIONS":environment["UBSAN_OPTIONS"]},
                "leak_check":"Disabled because /proc thread enumeration is restricted; tested adapter uses stack storage only",
                "limits":"Verifies the owned adapter's declared guards, clamps and alias behavior; the separate original Bionic probe supplies arithmetic equivalence evidence"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"result":"pass","cases":len(cases),"output":str(args.output)}))


if __name__=="__main__":
    main()
