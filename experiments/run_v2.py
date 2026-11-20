"""
Revision experiments (spec vcf-v2).

  python experiments/run_v2.py main               # main table, original protocol
  python experiments/run_v2.py scale  <variant>   # best-of-M up to 2^20
                                                  # (randomwalk, cellular, voronoi,
                                                  #  cellular_nosym)
  python experiments/run_v2.py adaptive           # hill-climbing vs random search
  python experiments/run_v2.py scalectl           # feature-scale control
  python experiments/run_v2.py sweep              # parameter sweep
  python experiments/run_v2.py symmetry           # mirror-symmetry controls

Each command writes experiments/results/v2_<name>.json. All sampling is
seeded, so every run is reproducible bit for bit.
"""

import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import vcf_v2 as V  # noqa: E402
import metrics as M  # noqa: E402

OUT = os.path.join(HERE, "results")
ENCODINGS = ("randomwalk", "cellular", "voronoi")
CHUNK = 4096


def digests(rng, n):
    return [hashlib.sha256(rng.bytes(32)).digest() for _ in range(n)]


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"v2_{name}.json")
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
    print("wrote", path, flush=True)


def pair_indices(rng, n_samples, n_pairs):
    pairs = set()
    while len(pairs) < n_pairs:
        i, j = rng.integers(0, n_samples, size=2)
        if i != j:
            pairs.add((min(i, j), max(i, j)))
    p = np.array(sorted(pairs))
    return p[:, 0], p[:, 1]


def pair_stats(imgs, ii, jj):
    s = np.concatenate([M.ssim_pairs(imgs[ii[k:k + 1000]], imgs[jj[k:k + 1000]])
                        for k in range(0, len(ii), 1000)])
    h = M.phash_bits(imgs)
    d = M.hamming(h[ii], h[jj])
    bitfreq = ((h[:, None] >> np.arange(63, -1, -1, dtype=np.uint64)) & np.uint64(1)).mean(axis=0)
    return {
        "phash_fixed_bits_95": int((np.abs(bitfreq - 0.5) > 0.45).sum()),
        "ssim_mean": float(s.mean()), "ssim_sd": float(s.std()),
        "ssim_max": float(s.max()), "ssim_p99": float(np.percentile(s, 99)),
        "phash_mean": float(d.mean()), "phash_sd": float(d.std()),
        "phash_min": int(d.min()), "phash_p1": float(np.percentile(d, 1)),
        "phash_cohen_d_vs_32": float((d.mean() - 32) / d.std()),
    }


def best_of_m(enc, targets, m, rng, size=64, ssim_limit=None, checkpoints=(),
              chunk=CHUNK, **params):
    """Each target is searched against the same stream of m independent
    candidates. Returns per-target best SSIM (max) and best pHash (min),
    plus running values at the requested checkpoints."""
    t_img = V.render(enc, targets, size, **params)
    t_h = M.phash_bits(t_img)
    best_p = np.full(len(targets), 64)
    best_s = np.full(len(targets), -1.0)
    ssim_limit = m if ssim_limit is None else ssim_limit
    trace = {}
    done = 0
    while done < m:
        b = min(chunk, m - done)
        imgs = V.render(enc, digests(rng, b), size, **params)
        h = M.phash_bits(imgs)
        dist = M.hamming(h[:, None], t_h[None, :])           # (b, T)
        best_p = np.minimum(best_p, dist.min(axis=0))
        if done < ssim_limit:
            st = M.ssim_stats(imgs)
            for k in range(len(targets)):
                best_s[k] = max(best_s[k], M.ssim_to_target(st, t_img[k]).max())
        done += b
        if done in checkpoints:
            trace[int(done)] = {
                "phash_min": int(best_p.min()), "phash_mean": float(best_p.mean()),
                "ssim_max": float(best_s.max()) if done <= ssim_limit else None,
                "ssim_mean": float(best_s.mean()) if done <= ssim_limit else None,
            }
            print(f"  {enc} M={done}: {trace[int(done)]}", flush=True)
    return best_s, best_p, trace


# ------------------------------------------------------------------

def cmd_main():
    rng = np.random.default_rng(20261119)
    res = {"spec": V.SPEC_VERSION, "protocol": {
        "samples": 5000, "pairs": 10000, "targets": 20, "M": 2000, "size": 64,
        "exact_test_samples": 100000}}
    ii, jj = pair_indices(np.random.default_rng(42), 5000, 10000)
    for enc in ENCODINGS:
        r = {}
        # exact collisions + throughput
        ds = digests(rng, 100_000)
        t = time.time()
        seen = set()
        for k in range(0, len(ds), CHUNK):
            for im in V.render(enc, ds[k:k + CHUNK]):
                seen.add(hashlib.sha256(im.tobytes()).digest())
        r["render_rate_batched"] = 100_000 / (time.time() - t)
        r["exact_unique"] = len(seen)
        t = time.time()
        for d in ds[:2000]:
            V.render_one(enc, d)
        r["render_rate_single"] = 2000 / (time.time() - t)
        imgs = V.render(enc, digests(rng, 5000))
        r.update(pair_stats(imgs, ii, jj))
        bs, bp, _ = best_of_m(enc, digests(rng, 20), 2000, rng)
        r.update({"best_ssim_max": float(bs.max()), "best_ssim_mean": float(bs.mean()),
                  "best_phash_min": int(bp.min()), "best_phash_mean": float(bp.mean())})
        res[enc] = r
        print(enc, r, flush=True)
    res["golden_sha256_of_pixels"] = V.golden_vectors()
    save("main", res)


