#!/usr/bin/env python3
"""
作用：批量去除跟踪结果文件名末尾的时间戳后缀 _YYYYMMDD_HHMMSS，
     将例如 cb_building_20260414_mavic2_tracking_20260703_103619.txt
     重命名为 cb_building_20260414_mavic2_tracking.txt。

用法:
    # 默认: 迭代处理当前路径下所有子目录并执行重命名
    ./rename_results.py

    # 指定其他根路径
    ./rename_results.py --result-dir /path/to/result_dir

    # 只处理指定 tracker 目录（覆盖默认迭代行为）
    ./rename_results.py --dirs /path/to/tracker1 /path/to/tracker2

关键参数:
    - DEFAULT_RESULT_DIR   —— 默认根路径为 os.getcwd()，可通过 --result-dir 覆盖。
    - TIMESTAMP_PATTERN    —— 匹配规则：_20\d{6}_\d{6}（仅在扩展名前），
                              不会误删文件主体中已存在的日期串。
    - --result-dir         —— 待处理根目录（不传时遍历当前目录所有子目录）。
    - --dirs <path...>     —— 显式指定要处理的 tracker 目录列表，传入后跳过自动遍历。
    - 冲突保护：若重命名目标已存在则跳过并计入 conflict，不会覆盖。
"""

import os
import re
import argparse

# 匹配文件名末尾的时间戳后缀 _YYYYMMDD_HHMMSS（在扩展名之前）
# 例如: cb_building_20260414_mavic2_tracking_20260703_103619.txt
#       -> cb_building_20260414_mavic2_tracking.txt
TIMESTAMP_PATTERN = re.compile(r'_20\d{6}_\d{6}(?=\.[^.]+$)')

# 默认使用当前工作目录
DEFAULT_RESULT_DIR = os.getcwd()


def rename_one_dir(dir_path):
    """处理单个 tracker 结果目录，去除文件名末尾的时间戳后缀。"""
    if not os.path.isdir(dir_path):
        print(f"[skip] 不是目录: {dir_path}")
        return 0, 0, 0

    files = sorted(os.listdir(dir_path))
    print(f"\n=== 处理目录: {dir_path}  (共 {len(files)} 个文件) ===")

    changed = 0
    skipped = 0
    conflict = 0
    for old_name in files:
        old_path = os.path.join(dir_path, old_name)
        if not os.path.isfile(old_path):
            continue

        new_name = TIMESTAMP_PATTERN.sub('', old_name)
        if new_name == old_name:
            skipped += 1
            continue

        new_path = os.path.join(dir_path, new_name)

        if os.path.exists(new_path):
            print(f"[conflict] 目标已存在, 跳过: {old_name} -> {new_name}")
            conflict += 1
            continue

        print(f"[rename] {old_name}")
        print(f"       -> {new_name}")
        os.rename(old_path, new_path)
        changed += 1

    print(f"\n汇总: 已重命名 {changed} 个, 跳过 {skipped} 个, 冲突 {conflict} 个")
    return changed, skipped, conflict


def main():
    parser = argparse.ArgumentParser(
        description='去除跟踪结果文件名末尾的时间戳后缀 _YYYYMMDD_HHMMSS')
    parser.add_argument(
        '--result-dir', default=DEFAULT_RESULT_DIR,
        help='根路径，默认为当前工作目录')
    parser.add_argument(
        '--dirs', nargs='+', default=None,
        help='只处理指定的 tracker 结果目录列表（绝对路径）。'
             '不指定时默认迭代根路径下所有子目录')
    args = parser.parse_args()

    if args.dirs:
        dirs = args.dirs
    else:
        if not os.path.isdir(args.result_dir):
            print(f"[error] result_dir 不存在: {args.result_dir}")
            return
        dirs = [os.path.join(args.result_dir, d)
                for d in sorted(os.listdir(args.result_dir))
                if os.path.isdir(os.path.join(args.result_dir, d))]

    total_changed = total_skipped = total_conflict = 0
    for d in dirs:
        c, s, k = rename_one_dir(d)
        total_changed += c
        total_skipped += s
        total_conflict += k

    print(f"\n{'='*60}")
    print(f"全部完成: 重命名 {total_changed}, 跳过 {total_skipped}, 冲突 {total_conflict}")


if __name__ == '__main__':
    main()
