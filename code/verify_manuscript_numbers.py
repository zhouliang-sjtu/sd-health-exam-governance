# -*- coding: utf-8 -*-
"""verify_manuscript_numbers.py — 论文00（Scientific Data 版）稿件数字一致性校验

架构对齐论文04 S09：期望值全部从产物**运行时推导**（M2 结果 CSV/TXT + 治理报告 MD +
审计 CSV），按稿件写法生成期望字符串逐一检索 Manuscript_SciData_v1.md；缺失即 FAIL。
另做护栏：旧废口径数字不得出现（2,080/326 为快照预估口径、566 为 G01b 注释口径、
1,407,195 为 PD 含重复口径——稿件一律用治理落地计数与清洗后口径）。
输出：results/verify_manuscript_report.txt；全 PASS 退出码 0。
用法：python verify_manuscript_numbers.py [稿件路径...]
"""
import os
import re
import sys
import pandas as pd

BASE = r"D:\projects\Paper\论文00-多源体检队列数据治理与质量审计"
RES = os.path.join(BASE, "results")
CLEAN = r"D:\projects\Paper\00-清洗源数据库"
SANXIAN = r"D:\projects\Paper\00-三线探索-多模态动态队列"
MS = os.path.join(BASE, "20_paper-methodology", "Manuscript_SciData_v1.md")

paths = sys.argv[1:] or [MS]
raw = "\n".join(open(p, encoding="utf-8").read() for p in paths)
# 只校验稿件正文——"## 写作备忘（不进稿）"及之后内容不参与（含 566 口径注记等内部信息）
text = raw.split("## 写作备忘")[0]
checks = []


def check(name, needle, in_text=True):
    if "|" in str(needle):
        a, b = str(needle).split("|", 1)
        ok = (a in text and b in text) == in_text
    else:
        ok = (str(needle) in text) == in_text
    checks.append((ok, name, needle if in_text else f"(不得出现) {needle}"))


def src_ok(name, src, needle):
    checks.append((needle in src, name, f"[源] {needle}"))


def src_eq(name, derived, expected):
    checks.append((derived == expected, name, f"[源推导] {derived} == {expected}"))


def med(s):
    return float(pd.Series(s).median())


# ============ 1. M2 grid summary（case-origin 12 格） ============
g = pd.read_csv(os.path.join(RES, "m2_grid_summary.csv"))
gc = g[g.origin == "case"]
check("total reps 2,400", f"{int(gc.reps.sum()):,}")
check("recall med 0.985", f"{med(gc.recall_med):.3f}")
check("recall per-cell min", f"{gc.recall_med.min():.3f}")
check("recall per-cell max", f"{gc.recall_med.max():.3f}")
check("recall p05 0.978", f"{gc.recall_p05.min():.3f}")
check("F1 0.992", f"{med(gc.f1_med):.3f}")
check("spec 1.000", f"{med(gc.spec_med):.3f}")
check("fp med 0 / p95 0", f"{med(gc.fp_med):.0f}|{med(gc.fp_p95):.0f}")
check("blockdet 100%", f"{med(gc.blockdet) * 100:.0f}%")
check("berr med 0 / p90 0", f"{med(gc.berr_med):.0f}|{med(gc.berr_p90):.0f}")
check("repair 0.998", f"{med(gc.repair_acc_med):.3f}")
d3 = gc[(gc.k == 1) & (gc.block == "contig")].sort_values("rate")
check("dmfab 50/248/495",
      " / ".join(f"{med(d3[d3.rate == r].dmfab_med):.0f}" for r in (0.01, 0.05, 0.1)))

