# Paper 2 literature

`pdf/` holds the open-access PDFs (prefix = number used in `../PAPER2_SCOPING.md` §3), and `txt/` holds their `pdftotext -layout` copies. `download_list.tsv` has the source URL of every entry. `openalex_hits_raw.json` holds the raw search hits.

## Read first

1. 01–02: Huang et al., retransmit or not / HARQ for remote estimation; 03: Nadeem et al., HARQ optimisation (the communication trade-off).
2. 05: Sun & Pappas, MobiHoc '26, remote estimation with overlapping sensor coverage (closest new competitor).
3. 13: SPIN (NeurIPS 2022) and 12: GRIN (ICLR 2022), the state of the art in spatio-temporal imputation (baselines).
4. 26 and 27: stream-network spatial statistics, which define the right notion of "neighbour" on a river.
5. 32: Zhao & Govindan 2003, bursty loss in sensor networks.

## Download status (2026-10-12)

All requested papers are in `pdf/`, except **paper 28** (Jia et al., physics-guided recurrent graph model for river networks, SDM 2021, https://doi.org/10.1137/1.9781611976700.69). It is paywalled with no open copy, and is not needed for the reshaped scope.

Notes per paper: `LITERATURE_NOTES.md`.

**Rule (as in Paper 1):** every citation is verified from the PDF or OpenAlex. The background papers listed in `proposals.md` do not exist and must not be cited. Author names in file names were checked against each PDF's first page on 2026-10-12; four wrong guesses were corrected (03 Nadeem, 17 Bansal, 19 Piao, 33 Le Dinh). SensorScope's first author is Ingelrest (59), not Barrenetxea.
