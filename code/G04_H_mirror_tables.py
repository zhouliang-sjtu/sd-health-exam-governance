# -*- coding: utf-8 -*-
"""G04_H_mirror_tables.py — 清洗源数据库 · H 库原始表单 1:1 镜像清洗（v1.0）

范围: 体检数据2018-2024 七个年度 XLS（一一对应）+ T2DM 队列三表
原则:
  - 行数与原始一致（不去重，重复打标 _dup_in_year）
  - 列名与原始一致（规范化空白），值清洗
  - PII: 姓名/姓名类列删除（记录存在性）；身份证号 → 平台伪标识（mapping_H_idcard），
    未映射者置空并打标；原始证件号不入库
  - 2022 移位修复: 移位行整行左移一位回正（含文本列），ALT 列置缺
  - 数值列: 语义值域（PLAUS）或 Hampel(8*MAD) 清洗；文本列保留
输出: data/H/raw_mirror/H_<year>_清洗版_v1.csv；T2DM → data/H/t2dm_mirror/...
"""
import os
import re
import numpy as np
import pandas as pd
import xlrd
import openpyxl

W = r"<institution-path>"
RAW = r"<institution-path>"
YEARS = {2018: "2018年总数.xls", 2019: "2019年.xls", 2020: "2020体检.xls",
         2021: "2021年.xls", 2022: "2022年总数.xls", 2023: "2023年总数.xls",
         2024: "2024年总数.xls"}
MAPF = r"<institution-path>"
VERSION = "v1.0"
rep = []

def rep_line(s=""):
    print(s)
    rep.append(str(s))

def norm(s):
    return re.sub(r"[\s\u3000]+", "", str(s if s is not None else ""))

def to_num(v):
    s = str(v).replace(",", "").replace("，", "").replace("↑", "").replace("↓", "").strip()
    if s in ("", "None", "nan"):
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan

PLAUS_BY_NAME = {"年龄": (15, 105), "收缩压": (60, 260), "舒张压": (30, 160),
                 "身高": (100, 250), "体重": (25, 300), "体重指数": (12, 60),
                 "腰围": (40, 200), "白细胞计数": (0.5, 100), "中性粒细胞绝对数": (0.1, 50),
                 "中性粒细胞绝对值": (0.1, 50), "淋巴细胞绝对数": (0.1, 50),
                 "淋巴细胞绝对值": (0.1, 50), "单核细胞绝对数": (0.01, 20),
                 "单核细胞绝对值": (0.01, 20), "血小板计数": (10, 2000), "血红蛋白": (30, 250),
                 "红细胞计数": (1, 10), "谷丙转氨酶": (1, 2000), "谷草转氨酶": (1, 2000),
                 "肌酐": (10, 3000), "尿酸": (30, 2000), "总胆固醇": (0.5, 30),
                 "甘油三酯": (0.05, 60), "高密度脂蛋白胆固醇": (0.05, 10),
                 "低密度脂蛋白胆固醇": (0.05, 30), "空腹血糖": (1, 50), "糖化血红蛋白": (3, 20),
                 "甲胎蛋白": (0, 2000), "癌胚抗原": (0, 2000), "糖类抗原CA19-9": (0, 3000),
                 "血小板平均体积": (2, 25), "平均血小板体积": (2, 25), "血小板压积": (0.05, 1),
                 "血小板比积": (0.05, 1), "红细胞压积": (15, 75), "平均红细胞体积": (40, 150),
                 "平均红细胞血红蛋白含量": (15, 50), "平均红细胞血红蛋白浓度": (200, 400),
                 "总胆红素": (1, 800), "直接胆红素": (0.5, 400), "尿素氮": (0.5, 50),
                 "嗜酸性粒细胞绝对数": (0, 20), "嗜酸性粒细胞绝对值": (0, 20),
                 "嗜碱性粒细胞绝对数": (0, 5), "嗜碱性粒细胞绝对值": (0, 5)}

MAP = pd.read_csv(MAPF, dtype=str)
idmap = MAP.set_index("idcard")["pseudo_id"]

os.makedirs(W + "/data/H/raw_mirror", exist_ok=True)
summary_tables = []