# ============ 2. origin coverage（22 起点 × 20 reps） ============
oc = pd.read_csv(os.path.join(RES, "m2_origin_coverage.csv"))
ocm = oc.groupby("origin_col")["recall"].median()
check("origins 22", f"{ocm.size}")
check("origins >=0.95: 14", f"{int((ocm >= 0.95).sum())}")
lipid = ocm[ocm.index.isin(["tg", "hdl", "ldl"])].median()
tumor = ocm[ocm.index.isin(["afp", "cea", "ca199"])].median()
check("lipid blind 0.09", f"{lipid:.2f}")
check("tumor blind 0.00", f"{tumor:.2f}")
check("fpg blind 0.00", f"{ocm.get('fpg', float('nan')):.2f}")
check("tc partial 0.922", f"{ocm.get('tc', float('nan')):.3f}")

# ============ 3. 盲态 2022 / 库C 阴性 / 迁移 / 外推域 ============
bl = open(os.path.join(RES, "m2_blind2022.txt"), encoding="utf-8").read()
check("blind 9,381", re.search(r"flagged (\d+)", bl).group(1).replace(",", ","))
check("blind 9,500", re.search(r"注入真值行: ([\d,]+)", bl).group(1))
bl_flag = int(re.search(r"flagged ([\d,]+)", bl).group(1).replace(",", ""))
bl_true = int(re.search(r"注入真值行: ([\d,]+)", bl).group(1).replace(",", ""))
check("blind recall 0.987（计数直推，防双重舍入）", f"{bl_flag / bl_true:.3f}")
check("blind FP 0", "块外 FP 0" in bl)
src_ok("blind 2022 wave 17,380", bl, "2022 波行数: 17,380")
ng = open(os.path.join(RES, "m2_pd_negative.txt"), encoding="utf-8").read()
neg_n = int(re.search(r"行数: ([\d,]+)", ng).group(1).replace(",", ""))
neg_flag = int(re.search(r"签名阳性行: ([\d,]+)", ng).group(1).replace(",", ""))
check("neg rows 1,389,967", f"{neg_n:,}")
src_eq("neg silent (v1.1 全静默)", neg_flag, 0)
check("neg probes 0", all(
    f"{r}=0" in ng for r in ("r01_shift_probe", "r02_shift_fb")))
pt = pd.read_csv(os.path.join(RES, "m2_pd_portability.csv"))
check("portability recall 0.58", f"{med(pt.recall):.2f}")
check("portability F1 0.72", f"{med(pt.f1):.2f}")
we = pd.read_csv(os.path.join(RES, "m2_wave_extrapolation.csv"))
d1 = we[we.wave_group == "2018-2021"].recall_med.median()
d2 = we[we.wave_group == "2023-2024"].recall_med.median()
check("domain recalls 0.985|0.985", f"{d1:.3f}|{d2:.3f}")

# ============ 4. 治理产物锚（报告文本数字存在性） ============
snap = open(os.path.join(CLEAN, "数据资产快照_v2.1.md"), encoding="utf-8").read()
h_rep = open(os.path.join(CLEAN, "docs", "H_治理报告_20260914.md"), encoding="utf-8").read()
hm_rep = open(os.path.join(CLEAN, "docs", "H_mirror_治理报告_20260914.md"), encoding="utf-8").read()
pg_rep = open(os.path.join(CLEAN, "docs", "PG_治理报告_20260914.md"), encoding="utf-8").read()
pd_rep = open(os.path.join(CLEAN, "docs", "PD_治理报告_v1.1_20260916.md"), encoding="utf-8").read()
charter = open(os.path.join(CLEAN, "治理规范.md"), encoding="utf-8").read()
au = pd.read_csv(os.path.join(SANXIAN, "data", "processed", "audit_fix_counts.csv"),
                 header=None, encoding="utf-8-sig")
au2 = pd.read_csv(os.path.join(SANXIAN, "data", "processed", "audit_row_signatures.csv"),
                  header=None, encoding="utf-8-sig")


def audit_total(prefix, src_df=None):
    """按首列前缀匹配行，取该行数值最大者（=总计）。"""
    df = src_df if src_df is not None else au
    for _, r in df.iterrows():
        if str(r[0]).strip().startswith(prefix):
            nums = pd.to_numeric(r[1:], errors="coerce").dropna()
            return int(nums.max()) if len(nums) else None
    return None


