#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多帧图片提取工具 v11 (文件名精确匹配版)
功能：
1. 根据 JSON 文件名精确匹配对应的标注 JPG（同名）
2. 根据 params + 前 17 位字符匹配同一组的多帧原图（必须正好 5 张）
3. 自动按 drone/speckle 分类输出，混组输出到 mix_drone_speckle
4. 没有 JSON 对应的纯 JPG 组不复制
5. 前 17 位字符不一致或原图数量不等于 5 张则整组不复制
"""

import os
import re
import shutil
import py7zr
import sys
from collections import defaultdict

# 添加JSON格式转换功能
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'JSON Format Cleaning'))
try:
    # 直接导入文件
    json_format_path = os.path.join(os.path.dirname(__file__), '..', 'JSON Format Cleaning', 'debug.json_to_labelme.json_format.py')
    if os.path.exists(json_format_path):
        exec(open(json_format_path).read())
    else:
        print("警告：未找到JSON格式转换工具")
        convert_json_format = lambda x: None
except Exception as e:
    print(f"导入JSON格式转换工具失败: {e}")
    convert_json_format = lambda x: None


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
        
        # 调用JSON格式转换
        print(f"  正在转换JSON格式...")
        # 确保在处理文件前先转换JSON格式
        convert_json_format(extract_to)
        print(f"  JSON格式转换完成")
        
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


def check_bbox_size(json_path):
    """
    检查JSON文件中的标注框大小
    如果所有标注框的长宽均<10，则返回True
    """
    try:
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查shapes中的标注框
        if 'shapes' in data:
            for shape in data['shapes']:
                if shape['shape_type'] == 'rectangle' and len(shape['points']) == 2:
                    x1, y1 = shape['points'][0]
                    x2, y2 = shape['points'][1]
                    width = abs(x2 - x1)
                    height = abs(y2 - y1)
                    if width >= 10 or height >= 10:
                        return False
        return True
    except Exception as e:
        print(f"检查标注框大小失败 {json_path}: {e}")
        return False


def is_sky_background(params):
    """
    检查是否为天空背景动态误报
    符合以下条件之一：
    - p220-280t5.20
    - p310-320t5.20
    - p350-359t8.20
    - p0-34t8.20
    """
    try:
        # 提取p和t值
        p_match = re.search(r'p([\d\.]+)', params)
        t_match = re.search(r't([\d\.]+)', params)
        
        if not p_match or not t_match:
            return False
        
        p = float(p_match.group(1))
        t = float(t_match.group(1))
        
        # 检查是否符合条件
        if (220 <= p <= 280 and t > 5.20) or \
           (310 <= p <= 320 and t > 5.20) or \
           (350 <= p <= 359 and t > 8.20) or \
           (0 <= p <= 34 and t > 8.20):
            return True
        
        return False
    except Exception as e:
        print(f"检查天空背景失败: {e}")
        return False


def parse_filename(filename):
    """
    解析文件名，提取关键信息
    示例：20260306_18-48-04.791_p16.00t0.00z2.00_narrow_capture_drone.json
    """

    name_no_ext = os.path.splitext(filename)[0]
    extension = os.path.splitext(filename)[1].lstrip('.')

    pattern = r'^(\d{8}_\d{2}-\d{2}-\d{2})\.(\d+)_([p\d\.t\-z]+)_(.+?)(?:_(drone|speckle))?$'
    match = re.match(pattern, name_no_ext)

    if not match:
        pattern_simple = r'^(\d{8}_\d{2}-\d{2}-\d{2})\.(\d+)_([p\d\.t\-z]+)_(.+)$'
        match = re.match(pattern_simple, name_no_ext)
        if match:
            base_ts = match.group(1)
            return {
                'base_ts': base_ts,
                'ms': match.group(2),
                'full_ts': f"{base_ts}.{match.group(2)}",
                'ts_17': base_ts[:17],
                'params': match.group(3),
                'capture_type': match.group(4),
                'suffix': None,
                'name_no_ext': name_no_ext,
                'extension': extension
            }
        return None

    base_ts = match.group(1)
    return {
        'base_ts': base_ts,
        'ms': match.group(2),
        'full_ts': f"{base_ts}.{match.group(2)}",
        'ts_17': base_ts[:17],
        'params': match.group(3),
        'capture_type': match.group(4),
        'suffix': match.group(5),
        'name_no_ext': name_no_ext,
        'extension': extension
    }


def collect_files_by_group(source_dirs):
    """
    收集所有文件并按组分类
    分组规则：ts_17（精确到秒）+ params + capture_type 相同为一组
    """
    all_json_files = []
    all_jpg_files = []

    for source_dir in source_dirs:
        print(f"  扫描目录：{source_dir}")
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_lower = file.lower()
                file_path = os.path.join(root, file)

                if file_lower.endswith('.json'):
                    parsed = parse_filename(file)
                    if parsed:
                        all_json_files.append({'path': file_path, 'name': file, 'parsed': parsed})
                elif file_lower.endswith('.jpg'):
                    parsed = parse_filename(file)
                    if parsed:
                        all_jpg_files.append({'path': file_path, 'name': file, 'parsed': parsed})

    print(f"  扫描完成：{len(all_json_files)} 个 JSON, {len(all_jpg_files)} 张 JPG")

    # 分组 key = ts_17（精确到秒）+ params + capture_type
    groups = defaultdict(lambda: {'json': [], 'jpg': [], 'jpg_no_suffix': []})

    for json_info in all_json_files:
        parsed = json_info['parsed']
        group_key = f"{parsed['ts_17']}_{parsed['params']}_{parsed['capture_type']}"
        groups[group_key]['json'].append(json_info)

    for jpg_info in all_jpg_files:
        parsed = jpg_info['parsed']
        group_key = f"{parsed['ts_17']}_{parsed['params']}_{parsed['capture_type']}"
        groups[group_key]['jpg'].append(jpg_info)

        if parsed['suffix'] is None:
            groups[group_key]['jpg_no_suffix'].append(jpg_info)

    return groups


def match_files_in_group(group_data, max_frames_per_group=5):
    """
    在一组文件中匹配 JSON 和对应的 JPG
    匹配规则：
    1. 检查组内是否有正好 max_frames_per_group 张无后缀原图（多帧）
    2. 每个 JSON 找同名的标注 JPG（带 drone/speckle 后缀）
    3. 如果原图数量不足，检查是否为单帧数据
    """
    json_list = group_data['json']
    jpg_list = group_data['jpg']
    jpg_no_suffix_list = group_data['jpg_no_suffix']

    # 按时间戳排序
    json_list.sort(key=lambda x: x['parsed']['full_ts'])
    jpg_no_suffix_list.sort(key=lambda x: x['parsed']['full_ts'])

    matched_groups = []
    json_without_jpg = []

    # 步骤 1: 检查是否为多帧数据
    if len(jpg_no_suffix_list) == max_frames_per_group:
        print(
            f"    ✓ 原图数量 {len(jpg_no_suffix_list)} = {max_frames_per_group}，前 17 位：{jpg_no_suffix_list[0]['parsed']['ts_17']}")

        # 步骤 2: 检测分类情况
        has_drone = any(j['parsed']['suffix'] == 'drone' for j in json_list)
        has_speckle = any(j['parsed']['suffix'] == 'speckle' for j in json_list)

        if has_drone:
            output_subdir = 'drone'
        elif has_speckle:
            output_subdir = 'speckle'
        else:
            output_subdir = 'unknown'
    else:
        print(f"    ✗ 原图数量 {len(jpg_no_suffix_list)} 不符合要求，只处理单帧分类")
        # 不返回，继续处理单帧分类

    # 步骤 3: 创建标注 JPG 查找字典（按 name_no_ext）
    jpg_annotation_by_name = {}
    for jpg_info in jpg_list:
        if jpg_info['parsed']['suffix'] is not None:
            jpg_annotation_by_name[jpg_info['parsed']['name_no_ext']] = jpg_info

    # 步骤 4: 为每个 JSON 匹配标注图
    used_annotation_paths = set()
    selected_json_list = []
    small_json_list = []
    fly_json_list = []
    similar_json_list = []

    for json_info in json_list:
        json_parsed = json_info['parsed']
        json_name_no_ext = json_parsed['name_no_ext']

        annotation_jpg = jpg_annotation_by_name.get(json_name_no_ext)

        if not annotation_jpg:
            json_without_jpg.append(json_info['name'])
            print(f"    ✗ JSON 无对应标注图：{json_info['name']}")
            continue

        if annotation_jpg['path'] in used_annotation_paths:
            json_without_jpg.append(json_info['name'])
            print(f"    ✗ 标注图已被使用：{json_info['name']}")
            continue

        # 检查标注框大小（优先级最高）
        if check_bbox_size(json_info['path']):
            print(f"    ✓ 标注框过小，分类到 small：{json_info['name']}")
            small_json_list.append({
                'json_info': json_info,
                'annotation_jpg': annotation_jpg
            })
        # 检查是否为天空背景动态误报
        elif is_sky_background(json_parsed['params']):
            print(f"    ✓ 天空背景动态误报，分类到 fly：{json_info['name']}")
            fly_json_list.append({
                'json_info': json_info,
                'annotation_jpg': annotation_jpg
            })
        else:
            used_annotation_paths.add(annotation_jpg['path'])
            selected_json_list.append({
                'json_info': json_info,
                'annotation_jpg': annotation_jpg
            })
        
        # 检查是否为非天空背景静态误报（similar）
        # 注意：这里不影响原有的speckle分类逻辑，且small文件不会被包含
        if len(jpg_no_suffix_list) == max_frames_per_group and json_parsed['suffix'] == 'speckle' and not is_sky_background(json_parsed['params']) and not check_bbox_size(json_info['path']):
            print(f"    ✓ 非天空背景静态误报，分类到 similar：{json_info['name']}")
            similar_json_list.append({
                'json_info': json_info,
                'annotation_jpg': annotation_jpg
            })

    # 步骤 5: 构建输出组（只有当原图数量符合要求时）
    if len(jpg_no_suffix_list) == max_frames_per_group and selected_json_list:
        matched_groups.append({
            'json_paths': [item['json_info']['path'] for item in selected_json_list],
            'json_names': [item['json_info']['name'] for item in selected_json_list],
            'annotation_jpg_paths': [item['annotation_jpg']['path'] for item in selected_json_list],
            'raw_jpg_paths': [j['path'] for j in jpg_no_suffix_list],
            'output_subdir': output_subdir
        })

        print(f"    ✓ {len(selected_json_list)} 个 JSON + {len(jpg_no_suffix_list)} 张原图 -> {output_subdir}/")
    
    # 步骤 6: 处理单帧分类（dronefp-single和specle-single）
    # 在一组多帧数据中只取时间最早的一张JSON和对应的原图
    print(f"  开始处理单帧分类，共有 {len(json_list)} 个JSON文件")
    
    # 按时间戳对JSON文件排序
    sorted_json_list = sorted(json_list, key=lambda x: x['parsed']['full_ts'])
    
    # 打印所有JSON文件的信息（按时间顺序）
    print(f"  JSON文件按时间顺序：")
    for i, json_info in enumerate(sorted_json_list):
        json_parsed = json_info['parsed']
        print(f"    {i+1}. {json_info['name']} (时间：{json_parsed['full_ts']}, 后缀：{json_parsed['suffix']})")
    
    # 打印所有无后缀原图
    print(f"  无后缀原图列表：")
    for jpg_info in jpg_no_suffix_list:
        print(f"    {os.path.basename(jpg_info['path'])}")
    
    # 按后缀分组，只取每组中时间最早的JSON
    suffix_json_map = {}
    for json_info in sorted_json_list:
        json_parsed = json_info['parsed']
        suffix = json_parsed['suffix']
        
        # 只处理drone或speckle后缀的文件
        if suffix in ['drone', 'speckle']:
            # 只保存每组中时间最早的JSON
            if suffix not in suffix_json_map:
                suffix_json_map[suffix] = json_info
    
    # 处理每组时间最早的JSON
    for suffix, json_info in suffix_json_map.items():
        json_parsed = json_info['parsed']
        json_name_no_ext = json_parsed['name_no_ext']
        
        print(f"  处理JSON：{json_info['name']}")
        
        # 只处理drone或speckle后缀的文件
        if json_parsed['suffix'] not in ['drone', 'speckle']:
            print(f"    ✗ 不是drone或speckle后缀，跳过")
            continue
        
        # 跳过被分类到small的文件
        if check_bbox_size(json_info['path']):
            print(f"    ✗ 被分类到small，跳过")
            continue
        
        # 构建对应的原图文件名（移除后缀）
        # 例如：20260311_20-56-53.7291_p224.00t0.00z2.00_narrow_capture_drone -> 20260311_20-56-53.7291_p224.00t0.00z2.00_narrow_capture
        if json_parsed['suffix']:
            suffix_val = json_parsed['suffix']
            base_name = json_name_no_ext.rsplit(f'_{suffix_val}', 1)[0]
            expected_raw_jpg_name = base_name + '.jpg'
            print(f"    构建期望原图文件名：{expected_raw_jpg_name}")
        else:
            expected_raw_jpg_name = json_name_no_ext + '.jpg'
            print(f"    构建期望原图文件名：{expected_raw_jpg_name}")
        
        # 查找对应的原图
        matching_raw_jpg = None
        for jpg_info in jpg_no_suffix_list:
            jpg_name = os.path.basename(jpg_info['path'])
            print(f"    检查原图：{jpg_name}")
            if jpg_name == expected_raw_jpg_name:
                matching_raw_jpg = jpg_info
                print(f"    ✓ 找到匹配的原图：{jpg_name}")
                break
        
        if matching_raw_jpg:
            # 确定单帧分类
            if json_parsed['suffix'] == 'drone':
                single_subdir = 'dronefp-single'
                print(f"    ✓ 找到drone单帧数据：{json_info['name']} -> 原图：{expected_raw_jpg_name}")
            else:  # speckle
                single_subdir = 'specle-single'
                print(f"    ✓ 找到speckle单帧数据：{json_info['name']} -> 原图：{expected_raw_jpg_name}")
            
            # 添加到匹配组 - 只复制原图和JSON，不复制标注图
            matched_groups.append({
                'json_paths': [json_info['path']],
                'json_names': [json_info['name']],
                'annotation_jpg_paths': [],  # 不复制标注图
                'raw_jpg_paths': [matching_raw_jpg['path']],
                'output_subdir': single_subdir
            })
            
            print(f"    ✓ 单帧数据 -> {single_subdir}/: {json_info['name']} + 原图：{expected_raw_jpg_name}")
        else:
            print(f"    ✗ 未找到对应的原图：{json_info['name']} -> 期望原图：{expected_raw_jpg_name}")

    # 处理small分类
    if small_json_list:
        matched_groups.append({
            'json_paths': [item['json_info']['path'] for item in small_json_list],
            'json_names': [item['json_info']['name'] for item in small_json_list],
            'annotation_jpg_paths': [item['annotation_jpg']['path'] for item in small_json_list],
            'raw_jpg_paths': [j['path'] for j in jpg_no_suffix_list],
            'output_subdir': 'small'
        })

        print(f"    ✓ {len(small_json_list)} 个 JSON + {len(jpg_no_suffix_list)} 张原图 -> small/")

    # 处理fly分类
    if fly_json_list:
        matched_groups.append({
            'json_paths': [item['json_info']['path'] for item in fly_json_list],
            'json_names': [item['json_info']['name'] for item in fly_json_list],
            'annotation_jpg_paths': [item['annotation_jpg']['path'] for item in fly_json_list],
            'raw_jpg_paths': [j['path'] for j in jpg_no_suffix_list],
            'output_subdir': 'fly'
        })

        print(f"    ✓ {len(fly_json_list)} 个 JSON + {len(jpg_no_suffix_list)} 张原图 -> fly/")

    # 处理similar分类
    if similar_json_list:
        matched_groups.append({
            'json_paths': [item['json_info']['path'] for item in similar_json_list],
            'json_names': [item['json_info']['name'] for item in similar_json_list],
            'annotation_jpg_paths': [item['annotation_jpg']['path'] for item in similar_json_list],
            'raw_jpg_paths': [j['path'] for j in jpg_no_suffix_list],
            'output_subdir': 'similar'
        })

        print(f"    ✓ {len(similar_json_list)} 个 JSON + {len(jpg_no_suffix_list)} 张原图 -> similar/")

    unassigned_jpg = len(jpg_list) - len(used_annotation_paths) - len(jpg_no_suffix_list)

    return matched_groups, json_without_jpg, unassigned_jpg


def copy_files_to_output(matched_groups, output_dir):
    """复制文件到输出目录"""
    os.makedirs(output_dir, exist_ok=True)
    print(f"  输出目录：{output_dir}")

    copied_jpg = 0
    copied_json = 0

    for group in matched_groups:
        json_paths = group['json_paths']
        annotation_jpg_paths = group['annotation_jpg_paths']
        raw_jpg_paths = group['raw_jpg_paths']
        output_subdir = group['output_subdir']

        subdir_path = os.path.join(output_dir, output_subdir)
        os.makedirs(subdir_path, exist_ok=True)

        # 复制 JSON
        for json_path in json_paths:
            json_name = os.path.basename(json_path)
            dst_json = os.path.join(subdir_path, json_name)

            if os.path.exists(dst_json):
                base, ext = os.path.splitext(json_name)
                counter = 1
                while os.path.exists(dst_json):
                    dst_json = os.path.join(subdir_path, f"{base}_{counter}{ext}")
                    counter += 1

            try:
                shutil.copy2(json_path, dst_json)
                copied_json += 1
            except Exception as e:
                print(f"    ✗ 复制 JSON 失败：{json_name} - {e}")
                continue

        # 复制标注 JPG
        for jpg_path in annotation_jpg_paths:
            jpg_name = os.path.basename(jpg_path)
            dst_jpg = os.path.join(subdir_path, jpg_name)

            if os.path.exists(dst_jpg):
                base, ext = os.path.splitext(jpg_name)
                counter = 1
                while os.path.exists(dst_jpg):
                    dst_jpg = os.path.join(subdir_path, f"{base}_{counter}{ext}")
                    counter += 1

            try:
                shutil.copy2(jpg_path, dst_jpg)
                copied_jpg += 1
            except Exception as e:
                print(f"    ✗ 复制标注 JPG 失败：{jpg_name} - {e}")
                continue

        # 复制原图 JPG
        for jpg_path in raw_jpg_paths:
            jpg_name = os.path.basename(jpg_path)
            dst_jpg = os.path.join(subdir_path, jpg_name)

            if os.path.exists(dst_jpg):
                base, ext = os.path.splitext(jpg_name)
                counter = 1
                while os.path.exists(dst_jpg):
                    dst_jpg = os.path.join(subdir_path, f"{base}_{counter}{ext}")
                    counter += 1

            try:
                shutil.copy2(jpg_path, dst_jpg)
                copied_jpg += 1
            except Exception as e:
                print(f"    ✗ 复制原图 JPG 失败：{jpg_name} - {e}")
                continue

    return copied_jpg, copied_json


def main():
    print("=" * 60)
    print("多帧图片提取工具 v12 (增强分类版)")
    print("=" * 60)
    print("功能：")
    print("  1. 根据 JSON 文件名精确匹配对应的标注 JPG（同名）")
    print("  2. 根据 params+ 前 17 位匹配同一组的多帧原图（必须正好 5 张）")
    print("  3. 支持单帧数据分类：specle-single、dronefp-single")
    print("  4. 支持特殊分类：small（标注框过小）、fly（天空背景动态误报）、similar（非天空背景静态误报）")
    print("  5. 自动按 drone/speckle 分类输出，混组输出到 mix_drone_speckle")
    print("  6. 没有 JSON 对应的纯 JPG 组不复制")
    print("  7. 前 17 位字符不一致或原图数量不等于 5 张则整组不复制")
    print("=" * 60)

    target_dir = input("请输入 7z 文件所在目录路径：").strip().strip('"').strip("'")
    output_dir = input("请输入输出目录路径（默认 D:\\multi-frame_test_set）：").strip().strip('"').strip("'")

    if not output_dir:
        output_dir = r"D:\multi-frame_test_set"

    if not os.path.exists(target_dir):
        print(f"错误：目录 '{target_dir}' 不存在")
        return

    print(f"  输入目录：{target_dir}")
    print(f"  输出目录：{output_dir}")

    max_frames = 5

    print(f"  使用最大帧数：{max_frames}（必须正好此数量）")
    print(f"  时间判定：前 17 位字符必须完全一致")

    print("\n" + "=" * 60)
    print("步骤 1: 查找 7z 文件")
    print("=" * 60)
    seven_z_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.7z')]
    print(f"  找到 {len(seven_z_files)} 个 7z 文件")

    if not seven_z_files:
        print("  没有找到 7z 文件")
        return

    print("\n" + "=" * 60)
    print("步骤 2: 解压 7z 文件")
    print("=" * 60)
    extracted_dirs = []
    for seven_z_file in seven_z_files:
        file_path = os.path.join(target_dir, seven_z_file)
        extracted_path = extract_7z_file(file_path)
        if extracted_path:
            extracted_dirs.append(extracted_path)

    print(f"  共解压 {len(extracted_dirs)} 个文件")

    print("\n" + "=" * 60)
    print("步骤 3: 查找 ping/pong 子目录")
    print("=" * 60)
    source_dirs = []
    for extracted_dir in extracted_dirs:
        ping_pong_dir = find_ping_or_pong_dir(extracted_dir)
        source_dirs.append(ping_pong_dir)
        print(f"  {os.path.basename(extracted_dir)} -> {os.path.basename(ping_pong_dir)}")

    print("\n" + "=" * 60)
    print("步骤 4: 文件名精确匹配")
    print("=" * 60)

    groups = collect_files_by_group(source_dirs)
    print(f"  共发现 {len(groups)} 个文件组（按 ts_17+params+capture_type 分类）")

    total_matched_groups = []
    total_json_without_jpg = []
    total_unassigned_jpg = 0

    for group_key, group_data in groups.items():
        if not group_data['json']:
            print(f"  跳过组 {group_key}（无 JSON 文件）")
            total_unassigned_jpg += len(group_data['jpg'])
            continue

        print(f"\n  处理组：{group_key}")
        print(
            f"    JSON: {len(group_data['json'])} 个，JPG: {len(group_data['jpg'])} 张，原图：{len(group_data['jpg_no_suffix'])} 张")

        matched, orphan_json, unassigned = match_files_in_group(group_data, max_frames)
        total_matched_groups.extend(matched)
        total_json_without_jpg.extend(orphan_json)
        total_unassigned_jpg += unassigned

    print("\n" + "=" * 60)
    print("步骤 5: 复制到输出目录")
    print("=" * 60)

    if total_matched_groups:
        copied_jpg, copied_json = copy_files_to_output(total_matched_groups, output_dir)
    else:
        copied_jpg, copied_json = 0, 0
        print("  没有匹配到任何文件组")

    print("\n" + "=" * 60)
    print("操作完成!")
    print("=" * 60)
    print(f"  解压的 7z 文件数：{len(seven_z_files)}")
    print(f"  成功匹配的组数：{len(total_matched_groups)} 组")
    print(f"  复制的 JPG 数量：{copied_jpg}")
    print(f"  复制的 JSON 数量：{copied_json}")
    print(f"  未分配的 JPG 数量：{total_unassigned_jpg}")
    print(f"  孤立的 JSON 数量：{len(total_json_without_jpg)}")
    print(f"  输出目录：{output_dir}")

    if os.path.exists(output_dir):
        print("\n  输出目录结构:")
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            if os.path.isdir(item_path):
                file_count = len(os.listdir(item_path))
                print(f"    {item}/ ({file_count} 个文件)")

    print(f"\n  源文件已保留（未删除）")

#
# def test_single_frame_processing():
#     """测试单帧分类处理逻辑"""
#     print("=" * 60)
#     print("测试单帧分类处理逻辑")
#     print("=" * 60)
#
#     # 模拟测试数据
#     test_json_file = "20260311_20-56-53.7291_p224.00t0.00z2.00_narrow_capture_drone.json"
#     test_raw_jpg_file = "20260311_20-56-53.7291_p224.00t0.00z2.00_narrow_capture.jpg"
#
#     # 解析测试文件名
#     parsed_json = parse_filename(test_json_file)
#     parsed_jpg = parse_filename(test_raw_jpg_file)
#
#     print(f"测试JSON文件: {test_json_file}")
#     print(f"解析结果: {parsed_json}")
#     print(f"测试原图文件: {test_raw_jpg_file}")
#     print(f"解析结果: {parsed_jpg}")
#
#     # 模拟组数据
#     test_group = {
#         'json': [{
#             'path': f"/test/{test_json_file}",
#             'name': test_json_file,
#             'parsed': parsed_json
#         }],
#         'jpg': [],
#         'jpg_no_suffix': [{
#             'path': f"/test/{test_raw_jpg_file}",
#             'name': test_raw_jpg_file,
#             'parsed': parsed_jpg
#         }]
#     }
#
#     # 调用匹配函数
#     matched_groups, json_without_jpg, unassigned_jpg = match_files_in_group(test_group)
#
#     print(f"\n匹配结果:")
#     print(f"matched_groups: {len(matched_groups)}")
#     for i, group in enumerate(matched_groups):
#         print(f"  组 {i+1}: {group['output_subdir']}")
#         print(f"    JSON: {group['json_names']}")
#         print(f"    原图: {[os.path.basename(p) for p in group['raw_jpg_paths']]}")
#
#     print(f"json_without_jpg: {json_without_jpg}")
#     print(f"unassigned_jpg: {unassigned_jpg}")
#     print("=" * 60)

if __name__ == "__main__":
    # # 检查命令行参数
    # import sys
    # if len(sys.argv) > 1 and sys.argv[1] == "--test":
    #     # 只运行测试模式
    #     test_single_frame_processing()
    # else:
    #     # 正常运行模式
        main()