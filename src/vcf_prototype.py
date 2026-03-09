"""
Visual Cryptographic Fingerprint (VCF) Prototype
Implements three encoding families from SHA-256 digests:
  A) Random-walk grid (drunken bishop)
  B) Cellular automata (LifeHash-like)
  C) Voronoi tessellation
Plus automated collision and near-collision testing.
"""

import hashlib
import os
import struct
import time
import json
from collections import Counter

import numpy as np
from PIL import Image
from scipy.spatial import Voronoi
from skimage.metrics import structural_similarity as ssim
import imagehash


# ============================================================
# Encoding A: Random-Walk Grid (Drunken Bishop)
# ============================================================

GRID_W, GRID_H = 17, 9
CHAR_RAMP = " .o+=*BOX@%&#/^SE"

def randomwalk_encode(digest_bytes: bytes) -> np.ndarray:
    """Drunken bishop walk on 17x9 grid from SHA-256 digest.
    Returns visit-count matrix (H x W) as uint8."""
    grid = np.zeros((GRID_H, GRID_W), dtype=np.int32)
    x, y = GRID_W // 2, GRID_H // 2
    for byte in digest_bytes:
        for shift in (0, 2, 4, 6):
            pair = (byte >> shift) & 0x03
            dx = 1 if (pair & 1) else -1
            dy = 1 if (pair & 2) else -1
            x = max(0, min(GRID_W - 1, x + dx))
            y = max(0, min(GRID_H - 1, y + dy))
            grid[y, x] += 1
    return grid


def randomwalk_to_ascii(grid: np.ndarray, digest_bytes: bytes) -> str:
    """Render visit-count grid as ASCII art string."""
    sx, sy = GRID_W // 2, GRID_H // 2
    lines = ["+--[SHA256]--------+"]
    for r in range(GRID_H):
        row = "|"
        for c in range(GRID_W):
            if r == sy and c == sx:
                row += "S"
            else:
                idx = min(grid[r, c], len(CHAR_RAMP) - 1)
                row += CHAR_RAMP[idx]
        row += "|"
        lines.append(row)
    lines.append("+------------------+")
    return "\n".join(lines)


def randomwalk_to_image(grid: np.ndarray, size: int = 64) -> np.ndarray:
    """Render visit-count grid as grayscale image array (size x size)."""
    max_val = max(grid.max(), 1)
    normed = (grid.astype(np.float64) / max_val * 255).astype(np.uint8)
    img = Image.fromarray(normed, mode='L')
    img = img.resize((size, size), Image.NEAREST)
    return np.array(img)


# ============================================================
# Encoding B: Cellular Automata (LifeHash-like)
# ============================================================

CA_SIZE = 32
CA_STEPS = 8

def ca_encode(digest_bytes: bytes, grid_size: int = CA_SIZE,
              steps: int = CA_STEPS) -> np.ndarray:
    """Seed a Game-of-Life CA with digest bits, evolve, return final state.
    Returns accumulated heat map (grid_size x grid_size) as uint8."""
    bits = np.unpackbits(np.frombuffer(digest_bytes, dtype=np.uint8))
    n_cells = grid_size * grid_size
    seed = np.zeros(n_cells, dtype=np.uint8)
    seed[:len(bits)] = bits[:n_cells]
    np.random.seed(int.from_bytes(digest_bytes[:4], 'big'))
    if len(bits) < n_cells:
        extra = np.random.randint(0, 2, n_cells - len(bits), dtype=np.uint8)
        seed[len(bits):] = extra
    board = seed.reshape(grid_size, grid_size)
    # enforce horizontal symmetry for recognizability
    half = grid_size // 2
    board[:, half:] = np.fliplr(board[:, :half + (grid_size % 2)])

    heat = board.astype(np.int32).copy()
    for _ in range(steps):
        padded = np.pad(board, 1, mode='wrap')
        neighbors = sum(
            padded[r:r + grid_size, c:c + grid_size]
            for r in range(3) for c in range(3)
        ) - board
        new_board = np.where(
            (board == 1) & ((neighbors == 2) | (neighbors == 3)), 1,
            np.where((board == 0) & (neighbors == 3), 1, 0)
        ).astype(np.uint8)
        board = new_board
        heat += board
    return heat


def ca_to_image(heat: np.ndarray, size: int = 64) -> np.ndarray:
    """Render CA heat map as grayscale image."""
    max_val = max(heat.max(), 1)
    normed = (heat.astype(np.float64) / max_val * 255).astype(np.uint8)
    img = Image.fromarray(normed, mode='L')
    img = img.resize((size, size), Image.NEAREST)
    return np.array(img)


# ============================================================
# Encoding C: Voronoi Tessellation
# ============================================================

