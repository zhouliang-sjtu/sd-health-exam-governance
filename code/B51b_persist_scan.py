# -*- coding: utf-8 -*-
"""B51b_persist_scan.py —— D-008/D-016 收口：PD 全列域扫描落盘 + PG 数值审计落盘 + PD 葡萄糖甄别
D-008：B51 扫描结论此前只在控制台，本脚本持久化产物（results/B51b_*）。
D-016：PD `葡萄糖`列尿糖定性/血糖数值混装甄别——
  甄别规则（B52 预定）：带 mmol/L 量纲的纯数值（1–40）且形态为血糖报告者保留为 fpg；
  定性词（阴性/弱阳性/阳性/±/++…）归尿糖定性，不得进入 fpg≥7.0 分类。
输出：results/B51_pd_domain_scan.csv、B51_pg_numeric_audit.csv、
      D016_pd_glucose_disposition.csv、B51b_D008_D016_report.md
"""
import os
import re
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GOV = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(GOV, "results")
os.makedirs(OUT, exist_ok=True)
PD_WAVE = r"<institution-path>"
PD_LONG = r"<institution-path>"
PG_ARM = r"<institution-path>"

report = []


def rep(s=""):
    print(s)
    report.append(s)


# ================= PD 全列域扫描（优先长表，回退发布波次层） =================
pd_path = PD_LONG if os.path.exists(PD_LONG) else PD_WAVE
src_label = "pd_checkup_long（机构侧分析长表）" if pd_path == PD_LONG else "PD_wave_level_v1.1（发布波次层回退）"
rep(f"======== PD 全列域扫描（{src_label}）========")
D = pd.read_csv(pd_path, encoding="utf-8-sig", low_memory=False)
rep(f"{len(D):,} 行 × {D.shape[1]} 列")

DOMS = {
    "ECG": re.compile(r"窦性|心电|ST|T波|房颤|早搏|传导阻滞|电轴|Q波|起搏|低电压"),
    "US": re.compile(r"脂肪肝|胆囊|胆结石|肝囊肿|肾囊肿|血管瘤|回声|肝脏|脾脏|胰腺|腹腔|结石"),
    "QUAL": re.compile(r"^(阴性|弱阳性|阳性|\d+\+|\++|\+-|±|-|×|未见|正常|无)([\(\（].*)?$"),
    "RADIO": re.compile(r"CT|MRI|X线|摄片|影像|放射"),
    "MAIN": re.compile(r"建议|随访|复查|定期|必要时"),
    "SYMPTOM": re.compile(r"头晕|头痛|心悸|胸闷|咳嗽|发热|乏力|多饮|多尿|消瘦"),
}
HDR_RULES = [
    ("ECG", re.compile(r"心电图")), ("US", re.compile(r"B超|超声|腹部")),
    ("SYMPTOM", re.compile(r"症状|腰围|臀围|体温|脉率|呼吸|身高|体重|指数|血压|听力|视力|口腔|皮肤|巩膜|淋巴|桶状|肺|心脏|腹部|运动功能")),
    ("DEMOG", re.compile(r"年龄|性别|日期|吸烟|饮酒|疾病|自我评估|饮食|锻炼|戒酒|醉酒|酒| ID|^id$")),
    ("BIOCHEM", re.compile(r"葡萄糖|胆固醇|甘油三酯|脂蛋白|尿素|肌酐|尿酸|胆红素|转氨酶|蛋白")),
]
DOM_MAP = {"ECG": "ECG", "US": "US", "BIOCHEM": "BIOCHEM", "SYMPTOM": "SYMPTOM"}


def header_domain(h):
    for k, rex in HDR_RULES:
        if rex.search(h):
            return k
    return "UNMAPPED"


def seg_dom(t):
    segs = [s for s in re.split(r"[。；;,，\n]", str(t)) if s.strip()]
    cnt = {k: 0 for k in DOMS}
    for s in segs:
        for k, rex in DOMS.items():
            if rex.search(s):
                cnt[k] += 1
    hits = {k: v for k, v in cnt.items() if v > 0}
    return max(hits, key=hits.get) if hits else "NONE"


