# Reproduction package: Outage-Aware Reporting and Loss Recovery for Energy-Efficient River Water-Quality Telemetry over LPWANs

This package regenerates every number, table and figure in the paper from the input data. Prepared for release at submission (review item M15); the authors upload it to a public archive and cite its DOI in the paper.

## Contents

| Path | What |
|---|---|
| `src/` | All code (Python). `src/paper/paper_numbers.py` writes every number in the paper as a LaTeX macro with its source file. |
| `tests/` | Unit tests (`python -m pytest tests -q`). |
| `docs/DESIGN_EVAL_PLAN.md` | Development plan for the design evaluation (2023 data), with deviations D1–D5. |
| `docs/CONFIRMATORY_PLAN.md`, `docs/CONFIRMATORY_FREEZE.txt` | Plan of the held-out 2024 evaluation, and SHA-256 hashes of the code frozen before the 2024 data were downloaded. `python -I src/confirm/freeze.py check` verifies them. |
| `release/requirements-lock.txt` | Exact package versions of the analysis environment (Python version in `python-version.txt`). |
| `release/requirements-deep-lock.txt` | Separate environment for the deep imputation baselines (PyTorch CPU, PyPOTS). |
| `release/CHECKSUMS.sha256` | SHA-256 of every input file used. |
| `release/weija_delivery_trace.csv` | Weija deployment: timestamps of every record per stream and probe, whether the received file flagged it as imputed, and whether the paper counts it as a genuine delivery. No water-quality values. This is all the delivery analysis uses from Weija. |

## Data

| Dataset | Source | How to obtain |
|---|---|---|
| USGS NWIS instantaneous values, 2023 (development) and 2024 (held-out) | U.S. Geological Survey | `python -I src/data/fetch_usgs.py <site> <start> <end>`; sites in `results/scoping/design_site_eligibility.csv` and `results/confirm/eligibility_2024.csv`; cleaning `src/data/clean_usgs.py` (approved values only). USGS revises data; compare with `CHECKSUMS.sha256`. |
| InWaterSense | Ahmedi et al., Mendeley Data, doi:10.17632/krzv3g6d5f.1 | download; cleaned cycles via the scripts in `src/data/` |
| LoED | Bhatia et al., Zenodo, doi:10.5281/zenodo.4121430 | download `LoED_full.zip` into `data/loed_full/` |
| UVA LoRaWAN | Nikseresht et al., UVA Dataverse, doi:10.18130/V3/RFTICK | download the parquet files into `data/uva_lorawan/` |
| Weija | provided by the deployment's operators | raw values not redistributed; the delivery trace above is |

## Order of runs

1. Scoping results: `sh src/reproduce_scoping.sh` (gap records, models, LoRaWAN analyses, river chains, loss handling).
2. Development design evaluation (2023): `python -I src/confirm/run_confirm.py data/clean/usgs results/scoping/design_site_eligibility.csv results/confirm/2023_dev 0`.
3. Held-out evaluation (2024): fetch and clean 2024, `src/confirm/eligibility.py`, then `run_confirm.py ... results/confirm/2024 2024`; verdicts with `src/confirm/analyse_confirm.py`.
4. Revision analyses: the scripts in `src/revision/` (queue in `src/revision/run_queue.sh`).
5. Paper: `sh draft/build.sh`.

## Seeds

Every random choice is seeded in code: per-site seeds are derived from the USGS site number (development: site number; held-out: site number + 2024); event injection uses seed 0 per site; the records' replay uses 20261011; revision analyses use 20261017 unless stated in the script.
