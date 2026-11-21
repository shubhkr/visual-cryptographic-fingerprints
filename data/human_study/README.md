# Human study data

`trials.csv` holds every screen of every participant (49 people, Prolific,
November 2026), one row per screen. It was made from the raw files by
`study/anonymize.py`: participant IDs are replaced by P01–P49, and the
Prolific study and session IDs and the design seed are removed. The raw files
are not in this repository.

Reproduce the analysis:

    python study/analyze.py data/human_study/trials.csv

This prints the output saved in `analysis_output.txt` and writes
`study/results.json`. Scoring is case-insensitive (see the Deviations section
of `study/PREREGISTRATION.md`). One participant (P09 in this file) is excluded
by the planned rules, leaving 48.

Main columns for comparison trials (`task == "compare"`, `phase == "main"`):
`rep` (representation), `pair_type` (same, random, phash_hard, ssim_hard,
hex_hard), `target` and `candidate` (SHA-256 digests), `phash`, `ssim`,
`edge_match` (pair closeness), `response` (key), `said_same`, `correct`, `rt`
(ms).
