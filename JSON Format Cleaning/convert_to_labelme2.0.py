import json
import os

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def get_image_size(image_path):
    if not HAS_PIL:
        print("警告: PIL库未安装，将使用默认分辨率 1920x1080")
        return 1920, 1080
    
    if not os.path.exists(image_path):
        print(f"警告: 图片文件不存在 - {image_path}，将使用默认分辨率 1920x1080")
        return 1920, 1080
    
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            print(f"检测到图片分辨率: {width} x {height}")
            return width, height
    except Exception as e:
        print(f"警告: 读取图片失败 - {e}，将使用默认分辨率 1920x1080")
        return 1920, 1080

def convert_to_labelme(input_json_path, output_dir):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    base_name = os.path.splitext(os.path.basename(input_json_path))[0]
    
    os.makedirs(output_dir, exist_ok=True)
    
    first_frame_path = os.path.join(output_dir, f"{base_name}_00000.jpg")
    image_width, image_height = get_image_size(first_frame_path)
    
    for frame_num, box_data in data.items():
        x1, y1, x2, y2, confidence = box_data
        
        labelme_json = {
            "version": "4.5.7",
            "flags": {},
            "shapes": [
                {
                    "label": "drone",
                    "line_color": None,
                    "fill_color": None,
                    "points": [
                        [x1, y1],
                        [x2, y2]
                    ],
                    "shape_type": "rectangle",
                    "flags": {}
                }
            ],
            "imagePath": f"{base_name}_{frame_num.zfill(5)}.jpg",
            "imageData": None,
            "imageHeight": image_height,
            "imageWidth": image_width
        }
        
        output_path = os.path.join(output_dir, f"{base_name}_{frame_num.zfill(5)}.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(labelme_json, f, indent=4)
        
        print(f"Generated: {output_path}")
    
    print(f"\nSuccessfully generated {len(data)} labelme JSON files.")

def process_directory(input_path):
    if os.path.isfile(input_path) and input_path.endswith('.json'):
        json_files = [input_path]
        input_dir = os.path.dirname(input_path)
    elif os.path.isdir(input_path):
        json_files = sorted([f for f in os.listdir(input_path) if f.endswith('.json')])
        json_files = [os.path.join(input_path, f) for f in json_files]
        input_dir = input_path
    else:
        print(f"错误: 路径不存在或不是有效的文件/目录 - {input_path}")
        return
    
    if not json_files:
        print("错误: 未找到任何JSON文件")
        return
    
    print(f"找到 {len(json_files)} 个JSON文件")
    
    for json_file in json_files:
        print(f"\n{'='*60}")
        print(f"正在处理: {json_file}")
        
        base_name = os.path.splitext(os.path.basename(json_file))[0]
        output_dir = os.path.join(input_dir, base_name)
        
        print(f"输出目录: {output_dir}")
        
        convert_to_labelme(json_file, output_dir)
    
    print(f"\n{'='*60}")
    print(f"处理完成！共处理 {len(json_files)} 个JSON文件")

if __name__ == "__main__":
    print("视频帧JSON转labelme格式工具")
    print("=" * 60)
    print("支持遍历目录下的多个JSON文件")
    print("每个JSON文件将在输入目录下创建同名文件夹存放输出")
    print("=" * 60)
    
    input_path = input("输入JSON文件路径或目录路径: ").strip()
    
    while not os.path.exists(input_path):
        print(f"错误: 路径不存在 - {input_path}")
        input_path = input("请重新输入JSON文件路径或目录路径: ").strip()
    
    process_directory(input_path)