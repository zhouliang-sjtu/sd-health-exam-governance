# -*- coding: utf-8 -*-
"""G05_PG_mirror_tables.py — 清洗源数据库 · PG 库全表 1:1 镜像清洗（v1.0）

范围（业务表+视图，一一对应）:
  raw_tj_userinfo(129,953) / raw_detection_result(21,666,246, 流式) /
  raw_check_result(1,285,603) / raw_medicine_result(4,142,349, 流式) /
  raw_dnajjh_result(70,873) / raw_questionnaire_result + tb_questionnaire_jsonb +
  vw_inter_questionnaire_full(469列) + vw_inter_questionnaire_single /
  vw_inter_body_composition / vw_methylation_wide
不镜像（索引注明）: *_backfill(空)、*_test(测试残留)、sync_job_tracking、table_profile
清洗语义: 行列 1:1；文本 hygiene（HTML反转义/_x000D_/trim）；
  检验/代谢组数值: 原文保留 + 增补 item_result_num（清洗数值；逐项目 p0.1–p99.9 之外置缺）+
  _num_flag；userinfo/视图数值列做值域校验。
"""
import html
import gzip
import os
import re
import numpy as np
import pandas as pd
import psycopg2

W = r"<institution-path>"
os.makedirs(W + "/data/PG/raw_mirror", exist_ok=True)
VERSION = "v1.0"
DET = "raw_detection_result_view_input_20251224_135539"
CHK = "raw_check_result_view_input_20251224_135530"
MED = "raw_medicine_result_view_input_20251222_205024"
UI = "raw_tj_userinfo_view_input_20251222_211802"
DNA = "raw_dnajjh_result_view_input_20251222_204431"
QUE = "raw_questionnaire_result_view_input_20251222_234533"
NUM_RE = r"^-?[0-9]+(\.[0-9]+)?$"
CHUNK = 400_000
rep = []

def rep_line(s=""):
    print(s, flush=True)
    rep.append(str(s))

conn = psycopg2.connect(host="127.0.0.1", port=5555, dbname="inter_mysql_tb",
                        user="postgres", connect_timeout=10)
cur = conn.cursor()

def pull(sql):
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)

def txt_clean(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: re.sub(r"\s+", " ", html.unescape(str(x))).strip()
                                if x is not None else "")
            df.loc[df[c].str.lower().isin(["none", "nan"]), c] = ""
    return df

# ---------- 1. userinfo ----------
rep_line("[1/8] userinfo ...")
ui = pull(f"SELECT * FROM {UI}")
ui["age"] = pd.to_numeric(ui["age"], errors="coerce")
ui.loc[~ui["age"].between(0, 110), "age"] = np.nan
ui = txt_clean(ui, ["sex", "username", "regional", "group_name", "package_name"])
n_dup = int(ui["report_id"].duplicated().sum())
ui.to_csv(W + f"/data/PG/raw_mirror/userinfo_清洗版_{VERSION}.csv", index=False,
          encoding="utf-8-sig")
rep_line(f"  rows={len(ui):,} dup_report_id={n_dup}")

# ---------- 2. detection_result（两遍法） ----------
rep_line("[2/8] detection_result pass1 逐项目统计 ...")
cur.execute(f"""
SELECT item_name, COUNT(*) AS n,
       COUNT(CASE WHEN item_result ~ '{NUM_RE}' THEN 1 END) AS n_num,
       percentile_cont(0.001) WITHIN GROUP (ORDER BY CASE WHEN item_result ~ '{NUM_RE}'
            THEN item_result::float8 END) AS p001,
       percentile_cont(0.999) WITHIN GROUP (ORDER BY CASE WHEN item_result ~ '{NUM_RE}'
            THEN item_result::float8 END) AS p999
FROM {DET} GROUP BY item_name""")
stats = pd.DataFrame(cur.fetchall(), columns=["item_name", "n", "n_num", "p001", "p999"])
stats["num_share"] = stats["n_num"] / stats["n"]
stats.to_csv(W + f"/data/PG/raw_mirror/detection_逐项目统计_{VERSION}.csv",
             index=False, encoding="utf-8-sig")
bounds = stats[(stats["num_share"] >= 0.8)].set_index("item_name")[["p001", "p999"]]
rep_line(f"  items={len(stats)}, 数值主导项目(≥80%数值)={len(bounds)}")

rep_line("[2/8] detection_result pass2 流式清洗 ...")
cur.execute(f"SELECT * FROM {DET}")
names = [d[0] for d in cur.description]
out_path = W + f"/data/PG/raw_mirror/detection_result_清洗版_{VERSION}.csv.gz"
n_rows, n_num, n_oor = 0, 0, 0
first = True
import gzip
with gzip.open(out_path, "wt", encoding="utf-8-sig", newline="") as fh:
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        d = pd.DataFrame(rows, columns=names)
        num = pd.to_numeric(d["item_result"], errors="coerce")
        ok_num = d["item_result"].astype(str).str.match(NUM_RE)
        num = num.where(ok_num)
        b = d["item_name"].map(bounds["p001"])
        b2 = d["item_name"].map(bounds["p999"])
        inrange = (num >= b) & (num <= b2)
        oor = num.notna() & ~inrange.fillna(True)
        num_clean = num.where(inrange.fillna(False) | num.isna())
        d["item_result_num"] = num_clean.round(6)
        d["_num_flag"] = np.where(num.isna(), "", np.where(oor, "out_of_range", ""))
        n_num += int(num.notna().sum())
        n_oor += int(oor.sum())
        d.to_csv(fh, index=False, header=first)
        first = False
        n_rows += len(d)
