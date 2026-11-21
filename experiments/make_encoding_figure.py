"""
Figure: the three encoding families (v2) for two model identifiers that
differ only by a suffix.

  python experiments/make_encoding_figure.py paper/encodings.pdf

Each image is rendered by src/vcf_v2.py from the SHA-256 digest of the label,
at the 64x64 resolution used in every measurement.
"""

import hashlib
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vcf_v2  # noqa: E402

LABELS = ["llama3-70b-v1", "llama3-70b-v1-TAMPERED"]
COLS = [("randomwalk", {}, "Random walk"),
        ("cellular", {}, "Cellular (mirr.)"),
        ("cellular", {"symmetric": False}, "Cellular (unmirr.)"),
        ("voronoi", {}, "Voronoi")]


def main(out):
    digests = [hashlib.sha256(s.encode()).digest() for s in LABELS]
    plt.rcParams.update({"font.family": "serif", "font.size": 6.5})
    fig, ax = plt.subplots(2, 4, figsize=(3.35, 1.95))
    for j, (enc, params, title) in enumerate(COLS):
        imgs = vcf_v2.render(enc, digests, size=64, **params)
        for i in range(2):
            a = ax[i, j]
            a.imshow(imgs[i], cmap="gray", vmin=0, vmax=255, interpolation="nearest")
            a.set_xticks([]); a.set_yticks([])
            for s in a.spines.values():
                s.set_linewidth(0.4)
        ax[0, j].set_title(title, fontsize=6.5, pad=2)
    ax[0, 0].set_ylabel("original", fontsize=6.5)
    ax[1, 0].set_ylabel("tampered", fontsize=6.5)
    plt.subplots_adjust(left=0.06, right=0.995, top=0.91, bottom=0.02, wspace=0.06, hspace=0.06)
    fig.savefig(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "encodings.pdf")
