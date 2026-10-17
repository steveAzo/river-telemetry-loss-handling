#!/bin/sh
# Rerun the river-chain reconstruction test with the D5 inclusive tolerance (from Paper2/).
O=results/revision/chains
for c in "delaware 01427510,01438500,01458500,01463500" "illinois 05537980,05543010,05553700,05559900,05586300" "tualatin 14203500,14206241,14206694,14207200" "clackamas 14209710,14210000,14211010" "mckenzie 14162500,14163900" "monongahela 03072655,03075070" "youghiogheny 03081000,03083500" "schuylkill 01473500,01474500" "klamath 420853121505500,11509370,11509500"; do
  set -- $c; python -I -W ignore src/scoping/chain_outage.py $1 $2 $O/chain_$1.csv > /dev/null
done
echo done
