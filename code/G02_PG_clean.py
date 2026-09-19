# -*- coding: utf-8 -*-
"""G02_PG_clean.py — 清洗源数据库 · PG 库固化清洗（v1.0）

溯源:
  1) 20_pg_extract_arm.py / probe 系列（三线探索）: PostgreSQL(127.0.0.1:5555, inter_mysql_tb)
  2) S00e 重提取修正: 补抓主血糖项"葡萄糖"(93,106) 与 ALT"丙氨酸氨基转移酶"(96,268)
     → pg_arm_v2.csv（report 级）
  3) 本脚本: 人-年聚合 + 异常值清理 + 标准衍生层 + 数据字典 + 治理报告
注: PG 无身高/体重/腰围/血压规模数据（体成分视图仅 2,112 行）→ 不构建需要 BP/腰围的
    组合暴露（steatosis_cmrf）；暴露仅 fatty（腹超文本词典）。
输出:
  data/PG/PG_wave_level_v1.csv     人-波层（人-年聚合）
  data/PG/PG_person_level_v1.csv   人级静态层
  data/PG/PG_数据字典_v1.csv
  docs/PG_治理报告_20260914.md
"""
import hashlib
import numpy as np
import pandas as pd

W = r"<institution-path>"
IN = r"<institution-path>"
SALT = "T1-PG-2026"
VERSION = "v1.0"
rep = []

def rep_line(s=""):
    print(s)
    rep.append(str(s))

df = pd.read_csv(IN, encoding="utf-8-sig", low_memory=False)
rep_line(f"输入 report 级 {len(df):,} 行 / {df['id'].nunique():,} 人")

