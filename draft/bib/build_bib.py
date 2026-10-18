"""Build draft/refs.bib from (1) BibTeX fetched from doi.org (fetched.bib), cleaned; (2) explicit
corrections, each listed below with its reason; (3) manual entries for sources without a usable DOI,
each built from the PDF's first page; (4) entries copied unchanged from Paper 1 (from_paper1.bib).
Usage (from Paper2/draft/bib): python -I build_bib.py  -> ../refs.bib
"""
import re

KEEP = ["author", "title", "journal", "booktitle", "volume", "number", "pages", "year", "doi", "note",
        "howpublished", "publisher", "organization", "institution"]

# corrections to registry data (field -> value), with reasons
FIX = {
    "ledinh2007design": {"author": "Le Dinh, Tuan and Hu, Wen and Sikka, Pavan and Corke, Peter and Overs, Leslie and Brosnan, Stephen"},  # surname is "Le Dinh"
    "langendoen2006murphy": {"booktitle": "Proc. 20th IEEE Int. Parallel and Distributed Processing Symp. (IPDPS)",
                             "title": "Murphy Loves Potatoes: Experiences from a Pilot Sensor Network Deployment in Precision Agriculture",
                             "pages": "8 pp."},                                                     # HTML escape; title case
    "peterson2010mixed": {"author": "Peterson, Erin E. and Ver Hoef, Jay M.",
                          "title": "A mixed-model moving-average approach to geostatistical modeling in stream networks"},  # surname "Ver Hoef"; non-ASCII hyphens
    "kyrgyzstan2025weather": {"title": "From mountains to data: low-cost weather stations in {Kyrgyzstan's} challenging terrain",
                              "note": "Art. no. 1505375"},                                           # curly apostrophe; article number
    "murphy2021arctic": {"author": "Murphy, Michael J. and Tveito, {\\O}ystein and Kleiven, Eivind Flittie and Rais, Issam and Soininen, Eeva M. and Bj{\\o}rndalen, John Markus and Anshus, Otto"},
    "bhatia2020loed": {"title": "{LoED}: The {LoRaWAN} at the Edge Dataset",
                       "booktitle": "Proc. 3rd Workshop on Data: Acquisition To Analysis (DATA '20)"},
    "nikseresht2025uva": {"title": "Dataset: Long-term {LoRaWAN} Communication Metadata from an Urban Deployment",
                          "booktitle": "Proc. 12th ACM Int. Conf. Systems for Energy-Efficient Buildings, Cities, and Transportation (BuildSys '25)"},
    "brzozowski2018lessons": {"booktitle": "Wired/Wireless Internet Communications (WWIC 2018), LNCS vol. 11618"},
    "efron1979bootstrap": {"pages": "1--26"},                                                        # pages missing in registry record
    "ugwuanyi2021developing": {"title": "Survey of {IoT} for Developing Countries: Performance Analysis of {LoRaWAN} and Cellular {NB-IoT} Networks",
                               "note": "Art. no. 2224"},
    "azari2019nbiot": {"title": "On the Latency-Energy Performance of {NB-IoT} Systems in Providing Wide-Area {IoT} Connectivity"},
    "cheng2013stcdg": {"title": "{STCDG}: An Efficient Data Gathering Algorithm Based on Matrix Completion for Wireless Sensor Networks"},
    "ingelrest2010sensorscope": {"title": "{SensorScope}: Application-specific sensor network for environmental monitoring",
                                 "pages": "17:1--17:32"},
    "mcdonald2007sendt": {"title": "Sensor Network with Delay Tolerance ({SeNDT})"},
    "kong2014dataloss": {},
    "huang2019retransmit": {"booktitle": "Proc. IEEE Int. Conf. Communications (ICC)"},
    "luo2009cdg": {"booktitle": "Proc. 15th Annu. Int. Conf. Mobile Computing and Networking (MobiCom)"},
    "zhao2003understanding": {"booktitle": "Proc. 1st Int. Conf. Embedded Networked Sensor Systems (SenSys)"},
    "puluckul2025subarctic": {"booktitle": "Proc. IEEE Wireless Communications and Networking Conf. (WCNC)"},
    "ledinh2007design_bt": {},
}
FIX["ledinh2007design"]["booktitle"] = "Proc. 32nd IEEE Conf. Local Computer Networks (LCN)"
FIX["murphy2021arctic"]["booktitle"] = "Proc. IEEE/ACM 21st Int. Symp. Cluster, Cloud and Internet Computing (CCGrid)"
FIX["chang2023deepcs"] = {"note": "Art. no. 17"}
FIX["piao2014lowrank"] = {}
FIX["ingelrest2010sensorscope"]["author"] = ("Ingelrest, Fran{\\c{c}}ois and Barrenetxea, Guillermo and Schaefer, Gunnar and "
                                             "Vetterli, Martin and Couach, Olivier and Parlange, Marc")   # LaTeX escape for the cedilla