scan_rows = []
for h in D.columns:
    if h in ("id", "year"):
        continue
    s = D[h].fillna("").astype(str).str.strip()
    snz = s[s != ""]
    ne = len(snz)
    if ne < 50:
        continue
    hd = header_domain(h)
    numv = pd.to_numeric(snz.str.replace(r"[↑↓]", "", regex=True)
                         .str.extract(r"([-+]?\d+(?:\.\d+)?)")[0], errors="coerce")
    numeric_pct = float(numv.notna().mean() * 100)
    doms = snz.map(seg_dom)
    dr = doms[doms != "NONE"]
    top = dr.value_counts().index[0] if len(dr) else "NONE"
    pct = dr.value_counts().iloc[0] / len(dr) * 100 if len(dr) else 0.0
    qual = snz.map(lambda t: bool(DOMS["QUAL"].match(t))).mean() * 100 if ne else 0.0
    expect = DOM_MAP.get(hd)
    mismatch = (top != expect and pct >= 20 and qual < 60 and hd in DOM_MAP and numeric_pct <= 95)
    scan_rows.append({"column": h, "header_domain": hd, "nonempty": ne,
                      "numeric_pct": round(numeric_pct, 1), "top_domain": top,
                      "top_share_pct": round(pct, 1), "qualitative_pct": round(qual, 1),
                      "expect": expect or "-", "mismatch": mismatch})
scan = pd.DataFrame(scan_rows)
scan.to_csv(os.path.join(OUT, "B51_pd_domain_scan.csv"), index=False, encoding="utf-8-sig")
mm = scan[scan.mismatch]
rep(f"扫描文本/混合列 {len(scan)}；域错配列 {len(mm)}")
for _, r in mm.iterrows():
    rep(f"  MISMATCH [{r.column}] 内容={r.top_domain}({r.top_share_pct:.0f}%) 期待={r.expect}")

# ================= D-016：PD 葡萄糖列甄别（单位感知版） =================
rep("\n======== D-016 PD 葡萄糖列甄别（单位感知）========")
QUAL_RE = DOMS["QUAL"]
raw = D["葡萄糖"]
g = raw.astype(str).str.strip()
is_missing = raw.isna() | g.isin(["", "nan", "NaN", "None"]) | g.str.fullmatch(r"[-－—]+(mmol/L|mg/dL)?")
unit_mmol = g.str.contains(r"mmol/L$", case=False, regex=True)
unit_mgdl = g.str.contains(r"mg/dL$", case=False, regex=True)
core = g.str.replace(r"(mmol/L|mg/dL)$", "", case=False, regex=True).str.strip()
num = pd.to_numeric(core.str.replace(r"[↑↓]", "", regex=True), errors="coerce")
is_q = g.map(lambda t: bool(QUAL_RE.match(t)))
is_num_mmol = num.notna() & unit_mmol & (num >= 1) & (num <= 40)            # 带单位 mmol/L
is_num_bare = num.notna() & ~unit_mmol & ~unit_mgdl & (num >= 1) & (num <= 40)  # 裸数值
is_num_mgdl = num.notna() & unit_mgdl & (num >= 20) & (num <= 400)          # mg/dL → /18
is_num = is_num_mmol | is_num_bare | is_num_mgdl
is_unit_empty_s = ~is_missing & ~is_q & ~is_num & (unit_mmol | unit_mgdl)
is_other = ~is_missing & ~is_q & ~is_num & ~is_unit_empty_s
fpg = pd.Series(np.nan, index=D.index)
fpg[is_num_mmol | is_num_bare] = num[is_num_mmol | is_num_bare]
fpg[is_num_mgdl] = num[is_num_mgdl] / 18.0                                   # mg/dL→mmol/L
rep(f"总行 {len(D):,}；缺失/空 {int(is_missing.sum()):,}")
rep(f"定性尿糖词形 {int(is_q.sum()):,}；数值可用 {int(is_num.sum()):,}"
    f"（裸数值 {int(is_num_bare.sum()):,}＋mmol/L {int(is_num_mmol.sum()):,}＋mg/dL {int(is_num_mgdl.sum()):,}）；"
    f"带单位但无值 {int(is_unit_empty_s.sum()):,}；其他形态 {int(is_other.sum()):,}")
