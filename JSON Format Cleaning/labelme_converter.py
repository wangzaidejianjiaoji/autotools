import json
import os
from pathlib import Path


def labelme_to_fiftyone(labelme_path, output_path=None):
    with open(labelme_path, 'r', encoding='utf-8') as f:
        labelme_data = json.load(f)

    image_path = labelme_data.get('imagePath', 'unknown.jpg')
    image_width = labelme_data.get('imageWidth', 1)
    image_height = labelme_data.get('imageHeight', 1)
    shapes = labelme_data.get('shapes', [])

    detections = []
    for shape in shapes:
        if shape.get('shape_type') != 'rectangle':
            continue

        points = shape.get('points', [])
        if len(points) < 2:
            continue

        x1, y1 = points[0]
        x2, y2 = points[1]

        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        width = right - left
        height = bottom - top
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2

        normalized_bbox = [
            center_x / image_width,
            center_y / image_height,
            width / image_width,
            height / image_height
        ]

        detection = {
            'label': shape.get('label', 'unknown'),
            'bounding_box': normalized_bbox
        }
        detections.append(detection)

    fiftyone_data = {
        image_path: {
            'ground_truth': {
                'detections': detections
            }
        }
    }

    if output_path is None:
        output_path = labelme_path.replace('.json', '_fiftyone.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fiftyone_data, f, indent=2, ensure_ascii=False)

    return fiftyone_data


def batch_convert(input_dir, output_dir=None):
    input_path = Path(input_dir)
    if output_dir is None:
        output_dir = input_path
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for json_file in input_path.glob('*.json'):
        if 'fiftyone' in json_file.stem.lower():
            continue

        try:
            output_file = output_dir / f'{json_file.stem}_fiftyone.json'
            result = labelme_to_fiftyone(json_file, output_file)
            results.append((json_file.name, output_file.name, True, None))
        except Exception as e:
            results.append((json_file.name, None, False, str(e)))

    return results


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None

        if os.path.isdir(input_file):
            results = batch_convert(input_file, output_file)
            for inp, out, success, error in results:
                status = '✓' if success else '✗'
                print(f'{status} {inp} -> {out if out else error}')
        else:
            result = labelme_to_fiftyone(input_file, output_file)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = labelme_to_fiftyone('labelme.json', 'fiftyone_output.json')
        print(json.dumps(result, indent=2, ensure_ascii=False))
