"""Revision 3: post hoc sensitivity run of the design evaluation with the audit corrections (docs/AUDIT3.md).

Applies, at run time, the corrected host and sensing power (corrected.apply(), audit issue 1) and reads the
barometric-corrected DO data (do_baro.py, audit issue 18). Everything else is the frozen confirmatory code
(src/confirm/run_confirm.py), with the same eligibility files and seeds as the original runs:
  2023 development: data/clean/usgs_baro,      results/scoping/design_site_eligibility.csv, salt 0
  2024 held out:    data/clean/usgs_2024_baro, results/confirm/eligibility_2024.csv,       salt 2024
Outputs: results/revision3/corrected_2023_dev, results/revision3/corrected_2024 (resumable: finished sites are
skipped). These are labelled post hoc; the confirmatory verdicts stay those of results/confirm/2024.
Usage (from Paper2/): python -I src/revision3/run_corrected.py [2023|2024|both]
"""
import json
import os
import sys

sys.path.insert(0, "src")
from revision3 import corrected  # noqa: E402  (also puts src/design and src/confirm on the path)

RUNS = {
    "2023": ("data/clean/usgs_baro", "results/scoping/design_site_eligibility.csv", "results/revision3/corrected_2023_dev", "0"),
    "2024": ("data/clean/usgs_2024_baro", "results/confirm/eligibility_2024.csv", "results/revision3/corrected_2024", "2024"),
}


def main(which):
    change = corrected.apply()
    import run_confirm
    os.makedirs("results/revision3", exist_ok=True)
    with open("results/revision3/corrections_applied.json", "w", encoding="utf-8") as f:
        json.dump({**change, "do": "barometric correction, src/revision3/do_baro.py"}, f, indent=1)
    for year in (("2023", "2024") if which == "both" else (which,)):
        clean, elig, out, salt = RUNS[year]
        print(f"=== {year}: {clean} -> {out} (salt {salt})", flush=True)
        run_confirm.main(clean, elig, out, salt)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "both")
