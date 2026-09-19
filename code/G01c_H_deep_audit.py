# -*- coding: utf-8 -*-
"""S00d_deep_governance_audit.py — H 库全字段深度治理审计 + 异常值处理（→ v3）

层级: H_checkup_long_v2fix2022.csv（2022 移位已修复的解析层）
范围:
  A. 身份证校验和（GB11643）与 年龄-出生年 一致性（链接完整性）
  B. 全数值字段跨年分布审计（中位数偏离 >25% 告警）
  C. 行级异常签名（移位残留/血压颠倒/单位混串/极端值）按年扫描
  D. ECG 文本错配扫描（含超声关键词的"心电图"文本）
  E. 异常值处理规则应用 → H_checkup_long_v3.csv
之后由 S00c (TAG=v3) 重建分析层与人级表。
"""
import re
import numpy as np
import pandas as pd

SBase = r"<institution-path>"
SRC = SBase + "/data/processed/H_checkup_long_v2fix2022.csv"
OUT = SBase + "/data/processed/H_checkup_long_v3.csv"
MAPF = r"<institution-path>"
REPF = r"<institution-path>"
rep = []

def rep_line(s=""):
    print(s)
    rep.append(str(s))

C = pd.read_csv(SRC, encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
NUMF = ["age", "sbp", "dbp", "pulse", "hr", "height", "weight", "bmi", "waist",
        "wbc", "neut", "lymph", "plt", "hb", "rbc", "hct", "mcv", "mch", "mchc",
        "tbil", "alt", "ast", "bun", "crea", "ua", "tc", "tg", "hdl", "ldl",
        "fpg", "hba1c", "afp", "cea", "ca199"]
for c in NUMF:
    if c in C.columns:
        C[c] = pd.to_numeric(C[c], errors="coerce")
rep_line(f"读入 {len(C):,} 行 / {C['id'].nunique():,} 人（2022 移位已修复层）")

# ============ A. 身份证校验和 + 年龄一致性 ============
rep_line("\n" + "=" * 70)
rep_line("A. 链接完整性：身份证校验和 + 年龄-出生年一致性")
rep_line("=" * 70)
MAP = pd.read_csv(MAPF, dtype=str)
W = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
M = "10X98765432"

def id_check(ic):
    if len(ic) != 18:
        return "len15" if len(ic) == 15 else "bad_len"
    try:
        s = sum(int(ic[i]) * W[i] for i in range(17))
    except Exception:
        return "nonnum"
    return "ok" if ic[17].upper() == M[s % 11] else "bad_check"

MAP["chk"] = MAP["idcard"].apply(id_check)
rep_line("身份证校验结果: " + MAP["chk"].value_counts().to_dict().__str__())
bad_pseudo = set(MAP.loc[~MAP["chk"].isin(["ok"]), "pseudo_id"])
rep_line(f"校验未过人数: {len(bad_pseudo)}（伪标识可定位，不作剔除，标记为链接完整性提示）")
MAP["birth_year"] = MAP["idcard"].str[6:10]
bmap = MAP.set_index("pseudo_id")["birth_year"]
C["birth_year"] = C["id"].map(bmap)
C["birth_year"] = pd.to_numeric(C["birth_year"], errors="coerce")
d = (C["year"] - C["birth_year"]) - C["age"]
mism = d.abs() > 3
rep_line(f"年龄-出生年偏差>3岁 的行: {int(mism.sum())} / {int(C['age'].notna().sum())} "
         f"({100 * mism.sum() / max(int(C['age'].notna().sum()), 1):.2f}%)，涉及 "
         f"{C.loc[mism, 'id'].nunique()} 人")
byy = C.loc[mism].groupby("year").size().to_dict()
rep_line(f"  按年: {byy}")

# ============ B. 跨年分布审计 ============
rep_line("\n" + "=" * 70)
rep_line("B. 全数值字段跨年分布审计（中位数偏离>25%告警）")
rep_line("=" * 70)
flags = []
med_all = {}
for c in NUMF:
    med_y = C.groupby("year")[c].median()
    for yr in med_y.index:
        others = med_y.drop(yr)
        others = others[others.notna()]
        if len(others) == 0 or pd.isna(med_y[yr]):
            continue
        mo = others.median()
        if mo and abs(mo) > 1e-9:
            dev = med_y[yr] / mo - 1
            if abs(dev) > 0.25:
                flags.append({"field": c, "year": int(yr), "median_y": med_y[yr],
                              "median_others": mo, "dev_pct": round(100 * dev, 1)})
F = pd.DataFrame(flags)
if len(F):
    rep_line(F.to_string(index=False))
else:
    rep_line("无 >25% 中位数偏离告警")
F.to_csv(SBase + "/data/processed/audit_crossyear_flags.csv", index=False,
         encoding="utf-8-sig")

# ============ C. 行级异常签名 ============
rep_line("\n" + "=" * 70)
rep_line("C. 行级异常签名（按年）")
rep_line("=" * 70)
sig_rules = {
    "shift_residual(bun>25&ua<90)": (C["bun"] > 25) & ~(C["ua"] >= 90),
    "sbp<dbp(血压颠倒)": C["sbp"] < C["dbp"],
    "bmi与身高体重矛盾(>2.5)": (C["bmi"].notna() & C["height"].notna() & C["weight"].notna()
        & ((C["bmi"] - C["weight"] / (C["height"] / 100) ** 2).abs() > 2.5)),
    "hdl>tc": C["hdl"] > C["tc"],
    "ldl>tc": C["ldl"] > C["tc"],
    "ua<120(疑似mg/dL)": (C["ua"] < 120) & (C["ua"] > 0),
    "fpg<3.0": C["fpg"] < 3.0,
    "tg>25": C["tg"] > 25,
    "crea<20": C["crea"] < 20,
    "plt>800": C["plt"] > 800,
    "hb<60": C["hb"] < 60,
    "wbc>25": C["wbc"] > 25,
    "alt>1500": C["alt"] > 1500,
    "ast>1500": C["ast"] > 1500,
    "age<18": C["age"] < 18,
}
sig_rows = []
for name, mask in sig_rules.items():
    per = C.loc[mask.fillna(False)].groupby("year").size()
    sig_rows.append({"rule": name, **{int(y): int(v) for y, v in per.items()},
                     "total": int(mask.fillna(False).sum())})
SG = pd.DataFrame(sig_rows).fillna(0)
rep_line(SG.to_string(index=False))
SG.to_csv(SBase + "/data/processed/audit_row_signatures.csv", index=False,
          encoding="utf-8-sig")

# ============ D. ECG 文本错配扫描 ============
rep_line("\n" + "=" * 70)
rep_line("D. ECG 文本错配扫描（含超声关键词）")
rep_line("=" * 70)
ec = C[C["ecg_text"].notna() & (C["ecg_text"].astype(str).str.len() > 0)].copy()
ec["is_us_kw"] = ec["ecg_text"].astype(str).str.contains("脂肪肝|肾囊肿|肝囊肿|胆囊|子宫肌瘤")
per = ec.loc[ec["is_us_kw"]].groupby("year").size()
rep_line("含超声关键词的 ecg_text 按年: " + per.to_dict().__str__() +
         f"（共 {int(ec['is_us_kw'].sum())} 行；2022 修复后应≈0）")

# ============ E. 异常值处理 → v3 ============
rep_line("\n" + "=" * 70)
rep_line("E. 异常值处理规则应用 → v3")
rep_line("=" * 70)
fix_counts = {}

# 1) 血压颠倒 → 双置缺失
m1 = (C["sbp"] < C["dbp"]).fillna(False)
fix_counts["sbp<dbp → 双缺失"] = int(m1.sum())
C.loc[m1, ["sbp", "dbp"]] = np.nan

# 2) BMI 重算
bmi_calc = C["weight"] / (C["height"] / 100) ** 2
m2 = (C["bmi"].notna() & C["height"].notna() & C["weight"].notna()
      & ((C["bmi"] - bmi_calc).abs() > 2.5))
fix_counts["bmi矛盾 → 重算/置缺"] = int(m2.sum())
ok_calc = bmi_calc.between(12, 60)
C.loc[m2 & ok_calc, "bmi"] = bmi_calc[m2 & ok_calc]
C.loc[m2 & ~ok_calc, "bmi"] = np.nan

simple_rules = {
    "fpg<3.0 → 缺失": C["fpg"] < 3.0,
    "ua<120(疑似mg/dL) → 缺失": (C["ua"] < 120) & (C["ua"] > 0),
    "hdl>tc → hdl缺失": C["hdl"] > C["tc"],
    "ldl>tc → ldl缺失": C["ldl"] > C["tc"],
    "tg>25 → 缺失": C["tg"] > 25,
    "crea<20 → 缺失": C["crea"] < 20,
    "plt>800 → 缺失": C["plt"] > 800,
    "hb<60 → 缺失": C["hb"] < 60,
    "wbc>25 → 缺失": C["wbc"] > 25,
    "alt>1500 → 缺失": C["alt"] > 1500,
    "ast>1500 → 缺失": C["ast"] > 1500,
}
for name, mask in simple_rules.items():
    m = mask.fillna(False)
    fix_counts[name] = int(m.sum())
    tgt = name.split(" ")[0].split("<")[0].split(">")[0]
    C.loc[m, tgt] = np.nan

rep_line("处理计数: " + fix_counts.__str__())
per_fix = {}
for name, mask in {**{"sbp<dbp → 双缺失": m1},
                   **{k: v for k, v in simple_rules.items()}}.items():
    pass
# 按年统计每条规则
rows = []
for name, mask in [("sbp<dbp", m1)] + [(k, v.fillna(False)) for k, v in simple_rules.items()]:
    per = C.loc[mask].groupby("year").size()
    rows.append({"rule": name, **{int(y): int(v) for y, v in per.items()}, "total": int(mask.sum())})
pd.DataFrame(rows).to_csv(SBase + "/data/processed/audit_fix_counts.csv",
                          index=False, encoding="utf-8-sig")

C.to_csv(OUT, index=False, encoding="utf-8-sig")
rep_line(f"\n[save] {OUT}")

with open(REPF, "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("\n===== S00d 完成 =====")
