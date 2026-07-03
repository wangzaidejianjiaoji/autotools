import os
import sys
import json
import shutil
import time
import argparse

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path = [p for p in sys.path if 'hermes-agent' not in p]

import fiftyone as fo
from PIL import Image, ImageDraw

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_fiftyone_data")


def create_test_data():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)

    sub1 = os.path.join(TEST_DIR, "subset1")
    sub2 = os.path.join(TEST_DIR, "subset2")
    os.makedirs(sub1, exist_ok=True)
    os.makedirs(sub2, exist_ok=True)

    for i, sub_dir in enumerate([sub1, sub2], 1):
        for j in range(1, 4):
            img_name = f"img_{i}_{j}.jpg"
            img_path = os.path.join(sub_dir, img_name)

            img = Image.new('RGB', (640, 480), color=(i*60, i*50, i*40))
            draw = ImageDraw.Draw(img)
            draw.rectangle([50*j, 50*j, 50*j+100, 50*j+80], outline=(255, 0, 0), width=3)
            img.save(img_path, quality=85)

            labelme_data = {
                "version": "4.5.7",
                "flags": {},
                "shapes": [
                    {
                        "label": "drone",
                        "points": [
                            [50.0 * j, 50.0 * j],
                            [50.0 * j + 100.0, 50.0 * j + 80.0]
                        ],
                        "shape_type": "rectangle",
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

    return TEST_DIR


def build_dataset():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import FiftyOne as fo_module

    test_dir = create_test_data()
    sub_datasets = fo_module.discover_sub_datasets(test_dir)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dataset = fo.Dataset(f"variant_test_{timestamp}")

    for image_dir, labelme_dir, labels_path in sub_datasets:
        labels_data = fo_module.convert_labelme_dir_to_fiftyone(labelme_dir, labels_path)
        sub_dataset = fo.Dataset.from_dir(
            dataset_type=fo.types.ImageDirectory,
            dataset_dir=image_dir,
        )
        if labels_data:
            fo_module.load_labels_and_attach(sub_dataset, labels_data)
        for sample in sub_dataset:
            dataset.add_sample(sample)

    print(f"Dataset: {dataset.name}, samples: {len(dataset)}")
    return dataset


def launch_with_config(dataset, use_patches, grid_zoom, port):
    fo.config.default_app_port = port
    fo.config.auto_open_browser = False

    if grid_zoom is not None:
        print(f"Setting grid_zoom = {grid_zoom}")
        fo.app_config.grid_zoom = grid_zoom

    if use_patches and "ground_truth" in dataset.get_field_schema():
        view = dataset.to_patches("ground_truth")
        print(f"Using to_patches view, patches: {len(view)}")
        session = fo.launch_app(view=view, port=port, auto=False)
    else:
        print("Using dataset view")
        session = fo.launch_app(dataset, port=port, auto=False)

    print(f"App launched at http://localhost:{port}")
    return session


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--patches", action="store_true", help="Use to_patches view")
    parser.add_argument("--zoom", type=int, default=None, help="grid_zoom value")
    parser.add_argument("--port", type=int, default=8080, help="Port")
    args = parser.parse_args()

    dataset = build_dataset()
    session = launch_with_config(dataset, args.patches, args.zoom, args.port)

    print("服务运行中，按 Ctrl+C 停止...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n服务已停止")
