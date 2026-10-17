#!/bin/sh
# Heavy revision runs, one at a time (this machine has 3.6 GB RAM). Every step is resumable or skipped when its
# output exists, so the whole queue can be relaunched after an interruption. Run from Paper2/.
set -u
L=results/revision/queue.log
step() { echo "$(date -u +%FT%TZ) start $1" >> $L; }
python -I src/confirm/freeze.py check >> $L 2>&1 || { echo "FROZEN CODE CHANGED: stop" >> $L; exit 1; }
step confirm2024
python -I src/confirm/run_confirm.py data/clean/usgs_2024 results/confirm/eligibility_2024.csv results/confirm/2024 2024 >> results/confirm/run_2024.log 2>&1
step dev2023
python -I src/confirm/run_confirm.py data/clean/usgs results/scoping/design_site_eligibility.csv results/confirm/2023_dev 0 >> results/confirm/run_2023_dev.log 2>&1
step deep
.venv_deep/Scripts/python -I src/revision/deep_baselines.py results/revision/deep >> results/revision/deep_run.log 2>&1
step ack
[ -f results/revision/ack_variant.done ] || { python -I src/revision/run_ack_variant.py results/revision/ack_variant.csv >> results/revision/ack_variant.log 2>&1 && touch results/revision/ack_variant.done; }
step gof
[ -f results/revision/gof_models.csv ] || python -I src/revision/outage_gof.py results/revision/gof 200 > results/revision/gof.log 2>&1
step mc
[ -f results/revision/energy_mc_summary.csv ] || python -I src/revision/energy_mc.py results/revision/energy_mc 100 > results/revision/energy_mc.log 2>&1
echo "$(date -u +%FT%TZ) QUEUE DONE" >> $L
