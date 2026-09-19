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

BASE = r"<institution-path>"
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures", "sd")
os.makedirs(FIG, exist_ok=True)

# 2022 原始波（before）与修复后（after）；仅取数值列，标识列不读取不落盘
RAW_XLS = r"<institution-path>"
AFTER_CSV = r"<institution-path>"

OI = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442"]
plt.rcParams.update({
    "font.family": "Arial", "font.size": 8, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 300, "savefig.bbox": "tight"})


def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=400)
    fig.savefig(os.path.join(FIG, name + ".pdf"))
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

# 源数据库列
srcs = [("Cohort A — community adults\n7 waves · 122,575 records\n30,677 adults", 44),
        ("Cohort B — health management\n4 waves · 21.7 M lab rows\n71,209 person-years", 27),
        ("Cohort C — regional examination\n3 waves · 1,389,967 records\n54,490 death records", 10)]
for t, y in srcs:
    box(ax, 0.5, y, 26.5, 13, t, "#EFF5FB", "#0072B2", 5.6)
ax.text(13.75, 59.8, "Source databases\n(pseudonymised, 1:1 mirror)",
        ha="center", fontsize=7.0, style="italic")

# 四步闭环（竖列）
steps = [("1 · DETECT", "15 physiological signatures\n+ cross-year median scan\n+ correlation probes", 47),
         ("2 · QUANTIFY", "before/after contrasts\nscreening counts, medians\ngold-standard contamination", 33),
         ("3 · REPAIR", "true-value remapping\ncopy-shift (never in-place)\nnullify · deduplicate-flag", 19),
         ("4 · VERIFY", "residual signatures = 0\ncorrelation recovery\nregression · spot checks", 5)]
for t, sub, y in steps:
    box(ax, 32.5, y, 31, 10.5, f"{t}\n{sub}", "#FFF7EC", "#E69F00", 6.0)
for y1, y2 in [(47, 43.5), (33, 29.5), (19, 15.5)]:
    arrow(ax, 48, y1, 48, y2, "#E69F00", 1.4)
ax.text(48, 62.0, "Detect–Quantify–Repair–Verify closed loop",
        ha="center", fontsize=7.5, style="italic")

# 数据资产列
assets = [("Cleaned analysis layers", "DR1–DR3 · controlled access\nperson-wave / person-year\ntables + screening vars", 38, "#EDF7F0", "#009E73"),
          ("Governance artefacts", "DR4 · open\nsignature library · audits\nrepair reports · harness", 18, "#EDF7F0", "#009E73")]
for t, sub, y, fc, ec in assets:
    box(ax, 74.5, y, 26, 14, f"{t}\n{sub}", fc, ec, 5.8)
ax.text(87.5, 56.5, "Data records (this Descriptor)",
        ha="center", fontsize=7.0, style="italic")

# 源→闭环、闭环→资产
for y in (50.5, 33.5, 16.5):
    arrow(ax, 27.2, y, 32.3, y, "#0072B2", 1.3)
arrow(ax, 63.7, 52, 74.3, 45, "#009E73", 1.3)
arrow(ax, 63.7, 10, 74.3, 25, "#009E73", 1.3)

# 验证 harness 底条
box(ax, 33, -6.5, 30, 7.5, "Injection harness — 4,800 synthetic shifts\nrecall 0.985 · specificity 1.000 · blind re-detection 0.987",
    "#F5EEF8", "#CC79A7", 6.2)
arrow(ax, 48, -2.5, 48, 4.8, "#CC79A7", 1.3)
ax.text(48, -8.8, "technical validation (Fig. 3)", ha="center", fontsize=6.4,
        color="#CC79A7", style="italic")
ax.set_ylim(-10, 63)
save(fig, "fig1_overview")

# ================= Fig 2 — case study =================
fig = plt.figure(figsize=(7.2, 5.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.25], hspace=0.42, wspace=0.28)

# (a) 机制示意
axa = fig.add_subplot(gs[0, :])
axa.set_xlim(0, 100); axa.set_ylim(0, 10); axa.axis("off")
heads_before = ["ALT", "AST", "BUN", "Creatinine", "Uric acid", "TC", "…", "CA19-9", "FPG"]
xs = np.linspace(4, 90, 9)
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
axb.set_xticks(xb[::2] + 0.25)
axb.set_xticklabels([f"{b:.1f}" for b in bins[:-1]][::2], fontsize=6.2)
axb.axvline(9 - 0.5, color="#333333", lw=0.8, ls="--")
axb.text(9.15, axb.get_ylim()[1] * 0.88, "diabetes\ncut-off 7.0", fontsize=5.8, color="#333333")
axb.set_xlabel("Fasting plasma glucose (mmol/L)")
axb.set_ylabel("Rows (affected block, n=9,396)")
axb.legend(frameon=False, fontsize=6.2)
axb.text(0.03, 0.96, "b", transform=axb.transAxes, fontsize=10, fontweight="bold", va="top")