# revision references: acronyms protected from IEEEtran's lower-casing of titles
FIX["du2023saits"] = {"title": "{SAITS}: Self-Attention-Based Imputation for Time Series"}
FIX["nie2024imputeformer"] = {"title": "{ImputeFormer}: Low Rankness-Induced Transformers for Generalizable Spatiotemporal Imputation",
                              "booktitle": "Proc. 30th ACM SIGKDD Conf. Knowledge Discovery and Data Mining (KDD)"}
FIX["marcelis2017dare"] = {"title": "{DaRe}: Data Recovery through Application Layer Coding for {LoRaWAN}",
                           "booktitle": "Proc. 2nd Int. Conf. Internet-of-Things Design and Implementation (IoTDI)"}
FIX["huang2020harq"] = {"title": "Real-Time Remote Estimation With Hybrid {ARQ} in Wireless Networked Control"}
FIX["jing2024casper"] = {"booktitle": "Proc. 33rd ACM Int. Conf. Information and Knowledge Management (CIKM)"}

RENAME = {"kyrgyzstan2025weather": "zennaro2025kyrgyzstan"}
EXCLUDE = ["adumanu2026code", "adumanu2026prediction"]

MANUAL = r"""
@inproceedings{cao2020stemgnn,
  author    = {Cao, Defu and Wang, Yujing and Duan, Juanyong and Zhang, Ce and Zhu, Xia and Huang, Congrui and Tong, Yunhai and Xu, Bixiong and Bai, Jing and Tong, Jie and Zhang, Qi},
  title     = {Spectral Temporal Graph Neural Network for Multivariate Time-series Forecasting},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  volume    = {33},
  pages     = {17766--17778},
  year      = {2020}}

@techreport{lora2016spec102,
  author      = {{LoRa Alliance Technical Committee}},
  title       = {{LoRaWAN} Specification v1.0.2},
  institution = {LoRa Alliance},
  year        = {2016},
  note        = {Sec.~18.4, Data-rate adaptation during message retransmissions}}

@techreport{lora2020spec104,
  author      = {{LoRa Alliance Technical Committee}},
  title       = {{LoRaWAN} {L2} 1.0.4 Specification ({TS001-1.0.4})},
  institution = {LoRa Alliance},
  year        = {2020},
  note        = {Sec.~4.3.1.3, Retransmission procedure; Sec.~5.3, LinkADRReq (NbTrans)}}

@manual{winbond2018w25q128jv,
  organization = {Winbond Electronics},
  title        = {{W25Q128JV} 3{V} 128{M}-bit Serial Flash Memory, Datasheet, Rev. {F}},
  year         = {2018},
  note         = {Sec.~9.4 (DC characteristics) and AC electrical characteristics}}
@inproceedings{cini2022grin,
  author    = {Cini, Andrea and Marisca, Ivan and Alippi, Cesare},
  title     = {Filling the {G\_ap\_s}: Multivariate Time Series Imputation by Graph Neural Networks},
  booktitle = {Proc. Int. Conf. Learning Representations (ICLR)},
  year      = {2022},
  note      = {arXiv:2108.00298}}

@inproceedings{marisca2022spin,
  author    = {Marisca, Ivan and Cini, Andrea and Alippi, Cesare},
  title     = {Learning to Reconstruct Missing Data from Spatiotemporal Graphs with Sparse Observations},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  volume    = {35},
  year      = {2022},
  doi       = {10.52202/068431-2324}}


@inproceedings{sun2026overlapping,
  author    = {Sun, Bowen and Pappas, Nikolaos},
  title     = {Resource-Constrained Semantic-Aware Remote Estimation with Overlapping Sensor Coverage},
  booktitle = {Proc. ACM MobiHoc},
  year      = {2026},
  note      = {to appear; arXiv:2609.07563}}

@misc{bhatia2020loeddata,
  author       = {Bhatia, Laksh and Breza, Michael and Marfievici, Ramona and McCann, Julie A.},
  title        = {{LoED}: The {LoRaWAN} at the Edge Dataset},
  howpublished = {Zenodo},
  year         = {2020},
  doi          = {10.5281/zenodo.4121430}}

@misc{nikseresht2025uvadata,
  author       = {Nikseresht, Fateme and Sobral, Victor Ariel Leal and Goodall, Jonathan L. and Campbell, Bradford},
  title        = {Long-term {LoRaWAN} Communication Metadata from an Urban Deployment},
  howpublished = {University of Virginia Dataverse (LibraData)},
  year         = {2025},
  doi          = {10.18130/V3/RFTICK}}

@techreport{lora2021rp002,
  author      = {{LoRa Alliance Technical Committee Regional Parameters Workgroup}},
  title       = {{RP002-1.0.3 LoRaWAN} Regional Parameters},
  institution = {LoRa Alliance},
  year        = {2021}}

"""


