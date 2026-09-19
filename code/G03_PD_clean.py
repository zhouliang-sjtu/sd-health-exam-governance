# -*- coding: utf-8 -*-
"""G03_PD_clean.py — 清洗源数据库 · PD（浦东老年体检）库固化清洗（v1.1）

溯源: <institution-path> 产物）
要点: 化验为带单位文本（"6.00mmol/L"）→ 数值抽取；B超/心电文本词典；病史字段；
     id×year 去重；值域与异常审计。人群 2019–2021 体检老人（分析层由论文自行限定 ≥60）。
v1.1（2026-09-16, 论文00 三专项审计裁决）: 与库A 同规补齐 4 个家族——
  肌酐绝对生理地板 20（v1.0 值域窗口地板 10 放行 1,661 行）、LDL>TC 置缺、
  BMI 恒等式重算（|bmi−w/h²|>2.5，重算后出窗 12–60 置缺）、ALT/AST>1500 置缺。
  行数不变（仅值级置缺）；v1.0 产物原地保留（论文01 B25/B30 路径兼容），现行版 = v1.1。
输出:
  data/PD/PD_wave_level_v1.1.csv.gz   人-波层
  data/PD/PD_person_level_v1.1.csv    人级静态层
  data/PD/PD_数据字典_v1.1.csv
  docs/PD_治理报告_v1.1_20260916.md
"""
import re
import numpy as np
import pandas as pd

W = r"<institution-path>"
IN = r"<institution-path>"
VERSION = "v1.1"
rep = []

def rep_line(s=""):
    print(s)
    rep.append(str(s))

USE = ["id", "year", "年龄", "性别", "体检日期", "腰围", "臀围", "舒张压", "收缩压",
       "身高", "体重", "体质指数(BMI)", "吸烟状况", "饮酒频率",
       "脑血管疾病", "肾脏疾病", "心脏疾病", "血管疾病", "眼部疾病", "神经系统疾病",
       "其他系统疾病", "心电图结果", "B超结果",
       "葡萄糖", "总胆固醇", "甘油三酯", "高密度脂蛋白", "低密度脂蛋白",
       "尿素", "肌酐", "尿酸", "总胆红素", "谷丙转氨酶", "谷草转氨酶",
       "总蛋白", "白蛋白", "球蛋白", "尿肌酐", "尿微量白蛋白"]
df = pd.read_csv(IN, encoding="utf-8-sig", usecols=lambda c: c in USE, low_memory=False)
rep_line(f"输入 {len(df):,} 行 / {df['id'].nunique():,} 人")

pat = re.compile(r"[-+]?\d+(?:\.\d+)?")

def strip_num(s):
    if pd.isna(s):
        return np.nan
    m = pat.search(str(s).replace("↑", "").replace("↓", ""))
    return float(m.group()) if m else np.nan

RANGES = {"bmi": ("体质指数(BMI)", 12, 60), "sbp": ("收缩压", 50, 250),
          "dbp": ("舒张压", 30, 150), "fpg": ("葡萄糖", 2, 40), "tg": ("甘油三酯", 0, 60),
          "hdl": ("高密度脂蛋白", 0, 10), "ldl": ("低密度脂蛋白", 0, 30),
          "tc": ("总胆固醇", 0.5, 30), "urea": ("尿素", 0.5, 50), "crea": ("肌酐", 10, 3000),
          "ua": ("尿酸", 30, 2000), "tbil": ("总胆红素", 1, 800), "alt": ("谷丙转氨酶", 1, 2000),
          "ast": ("谷草转氨酶", 1, 2000), "tp": ("总蛋白", 30, 150), "alb": ("白蛋白", 10, 80),
          "glob": ("球蛋白", 5, 80), "waist": ("腰围", 40, 160), "height": ("身高", 100, 230),
          "weight": ("体重", 20, 300), "uacr_crea": ("尿肌酐", 0.1, 50000),
          "ualb": ("尿微量白蛋白", 0, 10000)}
for out, (src, lo, hi) in RANGES.items():
    v = df[src].map(strip_num) if src in df.columns else pd.Series(np.nan, index=df.index)
    df[out] = v.where(v.between(lo, hi))
    n_excl = int((v.notna() & ~v.between(lo, hi)).sum())
    if n_excl:
        rep_line(f"  值域外剔除 {src}→{out}: {n_excl}")

df["age"] = pd.to_numeric(df["年龄"], errors="coerce").where(lambda x: x.between(18, 110))
df["male"] = df["性别"].astype(str).str.contains("男").astype(float).where(
    df["性别"].astype(str).str.contains("男|女"))
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df["_date"] = pd.to_datetime(df["体检日期"], errors="coerce")

