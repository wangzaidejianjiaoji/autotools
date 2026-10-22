import sys
import os
import glob
import json

"""
作用：将 debug.json（包含 DetbyStatus.real 中 rect=[x,y,w,h] 的检测结果以及 ImgH/ImgW）
      转换为标准 labelme 格式（version/flags/shapes/imagePath/imageData/imageHeight/imageWidth），
      label 直接取 detection 的 classification_ID。
用法：python debug.json_to_labelme.json_format.py
      运行后按提示输入包含 json 的目录路径，会原地写回 json。
关键参数：
  - input_directory (交互输入)：待处理的目录（会递归遍历所有 .json）
  - 已处理判定：若任一 json 已含 shapes[].points 字段则跳过整个目录，避免重复处理
  - imagePath：将原 .json 文件名后缀替换为 .jpg
  - imageHeight / imageWidth：读取 data["ImgH"] / data["ImgW"]
  - points：将 rect=[x,y,w,h] 转为 [[x,y],[x+w,y+h]]；label 取 classification_ID；shape_type=rectangle
"""

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

if __name__ == "__main__":
    input_directory = input("请输入目录路径: ")
    if not os.path.isdir(input_directory):
        print(f"错误: {input_directory} 不是有效的目录")
        exit(1)
    
    convert_json_format(input_directory)
    print("处理完成！")
