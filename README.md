# Visual Cryptographic Fingerprints for AI Supply-Chain Identity

**Reference implementation and experimental artifacts for the paper:**

> *Visual Cryptographic Fingerprints for AI Supply-Chain Identity*
> Shubham Kumar, 2026
> [[Paper PDF]](paper/research_paper_vcf.pdf) · [[arXiv]](#) *(link coming soon)*

## Overview

This repository contains:

- A **reference prototype** implementing three visual hash encoding families from SHA-256 digests
- **Automated collision and near-collision testing** framework
- **Experimental results** reported in the paper
- **Example visual fingerprints** for sample AI model identifiers

Visual Cryptographic Fingerprints (VCFs) are deterministic images derived from cryptographic digests of signed AI artifact bundles. They provide a human-recognizable identity layer atop machine-verifiable provenance infrastructure (Sigstore, SLSA, in-toto, AIBOMs), reducing human error at deployment gates, model card review, and incident triage.

## Repository Structure

```
visual-cryptographic-fingerprints/
├── README.md
├── LICENSE
├── requirements.txt
├── src/
│   └── vcf_prototype.py          # Three encoding implementations + testing framework
├── experiments/
│   ├── run_experiments.sh         # One-command reproduction of all results
│   └── results/
│       └── collision_results.json # Raw experimental data from the paper
├── examples/
│   ├── *.png                      # Generated visual fingerprints
│   └── *.txt                      # ASCII randomart outputs
└── paper/
    ├── research_paper_vcf.tex     # LaTeX source
    └── references.bib             # BibTeX references
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/shubhkr/visual-cryptographic-fingerprints.git
cd visual-cryptographic-fingerprints

# Install dependencies
pip install -r requirements.txt

# Generate example fingerprints and run collision tests
python src/vcf_prototype.py
```

## Encoding Families

### A. Random-Walk Grid (Drunken Bishop)
Terminal-friendly ASCII art. Implements the OpenSSH randomart algorithm adapted for SHA-256 (17×9 grid, 128 diagonal moves).

```
  llama3-70b-v1       llama3-70b-v1
    (original)          (tampered)
+--[SHA256]------+  +--[SHA256]------+
|+=+=. .         |  |.o***.o.        |
|B*=oo*..        |  | o+=.=o. .      |
|.**=*oo o . .   |  |.+..+o o+ .     |
|.+.o+o o . . .  |  |..o o+.o.+      |
|. . . . S   .   |  |  o.o o S .     |
|   o.  = . .    |  | + . + . . +    |
|  ....+   .     |  |  = . = o = .   |
|...  ..o .      |  | . . + o o .    |
|=.     .o       |  |  ..o...o       |
+----------------+  +----------------+
```

### B. Cellular Automata (LifeHash-like)
GUI-friendly grayscale images. A 32×32 Game-of-Life grid seeded from digest bits, evolved 8 steps with horizontal symmetry.

### C. Voronoi Tessellation
Dashboard-friendly region maps. 16 site points derived from the digest, Voronoi cells with deterministic intensity mapping.

## Experimental Results Summary

| Metric | Random-walk | Cellular | Voronoi |
|--------|-------------|----------|---------|
| Exact collisions (N=100K) | 0 | 0 | 0 |
| Render rate | 14,769/s | 3,446/s | 3,337/s |
| Random pair SSIM (mean / max) | 0.18 / 0.68 | 0.02 / 0.16 | 0.22 / 0.48 |
| Mining best SSIM (M=2,000) | 0.72 | 0.19 | 0.45 |

**Key finding:** Of the three families tested, cellular automata encodings show the strongest resistance under automated similarity metrics. Random-walk grids are the weakest and should be paired with textual encodings.

See `experiments/results/collision_results.json` for full data.

## Reproducing Paper Results

```bash
# Full reproduction (takes ~3 minutes)
bash experiments/run_experiments.sh

# Or run directly with custom parameters
python src/vcf_prototype.py
```

The collision testing runs:
1. **Exact collision test:** 100,000 random SHA-256 digests per encoding
2. **Near-collision analysis:** 10,000 random pairs with SSIM and pHash metrics
3. **Targeted mining:** 20 targets × 2,000 candidates per encoding

## Dependencies

- Python 3.10+
- NumPy, SciPy, Pillow, scikit-image, ImageHash, Matplotlib

See `requirements.txt` for pinned versions.

## Citation

If you use this code or build on this work, please cite:

```bibtex
@article{kumar2026vcf,
  title   = {Visual Cryptographic Fingerprints for {AI} Supply-Chain Identity},
  author  = {Kumar, Shubham},
  year    = {2026},
  note    = {Preprint}
}
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
