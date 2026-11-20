# Visual Cryptographic Fingerprints for AI Supply-Chain Identity

Reference implementation and experimental artifacts for a study of visual hash
encodings as a human-facing identity layer for AI supply-chain provenance.

> **Status:** the paper is being revised after review. Paper source will be
> published here after the next notification.

## Overview

Visual Cryptographic Fingerprints (VCFs) are deterministic images derived from
cryptographic digests of signed AI artifact bundles. They are meant as a
human-recognisable identity layer on top of machine-verifiable provenance
(Sigstore, SLSA, in-toto, AIBOMs), for deployment gates, model-card review and
incident triage.

This repository contains:

- **`src/vcf_v2.py`**, three encoding families (specification v2), with every bit
  of encoding state derived from the digest or from SHAKE-256
- **`src/metrics.py`**, batched SSIM and pHash, numerically identical to
  scikit-image and ImageHash
- **`experiments/run_v2.py`**, every experiment in the paper, seeded
- **`experiments/measure_scale.py`**, a matched-pair benchmark: the same 4,096
  digest pairs scored under 12 configurations and 3 display sizes, with
  fixed and proportional SSIM windows and per-pair SSIM/pHash rank correlation
- **`experiments/results/v2_*.json`**, raw results
- **`study/`** and **`docs/`**, a preregistered human study (not yet run)
- the reviewed-version code and results (`src/vcf_prototype.py`,
  `experiments/results/collision_results.json`,
  `experiments/results/ca_shake_replication.json`), kept for provenance, and
  `src/ca_shake.py`, the standalone SHAKE-256 cellular encoder with a
  golden-vector check

## Headline result

At default settings, SSIM and perceptual hashing (pHash) rank the three
encoding families in **opposite orders**. Controls show that **neither ranking
is a property of the encoding family**:

- **pHash responds to mirror symmetry.** The cellular encoding mirrors its board
  left-to-right, following LifeHash. A mirrored image has zero odd-frequency DCT
  coefficients, so 32 of pHash's 64 bits are the same for almost every image and
  random pairs differ in about 16 bits instead of 32.
- **SSIM responds to feature scale.** Its ranking changes with rendering
  resolution, and at a common 8×8 effective resolution it reverses for the
  cellular encoding.

The reviewed version of the paper explained the disagreement by Game-of-Life
boards decaying to "sparse debris". **That explanation is wrong.** A board that
is never evolved (`steps=0`) clusters in pHash just as much as an evolved one
(15.5 vs 15.4 bits).

| Configuration (10,000 random pairs)  | SSIM mean | pHash mean | pHash bits fixed in >95% of images |
| ------------------------------------ | --------- | ---------- | ---------------------------------- |
| Cellular, mirrored (default)         | 0.018     | 15.4       | 33 |
| Cellular, mirrored, `steps=0`        | 0.002     | 15.5       | – |
| Cellular, **no mirror**              | 0.014     | **31.5**   | 1 |
| Random-walk (default)                | 0.18      | 31.4       | – |
| Random-walk, **mirrored**            | 0.19      | **15.3**   | 33 |
| Voronoi (default)                    | 0.22      | 31.5       | – |
| Voronoi, **mirrored**                | 0.22      | **15.5**   | 33 |

pHash's first bit (the DC term) is the same for every image, so an ideal
encoding has a mean distance of 31.5, not 32. Mirroring fixes 32 more bits.

### Main table (spec v2, original protocol)

| Metric                          | Random-walk | Cellular    | Voronoi     |
| ------------------------------- | ----------- | ----------- | ----------- |
| Exact collisions (N=100K)       | 0           | 0           | 0           |
| Random-pair SSIM (mean / max)   | 0.18 / 0.71 | 0.02 / 0.19 | 0.22 / 0.39 |
| Random-pair pHash (mean / min)  | 31.4 / 14   | **15.4 / 6**| 31.5 / 18   |
| Best-of-2,000 SSIM              | 0.64        | 0.18        | 0.40        |
| Best-of-2,000 pHash             | 12          | **3**       | 14          |

### Larger searches (best pHash over 20 targets, min / mean)

| Encoding           | 2^11      | 2^16      | 2^20       | predicted 2^28 (median) |
| ------------------ | --------- | --------- | ---------- | ----------------------- |
| Random-walk        | 8 / 16.2  | 6 / 11.7  | 4 / 9.8    | 2                       |
| Cellular (mirrored) | 4 / 5.8   | 2 / 3.8   | 1 / 2.5    | 0                       |
| Cellular (no mirror) | 14 / 18.2 | 12 / 14.8 | 12 / 12.5  | 10                      |
| Voronoi            | 14 / 17.2 | 12 / 14.1 | 10 / 11.6  | 8                       |
| Ideal 64-bit hash  | –         | –         | 13 (median)| 10                      |

Hill-climbing over a malleable 16-byte pad gives **no advantage** over random
sampling (mean best 5.35 vs 5.25 bits at 2^13 evaluations), because each edit
produces an unrelated SHA-256 digest.

**Conclusion:** none of the three families is deployment-ready, and
single-metric validation of visual fingerprints is unsound. The unmirrored
cellular encoding scores like an ideal hash under both metrics while being close
to random texture, which people are likely worst at telling apart. Only a
human-subject study can settle which encodings work.

## Human study