for c in ["fpg", "hba1c", "tg", "tc", "hdl", "ldl", "ua", "crea", "alt", "ast", "ggt", "plt"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["fatty"] = pd.to_numeric(df["fatty"], errors="coerce")

# 人-年聚合（同一年多报告: 关键字段最全者, 平取最早）
KEYF = ["fpg", "hba1c", "fatty", "tg", "hdl", "ua", "crea", "alt", "ast", "ggt", "plt"]
df["_nn"] = df[KEYF].notna().sum(axis=1)
df["_q"] = pd.to_datetime(df["pe_queue_date"], errors="coerce")
df = df.sort_values(["id", "year", "_nn", "_q"], ascending=[True, True, False, True])
g = df.groupby(["id", "year"], as_index=False).first()
rep_line(f"人-年聚合: {len(g):,} 行 / {g['id'].nunique():,} 人")

# 异常值清理（与治理规范一致）
anom = {
    "fpg<3": int(((g["fpg"] < 3) & g["fpg"].notna()).sum()),
    "fpg>30": int(((g["fpg"] > 30) & g["fpg"].notna()).sum()),
    "hba1c<3或>15": int((((g["hba1c"] < 3) | (g["hba1c"] > 15)) & g["hba1c"].notna()).sum()),
    "tg>25": int(((g["tg"] > 25) & g["tg"].notna()).sum()),
    "ua<120": int((((g["ua"] < 120) & (g["ua"] > 0))).sum()),
    "crea<20": int(((g["crea"] < 20) & g["crea"].notna()).sum()),
    "hdl>tc": int((g["hdl"] > g["tc"]).fillna(False).sum()),
}
g.loc[(g["fpg"] < 3) | (g["fpg"] > 30), "fpg"] = np.nan
g.loc[(g["hba1c"] < 3) | (g["hba1c"] > 15), "hba1c"] = np.nan
g.loc[g["tg"] > 25, "tg"] = np.nan
g.loc[(g["ua"] < 120) & (g["ua"] > 0), "ua"] = np.nan
g.loc[g["crea"] < 20, "crea"] = np.nan
g.loc[g["hdl"] > g["tc"], "hdl"] = np.nan
rep_line("异常值清理: " + anom.__str__())

# 标准衍生层
g["sex_male"] = (g["sex"] == "男").astype("Float64")
g.loc[~g["sex"].isin(["男", "女"]), "sex_male"] = pd.NA
g["dm_screen"] = np.where((g["fpg"] >= 7.0).fillna(False) | (g["hba1c"] >= 6.5).fillna(False),
                          1.0, np.where(g["fpg"].notna() | g["hba1c"].notna(), 0.0, np.nan))
g["dysglycemia"] = np.where((g["fpg"] >= 5.6).fillna(False) | (g["hba1c"] >= 5.7).fillna(False),
                            1.0, np.where(g["fpg"].notna() | g["hba1c"].notna(), 0.0, np.nan))
g["high_tg"] = (g["tg"] >= 1.7).astype("Float64")
_male = (g["sex_male"] == 1).fillna(False).values
_female = (g["sex_male"] == 0).fillna(False).values
_low = np.where(_male, ((g["hdl"] < 1.0).fillna(False)).values.astype(float),
                np.where(_female, ((g["hdl"] < 1.3).fillna(False)).values.astype(float), np.nan))
g["low_hdl"] = _low
g.loc[g["hdl"].isna(), "low_hdl"] = np.nan
scr = (g["crea"] / 88.4).astype(float)
sexm = pd.to_numeric(g["sex_male"], errors="coerce").astype(float).values
k = 0.7 - 0.208 * sexm
a = np.where(sexm == 1, -0.302, -0.241)
m = g["crea"].notna() & g["age"].notna() & g["sex_male"].notna()
g["egfr"] = np.nan
g.loc[m, "egfr"] = (142 * np.minimum((scr[m] / k[m]), 1) ** a[m] *
                    np.maximum((scr[m] / k[m]), 1) ** (-1.2) * 0.9938 ** g.loc[m, "age"] *
                    np.where(sexm[m] == 1, 1.012, 1.0))

g = g.sort_values(["id", "year"]).reset_index(drop=True)
g["n_waves"] = g.groupby("id")["year"].transform("count")
g["wave_idx"] = g.groupby("id").cumcount() + 1
g["pid"] = g["id"].astype(str).fillna("").apply(
    lambda x: hashlib.md5((SALT + x).encode()).hexdigest()[:16])
g["qdate"] = g["pe_queue_date"]

WAVE_KEEP = ["pid", "id", "year", "wave_idx", "n_waves", "qdate", "age", "sex_male",
             "fatty", "fpg", "hba1c", "tg", "tc", "hdl", "ldl", "ua", "crea", "alt",
             "ast", "ggt", "plt", "dm_screen", "dysglycemia", "high_tg", "low_hdl", "egfr"]
wave = g[[c for c in WAVE_KEEP if c in g.columns]].copy()
wave.to_csv(W + f"/data/PG/PG_wave_level_{VERSION}.csv", index=False, encoding="utf-8-sig")
rep_line(f"波级输出: {len(wave):,} 行 × {len(wave.columns)} 列")

persons = g.groupby("id", as_index=False).agg(
    pid=("pid", "first"), sex_male=("sex_male", "first"), n_waves=("year", "count"),
    first_year=("year", "min"), last_year=("year", "max"), age_base=("age", "first"))
persons.to_csv(W + f"/data/PG/PG_person_level_{VERSION}.csv", index=False, encoding="utf-8-sig")
rep_line(f"人级输出: {len(persons):,} 人")

DICT = [
    ("pid", "str", "md5(T1-PG-2026 + 交付伪标识) 前 16 位（跨论文一致键）", "主键"),
    ("id", "str", "交付伪标识", "标识"),
    ("year", "int", "体检年份 2023–2026", "时间"),
    ("age/sex_male", "num/0-1", "年龄/性别", "协变量"),
    ("fatty", "0/1", "腹部超声脂肪肝（词典: 脂肪肝|细密|远场回声衰减|回声衰减）", "暴露"),
    ("fpg", "num", "空腹血糖 mmol/L（葡萄糖项为主；<3 或 >30 已置缺）", "结局判定"),
    ("hba1c", "num", "糖化血红蛋白 %（<3 或 >15 已置缺）", "结局判定"),
    ("dm_screen", "0/1", "糖尿病筛查阳性：FPG≥7.0 或 HbA1c≥6.5", "结局（L2）"),
    ("dysglycemia", "0/1", "FPG≥5.6 或 HbA1c≥5.7", "分层（L2）"),
    ("tg/tc/hdl/ldl/ua/crea/alt/ast/ggt/plt", "num", "常规生化（含值域清理）", "协变量"),
    ("high_tg/low_hdl", "0/1", "TG≥1.7 / 低HDL(男<1.0/女<1.3)", "组分（L2）"),
    ("egfr", "num", "CKD-EPI 2021", "衍生（L2）"),
]
pd.DataFrame(DICT, columns=["variable", "type", "definition", "role"]).to_csv(
    W + f"/data/PG/PG_数据字典_{VERSION}.csv", index=False, encoding="utf-8-sig")

rep_line(f"\n关键质量数字: dm_screen==1 波 {int((wave['dm_screen'] == 1).sum()):,}；"
         f"fatty 可判 {int(wave['fatty'].notna().sum()):,}（阳性率 "
         f"{100 * wave['fatty'].mean():.1f}%）；fpg 可用 {int(wave['fpg'].notna().sum()):,}；"
         f"hba1c 可用 {int(wave['hba1c'].notna().sum()):,}")

with open(W + "/docs/PG_治理报告_20260914.md", "w", encoding="utf-8") as f:
    f.write("# PG 库治理报告（v1.0，2026-09-14）\n\n```\n" + "\n".join(rep) + "\n```\n")
print("\n===== G02_PG_clean 完成 =====")
