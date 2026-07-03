import os
import shutil
import py7zr
import cv2
import numpy as np
from collections import defaultdict


def extract_7z_file(file_path, extract_to=None):
    """解压 7z 文件"""
    try:
        if extract_to is None:
            extract_to = os.path.splitext(file_path)[0]
        if os.path.exists(extract_to):
            print(f"文件夹已存在，跳过：{extract_to}")
            return extract_to
        os.makedirs(extract_to, exist_ok=True)
        with py7zr.SevenZipFile(file_path, mode='r') as archive:
            archive.extractall(path=extract_to)
        print(f"✓ 解压：{os.path.basename(file_path)} -> {os.path.basename(extract_to)}")
        return extract_to
    except Exception as e:
        print(f"✗ 解压失败 {file_path}: {e}")
        return None


def find_ping_or_pong_dir(extracted_dir):
    """在解压目录中查找 ping 或 pong 子目录"""
    for item in os.listdir(extracted_dir):
        item_path = os.path.join(extracted_dir, item)
        if os.path.isdir(item_path) and item.lower() in ['ping', 'pong']:
            return item_path
    return extracted_dir


def extract_timestamp(filename):
    """从文件名提取时间戳"""
    import re
    match = re.match(r'^(\d{8}_\d{2}-\d{2}-\d{2})\.?(\d+)?', filename)
    if match:
        base_ts = match.group(1)
        ms = match.group(2) or "0"
        return f"{base_ts}.{ms.ljust(4, '0')[:4]}", base_ts
    return None, None


