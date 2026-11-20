"""
Preregistered analysis for the visual-fingerprint comparison study.

  python study/analyze.py data/*.csv
  python study/analyze.py --include-debug /tmp/sim/*.csv   # testing only

Input: the CSV files saved by the experiment (one per participant).
Output: exclusions, per-condition rates, the confirmatory tests (H1, H2) and
the exploratory proxy analysis (H3), printed and written to study/results.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

VISUAL = ["walk", "life_mirrored", "life_unmirrored", "voronoi"]
HARD = {"phash_hard", "ssim_hard", "hex_hard"}


def load(paths):
    frames = [pd.read_csv(p) for p in paths]
    return pd.concat(frames, ignore_index=True)


def exclusions(df, include_debug=False):
    """Preregistered exclusion rules. Returns (kept participant ids, table)."""
    rows = []
    for pid, g in df.groupby("participant"):
        main = g[(g.task == "compare") & (g.phase == "main")]
        attn = g[g.task == "attention"]
        rt = pd.to_numeric(main.rt, errors="coerce")
        same_trials = main[main.pair_type == "same"]
        rows.append({
            "participant": pid,
            "debug": bool(g.debug.astype(str).str.lower().eq("true").any()),
            "complete": len(main) == 160,
            "attention_failed": int((~attn.passed.astype(str).str.lower().eq("true")).sum()),
            "fast_share": float((rt < 200).mean()) if len(rt) else 1.0,
            "same_acc": float(same_trials.correct.astype(str).str.lower().eq("true").mean()) if len(same_trials) else 0.0,
            "random_acc": float(main[main.pair_type == "random"].correct.astype(str).str.lower().eq("true").mean()) if len(main) else 0.0,
        })
    t = pd.DataFrame(rows)
    t["excluded"] = ((t.debug & (not include_debug)) | ~t.complete | (t.attention_failed >= 2) | (t.fast_share > 0.10)
                     | (t.random_acc < 0.5))
    return set(t.loc[~t.excluded, "participant"]), t


def main(paths, include_debug=False):
    df = load(paths)
    keep, ex = exclusions(df, include_debug)
    if not keep:
        sys.exit(f"no participants left after exclusions ({ex.shape[0]} loaded); see the exclusion rules")
    d = df[(df.task == "compare") & (df.phase == "main") & df.participant.isin(keep)].copy()
    d["said_same"] = d.said_same.astype(str).str.lower().eq("true")
    d["rt"] = pd.to_numeric(d.rt, errors="coerce")
    out = {"n_total": int(ex.shape[0]), "n_kept": len(keep),
           "exclusion_reasons": ex[ex.excluded].drop(columns="excluded").to_dict("records")}

    # Descriptive: acceptance rate by representation and pair type
    rates = d.groupby(["rep", "pair_type"]).said_same.mean().unstack()
    out["acceptance_rate"] = rates.round(4).to_dict()
    print(f"kept {len(keep)} of {ex.shape[0]} participants\n")
    print("P(say 'same') by representation and pair type")
    print(rates.round(3), "\n")

    # Per-participant false-acceptance on hard mismatches
    hard = d[d.pair_type.isin(HARD)]
    fa = hard.groupby(["participant", "rep"]).said_same.mean().unstack()

    # H1: each visual representation vs hexadecimal (paired t, Holm over 4 tests)
    tests = []
    for rep in VISUAL:
        pair = fa[["hex", rep]].dropna()
        t = stats.ttest_rel(pair[rep], pair["hex"])
        w = stats.wilcoxon(pair[rep], pair["hex"], zero_method="zsplit")
        tests.append({"rep": rep, "n": len(pair), "mean_visual": pair[rep].mean(), "mean_hex": pair["hex"].mean(),
                      "diff": (pair[rep] - pair["hex"]).mean(), "t": t.statistic, "p": t.pvalue,
                      "wilcoxon_p": w.pvalue})
    order = np.argsort([x["p"] for x in tests])
    m = len(tests)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * tests[i]["p"]))
        tests[i]["p_holm"] = running
    out["H1"] = tests
    print("H1: false acceptance of hard mismatches, visual minus hex")
    print(pd.DataFrame(tests).round(4).to_string(index=False), "\n")

    # H2: mirrored vs unmirrored cellular automaton
    pair = fa[["life_mirrored", "life_unmirrored"]].dropna()
    t = stats.ttest_rel(pair.life_mirrored, pair.life_unmirrored)
    out["H2"] = {"n": len(pair), "mean_mirrored": pair.life_mirrored.mean(),
                 "mean_unmirrored": pair.life_unmirrored.mean(), "t": t.statistic, "p": t.pvalue}
    print("H2: mirrored minus unmirrored cellular", {k: round(v, 4) for k, v in out["H2"].items()}, "\n")

    # H3 (exploratory): do pHash or SSIM predict acceptance within image representations?
    img = d[d.rep.isin(VISUAL) & (d.pair_type != "same")].copy()
    img["phash"] = pd.to_numeric(img.phash, errors="coerce")
    img["ssim"] = pd.to_numeric(img.ssim, errors="coerce")
    h3 = []
    for rep, g in img.groupby("rep"):
        h3.append({"rep": rep,
                   "rho_phash": stats.spearmanr(-g.phash, g.said_same).statistic,
                   "rho_ssim": stats.spearmanr(g.ssim, g.said_same).statistic,
                   "acc_phash_hard": g[g.pair_type == "phash_hard"].said_same.mean(),
                   "acc_ssim_hard": g[g.pair_type == "ssim_hard"].said_same.mean()})
    out["H3"] = h3
    print("H3 (exploratory): metric vs acceptance, image mismatches")
    print(pd.DataFrame(h3).round(4).to_string(index=False), "\n")

    # Secondary: median response time on correct trials
    out["median_rt_correct"] = (d[d.said_same == (d.correct_response == "same")]
                                .groupby("rep").rt.median().round(0).to_dict())
    print("median RT (ms), correct trials:", out["median_rt_correct"])

    Path(__file__).with_name("results.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    args = sys.argv[1:]
    debug = "--include-debug" in args
    args = [a for a in args if a != "--include-debug"]
    if not args:
        sys.exit(__doc__)
    main(args, debug)
