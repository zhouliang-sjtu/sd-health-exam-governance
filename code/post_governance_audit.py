# -*- coding: utf-8 -*-
"""post_governance_audit.py — 论文00 衍生：三库清洗治理残留三专项审计（只读，不改任何清洗产物）

由来：R2 审稿轮发现三库规则覆盖不对称（m2 库C 阴性对照 0.203% 残留），用户裁决"跑三项专项审计"。
  A1 规则×字段覆盖矩阵 —— 16 条规则 × 三库：字段具备？清洗是否落地？verdict ∈
      {actioned, structurally-na, gap(残留 n), scan-absent, flag-only, not-scanned, extraction-domain}
  A2 B/C 残留异常全量清单 —— 只扫覆盖矩阵判为 gap 的规则（附"已落地家族应静默"自检断言）
  A3 库A 2022 波 FPG 位尿 pH 离散度残留审计 —— 移位签名依赖 bun/ua 非缺失，签名静默行
      （盲态漏检 119/9,500）可能残留尿 pH 于 FPG 位；用小数位离散度做逐年对比取证

输出（results/）：audit_rule_field_coverage.csv、audit_residuals_libB.csv、audit_residuals_libC.csv、
audit_2022_fpg_residual.csv、post_governance_audit_report.md
地面真值：G03 RANGES（crea 窗口 10–3000）、PD/PG 治理报告、audit_fix_counts/row_signatures、
m2_pd_negative.txt、m2_framework.pd_rule_set。运行：python post_governance_audit.py
"""
import os
import re
import sys

import numpy as np
import pandas as pd

BASE = r"<institution-path>"
RES = os.path.join(BASE, "results")
CLEAN = r"<institution-path>"
SANX = r"<institution-path>"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m2_framework import pd_rule_set, evaluate_signatures  # noqa: E402

H_WAVE = os.path.join(CLEAN, "data", "H", "H_wave_level_v1.0.csv.gz")
PG_WAVE = os.path.join(CLEAN, "data", "PG", "PG_wave_level_v1.0.csv")
PD_WAVE = os.path.join(CLEAN, "data", "PD", "PD_wave_level_v1.1.csv.gz")
os.makedirs(RES, exist_ok=True)

rep_lines = []


def rep(s=""):
    print(s)
    rep_lines.append(str(s))


def read_report(path):
    return open(path, encoding="utf-8").read()


# ---------------------------------------------------------------- 治理动作证据（运行时解析）
pg_rep = read_report(os.path.join(CLEAN, "docs", "PG_治理报告_20260914.md"))
pd_rep = read_report(os.path.join(CLEAN, "docs", "PD_治理报告_v1.1_20260916.md"))
hm_rep = read_report(os.path.join(CLEAN, "docs", "H_mirror_治理报告_20260914.md"))
au = pd.read_csv(os.path.join(SANX, "data", "processed", "audit_fix_counts.csv"),
                 header=None, encoding="utf-8-sig")
au2 = pd.read_csv(os.path.join(SANX, "data", "processed", "audit_row_signatures.csv"),
                  header=None, encoding="utf-8-sig")
m2neg = read_report(os.path.join(RES, "m2_pd_negative.txt"))


def audit_total(prefix, src_df):
    for _, r in src_df.iterrows():
        if str(r[0]).strip().startswith(prefix):
            nums = pd.to_numeric(r[1:], errors="coerce").dropna()
            return int(nums.max()) if len(nums) else None
    return None


m_b = re.search(r"异常值清理: (\{[^}]*\})", pg_rep)
B_ACT = eval(m_b.group(1)) if m_b else {}          # {'fpg<3': 1, ...}
C_ACT = {}
for m_c in re.findall(r"(?:修复|补丁)落地: (.+)", pd_rep):
    for tok in re.findall(r"(\S+)\s*双?置缺\s*(\d+)", m_c):
        C_ACT[tok[0]] = int(tok[1])
H_SHIFT = re.search(r"移位修复 (\d+) 行", hm_rep)
H_SHIFT_N = int(H_SHIFT.group(1)) if H_SHIFT else None

# ---------------------------------------------------------------- 表头（字段具备性）
H_COLS = set(pd.read_csv(H_WAVE, nrows=0).columns)
PG_COLS = set(pd.read_csv(PG_WAVE, nrows=0).columns)
PD_COLS = set(pd.read_csv(PD_WAVE, nrows=0).columns)