VORONOI_K = 16
VORONOI_RES = 64

def voronoi_encode(digest_bytes: bytes, k: int = VORONOI_K,
                   res: int = VORONOI_RES) -> np.ndarray:
    """Derive K site points from digest, render Voronoi cells as labeled image.
    Returns label matrix (res x res) as uint8."""
    coords = []
    for i in range(k):
        bx = digest_bytes[i * 2 % 32]
        by = digest_bytes[(i * 2 + 1) % 32]
        coords.append((bx / 255.0 * (res - 1), by / 255.0 * (res - 1)))
    coords = np.array(coords)
    yy, xx = np.mgrid[0:res, 0:res]
    dists = np.stack([
        (xx - cx) ** 2 + (yy - cy) ** 2 for cx, cy in coords
    ])
    labels = np.argmin(dists, axis=0).astype(np.uint8)
    return labels


def voronoi_to_image(labels: np.ndarray, digest_bytes: bytes,
                     size: int = 64) -> np.ndarray:
    """Render Voronoi label map as grayscale image with distinct cell values."""
    k = labels.max() + 1
    lut = np.zeros(k, dtype=np.uint8)
    for i in range(k):
        lut[i] = int((digest_bytes[(i * 3 + 16) % 32] / 255.0) * 200 + 30)
    mapped = lut[labels]
    img = Image.fromarray(mapped, mode='L')
    img = img.resize((size, size), Image.NEAREST)
    return np.array(img)


# ============================================================
# Unified encode/render
# ============================================================

