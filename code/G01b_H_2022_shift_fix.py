# -*- coding: utf-8 -*-
"""S00b_fix_2022_shift.py — 2022 年度源表列移位修复（H_checkup 层）

背景（2026-09-14 治理审计发现）:
  2022年总数.xls 自第 ~7880 行起（约 9.4k 行，占 54%）采用缺"谷丙转氨酶"列的导出模板，
  自 AST 起整行左移一位。解析位(旧) → 真值位置：
    alt(79)←AST真   ast(80)←BUN真   bun(81)←crea真   crea(82)←UA真
    ua(83)←TC真     tc(84)←TG真     tg(85)←HDL真     hdl(86)←LDL真
    ldl(87)←AFP真   afp(88)←CEA真   cea(89)←CA199真  ca199(90)←FPG真
    fpg(91)←尿pH（旧管线把尿pH当血糖 → 566 行假 dm_screen==1）
  文本列同样左移：心电图结论 127→126、超声结论 128→127（旧管线把超声/放射文本当 ECG 解析）
修复:
  1) 数值区按真值重映射（alt 置缺失）
  2) ECG 文本改取 col126（缺失回落 col102），classifyECGv2 的 Python 移植重判读（并在非移位行验证一致性）
  3) 超声文本改取 col103/104/126/127（排除放射 col105/col128），parseUS 移植重判
  4) 尿检文本区置缺失；chronic_mgmt_flag 重扫 col134–136
输出: H_checkup_long_v2fix2022.csv + 治理报告
"""
import re
import numpy as np
import pandas as pd
import xlrd

RAW = r"<institution-path>"
SRC = r"<institution-path>"
OUT = r"<institution-path>"
REPF = r"<institution-path>"
rep = []

def rep_line(s=""):
    print(s)
    rep.append(str(s))

def norm(s):
    return re.sub(r"\s+", "", str(s if s is not None else ""))

def is_id(s):
    return bool(re.fullmatch(r"\d{17}[\dXx]|\d{15}", s))

def to_num(v):
    s = str(v).replace(",", "").replace("，", "").replace("↑", "").replace("↓", "").strip()
    if s in ("", "None", "nan"):
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan

# ---------- 读原始 2022 ----------
wb = xlrd.open_workbook(RAW)
sh = wb.sheet_by_index(0)
headers = [norm(sh.cell_value(0, c)) for c in range(sh.ncols)]
cID = next(i for i, h in enumerate(headers) if "身份证" in h)
cSmoke = next((i for i, h in enumerate(headers) if "吸烟" in h), -1)
cDrink = next((i for i, h in enumerate(headers) if "饮酒" in h), -1)
cPast = next((i for i, h in enumerate(headers) if "既往史" in h), -1)
assert 0 <= cSmoke < 79 and 0 <= cDrink < 79, "吸烟/饮酒列必须在移位区之前"
rep_line(f"[raw] 2022 cols={sh.ncols}, id_col={cID}, smoke={cSmoke}, drink={cDrink}, past={cPast}")
id_types = {}
for r in range(1, sh.nrows):
    id_types[sh.cell_type(r, cID)] = id_types.get(sh.cell_type(r, cID), 0) + 1
rep_line(f"[raw] id 列单元格类型分布 {id_types} (1=TEXT, 2=NUMBER)")

NUMC = {"v79": 79, "v80": 80, "v81": 81, "v82": 82, "v83": 83, "v84": 84, "v85": 85,
        "v86": 86, "v87": 87, "v88": 88, "v89": 89, "v90": 90, "v91": 91}
raw_rows = []
for r in range(1, sh.nrows):
    idv = norm(sh.cell_value(r, cID))
    rec = {"id": idv.upper() if is_id(idv) else "", "_row": r + 1}
    for k, c in NUMC.items():
        rec[k] = to_num(sh.cell_value(r, c))
    rec["ecg_concl"] = str(sh.cell_value(r, 126) or "").strip()
    rec["ecg_find"] = str(sh.cell_value(r, 102) or "").strip()
    rec["us_a"] = str(sh.cell_value(r, 103) or "").strip()
    rec["us_b"] = str(sh.cell_value(r, 104) or "").strip()
    rec["us_concl"] = str(sh.cell_value(r, 127) or "").strip()
    rec["flag_scan"] = " ".join(str(sh.cell_value(r, c) or "") for c in (134, 135, 136))
    raw_rows.append(rec)
