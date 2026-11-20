"""
Batched SSIM and pHash, numerically matched to the reference libraries.

* ssim_to_target reproduces skimage.metrics.structural_similarity(a, b,
  data_range=255) with its defaults (7x7 uniform window, sample covariance,
  reflect padding, 3-pixel border cropped before averaging).
* phash_bits reproduces imagehash.phash(img) with hash_size=8,
  highfreq_factor=4 (LANCZOS resize to 32x32, 2-D DCT-II, top-left 8x8
  block thresholded at its median). Hashes are packed into uint64 so that
  Hamming distances against millions of candidates are cheap.
"""

import numpy as np
from PIL import Image
from scipy.fftpack import dct
from scipy.ndimage import uniform_filter

_C1 = (0.01 * 255) ** 2
_C2 = (0.03 * 255) ** 2
_WIN = 7
_NP = _WIN * _WIN
_COV = _NP / (_NP - 1)
_PAD = (_WIN - 1) // 2


def _f(x):
    return uniform_filter(x, size=(1, _WIN, _WIN))


def ssim_stats(batch: np.ndarray):
    """Precompute local means and variances for a batch (B,H,W)."""
    x = batch.astype(np.float64)
    ux = _f(x)
    vx = _COV * (_f(x * x) - ux * ux)
    return x, ux, vx


def ssim_to_target(stats, target: np.ndarray) -> np.ndarray:
    """SSIM of every image in a batch against one target. Returns (B,)."""
    x, ux, vx = stats
    t = target.astype(np.float64)[None]
    ut = _f(t)
    vt = _COV * (_f(t * t) - ut * ut)
    vxt = _COV * (_f(x * t) - ux * ut)
    s = ((2 * ux * ut + _C1) * (2 * vxt + _C2)) / \
        ((ux * ux + ut * ut + _C1) * (vx + vt + _C2))
    p = _PAD
    return s[:, p:-p, p:-p].mean(axis=(1, 2))


def ssim_pairs(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Element-wise SSIM between two equal-length batches. Returns (B,)."""
    x = a.astype(np.float64)
    y = b.astype(np.float64)
    ux, uy = _f(x), _f(y)
    vx = _COV * (_f(x * x) - ux * ux)
    vy = _COV * (_f(y * y) - uy * uy)
    vxy = _COV * (_f(x * y) - ux * uy)
    s = ((2 * ux * uy + _C1) * (2 * vxy + _C2)) / \
        ((ux * ux + uy * uy + _C1) * (vx + vy + _C2))
    p = _PAD
    return s[:, p:-p, p:-p].mean(axis=(1, 2))


_BITW = (1 << np.arange(63, -1, -1, dtype=np.uint64)).astype(np.uint64)


def phash_bits(batch: np.ndarray) -> np.ndarray:
    """64-bit pHash for each image in (B,H,W) uint8. Returns (B,) uint64."""
    small = np.stack([
        np.asarray(Image.fromarray(im, mode="L").resize((32, 32), Image.Resampling.LANCZOS),
                   dtype=np.float64)
        for im in batch
    ])
    d = dct(dct(small, axis=1), axis=2)[:, :8, :8].reshape(len(batch), 64)
    med = np.median(d, axis=1, keepdims=True)
    bits = (d > med).astype(np.uint64)
    return (bits * _BITW).sum(axis=1, dtype=np.uint64)


def hamming(a: np.ndarray, b) -> np.ndarray:
    """Popcount of a XOR b for uint64 arrays (broadcasting)."""
    x = np.bitwise_xor(a, b)
    return np.bitwise_count(x).astype(np.int64) if hasattr(np, "bitwise_count") \
        else np.unpackbits(x.view(np.uint8).reshape(*x.shape, 8), axis=-1).sum(-1)
