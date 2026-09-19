# post_governance_audit — 三库清洗残留三专项审计（只读）

> 运行时生成 post_governance_audit.py；输入 = 清洗层 wave 表 + 治理报告 + 审计 CSV + m2 引擎。本审计不改任何清洗产物；残留处置（如库C V1.1 补丁）另行裁决。

## A1 规则×字段覆盖矩阵

| rule                                  | A(库A)                               | B(库B)                                 | C(库C)                                         |
|:--------------------------------------|:------------------------------------|:--------------------------------------|:----------------------------------------------|
| 移位主探针 r01（bun/urea 位>25 & ua 位<90）    | actioned (移位修复 9,396 行 + 残差扫描 0)    | structurally-na (无 bun)               | scan-absent (探针字段具备可做未做；无移位事件已知)              |
| 移位回落 r02（crea 位 150–1500 & ua 位 2–20） | actioned (移位修复 9,396 行 + 残差扫描 0)    | scan-absent (r02 字段具备可做未做；无移位事件已知)    | scan-absent (探针字段具备可做未做；无移位事件已知)              |
| 血压颠倒 SBP<DBP                          | actioned (n=130)                    | structurally-na (无 sbp,dbp)           | actioned (n=52)                               |
| 脂类反转 HDL>TC                           | actioned (n=4)                      | actioned (n=0)                        | actioned (n=38)                               |
| 脂类反转 LDL>TC                           | actioned (n=14)                     | gap (本次扫描残留 0 行)                      | actioned (n=973)                              |
| 尿酸单位混串 UA<120                         | actioned (n=131)                    | actioned (n=35)                       | actioned (n=323)                              |
| 血糖下限 FPG<3.0                          | actioned (n=14)                     | actioned (n=1)                        | actioned (n=2,072)                            |
| BMI 恒等式 |BMI−W/H²|>2.5                | actioned (n=33)                     | structurally-na (无 bmi,height,weight) | actioned (n=207)                              |
| TG 上限 >25                             | actioned (n=5)                      | actioned (n=45)                       | actioned (n=33)                               |
| 肌酐下限 <20                              | actioned (n=6)                      | actioned (n=4)                        | actioned (n=1,676)                            |
| 血小板上限 >800                            | actioned (n=6)                      | gap (本次扫描残留 2 行)                      | structurally-na (无 plt)                       |
| 血红蛋白下限 <60                            | actioned (n=17)                     | structurally-na (无 hb)                | structurally-na (无 hb)                        |
| 白细胞上限 >25                             | actioned (n=15)                     | structurally-na (无 wbc)               | structurally-na (无 wbc)                       |
| 转氨酶天花板 >1500                          | actioned (n=3)                      | gap (本次扫描残留 0 行)                      | actioned (n=1)                                |
| 文本域错配（ECG 文本含超声词）                     | actioned via 2022 移位重映射；独立词典扫描未单列证据 | structurally-na (无自由文本字段)             | extraction-domain (us_text/ecg_text 已抽取，清洗域外) |
| 年龄合理性 age<18                          | flag-only (签名标记 n=24, 未见置缺动作)       | not-scanned                           | not-scanned                                   |

## A2 残留扫描汇总

- 库C：合计 0 行；逐规则 r01_shift_probe=0, r02_shift_fb=0, r03_bp_rev=0, r04_hdl_gt_tc=0, r05_ldl_gt_tc=0, r06_ua_low=0, r07_fpg_low=0, r08_bmi_incons=0, r09_tg_high=0, r10_crea_low=0, r14_altast_high=0；与 m2 阴性对照逐规则一致 OK
- 库B gap 规则残留：{'ldl>tc': 0, 'alt/ast>1500': 0, 'plt>800': 2}；已落地家族静默自检 {'fpg<3': 0, 'tg>25': 0, 'ua<120': 0, 'crea<20': 0, 'hdl>tc': 0}（治理报告 {'fpg<3': 1, 'fpg>30': 0, 'hba1c<3或>15': 4, 'tg>25': 45, 'ua<120': 35, 'crea<20': 4, 'hdl>tc': 0}）
- 明细：audit_residuals_libC.csv / audit_residuals_libB.csv

## A3 库A 2022 波 FPG 离散度

|   year |   n_fpg |   n_1dp |   rate_1dp |   n_05 |   rate_05 |   med |   n_ge7 |
|-------:|--------:|--------:|-----------:|-------:|----------:|------:|--------:|
|   2018 |   14297 |    1438 |  0.100581  |    295 | 0.0206337 |  5.43 |    1825 |
|   2019 |   16116 |    1658 |  0.102879  |    318 | 0.0197319 |  5.49 |    2165 |
|   2020 |   15924 |    1567 |  0.0984049 |    301 | 0.0189023 |  5.48 |    2165 |
|   2021 |   15437 |    1551 |  0.100473  |    306 | 0.0198225 |  5.57 |    2281 |
|   2022 |   17164 |    1665 |  0.0970054 |    335 | 0.0195176 |  5.45 |    2437 |
|   2023 |   21345 |    2202 |  0.103162  |    468 | 0.0219255 |  5.62 |    3544 |
|   2024 |   20448 |    2024 |  0.0989828 |    418 | 0.0204421 |  5.57 |    3220 |

- 2022 波 1dp 且 FPG∈[4.5,8.5]: 1,493 行（≥7.0 候选残留假阳性 165；块内/块外 = 824/669）
- 候选行 bun/ua/crea 缺失率: {'bun': 0.0020093770931011385, 'ua': 0.0026791694574681848, 'crea': 0.0026791694574681848}
- 明细：audit_2022_fpg_residual.csv