# id 规范与去重
df["id"] = df["id"].astype(str).str.strip().str.upper()
is12 = df["id"].str.fullmatch(r"[0-9A-F]{12}").fillna(False).astype(bool)
rep_line(f"id 形态: 12位 {int(is12.sum()):,} / 其他 {int((~is12).sum()):,}")
df["_nn"] = df[[c for c in df.columns if c != "_date"]].notna().sum(axis=1)
# v1.1 对齐章程 §1.4：同人同年保留"关键完整性最高、日期最早"的一条
# （v1.0 实现为日期最晚优先，样例核验会把有值报告换成缺值报告，已纠正）
df = df.sort_values(["_nn", "_date"], ascending=[False, True]).drop_duplicates(
    subset=["id", "year"], keep="first")
rep_line(f"id×year 去重后: {len(df):,} 行（章程语义：完整性优先、日期最早）")

# 暴露/结局文本词典
for c in ["B超结果", "心电图结果", "其他系统疾病", "心脏疾病"]:
    df[c] = df[c].astype(str).str.replace("_x000D_", "", regex=False)
    df.loc[df[c].str.lower().isin(["nan"]), c] = ""
us = df["B超结果"]
us_ne = us.str.strip().ne("") & us.str.lower().ne("nan")
df["fatty_explicit"] = (us_ne & us.str.contains("脂肪肝", na=False)).astype(float).where(us_ne)
DESC = "细密|密集|弥漫|回声衰减|后方衰减|光点增粗|明亮肝|回声增粗|回声增强"
df["fatty_broad"] = (us_ne & (us.str.contains("脂肪肝", na=False) |
                              us.str.contains(DESC, na=False))).astype(float).where(us_ne)
ecg = df["心电图结果"]
ecg_ne = ecg.str.strip().ne("") & ecg.str.lower().ne("nan")
stt_pat = r"ST-?T|ST段|T波(改变|低平|倒置|高尖)|心肌缺血"
neg_pat = r"未见|无明显|大致正常|无特殊|正常心电图"
df["ecg_stt"] = np.where(ecg_ne & ecg.str.contains(stt_pat, na=False) &
                         ~ecg.str.contains(neg_pat, na=False), 1.0,
                         np.where(ecg_ne, 0.0, np.nan))
df["hist_dm"] = df["其他系统疾病"].str.contains("糖尿病", na=False)
df["hist_htn"] = df["心脏疾病"].str.contains("高血压", na=False)

df["dm_screen"] = np.where((df["fpg"] >= 7.0).fillna(False) | df["hist_dm"], 1.0,
                           np.where(((df["fpg"] < 7.0) & df["fpg"].notna()) |
                                    (df["其他系统疾病"].ne("") & df["其他系统疾病"].notna()),
                                    0.0, np.nan))
df["htn_screen"] = np.where((df["sbp"] >= 140).fillna(False) | (df["dbp"] >= 90).fillna(False) |
                            df["hist_htn"], 1.0,
                            np.where(((df["sbp"].notna() & (df["sbp"] < 140) &
                                       (df["dbp"].isna() | (df["dbp"] < 90)))) |
                                     (df["心脏疾病"].ne("") & df["心脏疾病"].notna()),
                                     0.0, np.nan))
df["high_tg"] = (df["tg"] >= 1.7).astype("Float64")
df["low_hdl"] = np.where(df["male"] == 1, (df["hdl"] < 1.0).astype(float),
                         np.where(df["male"] == 0, (df["hdl"] < 1.3).astype(float), np.nan))
df["central_obese"] = (((df["male"] == 1) & (df["waist"] >= 90)) |
                       ((df["male"] == 0) & (df["waist"] >= 85)) |
                       (df["bmi"] >= 28)).astype("Float64").where(
    df["waist"].notna() | df["bmi"].notna())
df["dysglycemia"] = np.where((df["fpg"] >= 5.6).fillna(False) | df["hist_dm"], 1.0,
                             np.where(df["fpg"].notna(), 0.0, np.nan))

# 审计
rep_line("\n—— 审计 ——")
for c in ["fpg", "tg", "hdl", "ua", "crea", "alt", "sbp", "dbp", "bmi"]:
    s = df[c].dropna()
    rep_line(f"  {c}: n={len(s):,} med={s.median():.2f} p1={s.quantile(.01):.2f} p99={s.quantile(.99):.2f}")