clean_readme = open(os.path.join(CLEAN, "README.md"), encoding="utf-8").read()


def src_eq(name, derived, expected):
    checks.append((derived == expected, name, f"[源推导] {derived} == {expected}"))


src_eq("audit sbp 130", audit_total("sbp<dbp"), 130)
src_eq("audit fpg 14", audit_total("fpg<3.0"), 14)
src_eq("audit ua 131", audit_total("ua<120"), 131)
src_eq("audit hdl 4", audit_total("hdl>tc"), 4)
src_eq("audit ldl 14", audit_total("ldl>tc"), 14)
src_eq("audit tg 5", audit_total("tg>25"), 5)
src_eq("audit bmi 33", audit_total("bmi", au2), 33)
src_ok("snap 568", snap, "568 行为尿 pH 误判")
src_ok("snap 1,678→2,437", snap, "1,678→2,437")
src_ok("snap ST-T 1,545→3,085", snap, "1,545→3,085")
src_ok("snap 598→70,678", snap, "598→70,678")
src_ok("snap 70,716/70,717", snap, "70,716/70,717")
src_ok("snap 2,167万", snap, "2,167 万行")
src_ok("snap 17,380(2022)", snap, "2022=17,380")
src_ok("H rep 122,575", h_rep, "122,575")
src_ok("H rep 30,677", h_rep, "30,677")
src_ok("H rep id ok 30676", h_rep, "'ok': 30676")
src_ok("Hmirror 9396", hm_rep, "移位修复 9396 行")
src_ok("Hmirror 99.95-99.97", hm_rep, "99.95%")
src_ok("PG rep 129,953", pg_rep, "129,953")
src_ok("PG rep 71,209", pg_rep, "71,209")
src_ok("PG rep 51,296", pg_rep, "51,296")
src_ok("PG rep fpg<3=1", pg_rep, "'fpg<3': 1")
src_ok("PG rep ua<120=35", pg_rep, "'ua<120': 35")
src_ok("PG rep fpg 可用 70,678", pg_rep, "fpg 可用 70,678")
src_ok("PD rep fpg 2,072", pd_rep, "fpg<3 置缺 2072")
src_ok("PD rep ua 323", pd_rep, "ua<120 置缺 323")
src_ok("PD rep sbp 52", pd_rep, "sbp<dbp 双置缺 52")
src_ok("PD v1.1 crea 1,676", pd_rep, "crea<20 置缺 1676")
src_ok("PD v1.1 ldl 973", pd_rep, "ldl>tc 置缺 973")
src_ok("PD v1.1 bmi 207", pd_rep, "bmi恒等式 置缺 207")
src_ok("PD v1.1 altast 1", pd_rep, "alt/ast>1500 置缺 1")
src_ok("PD rep hdl 38", pd_rep, "hdl>tc 置缺 38")
src_ok("PD rep tg 33", pd_rep, "tg>25 置缺 33")
src_ok("PD rep ua range 808", pd_rep, "尿酸→ua: 808")
src_ok("PD rep tbil range 627", pd_rep, "总胆红素→tbil: 627")
src_ok("PD rep height range 347", pd_rep, "身高→height: 347")
src_ok("charter 30,676/30,677", charter, "30,676/30,677")
src_ok("charter −17,228", charter, "−17,228 行")
src_ok("charter GB11643", charter, "GB11643-1999")
src_ok("readme 842/563", clean_readme, "842 个检验项目逐项目统计与值域标记")