`study/` and `docs/` contain a preregistered comparison study, ready to run but
not yet run. Participants judge whether two fingerprints show the same release
under five representations (hex, random walk, mirrored and unmirrored cellular,
Voronoi). Hard mismatches are chosen under the same attacker budget (2^16
candidates) for every representation. The experiment is a static jsPsych page
in `docs/` (GitHub Pages), saves data to a private Google Drive folder through
a small Apps Script, and recruits on Prolific. See `study/README.md` to launch it and `study/PREREGISTRATION.md`
for the design.

## Repository structure

```
visual-cryptographic-fingerprints/
├── src/
│   ├── vcf_v2.py             # encodings, spec v2 (use this)
│   ├── metrics.py            # batched SSIM / pHash
│   ├── vcf_prototype.py      # reviewed version (v1), frozen for provenance
│   └── ca_shake.py           # standalone SHAKE-256 CA with golden-vector check
├── experiments/
│   ├── run_v2.py             # all revision experiments
│   ├── measure_scale.py      # matched-pair benchmark (12 configs × 3 sizes)
│   ├── fill_paper.py         # fills paper numbers from results/*.json
│   ├── run_experiments.sh    # reproduces everything
│   └── results/
│       ├── v2_main.json            # main table + golden vectors
│       ├── v2_scale_*.json         # best-of-2^20 searches + tail distributions
│       ├── v2_adaptive.json        # hill-climbing vs random
│       ├── v2_scalectl.json        # feature-scale control
│       ├── v2_sweep.json           # parameter sweep
│       ├── v2_symmetry.json        # mirror-symmetry controls
│       ├── scale_sensitivity.json  # matched-pair benchmark (spec v2)
│       ├── scale_sensitivity_legacy_voronoi.json  # same, v1 Voronoi intensities
│       ├── collision_results.json  # reviewed version (v1)
│       └── ca_shake_replication.json
├── study/                    # human study: stimulus generator, prereg, analysis, tests
├── docs/                     # the study web page (GitHub Pages root)
└── examples/                 # sample fingerprints (v1 renderer)
```

## Quick start

```bash
pip install -r requirements.txt
python -c "import sys; sys.path.insert(0,'src'); import vcf_v2; print(vcf_v2.golden_vectors())"
```

## Encoding specification (v2)

All three encodings render to 64×64 greyscale by nearest-neighbour upscaling.

**A. Random-walk grid (drunken bishop).** OpenSSH randomart adapted to SHA-256:
17×9 grid, 128 diagonal moves from the digest's 2-bit pairs, least significant
pair first. Longer walks take further moves from SHAKE-256.

**B. Cellular automata (LifeHash-like).** The n×n board is the first n² bits of
SHAKE-256(digest). By default the left half is mirrored onto the right half
(`symmetric=True`); the board evolves for T Game-of-Life steps on a torus and
the summed activity is rendered. Defaults n=32, T=8.

**C. Voronoi tessellation.** SHAKE-256 expands the digest to 3K bytes: bytes
[0, 2K) give the K site coordinates (one byte each for x and y), bytes [2K, 3K)
give the cell intensities in [30, 230]. Defaults K=16.

**Changes from the reviewed version.** v1 seeded 768 of the 1,024 cellular
cells from NumPy's Mersenne Twister keyed on four digest bytes, and v1 Voronoi
used all 32 digest bytes for coordinates and then reused some of them for
intensities. Random-walk output is unchanged. `golden_vectors()` gives the
SHA-256 of the rendered pixels for three fixed inputs per encoding; the
cellular vectors match `ca_shake_replication.json`.

## Reproducing results

```bash
bash experiments/run_experiments.sh        # everything, several hours on 2 cores
python experiments/run_v2.py main          # main table, ~10 minutes
python experiments/run_v2.py scale cellular   # one 2^20 search, 10-40 minutes
```

All sampling is seeded. Every number in the paper is filled from the JSON files
by `experiments/fill_paper.py`.

The matched-pair benchmark is a separate script:

```bash
python experiments/measure_scale.py --output experiments/results/scale_sensitivity.json
```

Its random-walk and cellular rows are byte-identical to an independent
implementation run on the same pairs. Only the Voronoi rows differ, because
spec v2 takes cell intensities from separate SHAKE-256 bytes.
`scale_sensitivity_legacy_voronoi.json` holds the run with the v1 Voronoi
intensities; it reproduces at the commit "update scripts", which still had the
v1 Voronoi renderer.

`src/vcf_prototype.py` is the reviewed (v1) code, unchanged, so
`collision_results.json` still reproduces from it.

### Caveats

- **No human-subject data.** The results above are an argument that automated
  proxies cannot substitute for it.
- **Predicted values** for 2^24 and 2^28 extrapolate a pooled distance
  distribution measured over 2^28 target–candidate pairs; individual targets vary.
- **pHash is a proxy** with known adversarial weaknesses, not ground truth.
- **No textual baseline** (hex, Base32, sentence encodings) in the automated
  measurements. The human study includes hexadecimal as its baseline.

## Dependencies

Python 3.10+, NumPy, SciPy, Pillow, scikit-image, ImageHash and pandas
(`requirements.txt`). The study's browser test also needs Playwright and
Chrome, and its design test needs Node.js.

## License

MIT. See [LICENSE](LICENSE).
