"""
Make the shareable copy of the human-study data.

  python study/anonymize.py "path/to/raw/*.csv"

Reads the per-participant CSV files saved by the experiment and writes one
file, data/human_study/trials.csv, in which:
  - Prolific participant, study and session IDs are replaced by P01, P02, ...
    (assigned in an order that does not reveal the IDs; no key is kept),
  - the design seed, which is derived from the Prolific ID, is removed,
  - the HTML of each screen is removed (the stimulus columns remain).
Raw files must never be committed: they contain Prolific IDs.
"""

import csv
import glob
import hashlib
import os
import secrets
import sys

DROP = {"study_id", "session_id", "design_seed", "stimulus", "view_history"}


def main(patterns):
    paths = sorted(p for pat in patterns for p in glob.glob(pat))
    if not paths:
        sys.exit(__doc__)
    rows, fields = [], []
    for p in paths:
        with open(p, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for name in r.fieldnames:
                if name not in fields:
                    fields.append(name)
            rows.extend(r)
    salt = secrets.token_bytes(16)  # discarded, so the order cannot be recomputed
    ids = sorted({r["participant"] for r in rows}, key=lambda x: hashlib.sha256(salt + x.encode()).digest())
    label = {pid: f"P{i + 1:02d}" for i, pid in enumerate(ids)}
    out_fields = [f for f in fields if f not in DROP]
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "human_study", "trials.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = dict(r)
            r["participant"] = label[r["participant"]]
            w.writerow(r)
    print(f"{len(ids)} participants, {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