# ============ 4b. 文本域审计与血缘（2026-09-19 升级节源锚） ============
import json
GOV = r"D:\projects\Paper\00-数据质量核验与治理-20260917"
b36c = json.load(open(os.path.join(GOV, "B36c_chain_verify.json"), encoding="utf-8"))
b50 = open(os.path.join(GOV, "B50_impact_assessment.md"), encoding="utf-8").read()
baobei = open(os.path.join(GOV, "论文00报备记录_20260917.md"), encoding="utf-8").read()
zongkong = open(os.path.join(GOV, "00_问题清单总控.md"), encoding="utf-8").read()
mani = json.load(open(os.path.join(RES, "DATA_MANIFEST_v3.5.json"), encoding="utf-8"))
src_eq("b36c urine rows 7,159", int(b36c["nUrineECG"]), 7159)
src_eq("b36c rad ECG 7,001", int(b36c["radIsECG"]), 7001)
src_eq("b36c reverse 0", int(b36c["ecgColECG"]), 0)
src_eq("b36c chain share 97.8%", round(b36c["ecgColUrine"] / b36c["nUrineECG"] * 100, 1), 97.8)
src_ok("B50 7,038 remap", b50, "7,038")
src_ok("B50 parity 122,574", b50, "122,574")
src_ok("B50 gallstone 1,504", b50, "1,504")
src_ok("B50 kidneycyst 2,181", b50, "2,181")
src_ok("B50 fibroid 165", b50, "165")
src_ok("B50 chronic 5,123", b50, "5,123")
src_ok("B50 urine refill 9,429", b50, "9,429")
src_ok("B50 scattered ~500", b50, "500")
src_ok("ledger 7,180", baobei, "7,180")
src_ok("ledger 7,152", baobei, "7,152")
src_ok("ledger 7,179/7,180", baobei, "7,179/7,180")
src_ok("ledger 97.8%", baobei, "97.8%")
src_ok("总控 bare rebuild 0.433→0.224", zongkong, "0.433→0.224")
src_ok("总控 uprot 11,850→20,916", zongkong, "11,850→20,916")
src_eq("manifest db version v3.5", str(mani.get("database_version")), "v3.5")