# (c) 筛查计数 before/after
axc = fig.add_subplot(gs[1, 1])
labels = ["Diabetes-screening\npositives", "ECG ST-T\npositives"]
b_vals = [1678, 1545]
a_vals = [2437, 3085]
x = np.arange(2); w = 0.36
axc.bar(x - w / 2, b_vals, w, color="#D55E00", alpha=0.85, label="before")
axc.bar(x + w / 2, a_vals, w, color="#009E73", alpha=0.85, label="after")
for xi, (bv, av) in enumerate(zip(b_vals, a_vals)):
    axc.text(xi - w / 2, bv + 150, f"{bv:,}", ha="center", fontsize=6.4)
    axc.text(xi + w / 2, av + 150, f"{av:,}", ha="center", fontsize=6.4)
axc.annotate("", xy=(0 + w / 2 - 0.03, 2380), xytext=(0.42, 2900),
             arrowprops=dict(arrowstyle="-|>", color="#333333", lw=0.9))
axc.text(0.66, 0.965, "568 fabricated positives\nremoved by repair",
         transform=axc.transAxes, fontsize=6.2, va="top", ha="center")
axc.set_xticks(x); axc.set_xticklabels(labels, fontsize=7)
axc.set_ylabel("Count (2022 wave)")
axc.set_ylim(0, 4200)
axc.legend(frameon=False, fontsize=6.2, loc="upper left", bbox_to_anchor=(0.02, 0.88))
axc.text(0.03, 0.97, "c", transform=axc.transAxes, fontsize=10, fontweight="bold", va="top")

for ax_, t in [(axa, "a")]:
    ax_.text(0.005, 0.97, t, transform=ax_.transAxes, fontsize=10, fontweight="bold", va="top")
save(fig, "fig2_case")

# ================= Fig 3 — validation performance =================
g = pd.read_csv(os.path.join(RES, "m2_grid_summary.csv"))
oc = pd.read_csv(os.path.join(RES, "m2_origin_coverage.csv"))
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
ax.text(0.02, 0.015, "pooled over 2,400 replicates:\nF1 = 0.992 · specificity = 1.000\nrepair accuracy = 0.998 · boundary error = 0 rows",
        transform=ax.transAxes, fontsize=5.4, color="#333333", ha="left", va="bottom",
        bbox=dict(fc="white", ec="#CCCCCC", lw=0.6, pad=2.0, alpha=0.92))
ax.text(0.03, 0.97, "a", transform=ax.transAxes, fontsize=10, fontweight="bold", va="top")

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
ax.text(0.93, 0.97, "14/22 origins ≥0.95;  blind spots (orange):\nlipid region · tumour markers · FPG itself",
        transform=ax.transAxes, fontsize=5.6, ha="right", va="top", color="#D55E00")
ax.text(0.06, 0.90, "b", transform=ax.transAxes, fontsize=10, fontweight="bold", va="top")

# (c) 盲态复盘
ax = axs[2]
ax.bar([0], [9500], 0.62, color="#BBBBBB")
ax.bar([0], [9381], 0.62, color="#009E73")
ax.bar([1], [0], 0.62, color="#D55E00")
ax.text(0, 9381 / 2, "9,381\nTP", ha="center", va="center", fontsize=6.4, color="white")
ax.text(0, 9650, "9,500 injected", ha="center", fontsize=6.0)
ax.text(1, 300, "out-of-block\nFP = 0", ha="center", fontsize=6.4, color="#D55E00")
ax.set_xticks([0, 1])
ax.set_xticklabels(["blind re-detection\n(2022 event)", "out-of-block\nFP"], fontsize=5.8)
ax.set_ylabel("Rows"); ax.set_ylim(0, 11200)
ax.text(0.03, 0.97, "c", transform=ax.transAxes, fontsize=10, fontweight="bold", va="top")

save(fig, "fig3_validation")
print("ALL SD FIGURES DONE")