R = pd.DataFrame(raw_rows)
rep_line(f"[raw] 解析 {len(R)} 行")

# ---------- 移位判定 ----------
# 主规则: bun解析位(col81)=crea真值>25 且 ua解析位(col83)=TC真值<90
# 回落: bun 缺失时, crea位(col82)=UA真值 150-1500 且 ua位(col83)=TC真值 2-20
shifted = (R["v81"] > 25) & ~(R["v83"] >= 90)
fb = R["v81"].isna() & R["v82"].between(150, 1500) & R["v83"].between(2, 20)
shifted = shifted | fb
early = int((shifted & (R["_row"] < 7880)).sum())
bun25_nanua = int(((R["v81"] > 25) & R["v83"].isna() & R["v82"].between(90, 1500)
                   & ~R["v82"].isna()).sum())
rep_line(f"[detect] 移位行 n={int(shifted.sum())} (主规则 {int(((R['v81'] > 25) & ~(R['v83'] >= 90)).sum())}, "
         f"回落 {int(fb.sum())})；行号范围 {int(R.loc[shifted, '_row'].min())}–{int(R.loc[shifted, '_row'].max())}")
rep_line(f"[detect] 行号<7880 的移位判定数={early}（期望≈0）；"
         f"bun>25 且 ua 位缺失且 crea 位 90-1500（潜在误判源）={bun25_nanua}")
rep_line(f"[detect] id 可JOIN 的移位行 {int((shifted & (R['id'] != '')).sum())}")

# ---------- 修复前后一致性验证 ----------
# 移位行真值: AST=v79, BUN=v80, crea=v81, UA=v82, TC=v83, TG=v84, HDL=v85
ua_true = np.where(shifted, R["v82"], R["v83"])
cr_true = np.where(shifted, R["v81"], R["v82"])
tg_true = np.where(shifted, R["v84"], R["v85"])
hdl_true = np.where(shifted, R["v85"], R["v86"])
fpg_true = np.where(shifted, R["v90"], R["v91"])
S = pd.Series(shifted)
m = S & pd.Series(ua_true).between(90, 1500) & pd.Series(cr_true).between(20, 800)
rep_line(f"[check] 修复后 corr(UA,crea)={np.corrcoef(pd.Series(ua_true)[m], pd.Series(cr_true)[m])[0, 1]:.3f} (n={int(m.sum())})")
m2 = S & pd.Series(tg_true).between(0.1, 30) & pd.Series(hdl_true).between(0.1, 10)
rep_line(f"[check] 修复后 corr(TG,HDL)={np.corrcoef(pd.Series(tg_true)[m2], pd.Series(hdl_true)[m2])[0, 1]:.3f}")
fs = pd.Series(fpg_true)[S]
rep_line(f"[check] 移位行真 FPG: med={fs.median():.2f} q05={fs.quantile(.05):.2f} q95={fs.quantile(.95):.2f}；"
         f"真 FPG≥7.0: {int((fs >= 7).sum())}")
rep_line(f"[check] 旧管线移位行 fpg(=尿pH)≥7.0（假糖尿病行）: {int((R.loc[S, 'v91'] >= 7).sum())}")

