# Preregistration: Can people tell visual fingerprints of AI artifacts apart?

Draft for OSF or AsPredicted. Fill in the items marked **ACTION** before you
register, and do not change the design after data collection starts.

## 1. Data collection status

No data have been collected for this study when this document is registered.
The stimuli (`docs/stimuli.js`, version `vcf-study-v1`) and the analysis
script (`study/analyze.py`) are frozen at the registered commit. **ACTION:**
record the commit hash here.

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
instructed-response attention checks.

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
approval rate of at least 95%. Pay: **ACTION** (at least $12/hour for an
estimated 15 minutes).

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
4. did not complete all 160 main trials.

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

**ACTION:** state the review body and decision (exempt determination, or
approval number). The consent text is in `docs/experiment.js`.
