import os
import json
from PIL import Image


def get_image_dimensions(image_path):
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        print(f"无法读取图片尺寸: {image_path}, 错误: {e}")
        return None


def create_labelme_data(x1, y1, x2, y2, image_filename, image_width, image_height, label="drone"):
    """
    创建单个labelme格式的JSON数据
    """
    shape = {
        "label": label,
        "line_color": None,
        "fill_color": None,
        "points": [
            [x1, y1],
            [x2, y2]
        ],
        "shape_type": "rectangle",
        "flags": {}
    }
    
    labelme_data = {
        "version": "4.5.7",
        "flags": {},
        "shapes": [shape],
        "imagePath": image_filename,
        "imageData": None,
        "imageHeight": image_height,
        "imageWidth": image_width
    }
    
    return labelme_data


def convert_txt_to_labelme(txt_path, image_path=None, image_width=1280, image_height=1024, label="drone"):
    """
    将txt文件转换为labelme格式的JSON
    txt格式: 每行一帧，格式为 x1,y1,width,height
    返回一个列表，每个元素是一帧的labelme数据
    """
    results = []
    
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(',')
        if len(parts) < 4:
            continue
        
        try:
            x1 = float(parts[0].strip())
            y1 = float(parts[1].strip())
            width = float(parts[2].strip())
            height = float(parts[3].strip())
        except ValueError:
            continue
        
        x2 = x1 + width
        y2 = y1 + height
        
        if image_path:
            image_filename = os.path.basename(image_path)
        else:
            txt_basename = os.path.splitext(os.path.basename(txt_path))[0]
            image_filename = txt_basename + ".jpg"
        
        labelme_data = create_labelme_data(x1, y1, x2, y2, image_filename, image_width, image_height, label)
        results.append(labelme_data)
    
    return results


def main():
    print("=== TXT转Labelme JSON工具 ===")
    print("说明：txt文件中每行对应一帧，将为每一帧生成独立的JSON文件")
    print("输出目录：txt文件所在目录")
    print()
    
    txt_path = input("请输入txt文件路径：").strip()
    
    if not os.path.exists(txt_path):
        print(f"错误：文件不存在: {txt_path}")
        return
    
    if not txt_path.lower().endswith('.txt'):
        print("错误：文件必须是.txt格式")
        return
    
    txt_dir = os.path.dirname(txt_path)
    txt_fullname = os.path.basename(txt_path)
    txt_basename = os.path.splitext(txt_fullname)[0]
    
    print("\n请选择JSON命名格式：")
    print("1: 末级目录名_五位帧号 (如：folder_00001.json)")
    print("2: 六位帧号 (如：000001.json)")
    
    while True:
        format_choice = input("请输入选择 (1 或 2)：").strip()
        if format_choice in ['1', '2']:
            format_choice = int(format_choice)
            break
        print("无效输入，请输入 1 或 2")
    
    print("\n请选择起始帧号：")
    print("0: 从0开始")
    print("1: 从1开始")
    
    while True:
        start_frame = input("请输入起始帧号 (0 或 1)：").strip()
        if start_frame in ['0', '1']:
            start_frame = int(start_frame)
            break
        print("无效输入，请输入 0 或 1")
    
    base_name = os.path.basename(txt_dir) if format_choice == 1 else ""
    
    print(f"\n输出目录设置：")
    print(f"默认目录：{txt_dir}")
    output_dir_input = input("请输入输出目录（直接回车使用默认目录）：").strip()
    output_dir = output_dir_input if output_dir_input else txt_dir
    os.makedirs(output_dir, exist_ok=True)
    
    if format_choice == 1:
        first_image_path = os.path.join(txt_dir, f"{base_name}_{start_frame:05d}.jpg")
    else:
        first_image_path = os.path.join(txt_dir, f"{start_frame:06d}.jpg")
    
    if os.path.exists(first_image_path):
        img_dimensions = get_image_dimensions(first_image_path)
        if img_dimensions:
            image_width, image_height = img_dimensions
            print(f"已获取图片尺寸: {image_width} x {image_height}")
        else:
            print("无法获取图片尺寸，使用默认尺寸 1280x1024")
            image_width = 1920
            image_height = 1080
    else:
        print(f"警告：未找到第一张图片 {first_image_path}")
        print("将使用默认尺寸 1280x1024")
        image_width = 1920
        image_height = 1080
    
    label = "drone"
    
    frame_data_list = []
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(',')
        if len(parts) < 4:
            continue
        
        try:
            x1 = float(parts[0].strip())
            y1 = float(parts[1].strip())
            width = float(parts[2].strip())
            height = float(parts[3].strip())
        except ValueError:
            continue
        
        x2 = x1 + width
        y2 = y1 + height
        
        frame_num = i + start_frame
        
        if format_choice == 1:
            image_filename = f"{base_name}_{frame_num:05d}.jpg"
        else:
            image_filename = f"{frame_num:06d}.jpg"
        
        labelme_data = create_labelme_data(x1, y1, x2, y2, image_filename, image_width, image_height, label)
        frame_data_list.append(labelme_data)
    
    for i, frame_data in enumerate(frame_data_list):
        frame_num = i + start_frame
        
        if format_choice == 1:
            json_filename = f"{base_name}_{frame_num:05d}.json"
        else:
            json_filename = f"{frame_num:06d}.json"
        
        json_path = os.path.join(output_dir, json_filename)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(frame_data, f, indent=4, ensure_ascii=False)
        
        print(f"已生成：{json_filename}")
    
    print(f"\n转换完成！")
    print(f"共生成 {len(frame_data_list)} 个JSON文件")
    print(f"输出目录：{output_dir}")


if __name__ == "__main__":
    main()