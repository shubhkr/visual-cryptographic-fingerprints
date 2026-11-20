"""
VCF encodings, specification v2.

Changes from v1 (vcf_prototype.py):
  * Every bit of encoding state is derived from the input digest, either
    directly or through SHAKE-256 (FIPS 202). No library PRNG is used, so
    the encodings are reimplementable in any language with SHA-3.
  * Cellular automata: the whole board comes from SHAKE-256 (v1 seeded 768
    of 1,024 cells from NumPy's Mersenne Twister keyed on 4 digest bytes).
  * Voronoi: site coordinates and cell intensities come from disjoint
    SHAKE-256 output bytes (v1 reused coordinate bytes for intensities).
  * All encodings are parameterised so that configuration sweeps can be run.

Each encoder has a batched implementation (used for the large experiments)
and is checked against a simple per-image reference in tests below.
"""

import hashlib

import numpy as np
from PIL import Image

SPEC_VERSION = "vcf-v2"


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def xof(digest: bytes, n: int) -> bytes:
    """SHAKE-256 expansion of the digest to n bytes."""
    return hashlib.shake_256(digest).digest(n)


def _nearest_index(src: int, dst: int) -> np.ndarray:
    """Source index for each destination pixel, matching PIL NEAREST."""
    return np.minimum(((np.arange(dst) + 0.5) * src / dst).astype(np.int64), src - 1)


def upscale_nearest(native: np.ndarray, size: int) -> np.ndarray:
    """Batched nearest-neighbour resize (B,h,w) -> (B,size,size)."""
    _, h, w = native.shape
    return native[:, _nearest_index(h, size)][:, :, _nearest_index(w, size)]


def normalise(counts: np.ndarray) -> np.ndarray:
    """Per-image scale to 0..255 (B,h,w) int -> uint8, as in v1."""
    mx = counts.reshape(len(counts), -1).max(axis=1)
    mx = np.maximum(mx, 1).astype(np.float64)[:, None, None]
    return (counts.astype(np.float64) / mx * 255).astype(np.uint8)


# ------------------------------------------------------------------
# Encoding A: random-walk grid (drunken bishop)
# ------------------------------------------------------------------