for year, fn in YEARS.items():
    wb = xlrd.open_workbook(os.path.join(RAW, fn))
    sh = wb.sheet_by_index(0)
    headers = [norm(sh.cell_value(0, c)) for c in range(sh.ncols)]
    # 列名去重（同名列加 #序号）
    _seen = {}
    _uni = []
    for h in headers:
        if h in _seen:
            _seen[h] += 1
            _uni.append(f"{h}#{_seen[h]}")
        else:
            _seen[h] = 0
            _uni.append(h)
    headers = _uni
    nrows = sh.nrows - 1
    data = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(1, sh.nrows)]
    df = pd.DataFrame(data, columns=headers)
    n0 = len(df)

    # ---- PII: 身份证号 → 伪标识；姓名类列删除 ----
    pii = {}
    drop_cols = []
    for c in df.columns:
        if "身份证" in c:
            raw_id = df[c].astype(str).str.strip().str.upper()
            df[c] = raw_id.map(idmap)
            unmapped = int((df[c].isna() & raw_id.ne("") & raw_id.ne("NAN")).sum())
            pii[c] = {"unmapped": unmapped}
        elif c in ("姓名", "名字", "患者姓名") or c.endswith("姓名"):
            pii[c] = {"dropped": "姓名列不入库"}
            drop_cols.append(c)
    for c in drop_cols:
        df = df.drop(columns=[c])

    # ---- 2022 移位修复（行级判定 + 整行右移回正，非就地以免同值蔓延） ----
    n_shift = 0
    if year == 2022:
        cols = list(df.columns)
        # 注意: 本层已删「姓名」列 → 列号比原始表小 1；谷丙转氨酶=79-1=78、谷草=79、尿素氮=80
        i_bun = next((i for i, h in enumerate(cols) if "尿素" in h), None)
        i_alt = next((i for i, h in enumerate(cols) if "谷丙转氨酶" in h), None)
        i_ast = next((i for i, h in enumerate(cols) if "谷草转氨酶" in h), None)
        i_ua = next((i for i, h in enumerate(cols) if h.startswith("尿酸")), None)
        if None not in (i_bun, i_alt, i_ast, i_ua):
            v_bun = df[cols[i_bun]].map(to_num)          # 移位行此格=肌酐真值
            v_ua = df[cols[i_ua]].map(to_num)            # 移位行此格=总胆固醇真值
            shifted = ((v_bun > 25) & ~(v_ua >= 90)).fillna(False)
            # 回落判定：尿素氮位缺失但肌酐位呈尿酸量级、且尿酸位呈 TC 量级
            fb = (df[cols[i_bun]].map(to_num).isna() &
                  df[cols[i_ast]].map(to_num).between(150, 1500) &
                  df[cols[i_ua]].map(to_num).between(2, 20)).fillna(False)
            shifted = shifted | fb
            n_shift = int(shifted.sum())
            # 移位规则: 该批模板缺「谷丙转氨酶」列，自「谷草转氨酶」起整行左移一位
            #   → 真值(列 j) = 现有值(列 j-1)，j 自 i_ast 起；「谷丙转氨酶」列置缺
            arr = df.to_numpy(dtype=object)
            orig = arr.copy()                             # 关键: 用副本，避免就地蔓延
            idx = np.where(shifted.values)[0]
            if len(idx):
                js = np.arange(i_ast, len(cols))
                arr[np.ix_(idx, js)] = orig[np.ix_(idx, js - 1)]
                arr[idx, i_alt] = np.nan
            df = pd.DataFrame(arr, columns=cols)
            rep_line(f"[{year}] 移位修复 {n_shift} 行（整行右移回正，谷丙转氨酶置缺；"
                     f"i_alt={i_alt}/i_ast={i_ast}/i_bun={i_bun}/i_ua={i_ua}）")

    # ---- 数值列清洗 ----
    n_clean = {}
    for c in df.columns:
        s_raw = df[c]
        v = s_raw.map(to_num)
        nn = v.notna().sum()
        if nn >= 0.9 * max((s_raw.astype(str).str.strip().ne("")).sum(), 1):
            key = next((k for k in PLAUS_BY_NAME if k in c), None)
            if key:
                lo, hi = PLAUS_BY_NAME[key]
                bad = (~v.between(lo, hi)) & v.notna()
            else:
                med = v.median()
                mad = (v - med).abs().median()
                if mad and mad > 0 and nn >= 30:
                    bad = ((v - med).abs() > 8 * 1.4826 * mad) & v.notna()
                else:
                    bad = pd.Series(False, index=v.index)
            n_clean[c] = int(bad.sum())
            if n_clean[c]:
                v[bad] = np.nan
            df[c] = v.where(v.notna(), s_raw.where(~s_raw.astype(str).str.strip().isin(["", "nan"]), ""))
            # 全数值化列直接用数值
            df[c] = v
    # ---- 去重打标（不删行）----
    idcol = next((c for c in df.columns if "身份证" in c), None)
    if idcol:
        df["_dup_in_year"] = df.duplicated(subset=[idcol], keep="first")
        rep_line(f"[{year}] 同年重复行标记: {int(df['_dup_in_year'].sum())}")
    out = W + f"/data/H/raw_mirror/H_{year}_清洗版_{VERSION}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    summary_tables.append({"year": year, "rows_raw": n0, "rows_clean": len(df),
                           "cols": len(df.columns), "shifted_fixed": n_shift,
                           "numeric_outliers": sum(n_clean.values())})
    rep_line(f"[{year}] 输出 {out}  rows={n0} cols={len(df.columns)}")

