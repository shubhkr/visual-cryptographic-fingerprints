# Preregistration: Can people tell visual fingerprints of AI artifacts apart?

**Status (added 2026-11-21).** This is the analysis plan as it stood before
data collection, at commit `b14a417` (2026-11-20 19:28 UTC); the Prolific
study was published at 19:44 UTC. The plan was committed to this public
repository but not registered with OSF or AsPredicted. Items marked
"not filled in" were open at that time. What actually happened, including
deviations, is recorded at the end under **Record of the study**.

## 1. Data collection status

No data have been collected for this study when this document is registered.
The stimuli (`docs/stimuli.js`, version `vcf-study-v1`) and the analysis
script (`study/analyze.py`) are frozen at the registered commit. (Not filled in before data collection: the
commit is `b14a417`.)

## 2. Research questions

Visual fingerprints render a cryptographic digest as an image so that a
person can compare two releases at a glance. Automated similarity metrics
(SSIM and pHash) disagree on which encodings are hard to tell apart. We ask
how often people accept a mismatched pair under each encoding, compared with
the full hexadecimal digest.

## 3. Hypotheses

- **H1.** For mismatched pairs chosen by a matched attacker budget, the rate
  at which participants wrongly answer "same release" differs between each
  of the four visual encodings and the hexadecimal digest. Two-sided; four
  tests with Holm correction.
- **H2.** That rate differs between the mirrored and the unmirrored
  cellular-automaton encoding. Two-sided. (Mirroring fixes half of pHash's
  bits, so pHash predicts that mirrored pairs are easier to confuse; the
  intent of mirroring in LifeHash is easier recognition.)
- **H3 (exploratory).** Within each image encoding, smaller pHash distance or
  higher SSIM predicts wrong acceptance. We report this without a
  confirmatory claim.

## 4. Design

Within-subject. Every participant sees all five representations in separate
blocks. Block order, item assignment and trial order are randomised per
participant with a seed derived from the Prolific ID (`docs/design.js`).
The side on which the approved release appears is fixed per participant
and counterbalanced across participants.

| Representation      | Same | Random mismatch | Hard mismatch            |
| ------------------- | ---- | --------------- | ------------------------ |
| Hexadecimal         | 16   | 4               | 12 (edge-matched)        |
| Random walk         | 16   | 4               | 6 pHash-hard, 6 SSIM-hard |
| Life, mirrored      | 16   | 4               | 6 pHash-hard, 6 SSIM-hard |
| Life, unmirrored    | 16   | 4               | 6 pHash-hard, 6 SSIM-hard |
| Voronoi             | 16   | 4               | 6 pHash-hard, 6 SSIM-hard |

That gives 160 main trials, 4 practice trials with feedback and 3
instructed-response attention checks (press J, press F, press J).

**Stimuli.** 48 targets per representation. Each hard mismatch is the closest
of 2^16 random candidate digests to its target: under pHash or SSIM for
images, and by the number of matching leading and trailing characters for
hex. All representations therefore face the same attacker budget. Images are
64×64 greyscale, shown at 192×192 with nearest-neighbour scaling. Hex is
shown as four lines of four 4-character groups.

**Task.** "Same release" (F) or "different release" (J), no time limit.
Participants are told that different releases can look similar.

## 5. Outcomes

- **Primary:** false acceptance, the proportion of hard-mismatch trials
  answered "same release", per participant and representation.
- **Secondary:** false acceptance on random mismatches; false rejection on
  same pairs; median response time on correct trials.

## 6. Sample

**Platform:** Prolific. Adults, fluent in English, desktop or laptop only,
approval rate of at least 95%. Pay: (not filled in before data collection; at least $12/hour for an
estimated 15 minutes was the plan, see the Record).

**Size:** 48 included participants, after a pilot of 8 that is not analysed.
Recruitment continues until 48 participants meet the inclusion criteria, up to
a cap of 60.

**Justification:** simulation (`study/power.md`) with 12 hard trials per
representation, participant variability of 1.0 on the logit scale and item
variability of 0.5, at α = 0.0125 (Holm, 4 tests). It gives about 86% power
for 20% vs 30% false acceptance at n = 50, and above 95% for 15% vs 30% at
n = 40.

## 7. Exclusions

A participant is excluded if any of the following holds:

1. fails 2 or more of the 3 attention checks;
2. more than 10% of main trials have a response time under 200 ms;
3. accepts at least half of the random mismatches (accuracy below 50% on
   pairs that are obviously different);
4. rejects at least half of the matching pairs (accuracy below 50% on
   "same" trials);
5. did not complete all 160 main trials.

Rules 3 and 4 together catch a participant who presses the same key on
every trial. The attention checks ask for J, then F, then J, for the same
reason.

No trial-level exclusions. No other data are removed.

## 8. Analysis

Run `study/analyze.py` unchanged.

- **H1:** per-participant false acceptance on hard mismatches; paired t-test
  of each visual representation against hex; Holm correction over the four
  tests; Wilcoxon signed-rank as a robustness check.
- **H2:** paired t-test, mirrored vs unmirrored cellular automaton.
- **Robustness (not confirmatory):** mixed-effects logistic regression of
  acceptance on representation with random intercepts for participant and
  target item.
- **H3:** Spearman correlation between metric value and acceptance within each
  image representation.

## 9. Ethics

(Not filled in before data collection; see the Record.) The consent text is
in `docs/experiment.js`.

## Record of the study (added after data collection)

- **Run.** Prolific, published 2026-11-20 19:44 UTC after a manual review by
  Prolific, completed 2026-11-21. Filters: desktop only, fluent English,
  normal or corrected vision, approval rate 95–100%.
- **Pay.** $2.40 for an estimated 18 minutes ($8/hour, Prolific's minimum),
  not the $12/hour in the plan. The median completion time was 12.3 minutes.
  All submissions were approved, including the excluded participant's.
- **Pilot.** The paid pilot of 8 was not run. Two informal runs by
  volunteers (not analysed) set the time estimate.
- **Sample.** 49 completed; 1 excluded by rule 4 (accuracy on identical pairs
  below 50%), leaving 48. No replacements were needed.
- **Ethics.** The researcher is independent and has no institutional review
  board, so the study was not reviewed by one. The consent page says so;
  safeguards are described in the paper's Ethical Considerations appendix.
- **Analyses added after data collection** (not confirmatory): 95% CIs of the
  H1/H2 differences, a paired response-time comparison on correct trials, the
  planned mixed-effects model (fitted by variational Bayes in statsmodels) and
  a participant-clustered GEE logistic regression (`study/analyze.py`), and
  correlations with MS-SSIM and pixel difference (`study/metric_check.py`).
- **Data.** `data/human_study/trials.csv` (anonymised by
  `study/anonymize.py`) and the full output in
  `data/human_study/analysis_output.txt`.

## Deviations

1. **Case-insensitive scoring (found 2026-11-21, after data collection).**
   The experiment compared the pressed key with "f"/"j" case-sensitively.
   Three participants had Caps Lock on, so every "same" answer was scored as
   "different" and every attention check as failed, even though their raw
   keys were correct. The raw key is saved for every trial, so
   `study/analyze.py` now scores all keys case-insensitively. This changes
   no rule; it only fixes the scoring. The experiment code was fixed too.