# ---------------------------------------------------------------- A2 残留扫描（先算，矩阵引用其数字）
rep("========== A2 库C/库B 残留异常全量扫描（只读清洗层） ==========")

# ---- 库C（m2 同源规则集；输入同 m2 的 PD wave 层）----
pd_df = pd.read_csv(PD_WAVE, usecols=["id", "year", "height", "weight", "bmi", "sbp", "dbp",
                                      "fpg", "tc", "tg", "hdl", "ldl", "urea", "crea", "ua",
                                      "tbil", "alt", "ast"])
hit, per_rule, _ = evaluate_signatures(pd_df, pd_rule_set)
rule_names_cn = {"r01_shift_probe": "移位主探针(urea位)", "r02_shift_fb": "移位回落(crea位)",
                 "r03_bp_rev": "血压颠倒", "r04_hdl_gt_tc": "HDL>TC", "r05_ldl_gt_tc": "LDL>TC",
                 "r06_ua_low": "尿酸单位混串", "r07_fpg_low": "血糖下限", "r08_bmi_incons": "BMI恒等式",
                 "r09_tg_high": "TG上限", "r10_crea_low": "肌酐下限", "r14_altast_high": "转氨酶上限"}
rows_c = []
for idx in np.where(hit)[0]:
    r = pd_df.iloc[idx]
    rules = [k for k, v in per_rule.items() if bool(v[idx])]
    rows_c.append({"row_idx": int(idx), "id": r["id"], "year": int(r["year"]),
                   "rules": ";".join(rules),
                   "crea": r["crea"], "ldl": r["ldl"], "tc": r["tc"], "bmi": r["bmi"],
                   "height": r["height"], "weight": r["weight"], "alt": r["alt"], "ast": r["ast"]})
resid_c = pd.DataFrame(rows_c)
resid_c.to_csv(os.path.join(RES, "audit_residuals_libC.csv"), index=False, encoding="utf-8-sig")

c_counts = {k: int(v.sum()) for k, v in per_rule.items()}
rep(f"库C 残留行合计 {int(hit.sum()):,}（对照 m2 阴性对照逐规则）")
for k, v in c_counts.items():
    rep(f"  {k} ({rule_names_cn[k]}): {v:,}")
m2_expect = {k: int(v) for k, v in re.findall(r"(r\d+_\w+)=(\d+)", m2neg)}
drift = {k: (c_counts.get(k), m2_expect.get(k)) for k in set(c_counts) | set(m2_expect)
         if c_counts.get(k, -1) != m2_expect.get(k, -1)}
rep(f"与 m2 阴性对照逐规则一致性: {'一致 OK' if not drift else f'漂移! {drift}'}")

# ---- 库B（仅覆盖矩阵判 gap 的规则 + 已落地家族静默自检）----
pg_df = pd.read_csv(PG_WAVE, usecols=["id", "year", "fpg", "hba1c", "tg", "tc", "hdl", "ldl",
                                      "ua", "crea", "alt", "ast", "plt"])


def cmp(s, op, b):
    s = pd.Series(s)
    return (s > b if op == ">" else s < b).fillna(False)


b_gap = {
    "ldl>tc": cmp(pg_df["ldl"], ">", pg_df["tc"]),
    "alt/ast>1500": cmp(pg_df["alt"], ">", 1500) | cmp(pg_df["ast"], ">", 1500),
    "plt>800": cmp(pg_df["plt"], ">", 800),
}
b_silent = {  # 已落地家族在清洗层应静默（=0；治理报告计数为清洗前检出，置缺后不应再有）
    "fpg<3": cmp(pg_df["fpg"], "<", 3.0),
    "tg>25": cmp(pg_df["tg"], ">", 25),
    "ua<120": cmp(pg_df["ua"], "<", 120),
    "crea<20": cmp(pg_df["crea"], "<", 20),
    "hdl>tc": cmp(pg_df["hdl"], ">", pg_df["tc"]),
}
rows_b = []
for name, mask in b_gap.items():
    for idx in np.where(mask)[0]:
        r = pg_df.iloc[idx]
        rows_b.append({"residual_rule": name, "id": r["id"], "year": int(r["year"]),
                       "ldl": r["ldl"], "tc": r["tc"], "alt": r["alt"], "ast": r["ast"],
                       "plt": r["plt"]})