# ============ T2DM 三表 ============
os.makedirs(W + "/data/H/t2dm_mirror", exist_ok=True)
T2 = r"<institution-path>"

# 1) 处方表（7 sheet）
f = T2 + "/糖尿病(处方).xlsx"
wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
for sn in wb.sheetnames:
    rows = [list(r) for r in wb[sn].iter_rows(values_only=True)]
    hdr = [norm(x) for x in rows[0]]
    dfx = pd.DataFrame(rows[1:], columns=range(len(hdr)))
    dfx.columns = [hdr[i] if hdr[i] else f"col{i}" for i in range(len(hdr))]
    dfx = dfx.dropna(axis=1, how="all").dropna(axis=0, how="all")
    for c in dfx.columns:
        if "身份证" in str(c):
            raw_id = dfx[c].astype(str).str.strip().str.upper()
            dfx[c] = raw_id.map(idmap)
        elif "姓名" in str(c):
            dfx = dfx.drop(columns=[c])
    dfx.to_csv(W + f"/data/H/t2dm_mirror/糖尿病处方_{sn}_清洗版_{VERSION}.csv",
               index=False, encoding="utf-8-sig")
    summary_tables.append({"table": f"糖尿病处方[{sn}]", "rows_clean": len(dfx),
                           "cols": len(dfx.columns)})
    rep_line(f"[处方-{sn}] rows={len(dfx)} cols={len(dfx.columns)}")
wb.close()

# 2) T2DM 原始宽表（774 列，两行表头：年份行 + 字段行）
wb = openpyxl.load_workbook(T2 + "/H社区T2DM队列（原始）.xlsx", read_only=True,
                            data_only=True)
ws = wb["Sheet1"]
it = ws.iter_rows(values_only=True)
h1 = [norm(x) for x in next(it)]
h2 = [norm(x) for x in next(it)]
cols = [f"{h1[i]}|{h2[i]}" if h2[i] else (h1[i] or f"col{i}") for i in range(len(h1))]
dfw = pd.DataFrame([r for r in it], columns=cols)
dfw = dfw.dropna(axis=1, how="all")
for c in dfw.columns:
    if "身份证" in str(c):
        raw_id = dfw[c].astype(str).str.strip().str.upper()
        dfw[c] = raw_id.map(idmap)
    elif "姓名" in str(c):
        dfw = dfw.drop(columns=[c])
dfw.to_csv(W + f"/data/H/t2dm_mirror/T2DM队列原始宽表_清洗版_{VERSION}.csv.gz",
           index=False, encoding="utf-8-sig", compression="gzip")
summary_tables.append({"table": "T2DM队列原始宽表", "rows_clean": len(dfw),
                       "cols": len(dfw.columns)})
rep_line(f"[T2DM宽表] rows={len(dfw)} cols={len(dfw.columns)}")
wb.close()

# 3) 目标1 工作簿（12 sheet 全量镜像；分析库 sheet 做身份证处理）
wb = openpyxl.load_workbook(T2 + "/目标1_tyg长期变化趋势&dm新发.xlsx", read_only=True,
                            data_only=True)
for sn in wb.sheetnames:
    rows = [list(r) for r in wb[sn].iter_rows(values_only=True)]
    if not rows:
        continue
    hdr = [norm(x) if x is not None else "" for x in rows[0]]
    dfx = pd.DataFrame(rows[1:], columns=[h if h else f"col{i}" for i, h in enumerate(hdr)])
    dfx = dfx.dropna(axis=0, how="all")
    id_like = [c for c in dfx.columns if "身份证" in str(c)]
    for c in id_like:
        raw_id = dfx[c].astype(str).str.strip().str.upper()
        dfx[c] = raw_id.map(idmap)
    name_like = [c for c in dfx.columns if "姓名" in str(c)]
    dfx = dfx.drop(columns=name_like)
    dfx.to_csv(W + f"/data/H/t2dm_mirror/目标1_{sn}_清洗版_{VERSION}.csv",
               index=False, encoding="utf-8-sig")
    summary_tables.append({"table": f"目标1[{sn}]", "rows_clean": len(dfx),
                           "cols": len(dfx.columns)})
    rep_line(f"[目标1-{sn}] rows={len(dfx)} cols={len(dfx.columns)}")
wb.close()

pd.DataFrame(summary_tables).to_csv(W + "/data/H/H_mirror_summary.csv",
                                    index=False, encoding="utf-8-sig")
with open(W + "/docs/H_mirror_治理报告_20260914.md", "w", encoding="utf-8") as f:
    f.write("# H 库原始表单 1:1 镜像清洗报告（v1.0，2026-09-14）\n\n```\n" +
            "\n".join(rep) + "\n```\n")
print("\n===== G04 完成 =====")
