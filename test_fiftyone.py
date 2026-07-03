import os
import sys
import json
import shutil
import time
import threading
from pathlib import Path

# 修复 Windows 下子进程继承外部虚拟环境 PATH 导致 protobuf 版本冲突的问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path = [p for p in sys.path if 'hermes-agent' not in p]

import fiftyone as fo
from PIL import Image, ImageDraw

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_fiftyone_data")


def create_test_data():
    """创建测试数据集：图片 + labelme JSON。"""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)

    # 创建子目录结构
    sub1 = os.path.join(TEST_DIR, "subset1")
    sub2 = os.path.join(TEST_DIR, "subset2")
    os.makedirs(sub1, exist_ok=True)
    os.makedirs(sub2, exist_ok=True)

    for i, sub_dir in enumerate([sub1, sub2], 1):
        for j in range(1, 4):
            img_name = f"img_{i}_{j}.jpg"
            img_path = os.path.join(sub_dir, img_name)

            # 创建 640x480 测试图片
            img = Image.new('RGB', (640, 480), color=(i*60, i*50, i*40))
            draw = ImageDraw.Draw(img)
            draw.rectangle([50*j, 50*j, 50*j+100, 50*j+80], outline=(255, 0, 0), width=3)
            img.save(img_path, quality=85)

            # 创建 labelme JSON
            labelme_data = {
                "version": "4.5.7",
                "flags": {},
                "shapes": [
                    {
                        "label": "drone",
                        "line_color": None,
                        "fill_color": None,
                        "points": [
                            [50.0 * j, 50.0 * j],
                            [50.0 * j + 100.0, 50.0 * j + 80.0]
                        ],
                        "shape_type": "rectangle",
                        "flags": {}
                    }
                ],
                "imagePath": img_name,
                "imageData": None,
                "imageHeight": 480,
                "imageWidth": 640
            }
            json_path = os.path.join(sub_dir, f"{img_name}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(labelme_data, f, indent=2, ensure_ascii=False)

    print(f"测试数据已创建: {TEST_DIR}")
    return TEST_DIR


def test_launch():
    """测试 FiftyOne 启动。"""
    test_dir = create_test_data()

    # 导入 FiftyOne.py 中的函数
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import FiftyOne as fo_module

    sub_datasets = fo_module.discover_sub_datasets(test_dir)
    print(f"探测到 {len(sub_datasets)} 个子数据集")
    for image_dir, labelme_dir, labels_path in sub_datasets:
        print(f"  图片: {image_dir}, 标注: {labelme_dir}, 输出: {labels_path}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dataset_name = f"test_merged_dataset_{timestamp}"
    dataset = fo.Dataset(dataset_name)

    for i, (image_dir, labelme_dir, labels_path) in enumerate(sub_datasets, 1):
        print(f"\n[{i}/{len(sub_datasets)}] 处理: {image_dir}")
        labels_data = fo_module.convert_labelme_dir_to_fiftyone(labelme_dir, labels_path)

        sub_dataset = fo.Dataset.from_dir(
            dataset_type=fo.types.ImageDirectory,
            dataset_dir=image_dir,
        )

        if labels_data:
            fo_module.load_labels_and_attach(sub_dataset, labels_data)

        for sample in sub_dataset:
            dataset.add_sample(sample)

    print(f"\n总样本数: {len(dataset)}")
    print(f"字段: {dataset.get_field_schema()}")

    # 启动 FiftyOne
    session = fo_module.launch_fiftyone(dataset, port=8080)
    return session


if __name__ == "__main__":
    session = test_launch()
    if session:
        print("服务运行中，按 Ctrl+C 停止...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n服务已停止")
