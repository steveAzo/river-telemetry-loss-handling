#!/bin/sh
# Revision 3, audit issue 18: river-chain and deep reconstruction on the barometric-corrected DO (post hoc).
# Same chains, sites, and code as src/revision/run_chains.sh and the deep run in src/revision/run_queue.sh;
# only the input folder differs (src/revision3/with_baro.py). Outputs: results/revision3/rerun/chains, .../deep.
# Usage (from Paper2/): sh src/revision3/run_reconstruct_baro.sh
set -u
O=results/revision3/rerun/chains
mkdir -p $O results/revision3/rerun/deep
for c in "delaware 01427510,01438500,01458500,01463500" "illinois 05537980,05543010,05553700,05559900,05586300" "tualatin 14203500,14206241,14206694,14207200" "clackamas 14209710,14210000,14211010" "mckenzie 14162500,14163900" "monongahela 03072655,03075070" "youghiogheny 03081000,03083500" "schuylkill 01473500,01474500" "klamath 420853121505500,11509370,11509500"; do
  set -- $c
  [ -f $O/chain_$1.csv ] || python -I -W ignore src/revision3/with_baro.py src/scoping/chain_outage.py $1 $2 $O/chain_$1.csv > /dev/null || exit 1
  echo "chain $1 done"
done
.venv_deep/Scripts/python -I src/revision3/with_baro.py src/revision/deep_baselines.py results/revision3/rerun/deep || exit 1
echo RECON_DONE