# ============ 5. 稿件数字存在性（写法变体兼容；2026-09-17 导师合并版锚点） ============
for name, needle in [
    ("title", "A longitudinal health examination dataset with 28.9 million quality-controlled records"),
    ("abs A", "122,575 person-wave records from 30,677"),
    ("abs B", "71,209 person-years linked to a 21.7-million-row laboratory table"),
    ("abs C", "1,389,967 regional examination records linked to 54,490 mortality records"),
    ("abs workflow", "detect–quantify–repair–verify workflow"),
    ("abs release", "controlled-access cleaned and mirror layers"),
    ("shift 9,396", "9,396 shifted rows, 6.1%"),
    ("568 fab", "568 fabricated positives removed"),
    ("598→70,678", "recovered 70,678 usable records (from 598)"),
    ("4800 injections", "4,800 injections total"),
    ("case recall", "row-level recall was **0.985**"),
    ("case spec", "median specificity **1.000**"),
    ("blind 0.987", "(recall 0.987)"),
    ("tc partial coverage", "partial coverage at the total-cholesterol origin (median recall 0.922)"),
    ("port 50 replicates", "(50 replicates; k=1, r=5%, contiguous blocks)"),
    ("7 waves 2018–2024", "7 annual waves (2018–2024)"),
    ("842 items", "842 distinct item names"),
    ("563 numeric", "563"),
    ("400k chunks", "400,000-row chunks"),
    ("469 questionnaire", "469-column"),
    ("substrate 105,195×24", "105,195 person-wave rows × 24 template positions"),
    ("grid k/r/B", "k ∈ {1, 2}"),
    ("r grid", "r ∈ {1%, 5%, 10%}"),
    ("B=200", "B = 200"),
    ("24 cells", "24 grid cells"),
    ("20 reps/origin", "20 replicates per template position"),
    ("per-cell 0.983–0.986", "0.983–0.986"),
    ("p05 0.978", "0.978"),
    ("boundary zero", "boundary-localisation error **0 rows**"),
    ("repair <0.2%", "below 0.2%"),
    ("domain 0.985|0.984", "recall 0.985; calibration domain 2018–2021: 0.984"),
    ("counterfactual 50/248/495", "50 / 248 / 495"),
    ("4.8% vs 6.1%", "4.8% of shifted rows"),
    ("6.1% hist", "6.1%)"),
    ("14 origins", "recall ≥0.95) for 14 origins"),
    ("lipid 0.09", "recall 0.09"),
    ("port 0.58/0.76", "recall 0.58 at random origins (F1 0.76)"),
    ("blind 9,381 of 9,500", "9,381 of 9,500"),
    ("consist 9,396 census", "historical repair census of 9,396"),
    ("ALT/AST 70,716/70,717", "70,716 / 70,717"),
    ("glucose median 5.55", "median 5.55 mmol/L"),
    ("dedup 129,953→71,209", "129,953 report-level rows to 71,209"),
    ("−17,228", "−17,228 rows"),
    ("checksum 30,676/30,677", "30,676/30,677 checksum passes"),
    ("GB 11643", "GB 11643-1999"),
    ("FPG 7.0/HbA1c 6.5", "FPG ≥ 7.0 mmol/L or HbA1c ≥ 6.5%"),
    ("value fpg A14 C2072 B1", "(A: 14, C: 2,072, B: 1)"),
    ("value ua A131 C323 B35", "(A: 131, C: 323, B: 35)"),
    ("value bp A130 C52", "(A: 130, C: 52)"),
    ("value bmi A33 C207", "(A: 33, C: 207)"),
    ("value crea floor", "creatinine floor (A: 6, B: 4, C: 1,676)"),
    ("value altast ceiling", "transaminase ceiling (A: 3, C: 1)"),
    ("value ldl C973", "C 973"),
    ("neg zero rows claim", "flagged **zero rows**"),
    ("value lipid HDL A4 C38", "HDL > TC: A 4, C 38"),
    ("value lipid LDL A14", "LDL > TC: A 14"),
    ("value lipid TG A5 C33", "TG > 25 mmol/L: A 5, C 33"),
    ("C per-item ranges", "uric acid 808, total bilirubin 627, height 347 rows"),
    ("BUN rule table", "BUN-position >25 and UA-position <90"),
    ("BUN rule methods", "`BUN-position > 25 and UA-position < 90`"),
    ("BUN rationale", "µmol/L-scale creatinine occupies the mmol/L-scale urea field"),
    ("fallback rationale", "mmol/L TC in UA field"),
    ("blind span 104", "104 more than the census"),
    ("dedup master table", "examination-report master table deduplicated 129,953"),
    ("pandas NumPy", "pandas/NumPy"),
    ("DR4 open", "openly deposited"),
    ("Python 3.13", "Python 3.13"),
    # ---- 作者/伦理/基金等红标（2026-09-19 填入后反向校验）----
    ("ph author list filled", "Liang Zhou"),
    ("ph affiliations filled", "School of Public Health, Shanghai Jiao Tong University School of Medicine"),
    ("ph corresponding filled", "huiwang@shsmu.edu.cn"),
    ("ethics heading", "### Ethics statement"),
    ("ethics filled", "exemption opinion dated 8 September 2026"),
    ("ethics committee", "Public Health and Nursing Research Ethics Committee"),
    ("sw impl heading", "### Code availability"),
    ("code access statement", "under an open licence, without access restrictions"),
    ("ack filled", "The authors thank the examination organisations"),
    ("contributions filled", "Conceptualization, Methodology, Software, Data curation"),
    ("competing filled", "The authors declare no competing interests"),
    ("funding filled", "National Natural Science Foundation of China (grant 82630101)"),
    ("funding yfd", "2026ZB0556800"),
    ("funding rfp", "2022YFD2101500"),
    ("funding yg", "YG2025LC14"),
    ("funding no role", "had no role in"),
    ("methods data citations", "governance-artefact record DR4¹²"),
    ("methods DR13-15", "cohort records DR1–DR3¹³–¹⁵"),
    ("ai heading", "### Generative AI assistance"),
    ("ai declaration", "ChatGPT (OpenAI)"),
    ("DR controlled access", "shared under controlled access"),
    ("ph repository", "REPOSITORY CONFIRMATION REQUIRED"),
    ("DR table ref", "governance-artefact record (Table 2)"),
    ("ph doi note", "BEFORE SUBMISSION/PUBLICATION"),
    ("DA heading", "## Data Availability"),
    ("ph DA repo", "INSERT CONTROLLED-ACCESS REPOSITORY"),
    ("CA heading", "## Code Availability"),
    ("open repo github filled", "github.com/zhouliang-sjtu/sd-health-exam-governance"),
    ("zenodo concept doi filled", "10.5281/zenodo.22846134"),
    ("code mit licence filled", "under the MIT licence"),
    ("da ccby licence filled", "under the CC BY 4.0 licence"),
    ("ref12 open filled", "Governance artefacts: signature library, rule charter, audit tables"),
    ("ph dc ctrl", "CONTROLLED-ACCESS REPOSITORY AND DOI/PID REQUIRED"),
    ("BS fault families", "three recurrent fault families"),
    ("BS waves risk", "repeated annual exports create additional operational risks"),
    ("cite 9 drift", "item-name drift⁹"),
    ("cite 10 dedup", "duplication defects¹⁰"),
    ("cite 11 reuse", "reuse¹¹"),
    ("cite 16 usage", "anonymisation practice¹⁶"),
    ("privacy crossref DA", "described in Data Availability"),
    ("ECG first use", "electrocardiogram (ECG)"),
    # ---- 图与 SI 表正文引用（R7-I/F 轮修复）----
    ("fig1 cited", "between waves (Fig. 1)"),
    ("fig2 cited", "structural template shifts (Fig. 2)"),
    ("fig3 cited", "injection ground truth (Fig. 3)"),
    ("S1 cited", "full grid in Table S1"),
    ("S2 cited", "full map in Table S2"),
    ("S3 cited", "implementation mapping in Table S3"),
    ("S4 cited", "artefact inventory in Table S4"),
    ("S5 cited", "per-repair audit samples in Table S5"),
    # ---- 文本域审计与血缘（2026-09-19 升级节）----
    ("text domain heading", "### Text-field domain audit"),
    ("lineage heading", "### Data lineage and reproducible rebuild"),
    ("TV text fault heading", "### Text-field fault family (template displacement and cell-level contamination)"),
    ("matrix scope", "all 186 free-text columns"),
    ("24 suspects", "24 suspect column–wave pairs"),
    ("7,180 src rows", "7,180 source rows"),
    ("7,152 dedup", "7,152 after same-person deduplication"),
    ("own urine 7,179/7,180", "(7,179/7,180)"),
    ("reverse zero", "reverse-direction contamination was zero"),
    ("chain 7,001/7,159 97.8%", "(7,001 of 7,159 urinary rows, 97.8%)"),
    ("remap 7,038", "(7,038 rows)"),
    ("porting regression", "2,000-row classification-porting regression"),
    ("false positive family", "lack domain exclusivity"),
    ("bare rebuild ecg", "from 0.433 to 0.224"),
    ("bare rebuild uprot", "11,850 to 20,916"),
    ("parity 122,574", "(122,574 keys)"),
    ("frozen v3.5 manifest", "frozen v3.5 manifest"),
    ("rule15 matrix", "header-domain × content-domain matrix (186 text columns × 7 waves)"),
    ("scanner distributed", "scanner is distributed with the repository code"),
    ("quantification displaced text", "displaced-text recovery counts"),
    ("scanner in code avail", "the full-column text-domain scanner"),
    ("manifest in code avail", "the frozen-database manifest"),
    ("gallstone 1,504", "gallstone 1,504"),
    ("kidneycyst 2,181", "kidney-cyst 2,181"),
    ("fibroid 165", "fibroid 165 rows"),
    ("chronic 5,123", "5,123 rows"),
    ("urine refill 9,429", "9,429 urinary values"),
    ("scattered 500", "approximately 500 scattered numeric values"),
    ("single-year architecture", "single-year clean-library architecture"),
]:
    check(f"ms.{name}", needle)

