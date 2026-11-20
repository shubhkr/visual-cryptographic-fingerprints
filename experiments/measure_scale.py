"""Measure proxy agreement across a fixed panel of synthetic digest pairs."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import imagehash
import numpy as np
from PIL import Image
from scipy.stats import spearmanr
from skimage.metrics import structural_similarity

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.vcf_prototype import (
    ca_encode,
    ca_to_image,
    randomwalk_encode,
    randomwalk_to_image,
    voronoi_encode,
    voronoi_to_image,
)


DISPLAY_SIZES = (32, 64, 128)
CONFIGURATIONS = {
    "walk_13x7": (randomwalk_encode, randomwalk_to_image, {"width": 13, "height": 7}),
    "walk_17x9": (randomwalk_encode, randomwalk_to_image, {}),
    "walk_23x13": (randomwalk_encode, randomwalk_to_image, {"width": 23, "height": 13}),
    "life_24x24_8": (ca_encode, ca_to_image, {"grid_size": 24}),
    "life_32x32_4": (ca_encode, ca_to_image, {"steps": 4}),
    "life_32x32_8": (ca_encode, ca_to_image, {}),
    "life_32x32_12": (ca_encode, ca_to_image, {"steps": 12}),
    "life_48x48_8": (ca_encode, ca_to_image, {"grid_size": 48}),
    "life_32x32_8_unmirrored": (ca_encode, ca_to_image, {"mirror": False}),
    "voronoi_8": (voronoi_encode, voronoi_to_image, {"k": 8}),
    "voronoi_12": (voronoi_encode, voronoi_to_image, {"k": 12}),
    "voronoi_16": (voronoi_encode, voronoi_to_image, {}),
}


def summarize(images, size):
    bits = np.array([imagehash.phash(Image.fromarray(image)).hash for image in images])
    distances = np.count_nonzero(bits[::2] != bits[1::2], axis=(1, 2))
    fixed = np.array([
        structural_similarity(a, b, win_size=7, data_range=255)
        for a, b in zip(images[::2], images[1::2])
    ])
    relative_window = {32: 3, 64: 7, 128: 15}[size]
    relative = fixed
    if relative_window != 7:
        relative = np.array([
            structural_similarity(a, b, win_size=relative_window, data_range=255)
            for a, b in zip(images[::2], images[1::2])
        ])
    # This totals the variability of the 32 DCT coefficients at odd horizontal
    # frequencies. Exact reflection symmetry forces those coefficients to zero.
    odd_bit_frequencies = bits[:, :, 1::2].mean(axis=0)
    correlation = None
    if np.ptp(fixed) > 0 and np.ptp(distances) > 0:
        correlation = float(spearmanr(fixed, -distances).statistic)
    return {
        "mean_ssim_window_7": float(fixed.mean()),
        "p99_ssim_window_7": float(np.quantile(fixed, 0.99)),
        "mean_ssim_relative_window": float(relative.mean()),
        "mean_phash_distance": float(distances.mean()),
        "p01_phash_distance": float(np.quantile(distances, 0.01)),
        "spearman_ssim_and_negative_phash": correlation,
        "mean_odd_horizontal_phash_bit_frequency": float(odd_bit_frequencies.mean()),
        "expected_hamming_from_odd_horizontal_bits": float(
            (2 * odd_bit_frequencies * (1 - odd_bit_frequencies)).sum()
        ),
    }


def run(pair_count):
    # Disjoint pairs, with identical inputs in every experimental condition.
    namespace = b"vcf-scale-v1\x00"
    digests = [
        hashlib.sha256(namespace + index.to_bytes(8, "big")).digest()
        for index in range(2 * pair_count)
    ]
    results = []
    for name, (encode, render, parameters) in CONFIGURATIONS.items():
        print(f"Measuring {name}", flush=True)
        encoded = [encode(digest, **parameters) for digest in digests]
        for size in DISPLAY_SIZES:
            if render is voronoi_to_image:
                images = [
                    render(labels, digest, size) for labels, digest in zip(encoded, digests)
                ]
            else:
                images = [render(values, size) for values in encoded]
            results.append({"configuration": name, "display_size": size, **summarize(images, size)})
    return {
        "protocol": {
            "pairs_per_condition": pair_count,
            "input": "SHA-256 of vcf-scale-v1 followed by NUL and an 8-byte big-endian counter",
            "display_sizes": DISPLAY_SIZES,
            "ssim_windows": {"fixed": 7, "relative": [3, 7, 15]},
            "phash": "ImageHash pHash, hash_size=8, highfreq_factor=4",
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("numpy", "scipy", "Pillow", "scikit-image", "ImageHash")
            },
        },
        "conditions": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", default=4096, type=int)
    args = parser.parse_args()
    if args.pairs < 2:
        parser.error("--pairs must be at least 2")
    args.output.write_text(json.dumps(run(args.pairs), indent=2, allow_nan=False) + "\n")
