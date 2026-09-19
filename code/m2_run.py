# -*- coding: utf-8 -*-
"""m2_run.py —— 论文00 M2 注入式模拟实验：编排与执行

四个实验块（对齐 研究设计与叙事.md §3）：
  A. 网格注入（主实验台：库A 非移位波次 2018-2021 + 2023-2024）
     网格 k∈{1,2} × r∈{1%,5%,10%} × 块形态{连续,分散} × 起点{案例位(ALT),随机} × B=200
  B. 库C 阴性对照：未注入时签名阳性率（特异度的真实世界实证）
  C. 库C 可移植性抽查：同一注入算子（k=1, r=5%, 连续, 随机起点, 50 次）
  D. 盲态 2022 复盘：在已修复的 2022 波上按真实模式（自第 7,880 行起、自 ALT 位缺 1 列）
     重注 corrupted 形态，检测器盲态检测，对照注入真值与历史 9,396 行口径

时间外推：网格按注入主导波次分层报告（2018-2021 校准域 vs 2023-2024 外推域）。
并行：multiprocessing Pool(12)（MACHINE_PROFILE 规则：worker=min(任务,12)）。

用法：
  python m2_run.py --smoke   # 冒烟：B=3，每块只跑 1 个代表格
  python m2_run.py           # 全量：24 格 × B=200

输出：论文00/results/m2_*.csv|.txt；论文00/figures/m2_fig3_performance.png
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m2_framework import (evaluate_signatures, inject_shift, repair_shift,
                          confusion_metrics, block_boundary, dm_fabrication,
                          h_rule_set, pd_rule_set)

ROOT = r"<institution-path>"
H_PATH = os.path.join(ROOT, r"00-清洗源数据库\data\H\H_wave_level_v1.0.csv.gz")
PD_PATH = os.path.join(ROOT, r"00-清洗源数据库\data\PD\PD_wave_level_v1.1.csv.gz")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
os.makedirs(RES, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

SEED = 20260915
# 库A 模板列序（依 G01b FIELDMAP 复原的近似顺序；案例起点 = ALT 位）。
# 尾列 urine_ph 为合成尿 pH（N(6.2,0.5) 截断 [4.5,8.5]，固定种子）：真实模板中 FPG
# 之后为尿 pH，2022 事件中正是它顶替 FPG 位——P(pH>=7)≈5.5% × 9,396 行 ≈ 历史
# 口径 568 行假阳性，量纲自洽。
H_TEMPLATE = ["height", "weight", "bmi", "waist", "sbp", "dbp", "wbc", "plt", "hb",
              "tbil", "alt", "ast", "bun", "crea", "ua", "tc", "tg", "hdl", "ldl",
              "afp", "cea", "ca199", "fpg", "urine_ph"]
ALT_IDX = H_TEMPLATE.index("alt")
# 库C 模板列序
PD_TEMPLATE = ["height", "weight", "bmi", "waist", "sbp", "dbp", "fpg", "tc", "tg",
               "hdl", "ldl", "urea", "crea", "ua", "tbil", "alt", "ast", "tp", "alb", "glob"]

_G = {}  # worker 全局（Windows spawn 经 initializer 传入）


# ---------------------------------------------------------------- 基底构建

def build_h_substrate():
    df = pd.read_csv(H_PATH, usecols=H_TEMPLATE[:-1] + ["year"], dtype=np.float32)
    df["year"] = df["year"].astype(int)
    # 合成尿 pH 尾列（固定种子，基底确定性）
    ph_rng = np.random.default_rng(SEED)
    ph = np.clip(ph_rng.normal(6.2, 0.5, size=len(df)), 4.5, 8.5)
    df["urine_ph"] = ph.astype(np.float32)
    sub = df[df["year"] != 2022].reset_index(drop=True)
    inj = df[df["year"] == 2022].reset_index(drop=True)
    return sub, inj


def build_pd_substrate():
    df = pd.read_csv(PD_PATH, usecols=PD_TEMPLATE, dtype=np.float32)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 单次实验

def run_one_replicate(true_vals, year_arr, rule_fn, template, rng, k, rate,
                      block_mode, origin_mode, case_origin_idx):
    n_rows, n_cols = true_vals.shape
    n_inj = int(round(rate * n_rows))
    # 行块
    if block_mode == "contig":
        start = int(rng.integers(0, n_rows - n_inj + 1))
        row_idx = np.arange(start, start + n_inj)
    else:
        row_idx = np.sort(rng.choice(n_rows, size=n_inj, replace=False))
        start = int(row_idx[0])
    # 起点
    if origin_mode == "case":
        o = case_origin_idx
    else:
        o = int(rng.integers(1, n_cols - k - 1))  # 避开首尾，保证移位有效
        if o == case_origin_idx:
            o = (o + 1) % (n_cols - k - 1) + 1
    # 注入
    mask = np.zeros(n_rows, dtype=bool)
    mask[row_idx] = True
    inj = inject_shift(true_vals, o, k, row_idx)
    # 检测
    inj_df = pd.DataFrame(inj, columns=template)
    flagged, _, _ = evaluate_signatures(inj_df, rule_fn)
    # 指标
    m = confusion_metrics(mask, flagged)
    flag_idx = np.where(flagged)[0]
    if block_mode == "contig":
        detected, berr = block_boundary(flag_idx, start, n_inj)
    else:
        detected, berr = (m["tp"] > 0), np.nan
    # 修复（origin/k 由模板比对给出 = 真值；行集 = 检测输出）
    rep = repair_shift(inj, o, k, flag_idx)
    lo, hi = o + k, n_cols
    tp_rows = np.where(mask & flagged)[0]
    if len(tp_rows):
        cell_acc = float(np.mean(rep[np.ix_(tp_rows, np.arange(lo, hi))] ==
                                 true_vals[np.ix_(tp_rows, np.arange(lo, hi))]))
    else:
        cell_acc = np.nan
    # 临床后果：不修复时的假糖尿病阳性（fpg 位被尿 pH 顶替）
    fpg_idx = template.index("fpg")
    dm_fab = dm_fabrication(true_vals[:, fpg_idx], inj[:, fpg_idx])
    # 主导波次（连续块取起点行所在波；分散取注入行波次众数）
    if block_mode == "contig":
        wave_dom = int(year_arr[start])
    else:
        wave_dom = int(pd.Series(year_arr[row_idx]).mode().iloc[0])
    return dict(k=k, rate=rate, block=block_mode, origin=origin_mode,
                n_inj=n_inj, start=start, origin_idx=o,
                wave_group=("2018-2021" if wave_dom <= 2021 else "2023-2024"),
                tp=m["tp"], fp=m["fp"], fn=m["fn"], tn=m["tn"],
                recall=m["recall"], precision=m["precision"],
                specificity=m["specificity"], f1=m["f1"],
                block_detected=bool(detected), boundary_err=berr,
                dm_fabricated=dm_fab, repair_cell_acc=cell_acc)


# ---------------------------------------------------------------- worker

def _init(sub_vals, sub_years):
    _G["vals"] = sub_vals
    _G["years"] = sub_years


def _work(task):
    k, rate, block, origin, rep_i, seed = task
    rng = np.random.default_rng(seed)
    return run_one_replicate(_G["vals"], _G["years"], h_rule_set, H_TEMPLATE,
                             rng, k, rate, block, origin, ALT_IDX)


# ---------------------------------------------------------------- 报告

def agg_summary(rep_df):
    g = rep_df.groupby(["k", "rate", "block", "origin"], dropna=False)
    out = g.agg(
        reps=("rep", "count"),
        recall_med=("recall", "median"), recall_p05=("recall", lambda s: s.quantile(.05)),
        f1_med=("f1", "median"),
        spec_med=("specificity", "median"),
        fp_med=("fp", "median"), fp_p95=("fp", lambda s: s.quantile(.95)),
        blockdet=("block_detected", "mean"),
        berr_med=("boundary_err", "median"),
        berr_p90=("boundary_err", lambda s: s.quantile(.90)),
        dmfab_med=("dm_fabricated", "median"),
        repair_acc_med=("repair_cell_acc", "median"),
    ).reset_index()
    return out


def wave_summary(rep_df):
    g = rep_df.groupby(["wave_group", "k", "rate"], dropna=False)
    return g.agg(reps=("rep", "count"), recall_med=("recall", "median"),
                 f1_med=("f1", "median")).reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    B = 3 if args.smoke else 200
    print(f"[m2] B={B}（{'冒烟' if args.smoke else '全量'}）", flush=True)

    # ---- 基底 ----
    sub_df, inj2022_df = build_h_substrate()
    sub_vals = sub_df[H_TEMPLATE].to_numpy(dtype=np.float32)
    sub_years = sub_df["year"].to_numpy(dtype=int)
    print(f"[m2] 库A 注入基底：{sub_vals.shape[0]:,} 行 × {sub_vals.shape[1]} 列"
          f"（非移位波次 2018-2021 + 2023-2024）", flush=True)

    # 基线静默检查
    base_hit, base_rule, n_rules = evaluate_signatures(sub_df[H_TEMPLATE], h_rule_set)
    base_rate = base_hit.mean()
    print(f"[m2] 基线签名阳性率（干净基底，{n_rules} 条数值规则）：{base_hit.sum():,} 行"
          f"（{base_rate:.4%}）", flush=True)

    # ---- A. 网格注入 ----
    ks = [1, 2]
    rates = [0.01, 0.05, 0.10]
    blocks = ["contig", "scatter"]
    origins = ["case", "random"]
    cells = [(k, r, b, o) for k in ks for r in rates for b in blocks for o in origins]
    if args.smoke:
        cells = cells[:2]
    tasks = []
    for ci, (k, r, b, o) in enumerate(cells):
        for i in range(B):
            tasks.append((k, r, b, o, i, SEED + ci * 1_000_000 + i))  # 确定性种子
    print(f"[m2] 网格 {len(cells)} 格 × B={B} = {len(tasks)} 次注入，Pool(12) 并行…", flush=True)
    rows = []
    with Pool(min(12, os.cpu_count() or 4), initializer=_init,
              initargs=(sub_vals, sub_years)) as p:
        for i, res in enumerate(p.imap_unordered(_work, tasks, chunksize=4)):
            res["rep"] = i
            rows.append(res)
            if (i + 1) % 200 == 0:
                print(f"[m2]   {i+1}/{len(tasks)}  {time.time()-t0:.0f}s", flush=True)
    rep_df = pd.DataFrame(rows)
    rep_df.to_csv(os.path.join(RES, "m2_replicates.csv.gz"), index=False,
                  encoding="utf-8-sig")
    summ = agg_summary(rep_df)
    summ.to_csv(os.path.join(RES, "m2_grid_summary.csv"), index=False,
                encoding="utf-8-sig")
    wsum = wave_summary(rep_df)
    wsum.to_csv(os.path.join(RES, "m2_wave_extrapolation.csv"), index=False,
                encoding="utf-8-sig")
    print(f"[m2] 网格汇总 -> m2_grid_summary.csv（{len(summ)} 行）；逐次 -> m2_replicates.csv.gz", flush=True)

    # ---- B. 库C 阴性对照 ----
    pd_df = build_pd_substrate()
    hit_pd, per_rule_pd, _ = evaluate_signatures(pd_df, pd_rule_set)
    pd_rate = hit_pd.mean()
    print(f"[m2] 库C 阴性对照：{len(pd_df):,} 行未注入，签名阳性 {int(hit_pd.sum()):,}"
          f"（{pd_rate:.4%}）", flush=True)
    rule_txt = ", ".join(f"{k}={int(v.sum())}" for k, v in per_rule_pd.items())
    with open(os.path.join(RES, "m2_pd_negative.txt"), "w", encoding="utf-8") as f:
        f.write("库C 阴性对照（未注入）\n"
                f"行数: {len(pd_df):,}\n签名阳性行: {int(hit_pd.sum()):,}\n"
                f"阳性率: {pd_rate:.4%}\n逐规则: {rule_txt}\n")

    # ---- C. 库C 可移植性抽查 ----
    pd_vals = pd_df[PD_TEMPLATE].to_numpy(dtype=np.float32)
    rng = np.random.default_rng(SEED + 1)
    prows = []
    for i in range(50):
        r = run_one_replicate(pd_vals, np.zeros(len(pd_df), dtype=int), pd_rule_set,
                              PD_TEMPLATE, rng, 1, 0.05, "contig", "random",
                              PD_TEMPLATE.index("alt"))
        r["rep"] = i
        prows.append(r)
    pd_port = pd.DataFrame(prows)
    pd_port.to_csv(os.path.join(RES, "m2_pd_portability.csv"), index=False,
                   encoding="utf-8-sig")
    print(f"[m2] 库C 可移植性抽查（50 次, k=1, r=5%, 连续, 随机起点）："
          f"recall 中位 {pd_port['recall'].median():.3f}，"
          f"f1 中位 {pd_port['f1'].median():.3f}", flush=True)

    # ---- C2. 起点覆盖谱（刻画签名库检测覆盖边界；r=5%, k=1, 连续, 每起点 20 次） ----
    ocov_rows = []
    for o in range(1, len(H_TEMPLATE) - 1):
        for i in range(20):
            r = run_one_replicate(sub_vals, sub_years, h_rule_set, H_TEMPLATE,
                                  np.random.default_rng(SEED + 7777 + o * 100 + i),
                                  1, 0.05, "contig", "case", o)
            r["origin_idx"] = o
            r["origin_col"] = H_TEMPLATE[o]
            r["rep"] = i
            ocov_rows.append(r)
    ocov = pd.DataFrame(ocov_rows)
    ocov.to_csv(os.path.join(RES, "m2_origin_coverage.csv"), index=False,
                encoding="utf-8-sig")
    cov = ocov.groupby("origin_col")["recall"].median().sort_values(ascending=False)
    print(f"[m2] 起点覆盖谱 -> m2_origin_coverage.csv；"
          f"最高 {cov.index[0]}（{cov.iloc[0]:.3f}）/ 最低 {cov.index[-1]}（{cov.iloc[-1]:.3f}）",
          flush=True)

    # ---- D. 盲态 2022 复盘 ----
    inj_vals = inj2022_df[H_TEMPLATE].to_numpy(dtype=np.float32)
    n22 = inj_vals.shape[0]
    start22 = min(7880, n22 - 1)
    row_idx = np.arange(start22, n22)
    corr = inject_shift(inj_vals, ALT_IDX, 1, row_idx)
    corr_df = pd.DataFrame(corr, columns=H_TEMPLATE)
    flag22, _, _ = evaluate_signatures(corr_df, h_rule_set)
    truth_mask22 = np.zeros(n22, dtype=bool)
    truth_mask22[row_idx] = True
    m22 = confusion_metrics(truth_mask22, flag22)
    truth_in = flag22[row_idx]
    with open(os.path.join(RES, "m2_blind2022.txt"), "w", encoding="utf-8") as f:
        f.write("盲态 2022 复盘\n"
                f"2022 波行数: {n22:,}\n"
                f"重注模式: 自第 {start22:,} 行起、自 ALT 位缺 1 列（真实生成机制）\n"
                f"注入真值行: {len(row_idx):,}（历史口径 9,396 行）\n"
                f"检出: 总 flagged {int(flag22.sum()):,}；块内 TP {m22['tp']:,}；"
                f"块外 FP {m22['fp']:,}\n"
                f"召回: {m22['recall']:.4f}；特异: {m22['specificity']:.4f}\n"
                f"历史修复口径 9,396 行与本次注入行数差 = 原始文件中模板混排行\n")
    print(f"[m2] 盲态 2022：TP {m22['tp']:,}/{len(row_idx):,}"
          f"（recall {m22['recall']:.4f}），块外 FP {m22['fp']:,}", flush=True)

    # ---- 图 3 ----
    plot_fig3(rep_df, summ, ocov)
    print(f"[m2] 完成，总耗时 {time.time()-t0:.0f}s", flush=True)


def plot_fig3(rep_df, summ, ocov):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9))
    # (a) recall 热图：k × rate（合并块形态与起点）
    piv = rep_df.groupby(["k", "rate"])["recall"].median().unstack()
    ax = axes[0, 0]
    im = ax.imshow(piv.to_numpy(), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(piv.columns)), [f"{c:.0%}" for c in piv.columns])
    ax.set_yticks(range(len(piv.index)), [f"k={k}" for k in piv.index])
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.to_numpy()[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=10)
    ax.set_title("(a) Row-level recall (median, pooled over block/origin)")
    ax.set_xlabel("injection rate r"); ax.set_ylabel("shifted columns k")
    fig.colorbar(im, ax=ax, shrink=0.8)
    # (b) F1 热图
    piv2 = rep_df.groupby(["k", "rate"])["f1"].median().unstack()
    ax = axes[0, 1]
    im = ax.imshow(piv2.to_numpy(), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(piv2.columns)), [f"{c:.0%}" for c in piv2.columns])
    ax.set_yticks(range(len(piv2.index)), [f"k={k}" for k in piv2.index])
    for i in range(piv2.shape[0]):
        for j in range(piv2.shape[1]):
            v = piv2.to_numpy()[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=10)
    ax.set_title("(b) F1 (median)")
    ax.set_xlabel("injection rate r"); ax.set_ylabel("shifted columns k")
    fig.colorbar(im, ax=ax, shrink=0.8)
    # (c) 连续块起点定位误差
    ax = axes[1, 0]
    bc = rep_df[(rep_df["block"] == "contig") & rep_df["boundary_err"].notna()]
    labels, data = [], []
    for (k, r), gsub in bc.groupby(["k", "rate"]):
        labels.append(f"k={k}\n{r:.0%}")
        data.append(gsub["boundary_err"].to_numpy())
    if data:
        bp = ax.boxplot(data, tick_labels=labels, showfliers=False, patch_artist=True)
        for patch in bp["boxes"]:
            patch.set_facecolor("#DEEBF7")
    ax.set_title("(c) Boundary-localisation error, contiguous blocks")
    ax.set_xlabel("grid cell"); ax.set_ylabel("detected start − true start (rows)")
    # (d) 起点覆盖谱
    ax = axes[1, 1]
    cov = ocov.groupby("origin_col")["recall"].median().sort_values(ascending=False)
    ax.bar(range(len(cov)), cov.to_numpy(), color="#2E75B6")
    ax.set_xticks(range(len(cov)), list(cov.index), rotation=60, ha="right", fontsize=8)
    ax.axhline(0.95, color="#C00000", lw=1, ls="--", label="0.95")
    ax.set_ylim(0, 1.02)
    ax.set_title("(d) Detection coverage by shift origin (k=1, r=5%)")
    ax.set_xlabel("deleted (missing) template column"); ax.set_ylabel("recall (median)")
    ax.legend(loc="lower left")
    fig.tight_layout()
    out = os.path.join(FIG, "m2_fig3_performance.png")
    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"[m2] 图 -> {out}", flush=True)


if __name__ == "__main__":
    main()
