"""
作用：批量统一 labelme 格式 JSON 的标签。递归遍历输入路径下所有子目录的 JSON，
      仅修改每个 shape 的 label 值后直接写回原文件，其余字段（坐标、分辨率、imagePath 等）原样保留。
用法：python convert_to_labelme2.0-labelme标签转换.py
      运行后按提示输入 JSON 文件路径或目录路径。
关键参数：
  - input_path (交互输入)：单个 JSON 文件路径或包含 JSON 的目录路径
  - label (交互输入)：标签名称，直接回车默认 "drone"
"""

import os
import json

def rewrite_label(json_path, label):
    # utf-8-sig 兼容带 BOM 的文件（Windows 记事本/PowerShell 保存的常见格式）
    with open(json_path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    if not isinstance(data, dict) or 'shapes' not in data:
        print(f"警告: 非labelme格式（缺少shapes字段），已跳过 - {json_path}")
        return

    # 仅修改 label 值，其余字段原样保留
    for shape in data['shapes']:
        shape['label'] = label

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def find_json_files(input_path):
    """递归遍历所有子目录，收集所有 JSON 文件"""
    json_files = []
    for root, _, files in os.walk(input_path):
        for f in sorted(files):
            if f.endswith('.json'):
                json_files.append(os.path.join(root, f))
    return json_files

def process_directory(input_path, label):
    if os.path.isfile(input_path) and input_path.endswith('.json'):
        json_files = [input_path]
    elif os.path.isdir(input_path):
        json_files = find_json_files(input_path)
    else:
        print(f"错误: 路径不存在或不是有效的文件/目录 - {input_path}")
        return

    if not json_files:
        print("错误: 未找到任何JSON文件")
        return

    print(f"找到 {len(json_files)} 个JSON文件")

    # 按目录分组处理，日志以目录为单位输出目录名和数量
    groups = {}
    for json_file in json_files:
        groups.setdefault(os.path.dirname(json_file), []).append(json_file)

    for dir_path, dir_files in groups.items():
        print(f"{dir_path}: {len(dir_files)} 个")

        for json_file in dir_files:
            rewrite_label(json_file, label)

    print(f"\n{'='*60}")
    print(f"处理完成！共处理 {len(json_files)} 个JSON文件，{len(groups)} 个目录")

if __name__ == "__main__":
    print("labelme JSON标签批量统一工具")
    print("=" * 60)
    print("支持递归遍历目录及所有子目录下的多个JSON文件")
    print("仅修改所有shape的label值，其余字段原样保留")
    print("直接写回原JSON文件")
    print("=" * 60)

    input_path = input("输入JSON文件路径或目录路径: ").strip()

    while not os.path.exists(input_path):
        print(f"错误: 路径不存在 - {input_path}")
        input_path = input("请重新输入JSON文件路径或目录路径: ").strip()

    label = input("输入标签名称 (回车默认 drone): ").strip() or "drone"
    print(f"使用标签: {label}")

    process_directory(input_path, label)
