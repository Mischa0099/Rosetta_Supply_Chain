#!/usr/bin/env bash
# Regenerates all synthetic data, ontology CSVs, and demo results.
# Run from the repository root:  bash run_all.sh
set -euo pipefail
pip install pandas faker --break-system-packages -q 2>/dev/null || pip install pandas faker -q
mkdir -p docs contracts generators/state
for d in erp_a erp_b logistics iot ontology_core ontology_goods ontology_manufacturing ontology_services ontology_graph governance; do
  mkdir -p "csv/$d"
done
for s in generators/0[1-9]_*.py generators/1[0-5]_*.py; do
  echo "== $s"; python3 "$s"
done
