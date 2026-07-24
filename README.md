# Visual Cryptographic Fingerprints for AI Supply-Chain Identity

Reference implementation and experimental artifacts for a study of visual hash
encodings as a human-facing identity layer for AI supply-chain provenance.

> **Status:** the accompanying paper is under peer review. Paper source and PDF
> will be published here after notification.

## Overview

Visual Cryptographic Fingerprints (VCFs) are deterministic images derived from
cryptographic digests of signed AI artifact bundles. They are intended as a
human-recognizable identity layer atop machine-verifiable provenance
infrastructure (Sigstore, SLSA, in-toto, AIBOMs), reducing human error at
deployment gates, model card review, and incident triage.

This repository contains:

- A **reference prototype** implementing three visual hash encoding families from SHA-256 digests
- An **automated collision and near-collision measurement** framework
- **Raw experimental results**
- **Example visual fingerprints** for sample AI model identifiers

## Headline result: the two standard similarity metrics disagree

This is a **negative result**, and it is the main finding.

Measured against the two automated similarity metrics that dominate the visual
fingerprint literature — SSIM and perceptual hashing (pHash) — the three encoding
families rank in **opposite orders**:

| Metric | Ranking (best → worst separation) |
| ------ | --------------------------------- |
| SSIM   | Cellular → Random-walk → Voronoi  |
| pHash  | Voronoi → Random-walk → **Cellular (fails)** |

| Metric                          | Random-walk | Cellular    | Voronoi     |
| ------------------------------- | ----------- | ----------- | ----------- |
| Exact collisions (N=100K)       | 0           | 0           | 0           |
| Render rate                     | 14,769/s    | 3,446/s     | 3,337/s     |
| Random-pair SSIM (mean / max)   | 0.18 / 0.68 | 0.02 / 0.16 | 0.22 / 0.48 |
| Random-pair pHash (mean / min)  | 31.4 / 12   | **15.3 / 5**| 31.5 / 18   |
| Best-of-M SSIM (M=2,000)        | 0.72        | 0.19        | 0.45        |
| Best-of-M pHash (M=2,000)       | 12          | **4**       | 16          |

**Reading the pHash row is essential.** For a 64-bit perceptual hash, two
*ideally uncorrelated* outputs sit at expected Hamming distance 32. Random-walk
(31.4) and Voronoi (31.5) are statistically indistinguishable from that ideal.
Cellular automata average **15.3** — less than half the expected radius — meaning
the whole family occupies a compact subregion of perceptual-hash space. Its
closest random pair sits at distance 5, and a 2,000-candidate search reaches **4**,
inside the conventional "perceptually similar" threshold. Neither other encoding
comes within a factor of three of that threshold at the same budget.

**Why the metrics diverge.** A Game-of-Life board seeded densely and evolved 8
steps collapses toward sparse debris, so the rendered heat maps are low-variance
images of scattered bright cells on a mostly dark field. SSIM compares local
means, variances, and covariance in a sliding window; on two such images the
windows are near-constant and the sparse features rarely overlap, so SSIM returns
approximately zero. But SSIM ≈ 0 means "linearly uncorrelated," which is also what
you get comparing two different images of almost nothing. pHash thresholds a
low-frequency DCT, discarding exactly the fine detail SSIM keys on and retaining
the coarse structure a human sees at a glance — and it reports that all cellular
outputs look alike, because they do.

**Conclusion: none of the three families is deployment-ready**, and single-metric
validation of visual fingerprint schemes is unsound.

## Repository Structure

```
visual-cryptographic-fingerprints/
├── README.md
├── LICENSE
├── requirements.txt
├── src/
│   └── vcf_prototype.py           # Three encoding implementations + measurement framework
├── experiments/
│   ├── run_experiments.sh         # One-command reproduction of all results
│   └── results/
│       └── collision_results.json # Raw experimental data
└── examples/
    ├── *.png                      # Generated visual fingerprints
    └── *.txt                      # ASCII randomart outputs
```

## Quick Start

```bash
git clone https://github.com/shubhkr/visual-cryptographic-fingerprints.git
cd visual-cryptographic-fingerprints
pip install -r requirements.txt
python src/vcf_prototype.py
```

## Encoding Families

### A. Random-Walk Grid (Drunken Bishop)

Terminal-friendly ASCII art. Implements the OpenSSH randomart algorithm adapted
for SHA-256 (17×9 grid, 128 diagonal moves). `S` marks the start cell, `E` the
end cell.

```
  llama3-70b-v1         llama3-70b-v1
    (original)            (tampered)
+----[SHA256]-----+  +----[SHA256]-----+
|+=+=. .          |  |.o***.o.         |
|B*=oo*..         |  | o+=.=o. .       |
|.**=*oo o . .    |  |.+..+o o+ .      |
|.E.o+o o . . .   |  |..o o+.o.E       |
|. . . . S   .    |  |  o.o o S .      |
|   o.  = . .     |  | + . + . . +     |
|  ....+   .      |  |  = . = o = .    |
|...  ..o .       |  | . . + o o .     |
|=.     .o        |  |  ..o...o        |
+-----------------+  +-----------------+
```

### B. Cellular Automata (LifeHash-like)

GUI-friendly grayscale images. A 32×32 Game-of-Life grid seeded from digest bits,
evolved 8 steps with horizontal symmetry.

> **Known defect.** The prototype seeds 768 of its 1,024 cells from NumPy's
> pseudorandom generator keyed on the first four digest bytes, rather than from
> the digest directly. This is adequate for the measurements reported here, but
> it means the encoding is **not reimplementable across languages** and is not
> byte-level deterministic. A specification must derive the full board from an
> extendable-output function such as SHAKE-256.

### C. Voronoi Tessellation

Dashboard-friendly region maps. 16 site points derived from the digest, Voronoi
cells with deterministic intensity mapping.

## Reproducing Results

```bash
bash experiments/run_experiments.sh    # full reproduction, ~3 minutes
```

The measurement suite runs:

1. **Exact collision test:** 100,000 random SHA-256 digests per encoding
2. **Near-collision analysis:** 10,000 random pairs (from 5,000 samples) with SSIM and pHash
3. **Best-of-M search:** 20 targets × 2,000 candidates per encoding

See `experiments/results/collision_results.json` for the full data.

### Caveats on the measurements

- **The best-of-M search is non-adaptive.** Candidates are drawn independently and
  uniformly, so it estimates the upper tail of the random-pair distribution, not
  the reach of an optimizing adversary. A real attacker with a malleable preimage
  can hill-climb and will do better at equal budget. Treat these numbers as loose
  **lower bounds** on attacker capability.
- **M = 2,000 is far below realistic attacker budgets** (2²⁰–2²⁸).
- **Feature scale is a confound.** The encodings render at 17×9, 32×32, and 64×64
  natively before nearest-neighbour upscaling to 64×64, giving effective feature
  sizes of ~4×7, 2×2, and 1×1 pixels. SSIM uses a fixed window, so part of the
  measured difference between encodings reflects spatial frequency rather than
  collision resistance.
- **No textual baseline** (hex, Base32, sentence encodings) was measured, so the
  values lack an external reference point.
- **No human-subject data.** The metric disagreement documented above is precisely
  an argument that automated proxies cannot substitute for it.

## Dependencies

Python 3.10+, NumPy, SciPy, Pillow, scikit-image, ImageHash, Matplotlib.
See `requirements.txt` for pinned versions.

## License

MIT. See [LICENSE](LICENSE).
