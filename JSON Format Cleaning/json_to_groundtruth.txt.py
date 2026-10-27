"""
作用：遍历指定目录下所有 labelme 格式 json，提取每个矩形框 (x,y,w,h)，
      按 json 文件名顺序聚合写入到与目录同名的 groundtruth.txt，
      文件命名里 "_YYMMDD_" 形式的日期会被改写为 "_20YYMMDD_"。
用法：python json_to_groundtruth.txt.py
      运行后按提示输入 JSON 文件所在目录路径。
关键参数：
  - path (交互输入)：存放 labelme json 的目录，仅处理顶层 *.json（不递归）
  - 每行格式："x.xxx,y.yyy,w.www,h.hhh"
  - 输出：<path>/<folder_name>_groundtruth.txt，其中 folder_name 为目录名
    （若含 "_YYMMDD_" 子串会被改写为 "_20YYMMDD_"）
"""

import os
import re
import glob
import json

def process_labelme_json(json_path):
    """从labelme格式的JSON文件中提取矩形框的x,y,w,h"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    for shape in data.get('shapes', []):
        if shape.get('shape_type') == 'rectangle':
            points = shape.get('points', [])
            if len(points) >= 2:
                x1, y1 = points[0]  # 左上角
                x2, y2 = points[1]  # 右下角
                x = min(x1, x2)
                y = min(y1, y2)
                w = abs(x2 - x1)
                h = abs(y2 - y1)
                results.append(f"{x:.3f},{y:.3f},{w:.3f},{h:.3f}")
    return results

def main():
    # 交互输入路径
    path = input("请输入JSON文件所在目录路径: ").strip().strip('"')

    # 查找所有json文件并按名称排序
    json_pattern = os.path.join(path, "*.json")
    json_files = sorted(glob.glob(json_pattern))

    if not json_files:
        print("未找到任何JSON文件")
        return

    print(f"找到 {len(json_files)} 个JSON文件")

    # 处理所有JSON文件
    groundtruth_results = []
    for json_file in json_files:
        results = process_labelme_json(json_file)
        groundtruth_results.extend(results)
        print(f"已处理: {os.path.basename(json_file)}")

    # 写入groundtruth.txt
    folder_name = os.path.basename(path)
    folder_name = re.sub(r'_(\d{2})(\d{2})(\d{2})_', r'_20\1\2\3_', folder_name)
    output_path = os.path.join(path, f"{folder_name}_groundtruth.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in groundtruth_results:
            f.write(line + "\n")

    print(f"\n完成! 共生成 {len(groundtruth_results)} 条记录")
    print(f"输出文件: {output_path}")

if __name__ == "__main__":
    main()