rep_line(f"  rows={n_rows:,} numeric={n_num:,} out_of_range_flagged={n_oor:,}")

# ---------- 3. check_result ----------
rep_line("[3/8] check_result ...")
chk = pull(f"SELECT * FROM {CHK}")
chk = txt_clean(chk, ["item_result", "package_name", "item_combination_name"])
chk.to_csv(W + f"/data/PG/raw_mirror/check_result_清洗版_{VERSION}.csv.gz",
           index=False, encoding="utf-8-sig", compression="gzip")
rep_line(f"  rows={len(chk):,}")

# ---------- 4. medicine_result（流式，同两遍法） ----------
rep_line("[4/8] medicine_result pass1 ...")
cur.execute(f"""
SELECT item_name, COUNT(*) AS n,
       COUNT(CASE WHEN item_result ~ '{NUM_RE}' THEN 1 END) AS n_num,
       percentile_cont(0.001) WITHIN GROUP (ORDER BY CASE WHEN item_result ~ '{NUM_RE}'
            THEN item_result::float8 END) AS p001,
       percentile_cont(0.999) WITHIN GROUP (ORDER BY CASE WHEN item_result ~ '{NUM_RE}'
            THEN item_result::float8 END) AS p999
FROM {MED} GROUP BY item_name""")
stats_m = pd.DataFrame(cur.fetchall(), columns=["item_name", "n", "n_num", "p001", "p999"])
stats_m["num_share"] = stats_m["n_num"] / stats_m["n"]
stats_m.to_csv(W + f"/data/PG/raw_mirror/medicine_逐项目统计_{VERSION}.csv",
               index=False, encoding="utf-8-sig")
bounds_m = stats_m[stats_m["num_share"] >= 0.8].set_index("item_name")[["p001", "p999"]]
rep_line(f"  items={len(stats_m)}, 数值主导={len(bounds_m)}")
rep_line("[4/8] medicine_result pass2 流式清洗 ...")
cur.execute(f"SELECT * FROM {MED}")
names = [d[0] for d in cur.description]
out_path = W + f"/data/PG/raw_mirror/medicine_result_清洗版_{VERSION}.csv.gz"
n_rows, n_num, n_oor = 0, 0, 0
first = True
import gzip
with gzip.open(out_path, "wt", encoding="utf-8-sig", newline="") as fh:
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        d = pd.DataFrame(rows, columns=names)
        num = pd.to_numeric(d["item_result"], errors="coerce")
        ok_num = d["item_result"].astype(str).str.match(NUM_RE)
        num = num.where(ok_num)
        b = d["item_name"].map(bounds_m["p001"])
        b2 = d["item_name"].map(bounds_m["p999"])
        oor = num.notna() & ~((num >= b) & (num <= b2)).fillna(True)
        num_clean = num.where(((num >= b) & (num <= b2)).fillna(False) | num.isna())
        d["item_result_num"] = num_clean.round(6)
        d["_num_flag"] = np.where(num.isna(), "", np.where(oor, "out_of_range", ""))
        n_num += int(num.notna().sum())
        n_oor += int(oor.sum())
        d.to_csv(fh, index=False, header=first)
        first = False
        n_rows += len(d)
rep_line(f"  rows={n_rows:,} numeric={n_num:,} out_of_range_flagged={n_oor:,}")

# ---------- 5. dnajjh ----------
rep_line("[5/8] dnajjh ...")
dna = pull(f"SELECT * FROM {DNA}")
dna["item_result_num"] = pd.to_numeric(dna["item_result"], errors="coerce").round(6)
dna = txt_clean(dna, ["item_result", "project_name", "item_name"])
dna.to_csv(W + f"/data/PG/raw_mirror/dnajjh_result_清洗版_{VERSION}.csv.gz",
           index=False, encoding="utf-8-sig", compression="gzip")
rep_line(f"  rows={len(dna):,}")

# ---------- 6. 问卷/视图 ----------
rep_line("[6/8] questionnaire + views ...")
for t, out in [(QUE, "questionnaire_result"), ("tb_questionnaire_jsonb", "questionnaire_jsonb")]:
    d = pull(f"SELECT * FROM {t}")
    d = txt_clean(d, [c for c in d.columns if d[c].dtype == object])
    d.to_csv(W + f"/data/PG/raw_mirror/{out}_清洗版_{VERSION}.csv.gz",
             index=False, encoding="utf-8-sig", compression="gzip")
    rep_line(f"  {t}: rows={len(d):,} cols={len(d.columns)}")
for v in ["vw_inter_questionnaire_single", "vw_inter_questionnaire_full",
          "vw_inter_body_composition", "vw_methylation_wide"]:
    d = pull(f"SELECT * FROM {v}")
    d = txt_clean(d, [c for c in d.columns if d[c].dtype == object])
    for c in d.columns:
        if d[c].dtype == object:
            nn = pd.to_numeric(d[c], errors="coerce")
            if nn.notna().mean() > 0.9:
                d[c] = nn
    d.to_csv(W + f"/data/PG/raw_mirror/{v}_清洗版_{VERSION}.csv.gz",
             index=False, encoding="utf-8-sig", compression="gzip")
    rep_line(f"  {v}: rows={len(d):,} cols={len(d.columns)}")

conn.close()
with open(W + "/docs/PG_mirror_治理报告_20260914.md", "w", encoding="utf-8") as f:
    f.write("# PG 库全表 1:1 镜像清洗报告（v1.0，2026-09-14）\n\n```\n" +
            "\n".join(rep) + "\n```\n")
print("\n===== G05 完成 =====")
