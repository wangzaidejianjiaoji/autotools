#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互对比完整标注 A 与预标注 B，仅比较 LabelMe 的 shapes[].points。

运行：python compare_annotation_points_标注量检查.py
匹配：A/相对子目录/文件名.json -> B/相对子目录/文件名.json。
计数单位为 JSON 文件；坐标、框数量、框顺序、点顺序必须完全一致。
忽略修改时间以及 label 等其他字段。空 shapes 是有效的空标注。
B 缺失与读取/格式异常单独计数，不计入确定的实际标注数量。
没有 shapes 和 points 字段的元数据 JSON 跳过，不作为标注计数。
B 位于 A 内时排除 B；只读取数据，不修改任何标注文件。
"""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path


@dataclass
class Counts:
    unchanged: int = 0
    changed: int = 0
    missing: int = 0
    errors: int = 0
    skipped: int = 0

    def summary(self):
        text = f"没有改动的数量 {self.unchanged}，实际标注 {self.changed}"
        if self.missing:
            text += f"，B缺失 {self.missing}"
        if self.errors:
            text += f"，读取/格式异常 {self.errors}"
        if self.skipped:
            text += f"，跳过非标注JSON {self.skipped}"
        return text


def read_points(path):
    """保留框和点的原始顺序，避免缺少 points 被误判成空标注。"""
    with path.open(encoding="utf-8-sig") as file:
        data = json.load(file)
    if isinstance(data, dict) and "shapes" not in data and "points" not in data:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("shapes"), list):
        raise ValueError("JSON 缺少有效的 shapes 数组")
    result = []
    for shape in data["shapes"]:
        if not isinstance(shape, dict) or not isinstance(shape.get("points"), list):
            raise ValueError("标注缺少有效的 points 数组")
        points = shape["points"]
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("每个点必须是 [x, y]")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in point
            ):
                raise ValueError("坐标必须是有限数字")
        result.append(points)
    return result


def compare_directory(dir_a, dir_b):
    """按目录输出结果，并返回 A 全部 JSON 的统计。遍历失败直接报错。"""
    dir_a, dir_b = Path(dir_a).resolve(), Path(dir_b).resolve()
    if not dir_a.is_dir() or not dir_b.is_dir():
        raise ValueError("A、B 必须是存在的目录")
    if dir_a == dir_b:
        raise ValueError("A、B 不能是同一个目录")
    total = Counts()

    def walk_error(error):
        raise error

    for root, dirs, files in os.walk(dir_a, onerror=walk_error):
        directory = Path(root)
        dirs[:] = sorted(
            name for name in dirs if (directory / name).resolve() != dir_b
        )
        json_files = sorted(name for name in files if name.lower().endswith(".json"))
        if not json_files:
            continue
        relative = directory.relative_to(dir_a)
        counts = Counts()
        for filename in json_files:
            a_file = directory / filename
            b_file = dir_b / relative / filename
            try:
                a_points = read_points(a_file)
                if a_points is None:
                    counts.skipped += 1
                    continue
                try:
                    b_points = read_points(b_file)
                except FileNotFoundError:
                    counts.missing += 1
                    continue
                if b_points is None:
                    raise ValueError("B 对应 JSON 不是标注文件")
                if a_points == b_points:
                    counts.unchanged += 1
                else:
                    counts.changed += 1
            except (OSError, ValueError, OverflowError):
                counts.errors += 1
        total.unchanged += counts.unchanged
        total.changed += counts.changed
        total.missing += counts.missing
        total.errors += counts.errors
        total.skipped += counts.skipped
        if counts.unchanged + counts.changed + counts.missing + counts.errors:
            print(f"子目录 {relative if relative.parts else '（根目录）'} {counts.summary()}")

    print(f"路径A {dir_a} {total.summary()}")
    return total


def input_directory(prompt):
    while True:
        value = input(prompt).strip().strip('"').strip("'")
        if not value:
            print("路径不能为空，请重新输入。")
            continue
        path = Path(os.path.expandvars(value)).expanduser()
        if path.is_dir():
            return path.resolve()
        print("目录不存在，请重新输入。")


def main():
    try:
        dir_a = input_directory("请输入完整标注路径 A：")
        dir_b = input_directory("请输入预标注路径 B：")
        compare_directory(dir_a, dir_b)
        return 0
    except (OSError, ValueError) as error:
        print(f"统计未完成：{error}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
