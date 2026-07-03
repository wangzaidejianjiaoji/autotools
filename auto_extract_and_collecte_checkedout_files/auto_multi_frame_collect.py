import os
import shutil
import py7zr
import re
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
    """
    从文件名提取完整时间戳（包含毫秒）
    返回：(完整时间戳，毫秒值，秒级时间戳)
    """
    match = re.match(r'^(\d{8}_\d{2}-\d{2}-\d{2})\.(\d+)', filename)
    if match:
        base_ts = match.group(1)
        ms_str = match.group(2)
        ms_normalized = ms_str.ljust(4, '0')[:4]
        full_ts = f"{base_ts}.{ms_normalized}"
        ms_value = int(ms_normalized)
        return full_ts, ms_value, base_ts

    match = re.match(r'^(\d{8}_\d{2}-\d{2}-\d{2})', filename)
    if match:
        base_ts = match.group(1)
        return f"{base_ts}.0000", 0, base_ts
    return None, None, None


def get_base_name_without_suffix(filename):
    """获取文件基本名称（去除后缀如 _speckle, _drone 等）"""
    name_without_ext = os.path.splitext(filename)[0]
    suffixes = ['_speckle', '_drone', '_narrow_capture', '_wide_capture']
    for suffix in suffixes:
        if name_without_ext.endswith(suffix):
            name_without_ext = name_without_ext[:-len(suffix)]
    return name_without_ext


