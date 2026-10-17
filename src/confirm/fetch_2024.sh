#!/bin/sh
# Download the held-out 2024 data for every development candidate site (CONFIRMATORY_PLAN §1). Run from Paper2/.
for f in data/clean/usgs/*.csv; do
  s=$(basename "$f" .csv)
  if [ -f "data/raw/usgs/${s}_2024-01-01_2024-12-31.csv" ]; then echo "have $s"; continue; fi
  python -I src/data/fetch_usgs.py "$s" 2024-01-01 2024-12-31 || echo "FAILED $s"
done