SCALE_VARIANTS = {
    "randomwalk": ("randomwalk", {}, 1),
    "cellular": ("cellular", {}, 2),
    "voronoi": ("voronoi", {}, 3),
    "cellular_nosym": ("cellular", {"symmetric": False}, 4),
}


def cmd_scale(name):
    enc, params, seed = SCALE_VARIANTS[name]
    rng = np.random.default_rng(seed)
    m = 1 << 20
    t = time.time()
    # chunk of 2048 so that every power-of-two checkpoint is a chunk boundary
    bs, bp, trace = best_of_m(enc, digests(rng, 20), m, rng, ssim_limit=1 << 16,
                              checkpoints=tuple(1 << e for e in range(11, 21)),
                              chunk=2048, **params)
    # pHash tail: distances from 256 fresh targets to 2^20 fresh candidates
    tg = M.phash_bits(V.render(enc, digests(rng, 256), **params))
    hist = np.zeros(65, dtype=np.int64)
    uniq = set()
    n_tail = 1 << 20
    done = 0
    while done < n_tail:
        h = M.phash_bits(V.render(enc, digests(rng, CHUNK), **params))
        uniq.update(h.tolist())
        d = M.hamming(h[:, None], tg[None, :])
        hist += np.bincount(d.ravel(), minlength=65)
        done += CHUNK
    pairs = hist.sum()
    cdf = np.cumsum(hist) / pairs
    pred = {}
    for e in (11, 16, 20, 24, 28):
        mm = 2.0 ** e
        # P(best <= k) = 1 - (1 - p_k)^M ; report median and the k reached w.p. >= 0.5
        pbest = 1 - np.exp(mm * np.log1p(-np.minimum(cdf, 1 - 1e-16)))
        med = int(np.argmax(pbest >= 0.5))
        pred[f"2^{e}"] = {"median_best_phash": med,
                          "p_best_le_4": float(pbest[4]), "p_best_le_8": float(pbest[8])}
    save(f"scale_{name}", {
        "encoding": enc, "params": params, "M": m, "targets": 20, "ssim_search_limit": 1 << 16,
        "trace": trace, "final_phash_min": int(bp.min()),
        "final_phash_per_target": bp.tolist(), "final_ssim_max_at_2^16": float(bs.max()),
        "tail": {"targets": 256, "candidates": n_tail, "pairs": int(pairs),
                 "hist": hist.tolist(), "cdf_le_k": cdf[:21].tolist(),
                 "distinct_phash_values": len(uniq),
                 "extrapolated_best_of_M_pooled": pred},
        "seconds": time.time() - t})


def cmd_adaptive():
    """Hill-climbing over a 16-byte mutable region of a fixed artifact preimage
    vs independent random candidates, equal budget, pHash on the cellular
    encoding (the family closest to the threshold)."""
    enc = "cellular"
    rng = np.random.default_rng(7)
    budget, n_t = 1 << 13, 20
    base = rng.bytes(4096)                    # stand-in for artifact bytes
    targets = digests(rng, n_t)
    t_h = M.phash_bits(V.render(enc, targets))
    out = {"encoding": enc, "budget": budget, "targets": n_t, "random": [], "hill": []}
    for k in range(n_t):
        # random search
        h = M.phash_bits(V.render(enc, digests(rng, budget)))
        out["random"].append(int(M.hamming(h, t_h[k]).min()))
        # hill climb: mutate one byte of the pad, keep if not worse
        pad = bytearray(rng.bytes(16))
        cur = M.hamming(M.phash_bits(V.render(enc, [hashlib.sha256(base + pad).digest()])), t_h[k])[0]
        best = cur
        used = 1
        while used < budget:
            props = []
            for _ in range(256):
                p = bytearray(pad)
                p[rng.integers(16)] = rng.integers(256)
                props.append(p)
            hs = M.phash_bits(V.render(enc, [hashlib.sha256(base + p).digest() for p in props]))
            ds = M.hamming(hs, t_h[k])
            used += len(props)
            j = int(ds.argmin())
            if ds[j] <= cur:
                cur, pad = int(ds[j]), props[j]
            best = min(best, int(ds.min()))
        out["hill"].append(int(best))
        print(k, out["random"][-1], out["hill"][-1], flush=True)
    r, hc = np.array(out["random"]), np.array(out["hill"])
    out["summary"] = {"random_mean": float(r.mean()), "random_min": int(r.min()),
                      "hill_mean": float(hc.mean()), "hill_min": int(hc.min())}
    save("adaptive", out)


