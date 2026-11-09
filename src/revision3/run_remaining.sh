#!/bin/sh
# Revision 3: the remaining post hoc runs, strictly one at a time (running the deep imputers and the ablation in
# parallel coincided with an unexpected shutdown of this 3.7 GB machine on 2026-11-05). Each step is resumable.
# Usage (from Paper2/): sh src/revision3/run_remaining.sh   -> log lines in results/revision3/remaining.log
L=results/revision3/remaining.log
echo "$(date) start" >> $L
python -I src/revision3/no_batch_ablation.py >> results/revision3/no_batch.log 2>&1 && echo "$(date) no_batch ok" >> $L || { echo "$(date) no_batch FAILED" >> $L; exit 1; }
sh src/revision3/run_deep_baro.sh >> results/revision3/deep_baro3.log 2>&1
grep -q "FAILED" results/revision3/deep_baro3.log && { echo "$(date) deep FAILED" >> $L; exit 1; }
echo "$(date) deep ok" >> $L
python -I src/revision3/run_headroom.py > results/revision3/headroom.log 2>&1 && echo "$(date) headroom ok" >> $L || { echo "$(date) headroom FAILED" >> $L; exit 1; }
echo "REMAINING_DONE" >> $L
