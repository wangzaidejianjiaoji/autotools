# -*- coding: utf-8 -*-
"""
交互输入路径，遍历 .json 文件，
若 shapes 数组长度 >= threshold（即一个 json 含多个框），则打印其相对路径与文件名。
"""
import os
import json
import sys


def has_multi_shapes(json_path, threshold=2):
    """判断 labelme json 中 shapes 数量是否 >= threshold（即含多个框）。"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # 非法 json 或编码问题，跳过
        return False

    shapes = data.get("shapes", []) if isinstance(data, dict) else []
    return len(shapes) >= threshold


def main():
    root = input("请输入要扫描的目录路径: ").strip().strip('"').strip("'")
    if not root:
        print("未输入路径，退出。")
        sys.exit(1)
    if not os.path.isdir(root):
        print(f"路径不存在或不是目录: {root}")
        sys.exit(1)

    threshold = 2  # shapes 数量 >= 2，即视为含多个框（有问题）
    matched = []

    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.lower().endswith(".json"):
                continue
            full = os.path.join(dirpath, name)
            if has_multi_shapes(full, threshold):
                rel = os.path.relpath(full, root)
                matched.append(rel)
                print(rel)

    print(f"\n共找到 {len(matched)} 个含多个框的 json 文件。")


if __name__ == "__main__":
    main()
