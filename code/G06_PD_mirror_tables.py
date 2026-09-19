# -*- coding: utf-8 -*-
"""G06_PD_mirror_tables.py — 清洗源数据库 · PD 库原始表单 1:1 镜像清洗（v1.0）

范围:
  2019.xlsx / 2020.xlsx / 2021.xlsx（原始年度体检表, 80 列, 共 1,407,198 行）
  2019-2024死因【原始】.xlsx（Sheet1 死因链 / Sheet2 计数 / Sheet3 空）
原则: 行数与原始一致; 列名一致; PII: 身份证号 → mapping_pudong_idcard 伪标识（未映射置空打标）;
  带单位文本数值列按值域抽取; 一致性修复与 H/PG 同规; 重复打标不删行。
输出: data/PD/raw_mirror/PD_<year>_清洗版_v1.csv.gz, 死因_清洗版_v1.csv
"""
import os
import re
import numpy as np
import pandas as pd
import openpyxl

W = r"<institution-path>"
VERSION = "v1.1"   # v1.1（2026-09-16）：与 G03 同规补齐 4 家族（肌酐地板 20/LDL>TC/BMI 恒等式/转氨酶天花板）；v1.0 镜像已归档
MAPF = r"<institution-path>"
rep = []

def rep_line(s=""):
    print(s, flush=True)
    rep.append(str(s))

os.makedirs(W + "/data/PD/raw_mirror", exist_ok=True)
MAP = pd.read_csv(MAPF, dtype=str)
idmap = MAP.set_index(MAP.columns[0])[MAP.columns[1]]
rep_line(f"浦东伪标识映射: {len(idmap):,} 行")

pat = re.compile(r"[-+]?\d+(?:\.\d+)?")

def strip_num(s):
    if s is None:
        return np.nan
    m = pat.search(str(s).replace("↑", "").replace("↓", ""))
    return float(m.group()) if m else np.nan

RANGES = {"体质指数(BMI)": (12, 60), "收缩压": (50, 250), "舒张压": (30, 150),
          "葡萄糖": (2, 40), "甘油三酯": (0, 60), "高密度脂蛋白": (0, 10),
          "低密度脂蛋白": (0, 30), "总胆固醇": (0.5, 30), "尿素": (0.5, 50),
          "肌酐": (10, 3000), "尿酸": (30, 2000), "总胆红素": (1, 800),
          "谷丙转氨酶": (1, 2000), "谷草转氨酶": (1, 2000), "总蛋白": (30, 150),
          "白蛋白": (10, 80), "球蛋白": (5, 80), "腰围": (40, 160), "臀围": (40, 160),
          "身高": (100, 230), "体重": (20, 300), "体温": (33, 43), "脉率": (30, 220),
          "呼吸频率": (6, 40), "尿肌酐": (0.1, 50000), "尿微量白蛋白": (0, 10000),
          "年龄": (18, 110)}
TEXTNUM = set(RANGES)