def parse_oneline(s):
    """Registry BibTeX (one entry per line, fields as key={value})."""
    out = {}
    for line in [l.strip() for l in s.split("\n") if l.strip().startswith("@")]:
        m = re.match(r"@(\w+)\{([^,]+),(.*)\}\s*$", line)
        typ, key, body = m.group(1), m.group(2), m.group(3)
        fields, i = {}, 0
        while i < len(body):
            m2 = re.match(r"\s*,?\s*([A-Za-z]+)\s*=\s*", body[i:])
            if not m2:
                break
            name = m2.group(1).lower(); i += m2.end()
            if body[i] == "{":
                depth, j = 0, i
                while True:
                    if body[j] == "{": depth += 1
                    elif body[j] == "}":
                        depth -= 1
                        if depth == 0: break
                    j += 1
                fields[name] = body[i + 1:j]; i = j + 1
            else:
                m3 = re.match(r"([^,]+)", body[i:]); fields[name] = m3.group(1).strip(); i += m3.end()
        out[key] = (typ, fields)
    return out


def clean(v):
    v = v.replace("\u2013", "--").replace("\u2014", "--").replace("&amp;", "\\&").replace("\u2010", "-")
    v = v.replace("\u2019", "'").replace("\u2032", "'")
    # accented letters in author names of the revision's references (Cote, Alarcon): LaTeX escapes
    v = v.replace("\u00e9", "{\\'e}").replace("\u00f4", "{\\^o}").replace("\u00f3", "{\\'o}").replace("\u00e7", "{\\c{c}}")
    return v


def main():
    ents = parse_oneline(open("fetched.bib", encoding="utf-8").read())
    blocks = ["% Built by build_bib.py (DOI registry + listed corrections + manual entries + Paper 1 entries)."]
    for key, (typ, f) in ents.items():
        f = {k: clean(v) for k, v in f.items() if k in KEEP}
        if "doi" in f:
            f["doi"] = f["doi"].upper() if f["doi"].lower().startswith("10.") and False else f["doi"]
        f.update(FIX.get(key, {}))
        if typ == "inbook":
            typ = "inproceedings"
        k2 = RENAME.get(key, key)
        lines = [f"@{typ}{{{k2},"] + [f"  {n:9s} = {{{f[n]}}}," for n in KEEP if n in f]
        lines[-1] = lines[-1].rstrip(",")
        blocks.append("\n".join(lines) + "}")
    blocks.append(MANUAL.strip())
    # Paper 2 is a standalone submission: nothing from Paper 1 itself (its manuscript or code record) is cited
    p1 = open("from_paper1.bib", encoding="utf-8").read().strip()
    p1 = "\n\n".join(e for e in re.split(r"\n\s*\n(?=@)", p1) if not re.match(r"@\w+\{(%s)," % "|".join(EXCLUDE), e.strip()))
    blocks.append(p1)
    out = "\n\n".join(blocks) + "\n"
    for bad in ("\u2013", "&amp;", "\u2010", "\u2032"):
        assert bad not in out, bad
    assert all(ord(c) < 128 for c in out), "non-ASCII character left in refs.bib"
    open("../refs.bib", "w", encoding="utf-8").write(out)
    keys = re.findall(r"^@\w+\{([^,]+),", out, re.M)
    assert len(keys) == len(set(keys)), "duplicate keys"
    assert not set(keys) & set(EXCLUDE), "a Paper 1 entry is still in refs.bib"
    print(f"{len(keys)} entries written: " + ", ".join(sorted(keys)))


if __name__ == "__main__":
    main()