# ---------- JS 判读逻辑 Python 移植 ----------
def classify_ecg_v2(text):
    t = norm(text)
    if t == "" or t == "×" or t == "弃检" or re.search(r"拒检|图像质量差|未检", t):
        return None
    negation = bool(re.search(r"(未见|无明显|大致正常|无特殊)[^。；]{0,6}(ST|T波|异常|改变)", t))
    f = {
        "af": 1 if (re.search(r"房颤|心房颤动|心房扑动|房扑|颤动", t) and not negation) else 0,
        "pacPvc": 1 if re.search(r"早搏|期前收缩|过早搏动", t) else 0,
        "stt": 1 if (not negation and re.search(r"ST-?T|ST段|T波(改变|低平|倒置|高尖)|心肌缺血", t)) else 0,
        "avblock": 1 if re.search(r"房室传导阻滞|房室阻滞|一度传导|二度传导|三度传导|Ⅰ度房室|II度房室|III度房室", t) else 0,
        "bbb": 1 if re.search(r"束支阻滞|束支传导阻滞|分支阻滞|室内传导阻滞", t) else 0,
        "rate": 1 if re.search(r"心动过速|心动过缓", t) else 0,
        "srirr": 1 if re.search(r"窦性心律不齐|窦性不齐|窦性心动不齐|窦性心动律不齐", t) else 0,
        "axis": 1 if re.search(r"电轴(左|右|不)偏", t) else 0,
        "rotate": 1 if re.search(r"转位", t) else 0,
        "lowvolt": 1 if re.search(r"低电压", t) else 0,
        "avdiss": 1 if re.search(r"房室分离", t) else 0,
        "junctional": 1 if re.search(r"交界性", t) else 0,
        "qwave": 1 if re.search(r"异常Q波|异常q波|病理性Q波|陈旧性(下壁|前壁|侧壁|后壁)|心肌梗死|心肌梗塞", t) else 0,
        "lvh": 1 if re.search(r"高电压|肥大|肥厚", t) else 0,
        "pacer": 1 if re.search(r"起搏", t) else 0,
        "prdelay": 1 if re.search(r"P-?R间期(延长|延迟)|一度房室", t) else 0,
    }
    f["anyBlock"] = 1 if (f["avblock"] or f["bbb"]) else 0
    markers = ["af", "pacPvc", "stt", "avblock", "bbb", "rate", "axis", "rotate",
               "lowvolt", "avdiss", "junctional", "qwave", "lvh", "pacer", "prdelay"]
    f["abnormal"] = 1 if any(f[k] for k in markers) else 0
    if not f["abnormal"]:
        if re.search(r"正常心电图|大致正常|未见明显异常|未见异常|正常范围|正常", t):
            f["normal"] = 1
        elif re.search(r"窦性心律", t):
            f["sinusOnly"] = 1
        else:
            f["unclassified"] = 1
    return f

def parse_us(text, main_text=""):
    t = str(text or "")
    m2 = str(main_text or "")
    in_us = "脂肪肝" in t
    in_main = "脂肪肝" in m2
    fatty = 1 if (in_us or in_main) else 0
    degree = ""
    if fatty:
        m = re.search(r"脂肪肝[^。；\n]{0,8}?(轻度|中度|重度)|((?:轻度|中度|重度)[^。；\n]{0,6}?脂肪肝)",
                      t + " " + m2)
        degree = (m.group(1) or m.group(2) or "") if m else ""
    return {"fatty": fatty, "fatty_degree": degree.replace("脂肪肝", ""),
            "gallstone": 1 if re.search(r"胆(囊|管)?(结石|息肉)|胆囊(结石|息肉)", t) else 0,
            "kidneycyst": 1 if re.search(r"肾囊肿", t) else 0,
            "fibroid": 1 if re.search(r"子宫肌瘤", t) else 0}

