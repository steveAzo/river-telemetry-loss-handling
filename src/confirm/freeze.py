"""Freeze (or check) the code of the confirmatory evaluation (docs/CONFIRMATORY_PLAN.md §8).

  python -I src/confirm/freeze.py freeze   writes docs/CONFIRMATORY_FREEZE.txt (UTC time + SHA-256 per file)
  python -I src/confirm/freeze.py check    exits 1 if any frozen file has changed since
"""
import datetime
import hashlib
import sys
from pathlib import Path

FILES = ["docs/CONFIRMATORY_PLAN.md",
         "src/confirm/run_confirm.py", "src/confirm/analyse_confirm.py", "src/confirm/eligibility.py",
         "src/design/sitedata.py", "src/design/inject.py", "src/design/detector.py",
         "src/design/run_design_eval.py", "src/design/run_sensitivity.py",
         "src/energy/loss_handling.py", "src/energy/model.py", "src/energy/params.py",
         "src/data/fetch_usgs.py", "src/data/clean_usgs.py",
         "data/clean/inws_cycles.csv", "data/weija_raw/conductivity_cleaned_records.csv",
         "data/uva_lorawan/lorawan_combined_dataset.parquet"]
OUT = Path("docs/CONFIRMATORY_FREEZE.txt")


def digest(f):
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(mode):
    if mode == "freeze":
        if OUT.exists():
            sys.exit(f"{OUT} exists: the code is already frozen (a change is a deviation, CONFIRMATORY_PLAN §9)")
        lines = [f"frozen {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}"]
        lines += [f"{digest(f)}  {f}" for f in FILES]
        OUT.write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
    else:
        bad = [f for line in OUT.read_text().splitlines()[1:] for h, f in [line.split("  ", 1)] if digest(f) != h]
        if bad:
            print("CHANGED since the freeze:\n  " + "\n  ".join(bad)); sys.exit(1)
        print("frozen code unchanged")


if __name__ == "__main__":
    main(sys.argv[1])