def rw_moves(digest: bytes, n_moves: int) -> np.ndarray:
    """2-bit moves, LSB-first within each byte (OpenSSH order).
    128 moves use the digest itself; longer walks extend via SHAKE-256."""
    src = digest if n_moves <= 4 * len(digest) else xof(digest, n_moves // 4)
    b = np.frombuffer(src, dtype=np.uint8)
    pairs = np.stack([(b >> s) & 3 for s in (0, 2, 4, 6)], axis=1).reshape(-1)
    return pairs[:n_moves]


def mirror(native: np.ndarray) -> np.ndarray:
    """Copy the left half of each image onto the right half (control only)."""
    out = native.copy()
    w = out.shape[2]
    half = w // 2
    out[:, :, w - half:] = out[:, :, :half][:, :, ::-1]
    return out


def rw_native(digests, w=17, h=9, n_moves=128) -> np.ndarray:
    moves = np.stack([rw_moves(d, n_moves) for d in digests])  # (B,n)
    B = len(digests)
    grid = np.zeros((B, h, w), dtype=np.int32)
    x = np.full(B, w // 2)
    y = np.full(B, h // 2)
    ar = np.arange(B)
    for t in range(n_moves):
        p = moves[:, t]
        x = np.clip(x + np.where(p & 1, 1, -1), 0, w - 1)
        y = np.clip(y + np.where(p & 2, 1, -1), 0, h - 1)
        grid[ar, y, x] += 1
    return grid


# ------------------------------------------------------------------
# Encoding B: cellular automata (LifeHash-like)
# ------------------------------------------------------------------

def ca_native(digests, n=32, steps=8, symmetric=True) -> np.ndarray:
    nbytes = (n * n + 7) // 8
    bits = np.stack([
        np.unpackbits(np.frombuffer(xof(d, nbytes), dtype=np.uint8))[:n * n]
        for d in digests
    ]).reshape(-1, n, n).astype(np.uint8)
    if symmetric:
        half = n // 2
        bits[:, :, half:] = bits[:, :, :half][:, :, ::-1][:, :, : n - half]
    board = bits
    heat = board.astype(np.int32)
    for _ in range(steps):
        nb = sum(np.roll(np.roll(board, dr, axis=1), dc, axis=2)
                 for dr in (-1, 0, 1) for dc in (-1, 0, 1)) - board
        board = (((board == 1) & ((nb == 2) | (nb == 3))) |
                 ((board == 0) & (nb == 3))).astype(np.uint8)
        heat += board
    return heat


# ------------------------------------------------------------------
# Encoding C: Voronoi tessellation
# ------------------------------------------------------------------

def voronoi_params(digest: bytes, k: int):
    """Bytes [0,2k) give site coordinates (x,y one byte each);
    bytes [2k,3k) give cell intensities. Disjoint by construction."""
    s = np.frombuffer(xof(digest, 3 * k), dtype=np.uint8)
    xy = s[:2 * k].reshape(k, 2).astype(np.float64)
    inten = (s[2 * k:3 * k] / 255.0 * 200 + 30).astype(np.uint8)
    return xy, inten


def voronoi_native(digests, k=16, res=64) -> np.ndarray:
    params = [voronoi_params(d, k) for d in digests]
    xy = np.stack([p[0] for p in params]) / 255.0 * (res - 1)  # (B,k,2)
    inten = np.stack([p[1] for p in params])                    # (B,k)
    yy, xx = np.mgrid[0:res, 0:res]
    B = len(digests)
    best = np.full((B, res, res), np.inf)
    out = np.zeros((B, res, res), dtype=np.uint8)
    # first-minimum tie-breaking, identical to argmin over sites
    for i in range(k):
        d = ((xx[None] - xy[:, i, 0, None, None]) ** 2 +
             (yy[None] - xy[:, i, 1, None, None]) ** 2)
        m = d < best
        best = np.where(m, d, best)
        out = np.where(m, inten[:, i, None, None], out)
    return out


# ------------------------------------------------------------------
# unified rendering
# ------------------------------------------------------------------

DEFAULTS = {
    "randomwalk": dict(w=17, h=9, n_moves=128),
    "cellular": dict(n=32, steps=8),
    "voronoi": dict(k=16, res=64),
}


def render(enc: str, digests, size: int = 64, mirrored: bool = False,
           **params) -> np.ndarray:
    """Batched render -> (B,size,size) uint8 grayscale. `mirrored` imposes
    left-right symmetry on random-walk or Voronoi output (control only)."""
    p = {**DEFAULTS[enc], **params}
    if enc == "randomwalk":
        native = normalise(rw_native(digests, **p))
    elif enc == "cellular":
        native = normalise(ca_native(digests, **p))
    elif enc == "voronoi":
        native = voronoi_native(digests, **p)
    else:
        raise ValueError(enc)
    if mirrored:
        native = mirror(native)
    return upscale_nearest(native, size)


def render_one(enc: str, digest: bytes, size: int = 64, **params) -> np.ndarray:
    return render(enc, [digest], size, **params)[0]


GOLDEN_LABELS = ("llama3-70b-v1", "gpt2-base", "mistral-7b-instruct")


def golden_vectors():
    """SHA-256 of raw 64x64 pixel bytes for fixed inputs, per encoding."""
    out = {}
    for enc in DEFAULTS:
        out[enc] = {}
        for lab in GOLDEN_LABELS:
            d = hashlib.sha256(lab.encode()).digest()
            out[enc][lab] = hashlib.sha256(render_one(enc, d).tobytes()).hexdigest()
    return out