anom = {
    "sbp<dbp": int((df["sbp"] < df["dbp"]).fillna(False).sum()),
    "hdl>tc": int((df["hdl"] > df["tc"]).fillna(False).sum()),
    "ua<120": int(((df["ua"] < 120) & (df["ua"] > 0)).sum()),
    "glu<3": int(((df["fpg"] < 3) & df["fpg"].notna()).sum()),
    "tg>25": int(((df["tg"] > 25) & df["tg"].notna()).sum()),
    # v1.1 新增家族（计数于全部修复前，与库A 同规口径）
    "crea<20": int(((df["crea"] < 20) & df["crea"].notna()).sum()),
    "ldl>tc": int((df["ldl"] > df["tc"]).fillna(False).sum()),
    "bmi_incons": int((((df["bmi"] - df["weight"] / (df["height"] / 100.0) ** 2).abs() > 2.5) &
                       df["bmi"].notna() & df["height"].notna() & df["weight"].notna()).sum()),
    "altast>1500": int((((df["alt"] > 1500).fillna(False)) |
                        ((df["ast"] > 1500).fillna(False))).sum()),
}
rep_line("  异常签名: " + anom.__str__())
# 与 H/PG 同规修复
df.loc[(df["fpg"] < 3) & df["fpg"].notna(), "fpg"] = np.nan
df.loc[(df["ua"] < 120) & (df["ua"] > 0), "ua"] = np.nan
df.loc[df["tg"] > 25, "tg"] = np.nan
m_hdltc = (df["hdl"] > df["tc"]).fillna(False)
df.loc[m_hdltc, "hdl"] = np.nan
m_bp = (df["sbp"] < df["dbp"]).fillna(False)
df.loc[m_bp, ["sbp", "dbp"]] = np.nan
rep_line(f"  修复落地: fpg<3 置缺 {anom['glu<3']}, ua<120 置缺 {anom['ua<120']}, "
         f"tg>25 置缺 {anom['tg>25']}, hdl>tc 置缺 {anom['hdl>tc']}, "
         f"sbp<dbp 双置缺 {anom['sbp<dbp']}")
# —— v1.1 补丁：与库A 同规补齐 4 个家族（行数不变，仅值级置缺/重算）——
m_crea20 = (df["crea"] < 20) & df["crea"].notna()
df.loc[m_crea20, "crea"] = np.nan
m_ldltc = (df["ldl"] > df["tc"]).fillna(False)
df.loc[m_ldltc, "ldl"] = np.nan
bc = df["weight"] / (df["height"] / 100.0) ** 2
m_bmi = ((df["bmi"] - bc).abs() > 2.5) & df["bmi"].notna() & bc.notna()
bc_fix = bc.where(bc.between(12, 60))          # 重算值出窗(12–60) → 置缺
n_bmi_out = int((m_bmi & bc_fix.isna()).sum())
df.loc[m_bmi, "bmi"] = bc_fix[m_bmi]
m_alt15 = (df["alt"] > 1500).fillna(False)
df.loc[m_alt15, "alt"] = np.nan
m_ast15 = (df["ast"] > 1500).fillna(False)
df.loc[m_ast15, "ast"] = np.nan
rep_line(f"  v1.1 补丁落地: crea<20 置缺 {anom['crea<20']}, ldl>tc 置缺 {anom['ldl>tc']}, "
         f"bmi恒等式 置缺 {anom['bmi_incons']}（重算 {int(m_bmi.sum())}，其中重算后出窗置缺 {n_bmi_out}）, "
         f"alt/ast>1500 置缺 {anom['altast>1500']}")
# 修复后重算筛查状态
df["dm_screen"] = np.where((df["fpg"] >= 7.0).fillna(False) | df["hist_dm"], 1.0,
                           np.where(((df["fpg"] < 7.0) & df["fpg"].notna()) |
                                    (df["其他系统疾病"].ne("") & df["其他系统疾病"].notna()),
                                    0.0, np.nan))
df["htn_screen"] = np.where((df["sbp"] >= 140).fillna(False) | (df["dbp"] >= 90).fillna(False) |
                            df["hist_htn"], 1.0,
                            np.where(((df["sbp"].notna() & (df["sbp"] < 140) &
                                       (df["dbp"].isna() | (df["dbp"] < 90)))) |
                                     (df["心脏疾病"].ne("") & df["心脏疾病"].notna()),
                                     0.0, np.nan))
df["central_obese"] = (((df["male"] == 1) & (df["waist"] >= 90)) |
                       ((df["male"] == 0) & (df["waist"] >= 85)) |
                       (df["bmi"] >= 28)).astype("Float64").where(
    df["waist"].notna() | df["bmi"].notna())   # v1.1：bmi 重算后同步重算（bmi≥28 兜底支路）
