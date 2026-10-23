#!/usr/bin/env python3
"""Private full-frame phone RAW experiment and Android preview bundle.

Do not put its outputs into a public repository or CI artifact. Sensor WB and
colour calibration come ONLY from this SHA-bound DNG, using existing Stage24
DNG-to-D50 code. Phocus sensor matrices are deliberately not used for the phone.
The selected LUT temperature is an explicit look parameter, not calibrated AWB.
"""
import argparse,hashlib,io,json,plistlib,struct,sys,time,zipfile
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image,ImageDraw
from core42 import Core
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'phocus_stage41y'))
sys.path.insert(0,str(ROOT/'isp_colour_stage24/src'))
import inspect_phocus_pipeline41y as y
from inspect_phocus_temperature41x import Runner,SETUP,PIXELS
import offline_render24 as old

def load_private(apk):
    original=apk.read_bytes();assert y.sha(original)==y.APK_SHA
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        lib=z.read('lib/arm64-v8a/libcrosssdk.so');data=z.read('assets/Colormaps/'+y.TARGET)
    assert y.sha(lib)==y.LIB_SHA
    elf=y.Elf(lib);blocks=np.frombuffer(data,dtype=np.uint8).reshape(-1,16)
    plain=(y.decrypt_blocks(elf,blocks[1:])^blocks[:-1]).tobytes()
    pad=plain[-1];assert 1<=pad<=16 and plain[-pad:]==bytes([pad])*pad
    plain=plain[:-pad]
    assert y.sha(plain)=='c2b3d08e0d489eb852610c12a9b985e9d0340a4dd544f5b0b5b7a6a4f3427e95'
    return elf,plistlib.loads(plain)

def srgb(v):
    v=np.clip(v,0,1)
    v=np.where(v<=.0031308,12.92*v,1.055*v**(1/2.4)-.055)
    return np.floor(v*255+.5).astype(np.uint8)

def display(encoded,matrix,exponent):
    return srgb(((encoded.astype(np.float64)/65536)**exponent)@matrix.T)

def save_image(rgb,orientation,path):
    im=Image.fromarray(rgb)
    if orientation==6:im=im.transpose(Image.Transpose.ROTATE_270)
    im.save(path,quality=95)
    return im

def native_photo_sample(elf,profile,pixels,p,temperature):
    r=Runner(elf);r.profile=profile
    cc,m1,m2,grad,inp,out=0x10010000,0x10011000,0x10012000,0x10020000,0x10080000,0x10090000
    for ptr,length in ((r.obj,0x318),(cc,0x298)):
        r.u.mem_write(ptr-16,b'\xa5'*16);r.u.mem_write(ptr+length,b'\xa5'*16)
    r.call(y.DECODE,(r.obj,r.coder));r.u.mem_write(r.obj+9,b'\1')
    r.u.mem_write(m1,np.asarray(p.first,dtype='<f8').tobytes())
    r.u.mem_write(m2,np.asarray(p.second,dtype='<f8').tobytes())
    r.u.mem_write(grad,p._arrays[1].astype('<f4').tobytes())
    r.call(SETUP,(cc,m1,m2,r.obj,temperature,0,grad,65536),floats=(0.,0.),
           stack=struct.pack('<QQQQ',0,50,0,1))
    r.u.mem_write(cc+0x1b8,np.asarray(p.shadow,dtype='<f8').tobytes())
    assert np.allclose(r.table(cc+0x138)[0],p._arrays[0],rtol=0,atol=1e-12)
    source=pixels.astype('<u2').tobytes();r.u.mem_write(inp,source)
    r.u.mem_write(out,b'\xa5'*32+b'\xcc'*len(source)+b'\xa5'*32)
    frozen=[(cc,bytes(r.u.mem_read(cc,0x298))),(inp,source)]
    frozen += [(a+16,bytes(r.u.mem_read(a+16,n))) for a,n in r.allocations]
    r.call(PIXELS,(0,cc,out+32,inp,len(pixels),0))
    actual=np.frombuffer(bytes(r.u.mem_read(out+32,len(source))),dtype='<u2').reshape(-1,3)
    assert all(bytes(r.u.mem_read(a,len(b)))==b for a,b in frozen)
    assert bytes(r.u.mem_read(out,32))==bytes(r.u.mem_read(out+32+len(source),32))==b'\xa5'*32
    r.check_guards()
    return actual

