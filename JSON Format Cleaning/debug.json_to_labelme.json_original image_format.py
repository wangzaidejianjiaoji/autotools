import os
import glob
import sys
import json

def batch_rename_json_files(dir_path):
    # 检查目录是否存在
    if not os.path.isdir(dir_path):
        print(f"错误：目录 '{dir_path}' 不存在。")
        return

    # 获取所有 .json 文件
    json_files = glob.glob(os.path.join(dir_path, "*.json"))
    if not json_files:
        print(f"目录 '{dir_path}' 中没有找到 .json 文件。")
        return

    print(f"找到 {len(json_files)} 个 .json 文件。")

    # 存储重命名操作，用于最后确认
    rename_ops = []

    for filepath in json_files:
        basename = os.path.basename(filepath)
        name, ext = os.path.splitext(basename)

        # 查找最后一个下划线的位置
        last_underscore = name.rfind('_')
        if last_underscore == -1:
            print(f"跳过：'{basename}' 中没有下划线，无需处理。")
            continue

        # 检查最后一个下划线后的内容是否为 'drone' 或 'speckle'
        suffix = name[last_underscore+1:]
        if suffix not in ['drone', 'speckle']:
            print(f"跳过：'{basename}' 最后下划线后不是 'drone' 或 'speckle'，无需处理。")
            continue

        # 构建新文件名
        new_name = name[:last_underscore] + ext
        new_filepath = os.path.join(dir_path, new_name)

        # 检查目标文件是否已存在
        if os.path.exists(new_filepath):
            print(f"警告：无法重命名 '{basename}' -> '{new_name}'，因为目标文件已存在。")
            continue

        rename_ops.append((filepath, new_filepath, new_name))

    if not rename_ops:
        print("没有需要重命名的文件。")
        return

    # 显示将要执行的操作
    print("\n将执行以下重命名操作：")
    for old, new, new_name in rename_ops:
        print(f"  {os.path.basename(old)} -> {new_name}")

    # 执行重命名
    for old, new, _ in rename_ops:
        try:
            os.rename(old, new)
            print(f"已重命名：{os.path.basename(old)} -> {os.path.basename(new)}")
        except Exception as e:
            print(f"重命名失败：{os.path.basename(old)}，错误：{e}")

    print("批量重命名完成。")

def convert_json_format(input_dir):
    # 检查是否已经处理过（任一JSON文件中是否有points字段）
    processed = False
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                file_path = os.path.join(root, filename)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # 检查是否有shapes数组且其中包含points字段
                        if 'shapes' in data:
                            for shape in data['shapes']:
                                if 'points' in shape:
                                    processed = True
                                    break
                            if processed:
                                break
                    except Exception:
                        pass
        if processed:
            break
    
    if processed:
        print("检测到JSON文件已经处理过（包含points字段），无需重复执行。")
        return
    
    # 遍历目录及其所有子目录
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                file_path = os.path.join(root, filename)
                
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    relative_path = os.path.relpath(file_path, input_dir)
                    print(f"警告: 文件不存在，跳过处理: {relative_path}")
                    continue
                
                try:
                    # 读取原始JSON文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 构建新的JSON结构
                    new_data = {
                        "version": "4.5.7",
                        "flags": {},
                        "shapes": [],
                        "imagePath": filename.replace('.json', '.jpg'),  # 假设图像文件与JSON文件同名，扩展名不同
                        "imageData": None,
                        "imageHeight": data.get("ImgH", 0),
                        "imageWidth": data.get("ImgW", 0)
                    }
                    
                    # 处理real中的对象
                    if "DetbyStatus" in data and "real" in data["DetbyStatus"]:
                        for obj in data["DetbyStatus"]["real"]:
                            if "rect" in obj:
                                # 计算左上角和右下角坐标
                                x, y, width, height = obj["rect"]
                                x1, y1 = x, y  # 左上角
                                x2, y2 = x + width, y + height  # 右下角
                                
                                # 创建shape对象
                                shape = {
                                    "label": obj.get("classification_ID"),  # "label": obj.get("drone"), #  固定标签drone
                                    "line_color": None,
                                    "fill_color": None,
                                    "points": [[float(x1), float(y1)], [float(x2), float(y2)]],
                                    "shape_type": "rectangle",
                                    "flags": {}
                                }
                                new_data["shapes"].append(shape)
                    
                    # 写回文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(new_data, f, indent=4, ensure_ascii=False)
                    
                    # 打印相对路径，以便更好地了解处理的文件位置
                    relative_path = os.path.relpath(file_path, input_dir)
                    print(f"已处理文件: {relative_path}")
                except Exception as e:
                    relative_path = os.path.relpath(file_path, input_dir)
                    print(f"错误: 处理文件 {relative_path} 时发生异常: {str(e)}")
                    continue

def main():
    # 获取目录路径（优先使用命令行参数，否则使用用户输入）
    if len(sys.argv) > 1:
        dir_path = sys.argv[1].strip()
    else:
        dir_path = input("请输入要处理的目录路径: ").strip()

    # 检查目录是否存在
    if not os.path.isdir(dir_path):
        print(f"错误：目录 '{dir_path}' 不存在。")
        return

    # 第一步：执行重命名操作
    print("=== 开始执行第一步：重命名JSON文件 ===")
    batch_rename_json_files(dir_path)

    # 第二步：执行格式转换操作
    print("\n=== 开始执行第二步：转换JSON格式 ===")
    convert_json_format(dir_path)

    print("\n所有处理完成！")


if __name__ == "__main__":
    main()