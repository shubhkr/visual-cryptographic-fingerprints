"""
Fill numeric placeholders (@@NAME@@) in the paper template from
experiments/results/v2_*.json, so that every number in the paper is
traceable to a result file.

  python experiments/fill_paper.py paper/main_template.tex paper/main.tex
"""

import json
import os
import re
import sys
from math import comb, log2

import numpy as np

R = os.environ.get("VCF_RESULTS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"))


def load(name):
    with open(os.path.join(R, f"v2_{name}.json")) as f:
        return json.load(f)


def f2(x):
    return f"{x:.2f}"


def f1(x):
    return f"{x:.1f}"


def sd(x):  # signed, LaTeX minus
    return f"${x:+.2f}$".replace("+", "{+}").replace("-", "{-}")


main = load("main")
sweep = load("sweep")
sym = load("symmetry")
scalectl = load("scalectl")
adapt = load("adaptive")
scale = {k: load(f"scale_{k}") for k in ("randomwalk", "cellular", "voronoi", "cellular_nosym")}

V = {}
for tag, enc in (("RW", "randomwalk"), ("CA", "cellular"), ("VO", "voronoi")):
    m = main[enc]
    V[f"{tag}_SSIM_MEAN"] = f2(m["ssim_mean"])
    V[f"{tag}_SSIM_MAX"] = f2(m["ssim_max"])
    V[f"{tag}_PH_MEAN"] = f1(m["phash_mean"])
    V[f"{tag}_PH_SD"] = f2(m["phash_sd"])
    V[f"{tag}_PH_MIN"] = str(m["phash_min"])
    V[f"{tag}_B_SSIM"] = f2(m["best_ssim_max"])
    V[f"{tag}_B_PH"] = str(m["best_phash_min"])
    V[f"{tag}_D"] = sd(m["phash_cohen_d_vs_32"])

# --- scale table -------------------------------------------------------
for tag, key in (("RW", "randomwalk"), ("CA", "cellular"), ("VO", "voronoi"), ("CN", "cellular_nosym")):
    s = scale[key]
    tr = s["trace"]
    for e in (11, 16, 20):
        t = tr[str(1 << e)]
        V[f"{tag}_S{e}"] = f"{t['phash_min']} / {f1(t['phash_mean'])}"
    V[f"{tag}_S20_MIN"] = str(tr[str(1 << 20)]["phash_min"])
    V[f"{tag}_S20_MEAN"] = f1(tr[str(1 << 20)]["phash_mean"])
    pred = s["tail"]["extrapolated_best_of_M_pooled"]
    V[f"{tag}_P24"] = str(pred["2^24"]["median_best_phash"])
    V[f"{tag}_P28"] = str(pred["2^28"]["median_best_phash"])
    V[f"{tag}_SS16"] = f2(tr[str(1 << 16)]["ssim_max"])


def median_obs(key):
    return float(np.median(scale[key]["final_phash_per_target"]))


checks = []
for key, name in (("randomwalk", "random-walk"), ("cellular", "mirrored cellular"),
                  ("voronoi", "Voronoi"), ("cellular_nosym", "unmirrored cellular")):
    p = scale[key]["tail"]["extrapolated_best_of_M_pooled"]["2^20"]["median_best_phash"]
    checks.append(f"{p} against an observed median of {median_obs(key):g} for {name}")
V["PRED_CHECK"] = "; ".join(checks[:-1]) + "; and " + checks[-1]

# ideal encoding: P(best <= 4) at 2^28
p_ideal = np.array([comb(64, k) for k in range(65)], dtype=float) / 2.0 ** 64
cdf_ideal = np.cumsum(p_ideal)


def frac_le(key, k, field="final_phash_per_target"):
    v = np.array(scale[key][field])
    return int((v <= k).sum())


rw28 = scale["randomwalk"]["tail"]["extrapolated_best_of_M_pooled"]["2^28"]["p_best_le_4"]
vo28 = scale["voronoi"]["tail"]["extrapolated_best_of_M_pooled"]["2^28"]["p_best_le_4"]
cn28 = scale["cellular_nosym"]["tail"]["extrapolated_best_of_M_pooled"]["2^28"]["p_best_le_4"]
ideal28 = 1 - np.exp((2.0 ** 28) * np.log1p(-cdf_ideal[4]))