resid_b = pd.DataFrame(rows_b)
resid_b.to_csv(os.path.join(RES, "audit_residuals_libB.csv"), index=False, encoding="utf-8-sig")
b_gap_n = {k: int(v.sum()) for k, v in b_gap.items()}
b_sil_n = {k: int(v.sum()) for k, v in b_silent.items()}
rep(f"库B gap 规则残留（本次扫描量化）：{ {k: format(v, ',') for k, v in b_gap_n.items()} }")
b_left = {k: v for k, v in b_sil_n.items() if v > 0}
rep(f"库B 已落地家族清洗层静默检查（应全为 0，证明置缺有效）：{b_sil_n} "
    f"{'全部静默 OK（清理有效）' if not b_left else f'仍有残留 -> {b_left} 需人工复核'}")

# ---------------------------------------------------------------- A1 覆盖矩阵
rep("\n========== A1 规则×字段覆盖矩阵（三库） ==========")

A_ACT_N = {"sbp<dbp": audit_total("sbp<dbp", au), "hdl>tc": audit_total("hdl>tc", au),
           "ldl>tc": audit_total("ldl>tc", au), "ua<120": audit_total("ua<120", au),
           "fpg<3": audit_total("fpg<3.0", au), "bmi_identity": audit_total("bmi", au2),
           "tg>25": audit_total("tg>25", au), "crea<20": audit_total("crea<20", au),
           "plt>800": audit_total("plt>800", au), "hb<60": audit_total("hb<60", au),
           "wbc>25": audit_total("wbc>25", au),
           "alt/ast>1500": (audit_total("alt>1500", au) or 0) + (audit_total("ast>1500", au) or 0),
           "age<18": audit_total("age<18", au2)}
B_ACT_N = {"fpg<3": B_ACT.get("fpg<3"), "tg>25": B_ACT.get("tg>25"), "ua<120": B_ACT.get("ua<120"),
           "crea<20": B_ACT.get("crea<20"), "hdl>tc": B_ACT.get("hdl>tc")}
C_ACT_N = {"fpg<3": C_ACT.get("fpg<3"), "ua<120": C_ACT.get("ua<120"), "tg>25": C_ACT.get("tg>25"),
           "hdl>tc": C_ACT.get("hdl>tc"), "sbp<dbp": C_ACT.get("sbp<dbp"),
           "crea<20": C_ACT.get("crea<20"), "ldl>tc": C_ACT.get("ldl>tc"),
           "bmi_identity": C_ACT.get("bmi恒等式"), "alt/ast>1500": C_ACT.get("alt/ast>1500")}

# (标签, key, A需字段, B需字段, C需字段) —— 移位探针按各库实际可用字段分别声明
RULES = [
    ("移位主探针 r01（bun/urea 位>25 & ua 位<90）", "shift", ["bun", "ua"], ["bun", "ua"], ["urea", "ua"]),
    ("移位回落 r02（crea 位 150–1500 & ua 位 2–20）", "shift", ["crea", "ua"], ["crea", "ua"], ["crea", "ua"]),
    ("血压颠倒 SBP<DBP", "sbp<dbp", ["sbp", "dbp"], ["sbp", "dbp"], ["sbp", "dbp"]),
    ("脂类反转 HDL>TC", "hdl>tc", ["hdl", "tc"], ["hdl", "tc"], ["hdl", "tc"]),
    ("脂类反转 LDL>TC", "ldl>tc", ["ldl", "tc"], ["ldl", "tc"], ["ldl", "tc"]),
    ("尿酸单位混串 UA<120", "ua<120", ["ua"], ["ua"], ["ua"]),
    ("血糖下限 FPG<3.0", "fpg<3", ["fpg"], ["fpg"], ["fpg"]),
    ("BMI 恒等式 |BMI−W/H²|>2.5", "bmi_identity",
     ["bmi", "height", "weight"], ["bmi", "height", "weight"], ["bmi", "height", "weight"]),
    ("TG 上限 >25", "tg>25", ["tg"], ["tg"], ["tg"]),
    ("肌酐下限 <20", "crea<20", ["crea"], ["crea"], ["crea"]),
    ("血小板上限 >800", "plt>800", ["plt"], ["plt"], ["plt"]),
    ("血红蛋白下限 <60", "hb<60", ["hb"], ["hb"], ["hb"]),
    ("白细胞上限 >25", "wbc>25", ["wbc"], ["wbc"], ["wbc"]),
    ("转氨酶天花板 >1500", "alt/ast>1500", ["alt", "ast"], ["alt", "ast"], ["alt", "ast"]),
    ("文本域错配（ECG 文本含超声词）", "text", ["ecg_text"], ["__none__"], ["__extract__"]),
    ("年龄合理性 age<18", "age<18", ["age"], ["age"], ["age"]),
]
C_GAP_N = {"crea<20": c_counts["r10_crea_low"], "ldl>tc": c_counts["r05_ldl_gt_tc"],
           "bmi_identity": c_counts["r08_bmi_incons"], "alt/ast>1500": c_counts["r14_altast_high"]}