# ---------- 移植验证（2022 非移位行：Python vs JS 存储判读） ----------
# 注意: H_checkup_long.id = 交付伪标识(12位哈希)；原始XLS.id = 身份证号。
# 经 _deid_key/mapping_H_idcard.csv (1:1, 30,677人) 桥接。
MAPF = r"<institution-path>"
MAP = pd.read_csv(MAPF, dtype=str)
R["pseudo"] = R["id"].map(MAP.set_index("idcard")["pseudo_id"])
C = pd.read_csv(SRC, encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
R_first = R[R["pseudo"].notna()].drop_duplicates("pseudo", keep="first").set_index("pseudo")
rep_line(f"[join] R 有效 id 行 {len(R_first):,}（按伪标识去重后）；H_checkup 2022 行 "
         f"{int((C['year'] == 2022).sum()):,}")
C22 = C[C["year"] == 2022].copy()

def shifted_flag(df):
    s1 = (df["v81"] > 25) & ~(df["v83"] >= 90)
    s2 = df["v81"].isna() & df["v82"].between(150, 1500) & df["v83"].between(2, 20)
    return (s1 | s2).fillna(False)

C22v = C22.merge(R_first[["v81", "v82", "v83"]], left_on="id", right_index=True,
                 how="left", suffixes=("", "_r"))
hit_v = int(C22v["v81"].notna().sum())
skip = shifted_flag(C22v)
val = C22v[~skip & C22v["ecg_text"].notna()].copy()
agree = {"n": 0, "stt": 0, "af": 0, "abnormal": 0, "anyBlock": 0, "normal": 0}
KEYMAP = [("ecg_stt", "stt"), ("ecg_af", "af"), ("ecg_abnormal", "abnormal"),
          ("ecg_anyBlock", "anyBlock"), ("ecg_normal", "normal")]
py_flags = val["ecg_text"].map(classify_ecg_v2)
agree["n"] = int(py_flags.notna().sum())
for k_js, k_py in KEYMAP:
    old_v = pd.to_numeric(val[k_js], errors="coerce")
    new_v = py_flags.map(lambda f: 1 if (f and f.get(k_py)) else 0)
    both = old_v.notna()
    agree[k_py] = int((new_v[both] == old_v[both].astype(int)).sum())
n_ag = agree["n"]
rep_line(f"[port] classifyECGv2 移植一致性（2022 非移位行 n={n_ag}）: " +
         ", ".join(f"{k} {agree[k]}" for k in ["stt", "af", "abnormal", "anyBlock", "normal"]))

# ---------- 应用修复（merge 向量化） ----------
C = C.reset_index(drop=True)
mask22 = (C["year"] == 2022)
orig_idx = C.index[mask22]
Cm = C.loc[orig_idx].merge(R_first, left_on="id", right_index=True, how="left",
                           suffixes=("", "_r"))
shift_pos = shifted_flag(Cm).values
rows = orig_idx[shift_pos]
rep_line(f"[fix] H_checkup 2022 行 {int(mask22.sum())}，按 id 命中 "
         f"{int(Cm['v81'].notna().sum())}，判定移位 {int(shift_pos.sum())}")

FIELDMAP = {"ast": "v79", "bun": "v80", "crea": "v81", "ua": "v82", "tc": "v83",
            "tg": "v84", "hdl": "v85", "ldl": "v86", "afp": "v87", "cea": "v88",
            "ca199": "v89", "fpg": "v90"}
for tgt, src in FIELDMAP.items():
    C.loc[rows, tgt] = Cm.loc[shift_pos, src].values
C.loc[rows, "alt"] = np.nan

ecg_txt = Cm.loc[shift_pos, "ecg_concl"].where(
    Cm.loc[shift_pos, "ecg_concl"].ne(""), Cm.loc[shift_pos, "ecg_find"]).astype(str)
C.loc[rows, "ecg_text"] = ecg_txt.str.slice(0, 150).values
flags = ecg_txt.map(classify_ecg_v2)
for col, key, default in [("ecg_abnormal", "abnormal", ""), ("ecg_af", "af", ""),
                          ("ecg_pacPvc", "pacPvc", ""), ("ecg_stt", "stt", ""),
                          ("ecg_anyBlock", "anyBlock", ""), ("ecg_rate", "rate", ""),
                          ("ecg_srirr", "srirr", ""), ("ecg_qwave", "qwave", "")]:
    C.loc[rows, col] = flags.map(lambda f: f[key] if f else default)
C.loc[rows, "ecg_axis"] = flags.map(
    lambda f: (1 if (f and (f["axis"] or f["rotate"] or f["lowvolt"])) else 0) if f else "")
C.loc[rows, "ecg_normal"] = flags.map(
    lambda f: (1 if (f and (f.get("normal") or f.get("sinusOnly"))) else 0) if f else "")

us_txt = (Cm.loc[shift_pos, "us_a"].astype(str) + " " + Cm.loc[shift_pos, "us_b"].astype(str) + " "
          + Cm.loc[shift_pos, "ecg_concl"].astype(str) + " " + Cm.loc[shift_pos, "us_concl"].astype(str))
us_res = us_txt.map(parse_us)
C.loc[rows, "fatty"] = us_res.map(lambda u: u["fatty"])
C.loc[rows, "fatty_degree"] = us_res.map(lambda u: u["fatty_degree"])
C.loc[rows, "gallstone"] = us_res.map(lambda u: u["gallstone"])
C.loc[rows, "kidneycyst"] = us_res.map(lambda u: u["kidneycyst"])
C.loc[rows, "fibroid"] = us_res.map(lambda u: u["fibroid"])
for u in ["uprot", "uglu", "ubld", "uket", "uwbc", "unit", "usg", "ubg"]:
    C.loc[rows, u] = ""
C.loc[rows, "chronic_mgmt_flag"] = Cm.loc[shift_pos, "flag_scan"].map(
    lambda s: 1 if re.search(r"纳入慢性病", norm(s)) else 0)

C.to_csv(OUT, index=False, encoding="utf-8-sig")
rep_line(f"\n[save] {OUT}")

# ---------- 残留清扫：仍呈移位形态的行（id 无法 join 者），用存储列自身重映射 ----------
bun_s = pd.to_numeric(C["bun"], errors="coerce")
ua_s = pd.to_numeric(C["ua"], errors="coerce")
resid = C.index[(bun_s > 25) & ~(ua_s >= 90)]
rep_line(f"[residual] 清扫后仍呈移位形态 {len(resid)} 行")
if len(resid):
    # 存储列此时仍为错位值: alt=AST真, ast=BUN真, bun=crea真, crea=UA真, ua=TC真,
    # tc=TG真, tg=HDL真, hdl=LDL真, ca199槽=FPG真
    remap = {"ast": "alt", "bun": "ast", "crea": "bun", "ua": "crea", "tc": "ua",
             "tg": "tc", "hdl": "tg", "ldl": "hdl", "afp": "ldl", "cea": "afp",
             "ca199": "cea", "fpg": "ca199"}
    for tgt, src in remap.items():
        C.loc[resid, tgt] = pd.to_numeric(C.loc[resid, src], errors="coerce")
    C.loc[resid, "alt"] = np.nan
    C.loc[resid, "ecg_text"] = ""          # 无原始文本可恢复 → 置缺失（1 行量级）
    for colc in ["ecg_abnormal", "ecg_af", "ecg_pacPvc", "ecg_stt", "ecg_anyBlock",
                 "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave", "ecg_normal"]:
        C.loc[resid, colc] = ""
    C.to_csv(OUT, index=False, encoding="utf-8-sig")
    rep_line("[residual] 已按存储列自重映射修复并回写")

# ---------- 修复前后对比（2022） ----------
O = pd.read_csv(SRC, encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
for c in ["fpg", "ua", "tg", "hdl", "alt", "ast", "ecg_stt", "fatty"]:
    C[c] = pd.to_numeric(C[c], errors="coerce")
    O[c] = pd.to_numeric(O[c], errors="coerce")
rep_line("\n[compare] 2022 修复前 → 修复后（全行）:")
for c in ["fpg", "ua", "tg", "hdl", "alt", "ast"]:
    so, sn = O.loc[mask22, c].dropna(), C.loc[mask22, c].dropna()
    rep_line(f"  {c}: n {len(so)}→{len(sn)}, med {so.median():.2f}→{sn.median():.2f}")
rep_line(f"  fpg≥7.0 行: {int((O.loc[mask22, 'fpg'] >= 7).sum())} → {int((C.loc[mask22, 'fpg'] >= 7).sum())}")
rep_line(f"  ecg_stt==1: {int((O.loc[mask22, 'ecg_stt'] == 1).sum())} → {int((C.loc[mask22, 'ecg_stt'] == 1).sum())}")
rep_line(f"  fatty==1: {int((O.loc[mask22, 'fatty'] == 1).sum())} → {int((C.loc[mask22, 'fatty'] == 1).sum())}")

with open(REPF, "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("\n===== S00b 完成 =====")
