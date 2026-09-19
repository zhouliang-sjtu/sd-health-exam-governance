# -*- coding: utf-8 -*-
"""m2_framework.py —— 论文00 M2 注入式模拟实验：签名引擎 + 注入机制 + 指标

设计依据：论文00/20_paper-methodology/研究设计与叙事.md §3（单一事实源）。

组成：
  1. 签名引擎 evaluate_signatures(df, rules) —— 14 条数值签名（15 条库中的文本域规则
     不参与数值模拟），NaN 安全，逐规则布尔列 + any_hit。
  2. 注入机制 inject_shift(true_vals, origin_idx, k, row_mask) —— "缺 k 列型整行左移"：
     injected[:, o:n-K] = true[:, o+K:n]；尾部 K 列置 NaN（未采集）。
  3. 修复算子 repair_shift(inj, row_mask, origin_idx, k) —— 右移回正 + 起点列置缺。
  4. 指标 confusion_metrics(truth, flagged) —— 召回/精确/特异/F1；
     block_boundary(flagged_idx, s, b) —— 连续块的起点定位误差；
     dm_fabrication(true_fpg, inj_fpg, thresh=7.0) —— 不修复时的假糖尿病阳性。

尺度说明：阈值按清洗层口径整定（crea/ua μmol/L、bun/血糖 mmol/L、脂类 mmol/L）。
干净基底上值域类签名按构造静默（治理已置缺），移位探针（r01/r02）与跨列关系
（r03-r05）承担移位检测——与真实 2022 事件的检出机理一致（G01b）。
"""
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 签名引擎

def _cmp(a, op, b):
    """NaN 安全比较：NaN 一律 False。"""
    s = pd.Series(a)
    if op == ">":
        return (s > b).fillna(False)
    if op == "<":
        return (s < b).fillna(False)
    if op == ">=":
        return (s >= b).fillna(False)
    if op == "<=":
        return (s <= b).fillna(False)
    raise ValueError(op)


def h_rule_set(df):
    """Cohort A（库A）14 条数值签名。df 为按模板列名取好的数值框。"""
    g = df  # 列名：height,weight,bmi,waist,sbp,dbp,wbc,plt,hb,tbil,alt,ast,bun,crea,ua,tc,tg,hdl,ldl,afp,cea,ca199,fpg
    bmi_calc = g["weight"] / (g["height"] / 100.0) ** 2
    rules = {
        "r01_shift_probe":  _cmp(g["bun"], ">", 25) & _cmp(g["ua"], "<", 90),
        "r02_shift_fb":     _cmp(g["crea"], ">=", 150) & _cmp(g["ua"], "<", 20),
        "r03_bp_rev":       _cmp(g["sbp"], "<", g["dbp"]),
        "r04_hdl_gt_tc":    _cmp(g["hdl"], ">", g["tc"]),
        "r05_ldl_gt_tc":    _cmp(g["ldl"], ">", g["tc"]),
        "r06_ua_low":       _cmp(g["ua"], "<", 120),
        "r07_fpg_low":      _cmp(g["fpg"], "<", 3.0),
        "r08_bmi_incons":   ((g["bmi"] - bmi_calc).abs() > 2.5) & g["bmi"].notna() & g["height"].notna(),
        "r09_tg_high":      _cmp(g["tg"], ">", 25),
        "r10_crea_low":     _cmp(g["crea"], "<", 20),
        "r11_plt_high":     _cmp(g["plt"], ">", 800),
        "r12_hb_low":       _cmp(g["hb"], "<", 60),
        "r13_wbc_high":     _cmp(g["wbc"], ">", 25),
        "r14_altast_high":  _cmp(g["alt"], ">", 1500) | _cmp(g["ast"], ">", 1500),
    }
    return rules


