# Paper 2 draft directory

## Shareable deliverables

The current files to share with the supervisor are in `deliverables/`:

- `Paper2_TGCN_review_copy_v0.3.pdf`: 27-page, single-column, double-spaced review PDF.
- `Paper2_TGCN_review_copy_v0.3.docx`: editable review copy with fixed-width Tables V and VI.
- `Paper2_draft_v0.3.pdf`: IEEE two-column layout PDF.
- `Paper2_draft_v0.3.docx`: editable IEEE-layout Word copy.
- `Paper2_supplement_v0.3.pdf`: supplementary material PDF.
- `Paper2_TGCN_IEEE_LaTeX_submission_v0.3.zip`: Paper 2 source organized with the
  original IEEE TGCN LaTeX template files in a separate `IEEE_template/` folder.

The older source-only archive is retained for reference. The
`Paper2_TGCN_IEEE_LaTeX_submission_v0.3.zip` package is the one to share.

## Source and reproducibility files

The `.tex` files, `refs.bib`, `ieee.csl`, `tables/`, `figs/`, `bib/`, and
`build.sh` are the authoritative source and build inputs. Do not edit generated
PDF or Word files directly; rebuild them from the source.

## Other folders

- `archive/`: superseded v0.1/v0.2 drafts and earlier review output.
- `build/`: LaTeX auxiliary files, logs, and generated intermediate files.

Run `build.sh` from the `Paper2/` directory to regenerate the outputs.
