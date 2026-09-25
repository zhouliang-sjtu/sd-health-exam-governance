# -*- coding: utf-8 -*-
"""sim_r33_boundary_sensitivity.py — SIM-R3-3：Cohort B（PG 长表）分位边界敏感性分析

审稿模拟发现 R3-3：p0.1/p99.9 逐项目边界是工程选择，其敏感性（p1/p99 对照）与逐项目
拦截率分布未报告。本脚本对 21,666,246 行长表做 server-side 两遍分析：
  Q1 逐项目 n / n_num / 四分位（percentile_cont ARRAY；口径与 G05 Pass-1 逐位一致：
     NUM_RE = ^-?[0-9]+(\\.[0-9]+)?$，num_share ≥ 0.8 → 数值主导项目）
  Q2 数值主导项目两套边界外行数（released p0.1/p99.9 vs alternative p1/p99）
交叉校验：Q1 的 p0.001/p0.999 与冻结件 detection_逐项目统计_v1.0.csv 逐位比对（应为 0 差）。
只读分析：readonly 会话，不建持久对象，不改任何冻结层。
输出：results/sim_r33_boundary_sensitivity.csv（563 行逐项目 + 汇总打印）。
"""
import sys
import time

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DET = "raw_detection_result_view_input_20251224_135539"
NUM_RE = r"^-?[0-9]+(\.[0-9]+)?$"
FROZEN = r"D:\projects\Paper\00-清洗源数据库\data\PG\raw_mirror\detection_逐项目统计_v1.0.csv"
OUT = r"D:\projects\Paper\论文00-多源体检队列数据治理与质量审计\results\sim_r33_boundary_sensitivity.csv"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
t_all = time.time()

cn = psycopg2.connect(host="127.0.0.1", port=5555, dbname="inter_mysql_tb",
                      user="postgres", connect_timeout=10)
cn.set_session(readonly=True, autocommit=False)
cur = cn.cursor()
cur.execute("SET work_mem = '1GB'")

# ---------- Q1：逐项目统计 + 四分位（单次全表分组排序） ----------
t0 = time.time()
cur.execute(f"""
SELECT item_name, COUNT(*) AS n,
       COUNT(CASE WHEN item_result ~ '{NUM_RE}' THEN 1 END) AS n_num,
       percentile_cont(ARRAY[0.001, 0.01, 0.99, 0.999]) WITHIN GROUP (
         ORDER BY CASE WHEN item_result ~ '{NUM_RE}' THEN item_result::float8 END) AS q
FROM {DET} GROUP BY item_name""")
rows = cur.fetchall()
st = pd.DataFrame(rows, columns=["item_name", "n", "n_num", "q"])


def _aslist(x):
    if x is None:                              # 纯文本项目：无数值行 → percentile 为 NULL
        return [float("nan")] * 4
    if isinstance(x, str):                     # 数组被驱动端转成 '{a,b,c,d}' 字符串时兜底
        return [float(t) for t in x.strip("{}").split(",")]
    return [float(t) for t in x]


print(f"[Q1] q 元素类型样例：{type(st['q'].iloc[0])}", flush=True)
qexp = pd.DataFrame(st["q"].map(_aslist).tolist(), index=st.index)
qexp.columns = ["p001", "p01", "p99", "p999"]
st = pd.concat([st.drop(columns="q"), qexp], axis=1)
st["num_share"] = st["n_num"] / st["n"]
print(f"[Q1] items={len(st)}  elapsed={time.time() - t0:.0f}s", flush=True)

dom = st[st.num_share >= 0.8].sort_values("item_name").reset_index(drop=True)
print(f"[Q1] numeric-dominant (num_share>=0.8) = {len(dom)}（期望 563）", flush=True)
assert len(dom) == 563, f"数值主导项目数 {len(dom)} != 563（口径漂移，停）"

