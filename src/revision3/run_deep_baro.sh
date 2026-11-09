#!/bin/sh
# Revision 3, audit issue 18: deep imputers on the barometric-corrected DO (post hoc), one chain per process.
# src/revision/deep_baselines.py hard-codes data/clean/usgs/. Run in-process through src/revision3/with_baro.py it
# crashed in torch (segmentation fault; three times on 2026-11-05), while the unwrapped script reproduced the
# October McKenzie output bit for bit the same day. So the script is run UNCHANGED, from a mirror folder in which
#   src             -> junction to Paper2/src
#   data/clean/usgs -> junction to Paper2/data/clean/usgs_baro
# (created with mklink /J; REMOVE THE JUNCTIONS with rmdir, never a recursive delete, which would follow them).
# Resumable: finished chains are skipped. Usage (from Paper2/): sh src/revision3/run_deep_baro.sh
P=$(pwd)
O=$P/results/revision3/rerun/deep
mkdir -p $O
cd results/revision3/mirror || exit 1
for c in mckenzie monongahela youghiogheny schuylkill clackamas klamath tualatin illinois delaware; do
  if [ -f $O/deep_$c.csv ]; then echo "skip $c"; continue; fi
  "$P/.venv_deep/Scripts/python" -I src/revision/deep_baselines.py "$O" $c > "$O/log_$c.txt" 2>&1
  if [ -f $O/deep_$c.csv ]; then echo "deep $c done"; else echo "deep $c FAILED"; fi
done
echo DEEP_ALL_END