# ============ 6. 护栏：旧废口径不得入稿 ============
for name, needle in [
    ("快照预估 2,080", "2,080"),
    ("快照预估 326 行", "326 行"),
    ("G01b 注释 566", "566"),
    ("PD 含重复口径 1,407,195", "1,407,195"),
    ("H 人级旧数 30,678", "30,678"),
    ("旧摘要 70,180", "70,180"),
    ("未用依赖 lifelines", "lifelines"),
    ("未用数据库 MySQL", "MySQL"),
    ("旧残留口径 0.203%", "0.203"),
    ("旧残留口径 2,828", "2,828"),
    ("旧可移植性 F1 0.72", "F1 0.72"),
    # ---- 导师版陈旧口径（2026-09-17 合并裁决：一律禁入）----
    ("旧标题 Silent corruption", "Silent corruption"),
    ("旧审计计数 84", "all 84 checks"),
    ("旧盲态双重舍入 0.988", "0.988"),
    ("旧措辞 indistinguishable", "indistinguishable"),
    ("旧措辞 right-shifted", "right-shifted"),
    ("旧措辞 transfusion-band", "transfusion-band"),
    ("旧 DR2 metabolomics wide view", "metabolomics wide view"),
    ("旧规则1 creatinine-position >25", "creatinine-position >25"),
    ("旧规则1 creatinine-position > 25", "creatinine-position > 25"),
    ("旧平台 Windows or Linux", "Windows or Linux"),
    ("旧 uniform schema", "uniform schema"),
    ("旧摘要 ~28.9 million", "~28.9 million"),
    # ---- 边界政策（2026-09-19）：标注相关量化不得入论文00 ----
    ("边界 gold-standard samples", "curated gold-standard"),
    ("边界 85% 伪影（论文01 专域）", "85%"),
    ("旧规则15 窄口径", "ECG text containing ultrasound keywords"),
    # ---- 红标已填项：旧占位符不得残留 ----
    ("旧占位 AUTHOR LIST", "AUTHOR LIST REQUIRED"),
    ("旧占位 AFFILIATIONS", "AFFILIATIONS REQUIRED"),
    ("旧占位 CORRESPONDING", "CORRESPONDING AUTHOR REQUIRED"),
    ("旧占位 ETHICS DETAILS", "ETHICS DETAILS REQUIRED"),
    ("旧占位 OPTIONAL acks", "OPTIONAL: add acknowledgements"),
    ("旧占位 CONTRIBUTIONS", "AUTHOR CONTRIBUTIONS REQUIRED"),
    ("旧占位 FUNDING", "FUNDING INFORMATION REQUIRED"),
    ("旧占位 CA GITHUB", "INSERT GITHUB REPOSITORY"),
    ("旧占位 DA OPEN", "INSERT OPEN REPOSITORY, DOI/PID, AND LICENCE"),
    ("旧占位 REF12 OPEN", "OPEN REPOSITORY AND DOI/PID REQUIRED"),
    ("旧占位 README DOI", "DOI to be assigned"),
]:
    check(f"ban.{name}", needle, in_text=False)

# ============ 7. 审计计数自检（动态：稿件声明的检查总数须等于本脚本实际检查数） ============
audit_n = len(checks) + 1
check("audit count self", f"passes all {audit_n} checks")

# ============ 输出 ============
dfc = pd.DataFrame(checks, columns=["verdict", "name", "needle"])
dfc["verdict"] = dfc["verdict"].map({True: "PASS", False: "FAIL"})
out = os.path.join(RES, "verify_manuscript_report.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(f"稿件校验目标: {paths}\n日期: {pd.Timestamp.now()}\n\n")
    f.write(dfc.to_string(index=False))
nfail = int((dfc.verdict == "FAIL").sum())
print(dfc[dfc.verdict == "FAIL"].to_string(index=False) if nfail else "(no failures)")
print(f"\n===== {int((dfc.verdict == 'PASS').sum())}/{len(dfc)} PASS，{nfail} FAIL =====")
sys.exit(1 if nfail else 0)
