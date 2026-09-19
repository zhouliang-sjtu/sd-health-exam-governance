# -*- coding: utf-8 -*-
"""G05b_PG_views_finish.py — PG 镜像收尾：469列问卷宽视图 psql 流式导出 + 其余视图 + 报告

vw_inter_questionnaire_full（33,588×469）在 psycopg2 全量拉取时内存/耗时受阻，
改用 psql \copy 服务端流式导出（CSV 原样，字段内 hygiene 由后续按需进行——该视图为
结构化问卷字段，非自由文本）。
"""
import os
import re
import subprocess
import pandas as pd
import psycopg2

W = r"<institution-path>"
PSQL = r"D:\tools\pgsql\bin\psql.exe"
VERSION = "v1.0"
rep = []

def rep_line(s=""):
    print(s, flush=True)
    rep.append(str(s))

# 1) 问卷宽视图：psql \copy 流式导出
out = W + f"/data/PG/raw_mirror/vw_inter_questionnaire_full_清洗版_{VERSION}.csv"
cmd = [PSQL, "-h", "127.0.0.1", "-p", "5555", "-U", "postgres", "-d", "inter_mysql_tb",
       "-c", f"\\copy (SELECT * FROM vw_inter_questionnaire_full) TO '{out}' WITH (FORMAT csv, HEADER true)"]
env = dict(os.environ, PGPASSWORD="")
r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
rep_line(f"[vw_full] psql exit={r.returncode} stderr={r.stderr.strip()[:200]}")
if r.returncode == 0 and os.path.exists(out):
    with open(out, "r", encoding="utf-8-sig") as fh:
        n = sum(1 for _ in fh) - 1
    rep_line(f"[vw_full] 导出行数={n:,}")

# 2) 其余视图（小表，psycopg2 直接拉）
conn = psycopg2.connect(host="127.0.0.1", port=5555, dbname="inter_mysql_tb",
                        user="postgres", connect_timeout=10)
cur = conn.cursor()

def txt_clean(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: re.sub(r"\s+", " ", str(x)).strip()
                                if x is not None else "")
    return df

for v in ["vw_inter_body_composition", "vw_methylation_wide"]:
    cur.execute(f"SELECT * FROM {v}")
    cols = [d[0] for d in cur.description]
    d = pd.DataFrame(cur.fetchall(), columns=cols)
    d = txt_clean(d, [c for c in d.columns if d[c].dtype == object])
    for c in d.columns:
        if d[c].dtype == object:
            nn = pd.to_numeric(d[c], errors="coerce")
            if nn.notna().mean() > 0.9:
                d[c] = nn
    d.to_csv(W + f"/data/PG/raw_mirror/{v}_清洗版_{VERSION}.csv.gz",
             index=False, encoding="utf-8-sig", compression="gzip")
    rep_line(f"[{v}] rows={len(d):,} cols={len(d.columns)}")
conn.close()

with open(W + "/docs/PG_mirror_治理报告_20260914.md", "a", encoding="utf-8") as f:
    f.write("\n```\n" + "\n".join(rep) + "\n```\n")
print("\n===== G05b 完成 =====")
