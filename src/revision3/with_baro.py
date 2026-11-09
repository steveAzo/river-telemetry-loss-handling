"""Revision 3, audit issue 18: run an unmodified script on the barometric-corrected DO data.

Scripts that hard-code data/clean/usgs/ (src/scoping/chain_outage.py, src/revision/deep_baselines.py) are run
unchanged, with pandas.read_csv redirected from data/clean/usgs/ to data/clean/usgs_baro/ (same files and columns,
DO corrected, plus p_ratio). Nothing else is changed. Post hoc sensitivity run (docs/AUDIT3.md).
Usage (from Paper2/): python -I src/revision3/with_baro.py <script.py> [args ...]
"""
import runpy
import sys

import pandas as pd

SRC, DST = "data/clean/usgs/", "data/clean/usgs_baro/"
_read_csv = pd.read_csv


def _redirect(path, *a, **k):
    if isinstance(path, str) and path.replace("\\", "/").startswith(SRC):
        path = DST + path.replace("\\", "/")[len(SRC):]
    return _read_csv(path, *a, **k)


def main():
    pd.read_csv = _redirect
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    sys.path.insert(0, script.rsplit("/", 1)[0])      # as when the script is run directly
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