# ---------- 冻结件交叉校验（p0.001/p0.999 应逐位一致） ----------
fz = pd.read_csv(FROZEN, encoding="utf-8-sig")
mg = dom.merge(fz, on="item_name", suffixes=("_new", "_fz"))
assert len(mg) == len(dom), "冻结件项目集合对不上"
diff_p001 = float(np.max(np.abs(mg["p001_new"] - mg["p001_fz"])))
diff_p999 = float(np.max(np.abs(mg["p999_new"] - mg["p999_fz"])))
n_mismatch = int((mg["n_new"] != mg["n_fz"]).sum() + (mg["n_num_new"] != mg["n_num_fz"]).sum())
print(f"[XCHECK] 冻结件比对：max|Δp001|={diff_p001:.3e}  max|Δp999|={diff_p999:.3e}  n/n_num 不一致行={n_mismatch}", flush=True)
assert diff_p001 < 1e-6 and diff_p999 < 1e-6 and n_mismatch == 0, \
    "与冻结 Pass-1 口径超出浮点噪声级（停）"   # 实测 ~1e-12，机器精度级

# ---------- Q2：两套边界外行数（数值行第二遍扫描 + VALUES 连接） ----------
t0 = time.time()
vals = [(r.item_name, float(r.p001), float(r.p01), float(r.p99), float(r.p999))
        for r in dom.itertuples()]
q2 = f"""
WITH b(item_name, p001, p01, p99, p999) AS (VALUES %s)
SELECT d.item_name,
       COUNT(*) FILTER (WHERE d.v < b.p001 OR d.v > b.p999) AS oor_strict,
       COUNT(*) FILTER (WHERE d.v < b.p01  OR d.v > b.p99)  AS oor_loose
FROM (SELECT item_name, item_result::float8 AS v FROM {DET}
      WHERE item_result ~ '{NUM_RE}') d
JOIN b ON b.item_name = d.item_name
GROUP BY d.item_name"""
execute_values(cur, q2, vals, page_size=600)
cnt = pd.DataFrame(cur.fetchall(), columns=["item_name", "oor_strict", "oor_loose"])
print(f"[Q2] flagged-count 扫描完成  elapsed={time.time() - t0:.0f}s", flush=True)
cn.close()

res = dom.merge(cnt, on="item_name", how="left")
res[["oor_strict", "oor_loose"]] = res[["oor_strict", "oor_loose"]].fillna(0).astype("int64")
res["delta_rows"] = res["oor_loose"] - res["oor_strict"]
res["flagged_rate_released_pct"] = (res["oor_strict"] / res["n_num"] * 100).round(4)
res["flagged_rate_alt_pct"] = (res["oor_loose"] / res["n_num"] * 100).round(4)
res = res.sort_values(["delta_rows", "n_num"], ascending=False).reset_index(drop=True)
res = res[["item_name", "n", "n_num", "num_share", "p001", "p01", "p99", "p999",
           "oor_strict", "oor_loose", "delta_rows",
           "flagged_rate_released_pct", "flagged_rate_alt_pct"]]
res.to_csv(OUT, index=False, encoding="utf-8-sig")

# ---------- 汇总 ----------
num_rows = int(res["n_num"].sum())
strict_total = int(res["oor_strict"].sum())
loose_total = int(res["oor_loose"].sum())
delta_total = loose_total - strict_total
print("\n======== SIM-R3-3 汇总 ========")
print(f"items 全表 {len(st)}；数值主导 {len(res)}（num_share>=0.8）")
print(f"数值主导项目数值行合计 {num_rows:,}")
print(f"released p0.1/p99.9 拦截 {strict_total:,}（{strict_total / num_rows:.3%} of 数值行）")
print(f"alternative p1/p99   拦截 {loose_total:,}（{loose_total / num_rows:.3%} of 数值行）")
print(f"Δ 合计 +{delta_total:,}（median/item {float(res.delta_rows.median()):.0f}；"
      f"max/item {int(res.delta_rows.max()):,} @ {res.loc[0, 'item_name']}；"
      f"Δ=0 项目 {int((res.delta_rows == 0).sum())}）")
print("\nΔ 前 10 项目：")
print(res.head(10)[["item_name", "n_num", "oor_strict", "oor_loose", "delta_rows"]].to_string(index=False))
print(f"\n产物：{OUT}")
print(f"总耗时 {time.time() - t_all:.0f}s")
