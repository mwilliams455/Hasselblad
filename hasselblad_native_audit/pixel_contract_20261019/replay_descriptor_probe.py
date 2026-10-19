#!/usr/bin/env python3
"""Compile/run a bounded read of exact X2D II relocated MAIN_3DLUT metadata."""
import argparse,hashlib,json,os,resource,subprocess
from pathlib import Path

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware-root',type=Path,required=True)
    p.add_argument('--clang',type=Path,required=True)
    p.add_argument('--qemu',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.firmware_root.resolve()
    lib=root/'system/lib64/librcam.so'
    digest=sha(lib)
    if digest!='3dd5b37b3db18b3e6b54271e1501b4dd337e101c06cdd386a896b1547b662f66':
        raise ValueError('Unsupported librcam SHA256')
    source=Path(__file__).with_name('inspect_lut_descriptor.c')
    binary=a.output.resolve().with_name('inspect_lut_descriptor_android28_arm64')
    build=[str(a.clang.resolve()),'-O2','-Wall','-Wextra','-Werror',str(source),'-ldl','-o',str(binary)]
    subprocess.run(build,check=True,capture_output=True,text=True,timeout=30)
    argv=[str(a.qemu.resolve()),'-L',str(root),str(binary),str(lib)]
    env=os.environ.copy();env['LD_LIBRARY_PATH']=str(lib.parent)
    child=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=20,preexec_fn=limits)
    result={'library_sha256':digest,'source_sha256':sha(source),'probe_sha256':sha(binary),
            'runner_sha256':sha(Path(__file__)),'method':'Read original linker-relocated metadata; no camera function invoked',
            'build_command':build,'run_command':argv,'exit':child.returncode,'stdout':child.stdout,'stderr':child.stderr,
            'records':[json.loads(s) for s in child.stdout.splitlines() if s.startswith('{')]}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'exit':child.returncode,'records':result['records'],'output':str(a.output)}))
    if child.returncode:raise SystemExit(child.returncode)

if __name__=='__main__':main()