def digest_from_hex(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def random_digest() -> bytes:
    return hashlib.sha256(os.urandom(32)).digest()


def encode_all(digest_bytes: bytes, img_size: int = 64):
    """Return dict of encoding_name -> grayscale image array."""
    rw_grid = randomwalk_encode(digest_bytes)
    ca_heat = ca_encode(digest_bytes)
    voro_labels = voronoi_encode(digest_bytes)
    return {
        'randomwalk': randomwalk_to_image(rw_grid, img_size),
        'cellular': ca_to_image(ca_heat, img_size),
        'voronoi': voronoi_to_image(voro_labels, digest_bytes, img_size),
    }


# ============================================================
# Collision Testing
# ============================================================

def image_fingerprint(img: np.ndarray) -> str:
    """SHA-256 of raw pixel bytes for exact collision detection."""
    return hashlib.sha256(img.tobytes()).hexdigest()


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    return ssim(img1, img2, data_range=255)


def compute_phash_distance(img1: np.ndarray, img2: np.ndarray) -> int:
    h1 = imagehash.phash(Image.fromarray(img1, mode='L'))
    h2 = imagehash.phash(Image.fromarray(img2, mode='L'))
    return h1 - h2


def run_collision_test(n_samples: int = 100_000, img_size: int = 64):
    """Run full collision testing suite. Returns results dict."""
    print(f"\n{'='*60}")
    print(f"VCF Collision Testing: {n_samples:,} samples, {img_size}x{img_size} images")
    print(f"{'='*60}")

    encodings = ['randomwalk', 'cellular', 'voronoi']
    results = {}

    # Phase 1: Generate all digests and renderings
    print(f"\n[Phase 1] Generating {n_samples:,} random SHA-256 digests...")
    t0 = time.time()
    digests = [random_digest() for _ in range(n_samples)]
    print(f"  Digests generated in {time.time()-t0:.1f}s")

    all_images = {enc: [] for enc in encodings}
    all_fingerprints = {enc: [] for enc in encodings}

    for enc_name in encodings:
        print(f"\n[Phase 1] Rendering {enc_name}...")
        t0 = time.time()
        for d in digests:
            if enc_name == 'randomwalk':
                grid = randomwalk_encode(d)
                img = randomwalk_to_image(grid, img_size)
            elif enc_name == 'cellular':
                heat = ca_encode(d)
                img = ca_to_image(heat, img_size)
            else:
                labels = voronoi_encode(d)
                img = voronoi_to_image(labels, d, img_size)
            all_images[enc_name].append(img)
            all_fingerprints[enc_name].append(image_fingerprint(img))
        elapsed = time.time() - t0
        print(f"  {enc_name}: {n_samples:,} renders in {elapsed:.1f}s "
              f"({n_samples/elapsed:.0f} renders/sec)")

    # Phase 2: Exact collision detection
    print(f"\n[Phase 2] Exact collision detection...")
    for enc_name in encodings:
        fps = all_fingerprints[enc_name]
        unique = len(set(fps))
        collisions = n_samples - unique
        results[f'{enc_name}_exact_collisions'] = collisions
        results[f'{enc_name}_unique_outputs'] = unique
        print(f"  {enc_name}: {unique:,} unique / {n_samples:,} total "
              f"-> {collisions} exact collisions")

    # Phase 3: Near-collision analysis (random pair sampling)
    n_pairs = min(10_000, n_samples * (n_samples - 1) // 2)
    print(f"\n[Phase 3] Near-collision analysis ({n_pairs:,} random pairs)...")

    rng = np.random.default_rng(42)
    pair_indices = set()
    while len(pair_indices) < n_pairs:
        i, j = rng.integers(0, n_samples, size=2)
        if i != j:
            pair_indices.add((min(i, j), max(i, j)))
    pair_indices = list(pair_indices)[:n_pairs]

    for enc_name in encodings:
        print(f"\n  Computing SSIM + pHash for {enc_name}...")
        t0 = time.time()
        ssim_vals = []
        phash_dists = []
        imgs = all_images[enc_name]
        for idx, (i, j) in enumerate(pair_indices):
            sv = compute_ssim(imgs[i], imgs[j])
            pd = compute_phash_distance(imgs[i], imgs[j])
            ssim_vals.append(sv)
            phash_dists.append(pd)
            if (idx + 1) % 10000 == 0:
                print(f"    {idx+1:,}/{n_pairs:,} pairs...")
        elapsed = time.time() - t0

        ssim_arr = np.array(ssim_vals)
        phash_arr = np.array(phash_dists)

        results[f'{enc_name}_ssim_mean'] = float(np.mean(ssim_arr))
        results[f'{enc_name}_ssim_std'] = float(np.std(ssim_arr))
        results[f'{enc_name}_ssim_max'] = float(np.max(ssim_arr))
        results[f'{enc_name}_ssim_p99'] = float(np.percentile(ssim_arr, 99))
        results[f'{enc_name}_ssim_p999'] = float(np.percentile(ssim_arr, 99.9))
        results[f'{enc_name}_phash_mean'] = float(np.mean(phash_arr))
        results[f'{enc_name}_phash_std'] = float(np.std(phash_arr))
        results[f'{enc_name}_phash_min'] = int(np.min(phash_arr))
        results[f'{enc_name}_phash_p1'] = float(np.percentile(phash_arr, 1))

        print(f"  {enc_name} ({elapsed:.1f}s):")
        print(f"    SSIM:  mean={np.mean(ssim_arr):.4f} std={np.std(ssim_arr):.4f} "
              f"max={np.max(ssim_arr):.4f} p99={np.percentile(ssim_arr, 99):.4f} "
              f"p99.9={np.percentile(ssim_arr, 99.9):.4f}")
        print(f"    pHash: mean={np.mean(phash_arr):.1f} std={np.std(phash_arr):.1f} "
              f"min={np.min(phash_arr)} p1={np.percentile(phash_arr, 1):.1f}")

    # Phase 4: Targeted near-preimage mining
    n_targets = 20
    n_candidates = 2_000
    print(f"\n[Phase 4] Targeted mining: {n_targets} targets x "
          f"{n_candidates:,} candidates...")

    for enc_name in encodings:
        print(f"\n  Mining for {enc_name}...")
        t0 = time.time()
        best_ssims = []
        best_phash = []
        for t_idx in range(n_targets):
            target_img = all_images[enc_name][t_idx]
            max_ssim_val = -1.0
            min_phash_val = 999
            for _ in range(n_candidates):
                cand_digest = random_digest()
                if enc_name == 'randomwalk':
                    cand_img = randomwalk_to_image(
                        randomwalk_encode(cand_digest), img_size)
                elif enc_name == 'cellular':
                    cand_img = ca_to_image(ca_encode(cand_digest), img_size)
                else:
                    cand_img = voronoi_to_image(
                        voronoi_encode(cand_digest), cand_digest, img_size)
                sv = compute_ssim(target_img, cand_img)
                pd = compute_phash_distance(target_img, cand_img)
                if sv > max_ssim_val:
                    max_ssim_val = sv
                if pd < min_phash_val:
                    min_phash_val = pd
            best_ssims.append(max_ssim_val)
            best_phash.append(min_phash_val)
            if (t_idx + 1) % 20 == 0:
                print(f"    {t_idx+1}/{n_targets} targets done...")
        elapsed = time.time() - t0

        bs = np.array(best_ssims)
        bp = np.array(best_phash)
        results[f'{enc_name}_mining_ssim_mean'] = float(np.mean(bs))
        results[f'{enc_name}_mining_ssim_max'] = float(np.max(bs))
        results[f'{enc_name}_mining_phash_mean'] = float(np.mean(bp))
        results[f'{enc_name}_mining_phash_min'] = int(np.min(bp))
        results[f'{enc_name}_mining_budget'] = n_candidates

        print(f"  {enc_name} ({elapsed:.1f}s):")
        print(f"    Best SSIM found:  mean={np.mean(bs):.4f} max={np.max(bs):.4f}")
        print(f"    Best pHash found: mean={np.mean(bp):.1f} min={np.min(bp)}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for enc_name in encodings:
        print(f"\n{enc_name.upper()}:")
        print(f"  Exact collisions: {results[f'{enc_name}_exact_collisions']} "
              f"(out of {n_samples:,})")
        print(f"  Random pairs SSIM: "
              f"mean={results[f'{enc_name}_ssim_mean']:.4f} "
              f"max={results[f'{enc_name}_ssim_max']:.4f}")
        print(f"  Random pairs pHash dist: "
              f"mean={results[f'{enc_name}_phash_mean']:.1f} "
              f"min={results[f'{enc_name}_phash_min']}")
        print(f"  Mining ({n_candidates:,} candidates): "
              f"best SSIM={results[f'{enc_name}_mining_ssim_max']:.4f} "
              f"best pHash={results[f'{enc_name}_mining_phash_min']}")

    return results


def generate_examples(output_dir: str, n: int = 6):
    """Generate example VCF images for the paper."""
    os.makedirs(output_dir, exist_ok=True)
    sample_labels = [
        "llama3-70b-v1",
        "llama3-70b-v1-TAMPERED",
        "gpt2-base",
        "dataset-imagenet-2024",
        "mistral-7b-instruct",
        "phi3-mini-4k",
    ]
    for label in sample_labels:
        digest = hashlib.sha256(label.encode()).digest()
        hex_str = digest.hex()[:16]

        rw_grid = randomwalk_encode(digest)
        ascii_art = randomwalk_to_ascii(rw_grid, digest)
        with open(os.path.join(output_dir, f"rw_{label}.txt"), 'w') as f:
            f.write(f"# {label}\n# SHA256: {digest.hex()}\n\n{ascii_art}\n")

        imgs = encode_all(digest, img_size=128)
        for enc_name, img_arr in imgs.items():
            img = Image.fromarray(img_arr, mode='L')
            img.save(os.path.join(output_dir, f"{enc_name}_{label}.png"))

    print(f"Examples saved to {output_dir}/")
    return sample_labels


def run_fast_exact_test(n_samples: int = 100_000, img_size: int = 64):
    """Fast test: only exact collision detection on N samples (no SSIM)."""
    print(f"\n{'='*60}")
    print(f"EXACT COLLISION TEST: {n_samples:,} samples")
    print(f"{'='*60}")

    encodings_funcs = {
        'randomwalk': lambda d: randomwalk_to_image(randomwalk_encode(d), img_size),
        'cellular': lambda d: ca_to_image(ca_encode(d), img_size),
        'voronoi': lambda d: voronoi_to_image(voronoi_encode(d), d, img_size),
    }
    results = {}
    digests = [random_digest() for _ in range(n_samples)]

    for enc_name, enc_fn in encodings_funcs.items():
        print(f"\n  Rendering {enc_name}...", flush=True)
        t0 = time.time()
        fingerprints = set()
        collisions = 0
        for i, d in enumerate(digests):
            img = enc_fn(d)
            fp = hashlib.sha256(img.tobytes()).hexdigest()
            if fp in fingerprints:
                collisions += 1
            fingerprints.add(fp)
            if (i + 1) % 20000 == 0:
                print(f"    {i+1:,}/{n_samples:,}...", flush=True)
        elapsed = time.time() - t0
        unique = len(fingerprints)
        results[f'{enc_name}_exact_collisions'] = collisions
        results[f'{enc_name}_unique'] = unique
        results[f'{enc_name}_render_rate'] = n_samples / elapsed
        print(f"  {enc_name}: {unique:,} unique / {n_samples:,} total "
              f"({collisions} collisions) [{elapsed:.1f}s, "
              f"{n_samples/elapsed:.0f}/s]", flush=True)

    return results


if __name__ == '__main__':
    import sys

    out_dir = os.path.join(os.path.dirname(__file__), "vcf_outputs")
    os.makedirs(out_dir, exist_ok=True)

    # Step 1: Generate example visualizations
    print("Generating example visualizations...", flush=True)
    labels = generate_examples(os.path.join(out_dir, "examples"))

    # Step 2: Fast exact collision test on 100K samples
    exact_results = run_fast_exact_test(n_samples=100_000, img_size=64)

    # Step 3: Smaller similarity test (5K pairs + 20 targets x 2K candidates)
    print("\nRunning similarity analysis (reduced scale)...", flush=True)
    sim_results = run_collision_test(n_samples=5_000, img_size=64)

    all_results = {**exact_results, **sim_results}
    results_path = os.path.join(out_dir, "collision_results.json")
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll results saved to {results_path}", flush=True)
