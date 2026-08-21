#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互输入路径，遍历 .json 文件：
1. 若 shapes 数组长度 >= threshold（即一个 json 含多个框），输出其相对路径。
2. 对同一目录下编号连续的文件（如 000001.json 与 000002.json），
   比较其第一个矩形框：位置偏移 > 5 或面积变化 > 50% 任一满足即输出提示。
3. 将上述问题内容（多框 json 与框突变 json）所在帧及其前后各 2 帧的
   json 与原图（jpg），按原目录结构复制到同级 `<输入目录名>_Reviewed` 文件夹。
"""
import os
import json
import sys
import re
import shutil

# 视为原图的图片扩展名（不区分大小写）
IMAGE_EXTS = {".jpg"}


def enable_ansi_on_windows():
    """在 Windows 上启用 ANSI 转义序列支持（用于彩色输出），Linux/macOS 无需处理。"""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        # 非控制台环境（如重定向输出）下静默忽略
        pass


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


def parse_first_rect(json_path):
    """读取 json，返回第一个矩形的 (x1, y1, x2, y2)，非矩形或读取失败返回 None。"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    if not isinstance(data, dict):
        return None
    shapes = data.get("shapes", [])
    if not shapes:
        return None

    first = shapes[0]
    if first.get("shape_type") != "rectangle":
        return None

    points = first.get("points", [])
    if len(points) < 2:
        return None

    (x1, y1), (x2, y2) = points[0], points[1]
    return float(x1), float(y1), float(x2), float(y2)


def rect_area(rect):
    """计算矩形面积。"""
    x1, y1, x2, y2 = rect
    return abs(x2 - x1) * abs(y2 - y1)


def x_diff(a, b):
    """计算两个矩形 x1 与 x2 各自差值的最大值。"""
    return max(abs(a[0] - b[0]), abs(a[2] - b[2]))


def y_diff(a, b):
    """计算两个矩形 y1 与 y2 各自差值的最大值。"""
    return max(abs(a[1] - b[1]), abs(a[3] - b[3]))


def area_ratio_diff(a, b):
    """返回两个矩形面积变化比例（绝对值）。"""
    area_a = rect_area(a)
    area_b = rect_area(b)
    if area_a == 0 and area_b == 0:
        return 0.0
    if area_a == 0 or area_b == 0:
        return 1.0
    return abs(area_a - area_b) / max(area_a, area_b)


def extract_number(name):
    """提取文件名中的连续数字，用于判断编号连续。"""
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else None


def group_by_directory(json_paths):
    """按文件所在目录分组。"""
    groups = {}
    for path in json_paths:
        d = os.path.dirname(path)
        groups.setdefault(d, []).append(path)
    return groups


def check_consecutive_jumps(root, json_paths, x_threshold=25, y_threshold=20, area_ratio=0.65):
    """检查同一目录下编号连续的文件之间是否存在框突变，返回 (alerts, problem_paths)。"""
    groups = group_by_directory(json_paths)
    alerts = []
    problem_paths = []

    for directory, files in groups.items():
        # 只保留能提取数字的文件，按数字排序
        numbered = []
        for path in files:
            num = extract_number(os.path.basename(path))
            if num is not None:
                numbered.append((num, path))
        numbered.sort(key=lambda x: x[0])

        for i in range(1, len(numbered)):
            prev_num, prev_path = numbered[i - 1]
            curr_num, curr_path = numbered[i]
            if curr_num != prev_num + 1:
                continue

            prev_rect = parse_first_rect(prev_path)
            curr_rect = parse_first_rect(curr_path)
            if prev_rect is None or curr_rect is None:
                continue

            x_d = x_diff(prev_rect, curr_rect)
            y_d = y_diff(prev_rect, curr_rect)
            a_diff = area_ratio_diff(prev_rect, curr_rect)

            if x_d > x_threshold or y_d > y_threshold or a_diff > area_ratio:
                rel_prev = os.path.relpath(prev_path, root)
                rel_curr = os.path.relpath(curr_path, root)
                msg = f"{rel_prev} -> {rel_curr}: x偏移={x_d:.2f}, y偏移={y_d:.2f}, 面积变化={a_diff*100:.1f}%"
                if (x_d > x_threshold and a_diff > area_ratio) or y_d > y_threshold:
                    msg = f"\033[91m{msg}\033[0m"
                alerts.append(msg)
                problem_paths.append(prev_path)
                problem_paths.append(curr_path)

    return alerts, problem_paths


