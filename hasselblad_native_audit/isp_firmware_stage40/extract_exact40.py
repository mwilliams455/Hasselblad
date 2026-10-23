#!/usr/bin/env python3
"""Stage40: read-only extraction of exactly two official X2D II OTA releases.

Reuses the previously tested original research extractor's strict OTA range and
ExtFS regular-file readers. Never executes vendor code or update scripts.
The new firmware SHA-256 is deliberately required after Stage40A identifies it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import brotli

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cim_reader
import extract_official as reference

# Stage40A source identity result must replace the literal before paired CI.
RELEASES = {
    '1.3.16.2': {
        'size': 364814336,
        'sha256': '9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6',
        'filename': 'X2DII_100C_v1_3_16_2.cim',
    },
    '1.3.18.1': {
        'size': 365283840,
        'sha256': 'c65970cbc1519f876aa3296411f8bb5075995dabc9479bb8abb635945dad6496',
        'filename': 'X2DII_100C_v1_3_18_1.cim',
    },
}
MAX_OUTPUT_SIZE=4*1024**3


def require(value:bool,message:str):
    if not value: raise ValueError(message)


def file_sha(path:Path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def extract(source:Path,out:Path,version:str):
    spec=RELEASES[version]
    require(len(spec['sha256'])==64 and all(c in '0123456789abcdef' for c in spec['sha256']),
            'new_firmware_digest_must_be_pinned_before_comparison')
    require(source.is_file() and source.name==spec['filename'],'exact_version_filename_required')
    require(source.stat().st_size==spec['size'],'wrong_firmware_file_size')
    digest=file_sha(source)
    require(digest==spec['sha256'],'wrong_firmware_sha256')
    require(not out.exists(),'output_must_be_new')
    out.mkdir(parents=True)
    data=source.read_bytes()
    public,encrypted,iv,private,items=cim_reader.load_container(data)
    require(public['size_matches'] and public['product']=='1800000_PVF','wrong_camera_product_or_size')
    candidates=[i for i in items if i['name']=='ota.zip']
    require(len(candidates)==1,'expected_single_ota_zip')
    item=candidates[0]
    zip_data=(cim_reader.decrypt_component(data,item,iv) if encrypted else
             data[item['offset_in_cim']:item['offset_in_cim']+item['length']])
    del data
    zip_path=out/'ota.zip'
    zip_path.write_bytes(zip_data)
    del zip_data
    manifest={'schema':'hasselblad-stage40-private-full-extraction-v1',
              'firmware_version':version,'official_archive_sha256':digest,
              'official_archive_bytes':spec['size'],'ota_sha256':file_sha(zip_path),
              'partitions':{}}
    with zipfile.ZipFile(zip_path) as z:
        names=z.namelist()
        for partition in ('system','vendor'):
            tr=partition+'.transfer.list'
            if tr not in names:
                continue
            dat=partition+'.new.dat.br'
            if dat not in names: dat=partition+'.new.dat'
            for n in (tr,dat):
                require(names.count(n)==1,'duplicate_ota_member')
                require(z.getinfo(n).file_size<=MAX_OUTPUT_SIZE,'oversize_ota_member')
            transfer=z.read(tr).decode('ascii')
            expanded=out/(partition+'.expanded.dat')
            decoder=brotli.Decompressor() if dat.endswith('.br') else None
            amount=0
            with z.open(dat) as src,expanded.open('xb') as dst:
                while chunk:=src.read(65536):
                    block=decoder.process(chunk) if decoder else chunk
                    amount+=len(block)
                    require(amount<=MAX_OUTPUT_SIZE,'expanded_data_too_big')
                    dst.write(block)
            require(decoder is None or decoder.is_finished(),'truncated_brotli')
            img=out/(partition+'.img')
            with expanded.open('rb') as stream:
                reference.reconstruct(transfer,stream,img)
            expanded.unlink()
            records=reference.extract_regular(img,out/partition)
            manifest['partitions'][partition]={'image_bytes':img.stat().st_size,
                'image_sha256':file_sha(img),'records':records}
            img.unlink()
    zip_path.unlink()
    got=(out/'system/etc/VERSION').read_text().strip()
    require(got==version,'system_version_mismatch')
    (out/'extraction_manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':'PASS_original_ota_extracted_without_execution',
        'firmware_version':version,'source_sha256':digest,
        'file_counts':{k:sum(r['kind']=='file' for r in v['records']) for k,v in manifest['partitions'].items()},
        'vendor_data_exported':False,'pixel_equivalence_proven':False},sort_keys=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--version',choices=RELEASES,required=True)
    a=p.parse_args()
    extract(a.source.resolve(),a.output.resolve(),a.version)

if __name__=='__main__':main()