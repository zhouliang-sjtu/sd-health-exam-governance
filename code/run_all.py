# -*- coding: utf-8 -*-
"""run_all.py —— 多源体检队列数据治理与质量审计系统 V1.0 · 统一调度入口

按治理管线编号顺序调度各模块（编号即执行顺序）：
  G01a 原始解析 → G01b 移位还原 → G01c 深度审计 → G01 H清洗层
  → G02 PG清洗层 → G03 PD清洗层
  → G04 H镜像层 → G05 PG镜像层 → G05b PG宽视图(可选) → G06 PD镜像层
  → G09 资产总索引 → A00 影响评估(可选)

用法：
  python run_all.py --list                  查看管线阶段清单
  python run_all.py --upto G01              顺序执行 G01a→G01b→G01c→G01
  python run_all.py --only G01b             单独执行一个阶段
  python run_all.py --upto G09 --skip G05b  顺序执行并跳过可选阶段
  python run_all.py                         等价于 --list
"""
import argparse
import os
import subprocess
import sys
import time

CODE_DIR = os.path.dirname(os.path.abspath(__file__))

STAGES = [
    ("G01a", "H 原始逐年 XLS 解析与跨年链接（Node.js）", "G01a_H_raw_link.js", "node"),
    ("G01b", "H 2022 列移位检测与整行还原", "G01b_H_2022_shift_fix.py", "python"),
    ("G01c", "H 深度质量审计（校验和/跨年分布/行级签名）", "G01c_H_deep_audit.py", "python"),
    ("G01", "H 规范化清洗与标准衍生层（wave/person/数据字典）", "G01_H_clean.py", "python"),
    ("G02", "PG 清洗与人-年聚合 + 标准衍生层", "G02_PG_clean.py", "python"),
    ("G03", "PD 文本化验抽取/去重/审计/数据字典", "G03_PD_clean.py", "python"),
    ("G04", "H 镜像层 1:1 清洗（7 张年度表 + T2DM 三工作簿）", "G04_H_mirror_tables.py", "python"),
    ("G05", "PG 镜像层流式清洗（含 2,166 万行检验长表）", "G05_PG_mirror_tables.py", "python"),
    ("G05b", "PG 问卷宽视图服务端流式导出（可选，需 PostgreSQL）", "G05b_PG_views_finish.py", "python"),
    ("G06", "PD 镜像层 1:1 清洗（3 张年度表 + 死因表）", "G06_PD_mirror_tables.py", "python"),
    ("G09", "数据资产总索引生成（xlsx 八工作表）", "G09_build_index.py", "python"),
    ("A00", "治理影响评估（可选：修复前后对照 + 重跑必要性）", "A00_impact_assessment.py", "python"),
]
OPTIONAL = {"G05b", "A00"}


def stage_index(tag):
    for i, (t, _, _, _) in enumerate(STAGES):
        if t == tag:
            return i
    sys.exit(f"[run_all] 未知阶段: {tag}（--list 查看全部）")


def run_stage(tag, script, runner):
    print(f"\n{'=' * 72}\n[run_all] 阶段 {tag} -> {script}")
    t0 = time.time()
    rc = subprocess.call([runner, os.path.join(CODE_DIR, script)], cwd=CODE_DIR)
    dt = time.time() - t0
    if rc != 0:
        sys.exit(f"[run_all] 阶段 {tag} 失败（exit={rc}，耗时 {dt:.0f}s）——管线中止")
    print(f"[run_all] 阶段 {tag} 完成，耗时 {dt:.0f}s")


def main():
    ap = argparse.ArgumentParser(
        description="多源体检队列数据治理与质量审计系统 V1.0 统一调度入口")
    ap.add_argument("--list", action="store_true", help="列出管线阶段后退出")
    ap.add_argument("--upto", metavar="TAG", help="顺序执行至指定阶段（含）")
    ap.add_argument("--only", metavar="TAG", help="仅执行指定阶段")
    ap.add_argument("--skip", metavar="TAG", action="append", default=[],
                    help="跳过指定阶段（可多次，如 --skip G05b）")
    args = ap.parse_args()

    print("多源体检队列数据治理与质量审计系统 V1.0 —— 治理管线阶段：")
    for i, (tag, desc, _, _) in enumerate(STAGES):
        opt = " [可选]" if tag in OPTIONAL else ""
        print(f"  {i + 1:2d}. {tag:5s} {desc}{opt}")

    if args.list or (not args.upto and not args.only):
        return

    if args.only:
        seq = [s for s in STAGES if s[0] == args.only]
        if not seq:
            sys.exit(f"[run_all] 未知阶段: {args.only}")
    else:
        seq = [s for s in STAGES[:stage_index(args.upto) + 1]
               if s[0] not in args.skip]

    for tag, _, script, runner in seq:
        if not os.path.exists(os.path.join(CODE_DIR, script)):
            sys.exit(f"[run_all] 缺少脚本: {script}")
        run_stage(tag, script, runner)
    print(f"\n[run_all] 全部 {len(seq)} 个阶段执行完毕。")


if __name__ == "__main__":
    main()
