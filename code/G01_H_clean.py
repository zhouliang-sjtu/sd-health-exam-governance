# -*- coding: utf-8 -*-
"""G01_H_clean.py — 清洗源数据库 · H 社区库固化清洗（v1.0）

输入（溯源链，均已审计）:
  1) G01a_H_raw_link.js        原始逐年 XLS → H_checkup_long.csv（JS 解析器）
  2) G01b_H_2022_shift_fix.py  2022 年列移位修复（9,396 行）→ H_checkup_long_v2fix2022.csv
  3) G01c_H_deep_audit.py      深度治理审计 + 异常值处理 → H_checkup_long_v3.csv
  4) 本脚本: 数值规范化 + 标准衍生层 + 2020 脂肪肝补丁（源修复）+ 数据字典 + 治理报告
输出:
  data/H/H_wave_level_v1.csv.gz     人-波清洗层 + 标准衍生层
  data/H/H_person_level_v1.csv      人级静态层（结构信息，不含结局）
  data/H/H_数据字典_v1.csv
  docs/H_治理报告_20260914.md
"""
import hashlib
import numpy as np
import pandas as pd

W = r"<institution-path>"
IN = r"<institution-path>"
P2020 = r"<institution-path>"
MAPF = r"<institution-path>"
VERSION = "v1.0"
rep = []

def rep_line(s=""):
    print(s)
    rep.append(str(s))

