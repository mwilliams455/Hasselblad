#!/usr/bin/env python3
"""Verify real saved DNG access locally; emit no pixel values or private hashes.

This intentionally supports the established uncompressed, single-strip,
16-bit CFA phone fixture. It is not a general RAW converter or HNCS renderer.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def verify(dng,sidecar,jpeg=None):
    initial_hash=digest(dng)
    record=json.loads(sidecar.read_text())
    require(record['schema']=='hasselblad-photon-capture-evidence-v1','unsupported_capture_record')
    require(record['dng']['sha256']==initial_hash,'DNG_capture_record_hash_mismatch')
    require(record['dng']['bytes']==dng.stat().st_size,'DNG_capture_record_length_mismatch')
    require(record['pairing_status']=='image_timestamp_equals_selected_still_result_timestamp','capture_pairing_not_recorded')
    delivered=record['delivered_raw']
    with tifffile.TiffFile(dng) as f:
        require(len(f.pages)==1,'fixture_requires_one_top_level_IFD')
        p=f.pages[0]
        require(int(p.photometric)==32803 and 'DNGVersion' in p.tags,'not_CFA_DNG')
        require(int(p.compression)==1 and p.bitspersample==16 and p.samplesperpixel==1,'unsupported_raw_storage')
        require(len(p.dataoffsets)==1 and len(p.databytecounts)==1,'fixture_requires_one_strip')
        require(tuple(p.shape)==(delivered['delivered_height'],delivered['delivered_width']),'delivered_shape_mismatch')
        require(tuple(p.tags['CFARepeatPatternDim'].value)==(2,2),'unsupported_CFA_dimensions')
        require(bytes(p.tags['CFAPattern'].value)==bytes((0,1,1,2)),'fixture_requires_RGGB')
        offset=int(p.dataoffsets[0]);count=int(p.databytecounts[0])
        require(offset>=0 and offset+count<=dng.stat().st_size,'raw_strip_out_of_bounds')
        require(count==int(np.prod(p.shape))*2,'raw_strip_length_mismatch')
        samples=p.asarray()
        require(samples.dtype.kind=='u' and samples.dtype.itemsize==2,'unexpected_array_type')
        mapped=np.memmap(dng,dtype=f.byteorder+'u2',mode='r',offset=offset,shape=p.shape)
        require(np.array_equal(samples,mapped),'decoded_samples_differ_from_raw_strip')
        require(int(samples.max())>int(samples.min()),'fixture_has_no_sample_variation')
        colour_tags=['BlackLevel','WhiteLevel','AsShotNeutral','ColorMatrix1','ColorMatrix2',
                     'ForwardMatrix1','ForwardMatrix2','OpcodeList2']
        raw=dict(width=int(p.shape[1]),height=int(p.shape[0]),sensor_samples=int(samples.size),
            decoded_raw_bytes=count,storage_bits=16,cfa='RGGB',compression='none',
            full_array_read=True,independent_raw_strip_comparison='exact',
            nonconstant_samples=True,is_demosaiced_RGB=False,
            colour_metadata_presence={n:n in p.tags for n in colour_tags})
        del mapped
    jpg=None
    if jpeg is not None:
        with Image.open(jpeg) as im:
            im.load()
            jpg=dict(width=im.width,height=im.height,mode=im.mode,
                full_array_decoded=True,icc_profile_present=bool(im.info.get('icc_profile')),
                same_capture_binding_independently_proven=False,
                dimensions_equal_raw_without_rotation_or_resampling=im.size==(raw['width'],raw['height']))
    require(digest(dng)==initial_hash,'source_changed_during_read')
    return dict(schema='hasselblad-stage41i-real-RAW-access-v1',status='PASS_real_saved_RAW_pixels_accessible_in_Work_Mode',
        raw=raw,supplied_jpeg=jpg,input_is_synthetic=False,source_DNG_unmodified=True,
        DNG_hash_and_length_match_capture_record=True,capture_timestamp_pairing_record_present=True,
        independent_hardware_attestation=False,source_is_phone_DNG_not_X2D_II_internal_buffer=True,
        calibration_corrections_or_demosaic_applied=False,Hasselblad_pixel_renderer_executed=False,
        isolated_MAIN_CCM_before_after_pixels_obtained=False,
        private_pixel_values_hashes_camera_IDs_or_calibration_arrays_exported=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dng',type=Path,required=True)
    p.add_argument('--sidecar',type=Path,required=True)
    p.add_argument('--jpeg',type=Path)
    p.add_argument('--output-safe',type=Path,required=True)
    a=p.parse_args();r=verify(a.dng,a.sidecar,a.jpeg)
    a.output_safe.parent.mkdir(parents=True,exist_ok=True)
    a.output_safe.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=r['status'],sensor_samples=r['raw']['sensor_samples'],input_is_synthetic=False)))