def main():
    parser=argparse.ArgumentParser()
    for name in ('apk','dng','sidecar','out'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--temperature',type=int,default=4000)
    parser.add_argument('--reference-jpeg',type=Path)
    args=parser.parse_args();assert __debug__
    if not 2000<=args.temperature<=10000:raise ValueError('Unsupported LUT temperature')
    args.out.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(args.dng.read_bytes()).digest()
    sidecar=json.loads(args.sidecar.read_text())
    assert sidecar['dng']['sha256']==digest.hex(),'Sidecar does not bind this DNG'
    with tifffile.TiffFile(args.dng) as doc:
        pg=doc.pages[0];m=old.extract_metadata(pg.tags);raw=pg.asarray()
        assert raw.shape==(3072,4096) or raw.size<=16777216
        if 'ActiveArea' in pg.tags:
            assert tuple(pg.tags['ActiveArea'].value)==(0,0,*raw.shape),'Active crop unsupported'
        if 'DefaultCropOrigin' in pg.tags or 'DefaultCropSize' in pg.tags:
            raise ValueError('Explicit crop requires a separately tested path')
        if m['unhandled_dng_opcodes']!=['OpcodeList2']:
            raise ValueError('This preview preparer requires the tested GainMap-only DNG path')
        dem,gain_receipt=old.stage30_opcode2_gainmap_reference(raw,m,bytes(pg.tags['OpcodeList2'].value))
    ctx=old.context(old.compile_shared(args.out/'private-dng-core.so'),m,0)
    camera=np.asarray(ctx.camera_to_xyz_d50).reshape(3,3)
    xyz_to_srgb=np.asarray(ctx.xyz_d50_to_linear_rgb).reshape(3,3)
    elf,profile=load_private(args.apk)
    basis,to_internal,transforms=y.matrix_constants(elf)
    # Experimental phone-domain substitution: DNG calibrated D50 replaces P*G.
    # No X2D sensor matrix or its temperature-to-WB gains touches phone samples.
    first=basis@to_internal@camera;second=transforms[0]@np.linalg.inv(basis)
    grid=y.lut_oracle(profile,args.temperature,False)
    curve=y.curve_oracle(elf,1,1);shadow=y.shadow_oracle(elf,0,1)
    display_matrix=xyz_to_srgb@np.linalg.inv(to_internal)
    exponent=1/struct.unpack('<d',elf.read(0x306f9a0,8))[0]
    core=Core(args.out/'private-hb42.so')
    p=core.params(first,second,grid,False,curve,shadow)
    rgb=np.floor(np.clip(dem,0,1)*65535).astype(np.uint16)
    start=time.monotonic();encoded=core.render(rgb,p);elapsed=time.monotonic()-start
    # Stratified real photographic samples through original ARM64 colour code.
    indices=np.linspace(0,rgb.size//3-1,512,dtype=int)
    sample=rgb.reshape(-1,3)[indices];original=native_photo_sample(elf,profile,sample,p,args.temperature)
    tested=core.render(sample,p);delta=np.abs(original.astype(int)-tested.astype(int))
    assert delta.max()==0,('Photo sample mismatch',delta.max(),np.count_nonzero(delta))
    experimental=display(encoded,display_matrix,exponent)
    # Shared preparation, same quantization/WB, no exposure match or local tone.
    baseline=srgb((rgb.astype(float)/65535)@(xyz_to_srgb@camera).T)
    im_exp=save_image(experimental,m['orientation'],args.out/'Stage42_Experimental.jpg')
    im_base=save_image(baseline,m['orientation'],args.out/'Stage42_Same_RAW_Baseline.jpg')
    # Identity chroma map isolates the LUT's contribution while retaining tone.
    gy,gx=np.mgrid[:89,:105];identity=np.stack([gx-20,gy-32],-1)
    tone=core.render(rgb,core.params(first,second,identity,False,curve,shadow))
    tone_display=display(tone,display_matrix,exponent)
    save_image(tone_display,m['orientation'],args.out/'Stage42_Tone_Only_Control.jpg')
    # Compact Android input is a grid sample after full-resolution demosaic;
    # never average already transformed nonlinear output as a reference.
    step=max(1,int(np.ceil(np.sqrt(rgb.shape[0]*rgb.shape[1]/1048576))))
    small=np.ascontiguousarray(rgb[::step,::step]);small_out=core.render(small,p)
    small_base=np.ascontiguousarray(baseline[::step,::step])
    h,w=small.shape[:2]
    values=np.r_[first.ravel(),second.ravel(),shadow,[1.,1.,1.],1.,20.,32.,display_matrix.ravel(),exponent]
    payload=b'HB42RAW1'+struct.pack('<10i',w,h,105,89,1,m['orientation'],args.temperature,0,1,0)
    payload+=values.astype('<f8').tobytes()+grid.astype('<f8').tobytes()+curve.astype('<f4').tobytes()
    payload+=digest+hashlib.sha256(small_out.astype('<u2').tobytes()).digest()
    payload+=small.astype('<u2').tobytes()+small_base.tobytes()
    (args.out/'Stage42_Saved_RAW_Experiment.hb42').write_bytes(payload+hashlib.sha256(payload).digest())
    images=[('Same RAW: neutral baseline',im_base),('Experimental colour + tone',im_exp)]
    if args.reference_jpeg:
        # This source is not declared a registered/pixel-identical reference.
        from PIL import ImageOps
        images.append(('Saved Photon JPEG (unregistered)',ImageOps.exif_transpose(Image.open(args.reference_jpeg)).convert('RGB')))
    panel=Image.new('RGB',(600*len(images),850),(25,25,25));draw=ImageDraw.Draw(panel)
    for i,(label,im) in enumerate(images):
        im=im.copy();im.thumbnail((580,790));panel.paste(im,(600*i+(600-im.width)//2,48+(790-im.height)//2))
        draw.text((600*i+16,18),label,fill='white')
    panel.save(args.out/'Stage42_Comparison.jpg',quality=94)
    assert hashlib.sha256(args.dng.read_bytes()).digest()==digest
    assert hashlib.sha256(args.apk.read_bytes()).hexdigest()==y.APK_SHA
    d=np.abs(experimental.astype(int)-tone_display.astype(int))
    receipt={'schema':'hasselblad-stage42-private-phone-render-v1','source_dng_sha256':digest.hex(),
        'input_dimensions':list(raw.shape[::-1]),'output_orientation':m['orientation'],
        'cfa':'RGGB','black_level':m['black'],'white_level':m['white'],
        'gainmap':gain_receipt,'full_frame_rendered_pixels':int(rgb.size//3),
        'core_seconds':elapsed,'original_arm64_photo_channels':int(delta.size),
        'original_arm64_photo_max_difference':int(delta.max()),
        'wb_owner':'DNG calibrated camera_to_XYZ_D50 matrix; separate WB unity',
        'input_negative_channels_clipped_to_RGB16':int((dem<0).sum()),
        'input_over_unity_channels_clipped_to_RGB16':int((dem>1).sum()),
        'exposure_gain':1,'look_temperature_manual':args.temperature,'model_code':0,'film_code':1,'space_code':0,
        'display_adapter':'inverse recovered input basis to D50; recovered companding decoded; Stage19 D50 to sRGB',
        'display_adapter_is_experimental':True,'phocus_UI_space_names_bound':False,
        'look_vs_tone_only_mean_abs_8bit':float(d.mean()),'look_vs_tone_only_max_abs_8bit':int(d.max()),
        'experimental_display_clipped_black_channels':int((experimental==0).sum()),
        'experimental_display_clipped_white_channels':int((experimental==255).sum()),
        'preview_dimensions':[w,h],'preview_sha256':hashlib.sha256(payload+hashlib.sha256(payload).digest()).hexdigest(),
        'source_unchanged':True,'sidecar_bound':True,'camera_specific_X2D_matrix_applied_to_phone':False,
        'demosaic':'Stage30 RGGB float bilinear reference, not Photon',
        'phone_colour_adaptation_validated_against_controlled_Phocus_export':False,
        'full_Phocus_or_camera_ISP_equivalence':False,'photon_capture_renderer_changed':False}
    (args.out/'Stage42_Private_Render_Receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('full_frame_rendered_pixels','core_seconds',
        'original_arm64_photo_channels','original_arm64_photo_max_difference','preview_dimensions',
        'look_vs_tone_only_mean_abs_8bit','source_unchanged')}),flush=True)
if __name__=='__main__':main()
