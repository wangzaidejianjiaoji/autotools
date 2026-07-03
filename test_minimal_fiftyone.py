import os
import sys
import time

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path = [p for p in sys.path if 'hermes-agent' not in p]

import fiftyone as fo
from PIL import Image, ImageDraw


def create_test_image(path):
    img = Image.new('RGB', (640, 480), color=(100, 150, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 130], outline=(255, 0, 0), width=3)
    img.save(path)


def main():
    test_dir = os.path.join(os.path.dirname(__file__), "test_minimal_data")
    os.makedirs(test_dir, exist_ok=True)

    img_path = os.path.join(test_dir, "test.jpg")
    create_test_image(img_path)

    dataset = fo.Dataset("minimal_test")
    sample = fo.Sample(filepath=img_path)
    sample["ground_truth"] = fo.Detections(detections=[
        fo.Detection(label="drone", bounding_box=[0.1, 0.1, 0.2, 0.2])
    ])
    dataset.add_sample(sample)

    print(f"Dataset: {dataset.name}, samples: {len(dataset)}")
    print(f"Fields: {list(dataset.get_field_schema().keys())}")

    fo.config.default_app_port = 8080
    fo.config.auto_open_browser = False

    print("Launching app...")
    session = fo.launch_app(dataset, port=8080, auto=False)
    print(f"App launched at http://localhost:8080")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
