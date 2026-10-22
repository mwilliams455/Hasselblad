#!/usr/bin/env python3
"""Enumerate hash-pinned X1D II vendor OTA filesystem, never export vendor bytes.

The older public dump includes vendor.new.dat but did not expand it into files.
This static-only probe reconstructs an Ext4 image temporarily, records only
paths/sizes/checksums of likely camera components, and erases temporary data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request
from inspect_x1dii_isp import REPOSITORY, REV, gitblob

ROOT="_X1D_II_50C_v1_0_0.cim.extracted/"
SOURCES={
 "vendor.transfer.list":(134,"cb9c4338a062de87de56c034847e64a43e08fd5a"),
 "vendor.new.dat":(17530880,"2288b38899d13a7b4300d767bc9af9c02dd42599"),
}
MAX_BLOCKS=65536
CAMERA_FILTER=re.compile(r"(?:camera|isp|dsp|ccm|awb|hiso|gamma|colour|color|tun|iq|\.fw$|\.so$|\.ko$|\.json$|\.fbs$)",re.I)


def fetch(name):
    url=f"https://raw.githubusercontent.com/{REPOSITORY}/{REV}/{ROOT}{name}"
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"HasselbladVendorInventory/1.0"}),timeout=70) as response:
        data=response.read(SOURCES[name][0]+1)
    expected_size,expected_sha=SOURCES[name]
    if len(data)!=expected_size or gitblob(data)!=expected_sha:
        raise ValueError("pinned vendor input mismatch: "+name)
    return data


def ranges(text):
    values=[int(i) for i in text.split(",")]
    if not values or values[0]==0 or values[0]!=len(values)-1 or values[0]%2:
        raise ValueError("invalid OTA block extent")
    p=list(zip(values[1::2],values[2::2]))
    if any(a<0 or b<=a or b>MAX_BLOCKS for a,b in p):
        raise ValueError("OTA block boundary out of range")
    return p


def reconstruct(transfer, data, target):
    lines=transfer.decode("ascii").splitlines()
    if len(lines)<5 or lines[0] not in ("3","4"):
        raise ValueError("unexpected OTA version")
    declared=int(lines[1])
    if declared<=0 or declared>MAX_BLOCKS:
        raise ValueError("invalid declared partition blocks")
    written=[];cursor=0
    with target.open("xb") as f:
        f.truncate(declared*4096)
        for line in lines[4:]:
            if not line.strip():continue
            cmd,value=line.split(" ",1)
            pairs=ranges(value)
            if cmd not in ("new","zero","erase"):
                raise ValueError("unexpected OTA command")
            if cmd=="new":
                for a,b in pairs:
                    if b>declared:raise ValueError("new block exceeds partition size")
                    count=(b-a)*4096
                    if cursor+count>len(data):raise ValueError("new data truncated")
                    f.seek(a*4096);f.write(data[cursor:cursor+count]);cursor+=count
                    written.append([a,b])
            elif cmd=="zero" and any(b>declared for _,b in pairs):
                raise ValueError("zero exceeds partition size")
            # erase may refer beyond the declared partition; do not allocate it.
    if cursor!=len(data):raise ValueError("unconsumed OTA new data")
    return {"partition_blocks":declared,"image_bytes":declared*4096,
            "new_block_ranges":written,"all_source_data_consumed":True}


def traverse(image):
    from dissect.extfs import ExtFS
    files=[];all_types={};visited=set()
    with image.open("rb") as h:
        fs=ExtFS(h)
        def walk(node,path="",depth=0):
            if depth>30:raise ValueError("vendor directory depth exceeded")
            for ch in node.iterdir():
                name=str(ch.filename)
                if name in (".","..") or not name or "/" in name or "\\" in name:
                    continue
                p=path+name
                if p in visited or len(visited)>=100000:
                    raise ValueError("vendor filesystem traversal limit")
                visited.add(p)
                kind=int(ch.filetype)
                all_types[str(oct(kind))]=all_types.get(str(oct(kind)),0)+1
                if kind==0o040000:
                    walk(ch,p+"/",depth+1)
                elif kind==0o100000:
                    try:
                        with ch.open() as handle:
                            source=handle.read(24*1024*1024+1)
                    except Exception:
                        files.append({"path":p,"error":"unreadable"});continue
                    if len(source)>24*1024*1024:raise ValueError("unexpected large file")
                    if CAMERA_FILTER.search(p):
                        files.append({"path":p,"bytes":len(source),
                                      "sha256":hashlib.sha256(source).hexdigest(),
                                      "magic_class":"ELF" if source.startswith(b"\x7fELF") else
                                      "IMaH" if source.startswith(b"IM*H") else
                                      "other"})
        walk(fs.get("/"))
    return {"all_entries":len(visited),"type_counts":all_types,
            "filtered_relevant_files":files,
            "camera_binary_values_disclosed":False}


def self_test():
    assert ranges("4,0,1,3,7")==[(0,1),(3,7)]
    for s in ["3,1,2,4", "2,10,1", "0", "2,-1,2"]:
        try:ranges(s)
        except ValueError:pass
        else:raise AssertionError("failed invalid OTA range guard:"+s)
    with tempfile.TemporaryDirectory() as td:
        destination=Path(td)/"x.img"
        m=reconstruct(b"3\n16\n0\n0\nnew 2,1,2\nzero 2,0,1\n",b"A"*4096,destination)
        assert m["all_source_data_consumed"]
        assert destination.read_bytes()[4096:8192]==b"A"*4096
    print("PASS Stage15C OTA range, source consumption and sparse image self-test")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--output",type=Path)
    opts=ap.parse_args()
    if opts.self_test:self_test();return
    if not opts.output:ap.error("--output is required")
    transfer=fetch("vendor.transfer.list")
    payload=fetch("vendor.new.dat")
    with tempfile.TemporaryDirectory(prefix="hb-stage15-vendor-") as td:
        img=Path(td)/"vendor.img"
        metadata=reconstruct(transfer,payload,img)
        filelist=traverse(img)
    out={"schema":"hasselblad-stage15c-vendor-file-inventory-v1",
         "status":"inert_pinned_upstream_vendor_partition_parsed",
         "upstream_repository":REPOSITORY,"upstream_revision":REV,
         "pinned_blobs":{k:{"size":len(v),"git_blob_sha1":gitblob(v)} for k,v in
                         (("vendor.transfer.list",transfer),("vendor.new.dat",payload))},
         "partition":metadata,"file_inventory":filelist,
         "vendor_payload_copied_into_report":False,
         "original_isp_pixel_ccm_equation_verified":False,
         "x2dii_colour_processing_equivalent":False}
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    s=json.dumps(out,sort_keys=True,indent=2)+"\n"
    if len(s)>220000:raise ValueError("unbounded vendor inventory report")
    opts.output.write_text(s)
    print(json.dumps({"status":"PASS","files":filelist["all_entries"],
                      "camera_candidates":len(filelist["filtered_relevant_files"]),
                      "output":str(opts.output)}))

if __name__=="__main__":main()