df = pd.read_csv(IN, encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
rep_line(f"输入 {len(df):,} 行 / {df['id'].nunique():,} 人（H_checkup_long_v3，已含 2022 移位修复与深度审计修复）")

numcols = ["age", "sbp", "dbp", "pulse", "hr", "height", "weight", "bmi", "waist",
           "wbc", "neut", "neutP", "lymph", "lymphP", "mono", "monoP", "eos", "eosP",
           "baso", "basoP", "hb", "rbc", "hct", "mcv", "mch", "mchc", "rdwc", "rdws",
           "plt", "mpv", "pdw", "pct", "tbil", "dbil", "alt", "ast", "bun", "crea",
           "ua", "tc", "tg", "hdl", "ldl", "fpg", "hba1c", "afp", "cea", "ca199"]
for c in numcols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

PLAUS = {"age": (15, 105), "sbp": (60, 260), "dbp": (30, 160), "height": (100, 250),
         "weight": (25, 300), "bmi": (12, 60), "waist": (40, 200), "wbc": (0.5, 100),
         "neut": (0.1, 50), "lymph": (0.1, 50), "mono": (0.01, 20), "plt": (10, 2000),
         "hb": (30, 250), "rbc": (1, 10), "alt": (1, 2000), "ast": (1, 2000),
         "crea": (10, 3000), "ua": (30, 2000), "tc": (0.5, 30), "tg": (0.05, 60),
         "hdl": (0.05, 10), "ldl": (0.05, 30), "fpg": (1, 50), "hba1c": (3, 20),
         "afp": (0, 2000), "cea": (0, 2000), "ca199": (0, 3000)}
for c, (lo, hi) in PLAUS.items():
    if c in df.columns:
        df.loc[~df[c].between(lo, hi), c] = np.nan

df["sex_male"] = (df["sex"] == "男").astype("Float64")
df.loc[~df["sex"].isin(["男", "女"]), "sex_male"] = pd.NA

def ckdepi2021(crea_umol, age, male):
    scr = crea_umol / 88.4
    k = 0.7 - 0.208 * male
    a = np.where(male == 1, -0.302, -0.241)
    epi = 142 * np.minimum(scr / k, 1) ** a * np.maximum(scr / k, 1) ** (-1.2) * 0.9938 ** age
    return epi * np.where(male == 1, 1.012, 1.0)

df["egfr"] = np.nan
m = df["crea"].notna() & df["age"].notna() & df["sex_male"].notna()
df.loc[m, "egfr"] = ckdepi2021(df.loc[m, "crea"].values, df.loc[m, "age"].values,
                               df.loc[m, "sex_male"].values.astype(float))
df["sii"] = np.where((df["plt"] > 0) & (df["lymph"] > 0),
                     df["plt"] * df["neut"] / df["lymph"], np.nan)
df["tyg"] = np.log((df["tg"] * 88.57) * (df["fpg"] * 18.02) / 2).where(
    (df["tg"] > 0) & (df["fpg"] > 0))
df["fib4"] = np.where((df["plt"] > 0) & (df["alt"] > 0) & (df["ast"] > 0),
                      df["age"] * df["ast"] / (df["plt"] * np.sqrt(df["alt"])), np.nan)
df["hsi"] = 8 * (df["alt"] / df["ast"].replace(0, np.nan)) + df["bmi"] + 2 * (1 - df["sex_male"])

def map_uprot(v):
    if pd.isna(v):
        return np.nan
    s = str(v).strip()
    if s in ("阴性", "—", "-", "neg", "Neg", "N"):
        return 0.0
    if s in ("±", "trace", "TRACE", "微量"):
        return 0.5
    if s.startswith("1"):
        return 1.0
    if s.startswith("2"):
        return 2.0
    if s.startswith("3"):
        return 3.0
    if s.startswith("4"):
        return 4.0
    return pd.to_numeric(s, errors="coerce")

df["uprot_score"] = df["uprot"].apply(map_uprot)
df["proteinuria"] = (df["uprot_score"] >= 1).astype("Float64")
df.loc[df["uprot_score"].isna(), "proteinuria"] = pd.NA

df["dm_screen"] = ((df["fpg"] >= 7.0) | (df["hba1c"] >= 6.5)).astype("Float64")
df.loc[df["fpg"].isna() & df["hba1c"].isna(), "dm_screen"] = pd.NA
df["htn_screen"] = ((df["sbp"] >= 140) | (df["dbp"] >= 90)).astype("Float64")
df.loc[df["sbp"].isna() & df["dbp"].isna(), "htn_screen"] = pd.NA
df["central_obese"] = np.where(df["sex_male"] == 1, (df["waist"] >= 90).astype(float),
                               np.where(df["sex_male"] == 0, (df["waist"] >= 85).astype(float), np.nan))
df["high_tg"] = (df["tg"] >= 1.7).astype("Float64")
df["low_hdl"] = np.where(df["sex_male"] == 1, (df["hdl"] < 1.0).astype(float),
                         np.where(df["sex_male"] == 0, (df["hdl"] < 1.3).astype(float), np.nan))
df["dysglycemia"] = ((df["fpg"] >= 5.6) | (df["hba1c"] >= 5.7)).astype("Float64")
df.loc[df["fpg"].isna() & df["hba1c"].isna(), "dysglycemia"] = pd.NA

# 2020 脂肪肝补丁（源修复，溯源 论文06 11_build_h2020_layer.py）
patch = pd.read_csv(P2020, dtype={"id": str})
pmap = patch.set_index("id")["fat_state"]
_m20 = df["year"] == 2020
rep_line(f"2020 补丁: 行={int(_m20.sum()):,}, 键匹配={int(df.loc[_m20, 'id'].isin(pmap.index).sum()):,}")
df.loc[_m20, "fat_state"] = df.loc[_m20, "id"].map(pmap).values
df.loc[_m20, "fatty"] = df.loc[_m20, "fat_state"]
df.loc[_m20, "fatty_degree"] = np.nan
df["fatty"] = pd.to_numeric(df["fatty"], errors="coerce")
df["fat_state"] = pd.to_numeric(df["fat_state"], errors="coerce")

# 超声脂肪肝 ∧ ≥1 心代谢组分（2023 MASLD 近似；论文层可称 UDFL）
cmrf = ((df["central_obese"] == 1) | (df["htn_screen"] == 1) | (df["high_tg"] == 1) |
        (df["low_hdl"] == 1) | (df["dm_screen"] == 1) | (df["dysglycemia"] == 1))
df["steatosis_cmrf"] = np.select([df["fatty"] == 1, df["fatty"] == 0],
                                 [cmrf.astype(float), np.zeros(len(df))], default=np.nan)

df = df.sort_values(["id", "year"])
df["n_waves"] = df.groupby("id")["year"].transform("count")
df["wave_idx"] = df.groupby("id").cumcount() + 1

# 身份证完整性标记（仅存标记，不存原始证件号）
MAP = pd.read_csv(MAPF, dtype=str)
Wc = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
Mc = "10X98765432"

def id_check(ic):
    if len(ic) != 18:
        return "legacy15" if len(ic) == 15 else "bad_len"
    try:
        s = sum(int(ic[i]) * Wc[i] for i in range(17))
    except Exception:
        return "nonnum"
    return "ok" if ic[17].upper() == Mc[s % 11] else "bad_check"

MAP["id_integrity"] = MAP["idcard"].apply(id_check)
imap = MAP.set_index("pseudo_id")["id_integrity"]
df["id_integrity"] = df["id"].map(imap)
rep_line("id 完整性标记分布（人）: " +
         df.drop_duplicates("id")["id_integrity"].value_counts().to_dict().__str__())

WAVE_KEEP = [
    # 标识/时间
    "id", "year", "wave_idx", "n_waves", "体检月份" if "体检月份" in df.columns else "qdate",
    # 人口学/体格
    "age", "sex_male", "height", "weight", "bmi", "waist",
    # 血压
    "sbp", "dbp", "pulse", "hr",
    # 血常规
    "wbc", "neut", "lymph", "mono", "eos", "baso", "hb", "rbc", "hct", "mcv", "mch",
    "mchc", "plt", "mpv", "pdw",
    # 生化
    "tbil", "dbil", "alt", "ast", "bun", "crea", "ua", "tc", "tg", "hdl", "ldl",
    "fpg", "hba1c", "afp", "cea", "ca199",
    # 尿检
    "uprot_score", "proteinuria",
    # 暴露（超声）
    "fatty", "fat_state", "fatty_degree",
    # 结局筛查/标准状态（L2）
    "dm_screen", "htn_screen", "central_obese", "high_tg", "low_hdl", "dysglycemia",
    "steatosis_cmrf", "egfr", "tyg", "fib4", "hsi", "sii",
    # 文本与标记
    "ecg_text", "ecg_abnormal", "ecg_af", "ecg_pacPvc", "ecg_stt", "ecg_anyBlock",
    "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave", "ecg_normal",
    "smoke", "drink", "chronic_mgmt_flag", "past_history", "id_integrity"]
WAVE_KEEP = [c for c in WAVE_KEEP if c in df.columns]
wave = df[WAVE_KEEP].copy()
wave.to_csv(W + f"/data/H/H_wave_level_{VERSION}.csv.gz", index=False,
            encoding="utf-8-sig", compression="gzip")
rep_line(f"波级输出: {len(wave):,} 行 × {len(wave.columns)} 列")

# ---------- 人级静态层 ----------
ds = df.sort_values(["id", "year"])
persons = ds.groupby("id", as_index=False).agg(
    sex_male=("sex_male", "first"), birth_year=("birth_year", "first"),
    n_waves=("year", "count"), first_year=("year", "min"), last_year=("year", "max"),
    age_base=("age", "first"), id_integrity=("id_integrity", "first"))
first_rows = ds.drop_duplicates("id").set_index("id")
persons["dm_screen_base"] = persons["id"].map(first_rows["dm_screen"]).values
persons.to_csv(W + f"/data/H/H_person_level_{VERSION}.csv", index=False, encoding="utf-8-sig")
rep_line(f"人级输出: {len(persons):,} 人")

# ---------- 数据字典 ----------
DICT = [
    ("id", "str", "交付伪标识（12位哈希，数据方交付前生成）", "主键"),
    ("year", "int", "体检年份 2018–2024", "时间"),
    ("wave_idx/n_waves", "int", "波序号/总波数", "时间"),
    ("age", "num", "年龄（岁）15–105", "协变量"),
    ("sex_male", "0/1", "男=1", "协变量"),
    ("height/weight/bmi/waist", "num", "身高cm/体重kg/BMI（12–60）/腰围cm（40–200）", "暴露组分/协变量"),
    ("sbp/dbp", "num", "血压 mmHg（60–260/30–160；SBP<DBP 已双置缺）", "结局/协变量"),
    ("alt/ast/ua/crea/tc/tg/hdl/ldl", "num", "肝肾功能血脂（各含合理值域；单位错配已清）", "协变量"),
    ("fpg", "num", "空腹血糖 mmol/L（1–50；<3.0 已置缺）", "结局判定/协变量"),
    ("hba1c", "num", "糖化血红蛋白 %（3–20）", "结局判定"),
    ("dm_screen", "0/1", "糖尿病筛查阳性：FPG≥7.0 或 HbA1c≥6.5", "结局（L2）"),
    ("htn_screen", "0/1", "高血压筛查阳性：SBP≥140 或 DBP≥90", "结局（L2）"),
    ("fatty", "0/1", "超声脂肪肝（2020 波经描述式规则补丁恢复）", "暴露"),
    ("fat_state", "0–3", "0无/1轻/2中/3重（程度缺失按轻度近似）", "暴露"),
    ("steatosis_cmrf", "0/1", "超声脂肪肝 ∧ ≥1 心代谢组分（2023 MASLD 近似；论文层可称 UDFL）", "暴露（L2）"),
    ("dysglycemia", "0/1", "FPG≥5.6 或 HbA1c≥5.7", "分层（L2）"),
    ("central_obese/high_tg/low_hdl", "0/1", "中心性肥胖(腰围男≥90/女≥85)/TG≥1.7/低HDL(男<1.0/女<1.3)", "组分（L2）"),
    ("egfr/tyg/fib4/hsi/sii", "num", "CKD-EPI 2021/TyG/FIB-4/HSI/SII", "衍生（L2）"),
    ("ecg_*", "0/1", "心电图文本词典 v2 判读（ST-T/房颤/阻滞等）", "结局（L2）"),
    ("smoke/drink", "cat", "吸烟/饮酒原始文本（never/former/current；none/occasional/daily 由论文层映射）", "协变量"),
    ("id_integrity", "cat", "身份证校验标记 ok/legacy15（不含原始证件号）", "质量标记"),
]
pd.DataFrame(DICT, columns=["variable", "type", "definition", "role"]).to_csv(
    W + f"/data/H/H_数据字典_{VERSION}.csv", index=False, encoding="utf-8-sig")

rep_line(f"\n关键质量数字: dm_screen==1 波 {int((wave['dm_screen'] == 1).sum()):,}；"
         f"steatosis_cmrf==1 波 {int((wave['steatosis_cmrf'] == 1).sum()):,}；"
         f"fpg 可用 {int(wave['fpg'].notna().sum()):,}；hba1c 可用 {int(wave['hba1c'].notna().sum()):,}")

with open(W + "/docs/H_治理报告_20260914.md", "w", encoding="utf-8") as f:
    f.write("# H 社区库治理报告（v1.0，2026-09-14）\n\n```\n" + "\n".join(rep) + "\n```\n")
print("\n===== G01_H_clean 完成 =====")