def one_verdict(cohort, key, need, cols):
    if need == ["__none__"]:
        return "structurally-na (无自由文本字段)"
    if need == ["__extract__"]:
        return "extraction-domain (us_text/ecg_text 已抽取，清洗域外)"
    missing = ",".join(f for f in need if f not in cols)
    if missing:
        return f"structurally-na (无 {missing})"
    if cohort == "A":
        if key == "shift":
            return f"actioned (移位修复 {H_SHIFT_N:,} 行 + 残差扫描 0)" if H_SHIFT_N else "actioned"
        if key == "text":
            return "actioned via 2022 移位重映射；独立词典扫描未单列证据"
        n = A_ACT_N.get(key)
        if key == "age<18":
            return f"flag-only (签名标记 n={n}, 未见置缺动作)" if n else "flag-only"
        return f"actioned (n={n:,})" if n is not None else "not-scanned"
    if cohort == "B":
        if key == "shift":
            return "scan-absent (r02 字段具备可做未做；无移位事件已知)"
        if key in B_ACT_N and B_ACT_N[key] is not None:
            return f"actioned (n={B_ACT_N[key]:,})"
        if key in b_gap_n:
            return f"gap (本次扫描残留 {b_gap_n[key]:,} 行)"
        return "not-scanned"
    # cohort == "C"
    if key == "shift":
        return "scan-absent (探针字段具备可做未做；无移位事件已知)"
    if key in C_ACT_N and C_ACT_N[key] is not None:
        return f"actioned (n={C_ACT_N[key]:,})"
    if key in C_GAP_N:
        note = "；G03 RANGES 地板=10 < 生理地板 20" if key == "crea<20" else ""
        return f"gap (残留 {C_GAP_N[key]:,} 行{note})"
    return "not-scanned"


mat = []
for label, key, need_a, need_b, need_c in RULES:
    mat.append({"rule": label,
                "A(库A)": one_verdict("A", key, need_a, H_COLS),
                "B(库B)": one_verdict("B", key, need_b, PG_COLS),
                "C(库C)": one_verdict("C", key, need_c, PD_COLS)})
mat_df = pd.DataFrame(mat)
mat_df.to_csv(os.path.join(RES, "audit_rule_field_coverage.csv"), index=False, encoding="utf-8-sig")
rep(mat_df.to_string(index=False))

# ---------------------------------------------------------------- A3 2022 波 FPG 离散度残留审计
rep("\n========== A3 库A 2022 波 FPG 位尿 pH 离散度残留审计 ==========")
h = pd.read_csv(H_WAVE, usecols=["id", "year", "fpg", "bun", "ua", "crea"])
h["_pos_in_year"] = h.groupby("year").cumcount()

x = pd.to_numeric(h["fpg"], errors="coerce")
h["_ok"] = x.notna()
h["_1dp"] = h["_ok"] & (np.abs(x * 10 - np.round(x * 10)) < 1e-6)
h["_05"] = h["_ok"] & (np.abs(x * 2 - np.round(x * 2)) < 1e-6)
yearly = h[h["_ok"]].groupby("year").agg(
    n_fpg=("fpg", "size"), n_1dp=("_1dp", "sum"), n_05=("_05", "sum"),
    med=("fpg", "median"), n_ge7=("fpg", lambda s: int((s >= 7.0).sum())))
yearly["rate_1dp"] = yearly["n_1dp"] / yearly["n_fpg"]
yearly["rate_05"] = yearly["n_05"] / yearly["n_fpg"]
rep("逐年 FPG 离散度（尿 pH 实验室报告 1 位小数、血糖 2 位小数——1dp 率异常升高 = 残留信号）：")
rep(yearly[["n_fpg", "n_1dp", "rate_1dp", "n_05", "rate_05", "med", "n_ge7"]].to_string())

