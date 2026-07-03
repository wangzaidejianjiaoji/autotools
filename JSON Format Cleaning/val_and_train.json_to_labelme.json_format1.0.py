import os
import json
from pathlib import Path
from PIL import Image


def convert_bbox_format(bbox):
    """将[x, y, width, height]格式转换为[[x1, y1], [x2, y2]]格式"""
    x, y, width, height = bbox
    return [[x, y], [x + width, y + height]]


def build_image_index(base_path):
    """
    构建图片文件索引，加速查找
    返回：{文件名: 完整路径} 的字典
    """
    print(f"正在建立图片索引...")
    image_index = {}
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.JPG', '.JPEG', '.PNG', '.BMP', '.TIFF')
    
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(image_extensions):
                full_path = os.path.join(root, file)
                # 使用文件名作为key（不区分大小写）
                key = file.lower()
                # 如果有重复，保存所有路径
                if key in image_index:
                    if isinstance(image_index[key], list):
                        image_index[key].append(full_path)
                    else:
                        image_index[key] = [image_index[key], full_path]
                else:
                    image_index[key] = full_path
    
    print(f"索引完成，找到 {len(image_index)} 个图片文件")
    return image_index


def find_image_by_path(img_path, image_index, base_path):
    """
    根据路径查找图片，支持多种路径格式
    """
    # 标准化路径（统一使用反斜杠）
    img_path_normalized = os.path.normpath(img_path)
    
    # 尝试1: 使用文件名查找（不区分大小写）
    filename = os.path.basename(img_path).lower()
    if filename in image_index:
        result = image_index[filename]
        if isinstance(result, list):
            # 如果有多个匹配，优先选择路径匹配度高的
            for path in result:
                if img_path_normalized.replace('/', '\\') in path:
                    return path
            return result[0]
        return result
    
    # 尝试2: 使用完整相对路径查找
    full_path = os.path.join(base_path, img_path_normalized)
    if os.path.exists(full_path):
        return full_path
    
    # 尝试3: 处理 "6/390.jpg" -> "6\6\390.jpg" 这种情况
    # 提取目录编号
    path_parts = img_path_normalized.split(os.sep)
    if len(path_parts) >= 2:
        # 例如: "6/390.jpg" -> ["6", "390.jpg"]
        folder_num = path_parts[0]
        # 尝试 base_path/6/6/390.jpg
        double_folder_path = os.path.join(base_path, folder_num, folder_num, *path_parts[1:])
        if os.path.exists(double_folder_path):
            return double_folder_path
    
    # 尝试4: 在image_index中模糊匹配路径
    for key, value in image_index.items():
        paths = [value] if not isinstance(value, list) else value
        for path in paths:
            # 检查路径是否包含所有路径部分
            path_lower = path.lower()
            parts_to_match = [p.lower() for p in path_parts if p]
            if all(part in path_lower for part in parts_to_match):
                # 进一步验证顺序是否正确
                if len(parts_to_match) >= 2:
                    # 检查路径结构是否匹配
                    path_normalized = os.path.normpath(path).lower()
                    if parts_to_match[-1] in path_normalized:  # 文件名匹配
                        return path
    
    return None


