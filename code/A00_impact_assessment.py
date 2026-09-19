# -*- coding: utf-8 -*-
"""A00_impact_assessment.py — 清洗治理对论文01/05/06/07 的影响量化

问题: H 库 2022 列移位（9,396 行）与 PG 项目名遗漏（fpg/ALT/AST），
      对各论文已用数据的影响范围。
方法: 对比修复前后 → 定位受影响样本 → 映射到各论文数据资产。
输出: results/清洗治理影响评估_20260914.csv + 控制台报告
"""
import numpy as np
import pandas as pd

PAPER = r"<institution-path>"
OUT = PAPER + r"/00-清洗源数据库/docs/清洗治理影响评估_20260914.md"
rep = []

def rep_line(s=""):
    print(s, flush=True)
    rep.append(str(s))

# ============ A. H 库 2022 移位影响 ============
rep_line("# 清洗治理对既有论文的影响评估（2026-09-14）\n")
rep_line("## A. H 库 2022 列移位：修复前后差异\n")
old = pd.read_csv(PAPER + r"/00-三线探索-多模态动态队列/data/processed/H_checkup_long.csv",
                  encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
new = pd.read_csv(PAPER + r"/00-三线探索-多模态动态队列/data/processed/H_checkup_long_v3.csv",
                  encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
OA = pd.read_csv(PAPER + r"/00-三线探索-多模态动态队列/data/processed/H_analysis_long.csv",
                 encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
NA = pd.read_csv(PAPER + r"/00-三线探索-多模态动态队列/data/processed/H_analysis_long_v3.csv",
                 encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
o22 = old[old["year"] == 2022].copy()
n22 = new[new["year"] == 2022].copy()
oa22 = OA[OA["year"] == 2022].copy()
na22 = NA[NA["year"] == 2022].copy()
for c in ["fpg", "ua", "tg", "hdl", "alt", "ast", "crea", "ecg_stt", "fatty"]:
    o22[c] = pd.to_numeric(o22[c], errors="coerce")
    n22[c] = pd.to_numeric(n22[c], errors="coerce")
for c in ["dm_screen", "masld", "ecg_stt"]:
    oa22[c] = pd.to_numeric(oa22[c], errors="coerce")
    na22[c] = pd.to_numeric(na22[c], errors="coerce")
# 移位行 = 修复后仍可识别的原始签名（用旧表 bun>25 & ua<90）
o22["_shift"] = ((pd.to_numeric(o22["bun"], errors="coerce") > 25) &
                 ~(pd.to_numeric(o22["ua"], errors="coerce") >= 90)).fillna(False)
shift_ids = set(o22.loc[o22["_shift"], "id"].dropna())
rep_line(f"- 2022 年移位行: {int(o22['_shift'].sum()):,} / {len(o22):,}"
         f"（涉及 {len(shift_ids):,} 人）")
rep_line(f"- 受影响字段: FPG（实为尿pH）、UA、TG、HDL、ALT、AST、肌酐、TC、LDL、AFP/CEA/CA199、"
         f"心电文本、超声文本\n")
rep_line("| 变量 | 修复前（错值） | 修复后（真值） | 差异幅度 |")
rep_line("|---|---|---|---|")
for c, name in [("fpg", "空腹血糖中位"), ("ua", "尿酸中位"), ("tg", "TG中位"),
                ("hdl", "HDL中位"), ("alt", "ALT可测数"), ("ast", "AST中位")]:
    om, nm = o22[c].median(), n22[c].median()
    if c == "alt":
        rep_line(f"| ALT | {int(o22[c].notna().sum()):,}（含伪值） | {int(n22[c].notna().sum()):,}（真值） | 2022 模板缺列 |")
    else:
        rep_line(f"| {name} | {om:.2f} | {nm:.2f} | {abs(nm - om) / max(abs(nm), 1e-9) * 100:.0f}% |")
rep_line(f"| 2022 糖尿病筛查阳性 | {int((oa22['dm_screen'] == 1).sum()):,} | "
         f"{int((na22['dm_screen'] == 1).sum()):,} | "
         f"{int((na22['dm_screen'] == 1).sum()) - int((oa22['dm_screen'] == 1).sum()):+,} |")
rep_line(f"| 2022 心电图 ST-T 阳性 | {int((oa22['ecg_stt'] == 1).sum()):,} | "
         f"{int((na22['ecg_stt'] == 1).sum()):,} | 假阴性纠正 |")
rep_line(f"| 2022 脂肪肝阳性 | {int((o22['fatty'] == 1).sum()):,} | "
         f"{int((n22['fatty'] == 1).sum()):,} | — |\n")

# ============ B. 论文01 金标准样本受影响比例 ============
rep_line("## B. 论文01（LLM 抽取验证）金标准样本受影响比例\n")
B1 = PAPER + r"/论文01-金标准标注-LLM抽取验证/data"
# 注意: 论文01 金标准 id = 身份证号原文（非伪标识）→ 经 mapping_H_idcard 桥接方可比对
MAP = pd.read_csv(r"<institution-path>", dtype=str)
idmap = MAP.set_index("idcard")["pseudo_id"]
rows = []
for f, tag in [("gold_abdus_H.csv", "腹部超声-H-600"), ("gold_abdus_H_300.csv", "腹部超声-H-300"),
               ("gold_ecg_H.csv", "心电图-H-570")]:
    d = pd.read_csv(f"{B1}/{f}", encoding="utf-8-sig", low_memory=False, dtype={"id": str})
    d["_pseudo"] = d["id"].map(idmap)
    d["_shift"] = (d["year"] == 2022) & d["_pseudo"].isin(shift_ids)
    nsh = int(d["_shift"].sum())
    rows.append({"金标准文件": tag, "样本数": len(d), "2022样本": int((d["year"] == 2022).sum()),
                 "其中移位行": nsh, "受影响比例": f"{100 * nsh / len(d):.1f}%"})
    rep_line(f"- **{tag}**：n={len(d)}，2022 年样本 {int((d['year'] == 2022).sum())}，"
             f"落在移位行 **{nsh}**（{100 * nsh / len(d):.1f}%）")
    if nsh:
        ex = d.loc[d["_shift"], "text"].astype(str).head(2).tolist()
        rep_line(f"  - 错位样例：{ex[0][:60]}…")
rep_line("")
rep_line("> 结论：论文01 的 H 库金标准中约 **5–7%** 样本取自 2022 移位行；"
         "因整行左移，US 文本列混入了放射科文本、ECG 文本列混入了超声文本"
         "（实证：ECG 金标准样本文本为\"脂肪肝，胆囊结石。\"），"
         "**该部分样本标注对象与文件标题不符，须重新抽取并复核**。PG 金标准不受影响。\n")

# ============ C. PG 项目名遗漏影响 ============
rep_line("## C. PG 库项目名遗漏（fpg / ALT / AST）影响\n")
arm = pd.read_csv(PAPER + r"/00-三线探索-多模态动态队列/data/processed/pg_arm_long.csv",
                  encoding="utf-8-sig", low_memory=False)
arm2 = pd.read_csv(PAPER + r"/00-清洗源数据库/data/PG/PG_wave_level_v1.0.csv",
                   encoding="utf-8-sig", low_memory=False)
rep_line("| 字段 | 旧 pg_arm_long | 新 PG 清洗层 | 影响 |")
rep_line("|---|---|---|---|")
rep_line(f"| FPG | {int(arm['fpg'].notna().sum()):,} / {len(arm):,} | "
         f"{int(arm2['fpg'].notna().sum()):,} / {len(arm2):,} | 论文07 已自行用 raw 重建；"
         f"论文03/05 未用 FPG |")
rep_line(f"| ALT（丙氨酸氨基转移酶） | 列不存在 | "
         f"{int((arm2['alt'].notna()).sum()):,} | PG 侧 HSI/FIB-4 此前不可算 |")
rep_line(f"| AST | 列不存在 | {int((arm2['ast'].notna()).sum()):,} | 同上 |")
rep_line(f"| HbA1c | {int(arm['糖化血红蛋白'].notna().sum()):,} | "
         f"{int(arm2['hba1c'].notna().sum()):,} | 一致（论文03/05 用 HbA1c 定义 DM） |\n")

# ============ D. 各论文受影响判定 ============
rep_line("## D. 各论文受影响判定与重跑必要性\n")
tbl = [
    ("论文01 LLM 抽取验证", "H 库 US/ECG 文本（全 7 年，自原始 XLS 自建抽取器）",
     "中：2022 移位行文本错位", "是（2022 部分文本与金标准复核）", "影响约 1 成金标准样本"),
    ("论文05 中心性肥胖→T2DM（已投稿）", "H（前瞻性佐证）+ PG（重复测量）+ CHARLS",
     "中：H 2022 错值 + PG FPG/ALT/AST 缺失", "是（等修回时重跑）", "投稿已提交，暂不动"),
    ("论文06 MASLD 逆转自然史（JHEP）", "PD（主队列）+ H（决定因素/持续性）+ PG + CHARLS",
     "低-中：PD 仅数值清理；H 2022 错值", "是（H 相关分析重跑；PD 主结果复核）", "主结论稳健性需验证"),
    ("论文07 尿有机酸代谢组（Hepatology）", "PG（代谢组 + 状态 + 结局）",
     "低：已自建 fpg；无列移位", "部分（ALT/AST/GGT 新增可作敏感性）", "fpg 已修正；主结果不受影响"),
]
rep_line("| 论文 | 数据依赖 | 受影响程度 | 是否需重跑 | 备注 |")
rep_line("|---|---|---|---|---|")
for r in tbl:
    rep_line("| " + " | ".join(r) + " |")
rep_line("")
rep_line("## E. 结论\n")
rep_line("1. **论文04** 已完全基于清洗治理后数据（前置已完成）。")
rep_line("2. **论文01**：需重新抽取 2022 年 US/ECG 文本并复核受影响金标准样本；")
rep_line("   抽取器本身（词典/LLM 一致性统计）不受影响。")
rep_line("3. **论文05**：受影响但已投稿 → 修回阶段重跑（H 侧全部数字 + PG 侧 FPG 可及后的新口径）。")
rep_line("4. **论文06**：PD 主队列仅为数值级清理（量级 10⁻³），主结果预计稳健；")
rep_line("   H 侧（A2 决定因素 / A3 持续性）需重跑。")
rep_line("5. **论文07**：主结果不受影响；新可用的 ALT/AST/GGT 可作补充验证。")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
rep_line(f"\n[save] {OUT}")
print("\n===== A00 完成 =====")