def is_image_file(name):
    """判断文件名是否为原图（jpg）。"""
    return os.path.splitext(name)[1].lower() in IMAGE_EXTS


def expand_problem_window(problem_json_paths, all_json_paths, all_img_paths, radius=2):
    """将每个问题 json 扩展到其前后各 radius 帧，返回去重后的 json+原图文件集合。"""
    json_map = {}  # 目录 -> {帧号: json 路径}
    img_map = {}   # 目录 -> {帧号: 图片路径}

    for path in all_json_paths:
        num = extract_number(os.path.basename(path))
        if num is None:
            continue
        json_map.setdefault(os.path.dirname(path), {})[num] = path

    for path in all_img_paths:
        num = extract_number(os.path.basename(path))
        if num is None:
            continue
        img_map.setdefault(os.path.dirname(path), {})[num] = path

    result = set()
    for path in problem_json_paths:
        num = extract_number(os.path.basename(path))
        directory = os.path.dirname(path)
        if num is None:
            result.add(path)
            continue

        for offset in range(-radius, radius + 1):
            target = num + offset
            json_path = json_map.get(directory, {}).get(target)
            if json_path:
                result.add(json_path)
            img_path = img_map.get(directory, {}).get(target)
            if img_path:
                result.add(img_path)

    return result


def copy_files_to_output(root, file_paths, suffix="_Reviewed"):
    """将文件集合按相对目录结构复制到同级输出文件夹，返回 (output_root, copied_count)。"""
    base = os.path.basename(os.path.normpath(root))
    output_root = os.path.join(os.path.dirname(os.path.normpath(root)), base + suffix)

    copied = 0
    for path in sorted(file_paths):
        rel = os.path.relpath(path, root)
        if rel.startswith(".."):
            continue
        dest = os.path.join(output_root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)
        copied += 1

    return output_root, copied


def main():
    enable_ansi_on_windows()
    root = input("请输入要扫描的目录路径: ").strip().strip('"').strip("'")
    if not root:
        print("未输入路径，退出。")
        sys.exit(1)
    if not os.path.isdir(root):
        print(f"路径不存在或不是目录: {root}")
        sys.exit(1)

    threshold = 2  # shapes 数量 >= 2，即视为含多个框（有问题）
    matched = []
    single_shape_paths = []
    problem_json_paths = set()
    all_json_paths = []
    all_img_paths = []

    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            lower = name.lower()
            if lower.endswith(".json"):
                all_json_paths.append(full)
                if has_multi_shapes(full, threshold):
                    rel = os.path.relpath(full, root)
                    matched.append(rel)
                    problem_json_paths.add(full)
                    print(rel)
                else:
                    single_shape_paths.append(full)
            elif is_image_file(name):
                all_img_paths.append(full)

    print(f"\n共找到 {len(matched)} 个含多个框的 json 文件。")

    print("\n检查编号连续文件之间的框突变...")
    alerts, jump_paths = check_consecutive_jumps(root, single_shape_paths)
    problem_json_paths.update(jump_paths)
    if alerts:
        for alert in alerts:
            print(alert)
        print(f"\n共发现 {len(alerts)} 处框突变。")
    else:
        print("未发现框突变。")

    if problem_json_paths:
        output_paths = expand_problem_window(problem_json_paths, all_json_paths, all_img_paths)
        output_root, copied = copy_files_to_output(root, output_paths)
        print(f"\n已输出 {copied} 个文件（问题帧前后各 2 帧的 JSON 与原图）到: {output_root}")
    else:
        print("\n没有需要输出的问题内容。")

    # 双击运行 exe 时保留窗口，等待用户确认后再退出
    input("\n处理完成，按回车键退出...")


if __name__ == "__main__":
    main()
