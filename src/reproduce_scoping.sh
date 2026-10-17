#!/bin/bash
# Regenerate every scoping result used by the paper into results/rerun_check/ (from Paper2/).
set -e
O=results/rerun_check
P="python -I -W ignore"
$P src/scoping/inws_outages.py $O/inws_outages.csv > $O/inws_outages.log
$P src/scoping/weija_outages.py data/weija_raw > $O/weija_outages.log
$P src/scoping/outage_models.py $O/outage_models.csv > $O/outage_models.log
$P src/scoping/outage_tail_check.py > $O/outage_tail_check.log
$P src/scoping/uva_loss.py $O/uva_loss > $O/uva_loss.log
for c in "delaware 01427510,01438500,01458500,01463500" "illinois 05537980,05543010,05553700,05559900,05586300" "tualatin 14203500,14206241,14206694,14207200" "clackamas 14209710,14210000,14211010" "mckenzie 14162500,14163900" "monongahela 03072655,03075070" "youghiogheny 03081000,03083500" "schuylkill 01473500,01474500" "klamath 420853121505500,11509370,11509500"; do
  set -- $c; $P src/scoping/chain_outage.py $1 $2 $O/chain_$1.csv > /dev/null
done
$P src/scoping/chain_summary.py $O/chain_*.csv > $O/chain_summary.log
$P src/energy/run_loss_handling.py $O/loss_handling.csv > $O/loss_handling.log
$P src/scoping/loed_full.py data/loed_full/LoED_full.zip $O/loed_full > $O/loed_full.log
echo ALL DONE > $O/done.flag