per_fat = df.dropna(subset=["fatty_explicit"]).groupby("year")["fatty_explicit"].agg(["size", "mean"])
rep_line("  fatty_explicit 按年(可判数/阳性率): " +
         {int(y): (int(r["size"]), round(100 * r["mean"], 1)) for y, r in per_fat.iterrows()}.__str__())
per_dm = df.dropna(subset=["dm_screen"]).groupby("year")["dm_screen"].mean()
rep_line("  dm_screen 阳性率按年: " +
         {int(y): round(100 * v, 1) for y, v in per_dm.items()}.__str__())

# 输出
df = df.sort_values(["id", "year"]).reset_index(drop=True)
df["n_waves"] = df.groupby("id")["year"].transform("count")
df["wave_idx"] = df.groupby("id").cumcount() + 1
df["qdate"] = df["_date"].dt.strftime("%Y-%m-%d")
WAVE = ["id", "year", "wave_idx", "n_waves", "qdate", "age", "male", "height", "weight",
        "bmi", "waist", "sbp", "dbp", "fpg", "tc", "tg", "hdl", "ldl", "urea", "crea",
        "ua", "tbil", "alt", "ast", "tp", "alb", "glob",
        "fatty_explicit", "fatty_broad", "dm_screen", "htn_screen", "dysglycemia",
        "high_tg", "low_hdl", "central_obese", "ecg_stt", "hist_dm", "hist_htn",
        "吸烟状况", "饮酒频率", "B超结果", "心电图结果"]
wave = df[[c for c in WAVE if c in df.columns]].copy()
wave = wave.rename(columns={"吸烟状况": "smoke_raw", "饮酒频率": "drink_raw",
                            "B超结果": "us_text", "心电图结果": "ecg_text"})
for c in ["us_text", "ecg_text"]:
    wave[c] = wave[c].astype(str).str.slice(0, 150)
wave.to_csv(W + f"/data/PD/PD_wave_level_{VERSION}.csv.gz", index=False,
            encoding="utf-8-sig", compression="gzip")
rep_line(f"\n波级输出: {len(wave):,} 行 × {len(wave.columns)} 列")

persons = wave.groupby("id", as_index=False).agg(
    male=("male", "first"), n_waves=("year", "count"), first_year=("year", "min"),
    last_year=("year", "max"), age_base=("age", "first"))
persons.to_csv(W + f"/data/PD/PD_person_level_{VERSION}.csv", index=False, encoding="utf-8-sig")
rep_line(f"人级输出: {len(persons):,} 人")

DICT = [
    ("id", "str", "交付伪标识（12位哈希）", "主键"),
    ("year", "int", "体检年份 2019–2021", "时间"),
    ("age/male", "num/0-1", "年龄/性别（论文层通常限 ≥60）", "协变量"),
    ("height/weight/bmi/waist", "num", "体格测量（值域清理后）", "协变量/组分"),
    ("sbp/dbp", "num", "血压 mmHg", "结局/协变量"),
    ("fpg", "num", "空腹血糖 mmol/L（\"葡萄糖\"文本抽取，2–40）", "结局判定"),
    ("tc/tg/hdl/ldl/ua/crea/alt/ast/urea/tbil/tp/alb/glob", "num", "常规生化（文本抽取+值域）", "协变量"),
    ("fatty_explicit", "0/1", "B超文本含\"脂肪肝\"（主口径）", "暴露"),
    ("fatty_broad", "0/1", "explicit ∪ 描述性声像词（敏感口径）", "暴露（敏感）"),
    ("dm_screen", "0/1", "FPG≥7.0 或 病史\"糖尿病\"（测量×病史组合口径，缺失置NA）", "结局（L2）"),
    ("htn_screen", "0/1", "SBP≥140 或 DBP≥90 或 病史\"高血压\"", "结局（L2）"),
    ("hist_dm/hist_htn", "bool", "其他系统疾病含\"糖尿病\"/心脏疾病含\"高血压\"", "病史"),
    ("us_text/ecg_text", "str", "原始文本（截断150字符）", "溯源"),
]
pd.DataFrame(DICT, columns=["variable", "type", "definition", "role"]).to_csv(
    W + f"/data/PD/PD_数据字典_{VERSION}.csv", index=False, encoding="utf-8-sig")

with open(W + "/docs/PD_治理报告_v1.1_20260916.md", "w", encoding="utf-8") as f:
    f.write("# PD（浦东老年体检）库治理报告（v1.1，2026-09-16）\n\n"
            "> v1.0 报告见 PD_治理报告_v1.0_20260914.md（已归档）；v1.1 = 同规补齐 4 家族，行数不变。\n\n"
            "```\n" + "\n".join(rep) + "\n```\n")
print("\n===== G03_PD_clean 完成 =====")
