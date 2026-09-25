# -*- coding: utf-8 -*-
"""sim_r32_extraction_crosscheck.py — SIM-R3-2：Cohort C（PD）葡萄糖文本抽取交叉实现一致率

审稿模拟发现 R3-2：C 库 1/3 资源依赖正则抽取（text-embedded laboratory values），
抽取正确性无金标准量化。本审计用**独立第二实现**（与 B51b 原实现异构的代码路径）对
n=200 确定性随机子样重新抽取血糖值，与 D016 可用行清单（B51b 产物）比对：
  一致率（分类一致 + 逐值一致）+ 分歧逐条表。
第二实现规则（有意异构）：_x000D_/CR 清洗 → CJK 存在即判非数值（原实现为定性词表）→
  任意位置单位标记（原实现为行尾锚定 $）→ 首个数字 token 浮点解析 → mg/dL÷18 →
  生理窗 [1.0, 40.0] mmol/L（原实现 mmol/L 1–40 / mg/dL 20–400 分窗）。
抽样框：D016 可用行中 (id, year) 键唯一者（重复键 1,237 行排除——属源表同人多行，
清洗层由同人以同年去重规则处置；键唯一保证回连源文本无歧义）。
只读分析：不改任何冻结层。
输出：results/sim_r32_extraction_crosscheck.csv（200 行逐条）。
"""
import os
import re
import sys

import pandas as pd

PD_LONG = r"D:\projects\Data\pudong\analysis\pd_checkup_long.csv"
D016 = r"D:\projects\Paper\00-数据质量核验与治理-20260917\results\D016_pd_glucose_disposition.csv"
OUT = r"D:\projects\Paper\论文00-多源体检队列数据治理与质量审计\results\sim_r32_extraction_crosscheck.csv"
N = 200
SEED = 20260925

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------- 1. 源长表（仅所需列） ----------
src = pd.read_csv(PD_LONG, encoding="utf-8-sig", low_memory=False,
                  usecols=["id", "year", "葡萄糖"], dtype={"id": str})
print(f"源长表 {len(src):,} 行 × {src.shape[1]} 列（仅取 id/year/葡萄糖）")
key_n = src.groupby(["id", "year"]).size()
src_unique = key_n[key_n == 1]
print(f"(id,year) 键唯一源行 {len(src_unique):,}；重复键行 {int((key_n > 1).sum()):,} 组")
src = src[src.set_index(["id", "year"]).index.isin(src_unique.index)]  # 键唯一子集（抽样框 ⊆ 此集）

# ---------- 2. 抽样框：D016 可用行 ∩ 键唯一 ----------
disp = pd.read_csv(D016, encoding="utf-8-sig", dtype={"id": str})
dup_in_disp = int(disp.duplicated(["id", "year"], keep=False).sum())
disp_u = disp[~disp.duplicated(["id", "year"], keep=False)]
disp_u = disp_u[disp_u.set_index(["id", "year"]).index.isin(src_unique.index)]
print(f"D016 可用行 {len(disp):,}（重复键行 {dup_in_disp} 排除）∩ 键唯一 → 抽样框 {len(disp_u):,}")

samp = disp_u.sample(n=N, random_state=SEED).reset_index(drop=True)

# ---------- 3. 回连源文本（键已保证 1:1） ----------
m = samp.merge(src, on=["id", "year"], how="left", validate="one_to_one")
assert m["葡萄糖"].notna().all(), "抽样行回连源文本缺失"

# ---------- 4. 独立第二实现 ----------
CJK = re.compile(r"[\u4e00-\u9fff]")
NUM = re.compile(r"\d+(?:\.\d+)?")


def extract_v2(raw):
    """独立第二实现：返回 (value_mmol, unit)；非数值返回 (None, None)。"""
    if not isinstance(raw, str):
        return None, None
    s = raw.replace("_x000D_", "").replace("\r", " ").replace("\n", " ").strip()
    if not s or CJK.search(s) or re.fullmatch(r"[-+±()\s]*", s):
        return None, None
    unit = "mg/dL" if "mg/dl" in s.lower() else ("mmol/L" if "mmol/l" in s.lower() else "bare")
    core = re.sub(r"(?i)mg/dl|mmol/l|[↑↓+]", " ", s)
    hit = NUM.search(core)
    if not hit:
        return None, None
    v = float(hit.group(0))
    if unit == "mg/dL":
        v /= 18.0
    if not (1.0 <= v <= 40.0):          # 第二实现生理窗（mmol/L 口径）
        return None, None
    return v, unit


parsed = m["葡萄糖"].map(extract_v2)
m["v2_value"] = [p[0] for p in parsed]
m["v2_unit"] = [p[1] for p in parsed]
m["v2_usable"] = m["v2_value"].notna()

# ---------- 5. 与 B51b 清单比对 ----------
m["agree_value"] = m["v2_usable"] & (m["v2_value"].round(2) - m["fpg_pd_mmol"]).abs().le(1e-9)
m["agree"] = m["v2_usable"] & m["agree_value"]
n_class = int(m["v2_usable"].sum())
n_val = int(m["agree_value"].sum())
n_agree = int(m["agree"].sum())

out = m[["id", "year", "葡萄糖", "src_unit", "fpg_pd_mmol",
         "v2_unit", "v2_value", "v2_usable", "agree_value", "agree"]].copy()
out = out.rename(columns={"葡萄糖": "src_text", "fpg_pd_mmol": "b51_fpg_mmol",
                          "src_unit": "b51_unit"})
out.to_csv(OUT, index=False, encoding="utf-8-sig")
# 抽样框分母侧车（S2 生成器硬编码条款：SI 引用的数据数字一律工件驱动）
FRAME = os.path.join(os.path.dirname(OUT), "sim_r32_frame.txt")
with open(FRAME, "w", encoding="utf-8") as f:
    f.write(f"frame={len(disp_u)}\nusable_rows={len(disp)}\n"
            f"dup_key_rows_in_disp={dup_in_disp}\nsampled={len(m)}\nseed={SEED}\n")

print("\n======== SIM-R3-2 汇总 ========")
print(f"子样 n={len(m)}（random_state={SEED}，抽样框 {len(disp_u):,} 行）")
print(f"分类一致（第二实现亦判数值可用）：{n_class}/{len(m)}")
print(f"逐值一致（2 位小数 mmol/L）：    {n_val}/{len(m)}")
print(f"总一致率：{n_agree}/{len(m)}")
if n_agree < len(m):
    print("分歧逐条：")
    print(m[~m.agree][["id", "year", "葡萄糖", "b51_unit", "b51_fpg_mmol",
                       "v2_unit", "v2_value", "v2_usable"]].to_string(index=False))
print(f"子样 B51 值域：{m.fpg_pd_mmol.min():.2f}–{m.fpg_pd_mmol.max():.2f} mmol/L；"
      f"单位构成 {m.src_unit.value_counts().to_dict()}")
print(f"产物：{OUT}")
