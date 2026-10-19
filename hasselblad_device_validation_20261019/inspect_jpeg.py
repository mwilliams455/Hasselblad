#!/usr/bin/env python3
"""Read a supplied JPEG; record integrity, metadata, and exact pixel counts.

No image is modified or generated. Counts include watermarks and therefore
must not be presented as scene-only clipping measurements.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms


def inspect(path):
    payload = path.read_bytes()
    with Image.open(BytesIO(payload)) as check:
        check.verify()
    with Image.open(BytesIO(payload)) as image:
        image.load()
        pixels = np.asarray(image)
        if image.mode != "RGB":
            raise ValueError("This analysis expects the supplied RGB JPEG")
        profile_bytes = image.info.get("icc_profile", b"")
        profile = ImageCms.ImageCmsProfile(BytesIO(profile_bytes)) if profile_bytes else None
        result = {
            "input_filename": path.name,
            "input_bytes": len(payload),
            "input_sha256": hashlib.sha256(payload).hexdigest(),
            "decode_and_structure_verification": "passed",
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "exif_entry_count": len(image.getexif()),
            "icc_bytes": len(profile_bytes),
            "icc_name": ImageCms.getProfileName(profile).strip() if profile else None,
            "icc_description": ImageCms.getProfileDescription(profile).strip() if profile else None,
            "pixel_count": int(image.width * image.height),
            "channel_order": ["R", "G", "B"],
            "channel_min": pixels.min(axis=(0, 1)).tolist(),
            "channel_max": pixels.max(axis=(0, 1)).tolist(),
            "channel_at_255_counts": [int((pixels[:, :, i] == 255).sum()) for i in range(3)],
            "all_channels_255_pixel_count": int((pixels == 255).all(axis=2).sum()),
            "channel_at_zero_counts": [int((pixels[:, :, i] == 0).sum()) for i in range(3)],
            "all_channels_zero_pixel_count": int((pixels == 0).all(axis=2).sum()),
            "limitations": [
                "This received JPEG has no EXIF capture metadata.",
                "These dimensions describe the received file, not a verified original saved JPEG.",
                "Clipping counts include the burned-in Photon watermark.",
                "JPEG pixel values cannot prove RAW saturation, scene illuminant, or Hasselblad colour fidelity.",
            ],
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("jpeg", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = json.dumps(inspect(args.jpeg), indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
