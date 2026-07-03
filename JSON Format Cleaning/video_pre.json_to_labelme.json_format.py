import json
import os

def convert_json_to_labelme(input_json_path, output_dir):
    # 检查输入文件是否存在
    if not os.path.exists(input_json_path):
        print(f"错误: 输入文件 '{input_json_path}' 不存在")
        return False
    
    # 创建输出目录（如果不存在）
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出目录: {output_dir}")
    
    # 读取输入JSON文件
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
    except Exception as e:
        print(f"错误: 读取输入文件失败 - {str(e)}")
        return False
    
    # 提取基础文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(input_json_path))[0]
    # 移除_ostrack后缀（如果存在）
    if base_name.endswith('_ostrack'):
        base_name = base_name[:-8]
    
    # 处理每个帧
    generated_count = 0
    for frame_id, bboxes in input_data.items():
        # 生成输出文件名（帧号从1开始，补零到5位）
        frame_num = int(frame_id)
        output_filename = f"{base_name}_{str(frame_num).zfill(5)}.json"
        output_path = os.path.join(output_dir, output_filename)
        
        # 生成对应的图像文件名
        image_filename = f"{base_name}_{str(frame_num).zfill(5)}.jpg"
        
        # 检查对应的jpg文件是否存在
        image_path = os.path.join(output_dir, image_filename)
        if not os.path.exists(image_path):
            print(f"跳过: 对应图像文件 '{image_filename}' 不存在")
            continue

        # 构建LabelMe格式的数据
        labelme_data = {
            "version": "4.5.7",
            "flags": {},
            "shapes": [],
            "imagePath": image_filename,
            "imageData": None,
            "imageHeight": 1024,  # 固定图像高度
            "imageWidth": 1280    # 固定图像宽度
        }
        
        # 处理每个边界框
        for bbox in bboxes:
            if len(bbox) >= 4:
                x1, y1, x2, y2 = bbox[:4]
                
                # 确保左上角坐标小于右下角坐标
                if x1 > x2:
                    x1, x2 = x2, x1
                if y1 > y2:
                    y1, y2 = y2, y1
                
                # 创建形状对象
                shape = {
                    "label": "drone",  # 固定为drone
                    "line_color": None,
                    "fill_color": None,
                    "points": [
                        [float(x1), float(y1)],  # 左上角坐标
                        [float(x2), float(y2)]   # 右下角坐标
                    ],
                    "shape_type": "rectangle",
                    "flags": {}
                }
                labelme_data["shapes"].append(shape)
        
        # 保存输出JSON文件
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(labelme_data, f, indent=4, ensure_ascii=False)
            print(f"已生成: {output_filename}")
            generated_count += 1
        except Exception as e:
            print(f"错误: 保存文件 '{output_filename}' 失败 - {str(e)}")
            return False
    
    print(f"\n转换完成! 共生成 {generated_count} 个文件")
    return True

def main():
    print("=" * 60)
    print("JSON转LabelMe格式工具")
    print("=" * 60)
    
    # 使用input()获取用户输入
    input_json_path = input("请输入输入JSON文件路径: ")
    output_dir = input("请输入生成目标目录: ")
    
    print("\n开始转换...")
    success = convert_json_to_labelme(input_json_path, output_dir)
    
    if success:
        print("\n转换成功!")
    else:
        print("\n转换失败!")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
