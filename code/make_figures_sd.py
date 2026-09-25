# -*- coding: utf-8 -*-
"""make_figures_sd.py — 论文00 Scientific Data 版三图（学术化）
Fig1 数据与治理总览（schematic）｜Fig2 列移位案例（机制+前后分布+计数）｜Fig3 注入验证性能
风格：Arial、Okabe-Ito、300dpi、PNG+PDF。数字均来自已锚定产物（verify_manuscript_numbers 117 项同源）。
用法：python make_figures_sd.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

BASE = r"D:\projects\Paper\论文00-多源体检队列数据治理与质量审计"
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures", "sd")
os.makedirs(FIG, exist_ok=True)

# ---- 工件驱动数字（S2 硬编码清零，周期3 建档轮）：与 verify_manuscript_numbers 同源运行时推导 ----
# 白名单留痕（定义性常数，不入工件驱动）：15 规则库、k=1 事件参数、fig2b 切片 7880:7880+9,396
import re as _re

_H_REP = open(r"D:\projects\Paper\00-清洗源数据库\docs\H_治理报告_wave重生成_20260925.md", encoding="utf-8").read()  # B68/B69 后现行报告（数字口径与旧件逐位同源）
_HM_REP = open(r"D:\projects\Paper\00-清洗源数据库\docs\H_mirror_治理报告_20260914.md", encoding="utf-8").read()
_PG_REP = open(r"D:\projects\Paper\00-清洗源数据库\docs\PG_治理报告_20260914.md", encoding="utf-8").read()
_PDM_REP = open(r"D:\projects\Paper\00-清洗源数据库\docs\PD_mirror_治理报告_v1.1_20260916.md", encoding="utf-8").read()
_SNAP = open(r"D:\projects\Paper\00-清洗源数据库\数据资产快照_v2.1.md", encoding="utf-8").read()
_NEG = open(os.path.join(RES, "m2_pd_negative.txt"), encoding="utf-8").read()
_BLIND = open(os.path.join(RES, "m2_blind2022.txt"), encoding="utf-8").read()
_GRID = pd.read_csv(os.path.join(RES, "m2_grid_summary.csv"))
_GRID_C = _GRID[_GRID.origin == "case"]
_OC = pd.read_csv(os.path.join(RES, "m2_origin_coverage.csv"))


def _x(pattern, src, cast=str):
    m = _re.search(pattern, src)
    assert m, f"工件缺 token: {pattern}"
    return cast(m.group(1).replace(",", "")) if cast is int else m.group(1)


N_A_REC = _x(r"波级输出: ([\d,]+) 行", _H_REP, int)            # 122,575
N_A_IND = _x(r"人级输出: ([\d,]+) 人", _H_REP, int)            # 30,677
N_B_PY = _x(r"人-年聚合: ([\d,]+) 行", _PG_REP, int)           # 71,209
N_B_IND = _x(r"人级输出: ([\d,]+) 人", _PG_REP, int)           # 51,296
N_B_LAB_M = f"{_x(r'检验长表 ([\d,]+) 万行', _SNAP, int) / 100:.1f} M"   # 21.7 M
N_C_REC = _x(r"行数: ([\d,]+)", _NEG, int)                     # 1,389,967
N_C_DEATH = _x(r"死因-Sheet1\] rows=(\d+)", _PDM_REP, int)     # 54,490
N_SHIFT = _x(r"移位修复 (\d+) 行", _HM_REP, int)               # 9,396
DM_PAIR = _x(r"筛查阳性 ([\d,]+→[\d,]+)", _SNAP)               # 1,678→2,437
STT_PAIR = _x(r"ST-T 阳性 ([\d,]+→[\d,]+)", _SNAP)             # 1,545→3,085
N_FAB = _x(r"其中 (\d+) 行为尿 pH 误判", _SNAP)                # 568
N_INJ = int(_GRID_C.reps.sum())                                # 4,800
RECALL_F = f"{_GRID_C.recall_med.median():.3f}"                # 0.985
SPEC_F = f"{_GRID_C.spec_med.median():.3f}"                    # 1.000
F1_F = f"{_GRID_C.f1_med.median():.3f}"                        # 0.992
REPAIR_F = f"{_GRID_C.repair_acc_med.median():.3f}"            # 0.998
BERR_F = f"{_GRID_C.berr_med.median():.0f}"                    # 0
BL_FLAG = _x(r"flagged ([\d,]+)", _BLIND, int)                 # 9,381
BL_TRUE = _x(r"注入真值行: ([\d,]+)", _BLIND, int)             # 9,500
BL_RECALL = f"{BL_FLAG / BL_TRUE:.3f}"                         # 0.987

# 2022 原始波（before）与修复后（after）；仅取数值列，标识列不读取不落盘
RAW_XLS = r"D:\projects\Data\H社区数据\体检数据2018-2024\2022年总数.xls"
AFTER_CSV = r"D:\projects\Paper\00-三线探索-多模态动态队列\data\processed\H_checkup_long_v2fix2022.csv"

OI = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442"]
plt.rcParams.update({
    "font.family": "Arial", "font.size": 8, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 300, "savefig.bbox": "tight"})


def save(fig, name):
    # 元数据抑制（审稿技能 §11 净化条款：生成器内建，禁事后修补）——PNG tEXt Software；PDF /Creator+/Producer+/CreationDate
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=400, metadata={"Software": None})
    fig.savefig(os.path.join(FIG, name + ".pdf"),
                metadata={"Creator": None, "Producer": None, "CreationDate": None})
    plt.close(fig)
    print(f"[fig] {name} done")


def box(ax, x, y, w, h, text, fc, ec=None, fs=7.5, tc="black", bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                                fc=fc, ec=ec or fc, lw=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, x1, y1, x2, y2, color="#444444", lw=1.2, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=9, color=color, lw=lw,
                                 shrinkA=0, shrinkB=0))


# ================= Fig 1 — overview schematic =================
fig, ax = plt.subplots(figsize=(7.2, 4.6))
ax.set_xlim(0, 100); ax.set_ylim(0, 64); ax.axis("off")

# 源数据库列（3 框与中列前三框同行对齐：y=47/33/19，高 10.5、间隙 3.5）
srcs = [(f"Cohort A — community adults\n7 waves · {N_A_REC:,} records\n{N_A_IND:,} adults", 47),
        (f"Cohort B — health management\n4 waves · {N_B_LAB_M} lab rows\n{N_B_PY:,} person-years", 33),
        (f"Cohort C — regional examination\n3 waves · {N_C_REC:,} records\n{N_C_DEATH:,} death records", 19)]
for t, y in srcs:
    box(ax, 0.5, y, 26.5, 10.5, t, "#EFF5FB", "#0072B2", 5.6)
ax.text(13.75, 62.2, "Source databases\n(pseudonymised, 1:1 mirror)",
        ha="center", va="top", fontsize=7.0, style="italic")

# 四步闭环（竖列）
steps = [("1 · DETECT", "15 physiological signatures\n+ cross-year median scan\n+ correlation probes", 47),
         ("2 · QUANTIFY", "before/after contrasts\nscreening counts, medians\nfabricated-diagnosis counts", 33),
         ("3 · REPAIR", "true-value remapping\ncopy-shift (never in-place)\nnullify · deduplicate-flag", 19),
         ("4 · VERIFY", "residual signatures = 0\ncorrelation recovery\nregression · spot checks", 5)]
for t, sub, y in steps:
    box(ax, 32.5, y, 31, 10.5, f"{t}\n{sub}", "#FFF7EC", "#E69F00", 6.0)
for y1, y2 in [(47, 43.5), (33, 29.5), (19, 15.5)]:
    arrow(ax, 48, y1, 48, y2, "#E69F00", 1.4)
ax.text(48, 62.2, "Detect–Quantify–Repair–Verify closed loop",
        ha="center", va="top", fontsize=7.5, style="italic")

# 数据资产列（2 框一组：高 10.5、间隙 3.5，组中心 31.25）
assets = [("Cleaned analysis layers", "DR1–DR3 · controlled access\nperson-wave / person-year\ntables + screening vars", 33, "#EDF7F0", "#009E73"),
          ("Governance artefacts", "DR4 · open\nsignature library · audits\nrepair reports · harness", 19, "#EDF7F0", "#009E73")]
for t, sub, y, fc, ec in assets:
    box(ax, 73.5, y, 25.5, 10.5, f"{t}\n{sub}", fc, ec, 5.8)
ax.text(86.25, 62.2, "Data records (this Descriptor)",
        ha="center", va="top", fontsize=7.0, style="italic")

# 源→闭环（左侧汇流线：三个库统一流入闭环起点 DETECT）
ax.plot([30.0, 30.0], [24.25, 52.25], color="#0072B2", lw=1.1,
        solid_capstyle="round", zorder=1)
for y in (52.25, 38.25, 24.25):
    ax.plot([27.2, 30.0], [y, y], color="#0072B2", lw=1.1, zorder=1)
arrow(ax, 30.0, 52.25, 32.3, 52.25, "#0072B2", 1.3)
# 闭环→资产（右侧汇流线：DR1–DR3 与 DR4 均为全闭环产出，非单步产出）
ax.plot([66.5, 66.5], [10.25, 52.25], color="#009E73", lw=1.1,
        solid_capstyle="round", zorder=1)
for y in (52.25, 38.25, 24.25, 10.25):
    ax.plot([63.7, 66.5], [y, y], color="#009E73", lw=1.1, zorder=1)
arrow(ax, 66.5, 38.25, 73.3, 38.25, "#009E73", 1.3)
arrow(ax, 66.5, 24.25, 73.3, 24.25, "#009E73", 1.3)

# 验证 harness 底条（与中列同宽 31、同高 10.5）
box(ax, 32.5, -9, 31, 10.5, f"Injection harness — {N_INJ:,} synthetic shifts\nrecall {RECALL_F} · specificity {SPEC_F}\nblind re-detection {BL_RECALL}",
    "#F5EEF8", "#CC79A7", 6.0)
arrow(ax, 48, 1.5, 48, 4.8, "#CC79A7", 1.3)
ax.text(48, -11.5, "technical validation (Fig. 3)", ha="center", fontsize=6.4,
        color="#CC79A7", style="italic")
ax.set_ylim(-13, 62.5)
save(fig, "fig1_overview")

# ================= Fig 2 — case study =================
fig = plt.figure(figsize=(7.2, 5.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.25], hspace=0.24, wspace=0.28)

# (a) 机制示意
axa = fig.add_subplot(gs[0, :])
axa.set_xlim(0, 100); axa.set_ylim(0, 10); axa.axis("off")
heads_before = ["ALT", "AST", "BUN", "Creatinine", "Uric acid", "TC", "…", "CA19-9", "FPG"]
xs = np.linspace(5.5, 90.5, 9)  # 首框左缘 0.4，防 ALT 左边框被轴裁切
axa.text(2, 8.6, "Stored layout after the 2022 template change (ALT column dropped):", fontsize=7.2)
for x, h in zip(xs, heads_before):
    box(axa, x - 5.1, 5.2, 10.2, 2.3, h, "#FDEDEC", "#D55E00", 4.8)
axa.text(97, 6.3, "k=1", fontsize=6.5, color="#D55E00", va="center")
true_vals = ["AST", "BUN", "Creatinine", "Uric acid", "TC", "TG", "…", "FPG", "Urine pH"]
axa.text(2, 3.6, "true value now in column:", fontsize=7.2)
for x, v in zip(xs, true_vals):
    axa.text(x, 2.5, v, ha="center", fontsize=5.6, color="#333333")
for x in xs[1:]:
    arrow(axa, x + 3.9, 4.9, x - 1.2, 4.9, "#D55E00", 1.0)
axa.text(50, 0.6, "every value from the loss position shifts one column left — urine pH occupies the FPG position",
         ha="center", fontsize=6.4, color="#D55E00", style="italic")

# (b) 污染段 grouped bar：stored（离散尿 pH 尺度） vs repaired（连续 FPG）
axb = fig.add_subplot(gs[1, 0])
raw = pd.read_excel(RAW_XLS)
fpg_col = [c for c in raw.columns if c.startswith("空腹血糖")][0]
seg = pd.to_numeric(raw[fpg_col].iloc[7880:7880 + 9396], errors="coerce").dropna()
seg = seg[(seg >= 2.5) & (seg <= 20)]
after = pd.read_csv(AFTER_CSV, encoding="utf-8-sig", low_memory=False)
fpg_after = pd.to_numeric(after["fpg"].iloc[7880:7880 + 9396], errors="coerce").dropna()
fpg_after = fpg_after[(fpg_after >= 2.5) & (fpg_after <= 20)]
bins = np.arange(2.5, 12.5, 0.5)
cnt_b, _ = np.histogram(seg, bins=bins)
cnt_a, _ = np.histogram(fpg_after, bins=bins)
xb = np.arange(len(cnt_b)); w = 0.4
axb.bar(xb - w / 2, cnt_b, w, color="#D55E00", label="before (stored: urine pH)")
axb.bar(xb + w / 2, cnt_a, w, color="#009E73", label="after (repaired FPG)")
axb.set_xticks(np.arange(-0.5, len(cnt_b), 2))  # 刻度落在真实数据位置（bin 左边界值）
axb.set_xticklabels([f"{b:.1f}" for b in bins[:-1]][::2], fontsize=6.2)
axb.axvline(9 - 0.5, color="#333333", lw=0.8, ls="--")
axb.text(9.15, axb.get_ylim()[1] * 0.88, "diabetes\ncut-off 7.0", fontsize=5.8, color="#333333")
axb.set_xlabel("Fasting plasma glucose (mmol/L)")
axb.set_ylabel(f"Rows (affected block, n={N_SHIFT:,})")
axb.legend(frameon=False, fontsize=6.2)
axb.text(0.005, 1.01, "b", transform=axb.transAxes, fontsize=10, fontweight="bold",
         va="bottom")

# (c) 筛查计数 before/after（工件驱动：快照 1,678→2,437 / 1,545→3,085）
axc = fig.add_subplot(gs[1, 1])
labels = ["Diabetes-screening\npositives", "ECG ST-T\npositives"]
_dm_b, _dm_a = (int(v.replace(",", "")) for v in DM_PAIR.split("→"))
_st_b, _st_a = (int(v.replace(",", "")) for v in STT_PAIR.split("→"))
b_vals = [_dm_b, _st_b]
a_vals = [_dm_a, _st_a]
x = np.arange(2); w = 0.36
axc.bar(x - w / 2, b_vals, w, color="#D55E00", alpha=0.85, label="before")
axc.bar(x + w / 2, a_vals, w, color="#009E73", alpha=0.85, label="after")
for xi, (bv, av) in enumerate(zip(b_vals, a_vals)):
    axc.text(xi - w / 2, bv + 150, f"{bv:,}", ha="center", fontsize=6.4)
    axc.text(xi + w / 2, av + 150, f"{av:,}", ha="center", fontsize=6.4)
axc.text(0.5, 3950, f"{N_FAB} fabricated positives removed by repair (diabetes screening)",
         ha="center", fontsize=5.8, color="#333333")
axc.set_xticks(x); axc.set_xticklabels(labels, fontsize=7)
axc.set_ylabel("Count (2022 wave)")
axc.set_ylim(0, 4200)
axc.legend(frameon=False, fontsize=6.2, loc="upper left", bbox_to_anchor=(0.02, 0.88))
axc.text(0.005, 1.01, "c", transform=axc.transAxes, fontsize=10, fontweight="bold",
         va="bottom")

for ax_, t in [(axa, "a")]:
    ax_.text(0.005, 0.97, t, transform=ax_.transAxes, fontsize=10, fontweight="bold", va="top")
save(fig, "fig2_case")

# ================= Fig 3 — validation performance =================
g, oc = _GRID, _OC
fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.7), gridspec_kw={"width_ratios": [1.15, 1.25, 0.72]})
plt.subplots_adjust(wspace=0.42)

# (a) 12 case-origin 格：recall med 点 + p05–med 线；注释框给 F1/repair/blockdet
ax = axs[0]
gg = g[g.origin == "case"].copy()
gg["cell"] = gg["k"].astype(str) + " · " + (gg["rate"] * 100).astype(int).astype(str) + "% · " + gg["block"]
gg = gg.sort_values(["k", "rate", "block"], ascending=[True, False, True])
order = gg.cell.tolist()
yp = np.arange(len(order))
ax.hlines(yp, gg.recall_p05, gg.recall_med, color="#009E73", lw=1.8, alpha=0.9)
ax.plot(gg.recall_med, yp, "o", color="#009E73", ms=3.4)
ax.set_yticks(yp); ax.set_yticklabels(order, fontsize=5.8)
ax.axvline(0.95, color="#D55E00", lw=0.8, ls="--")
ax.text(0.953, 11.35, "0.95", fontsize=5.6, color="#D55E00", ha="left")
ax.set_xlim(0.90, 1.012)
ax.set_xlabel("Row-level recall per grid cell\n(line = 5th–50th percentile)")
ax.set_ylim(-3.1, 11.3)
ax.text(0.02, 0.015, f"pooled over {N_INJ:,} replicates:\nF1 = {F1_F} · specificity = {SPEC_F}\nrepair accuracy = {REPAIR_F}\nboundary error = {BERR_F} rows",
        transform=ax.transAxes, fontsize=5.2, color="#333333", ha="left", va="bottom",
        bbox=dict(fc="white", ec="#CCCCCC", lw=0.6, pad=2.0, alpha=0.92))
ax.text(0.005, 1.01, "a", transform=ax.transAxes, fontsize=10, fontweight="bold",
        va="bottom")

# (b) 覆盖谱
ax = axs[1]
ocm = oc.groupby("origin_col")["recall"].median().sort_values(ascending=False)
colors = ["#009E73" if v >= 0.95 else "#D55E00" for v in ocm.values]
ax.hlines(np.arange(len(ocm)), 0, ocm.values, color=colors, lw=2.4)
ax.plot(ocm.values, np.arange(len(ocm)), "o", color="#333333", ms=2.6)
ax.set_yticks(np.arange(len(ocm)))
ax.set_yticklabels([c.replace("_", " ") for c in ocm.index], fontsize=5.6)
ax.axvline(0.95, color="#444444", lw=0.8, ls="--")
ax.set_xlim(-0.04, 1.06)
ax.set_xlabel("Median recall by shift origin (k=1, r=5%)")
_n_cov = int((ocm.values >= 0.95).sum())
ax.text(0.17, 0.985, f"{_n_cov}/{len(ocm)} origins ≥0.95;\nblind spots (orange):\nlipid · tumour markers · FPG",
        transform=ax.transAxes, fontsize=5.2, ha="left", va="top", color="#D55E00")
ax.text(0.005, 1.01, "b", transform=ax.transAxes, fontsize=10, fontweight="bold",
        va="bottom")

# (c) 盲态复盘（工件驱动：m2_blind2022.txt 计数直推）
ax = axs[2]
ax.bar([0], [BL_TRUE], 0.62, color="#BBBBBB")
ax.bar([0], [BL_FLAG], 0.62, color="#009E73")
ax.bar([1], [0], 0.62, color="#D55E00")
ax.text(0, BL_FLAG / 2, f"{BL_FLAG:,}\nTP", ha="center", va="center", fontsize=6.4, color="white")
ax.text(0, BL_TRUE * 1.016, f"{BL_TRUE:,}\ninjected", ha="center", va="bottom", fontsize=5.8)  # 两行收窄，不触纵轴
ax.text(1, 350, "0", ha="center", fontsize=6.6, color="#D55E00", fontweight="bold")
ax.set_xticks([0, 1])
ax.set_xticklabels(["blind re-detection\n(2022 event)", "out-of-block\nFP"], fontsize=5.8)
ax.set_ylabel("Rows"); ax.set_ylim(0, 11200)
ax.text(0.005, 1.01, "c", transform=ax.transAxes, fontsize=10, fontweight="bold",
        va="bottom")

save(fig, "fig3_validation")
print("ALL SD FIGURES DONE")