def process_annotation_file(annotation_file, base_path, output_base_path, debug=False):
    """处理单个标注文件（val.json或train.json）"""
    print(f"\n{'='*60}")
    print(f"处理文件: {os.path.basename(annotation_file)}")
    print(f"{'='*60}")

    try:
        with open(annotation_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: JSON格式错误 - 第{e.lineno}行, 第{e.colno}列")
        print(f"请检查并修复文件: {annotation_file}")
        return
    except Exception as e:
        print(f"错误: 无法读取文件: {e}")
        return

    if not isinstance(data, list):
        print(f"警告: JSON内容不是列表格式，跳过")
        return

    print(f"找到 {len(data)} 条标注数据\n")
    
    # 构建图片索引
    image_index = build_image_index(base_path)
    
    # 按目录分组处理
    dir_items = {}  # {目录路径: [items]}
    not_found_items = []
    
    print("\n正在查找图片文件...")
    for idx, item in enumerate(data, 1):
        if 'path' not in item:
            continue

        img_path = item['path']
        
        # 查找图片文件
        img_abs_path = find_image_by_path(img_path, image_index, base_path)
        
        if not img_abs_path:
            not_found_items.append(img_path)
            if debug:
                print(f"  未找到: {img_path}")
            continue
        
        if debug and idx <= 5:
            print(f"  找到: {img_path} -> {img_abs_path}")
        
        # 按目录分组
        output_dir = os.path.dirname(img_abs_path)
        if output_dir not in dir_items:
            dir_items[output_dir] = []
        
        dir_items[output_dir].append({
            'item': item,
            'img_abs_path': img_abs_path
        })
    
    if not_found_items:
        print(f"\n警告: 有 {len(not_found_items)} 个图片未找到")
        if len(not_found_items) <= 20:
            for nf in not_found_items:
                print(f"  - {nf}")
        else:
            for nf in not_found_items[:20]:
                print(f"  - {nf}")
            print(f"  ... 还有 {len(not_found_items) - 20} 个")
        
        # 建议可能的原因
        print(f"\n可能的原因:")
        print(f"  1. 图片文件不存在于 {base_path} 目录下")
        print(f"  2. 图片文件名大小写不匹配")
        print(f"  3. 图片路径结构与标注文件中的路径不一致")
    
    print(f"\n开始处理 {len(dir_items)} 个目录...\n")
    
    # 按目录处理
    total_success = 0
    total_failed = 0
    total_skipped = 0  # 跳过的无标注图片
    
    for dir_path in sorted(dir_items.keys()):
        items = dir_items[dir_path]
        success_count = 0
        failed_count = 0
        skipped_count = 0  # 当前目录跳过的数量
        
        for data_item in items:
            item = data_item['item']
            img_abs_path = data_item['img_abs_path']
            
            try:
                # 获取图片尺寸
                with Image.open(img_abs_path) as img:
                    img_width, img_height = img.size
                
                # 构建shapes
                shapes = []
                bboxes = item.get('bbox', [])
                labels = item.get('label', [])
                
                # 确保bbox和label数量匹配
                min_len = min(len(bboxes), len(labels))
                for i in range(min_len):
                    bbox = bboxes[i]
                    label = labels[i]
                    
                    # 转换bbox格式
                    if len(bbox) == 4:  # [x, y, width, height] 格式
                        points = convert_bbox_format(bbox)
                    elif len(bbox) == 2:  # [[x1, y1], [x2, y2]] 格式
                        points = bbox
                    else:
                        continue
                    
                    shape = {
                        "label": label,
                        "line_color": None,
                        "fill_color": None,
                        "points": points,
                        "shape_type": "rectangle",
                        "flags": {}
                    }
                    shapes.append(shape)
                
                # 如果shapes为空，跳过该图片，不生成JSON文件
                if not shapes:
                    skipped_count += 1
                    if debug:
                        print(f"  跳过（无标注）: {os.path.basename(img_abs_path)}")
                    continue
                
                # 构建输出JSON结构
                output_json = {
                    "version": "4.5.7",
                    "flags": {},
                    "shapes": shapes,
                    "imagePath": os.path.basename(img_abs_path),
                    "imageData": None,
                    "imageHeight": img_height,
                    "imageWidth": img_width
                }
                
                # 生成输出路径（与图片同目录）
                output_filename = os.path.splitext(os.path.basename(img_abs_path))[0] + '.json'
                output_path = os.path.join(dir_path, output_filename)
                
                # 写入JSON文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output_json, f, indent=4, ensure_ascii=False)
                
                success_count += 1
                
            except Exception as e:
                failed_count += 1
                if debug:
                    print(f"  处理失败: {img_abs_path}, 错误: {e}")
        
        # 实时输出每个目录的处理结果
        try:
            rel_path = os.path.relpath(dir_path, base_path)
        except:
            rel_path = dir_path
        
        if success_count > 0:
            print(f"✓ {rel_path} 目录处理转换完成 (成功: {success_count} 个)")
        if skipped_count > 0:
            print(f"  ○ {rel_path} 目录跳过 {skipped_count} 个无标注图片")
        if failed_count > 0:
            print(f"✗ {rel_path} 目录有 {failed_count} 个文件处理失败")
        
        total_success += success_count
        total_failed += failed_count
        total_skipped += skipped_count
    
    print(f"\n{'='*60}")
    print(f"{os.path.basename(annotation_file)} 处理完成")
    print(f"总计 - 成功: {total_success} 个, 跳过: {total_skipped} 个, 失败: {total_failed} 个, 未找到: {len(not_found_items)} 个")
    print(f"{'='*60}")


def main():
    """
    主函数，获取用户输入并执行转换
    """
    print("=" * 60)
    print("Val/Train JSON 转 Labelme JSON 格式转换工具")
    print("=" * 60)
    
    # 获取输入目录
    input_dir = input("\n请输入目录路径: ").strip()

    # 检查路径是否存在
    if not os.path.exists(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        return

    # 获取标注文件目录
    annotations_dir = input("请输入标注文件所在目录路径（如: annotations/annotations）: ").strip()
    
    # 如果输入的是相对路径，则拼接到input_dir
    if not os.path.isabs(annotations_dir):
        annotations_dir = os.path.join(input_dir, annotations_dir)

    if not os.path.exists(annotations_dir):
        print(f"错误: 标注目录不存在: {annotations_dir}")
        return

    # 询问是否开启调试模式
    debug_input = input("是否开启调试模式？(y/n，默认n): ").strip().lower()
    debug = debug_input == 'y'
    
    if debug:
        print("\n[调试模式已开启，将显示详细处理信息]")

    print(f"\n开始遍历处理目录: {input_dir}")
    
    # 处理val.json和train.json
    annotation_files = ['val.json', 'train.json']

    for ann_file in annotation_files:
        ann_file_path = os.path.join(annotations_dir, ann_file)
        if os.path.exists(ann_file_path):
            process_annotation_file(ann_file_path, input_dir, input_dir, debug)
        else:
            print(f"警告: 标注文件不存在: {ann_file_path}")

    print("\n" + "=" * 60)
    print("所有转换任务完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()