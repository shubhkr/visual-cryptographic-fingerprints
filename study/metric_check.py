"""
Exploratory: do other automated similarity measures predict which image
mismatches people accepted?

  python study/metric_check.py data/human_study/trials.csv

For every image mismatch shown in the main trials, compute between the
reference and the candidate image (as shown to participants):
  - ms_ssim: 3-scale MS-SSIM (64, 32, 16 px; weights of Wang et al. 2003,
    renormalised to three scales),
  - mae: mean absolute pixel difference,
and report Spearman's rho between closeness and acceptance within each
representation. pHash and SSIM are already in the trial data.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import stats
from skimage.metrics import structural_similarity

sys.path.insert(0, str(Path(__file__).parent))
import analyze  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
W = np.array([0.0448, 0.2856, 0.3001])
W = W / W.sum()


def load(rep, digest):
    img = Image.open(ROOT / "docs" / "stimuli" / rep / f"{digest[:20]}.png").convert("L")
    return np.asarray(img, dtype=float) / 255.0


def ms_ssim(a, b):
    vals = []
    for _ in range(3):
        vals.append(max(structural_similarity(a, b, data_range=1.0, win_size=7), 1e-6))
        a = a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2).mean(axis=(1, 3))
        b = b.reshape(b.shape[0] // 2, 2, b.shape[1] // 2, 2).mean(axis=(1, 3))
    return float(np.prod(np.power(vals, W)))


def main(paths):
    df = analyze.load(paths)
    keep, _ = analyze.exclusions(df)
    d = df[(df.task == "compare") & (df.phase == "main") & df.participant.isin(keep)
           & df.rep.isin(analyze.VISUAL) & (df.pair_type != "same")].copy()
    d["said_same"] = d.said_same.astype(bool)
    cache = {}
    for key in d[["rep", "target", "candidate"]].drop_duplicates().itertuples(index=False):
        a, b = load(key.rep, key.target), load(key.rep, key.candidate)
        cache[tuple(key)] = (ms_ssim(a, b), float(np.abs(a - b).mean()))
    d["ms_ssim"] = [cache[(r, t, c)][0] for r, t, c in zip(d.rep, d.target, d.candidate)]
    d["mae"] = [cache[(r, t, c)][1] for r, t, c in zip(d.rep, d.target, d.candidate)]
    rows = []
    for rep, g in d.groupby("rep"):
        rows.append({"rep": rep, "n_trials": len(g),
                     "rho_ms_ssim": stats.spearmanr(g.ms_ssim, g.said_same).statistic,
                     "rho_neg_mae": stats.spearmanr(-g.mae, g.said_same).statistic,
                     "rho_neg_phash": stats.spearmanr(-pd.to_numeric(g.phash), g.said_same).statistic,
                     "rho_ssim": stats.spearmanr(pd.to_numeric(g.ssim), g.said_same).statistic})
    print("Spearman rho between closeness and acceptance, image mismatches (random + hard)")
    print(pd.DataFrame(rows).round(3).to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