cn_hist = scale["cellular_nosym"]["tail"]["hist"]
V["CN_TAIL_MIN"] = str(next(k for k, c in enumerate(cn_hist) if c > 0))
V["SCALE_TEXT"] = (
    f"Every target of the mirrored cellular encoding had a candidate within "
    f"{max(scale['cellular']['final_phash_per_target'])} bits at $2^{{20}}$ "
    f"(mean {V['CA_S20_MEAN']}, minimum {V['CA_S20_MIN']}), so all "
    f"{frac_le('cellular', 4)} targets were inside the 5-bit threshold. "
    f"Random-walk reached {V['RW_S20_MIN']} bits on {frac_le('randomwalk', 4)} "
    f"target{'s' if frac_le('randomwalk', 4) != 1 else ''} (mean {V['RW_S20_MEAN']}) and "
    f"Voronoi {V['VO_S20_MIN']} (mean {V['VO_S20_MEAN']}), against a median of 13 for an ideal "
    f"encoding. Both have heavier lower tails than the ideal even though their mean distance "
    f"is close to 32. Under the pooled distribution, the probability that a target has a "
    f"candidate within 4 bits at $2^{{28}}$ is {rw28:.2f} for random-walk, against about "
    f"$10^{{-5}}$ for the ideal. Voronoi is predicted to stay above the threshold at "
    f"$2^{{28}}$ (median best {V['VO_P28']}, against 10 for the ideal). The unmirrored cellular encoding "
    f"behaves like the ideal, with a mean best of {V['CN_S20_MEAN']} at $2^{{20}}$ and no pair "
    f"closer than {V['CN_TAIL_MIN']} bits among the $2^{{28}}$ pairs of the tail sample. "
    f"Best SSIM keeps rising with $M$, reaching {V['RW_SS16']} for random-walk at $2^{{16}}$."
)

# --- entropy -------------------------------------------------------------
ent, bits = [], []
for key, name in (("randomwalk", "random-walk"), ("cellular", "mirrored cellular"),
                  ("voronoi", "Voronoi"), ("cellular_nosym", "unmirrored cellular")):
    t = scale[key]["tail"]
    n = t["candidates"]
    c = n - t["distinct_phash_values"]
    ent.append(f"{c:,} ({name})".replace(",", "{,}"))
    bits.append(f"{log2(n * n / (2 * c)):.0f} ({name})" if c > 0 else f"more than 39 ({name})")
V["ENT_TEXT"] = ", ".join(ent[:-1]) + " and " + ent[-1]
V["ENT_BITS"] = ", ".join(bits[:-1]) + " and " + bits[-1]

# --- adaptive ------------------------------------------------------------
a = adapt["summary"]
V["ADAPT_TEXT"] = (
    f"Hill-climbing reached a mean best distance of {a['hill_mean']:.2f} bits (minimum "
    f"{a['hill_min']}), and random sampling at the same budget reached {a['random_mean']:.2f} "
    f"(minimum {a['random_min']}). The difference is within run-to-run variation."
)

# --- feature-scale control ----------------------------------------------
sc = scalectl
# the narrative in SCALECTL_TEXT describes these orderings; fail loudly if they change
_rk = sc["rankings"]
assert _rk["native_64"]["ssim_best_to_worst"] == ["cellular", "randomwalk", "voronoi"]
assert _rk["render_32"]["ssim_best_to_worst"] == ["cellular", "voronoi", "randomwalk"]
assert _rk["common_16_to_64"]["ssim_best_to_worst"] == ["cellular", "randomwalk", "voronoi"]
assert _rk["common_8_to_64"]["ssim_best_to_worst"][-1] == "cellular"
assert _rk["ms_ssim_3scale"]["best_to_worst"] == ["cellular", "voronoi", "randomwalk"]
assert all(_rk[c]["phash_best_to_worst"][-1] == "cellular" for c in
           ("native_64", "render_32", "render_128", "common_16_to_64", "common_8_to_64"))
names = {"randomwalk": "random-walk", "cellular": "cellular", "voronoi": "Voronoi"}


def order(lst):
    return ", ".join(names[e] for e in lst)