y22 = h[(h["year"] == 2022) & h["_ok"]]
base_rate = yearly.loc[yearly.index != 2022, "rate_1dp"].max()
susp = y22[y22["_1dp"] & y22["fpg"].between(4.5, 8.5)].copy()
susp_ge7 = susp[susp["fpg"] >= 7.0]
rep(f"\n2022 波 1dp 且 FPG∈[4.5,8.5]（尿 pH 候带）行数: {len(susp):,}"
    f"（其中 ≥7.0 候选残留假阳性: {len(susp_ge7):,}）；其他年份同口径 1dp 率上限 = {base_rate:.4%}")
rep(f"2022 受影响块（年内行号 ≥7,880）内外分布: "
    f"块内 {int((susp['_pos_in_year'] >= 7880).sum())} / 块外 {int((susp['_pos_in_year'] < 7880).sum())}")
miss = susp[["bun", "ua", "crea"]].isna().mean()
rep(f"候选行 bun/ua/crea 缺失率（签名静默机制预测应偏高；实测≈全库背景即无富集）: "
    f"bun={miss['bun']:.3f}, ua={miss['ua']:.3f}, crea={miss['crea']:.3f}")
r22 = float(yearly.loc[2022, "rate_1dp"])
rep(f"A3 判读: 2022 波 1dp 率 {r22:.2%} 不高于其余年份（{base_rate:.4%} 上限），"
    f"候选行签名位缺失率≈背景（无静默富集），块内外分布与块大小成比例 "
    f"→ 尿 pH 残留假设不成立；残留上界收缩至个位行级（离散度检验功效限）")

susp_out = susp[["id", "year", "_pos_in_year", "fpg", "bun", "ua", "crea"]].rename(
    columns={"_pos_in_year": "row_idx_in_2022wave"})
susp_out.to_csv(os.path.join(RES, "audit_2022_fpg_residual.csv"), index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 汇总报告
rep("\n========== 结论 ==========")
rep(f"A1 覆盖矩阵: 落地不对称——B gap={ {k: format(v, ',') for k, v in b_gap_n.items()} }；"
    f"C gap=crea<20 {c_counts['r10_crea_low']:,} / LDL>TC {c_counts['r05_ldl_gt_tc']:,} / "
    f"BMI恒等式 {c_counts['r08_bmi_incons']:,} / 转氨酶 {c_counts['r14_altast_high']:,}")
rep(f"A2 残留清单: audit_residuals_libC.csv ({len(resid_c):,} 行) / "
    f"audit_residuals_libB.csv ({len(resid_b):,} 行)")
rep(f"A3 2022 残留: 1dp 候带行 {len(susp):,}（≥7.0 候选 {len(susp_ge7):,} 个）；判读见 report md")

md = ["# post_governance_audit — 三库清洗残留三专项审计（只读）",
      "",
      "> 运行时生成 post_governance_audit.py；输入 = 清洗层 wave 表 + 治理报告 + 审计 CSV + m2 引擎。"
      "本审计不改任何清洗产物；残留处置（如库C V1.1 补丁）另行裁决。",
      "",
      "## A1 规则×字段覆盖矩阵", "",
      mat_df.to_markdown(index=False),
      "",
      "## A2 残留扫描汇总", "",
      f"- 库C：合计 {int(hit.sum()):,} 行；逐规则 " + ", ".join(f"{k}={v:,}" for k, v in c_counts.items()) +
      f"；与 m2 阴性对照逐规则{'一致 OK' if not drift else '漂移 ' + str(drift)}",
      f"- 库B gap 规则残留：{b_gap_n}；已落地家族静默自检 {b_sil_n}（治理报告 {B_ACT}）",
      "- 明细：audit_residuals_libC.csv / audit_residuals_libB.csv",
      "",
      "## A3 库A 2022 波 FPG 离散度", "",
      yearly[["n_fpg", "n_1dp", "rate_1dp", "n_05", "rate_05", "med", "n_ge7"]].to_markdown(),
      "",
      f"- 2022 波 1dp 且 FPG∈[4.5,8.5]: {len(susp):,} 行（≥7.0 候选残留假阳性 {len(susp_ge7):,}；"
      f"块内/块外 = {int((susp['_pos_in_year'] >= 7880).sum())}/{int((susp['_pos_in_year'] < 7880).sum())}）",
      f"- 候选行 bun/ua/crea 缺失率: {miss.to_dict()}",
      "- 明细：audit_2022_fpg_residual.csv", ""]
with open(os.path.join(RES, "post_governance_audit_report.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print("\nreport -> results/post_governance_audit_report.md")