def _common_scale(imgs, s=16, size=64):
    """Area-average to s x s, then nearest-upscale: caps every encoding at the
    same maximum spatial frequency."""
    small = np.stack([np.asarray(Image.fromarray(im).resize((s, s), Image.Resampling.BOX))
                      for im in imgs])
    return V.upscale_nearest(small, size)


def _downsample(imgs, f):
    s = imgs.shape[1] // f
    return np.stack([np.asarray(Image.fromarray(im).resize((s, s), Image.Resampling.BOX))
                     for im in imgs])


def cmd_scalectl():
    rng = np.random.default_rng(11)
    ii, jj = pair_indices(np.random.default_rng(42), 5000, 10000)
    res = {}
    for enc in ENCODINGS:
        ds = digests(rng, 5000)
        base = V.render(enc, ds, 64)
        conds = {
            "native_64": base,
            "render_32": V.render(enc, ds, 32),
            "render_128": V.render(enc, ds, 128),
            "common_16_to_64": _common_scale(base, 16),
            "common_8_to_64": _common_scale(base, 8),
        }
        r = {}
        for c, im in conds.items():
            r[c] = pair_stats(im, ii, jj)
        # multi-scale SSIM: product of SSIM at full, 1/2 and 1/4 resolution
        ms = np.ones(len(ii))
        for f in (1, 2, 4):
            im = base if f == 1 else _downsample(base, f)
            ms *= np.clip(np.concatenate([M.ssim_pairs(im[ii[k:k + 1000]], im[jj[k:k + 1000]])
                                          for k in range(0, len(ii), 1000)]), 0, None)
        r["ms_ssim_3scale"] = {"mean": float(ms.mean()), "max": float(ms.max())}
        res[enc] = r
        print(enc, json.dumps(r)[:400], flush=True)
    rank = {}
    for c in ("native_64", "render_32", "render_128", "common_16_to_64", "common_8_to_64"):
        s = sorted(ENCODINGS, key=lambda e: res[e][c]["ssim_mean"])          # low = better
        p = sorted(ENCODINGS, key=lambda e: -res[e][c]["phash_mean"])        # high = better
        rank[c] = {"ssim_best_to_worst": s, "phash_best_to_worst": p}
    rank["ms_ssim_3scale"] = {"best_to_worst": sorted(ENCODINGS, key=lambda e: res[e]["ms_ssim_3scale"]["mean"])}
    res["rankings"] = rank
    save("scalectl", res)


SWEEP = (
    [("randomwalk", dict(w=17, h=9, n_moves=128)),
     ("randomwalk", dict(w=17, h=9, n_moves=512)),
     ("randomwalk", dict(w=33, h=17, n_moves=512))] +
    [("cellular", dict(n=n, steps=s)) for n in (16, 32, 64) for s in (0, 4, 8, 16)] +
    [("voronoi", dict(k=k)) for k in (8, 16, 32, 64)]
)


SYMMETRY_SWEEP = (
    [("cellular", dict(n=32, steps=8, symmetric=True))] +
    [("cellular", dict(n=n, steps=s, symmetric=False)) for n in (16, 32, 64) for s in (0, 8)] +
    [("randomwalk", dict(mirrored=True)), ("voronoi", dict(mirrored=True))]
)


def cmd_sweep(configs=SWEEP, seed=13, name="sweep"):
    rng = np.random.default_rng(seed)
    ii, jj = pair_indices(np.random.default_rng(42), 5000, 10000)
    rows = []
    for enc, p in configs:
        imgs = V.render(enc, digests(rng, 5000), **p)
        r = {"encoding": enc, "params": p}
        r.update(pair_stats(imgs, ii, jj))
        bs, bp, _ = best_of_m(enc, digests(rng, 20), 2048, rng, **p)
        r.update({"best_ssim_max": float(bs.max()), "best_phash_min": int(bp.min()),
                  "best_phash_mean": float(bp.mean())})
        rows.append(r)
        print(enc, p, {k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()
                       if k in ("ssim_mean", "phash_mean", "phash_min", "best_phash_min",
                                "best_ssim_max")}, flush=True)
    save(name, {"pairs": 10000, "samples": 5000, "best_of_M": 2048, "targets": 20,
                   "rows": rows})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "scale":
        cmd_scale(sys.argv[2])
    else:
        {"main": cmd_main, "adaptive": cmd_adaptive,
         "scalectl": cmd_scalectl, "sweep": cmd_sweep,
         "symmetry": lambda: cmd_sweep(SYMMETRY_SWEEP, 17, "symmetry")}[cmd]()
