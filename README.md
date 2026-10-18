# Paper 2: Outage-Aware Reporting and Loss Recovery

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23455071.svg)](https://doi.org/10.5281/zenodo.23455071)
[![GitHub release](https://img.shields.io/github/v/release/steveAzo/river-telemetry-loss-handling)](https://github.com/steveAzo/river-telemetry-loss-handling/releases/tag/v1.0.0)

This repository contains the reproducibility package for:

> **Outage-Aware Reporting and Loss Recovery for Energy-Efficient River
> Water-Quality Telemetry over LPWANs**

The archived release is available on [Zenodo](https://doi.org/10.5281/zenodo.23455071)
and corresponds to [version 1.0.0](https://github.com/steveAzo/river-telemetry-loss-handling/tree/v1.0.0).
The archive is open access and licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Cite this release

Azongo, Stephen. (2026). *steveAzo/river-telemetry-loss-handling: v1.0.0*
[Software]. Zenodo. https://doi.org/10.5281/zenodo.23455071

The DOI above resolves to the immutable archived release. For the latest
development version, use the [GitHub repository](https://github.com/steveAzo/river-telemetry-loss-handling).

Self-contained working directory for Paper 2. **Paper 1 (`../WSN/`) is sealed:** nothing here reads from or writes to it. Code reused from Paper 1 is copied into `src/` first.

| Path | Contents |
|---|---|
| `PAPER2_SCOPING.md` | Initial scoping analysis: premise audit, first experiments, literature map, candidate scopes |
| `papers/` | Literature: `pdf/`, `txt/`, `README.md` (reading order and manual-download list) |
| `data/inws_raw/` | InWaterSense dataset as published (Ahmedi, Mendeley Data, doi:10.17632/krzv3g6d5f.1), copied from Paper 1 |
| `data/weija_raw/` | Weija deployment files as received (Prof Adu-Manu; use allowed 2026-10-11) + the Paper 1 Weija report |
| `data/clean/` | Cleaned inputs, copied from Paper 1 on 2026-10-11: `inws_cycles.csv` (InWaterSense cycles) and `usgs/` (13 USGS sites, 2023) |
| `requirements.txt` | Python packages (Paper 1 versions + pyarrow for the UVA parquet files) |
| `src/scoping/` | Scoping scripts. Run them from this directory, e.g. `python -I src/scoping/usgs_pair_outage.py 01458500 01438500` |
| `results/scoping/` | Scoping outputs |
