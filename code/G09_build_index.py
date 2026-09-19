# -*- coding: utf-8 -*-
"""G09_build_index.py — 清洗源数据库 · 数据资产总索引（index 文档）构建

输出: 数据资产总索引_v1.xlsx
  Sheet[总览]      三库快照概况
  Sheet[H/PG/PD]   每张原始表单一行: 原始表名/源位置/行列数/清洗镜像文件/清洗摘要/指标清单
  Sheet[清洗层]    仓库 L1/L2 数据资产（wave/person/数据字典）
  Sheet[分析资产]  各论文分析资产快照（含路径索引）
  Sheet[PII治理]   敏感列与处理
  Sheet[未纳入清洗] 系统表/测试表/空表及原因
"""
import glob
import os
import pandas as pd
import openpyxl

W = r"<institution-path>"
VERSION = "v1.0"
SNAP = "2026-09-14"


def header_cols(path, n=2000):
    import csv
    op = gzip_open(path)
    r = csv.reader(op)
    hdr = next(r, [])
    op.close()
    return hdr


def gzip_open(path):
    import gzip
    return gzip.open(path, "rt", encoding="utf-8-sig") if path.endswith(".gz") else \
        open(path, "r", encoding="utf-8-sig")


def cols_of(path, cap=1500):
    try:
        h = header_cols(path)
        s = ", ".join(h)
        if len(s) > cap:
            s = s[:cap] + f" …（共{len(h)}列，截断）"
        return s
    except Exception as e:
        return f"(读取失败 {e})"


rows_overview = [
    {"数据库": "H 社区库", "源位置": r"<institution-path> 7个年度XLS；T2DM队列 3个工作簿）",
     "原始表单数": 10, "已清洗镜像": 21, "未纳入清洗": 0, "版本": VERSION, "快照": SNAP},
    {"数据库": "PG 库（PostgreSQL inter_mysql_tb）", "源位置": r"<institution-path> 127.0.0.1:5555）",
     "原始表单数": 21, "已清洗镜像": 12, "未纳入清洗": 9, "版本": VERSION, "快照": SNAP},
    {"数据库": "PD 库（浦东体检）", "源位置": r"<institution-path> + 死因XLS）",
     "原始表单数": 4, "已清洗镜像": 5, "未纳入清洗": 0, "版本": VERSION, "快照": SNAP},
]

H_tables = []
for y in [2018, 2019, 2020, 2021, 2022, 2023, 2024]:
    fn = {2018: "2018年总数.xls", 2019: "2019年.xls", 2020: "2020体检.xls",
          2021: "2021年.xls", 2022: "2022年总数.xls", 2023: "2023年总数.xls",
          2024: "2024年总数.xls"}[y]
    p = W + f"/data/H/raw_mirror/H_{y}_清洗版_{VERSION}.csv"
    rows = {"原始表名": f"体检数据{y}（年度体检总表）", "源位置": fn,
            "清洗镜像": f"data/H/raw_mirror/H_{y}_清洗版_{VERSION}.csv"}
    H_tables.append(rows)
H_fixed = {
    2022: "列移位修复 9,396 行（缺ALT列模板致整行左移，含FPG/尿酸/血脂/心电超声文本）；"
          "数值列值域清洗；同年重复打标 49 行",
    2023: "同年重复行打标 4,028 行（保留全部行，分析层去重）",
    2018: "同年重复行打标 83 行", 2019: "同年重复行打标 71 行",
    2020: "同年重复行打标 9 行（脂肪肝经描述式规则补丁恢复，见 wave 层）",
    2021: "同年重复行打标 35 行", 2024: "同年重复行打标 20 行"}
H_extra = [
    ("糖尿病(处方) [2018–2024 七sheet]", "T2DM队列/糖尿病(处方).xlsx",
     "data/H/t2dm_mirror/糖尿病处方_<年>_清洗版_v1.0.csv", 1943,
     "PII: 身份证号→伪标识映射、姓名列删除；7 个年度 sheet"),
    ("H社区T2DM队列（原始）宽表", "T2DM队列/H社区T2DM队列（原始）.xlsx",
     "data/H/t2dm_mirror/T2DM队列原始宽表_清洗版_v1.0.csv.gz", 1943,
     "774→773 列两行表头展平；身份证号→伪标识；1,943 名 T2DM 患者多年面板"),
    ("目标1 工作簿 [12 sheet]", "T2DM队列/目标1_tyg长期变化趋势&dm新发.xlsx",
     "data/H/t2dm_mirror/目标1_<sheet>_清洗版_v1.0.csv", 13601,
     "12 个 sheet 全量镜像（含分析用合并库 13,601 行×31 列；研究目标/整理过程为文本说明页）"),
]

