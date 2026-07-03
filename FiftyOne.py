import os
import sys
import json
import glob
import time
import threading
from pathlib import Path

# 修复 Windows 下子进程继承外部虚拟环境 PATH 导致 protobuf 版本冲突的问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path = [p for p in sys.path if 'hermes-agent' not in p]

import psutil
import fiftyone as fo

fo.config.show_progress_bars = True


def kill_processes_on_port(port):
    """终止所有占用指定端口的进程（排除当前进程），避免端口冲突。"""
    current_pid = os.getpid()
    killed = []
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port and conn.pid and conn.pid != current_pid:
            try:
                proc = psutil.Process(conn.pid)
                proc_name = proc.name()
                proc.terminate()
                proc.wait(timeout=5)
                killed.append((conn.pid, proc_name))
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                try:
                    proc.kill()
                    killed.append((conn.pid, proc.name()))
                except Exception:
                    pass
    if killed:
        print(f"  已清理占用端口 {port} 的进程: {killed}")
    else:
        print(f"  端口 {port} 未被占用")


def convert_labelme_to_fiftyone(labelme_json_path):
    """将单个 labelme 格式的 JSON 转换为 FiftyOne 的标注格式。"""
    with open(labelme_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    image_path = data.get('imagePath', '')
    image_filename = os.path.basename(image_path)
    image_width = data.get('imageWidth', 1)
    image_height = data.get('imageHeight', 1)

    if image_width <= 0 or image_height <= 0:
        print(f"  警告：{labelme_json_path} 图片尺寸异常，跳过")
        return None

    detections = []
    for shape in data.get('shapes', []):
        if shape.get('shape_type') == 'rectangle':
            points = shape['points']
            x1, y1 = points[0]
            x2, y2 = points[1]

            x_min = min(x1, x2)
            y_min = min(y1, y2)
            x_max = max(x1, x2)
            y_max = max(y1, y2)

            width = max(x_max - x_min, 0)
            height = max(y_max - y_min, 0)

            if width == 0 or height == 0:
                continue

            x_min_norm = x_min / image_width
            y_min_norm = y_min / image_height
            norm_width = width / image_width
            norm_height = height / image_height

            detections.append({
                "label": shape.get('label', 'unknown'),
                "bounding_box": [x_min_norm, y_min_norm, norm_width, norm_height]
            })

    return {
        image_filename: {
            "ground_truth": {
                "detections": detections
            }
        }
    }


def convert_labelme_dir_to_fiftyone(labelme_dir, output_json_path=None):
    """批量转换目录下的 labelme JSON 文件为 FiftyOne labels.json。"""
    json_files = glob.glob(os.path.join(labelme_dir, '*.json'))
    # 排除自动生成的 fiftyone_labels.json，避免自我转换污染
    json_files = [f for f in json_files if os.path.basename(f).lower() != 'fiftyone_labels.json']
    if not json_files:
        print(f"  警告：在 {labelme_dir} 中未找到任何 .json 文件")
        return None

    result = {}
    for json_file in json_files:
        try:
            converted = convert_labelme_to_fiftyone(json_file)
            if converted:
                result.update(converted)
                print(f"  已转换: {os.path.basename(json_file)}")
        except Exception as e:
            print(f"  转换失败 {os.path.basename(json_file)}: {str(e)}")

    if not result:
        return None

    if output_json_path:
        output_dir = os.path.dirname(output_json_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  已保存转换结果: {output_json_path}")

    return result


def find_image_dir(base_dir, max_depth=3):
    """在目录中查找包含最多图片文件的子目录，限制递归深度。"""
    image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
    best_dir = None
    best_count = 0

    base_depth = base_dir.count(os.sep)
    for root, dirs, files in os.walk(base_dir):
        if root.count(os.sep) - base_depth > max_depth:
            del dirs[:]
            continue
        count = sum(1 for f in files if Path(f).suffix.lower() in image_exts)
        if count > best_count:
            best_count = count
            best_dir = root

    return best_dir


def discover_sub_datasets(input_path, max_depth=3):
    """自动探测输入路径下的所有子数据集（图片目录 + labelme JSON 目录）。"""
    input_path = os.path.abspath(input_path)

    if not os.path.isdir(input_path):
        if os.path.isfile(input_path) and input_path.lower().endswith('.json'):
            return [(os.path.dirname(input_path), None, input_path)]
        else:
            print(f"错误：输入路径不存在或不是有效的目录/JSON 文件 - {input_path}")
            return []

    image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
    base_depth = input_path.count(os.sep)
    sub_datasets = []

    for root, dirs, files in os.walk(input_path):
        if root.count(os.sep) - base_depth > max_depth:
            del dirs[:]
            continue

        # 排除自动生成的 fiftyone_labels.json
        json_files = [f for f in files if f.lower().endswith('.json') and f.lower() != 'fiftyone_labels.json']
        image_files = [f for f in files if Path(f).suffix.lower() in image_exts]

        if not json_files:
            continue

        # 此目录即为 labelme 标注目录
        labelme_dir = root

        # 优先选择 labelme 目录同级的图片目录，否则在 labelme 目录内查找图片
        image_dir = None
        parent_dir = os.path.dirname(labelme_dir)
        if parent_dir and parent_dir != input_path:
            sibling_images = [f for f in os.listdir(parent_dir)
                              if Path(f).suffix.lower() in image_exts
                              and os.path.isfile(os.path.join(parent_dir, f))]
            if sibling_images:
                image_dir = parent_dir

        if image_dir is None:
            if image_files:
                image_dir = labelme_dir
            else:
                image_dir = find_image_dir(labelme_dir, max_depth=2)

        if image_dir is None:
            print(f"  警告：在 {labelme_dir} 附近未找到图片文件，跳过")
            continue

        labels_path = os.path.join(labelme_dir, 'fiftyone_labels.json')
        sub_datasets.append((image_dir, labelme_dir, labels_path))

    return sub_datasets


def load_labels_and_attach(dataset, labels_data):
    """将 FiftyOne 格式标注数据附加到数据集的每个样本。"""
    match_count = 0
    miss_count = 0
    missed_files = []

    for sample in dataset:
        filename = os.path.basename(sample.filepath)
        if filename in labels_data:
            ground_truth = labels_data[filename].get('ground_truth', {})
            detections = ground_truth.get('detections', [])
            fo_detections = []
            for det in detections:
                label = det.get('label', 'unknown')
                bounding_box = det.get('bounding_box')
                if bounding_box and len(bounding_box) == 4:
                    fo_detections.append(
                        fo.Detection(
                            label=label,
                            bounding_box=bounding_box
                        )
                    )
            if fo_detections:
                sample['ground_truth'] = fo.Detections(detections=fo_detections)
                sample.save()
            match_count += 1
        else:
            miss_count += 1
            missed_files.append(filename)

    print(f"标签匹配: {match_count} 个样本, 未匹配: {miss_count} 个样本")
    if missed_files and miss_count <= 20:
        print(f"  未匹配文件: {', '.join(missed_files[:20])}")
    elif missed_files:
        print(f"  未匹配文件示例 (前20个): {', '.join(missed_files[:20])}")


def launch_fiftyone(dataset, port=8080, auto_to_patches=True):
    """启动 FiftyOne App，并可选默认以 ToPatches 视图打开、最小 zoom 显示。"""
    fo.config.default_app_port = port
    fo.config.auto_open_browser = False

    # 最小 zoom，一屏显示更多 patch/样本
    fo.app_config.grid_zoom = 0

    try:
        # 如果启用，直接用 ToPatches 视图启动，浏览器打开即显示放大图
        if auto_to_patches and "ground_truth" in dataset.get_field_schema():
            view = dataset.to_patches("ground_truth")
            session = fo.launch_app(view=view, port=port, auto=False)
            print("  已默认以 ground_truth 的 ToPatches 视图启动")
        else:
            session = fo.launch_app(dataset, port=port, auto=False)

        print(f"\nFiftyOne App 已启动！")
        print(f"请在浏览器中访问：http://localhost:{port}")
        print(f"或访问：http://{session.server_address}:{session.server_port}")

        return session
    except Exception as e:
        print(f"启动时出现错误: {e}")
        print("请尝试手动访问 http://localhost:5151")
        return None


def main():
    port = 8080

    print("=" * 60)
    print("          FiftyOne 数据集可视化工具")
    print("=" * 60)
    print("说明：输入一个目录，自动递归探测子目录下的图片和 labelme 标注文件；")
    print("      若标注为 labelme 格式，会自动转换为 FiftyOne 格式。")
    print("=" * 60)

    print(f"\n[准备] 检查并清理端口 {port} 占用...")
    kill_processes_on_port(port)

    input_path = input("\n请输入数据集目录或 labels.json 路径: ").strip().strip('"')

    if not input_path:
        print("错误：路径不能为空")
        sys.exit(1)

    sub_datasets = discover_sub_datasets(input_path)
    if not sub_datasets:
        print("错误：未找到有效的数据集")
        sys.exit(1)

    print(f"\n探测到 {len(sub_datasets)} 个子数据集：")
    for i, (image_dir, labelme_dir, labels_path) in enumerate(sub_datasets, 1):
        print(f"  [{i}] 图片目录: {image_dir}")
        if labelme_dir:
            print(f"       Labelme 标注目录: {labelme_dir}")
            print(f"       转换输出: {labels_path}")

    # 创建新数据集，使用唯一名称避免冲突
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dataset_name = f"merged_dataset_{timestamp}"
    dataset = fo.Dataset(dataset_name)

    for i, (image_dir, labelme_dir, labels_path) in enumerate(sub_datasets, 1):
        print(f"\n[{i}/{len(sub_datasets)}] 正在处理子数据集：{image_dir}")

        labels_data = None
        if labelme_dir and labels_path:
            labels_data = convert_labelme_dir_to_fiftyone(labelme_dir, labels_path)

        if labels_data is None and labels_path and os.path.exists(labels_path):
            try:
                with open(labels_path, 'r', encoding='utf-8') as f:
                    labels_data = json.load(f)
                print(f"  已读取现有标签: {labels_path}")
            except Exception as e:
                print(f"  读取标签文件失败: {e}")

        print("  正在加载图片到数据集...")
        sub_dataset = fo.Dataset.from_dir(
            dataset_type=fo.types.ImageDirectory,
            dataset_dir=image_dir,
        )

        if labels_data:
            print("  正在加载标签...")
            load_labels_and_attach(sub_dataset, labels_data)
        else:
            print("  警告：未找到可用标签，将仅显示图片")

        # 合并到总数据集
        for sample in sub_dataset:
            dataset.add_sample(sample)

        print(f"  子数据集处理完成，当前总样本数: {len(dataset)}")

    print(f"\n所有子数据集加载完成！共 {len(dataset)} 个样本")

    session = launch_fiftyone(dataset, port=port)
    if session:
        print("\n提示：在 FiftyOne 网页中，点击检测结果即可在右侧面板查看裁剪放大的局部图。")
        print("  按 Ctrl+C 或关闭终端可退出服务。")
        try:
            input("\n按 Enter 键退出...")
        except EOFError:
            print("\n检测到非交互式输入（管道），保持服务运行...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n服务已停止")


if __name__ == "__main__":
    main()
