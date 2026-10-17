#!/bin/bash
# Download 2023 15-min data for the USGS chain sites (PAPER2_SCOPING.md section 4). Resumable: skips sites already saved.
# Montague, Frenchtown, Schuylkill at Norristown and Illinois at Florence are already in data/clean/usgs (from Paper 1).
SITES="01427510 01463500 014670261 01467200 01477050 01474500 05543010 05553700 05559900 05537980 11509370 11509500 420853121505500 14162500 14163900 14203500 14206241 14206694 14207200 14209710 14210000 14211010 03072655 03075070 03081000 03083500"
for s in $SITES; do
  [ -s "data/raw/usgs/${s}_2023-01-01_2023-12-31.csv" ] && { echo "skip $s"; continue; }
  python -I -W ignore src/data/fetch_usgs.py "$s" 2023-01-01 2023-12-31 || echo "FAILED $s"
done
echo ALL DONE