crosscheck = {}
yearly_stats = []
for year in [2019, 2020, 2021]:
    f = rf"<institution-path>"
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(values_only=True)
    hdr = [str(x).strip() if x is not None else f"col{i}" for i, x in enumerate(next(it))]
    _seen = {}
    uni = []
    for h in hdr:
        if h in _seen:
            _seen[h] += 1
            uni.append(f"{h}#{_seen[h]}")
        else:
            _seen[h] = 0
            uni.append(h)
    hdr = uni
    data = [list(r) for r in it]
    wb.close()
    df = pd.DataFrame(data, columns=hdr)
    n0 = len(df)
    rep_line(f"[{year}] raw rows={n0:,} cols={len(hdr)}")

    # PII
    idc = next((c for c in df.columns if "身份证" in c), None)
    unmapped = 0
    if idc:
        raw_id = df[idc].astype(str).str.strip().str.upper()
        df[idc] = raw_id.map(idmap)
        unmapped = int((df[idc].isna() & raw_id.ne("") & raw_id.ne("NAN")).sum())
        df["_id_unmapped"] = df[idc].isna() & raw_id.ne("") & raw_id.ne("NAN")
    name_like = [c for c in df.columns if "姓名" in str(c)]
    df = df.drop(columns=name_like)

    # 数值抽取列
    for c in df.columns:
        base = re.sub(r"#\d+$", "", str(c))
        if base in TEXTNUM:
            v = df[c].map(strip_num)
            lo, hi = RANGES[base]
            df[c] = v.where(v.between(lo, hi))
    df["year"] = year

    # 一致性修复（同规）
    n_fix = {}
    m = (df["收缩压"] < df["舒张压"]).fillna(False) if "收缩压" in df else pd.Series(False, index=df.index)
    n_fix["sbp<dbp"] = int(m.sum())
    df.loc[m, ["收缩压", "舒张压"]] = np.nan
    for col, lo in [("葡萄糖", 3.0), ("尿酸", 120)]:
        if col in df:
            mm = (df[col] < lo) & df[col].notna()
            n_fix[f"{col}<{lo}"] = int(mm.sum())
            df.loc[mm, col] = np.nan
    if "甘油三酯" in df:
        mm = (df["甘油三酯"] > 25) & df["甘油三酯"].notna()
        n_fix["甘油三酯>25"] = int(mm.sum())
        df.loc[mm, "甘油三酯"] = np.nan
    if "高密度脂蛋白" in df and "总胆固醇" in df:
        mm = (df["高密度脂蛋白"] > df["总胆固醇"]).fillna(False)
        n_fix["hdl>tc"] = int(mm.sum())
        df.loc[mm, "高密度脂蛋白"] = np.nan
    # —— v1.1 同规补丁（与 G03 一致）——
    if "肌酐" in df:
        mm = (df["肌酐"] < 20) & df["肌酐"].notna()
        n_fix["crea<20"] = int(mm.sum())
        df.loc[mm, "肌酐"] = np.nan
    if "低密度脂蛋白" in df and "总胆固醇" in df:
        mm = (df["低密度脂蛋白"] > df["总胆固醇"]).fillna(False)
        n_fix["ldl>tc"] = int(mm.sum())
        df.loc[mm, "低密度脂蛋白"] = np.nan
    if all(c in df for c in ["体质指数(BMI)", "身高", "体重"]):
        h = pd.to_numeric(df["身高"], errors="coerce")
        w = pd.to_numeric(df["体重"], errors="coerce")
        b = pd.to_numeric(df["体质指数(BMI)"], errors="coerce")
        bc = w / (h / 100.0) ** 2
        mm = ((b - bc).abs() > 2.5) & b.notna() & bc.notna()
        bc_fix = bc.where(bc.between(12, 60))
        n_fix["bmi恒等式"] = int(mm.sum())
        n_fix["bmi重算后出窗置缺"] = int((mm & bc_fix.isna()).sum())
        df.loc[mm, "体质指数(BMI)"] = bc_fix[mm]
    for col in ["谷丙转氨酶", "谷草转氨酶"]:
        if col in df:
            mm = (df[col] > 1500) & df[col].notna()
            n_fix[f"{col}>1500"] = int(mm.sum())
            df.loc[mm, col] = np.nan

    if idc:
        df["_dup_in_year"] = df.duplicated(subset=[idc], keep="first")
    else:
        df["_dup_in_year"] = False
    crosscheck[year] = n0
    yearly_stats.append({"year": year, "rows": n0, "unmapped_id": unmapped,
                         "dup": int(df["_dup_in_year"].sum()), **n_fix})
    rep_line(f"[{year}] unmapped_id={unmapped}, dup={int(df['_dup_in_year'].sum())}, fixes={n_fix}")
    df.to_csv(W + f"/data/PD/raw_mirror/PD_{year}_清洗版_{VERSION}.csv.gz",
              index=False, encoding="utf-8-sig", compression="gzip")

# 与解析长表交叉核对
try:
    L = pd.read_csv(r"<institution-path>",
                    encoding="utf-8-sig", usecols=["year"], low_memory=False)
    rep_line("与 pd_checkup_long.csv 行数交叉核对: " +
             {int(y): int(n) for y, n in L["year"].value_counts().sort_index().items()}.__str__() +
             f" total={len(L):,}; 原始三表合计={sum(crosscheck.values()):,}")
except Exception as e:
    rep_line(f"交叉核对失败: {e}")

# 死因表
f = r"<institution-path>"
wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
for sn in wb.sheetnames:
    it = wb[sn].iter_rows(values_only=True)
    hdr = next(it, None)
    if hdr is None:
        rep_line(f"[死因-{sn}] 空 sheet")
        continue
    hdr = [str(x).strip() if x is not None else f"col{i}" for i, x in enumerate(hdr)]
    dfd = pd.DataFrame([list(r) for r in it], columns=hdr)
    for c in dfd.columns:
        if "身份证" in str(c):
            raw_id = dfd[c].astype(str).str.strip().str.upper()
            dfd[c] = raw_id.map(idmap)
            dfd["_id_unmapped"] = dfd[c].isna() & raw_id.ne("") & raw_id.ne("NAN")
        elif "姓名" in str(c):
            dfd = dfd.drop(columns=[c])
    dfd.to_csv(W + f"/data/PD/raw_mirror/死因_{sn}_清洗版_{VERSION}.csv",
               index=False, encoding="utf-8-sig")
    rep_line(f"[死因-{sn}] rows={len(dfd)} cols={len(dfd.columns)}")
wb.close()

pd.DataFrame(yearly_stats).to_csv(W + "/data/PD/PD_mirror_summary.csv",
                                  index=False, encoding="utf-8-sig")
with open(W + "/docs/PD_mirror_治理报告_v1.1_20260916.md", "w", encoding="utf-8") as f:
    f.write("# PD 库原始表单 1:1 镜像清洗报告（v1.1，2026-09-16）\n\n"
            "> v1.0 报告见 PD_mirror_治理报告_v1.0_20260914.md（已归档）；v1.1 与 G03 同规补齐 4 家族。\n\n"
            "```\n" + "\n".join(rep) + "\n```\n")
print("\n===== G06 完成 =====")