ph_range = max(abs(sc[e][c]["phash_mean"] - sc[e]["native_64"]["phash_mean"])
               for e in names for c in ("render_32", "render_128", "common_16_to_64", "common_8_to_64"))
c8 = {e: sc[e]["common_8_to_64"]["ssim_mean"] for e in names}
r32 = {e: sc[e]["render_32"]["ssim_mean"] for e in names}
ms = {e: sc[e]["ms_ssim_3scale"]["mean"] for e in names}
V["SCALECTL_TEXT"] = (
    f"pHash was unaffected by every manipulation (all means within {ph_range:.1f} bits of the "
    f"default), because it resizes to 32$\\times$32 and keeps only the lowest frequencies. "
    f"SSIM was not. Rendering at 32 pixels moved Voronoi from the worst SSIM separation to "
    f"second place ({f2(r32['voronoi'])} against {f2(r32['randomwalk'])} for random-walk). "
    f"Equalising feature scale at 8$\\times$8 reversed the cellular result, with mean SSIM "
    f"{f2(c8['cellular'])} for cellular against {f2(c8['randomwalk'])} and {f2(c8['voronoi'])}, "
    f"so that SSIM then agrees with pHash that the mirrored cellular encoding is the least "
    f"separated. At 16$\\times$16 the default order held. The three-scale SSIM kept the cellular "
    f"encoding best ({ms['cellular']:.4f} against {ms['voronoi']:.4f} and "
    f"{ms['randomwalk']:.4f}) but swapped random-walk and Voronoi. "
    f"The SSIM side of the inversion is therefore a statement about texture scale at one "
    f"rendering resolution, which confirms the confound we flagged in the earlier version."
)

# --- sweep ---------------------------------------------------------------
rows = sweep["rows"]
srows = sym["rows"]
V["SWEEP_N"] = str(len(rows) + len(srows) - 1)  # minus the duplicated mirrored reference


def rng_txt(vals, fmt="{:.1f}"):
    lo, hi = fmt.format(min(vals)), fmt.format(max(vals))
    return f"about {lo}" if lo == hi else f"{lo} to {hi}"


def get(rows, enc, **p):
    for r in rows:
        if r["encoding"] == enc and all(r["params"].get(k) == v for k, v in p.items()):
            return r
    raise KeyError((enc, p))


V["SW_CA32_T0_PH"] = f1(get(rows, "cellular", n=32, steps=0)["phash_mean"])
V["SW_CA32_T0_SSIM"] = f"{get(rows, 'cellular', n=32, steps=0)['ssim_mean']:.3f}"
V["SYM_CA_NOSYM_PH"] = f1(get(srows, "cellular", n=32, steps=8, symmetric=False)["phash_mean"])
V["SYM_RW_MIR_PH"] = f1(get(srows, "randomwalk", mirrored=True)["phash_mean"])
V["SYM_VO_MIR_PH"] = f1(get(srows, "voronoi", mirrored=True)["phash_mean"])
V["SYM_FIXED"] = str(get(srows, "cellular", n=32, steps=8, symmetric=True)["phash_fixed_bits_95"])
unm = [r for r in srows if r["encoding"] == "cellular" and r["params"].get("symmetric") is False]
unm_fixed = sorted({r["phash_fixed_bits_95"] for r in unm})
# the text says the count is the same for all three mirrored encodings and is DC + 32
assert V["SYM_FIXED"] == "33"
assert get(srows, "randomwalk", mirrored=True)["phash_fixed_bits_95"] == 33
assert get(srows, "voronoi", mirrored=True)["phash_fixed_bits_95"] == 33
assert all(r["phash_fixed_bits_95"] == 1 for r in unm)