PG_tables = [
    ("raw_tj_userinfo（人员×报告主档）", "129,953 行 × 13 列",
     f"data/PG/raw_mirror/userinfo_清洗版_{VERSION}.csv", 129953,
     "年龄值域校验；文本 hygiene；report_id 无重复"),
    ("raw_detection_result（检验长表）", "21,666,246 行 × 20 列",
     f"data/PG/raw_mirror/detection_result_清洗版_{VERSION}.csv.gz", 21666246,
     "842 个检验项目逐项目统计（563 个数值主导）；增补 item_result_num 清洗数值列"
     "（逐项目 p0.1–p99.9 之外置缺并 _num_flag 标记）；原文保留"),
    ("raw_check_result（检查文本：心电/超声等）", "1,285,603 行 × 14 列",
     f"data/PG/raw_mirror/check_result_清洗版_{VERSION}.csv.gz", 1285603,
     "HTML 反转义/_x000D_ 清除/trim"),
    ("raw_medicine_result（尿有机酸代谢组）", "4,142,349 行 × 19 列",
     f"data/PG/raw_mirror/medicine_result_清洗版_{VERSION}.csv.gz", 4142349,
     "逐项目统计+数值清洗（同 detection）"),
    ("raw_dnajjh_result（基因检测）", "70,873 行 × 17 列",
     f"data/PG/raw_mirror/dnajjh_result_清洗版_{VERSION}.csv.gz", 70873,
     "数值抽取 + 文本 hygiene"),
    ("raw_questionnaire_result（问卷原始）", "33,588 行 × 13 列",
     f"data/PG/raw_mirror/questionnaire_result_清洗版_{VERSION}.csv.gz", 33588,
     "文本 hygiene（问卷内容 JSON 保留原文）"),
    ("tb_questionnaire_jsonb", "33,588 行 × 11 列",
     f"data/PG/raw_mirror/questionnaire_jsonb_清洗版_{VERSION}.csv.gz", 33588,
     "同上"),
    ("vw_inter_questionnaire_full（问卷宽视图）", "33,588 行 × 469 列",
     f"data/PG/raw_mirror/vw_inter_questionnaire_full_清洗版_{VERSION}.csv.gz", 33588,
     "数值列自动识别"),
    ("vw_inter_questionnaire_single", "33,588 行 × 112 列",
     f"data/PG/raw_mirror/vw_inter_questionnaire_single_清洗版_{VERSION}.csv.gz", 33588,
     "数值列自动识别"),
    ("vw_inter_body_composition（体成分）", "2,112 行 × 12 列",
     f"data/PG/raw_mirror/vw_inter_body_composition_清洗版_{VERSION}.csv.gz", 2112,
     "BMI/体脂/内脏脂肪等数值校验"),
    ("vw_methylation_wide（甲基化视图）", "4,169 行 × 23 列",
     f"data/PG/raw_mirror/vw_methylation_wide_清洗版_{VERSION}.csv.gz", 4169,
     "10 个系统评分数值校验"),
]
PG_uncleaned = [
    ("raw_*_backfill × 6", "全部 0 行（空表）", "无需清洗"),
    ("raw_*_test × 6", "测试残留数据（最大 227,884 行）", "非生产数据，不入清洗库（索引备查）"),
    ("sync_job_tracking", "1,924 行同步作业日志", "系统表，非研究数据"),
    ("table_profile", "6 行表画像", "系统表，非研究数据"),
]

PD_tables = [
    ("2019.xlsx（年度体检原始表）", "453,121 行 × 80 列",
     "data/PD/raw_mirror/PD_2019_清洗版_v1.1.csv.gz", None,
     "身份证号→伪标识映射；带单位文本数值列值域抽取；血压颠倒/血糖<3/尿酸<120 等同规修复；"
     "v1.1 补齐肌酐地板20/LDL>TC/BMI恒等式/转氨酶天花板；重复打标"),
    ("2020.xlsx", "481,642 行 × 80 列",
     "data/PD/raw_mirror/PD_2020_清洗版_v1.1.csv.gz", None, "同 2019"),
    ("2021.xlsx", "472,435 行 × 80 列",
     "data/PD/raw_mirror/PD_2021_清洗版_v1.1.csv.gz", None, "同 2019"),
    ("2019-2024死因【原始】 Sheet1", "身份证号/死因链 ICD 文本",
     "data/PD/raw_mirror/死因_Sheet1_清洗版_v1.1.csv", None,
     "身份证号→伪标识；未映射打标"),
    ("2019-2024死因【原始】 Sheet2", "身份证号×计数",
     "data/PD/raw_mirror/死因_Sheet2_清洗版_v1.1.csv", None, "同上"),
]

wave_assets = [
    ("H", "H_wave_level_v1.0.csv.gz", "122,575 行 × 78 列", "人-波清洗层+标准衍生层（含 2020 脂肪肝补丁）"),
    ("H", "H_person_level_v1.0.csv", "30,677 人", "人级静态层"),
    ("H", "H_数据字典_v1.0.csv", "31 变量", "变量字典"),
    ("PG", "PG_wave_level_v1.0.csv", "71,209 人年 × 26 列", "人-年聚合层（含修正后 FPG/HbA1c）"),
    ("PG", "PG_person_level_v1.0.csv", "51,296 人", "人级静态层"),
    ("PG", "PG_数据字典_v1.0.csv", "26 变量", "变量字典"),
    ("PD", "PD_wave_level_v1.1.csv.gz", "1,389,967 行 × 42 列", "人-波清洗层（id×year 去重后；v1.1 同规补齐 4 家族）"),
    ("PD", "PD_person_level_v1.1.csv", "686,688 人", "人级静态层"),
    ("PD", "PD_数据字典_v1.1.csv", "40 变量", "变量字典"),
]

