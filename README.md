# Governance pipeline and quality audit for a longitudinal multi-source health-examination dataset

Companion code and governance artefacts for the Scientific Data Data Descriptor:
*"A longitudinal health examination dataset with 28.9 million quality-controlled records."*

**Authors**: Liang Zhou, Zhenkai Ma, Dan Zhou, Gang Xu, Hui Wang

This repository openly shares everything required to audit and reproduce the
governance decisions reported in the Descriptor — the cleaning pipeline, the
synthetic fault-injection harness, the text-field scanners, the audit tables,
and the figure-generation code. It deliberately contains **no individual-level
records**: the cleaned and mirror data layers are distributed separately under
controlled access (see *Data availability*).

## Repository contents

```
├── code/                            Analysis and governance code (Python ≥ 3.10; Node.js ≥ 18)
│   ├── G01–G09_*.py, G01a_*.js      Cleaning pipeline: H/PG/PD source databases and mirror tables
│   ├── run_all.py                   End-to-end pipeline driver
│   ├── A00_impact_assessment.py     Cleaning-impact assessment
│   ├── m2_framework.py, m2_run.py   Synthetic column-shift injection harness (2,400 case-origin replicates)
│   ├── make_figures_sd.py           Generates Figs. 1–3 from released artefacts
│   ├── verify_manuscript_numbers.py Deterministic verification of every number in the manuscript
│   ├── post_governance_audit.py     Post-governance residual audit
│   ├── B36_full_domain_scan.js      Text-field full-domain scanner (template displacement, cell contamination)
│   ├── B36c_chain_verify.js         Text-field chain verification
│   └── B51b_persist_scan.py         Unit-aware persistent-defect re-screen (mmol/L vs mg/dL vs bare values)
├── docs/                            Governance charter (rule charter, single authoritative source) and
│                                    per-database governance reports
├── results/                         Machine-readable governance artefacts:
│   ├── DATA_MANIFEST_v3.5.json      Frozen-release manifest (lineage, known defects, SHA-256 fingerprints)
│   ├── m2_*.csv/.txt/.gz            Injection-validation outputs (grid summary, origin coverage, replicates,
│   │                                blind 2022 re-detection, PD negative control, portability, wave extrapolation)
│   ├── audit_residuals_libB/libC.csv  Post-governance residual rows (library B: 2 rows; library C: none)
│   ├── audit_rule_field_coverage.csv  Rule × field coverage matrix
│   ├── post_governance_audit_report.md
│   ├── B51b_D008_D016_report.md     Persistent-defect re-screen report (D-008/D-016 closure)
│   └── B36c_chain_verify.json       Text-field chain verification result
└── figures/sd/                      Figs. 1–3 (PNG + PDF)
```

## Reproduction

```bash
# environment
pip install pandas numpy matplotlib psycopg2 openpyxl xlrd   # PostgreSQL required for pipeline stages
node --version                                                # ≥ 18 for the B36 scanners

# 1. cleaning pipeline (writes audit tables and the runtime governance report)
python code/run_all.py

# 2. synthetic injection validation
python code/m2_run.py

# 3. post-governance audit
python code/post_governance_audit.py

# 4. regenerate figures from released artefacts
python code/make_figures_sd.py
```

Pipeline stages read the source examination exports at `<institution-path>`
(removed from this copy; substitute your own database exports). The injection
harness, audit tooling, and figure generation run entirely on the artefacts in
`results/` and require no institutional data.

`code/verify_manuscript_numbers.py` re-derives every quantitative claim in the
manuscript from the artefacts in `results/` and exits non-zero on any mismatch.

## Data availability

The cleaned analysis layer, row-identical mirror layers, and laboratory long
table (DR1–DR4) contain de-identified but individual-level human data and are
available under **controlled access** through the institutional data-access
committee. Requests are reviewed for compliant secondary use. No individual-level
records, identifier mappings, or PII scans are included in this repository.

## Ethics

Secondary analysis of de-identified, routinely collected examination records was
determined exempt from ethical review by the Public Health and Nursing Research
Ethics Committee of Shanghai Jiao Tong University School of Medicine (exemption
opinion dated 8 September 2026). The identifier key resides outside the
analytical environment and never enters any deliverable.

## License

Code in `code/` is released under the MIT License (see `LICENSE`).
Governance documents (`docs/`), audit artefacts (`results/`), and figures
(`figures/`) are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Citation

If you use this resource, please cite the Data Descriptor and the archived code
release (DOI to be assigned on Zenodo publication).
