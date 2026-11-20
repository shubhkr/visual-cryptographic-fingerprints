"""
Generate stimuli for the human comparison study.

For each representation we fix 48 target digests and, for every target,
search the same budget of M = 2^16 random candidate digests. We keep:

  * images:  the candidate closest to the target under pHash and, separately,
             under SSIM ("phash_hard", "ssim_hard"), plus one random mismatch
  * hex:     the candidate whose hex string shares the most leading plus
             trailing characters with the target ("hex_hard"), plus one
             random mismatch

All digests are derived from SHA-256 of fixed namespaces, so the stimulus set
is reproducible byte for byte. Images are written as 64x64 greyscale PNGs; the
experiment scales them with nearest-neighbour sampling for display.

  python study/make_stimuli.py --rep life_mirrored --out docs
  python study/make_stimuli.py --rep hex --out docs
  python study/make_stimuli.py --manifest --out docs   # after all reps
"""

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import metrics as M  # noqa: E402
import vcf_v2 as V  # noqa: E402

STUDY_VERSION = "vcf-study-v1"
N_TARGETS = 48
BUDGET = 1 << 16
CHUNK = 2048
SIZE = 64

IMAGE_REPS = {
    "walk": ("randomwalk", {}),
    "life_mirrored": ("cellular", {}),
    "life_unmirrored": ("cellular", {"symmetric": False}),
    "voronoi": ("voronoi", {}),
}
ALL_REPS = ("hex",) + tuple(IMAGE_REPS)


def digest(kind: str, rep: str, i: int) -> bytes:
    return hashlib.sha256(f"{STUDY_VERSION}\0{kind}\0{rep}\0".encode() + i.to_bytes(8, "big")).digest()


def edge_match(a: str, b: str) -> int:
    """Leading plus trailing hex characters two strings share."""
    p = 0
    while p < len(a) and a[p] == b[p]:
        p += 1
    s = 0
    while s < len(a) - p and a[-1 - s] == b[-1 - s]:
        s += 1
    return p + s


def save_png(rep, d: bytes, img: np.ndarray, out: str) -> str:
    rel = f"stimuli/{rep}/{d.hex()[:20]}.png"
    path = os.path.join(out, rel)
    if not os.path.exists(path):
        Image.fromarray(img, mode="L").save(path, optimize=True)
    return rel


def image_rep(rep: str, out: str) -> dict:
    enc, params = IMAGE_REPS[rep]
    os.makedirs(os.path.join(out, "stimuli", rep), exist_ok=True)
    targets = [digest("target", rep, i) for i in range(N_TARGETS)]
    t_img = V.render(enc, targets, SIZE, **params)
    t_h = M.phash_bits(t_img)
    best_p = np.full(N_TARGETS, 65)
    best_p_idx = np.zeros(N_TARGETS, dtype=np.int64)
    best_s = np.full(N_TARGETS, -2.0)
    best_s_idx = np.zeros(N_TARGETS, dtype=np.int64)
    t0 = time.time()
    for start in range(0, BUDGET, CHUNK):
        cands = [digest("candidate", rep, start + j) for j in range(CHUNK)]
        imgs = V.render(enc, cands, SIZE, **params)
        dist = M.hamming(M.phash_bits(imgs)[:, None], t_h[None, :])        # (chunk, T)
        j = dist.argmin(axis=0)
        better = dist[j, np.arange(N_TARGETS)] < best_p
        best_p = np.where(better, dist[j, np.arange(N_TARGETS)], best_p)
        best_p_idx = np.where(better, start + j, best_p_idx)
        st = M.ssim_stats(imgs)
        for k in range(N_TARGETS):
            s = M.ssim_to_target(st, t_img[k])
            jj = int(s.argmax())
            if s[jj] > best_s[k]:
                best_s[k], best_s_idx[k] = float(s[jj]), start + jj
        print(f"  {rep}: {start + CHUNK}/{BUDGET} ({time.time() - t0:.0f}s)", flush=True)

    def pair_metrics(k, d):
        img = V.render(enc, [d], SIZE, **params)
        return img[0], {
            "digest": d.hex(),
            "phash": int(M.hamming(M.phash_bits(img), t_h[k])[0]),
            "ssim": round(float(M.ssim_pairs(img, t_img[k:k + 1])[0]), 4),
        }

    items = []
    for k, t in enumerate(targets):
        item = {"target": t.hex(), "target_img": save_png(rep, t, t_img[k], out)}
        for role, d in (("random", digest("random", rep, k)),
                        ("phash_hard", digest("candidate", rep, int(best_p_idx[k]))),
                        ("ssim_hard", digest("candidate", rep, int(best_s_idx[k])))):
            img, m = pair_metrics(k, d)
            m["img"] = save_png(rep, d, img, out)
            item[role] = m
        items.append(item)
    return {"kind": "image", "encoding": enc, "params": params, "items": items}


def hex_rep(out: str) -> dict:
    targets = [digest("target", "hex", i).hex() for i in range(N_TARGETS)]
    best = [(-1, None)] * N_TARGETS
    for c in range(BUDGET):
        h = digest("candidate", "hex", c).hex()
        for k, t in enumerate(targets):
            m = edge_match(t, h)
            if m > best[k][0]:
                best[k] = (m, h)
    items = []
    for k, t in enumerate(targets):
        r = digest("random", "hex", k).hex()
        items.append({"target": t,
                      "random": {"digest": r, "edge_match": edge_match(t, r)},
                      "hex_hard": {"digest": best[k][1], "edge_match": best[k][0]}})
    return {"kind": "hex", "items": items}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", choices=ALL_REPS)
    ap.add_argument("--manifest", action="store_true", help="combine per-rep parts into stimuli.js")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    parts = os.path.join(a.out, "stimuli", "parts")
    os.makedirs(parts, exist_ok=True)
    if a.rep:
        data = hex_rep(a.out) if a.rep == "hex" else image_rep(a.rep, a.out)
        with open(os.path.join(parts, f"{a.rep}.json"), "w") as f:
            json.dump(data, f, indent=1)
        print("wrote", a.rep)
    if a.manifest:
        reps = {}
        for r in ALL_REPS:
            with open(os.path.join(parts, f"{r}.json")) as f:
                reps[r] = json.load(f)
        manifest = {"version": STUDY_VERSION, "budget": BUDGET, "n_targets": N_TARGETS,
                    "image_size": SIZE, "reps": reps}
        with open(os.path.join(a.out, "stimuli.js"), "w") as f:
            f.write("// Generated by study/make_stimuli.py. Do not edit.\n")
            f.write("window.STIMULI = " + json.dumps(manifest, separators=(",", ":")) + ";\n")
        print("wrote", os.path.join(a.out, "stimuli.js"))


if __name__ == "__main__":
    main()