mir_ca = [r for r in rows if r["encoding"] == "cellular"]
asym = [r for r in rows if r["encoding"] != "cellular"]
V["SWEEP_TEXT"] = (
    f"Within each group the pHash mean barely moves. It is {rng_txt([r['phash_mean'] for r in asym])} "
    f"bits for every unmirrored configuration of random-walk and Voronoi, "
    f"{rng_txt([r['phash_mean'] for r in mir_ca])} for every mirrored cellular configuration "
    f"including $T{{=}}0$, and {rng_txt([r['phash_mean'] for r in unm])} "
    f"for every unmirrored one. SSIM varies by an order of magnitude with walk length, board size "
    f"and number of sites, for example from {f2(get(rows, 'voronoi', k=8)['ssim_mean'])} to "
    f"{f2(get(rows, 'voronoi', k=64)['ssim_mean'])} for Voronoi as $K$ grows from 8 to 64. "
    f"The sweep separates the two metrics cleanly. pHash tracks symmetry, SSIM tracks feature "
    f"size, and neither tracks the encoding family. Every mirrored cellular configuration also "
    f"comes within {min(r['best_phash_min'] for r in mir_ca)} to "
    f"{max(r['best_phash_min'] for r in mir_ca)} bits of some target with only 2{{,}}048 "
    f"candidates, so no board size or step count rescues the LifeHash-style design under pHash."
)


def cfg(r):
    e, p = r["encoding"], r["params"]
    if e == "randomwalk":
        base = f"{p.get('w', 17)}$\\times${p.get('h', 9)}, {p.get('n_moves', 128)} moves"
        return ("Random-walk, mirrored", base) if p.get("mirrored") else ("Random-walk", base)
    if e == "voronoi":
        return ("Voronoi, mirrored" if p.get("mirrored") else "Voronoi", f"$K{{=}}{p.get('k', 16)}$")
    m = "mirrored" if p.get("symmetric", True) else "no mirror"
    return (f"Cellular, {m}", f"$n{{=}}{p['n']}$, $T{{=}}{p['steps']}$")


lines = []
last = None
seen = set()
for r in rows + srows:
    fam, c = cfg(r)
    if (fam, c) in seen:
        continue
    seen.add((fam, c))
    famcell = fam if fam != last else ""
    if fam != last and last is not None:
        lines.append("\\addlinespace[2pt]")
    last = fam
    lines.append(f"{famcell} & {c} & {r['ssim_mean']:.3f} & {f1(r['phash_mean'])} & "
                 f"{r['best_phash_min']} / {f1(r['best_phash_mean'])} \\\\")

V["SWEEP_TABLE"] = (
    "\\begin{table}[t]\n\\centering\n"
    "\\caption{Parameter sweep and symmetry controls. SSIM and pHash are means over 10{,}000 "
    "random pairs. Best pHash is the minimum / mean of per-target bests over 20 targets with "
    "2{,}048 random candidates each.}\n\\label{tab:sweep}\n\\scriptsize\n"
    "\\setlength{\\tabcolsep}{3pt}\n"
    "\\begin{tabular}{@{}l l c c c@{}}\n\\toprule\n"
    "\\textbf{Family} & \\textbf{Configuration} & \\textbf{SSIM} & \\textbf{pHash} & "
    "\\textbf{Best pHash} \\\\\n\\midrule\n" + "\n".join(lines) +
    "\n\\bottomrule\n\\end{tabular}\n\\end{table}"
)

V["IMPL1"] = (
    f"Under pHash, random-walk, Voronoi and the mirrored cellular encoding all have heavier "
    f"lower tails than an ideal encoding. The mirrored cellular encoding reaches the 5-bit "
    f"threshold for every target with $2^{{20}}$ random candidates, and random-walk is "
    f"predicted to do so for most targets within $2^{{28}}$. Voronoi stays above the threshold "
    f"in our data, with a margin that shrinks as the budget grows. Under SSIM, random-walk candidates "
    f"reach {V['RW_SS16']} at $2^{{16}}$. The unmirrored cellular encoding is the best "
    f"configuration under both metrics, with pHash statistics indistinguishable from an ideal "
    f"hash and the lowest SSIM. It is also close to uniform random texture, which people are "
    f"likely to find hardest to tell apart at a glance, so the metrics reward the property a "
    f"human comparison may lack most. Nothing in our data shows that any configuration is "
    f"safe, and without human data nothing could."
)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    s = open(src).read()
    missing = set(re.findall(r"@@([A-Z0-9_]+)@@", s)) - set(V)
    if missing:
        sys.exit(f"missing values: {sorted(missing)}")
    for k, v in V.items():
        s = s.replace(f"@@{k}@@", v)
    open(dst, "w").write(s)
    print(f"filled {dst}")
