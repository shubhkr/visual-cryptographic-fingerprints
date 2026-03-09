#!/usr/bin/env bash
# Reproduce all experimental results from the paper.
# Usage: bash experiments/run_experiments.sh
# Expected runtime: ~3 minutes on a modern laptop.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Visual Cryptographic Fingerprints — Experiment Reproduction ==="
echo ""
echo "Working directory: $REPO_DIR"
echo "Start time: $(date)"
echo ""

cd "$REPO_DIR"

echo "[1/2] Installing dependencies..."
pip install -q -r requirements.txt
echo "      Done."
echo ""

echo "[2/2] Running prototype (collision tests + example generation)..."
PYTHONUNBUFFERED=1 python src/vcf_prototype.py
echo ""

echo "=== All experiments complete ==="
echo "End time: $(date)"
echo ""
echo "Results written to:"
echo "  - vcf_outputs/collision_results.json  (raw metrics)"
echo "  - vcf_outputs/examples/               (sample fingerprints)"
echo ""
echo "To copy results into experiments/results/:"
echo "  cp vcf_outputs/collision_results.json experiments/results/"