if is_other.sum():
    rep("其他形态样例：" + str(g[is_other].value_counts().head(8).to_dict()))
per_year = pd.DataFrame({
    "缺失": is_missing.groupby(D["year"]).sum(),
    "定性": is_q.groupby(D["year"]).sum(),
    "数值可用": is_num.groupby(D["year"]).sum(),
})
per_year["可用率%"] = (per_year["数值可用"] / (per_year[["缺失", "定性", "数值可用"]].sum(axis=1)) * 100).round(1)
rep("分年分布：\n" + per_year.to_string())
keep = D[is_num][["id", "year"]].copy()
keep["fpg_pd_mmol"] = fpg[is_num].round(2)
keep["src_unit"] = np.where(is_num_mgdl[is_num], "mg/dL", "mmol/L")
keep.to_csv(os.path.join(OUT, "D016_pd_glucose_disposition.csv"),
            index=False, encoding="utf-8-sig")
rep(f"fpg 可用行清单已落盘：{len(keep):,} 行（results/D016_pd_glucose_disposition.csv，含 mg/dL→mmol/L 换算标记）")
rep(f"甄别结论：数值形态 {int(is_num.sum()):,} 行可作 fpg（占非缺失 "
    f"{is_num.sum()/(~is_missing).sum()*100:.1f}%）；定性 {int(is_q.sum()):,} 行归尿糖定性，"
    f"禁止进入 fpg≥7.0 分类；mg/dL 残留已按 /18 换算并打标。")

# ================= PG 数值审计（pg_arm_v2） =================
rep("\n======== PG pg_arm_v2.csv 数值审计 ========")
PG = pd.read_csv(PG_ARM, encoding="utf-8-sig", low_memory=False)
rep(f"{len(PG):,} 行 × {PG.shape[1]} 列；年份: {sorted(PG['year'].dropna().unique())}")
pg_rows = []
for c in ["alt", "ast", "crea", "fpg", "ggt", "hba1c", "hdl", "ldl", "plt", "tc", "tg", "ua"]:
    v = pd.to_numeric(PG[c], errors="coerce")
    pg_rows.append({"column": c, "nonempty_pct": round(v.notna().mean() * 100, 1),
                    "median": round(v.median(), 2),
                    "q005": round(v.quantile(0.005), 2), "q995": round(v.quantile(0.995), 2)})
    rep(f"  {c:<6} 非空 {pg_rows[-1]['nonempty_pct']:5.1f}%  中位 {pg_rows[-1]['median']:>9.2f}  "
        f"q0.5%~q99.5% [{pg_rows[-1]['q005']:.2f}, {pg_rows[-1]['q995']:.2f}]")
pd.DataFrame(pg_rows).to_csv(os.path.join(OUT, "B51_pg_numeric_audit.csv"),
                             index=False, encoding="utf-8-sig")

# ================= 报告落盘 =================
header = f"""# B51b ｜ D-008/D-016 收口报告

> 生成：治理规范 §8 台账工具｜PD 源：{src_label}｜PG 源：pg_arm_v2.csv
> D-008：B51 扫描产物持久化（此前仅控制台输出）；D-016：PD 葡萄糖列甄别落地。

"""
with open(os.path.join(OUT, "B51b_D008_D016_report.md"), "w", encoding="utf-8") as f:
    f.write(header + "\n".join(report) + "\n")
print("\n报告：results/B51b_D008_D016_report.md")
