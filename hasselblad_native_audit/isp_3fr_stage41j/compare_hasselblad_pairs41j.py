#!/usr/bin/env python3
"""Private 3FR/reference comparison; conventional LibRaw baseline, not HNCS.

Manifest: [{"label": "A", "raw": "/private/input.3fr", "jpeg": "/private/ref.jpg"}].
Only the explicitly selected aggregate receipt is suitable for a public repository.
Keep the manifest, caches, images, and private ledger outside public repositories.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
import cv2
import numpy as np
import rawpy
import tifffile
from PIL import Image, ImageCms
from scipy.optimize import minimize_scalar


def srgb_encode(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= .0031308, 12.92*x, 1.055*x**(1/2.4)-.055)


def srgb_decode(x):
    x = np.asarray(x)
    return np.where(x <= .04045, x/12.92, ((x+.055)/1.055)**2.4)


def orient(a, orientation):
    if orientation == 1:
        return a
    if orientation == 8:
        return np.rot90(a, 1)
    if orientation == 6:
        return np.rot90(a, -1)
    if orientation == 3:
        return np.rot90(a, 2)
    raise ValueError(f"Unsupported orientation: {orientation}")


def half_crop(a, origin, size):
    x, y = map(int, origin)
    w, h = map(int, size)
    assert all(v % 2 == 0 for v in (x, y, w, h)), "Odd crop needs explicit resampling"
    assert x >= 0 and y >= 0 and x+w <= a.shape[1]*2 and y+h <= a.shape[0]*2
    return a[y//2:(y+h)//2, x//2:(x+w)//2]


def resize(a, size):
    return cv2.resize(a, tuple(size), interpolation=cv2.INTER_AREA)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8*1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def gray(a):
    return np.asarray(a @ np.array([.2126, .7152, .0722], np.float32), np.float32)


def registration(source, target):
    """Similarity transform from independent grayscale keypoints, not RGB fitting."""
    cv2.setRNGSeed(410)
    sift = cv2.SIFT_create(nfeatures=6000)
    def features(a):
        g = np.uint8(np.clip(gray(a)*255, 0, 255))
        return sift.detectAndCompute(g, None)
    ka, da = features(source)
    kb, db = features(target)
    assert da is not None and db is not None, "No registration descriptors"
    nn = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [a for pair in nn if len(pair) == 2 for a, b in [pair] if a.distance < .7*b.distance]
    assert len(good) >= 30, "Insufficient image correspondences"
    a = np.float32([ka[m.queryIdx].pt for m in good])
    b = np.float32([kb[m.trainIdx].pt for m in good])
    warp, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=1.5, maxIters=5000, confidence=.999)
    assert warp is not None
    valid = inliers.ravel().astype(bool)
    errors = np.linalg.norm(a @ warp[:,:2].T + warp[:,2] - b, axis=1)
    scale = float(np.hypot(warp[0,0], warp[1,0]))
    rotation = float(np.degrees(np.arctan2(warp[1,0], warp[0,0])))
    span = np.ptp(b[valid], axis=0) / np.array([target.shape[1], target.shape[0]])
    assert valid.sum() >= 30 and np.all(span > .45), "Poor registration coverage"
    assert .97 < scale < 1.03 and abs(rotation) < 1 and np.max(abs(warp[:,2])) < 25, "Unexpected geometry"
    info = {"matches":len(good), "inliers":int(valid.sum()), "median_inlier_error_px":float(np.median(errors[valid])), "p95_inlier_error_px":float(np.percentile(errors[valid],95)), "scale":scale, "rotation_degrees":rotation, "translation_px":warp[:,2].tolist()}
    return warp, info


def fit_exposure(linear, target, mask):
    x = linear[mask][::7]
    y = target[mask][::7]
    assert len(x) >= 100
    objective = lambda ev: float(np.mean(np.abs(srgb_encode(x * 2**ev)-y)))
    fit = minimize_scalar(objective, bounds=(-4, 4), method="bounded", options={"xatol":1e-6})
    assert fit.success and abs(fit.x) < 3.99
    return float(fit.x)


def metric(pred, ref, mask):
    p, r = pred[mask].astype(np.float32), ref[mask].astype(np.float32)
    mae = float(np.abs(p-r).mean()*255)
    # OpenCV float RGB->Lab uses an sRGB/D65 interpretation. This is a rendered
    # image difference, not colour-chart accuracy, and is labelled accordingly.
    lp = cv2.cvtColor(p.reshape(-1,1,3), cv2.COLOR_RGB2Lab).reshape(-1,3)
    lr = cv2.cvtColor(r.reshape(-1,1,3), cv2.COLOR_RGB2Lab).reshape(-1,3)
    de = np.linalg.norm(lp-lr, axis=1)
    return {"pixels":int(mask.sum()), "rgb_mae_8bit":mae, "median_deltaE76_srgb_assumption":float(np.median(de)), "p90_deltaE76_srgb_assumption":float(np.percentile(de,90)), "median_abs_deltaL":float(np.median(abs(lp[:,0]-lr[:,0]))), "median_ab_distance":float(np.median(np.linalg.norm(lp[:,1:]-lr[:,1:],axis=1)))}


def png(path, a):
    # Quantitative render export, no creative/generative processing.
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.fromarray(np.uint8(np.rint(np.clip(a,0,1)*255))).save(path, icc_profile=icc)


def process(item, out, edge=768):
    p = Path(item["raw"])
    label = item["label"]
    assert label.isalnum() and len(label) <= 12
    original_hash = digest(p)
    with tifffile.TiffFile(p) as t:
        root = t.pages[0]
        pg = root.pages[0]
        assert int(pg.compression) == 1 and len(pg.dataoffsets) == 1
        assert pg.databytecounts[0] == np.prod(pg.shape)*2
        assert pg.dataoffsets[0]+pg.databytecounts[0] <= p.stat().st_size
        origin = root.pages[0].tags["DefaultCropOrigin"].value
        size = root.pages[0].tags["DefaultCropSize"].value
        orientation = root.tags["Orientation"].value
        b = pg.tags["BlackLevel"].value
        assert len(b) == 2 and b[1] > 0 and b[0] % b[1] == 0
        black = b[0]//b[1]
        white = int(pg.tags["WhiteLevel"].value)
        neutral_pairs = np.asarray(root.tags["AsShotNeutral"].value).reshape(-1,2)
        neutral = neutral_pairs[:,0]/neutral_pairs[:,1]
        inv = 1/neutral
        inv /= inv[1]
        software = str(root.tags["Software"].value)
        model = str(root.tags["Model"].value)
        raw_shape = pg.shape
        mm = np.memmap(p, mode="r", dtype=t.byteorder+"u2", offset=pg.dataoffsets[0], shape=pg.shape)
        assert len(root.dataoffsets) == 1
        with p.open("rb") as f:
            f.seek(root.dataoffsets[0]); preview_bytes = f.read(root.databytecounts[0])
    with Image.open(io.BytesIO(preview_bytes)) as im:
        preview_icc = bool(im.info.get("icc_profile"))
        reference = orient(np.asarray(im.convert("RGB"),np.float32)/255, orientation)
    h, w = reference.shape[:2]
    target_size = (round(w*edge/max(w,h)), round(h*edge/max(w,h)))
    reference = resize(reference, target_size)
    with Image.open(item["jpeg"]) as im:
        jpeg_icc = im.info.get("icc_profile")
        assert jpeg_icc, "Tagged JPEG required for the secondary colour reference"
        profile_name = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(jpeg_icc))).strip()
        converted = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(jpeg_icc)), ImageCms.createProfile("sRGB"), outputMode="RGB")
        jpeg = resize(np.asarray(converted,np.float32)/255, target_size)
    with rawpy.imread(str(p)) as r:
        assert r.raw_image.shape == mm.shape
        exact = all(np.array_equal(r.raw_image[y:y+128],mm[y:y+128]) for y in range(0,raw_shape[0],128))
        assert exact, "LibRaw unpack differs from stored TIFF sensor samples"
        pattern = r.raw_pattern.tolist()
        assert pattern == [[0,1],[3,2]] and r.color_desc == b"RGBG"
        wb = np.array(r.camera_whitebalance[:3])
        assert np.max(abs(wb/wb[1]-inv)) < 1e-6
        original_sizes = r.sizes._asdict()
        black_offsets = [int(x-black) for x in r.black_level_per_channel]
        assert r.white_level == white
        linear = r.postprocess(half_size=True, use_camera_wb=True, use_auto_wb=False,
            output_color=rawpy.ColorSpace.sRGB, output_bps=16, user_flip=0,
            user_black=black, user_cblack=[0,0,0,0], user_sat=white,
            no_auto_bright=True, adjust_maximum_thr=0.0, bright=1.0,
            gamma=(1,1), highlight_mode=rawpy.HighlightMode.Clip)
        actual_wb = np.array(r.auto_whitebalance[:3])
        wb_error = float(np.max(abs(actual_wb/actual_wb[1]-inv)))
        assert wb_error < 1e-5
        linear = half_crop(linear, origin, size)
        linear = resize(orient(linear, orientation), target_size).astype(np.float32)/65535
    del mm
    assert digest(p) == original_hash
    initial = srgb_encode(linear)
    warp, alignment = registration(initial, reference)
    aligned = cv2.warpAffine(linear, warp, target_size, flags=cv2.INTER_LINEAR)
    mask = cv2.warpAffine(np.ones(linear.shape[:2],np.uint8), warp, target_size, flags=cv2.INTER_NEAREST).astype(bool)
    # Registration is sub-pixel; exclude high-gradient detail, clipping, borders
    # for colour measurements. These are diagnostic sampling choices, not a fit.
    g = gray(reference)
    grad = np.hypot(cv2.Sobel(g,cv2.CV_32F,1,0,ksize=3),cv2.Sobel(g,cv2.CV_32F,0,1,ksize=3))
    mask &= (grad < .08) & (reference.min(2) > .02) & (reference.max(2) < .98)
    mask &= (aligned.min(2) > .0002) & (aligned.max(2) < .98)
    mask[:12,:]=False; mask[-12:,:]=False; mask[:,:12]=False; mask[:,-12:]=False
    assert mask.sum() > 2000
    ev = fit_exposure(aligned, reference, mask)
    adjusted = srgb_encode(aligned*2**ev)
    base = srgb_encode(aligned)
    public = {"label":label,"camera_model":model,"capture_software":software,
        "sensor_shape":list(raw_shape),"full_sensor_decoder_matches_storage":exact,
        "cfa":"RGGB (LibRaw RGBG indices 0,1 / 3,2)","default_crop_origin":list(origin),"default_crop_size":list(size),
        "libraw_default_crop_applied":original_sizes["width"]==size[0] and original_sizes["height"]==size[1],
        "decoder_black_minus_declared_per_channel":black_offsets,"white_level_matches_metadata":True,
        "as_shot_wb_matches_inverse_neutral":True,"applied_wb_normalized_max_error":wb_error,
        "reference_preview_has_icc":preview_icc,"secondary_jpeg_profile":profile_name,
        "analysis_size":list(target_size),"registration":alignment,
        "exposure_fit_EV":ev,"original_unchanged":True,
        "baseline_vs_preview":metric(base,reference,mask),
        "exposure_only_vs_preview":metric(adjusted,reference,mask),
        "exposure_only_vs_tagged_jpeg":metric(adjusted,jpeg,mask),
        "preview_vs_tagged_jpeg":metric(reference,jpeg,mask)}
    np.savez_compressed(out/f"{label}_analysis.npz", linear=aligned, reference=reference, jpeg=jpeg, mask=mask)
    png(out/f"{label}_baseline.png",base)
    png(out/f"{label}_exposure.png",adjusted)
    png(out/f"{label}_reference.png",reference)
    private = {"label":label,"raw_path":str(p.resolve()),"raw_sha256":original_hash,"jpeg_path":str(Path(item["jpeg"]).resolve()),"jpeg_sha256":digest(item["jpeg"]),"black_level":black,"white_level":white,"as_shot_neutral":neutral.tolist(),"rawpy_original_sizes":original_sizes}
    return public, private


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--private-dir",type=Path,required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    args=ap.parse_args()
    args.private_dir.mkdir(parents=True,exist_ok=True)
    cv2.setNumThreads(2)
    result={"schema":"hasselblad-stage41j-real-3fr-baseline-v1","renderer":"LibRaw conventional half-size linear sRGB; explicit metadata black/white/crop and as-shot WB; manual sRGB encoding","rawpy_version":rawpy.__version__,"libraw_version":list(rawpy.libraw_version),"opencv_version":cv2.__version__,"numpy_version":np.__version__,"tifffile_version":tifffile.__version__,"main_ccm_equation_recovered":False,"hncs_rendering_implemented":False,"production_photo_output_changed":False,"preview_colour_space_assumed":"sRGB (untagged preview); tagged JPEG checked separately","metrics_scope":"Descriptive within-image measurements; per-image exposure fitted on those same pixels, not held-out validation or chart accuracy; residual includes decoder, tone, colour, optical, sharpening and noise differences","pairs":[]}
    private=[]
    for item in json.loads(args.manifest.read_text()):
        public, record=process(item,args.private_dir)
        result["pairs"].append(public); private.append(record)
        print(json.dumps(public),flush=True)
    args.receipt.write_text(json.dumps(result,indent=2)+"\n")
    (args.private_dir/"private_input_ledger.json").write_text(json.dumps(private,indent=2)+"\n")


if __name__ == "__main__":
    main()
