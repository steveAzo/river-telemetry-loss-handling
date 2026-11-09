"""Revision 3, audit issue 12: the probing-schedule oracle bound (src/rescoping/headroom.py) with the corrected model.

headroom.py is run unchanged with the audit corrections applied (failed-probe energy from the corrected radio model)
and its denominator, the design's energy per day, read from the corrected held-out run (an2024c_energy.csv) through
the redirect table of src/revision3/corrected_numbers.py. Output: results/revision3/rerun/headroom_{frontier,summary}.csv.
Usage (from Paper2/): python -I src/revision3/run_headroom.py
"""
import sys

sys.path.insert(0, "src")
from revision3 import corrected  # noqa: E402
from revision3 import corrected_numbers as CN  # noqa: E402

corrected.apply()
CN.install()
from rescoping import headroom as H  # noqa: E402

H.OUT = "results/revision3/rerun"
H.main()
assert "results/confirm/an2024_" in CN.USED, "the design energy was not read from the corrected run"
print("HEADROOM_DONE")
