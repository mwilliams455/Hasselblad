#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Download ONE explicitly shared X2D II ColorChecker RAW+JPEG for private tests.

Network access is exclusive to a hash-pinned public GitHub manifest and two
Google Drive files listed there. No image is allowed into the Git checkout or
Actions artifact. Intended only for ephemeral GitHub runner temp directory.
"""
from __future__ import annotations
import argparse,base64,csv,hashlib,io,re,sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests

UPSTREAM_COMMIT="5f1dd7e8f4fa64b16032842e4be50208c16a4140"
MANIFEST_SHA_GIT="eddba2570ba2d19f443920483e5228685830127f"
UPSTREAM_PATH="datasets/hasselblad/contributed/kmichels-x2dii-2026-07/manifest.csv"
PAIR_STEM="B_31325"
CAP_RAW=320*1024*1024
CAP_JPEG=90*1024*1024
JPG_MAGIC=b'\xff\xd8\xff'
RAW_MAGIC=(b'II*\x00',b'MM\x00*')


def extract_drive_id(url: str)->str:
    u=urlparse(url)
    if (u.scheme,u.netloc)!=("https","drive.google.com"):
        raise ValueError("only HTTPS drive.google.com URL supported")
    m=re.fullmatch(r"/file/d/([\w-]{20,64})/view/?",u.path)
    if not m:raise ValueError("public file/d/.../view link required")
    return m.group(1)


def parse_pinned_manifest(raw_bytes:bytes)->tuple[str,str]:
    try:rows=list(csv.DictReader(io.StringIO(raw_bytes.decode("utf-8-sig"))))
    except (UnicodeError,csv.Error) as e:raise ValueError("invalid manifest") from e
    if len(rows)!=9 or len({x["filename_raw"] for x in rows})!=9:
        raise ValueError("unrecognized upstream chart manifest")
    matches=[x for x in rows if x["filename_raw"]==PAIR_STEM+".3FR" and x["filename_jpeg"]==PAIR_STEM+".JPG"]
    if len(matches)!=1:raise ValueError("Missing exactly paired public chart files")
    row=matches[0]
    if row["camera"]!="X2D II 100C" or row["scene_type"]!="chart" or row["iso"]!="50":
        raise ValueError("Unexpected sensor/chart provenance")
    if row["illuminant"].strip():raise ValueError("Illuminant must be acknowledged as unmeasured")
    raw_id=extract_drive_id(row["download_url"])
    j=re.search(r"JPEG:\s*(https://drive\.google\.com/file/d/[A-Za-z0-9_-]+/view)",row["notes"])
    if not j:raise ValueError("Missing explicit JPEG URL")
    return raw_id,extract_drive_id(j.group(1))


def download_one(s:requests.Session,file_id:str,target:Path,kind:str)->int:
    uri="https://drive.google.com/uc?export=download&id="+file_id
    resp=s.get(uri,timeout=(25,120),stream=True)
    resp.raise_for_status()
    for attempt in range(3):
        content_type=resp.headers.get("content-type","").lower()
        if "text/html" not in content_type and not resp.url.lower().endswith(".html"):
            break
        text=resp.content[:2*1024*1024].decode("utf-8","replace")
        confirm=re.search(r'name="confirm"\s+value="([A-Za-z0-9_-]+)"',text)
        uuid=re.search(r'name="uuid"\s+value="([A-Za-z0-9_-]+)"',text)
        if not (confirm and uuid):
            raise ValueError("Public Google Drive share unavailable or confirmation absent")
        uri=("https://drive.usercontent.google.com/download?id="+file_id+
             "&export=download&confirm="+confirm.group(1)+"&uuid="+uuid.group(1))
        resp.close();resp=s.get(uri,timeout=(25,150),stream=True);resp.raise_for_status()
    # HTML can also be content-type octet-stream; verify file signature after download.
    if urlparse(resp.url).hostname not in ("drive.google.com","drive.usercontent.google.com","doc-0k-0c-docs.googleusercontent.com") and not urlparse(resp.url).hostname.endswith(".googleusercontent.com"):
        raise ValueError("Unexpected public Drive download host")
    length=0;limit=CAP_RAW if kind=="raw" else CAP_JPEG
    part=target.with_suffix(target.suffix+".partial")
    try:
        with part.open("wb") as f:
            for block in resp.iter_content(chunk_size=1024*1024):
                if not block:continue
                length+=len(block)
                if length>limit:raise ValueError("download exceeds safety size ceiling")
                f.write(block)
        with part.open("rb") as f:signature=f.read(4)
        good = (signature in RAW_MAGIC) if kind=="raw" else signature.startswith(JPG_MAGIC)
        if not good or length < (2*1024*1024 if kind=="raw" else 100*1024):
            raise ValueError("download returned HTML or a wrong/short image")
        part.replace(target)
        return length
    finally:
        resp.close()
        if part.exists():part.unlink()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--destination",type=Path)
    p.add_argument("--selftest",action="store_true")
    args=p.parse_args()
    if args.selftest:
        assert extract_drive_id('https://drive.google.com/file/d/1BNbyF6qlJoJ6gW2FQPr3H_pV2gH9psTa/view')=='1BNbyF6qlJoJ6gW2FQPr3H_pV2gH9psTa'
        for invalid in ('http://drive.google.com/file/d/aaaaaaaaaaaaaaaaaaaa/view','https://example.com/file/d/aaaaaaaaaaaaaaaaaaaa/view'):
            try:extract_drive_id(invalid);raise AssertionError("unsafe URL allowed")
            except ValueError:pass
        print('PASS fixed-site source constraints and negative inputs')
        return
    if not args.destination or args.destination.resolve().is_relative_to(Path.cwd().resolve()):
        raise SystemExit("Destination must be an outside-repository ephemeral directory")
    args.destination.mkdir(parents=True,exist_ok=True)
    url=("https://api.github.com/repos/songjiun10-collab/Hncs/contents/"+
         UPSTREAM_PATH+"?ref="+UPSTREAM_COMMIT)
    s=requests.Session();s.headers.update({'User-Agent':'hasselblad-research-stage23'})
    response=s.get(url,timeout=(25,40));response.raise_for_status();doc=response.json()
    if doc.get('sha')!=MANIFEST_SHA_GIT or doc.get('encoding')!='base64':
        raise ValueError("Upstream immutable manifest identity changed")
    manifest=base64.b64decode(doc['content'])
    raw_id,jpg_id=parse_pinned_manifest(manifest)
    raw=args.destination/(PAIR_STEM+'.3FR');jpg=args.destination/(PAIR_STEM+'.JPG')
    a=download_one(s,raw_id,raw,'raw');b=download_one(s,jpg_id,jpg,'jpeg')
    print(f'PASS public same-stem RAW/JPEG downloaded to ephemeral directory (bytes: RAW {a}, JPEG {b}); never upload image files')

if __name__=='__main__':main()
