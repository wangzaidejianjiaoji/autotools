#!/usr/bin/env python3
"""
作用：递归扫描输入目录，在每个含 IR_label.json 的子目录里，把 exist 标志为 1 的帧
      按其 gt_rect=[x,y,w,h] 生成对应的 labelme json（命名 "六位帧号.json"）。
      适用于红外（IR）鸟类目标跟踪数据集。
用法：python IR_label.json_to_labelme.json.py
      运行后按提示输入根目录路径。
关键参数：
  - input_dir (交互输入)：根目录，会递归查找所有名为 IR_label.json 的文件
  - exist_list[i]==0：跳过该帧
  - label (交互输入)：标签名称，直接回车默认 "bird"
  - shape_type：固定为 "rectangle"
  - imageHeight / imageWidth：硬编码 512 / 640（红外图像常用分辨率）
  - 输出命名：{seq_num:06d}.json，imagePath 同名 .jpg
"""

import os
import json


def convert_gt_rect_to_points(gt_rect):
    x, y, w, h = gt_rect
    return [[float(x), float(y)], [float(x + w), float(y + h)]]


def process_ir_label(ir_label_path, dir_path, label):
    with open(ir_label_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    exist_list = data.get("exist", [])
    gt_rect_list = data.get("gt_rect", [])

    count = 0
    for i in range(len(exist_list)):
        if exist_list[i] == 0:
            continue

        gt_rect = gt_rect_list[i]
        points = convert_gt_rect_to_points(gt_rect)

        seq_num = i + 1
        filename = f"{seq_num:06d}"
        json_filename = f"{filename}.json"
        json_path = os.path.join(dir_path, json_filename)

        labelme_json = {
            "version": "4.5.7",
            "flags": {},
            "shapes": [
                {
                    "label": label,
                    "line_color": None,
                    "fill_color": None,
                    "points": points,
                    "shape_type": "rectangle",
                    "flags": {}
                }
            ],
            "imagePath": f"{filename}.jpg",
            "imageData": None,
            "imageHeight": 512,
            "imageWidth": 640
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(labelme_json, f, indent=4, ensure_ascii=False)

        print(f"  生成: {json_filename}  gt_rect={gt_rect}")
        count += 1

    return count


def main():
    print("=" * 60)
    print("IR_label.json 转 Labelme JSON 格式转换工具")
    print("=" * 60)

    input_dir = input("\n请输入目录路径: ").strip()

    if not os.path.exists(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        return

    if not os.path.isdir(input_dir):
        print(f"错误: 路径不是目录: {input_dir}")
        return

    label = input("输入标签名称 (回车默认 bird): ").strip() or "bird"
    print(f"使用标签: {label}")

    total_dirs = 0
    total_files = 0

    for root, dirs, files in os.walk(input_dir):
        if "IR_label.json" in files:
            ir_label_path = os.path.join(root, "IR_label.json")
            print(f"\n处理目录: {root}")
            count = process_ir_label(ir_label_path, root, label)
            total_dirs += 1
            total_files += count

    print(f"\n{'=' * 60}")
    print(f"处理完成! 共处理 {total_dirs} 个目录, 生成 {total_files} 个JSON文件")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
