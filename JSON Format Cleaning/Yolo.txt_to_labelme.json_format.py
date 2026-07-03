import os
import json
import glob
from pathlib import Path
from PIL import Image
import re


def yolo_to_labelme_shapes(yolo_format, img_width, img_height):
    """
    将YOLO格式转换为Labelme格式的shapes
    YOLO格式: class_id x_center y_center width height (归一化坐标)
    Labelme格式: shapes列表，每个shape包含points(左上角和右下角坐标)
    """
    shapes = []

    for line in yolo_format.strip().split('\n'):
        if not line.strip():
            continue

        parts = line.strip().split()
        if len(parts) < 5:
            continue

        class_id = int(parts[0])
        x_center = float(parts[1])
        y_center = float(parts[2])
        width = float(parts[3])
        height = float(parts[4])

        # 将归一化坐标转换为绝对像素坐标
        x_center_abs = x_center * img_width
        y_center_abs = y_center * img_height
        width_abs = width * img_width
        height_abs = height * img_height

        # 计算左上角和右下角坐标
        x1 = x_center_abs - (width_abs / 2)
        y1 = y_center_abs - (height_abs / 2)
        x2 = x1 + width_abs
        y2 = y1 + height_abs

        # 转换为整数并确保在图像范围内
        x1 = max(0, int(x1))
        y1 = max(0, int(y1))
        x2 = min(img_width, int(x2))
        y2 = min(img_height, int(y2))

        # 创建shape字典
        shape = {
            "label": "bird",  # 固定为bird
            "line_color": None,
            "fill_color": None,
            "points": [
                [float(x1), float(y1)],  # 左上角坐标
                [float(x2), float(y2)]  # 右下角坐标
            ],
            "shape_type": "rectangle",
            "flags": {}
        }

        shapes.append(shape)

    return shapes


def find_image_file(image_dir, txt_filename):
    """
    在图片目录中查找对应的图片文件
    支持常见的图片格式
    """
    base_name = os.path.splitext(txt_filename)[0]

    # 常见的图片格式
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.JPG', '.JPEG', '.PNG']

    for ext in image_extensions:
        # 尝试直接匹配
        image_path = os.path.join(image_dir, base_name + ext)
        if os.path.exists(image_path):
            return image_path, os.path.basename(image_path)

        # 尝试不区分大小写匹配
        for file in os.listdir(image_dir):
            file_lower = file.lower()
            base_name_lower = base_name.lower()
            if file_lower.startswith(base_name_lower) and any(
                    file_lower.endswith(ext.lower()) for ext in image_extensions):
                return os.path.join(image_dir, file), file

    return None, None


def get_image_dimensions(image_path):
    """
    获取图片的宽度和高度
    """
    try:
        with Image.open(image_path) as img:
            return img.size  # 返回 (width, height)
    except Exception as e:
        print(f"无法读取图片尺寸: {image_path}, 错误: {e}")
        return None


def find_all_txt_files(root_dir):
    """
    递归查找所有txt文件
    """
    txt_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_files.append(os.path.join(root, file))
    return txt_files


def get_corresponding_images_dir(txt_path, input_dir):
    """
    根据txt文件路径获取对应的图片目录
    规则：将路径中的"labels"替换为"images"
    """
    # 将路径标准化
    txt_path = os.path.normpath(txt_path)
    input_dir = os.path.normpath(input_dir)

    # 获取txt文件相对于输入目录的相对路径
    rel_path = os.path.relpath(os.path.dirname(txt_path), input_dir)

    # 将路径中的"labels"替换为"images"
    images_rel_path = rel_path.replace("labels", "images")

    # 构建完整的图片目录路径
    images_dir = os.path.join(input_dir, images_rel_path)

    return images_dir


def convert_yolo_to_labelme(input_dir):
    """
    主转换函数
    """
    # 递归查找所有txt文件
    txt_files = find_all_txt_files(input_dir)

    if not txt_files:
        print(f"在 {input_dir} 及其子文件夹中未找到.txt文件")
        return

    print(f"找到 {len(txt_files)} 个txt文件")

    # 处理每个txt文件
    for txt_file in txt_files:
        try:
            # 读取YOLO格式文件
            with open(txt_file, 'r', encoding='utf-8') as f:
                yolo_content = f.read()

            # 获取txt文件名（不含扩展名）
            txt_filename = os.path.basename(txt_file)

            # 获取对应的图片目录
            images_dir = get_corresponding_images_dir(txt_file, input_dir)

            # 检查images文件夹是否存在
            if not os.path.exists(images_dir):
                print(f"警告: 对应的images文件夹不存在: {images_dir}")
                # 尝试另一种模式：在images目录下创建同名子目录
                images_dir_alt = os.path.join(images_dir, os.path.basename(images_dir))
                if os.path.exists(images_dir_alt):
                    images_dir = images_dir_alt
                    print(f"使用替代路径: {images_dir}")
                else:
                    continue

            # 查找对应的图片文件
            image_path, image_filename = find_image_file(images_dir, txt_filename)

            if not image_path or not image_filename:
                print(f"警告: 在 {images_dir} 中未找到 {txt_filename} 对应的图片文件")
                continue

            # 获取图片尺寸
            img_dimensions = get_image_dimensions(image_path)
            if not img_dimensions:
                print(f"警告: 无法获取图片尺寸: {image_path}")
                continue

            img_width, img_height = img_dimensions

            # 转换YOLO格式到Labelme格式的shapes
            shapes = yolo_to_labelme_shapes(yolo_content, img_width, img_height)

            # 如果没有任何标注框，跳过该文件或创建空的shapes列表
            if not shapes:
                print(f"提示: {txt_filename} 中没有标注框")

            # 构建Labelme格式的JSON数据
            labelme_data = {
                "version": "4.5.7",
                "flags": {},
                "shapes": shapes,
                "imagePath": image_filename,  # 仅文件名，不是完整路径
                "imageData": None,
                "imageHeight": img_height,
                "imageWidth": img_width
            }

            # 生成JSON文件名（与txt文件同名，但扩展名为.json）
            json_filename = os.path.splitext(txt_filename)[0] + ".json"
            json_path = os.path.join(images_dir, json_filename)

            # 确保目录存在
            os.makedirs(os.path.dirname(json_path), exist_ok=True)

            # 保存JSON文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(labelme_data, f, indent=4, ensure_ascii=False)

            print(f"已转换: {txt_filename} -> {json_filename}")

        except Exception as e:
            print(f"转换文件 {txt_file} 时出错: {e}")
            import traceback
            traceback.print_exc()

    print("转换完成!")


def main():
    """
    主函数，获取用户输入并执行转换
    """
    # 获取输入目录
    input_dir = input("请输入目录路径： ").strip()

    # 检查目录是否存在
    if not os.path.exists(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        return

    # 执行转换
    convert_yolo_to_labelme(input_dir)


if __name__ == "__main__":
    # 如果需要直接运行而不需要输入，可以取消下面的注释并修改目录路径
    # input_dir = r"D:\桌面\历正\算法\数据集\下载的数据集1\text"
    # convert_yolo_to_labelme(input_dir)

    main()