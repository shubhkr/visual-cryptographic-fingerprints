#!/usr/bin/env bash
# Reproduce every experiment in the paper (specification v2).
# Usage: bash experiments/run_experiments.sh
# Runtime: several hours on a 2-core machine; the 2^20 searches dominate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

echo "=== Visual Cryptographic Fingerprints: experiment reproduction (spec v2) ==="
echo "Start: $(date)"

pip install -q -r requirements.txt

run() { echo; echo "--- $* ---"; PYTHONUNBUFFERED=1 python experiments/run_v2.py "$@"; }

run main
run adaptive
run scalectl
run sweep
run symmetry
echo; echo "--- matched-pair benchmark ---"
python experiments/measure_scale.py --output experiments/results/scale_sensitivity.json

for v in randomwalk cellular voronoi cellular_nosym; do
  run scale "$v"
done

echo
echo "Results written to experiments/results/v2_*.json"
echo "End: $(date)"