def pd_rule_set(df):
    """Cohort C（库C）签名子集（无 bun/plt/hb/wbc/肿瘤标志物列）：
    移位探针改用 urea 位（urea mmol/L ~3-8 vs crea μmol/L ~70 量纲分离）。"""
    g = df
    bmi_calc = g["weight"] / (g["height"] / 100.0) ** 2
    rules = {
        "r01_shift_probe":  _cmp(g["urea"], ">", 25) & _cmp(g["ua"], "<", 90),
        "r02_shift_fb":     _cmp(g["crea"], ">=", 150) & _cmp(g["ua"], "<", 20),
        "r03_bp_rev":       _cmp(g["sbp"], "<", g["dbp"]),
        "r04_hdl_gt_tc":    _cmp(g["hdl"], ">", g["tc"]),
        "r05_ldl_gt_tc":    _cmp(g["ldl"], ">", g["tc"]),
        "r06_ua_low":       _cmp(g["ua"], "<", 120),
        "r07_fpg_low":      _cmp(g["fpg"], "<", 3.0),
        "r08_bmi_incons":   ((g["bmi"] - bmi_calc).abs() > 2.5) & g["bmi"].notna() & g["height"].notna(),
        "r09_tg_high":      _cmp(g["tg"], ">", 25),
        "r10_crea_low":     _cmp(g["crea"], "<", 20),
        "r14_altast_high":  _cmp(g["alt"], ">", 1500) | _cmp(g["ast"], ">", 1500),
    }
    return rules


def evaluate_signatures(df, rule_set_fn):
    """返回 (any_hit: bool np.array, per_rule: dict[str, bool np.array], n_rules)。"""
    rules = rule_set_fn(df)
    per_rule = {k: v.to_numpy(dtype=bool) for k, v in rules.items()}
    any_hit = np.zeros(len(df), dtype=bool)
    for v in per_rule.values():
        any_hit |= v
    return any_hit, per_rule, len(per_rule)


# ---------------------------------------------------------------- 注入机制

def inject_shift(true_vals, origin_idx, k, row_idx):
    """缺 k 列型整行左移：injected[:, o:n-K] = true[:, o+K:n]；尾部 K 列 NaN。

    true_vals: np.ndarray (n_rows, n_cols) float32，模板列序。
    origin_idx: 被删的首列位置（模拟真实事件中被缺的"谷丙转氨酶"列）。
    row_idx: 受影响行号数组。
    """
    inj = true_vals.copy()
    n = true_vals.shape[1]
    if len(row_idx):
        inj[np.ix_(row_idx, np.arange(origin_idx, n - k))] = \
            true_vals[np.ix_(row_idx, np.arange(origin_idx + k, n))]
        inj[np.ix_(row_idx, np.arange(n - k, n))] = np.nan
    return inj


def repair_shift(inj_vals, origin_idx, k, row_idx):
    """右移回正（副本修复，非就地）：repaired[:, o+K:n] = inj[:, o:n-K]；起点 K 列置缺。
    前提：origin/k 由"模板表头比对"步骤给出（真实工作流即如此）。"""
    rep = inj_vals.copy()
    n = inj_vals.shape[1]
    if len(row_idx):
        rep[np.ix_(row_idx, np.arange(origin_idx + k, n))] = \
            inj_vals[np.ix_(row_idx, np.arange(origin_idx, n - k))]
        rep[np.ix_(row_idx, np.arange(origin_idx, origin_idx + k))] = np.nan
    return rep


# ---------------------------------------------------------------- 指标

def confusion_metrics(truth, flagged):
    truth = np.asarray(truth, dtype=bool)
    flagged = np.asarray(flagged, dtype=bool)
    tp = int((truth & flagged).sum())
    fp = int((~truth & flagged).sum())
    fn = int((truth & ~flagged).sum())
    tn = int((~truth & ~flagged).sum())
    recall = tp / (tp + fn) if tp + fn else np.nan
    precision = tp / (tp + fp) if tp + fp else np.nan
    specificity = tn / (tn + fp) if tn + fp else np.nan
    f1 = np.nan
    if tp + fn and tp + fp:
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, recall=recall, precision=precision,
                specificity=specificity, f1=f1)


def block_boundary(flagged_idx, start, block_len):
    """连续块起点定位：块内首个被标记行的行号 - 真实起点。
    块内无标记行 -> (False, nan)。"""
    inside = flagged_idx[(flagged_idx >= start) & (flagged_idx < start + block_len)]
    if len(inside) == 0:
        return False, np.nan
    return True, int(inside.min() - start)


def dm_fabrication(true_fpg, inj_fpg, thresh=7.0):
    """不修复时的假糖尿病筛查阳性（hba1c 缺失为主，口径 = fpg>=7）。"""
    t = pd.Series(true_fpg)
    i = pd.Series(inj_fpg)
    dm_t = (t >= thresh).fillna(False).to_numpy()
    dm_i = (i >= thresh).fillna(False).to_numpy()
    return int((dm_i & ~dm_t).sum())
