"""Revision 3: the paper's figures from the corrected post hoc runs (src/paper/make_figures.py, unchanged).

Applies the audit corrections and the redirect table of src/revision3/corrected_numbers.py, then runs
make_figures.py as its own __main__. Figures are written to draft/figs/ (the frozen-model figures are kept in
results/revision3/draft_figs_backup/).
Usage (from Paper2/): python -I src/revision3/run_figures.py
"""
import runpy
import sys

sys.path.insert(0, "src")
from revision3 import corrected  # noqa: E402
from revision3 import corrected_numbers as CN  # noqa: E402

corrected.apply()
CN.install()
sys.path.insert(0, "src/paper")
runpy.run_path("src/paper/make_figures.py", run_name="__main__")
assert "results/confirm/an2024_" in CN.USED and "results/confirm/2024/" in CN.USED
print("FIGURES_DONE; redirected:", sorted(CN.USED))
