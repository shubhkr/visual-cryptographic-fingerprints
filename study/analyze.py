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
    return rescore(pd.concat(frames, ignore_index=True))


def rescore(df):
    """Score key presses case-insensitively.

    Versions of the experiment before 2026-11-21 compared the pressed key
    with "f"/"j" case-sensitively, so a participant with Caps Lock on was
    scored as answering "different" on every trial and failing every
    attention check. The raw key is saved, so the scores are recomputed
    here from it.
    """
    df = df.copy()
    key = df.response.astype(str).str.strip().str.lower()
    cmp = df.task == "compare"
    df.loc[cmp, "said_same"] = key[cmp].eq("f")
    df.loc[cmp, "correct"] = df.loc[cmp, "said_same"] == df.loc[cmp, "correct_response"].eq("same")
    df.loc[cmp, "false_accept"] = df.loc[cmp, "correct_response"].eq("different") & df.loc[cmp, "said_same"].astype(bool)
    att = df.task == "attention"
    if att.any():
        expected = df.loc[att, "expected_key"] if "expected_key" in df else pd.Series("j", index=df.index[att])
        df.loc[att, "passed"] = key[att].eq(expected.fillna("j").astype(str).str.lower())
    return df


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
                     | (t.random_acc < 0.5) | (t.same_acc < 0.5))
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
    print("median RT (ms), correct trials:", out["median_rt_correct"], "\n")

    robustness(d, fa, out)

    Path(__file__).with_name("results.json").write_text(json.dumps(out, indent=1, default=float))


def mean_ci(x, level=0.95):
    x = np.asarray(x, dtype=float)
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    h = stats.t.ppf(0.5 + level / 2, len(x) - 1) * se
    return m, m - h, m + h


def robustness(d, fa, out):
    """Robustness and descriptive analyses added after data collection.

    None of these is confirmatory. They report confidence intervals for the
    H1 and H2 differences, a paired response-time comparison, and the
    mixed-effects logistic regression named in the analysis plan.
    """
    # 95% CIs for the paired differences behind H1 and H2
    ci = {}
    for rep in VISUAL:
        m, lo, hi = mean_ci(fa[rep] - fa["hex"])
        ci[f"{rep}_minus_hex"] = {"diff": m, "lo": lo, "hi": hi}
    m, lo, hi = mean_ci(fa["life_mirrored"] - fa["life_unmirrored"])
    ci["mirrored_minus_unmirrored"] = {"diff": m, "lo": lo, "hi": hi}
    out["diff_ci95"] = ci
    print("95% CI of differences in false acceptance (percentage points)")
    for k, v in ci.items():
        print(f"  {k:28s} {100 * v['diff']:+.2f} [{100 * v['lo']:+.2f}, {100 * v['hi']:+.2f}]")

    # Paired response time: per-participant median on correct trials
    corr = d[d.said_same == (d.correct_response == "same")]
    prt = corr.groupby(["participant", "rep"]).rt.median().unstack()
    rt = {}
    print("\nper-participant median RT on correct trials, visual vs hex")
    for rep in VISUAL:
        pair = prt[["hex", rep]].dropna()
        faster = int((pair[rep] < pair["hex"]).sum())
        w = stats.wilcoxon(pair[rep], pair["hex"])
        rt[rep] = {"n": len(pair), "faster": faster, "median_of_medians_ms": float(pair[rep].median()),
                   "hex_median_of_medians_ms": float(pair["hex"].median()), "wilcoxon_p": w.pvalue}
        print(f"  {rep:16s} {faster}/{len(pair)} faster, median {pair[rep].median():.0f} vs hex "
              f"{pair['hex'].median():.0f} ms, Wilcoxon p={w.pvalue:.2g}")
    out["rt_paired"] = rt

    # Mixed-effects logistic regression on hard mismatches: random intercepts
    # for participant and for target item (variational Bayes, statsmodels)
    try:
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    except ImportError:
        print("\nstatsmodels not installed; skipping the mixed-effects model")
        return
    h = d[d.pair_type.isin(HARD)].copy()
    h["y"] = h.said_same.astype(int)
    h["rep"] = pd.Categorical(h.rep, categories=["hex"] + VISUAL)
    h["item"] = h.rep.astype(str) + ":" + h.target.astype(str)
    model = BinomialBayesMixedGLM.from_formula(
        "y ~ C(rep)", {"participant": "0 + C(participant)", "item": "0 + C(item)"}, h)
    fit = model.fit_vb()
    names = model.exog_names
    mixed = {}
    print("\nmixed-effects logistic regression (hard mismatches), odds ratio vs hex [95% interval]")
    for i, name in enumerate(names):
        if not name.startswith("C(rep)"):
            continue
        rep = name.split("T.")[1].rstrip("]")
        mu, sd = fit.fe_mean[i], fit.fe_sd[i]
        mixed[rep] = {"log_or": mu, "sd": sd, "or": float(np.exp(mu)),
                      "or_lo": float(np.exp(mu - 1.96 * sd)), "or_hi": float(np.exp(mu + 1.96 * sd))}
        print(f"  {rep:16s} OR {np.exp(mu):.2f} [{np.exp(mu - 1.96 * sd):.2f}, {np.exp(mu + 1.96 * sd):.2f}]")
    out["mixed_model"] = mixed
    print("  (variational intervals are known to be narrow; see the GEE below)")

    # Population-averaged logistic regression with participant-clustered
    # (robust) standard errors, as a frequentist cross-check
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    g = smf.gee("y ~ C(rep)", groups="participant", data=h, family=sm.families.Binomial(),
                cov_struct=sm.cov_struct.Exchangeable()).fit()
    ci = g.conf_int()
    gee = {}
    print("\nGEE logistic regression (clustered by participant), odds ratio vs hex [95% CI]")
    for name in g.params.index:
        if not name.startswith("C(rep)"):
            continue
        rep = name.split("T.")[1].rstrip("]")
        gee[rep] = {"or": float(np.exp(g.params[name])), "or_lo": float(np.exp(ci.loc[name, 0])),
                    "or_hi": float(np.exp(ci.loc[name, 1])), "p": float(g.pvalues[name])}
        print(f"  {rep:16s} OR {gee[rep]['or']:.2f} [{gee[rep]['or_lo']:.2f}, {gee[rep]['or_hi']:.2f}], p={gee[rep]['p']:.3f}")
    out["gee"] = gee


if __name__ == "__main__":
    args = sys.argv[1:]
    debug = "--include-debug" in args
    args = [a for a in args if a != "--include-debug"]
    if not args:
        sys.exit(__doc__)
    main(args, debug)