def collect_multi_frame_files(source_dirs, output_dir, max_frames_per_group=5):
    """
    以 JSON 为主导收集文件：
    1. 先找到所有 JSON 文件，按时间戳排序
    2. 每个 JSON 独立匹配时间最接近的 N 张 JPG
    3. JPG 不能重复使用，已分配的 JPG 从池中移除
    4. 如果不够 N 张，继续找次接近的直到凑够或没有候选
    5. 只复制有 JPG 配对的 JSON
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

    # 步骤 2: 预处理所有 JPG 的时间戳信息
    jpg_info_list = []
    for jpg_path in all_jpg_files:
        jpg_name = os.path.basename(jpg_path)
        full_ts, ms_value, base_ts = extract_timestamp(jpg_name)
        if base_ts:
            jpg_info_list.append({
                'path': jpg_path,
                'name': jpg_name,
                'full_ts': full_ts,
                'ms_value': ms_value,
                'base_ts': base_ts,
                'assigned': False  # 标记是否已被分配
            })

    print(f"  有效 JPG: {len(jpg_info_list)} 张")

    # 步骤 3: JSON 按时间戳排序，确保分配顺序一致
    json_info_list = []
    for json_path in all_json_files:
        json_name = os.path.basename(json_path)
        json_full_ts, json_ms, json_base_ts = extract_timestamp(json_name)
        if json_base_ts:
            json_info_list.append({
                'path': json_path,
                'name': json_name,
                'full_ts': json_full_ts,
                'ms_value': json_ms,
                'base_ts': json_base_ts
            })

    # 按秒级时间戳 + 毫秒排序
    json_info_list.sort(key=lambda x: (x['base_ts'], x['ms_value']))

    print(f"  有效 JSON: {len(json_info_list)} 个（已按时间排序）")

    # 步骤 4: 依次给每个 JSON 分配不重复的 JPG
    print(f"\n 匹配 JSON 与 JPG（每个 JSON 独立分配 {max_frames_per_group} 张，JPG 不重复）...")
    matched_pairs = []
    json_without_jpg = []

    for json_info in json_info_list:
        json_path = json_info['path']
        json_name = json_info['name']
        json_full_ts = json_info['full_ts']
        json_ms = json_info['ms_value']
        json_base_ts = json_info['base_ts']

        print(f"\n  处理 JSON: {json_name}")
        print(f"  JSON 时间戳：{json_full_ts} (毫秒={json_ms})")

        # 过滤：只考虑同秒级别且未被分配的 JPG
        candidate_jpgs = [j for j in jpg_info_list if j['base_ts'] == json_base_ts and not j['assigned']]

        print(f"  可用候选 JPG: {len(candidate_jpgs)} 张")

        if candidate_jpgs:
            # 按毫秒差值排序
            def time_diff(jpg_info):
                return abs(jpg_info['ms_value'] - json_ms)

            candidate_jpgs_sorted = sorted(candidate_jpgs, key=time_diff)

            # 显示排序结果（前 10 个）
            print(f"  候选 JPG 按时间差排序:")
            for i, jpg_info in enumerate(candidate_jpgs_sorted[:10]):
                diff = abs(jpg_info['ms_value'] - json_ms)
                marker = "✓" if i < max_frames_per_group else "○"
                print(f"    {marker} [{i + 1}] {jpg_info['name']} (差{diff}ms)")

            if len(candidate_jpgs_sorted) > 10:
                print(f"    ...还有{len(candidate_jpgs_sorted) - 10}张")

            # 取前 N 张（或全部如果不够）
            actual_count = min(max_frames_per_group, len(candidate_jpgs_sorted))
            matched_jpgs = candidate_jpgs_sorted[:actual_count]

            # 标记为已分配
            for jpg_info in matched_jpgs:
                jpg_info['assigned'] = True

            matched_pairs.append({
                'json_path': json_path,
                'json_name': json_name,
                'jpg_paths': [j['path'] for j in matched_jpgs],
                'jpg_info': matched_jpgs,
                'timestamp': json_base_ts,
                'json_ms': json_ms,
                'assigned_count': actual_count
            })

            if actual_count < max_frames_per_group:
                print(f"  → 选中 {actual_count} 张（不足{max_frames_per_group}张）")
            else:
                print(f"  → 选中 {actual_count} 张 ✓")
        else:
            json_without_jpg.append(json_name)
            print(f"  ✗ 没有可用的 JPG（已被其他 JSON 分配完）")

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
            print(f"  ✗ 复制 JSON 失败 {json_name}: {e}")
            continue

        # 复制匹配的 JPG
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
                print(f"  ✗ 复制 JPG 失败 {jpg_name}: {e}")

    # 统计未分配的 JPG
    unassigned_jpg = sum(1 for j in jpg_info_list if not j['assigned'])

    return copied_jpg, copied_json, len(matched_pairs), unassigned_jpg, len(json_without_jpg)


def main():
    print("=" * 60)
    print("多帧图片提取工具 v8 (JPG 不重复分配版)")
    print("=" * 60)
    print("功能：每个 JSON 分配 5 张不重复的 JPG，按时间接近度")
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

    # 步骤 4: 收集并复制
    print("\n" + "=" * 60)
    print("步骤 4: 以 JSON 为主导提取文件")
    print("=" * 60)

    max_frames_input = input("请输入每组最大帧数（默认 5）：").strip()
    max_frames = int(max_frames_input) if max_frames_input else 5

    copied_jpg, copied_json, matched_count, unassigned_jpg, orphan_json = collect_multi_frame_files(source_dirs,
                                                                                                    output_dir,
                                                                                                    max_frames)

    # 最终统计
    print("\n" + "=" * 60)
    print("操作完成!")
    print("=" * 60)
    print(f" 解压的 7z 文件数：{len(seven_z_files)}")
    print(f" 成功匹配的组数：{matched_count} 组")
    print(f" 复制的 JPG 数量：{copied_jpg}")
    print(f" 复制的 JSON 数量：{copied_json}")
    print(f" 未分配的 JPG 数量：{unassigned_jpg}（未被任何 JSON 选中）")
    print(f" 孤立的 JSON 数量：{orphan_json}（无可用 JPG）")
    print(f" 输出目录：{output_dir}")
    print(f"\n 源文件已保留（未删除）")


if __name__ == "__main__":
    main()