def compute_histogram_fast(image_path, size=(112, 112), bins=16):
    """
    快速计算图片直方图特征（HSV 色彩空间）
    返回：归一化的直方图向量
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None

        # 缩小图片加速处理
        img_small = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(img_small, cv2.COLOR_BGR2HSV)

        # 计算直方图（减少 bins 加速）
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [bins, bins, bins],
                            [0, 180, 0, 256, 0, 256])
        cv2.normalize(hist, hist)

        return hist.flatten()
    except Exception as e:
        return None


def compute_similarity_fast(hist1, hist2):
    """快速计算两个直方图的相似度"""
    if hist1 is None or hist2 is None:
        return 0.0
    similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    return max(0, similarity)


def collect_multi_frame_files(source_dirs, output_dir, max_frames_per_group=5, similarity_threshold=0.70):
    """
    快速直方图版本
    1. 预计算所有 JPG 的直方图特征
    2. 每个 JSON 找同名 JPG 作为参考
    3. 用直方图相似度找最相似的 4 张图
    4. JPG 不重复分配
    """
    all_json_files = []
    all_jpg_files = []

    # 步骤 1: 扫描所有文件
    for source_dir in source_dirs:
        print(f"\n 扫描目录：{source_dir}")
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_lower = file.lower()
                file_path = os.path.join(root, file)
                if file_lower.endswith('.json'):
                    all_json_files.append(file_path)
                elif file_lower.endswith('.jpg'):
                    all_jpg_files.append(file_path)

    print(f"\n 扫描完成：{len(all_json_files)} 个 JSON, {len(all_jpg_files)} 张 JPG")

    # 步骤 2: 预计算所有 JPG 的直方图特征（批量处理，速度快）
    print("  预计算直方图特征...")
    jpg_info_list = []
    for i, jpg_path in enumerate(all_jpg_files):
        jpg_name = os.path.basename(jpg_path)
        full_ts, base_ts = extract_timestamp(jpg_name)
        hist = compute_histogram_fast(jpg_path)

        if hist is not None:
            jpg_info_list.append({
                'path': jpg_path,
                'name': jpg_name,
                'full_ts': full_ts,
                'base_ts': base_ts,
                'hist': hist,
                'assigned': False
            })

        if (i + 1) % 50 == 0:
            print(f"    已处理 {i + 1}/{len(all_jpg_files)} 张...")

    print(f"  有效 JPG: {len(jpg_info_list)} 张")

    # 步骤 3: 预处理 JSON 信息并排序
    json_info_list = []
    for json_path in all_json_files:
        json_name = os.path.basename(json_path)
        full_ts, base_ts = extract_timestamp(json_name)
        if base_ts:
            json_info_list.append({
                'path': json_path,
                'name': json_name,
                'full_ts': full_ts,
                'base_ts': base_ts
            })

    json_info_list.sort(key=lambda x: (x['base_ts'], x['full_ts'] or ''))
    print(f"  有效 JSON: {len(json_info_list)} 个（已按时间排序）")

    # 步骤 4: 为每个 JSON 匹配相似 JPG
    print(f"\n 匹配：每个 JSON 找 {max_frames_per_group} 张相似 JPG（阈值={similarity_threshold}）...")
    matched_pairs = []
    json_without_jpg = []

    for json_info in json_info_list:
        json_path = json_info['path']
        json_name = json_info['name']
        json_base_ts = json_info['base_ts']

        # 找到同名的 JPG 作为参考图
        reference_jpg = None
        json_base_name = os.path.splitext(json_name)[0]

        # 去除后缀找同名 JPG
        for suffix in ['_speckle', '_drone', '_narrow_capture', '_wide_capture']:
            if json_base_name.endswith(suffix):
                json_base_name = json_base_name[:-len(suffix)]
                break

        # 先找完全同名
        for jpg_info in jpg_info_list:
            expected_name = json_base_name + '.jpg'
            if jpg_info['name'] == expected_name and not jpg_info['assigned']:
                reference_jpg = jpg_info
                break

        # 再找带后缀的
        if not reference_jpg:
            for suffix in ['_narrow_capture', '_speckle', '_drone', '_wide_capture']:
                for jpg_info in jpg_info_list:
                    expected_name = json_base_name + suffix + '.jpg'
                    if jpg_info['name'] == expected_name and not jpg_info['assigned']:
                        reference_jpg = jpg_info
                        break
                if reference_jpg:
                    break

        # 最后找同时间戳的任意 JPG
        if not reference_jpg:
            for jpg_info in jpg_info_list:
                if jpg_info['base_ts'] == json_base_ts and not jpg_info['assigned']:
                    reference_jpg = jpg_info
                    break

        if not reference_jpg:
            json_without_jpg.append(json_name)
            continue

        # 找最相似的 4 张图（使用预计算的直方图）
        similarities = []
        ref_hist = reference_jpg['hist']

        for jpg_info in jpg_info_list:
            if jpg_info['assigned'] or jpg_info['path'] == reference_jpg['path']:
                continue

            sim = compute_similarity_fast(ref_hist, jpg_info['hist'])
            if sim >= similarity_threshold:
                similarities.append({
                    'jpg_info': jpg_info,
                    'similarity': sim
                })

        # 按相似度排序
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        selected = [item['jpg_info'] for item in similarities[:max_frames_per_group - 1]]

        # 合并参考图和相似图
        all_selected = [reference_jpg] + selected

        if len(all_selected) < 2:
            json_without_jpg.append(json_name)
            continue

        # 标记为已分配
        for jpg_info in all_selected:
            jpg_info['assigned'] = True

        matched_pairs.append({
            'json_path': json_path,
            'json_name': json_name,
            'jpg_paths': [j['path'] for j in all_selected],
            'selected_count': len(all_selected)
        })

        print(f"  ✓ {json_name}: {len(all_selected)} 张")

    # 步骤 5: 复制到输出目录
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n 输出目录：{output_dir}")

    copied_jpg = 0
    copied_json = 0

    for pair in matched_pairs:
        json_path = pair['json_path']
        jpg_paths = pair['jpg_paths']

        # 复制 JSON
        json_name = os.path.basename(json_path)
        dst_json = os.path.join(output_dir, json_name)
        if os.path.exists(dst_json):
            base, ext = os.path.splitext(json_name)
            counter = 1
            while os.path.exists(dst_json):
                dst_json = os.path.join(output_dir, f"{base}_{counter}{ext}")
                counter += 1
        try:
            shutil.copy2(json_path, dst_json)
            copied_json += 1
        except Exception as e:
            continue

        # 复制 JPG
        for jpg_path in jpg_paths:
            jpg_name = os.path.basename(jpg_path)
            dst_jpg = os.path.join(output_dir, jpg_name)
            if os.path.exists(dst_jpg):
                base, ext = os.path.splitext(jpg_name)
                counter = 1
                while os.path.exists(dst_jpg):
                    dst_jpg = os.path.join(output_dir, f"{base}_{counter}{ext}")
                    counter += 1
            try:
                shutil.copy2(jpg_path, dst_jpg)
                copied_jpg += 1
            except Exception as e:
                continue

    unassigned_jpg = sum(1 for j in jpg_info_list if not j['assigned'])

    return copied_jpg, copied_json, len(matched_pairs), unassigned_jpg, len(json_without_jpg)


def main():
    print("=" * 60)
    print("多帧图片提取工具 v10 (快速直方图版)")
    print("=" * 60)
    print("功能：预计算直方图特征，速度提升 5-10 倍")
    print("=" * 60)

    target_dir = input("\n请输入 7z 文件所在目录路径：").strip().strip('"').strip("'")
    output_dir = input("请输入输出目录路径（默认 D:\\multi-frame_test_set）：").strip().strip('"').strip("'")

    if not output_dir:
        output_dir = r"D:\multi-frame_test_set"

    if not os.path.exists(target_dir):
        print(f"错误：目录 '{target_dir}' 不存在")
        return

    print(f"\n 输入目录：{target_dir}")
    print(f" 输出目录：{output_dir}")

    threshold_input = input("请输入相似度阈值（默认 0.70，范围 0.5-0.90）：").strip()
    try:
        similarity_threshold = float(threshold_input) if threshold_input else 0.70
        similarity_threshold = max(0.5, min(0.90, similarity_threshold))
    except:
        similarity_threshold = 0.70
    print(f"  使用相似度阈值：{similarity_threshold}")

    # 步骤 1: 查找 7z 文件
    print("\n" + "=" * 60)
    print("步骤 1: 查找 7z 文件")
    print("=" * 60)

    seven_z_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.7z')]
    print(f" 找到 {len(seven_z_files)} 个 7z 文件")

    if not seven_z_files:
        print(" 没有找到 7z 文件")
        return

    # 步骤 2: 解压
    print("\n" + "=" * 60)
    print("步骤 2: 解压 7z 文件")
    print("=" * 60)

    extracted_dirs = []
    for seven_z_file in seven_z_files:
        file_path = os.path.join(target_dir, seven_z_file)
        extracted_path = extract_7z_file(file_path)
        if extracted_path:
            extracted_dirs.append(extracted_path)

    print(f"\n 共解压 {len(extracted_dirs)} 个文件")

    # 步骤 3: 查找 ping/pong
    print("\n" + "=" * 60)
    print("步骤 3: 查找 ping/pong 子目录")
    print("=" * 60)

    source_dirs = []
    for extracted_dir in extracted_dirs:
        ping_pong_dir = find_ping_or_pong_dir(extracted_dir)
        source_dirs.append(ping_pong_dir)
        print(f"  {os.path.basename(extracted_dir)} -> {os.path.basename(ping_pong_dir)}")

    # 步骤 4: 快速匹配并复制
    print("\n" + "=" * 60)
    print("步骤 4: 直方图相似度匹配")
    print("=" * 60)

    max_frames_input = input("请输入每组最大帧数（默认 5）：").strip()
    max_frames = int(max_frames_input) if max_frames_input else 5

    copied_jpg, copied_json, matched_count, unassigned_jpg, orphan_json = collect_multi_frame_files(
        source_dirs, output_dir, max_frames, similarity_threshold
    )

    # 最终统计
    print("\n" + "=" * 60)
    print("操作完成!")
    print("=" * 60)
    print(f" 解压的 7z 文件数：{len(seven_z_files)}")
    print(f" 成功匹配的组数：{matched_count} 组")
    print(f" 复制的 JPG 数量：{copied_jpg}")
    print(f" 复制的 JSON 数量：{copied_json}")
    print(f" 未分配的 JPG 数量：{unassigned_jpg}")
    print(f" 孤立的 JSON 数量：{orphan_json}")
    print(f" 输出目录：{output_dir}")
    print(f"\n 源文件已保留（未删除）")


if __name__ == "__main__":
    main()