analysis_assets = [
    ("论文04", "t1_panel_long.csv / t1_persons.csv", r"论文04-T1-超声MASLD七年动态与新发心代谢风险\data\processed",
     "DC 版主分析面板（2022 移位修复+深度审计后重建；与仓库 H 库 v1.0 同链路）"),
    ("论文04", "pg_t1_long_v2.csv / pg_dc_cohort.csv", r"论文04-T1-超声MASLD七年动态与新发心代谢风险\data\processed",
     "PG 外验二分析集（葡萄糖项目名修正后；10,829 人/480 事件）"),
    ("论文04", "dc_primary_intervals / dc_landmark_persons / dc_table1_base / dc_dyn_* / dc_flow",
     r"论文04-T1-超声MASLD七年动态与新发心代谢风险\results", "Diabetes Care 版全部分析中间产物"),
    ("论文03/04", "pd_person_index / pd_3wave_cohort_death / pd_death_person / pd_hukou_person",
     r"<institution-path>", "PD 人级分析资产（留在源目录，路径索引）"),
    ("论文06", "h2020_fat_state_patch.csv", r"论文06-T3-MASLD逆转自然史与生存获益\data\processed",
     "H 2020 脂肪肝补丁（已固化进 G01 wave 层）"),
]

pii_rows = [
    ("H", "体检年度表.身份证号", "→ mapping_H_idcard 伪标识替换；未映射置空+_id_unmapped 标记；原文不入库"),
    ("H", "T2DM 处方表.姓名/身份证号", "姓名列删除；身份证号→伪标识"),
    ("H", "T2DM 宽表.身份证号", "→ 伪标识替换"),
    ("PD", "年度表.身份证号", "→ mapping_pudong_idcard 伪标识替换；未映射置空打标"),
    ("PD", "死因表.身份证号", "→ 伪标识替换"),
    ("PG", "userinfo.username", "文本保留（非证件号），如需外发另行脱敏审查"),
    ("规则", "全部映射表（_deid_key）", "不入清洗库、不入任何论文目录"),
]

uncleaned_rows = [(pg[0], pg[1], pg[2]) for pg in PG_uncleaned]

with pd.ExcelWriter(W + f"/数据资产总索引_{VERSION}.xlsx", engine="openpyxl") as xw:
    pd.DataFrame(rows_overview).to_excel(xw, sheet_name="总览", index=False)
    # H sheet
    h_rows = []
    for y in [2018, 2019, 2020, 2021, 2022, 2023, 2024]:
        p = W + f"/data/H/raw_mirror/H_{y}_清洗版_{VERSION}.csv"
        h_rows.append({"原始表名": f"体检数据{y}", "清洗镜像": f"H_{y}_清洗版_{VERSION}.csv",
                       "指标清单（列名）": cols_of(p), "清洗摘要": H_fixed[y]})
    for name, src, out, nrows, note in H_extra:
        glob_p = glob.glob(W + "/" + out.replace("<年>", "*").replace("<sheet>", "*"))
        h_rows.append({"原始表名": name, "源位置": src, "清洗镜像": out,
                       "指标清单（列名）": cols_of(glob_p[0]) if glob_p else "",
                       "清洗摘要": note})
    pd.DataFrame(h_rows).to_excel(xw, sheet_name="H库表单", index=False)
    # PG sheet
    pg_rows = [{"原始表名": t, "规模": size, "清洗镜像": out, "清洗摘要": note,
                "指标清单（列名）": cols_of(W + "/" + out) if not str(nrows) or nrows < 500000
                else f"（{nrows:,} 行，列清单见源表结构）"}
               for t, size, out, nrows, note in PG_tables]
    pd.DataFrame(pg_rows).to_excel(xw, sheet_name="PG库表单", index=False)
    pd.DataFrame(uncleaned_rows, columns=["表名", "规模", "不清洗原因"]).to_excel(
        xw, sheet_name="PG未纳入清洗", index=False)
    # PD sheet
    pd_rows = [{"原始表名": t, "规模": size, "清洗镜像": out, "清洗摘要": note}
               for t, size, out, _, note in PD_tables]
    pd.DataFrame(pd_rows).to_excel(xw, sheet_name="PD库表单", index=False)
    pd.DataFrame(wave_assets, columns=["库", "资产", "规模", "说明"]).to_excel(
        xw, sheet_name="清洗层资产", index=False)
    pd.DataFrame(analysis_assets, columns=["论文", "资产", "路径", "说明"]).to_excel(
        xw, sheet_name="分析资产快照", index=False)
    pd.DataFrame(pii_rows, columns=["库", "敏感列", "处理"]).to_excel(
        xw, sheet_name="PII治理", index=False)

print(f"输出 {W}/数据资产总索引_{VERSION}.xlsx")
print("===== G09 完成 =====")
