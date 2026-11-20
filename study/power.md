# Sample-size simulation

Within-subject comparison of false-acceptance rates on hard mismatches. Each
participant contributes 12 hard trials per representation. Participant
tendency to answer "same" varies with SD 1.0 on the logit scale, and item
difficulty varies with SD 0.5. The test is a paired t-test on per-participant
rates at α = 0.0125 (Holm, four comparisons). 2,000 simulated studies per
cell.

| False acceptance (A vs B) | n = 30 | n = 40 | n = 50 | n = 60 |
| ------------------------- | ------ | ------ | ------ | ------ |
| 15% vs 30%                | 0.96   | 1.00   | 1.00   | 1.00   |
| 20% vs 30%                | 0.60   | 0.76   | 0.86   | 0.92   |
| 20% vs 35%                | 0.91   | 0.98   | 1.00   | 1.00   |

Forty participants detect differences of 15 percentage points reliably.
Differences of 10 points need about 50 to 60. We plan 48 included
participants.

These numbers depend on the assumed variability. Re-run the simulation with
the variances estimated from the pilot before the main study.
