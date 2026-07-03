import os
import shutil
import py7zr
import json
import re
from collections import defaultdict
import datetime


def extract_7z_file(file_path, extract_to=None):
    """
    解压7z文件
    :param file_path: 7z文件路径
    :param extract_to: 解压目标路径（可选，默认使用原文件名）
    :return: 解压后的目录路径或None
    """
    try:
        if extract_to is None:
            extract_to = os.path.splitext(file_path)[0]

        if os.path.exists(extract_to):
            print(f"文件夹已存在: {extract_to}")
            return extract_to

        os.makedirs(extract_to, exist_ok=True)

        with py7zr.SevenZipFile(file_path, mode='r') as archive:
            archive.extractall(path=extract_to)

        print(f"成功解压: {os.path.basename(file_path)} -> {os.path.basename(extract_to)}")
        return extract_to
    except Exception as e:
        print(f"解压失败 {file_path}: {e}")
        return None


def should_skip_directory(current_dir, skip_dir):
    """
    判断是否应该跳过当前目录
    :param current_dir: 当前目录路径
    :param skip_dir: 需要跳过的目录路径
    :return: True表示应该跳过，False表示不跳过
    """
    current_abs = os.path.abspath(current_dir)
    skip_abs = os.path.abspath(skip_dir)
    return current_abs.startswith(skip_abs + os.sep) or current_abs == skip_abs


def find_and_extract_archives(root_dir, output_dir):
    """
    在目录中查找并解压所有7z压缩文件
    :param root_dir: 当前目录路径
    :param output_dir: 输出目录路径
    :return: extracted_dirs已经解压后的目录路径
    """
    extracted_dirs = []

    for root, dirs, files in os.walk(root_dir):
        if should_skip_directory(root, output_dir):
            continue

        for file in files:
            if file.lower().endswith('.7z'):
                file_path = os.path.join(root, file)
                print(f"\n找到7z文件: {file}")
                extracted_path = extract_7z_file(file_path)
                if extracted_path:
                    extracted_dirs.append(extracted_path)

    return extracted_dirs


def extract_base_name(filename):
    """
    提取文件名的基本部分
    :param filename: 文件名
    :return: 文件的基本名称
    """
    # 去除扩展名
    name_without_ext = os.path.splitext(filename)[0]

    # 定义需要去除的后缀模式
    patterns_to_remove = [
        # 窄视场图像模式（带坐标信息的）
        r'_z\[\[.*?\]\].*?_to_.*?@.*',
        # 斑点标注图像
        r'_speckle$',
        # 无人机标注图像
        r'_drone$',
    ]

    # 按顺序尝试匹配并去除
    for pattern in patterns_to_remove:
        match = re.search(pattern, name_without_ext)
        if match:
            name_without_ext = name_without_ext[:match.start()]
            break

    return name_without_ext


def collect_all_files(root_dir, output_dir, extensions=None):
    """
    收集目录中所有指定类型的文件
    :param root_dir: 要搜索的根目录路径
    :param output_dir: 需要跳过的输出目录路径
    :param extensions: 需要收集的文件扩展名集合
    :return: all_files文件信息列表
    """
    if extensions is None:
        extensions = {'.jpg', '.json'}

    all_files = []

    for root, dirs, files in os.walk(root_dir):
        if should_skip_directory(root, output_dir):
            continue

        for file in files:
            file_ext = os.path.splitext(file)[1].lower()

            if file_ext in extensions:
                file_path = os.path.join(root, file)
                base_name = extract_base_name(file)

                all_files.append({
                    'path': file_path,
                    'name': file,
                    'ext': file_ext,
                    'source_dir': root,
                    'base_name': base_name,
                    'original_name': file
                })

    return all_files


def group_files_by_base_name(files):
    """
    按文件基本名称分组
    :param files: 文件信息列表
    :return: 分组后的字典
    """
    file_groups = defaultdict(list)

    for file_info in files:
        base_name = file_info['base_name']
        file_groups[base_name].append(file_info)

    return file_groups


def analyze_json_file(json_path):
    """
    分析JSON文件内容
    :param json_path: JSON文件路径
    :return: (type_value, classification_id_value, json_type) 或 (None, None, None) 如果解析失败
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 检查不同的JSON结构
        if 'DetbyStatus' in data:
            detby_status = data['DetbyStatus']

            # 尝试从efflt中读取（无人机检测格式）
            if 'efflt' in detby_status and detby_status['efflt']:
                first_detection = detby_status['efflt'][0]
                type_value = first_detection.get('type')
                classification_id = first_detection.get('classification_ID')
                return type_value, classification_id, 'efflt'

            # 尝试从real中读取（斑点检测格式）
            if 'real' in detby_status and detby_status['real']:
                first_detection = detby_status['real'][0]
                type_value = first_detection.get('type')
                classification_id = first_detection.get('classification_ID')
                return type_value, classification_id, 'real'

        return None, None, None
    except Exception as e:
        print(f"解析JSON文件失败 {json_path}: {e}")
        return None, None, None


def analyze_file_group(file_list):
    """
    分析文件组的组成和内容
    :param file_list: 文件信息列表
    :return: 分析结果字典
    """
    # 统计不同类型的文件
    jpg_files = [f for f in file_list if f['ext'] == '.jpg']
    json_files = [f for f in file_list if f['ext'] == '.json']

    # 检查是否有宽视场原图
    has_wide_original = any(
        '_wide_capture.jpg' == f['original_name'] or
        (f['original_name'].endswith('_wide_capture.jpg') and
         '_speckle' not in f['original_name'] and
         '_drone' not in f['original_name'])
        for f in jpg_files
    )

    # 检查是否有斑点标注图像
    has_speckle_jpg = any('_speckle.jpg' in f['original_name'] for f in jpg_files)

    # 检查是否有无人机标注图像
    has_drone_jpg = any('_drone.jpg' in f['original_name'] for f in jpg_files)

    # 检查是否有窄视场图像
    has_narrow_jpg = any(
        '_z[[' in f['original_name'] and '_narrow_capture.jpg' in f['original_name'] for f in jpg_files)

    # 检查是否有斑点标注JSON
    speckle_json_files = [f for f in json_files if '_speckle.json' in f['original_name']]
    has_speckle_json = len(speckle_json_files) > 0

    # 检查是否有无人机标注JSON
    drone_json_files = [f for f in json_files if '_drone.json' in f['original_name']]
    has_drone_json = len(drone_json_files) > 0

    # 分析斑点JSON
    speckle_type = None
    speckle_classification_id = None
    if has_speckle_json and speckle_json_files:
        json_path = speckle_json_files[0]['path']
        speckle_type, speckle_classification_id, _ = analyze_json_file(json_path)

    # 分析无人机JSON
    drone_type = None
    drone_classification_id = None
    if has_drone_json and drone_json_files:
        json_path = drone_json_files[0]['path']
        drone_type, drone_classification_id, _ = analyze_json_file(json_path)

    # 决定最终类型（优先级：无人机检测 > 斑点检测）
    final_type = None
    final_classification_id = None
    detection_source = None

    if has_drone_json and drone_type:
        final_type = drone_type
        final_classification_id = drone_classification_id
        detection_source = 'drone'
    elif has_speckle_json and speckle_type:
        final_type = speckle_type
        final_classification_id = speckle_classification_id
        detection_source = 'speckle'

    return {
        'type': final_type,
        'classification_id': final_classification_id,
        'detection_source': detection_source,
        'speckle_type': speckle_type,
        'speckle_classification_id': speckle_classification_id,
        'drone_type': drone_type,
        'drone_classification_id': drone_classification_id,
        'file_count': len(file_list),
        'jpg_count': len(jpg_files),
        'json_count': len(json_files),
        'has_wide_original': has_wide_original,
        'has_speckle_jpg': has_speckle_jpg,
        'has_drone_jpg': has_drone_jpg,
        'has_narrow_jpg': has_narrow_jpg,
        'has_speckle_json': has_speckle_json,
        'has_drone_json': has_drone_json,
        'has_json': len(json_files) > 0
    }


def classify_file_groups(file_groups):
    """
    对文件组进行分类
    :param file_groups: 按基本名称分组的文件字典
    :return: 分类后的字典，键为分类名称，值为文件组列表
    """
    classified_groups = {
        '未检出_背景': [],  # 没有有效JSON或JSON解析无type
        '已检出_斑点': [],  # 有JSON且type为speckle（且没有更优先的无人机检测）
        '已检出_分类模型_红框正确上报': [],  # 有JSON且type为drone且classification_ID为drone
        '已检出_分类模型_黑框正确未上报': [],  # 有JSON且type为drone但classification_ID不为drone
    }

    for base_name, file_list in file_groups.items():
        analysis = analyze_file_group(file_list)

        if analysis['type'] == "speckle":
            classified_groups['已检出_斑点'].append(file_list)
        elif analysis['type'] == "drone":
            if analysis['classification_id'] == "drone":
                classified_groups['已检出_分类模型_红框正确上报'].append(file_list)
            else:
                classified_groups['已检出_分类模型_黑框正确未上报'].append(file_list)
        else:
            # 没有有效JSON或解析失败，归为未检出_背景
            classified_groups['未检出_背景'].append(file_list)

    return classified_groups


def create_directory_structure(output_dir):
    """
    创建目录结构
    :param output_dir: 输出目录
    :return: 目录路径字典
    """
    dir_paths = {
        '未检出_背景': os.path.join(output_dir, "未检出_背景"),
        '已检出_斑点': os.path.join(output_dir, "已检出_斑点"),
        '已检出_斑点_误检': os.path.join(output_dir, "已检出_斑点", "已检出_斑点_误检"),
        '已检出_分类模型_红框_正确上报': os.path.join(output_dir, "已检出_分类模型_红框_正确上报"),
        '已检出_分类模型_红框_误报': os.path.join(output_dir, "已检出_分类模型_红框_正确上报",
                                                  "已检出_分类模型_红框_误报"),
        '已检出_分类模型_黑框_正确未上报': os.path.join(output_dir, "已检出_分类模型_黑框_正确未上报"),
        '已检出_分类模型_黑框_误报': os.path.join(output_dir, "已检出_分类模型_黑框_正确未上报",
                                                  "已检出_分类模型_黑框_误报")
    }

    for dir_path in dir_paths.values():
        os.makedirs(dir_path, exist_ok=True)

    print(f"已创建目录结构: {output_dir}")
    return dir_paths


def copy_files_to_categories(classified_groups, dir_paths):
    """
    复制文件到对应分类目录
    :param classified_groups: 分类后的文件组
    :param dir_paths: 目录路径字典
    :return: (total_copied, group_info)
    """
    copied_count = 0
    group_info = []
    group_idx = 1

    # 分类名称到目标目录的映射
    category_to_dir = {
        '未检出_背景': dir_paths['未检出_背景'],
        '已检出_斑点': dir_paths['已检出_斑点'],
        '已检出_分类模型_红框正确上报': dir_paths['已检出_分类模型_红框_正确上报'],
        '已检出_分类模型_黑框正确未上报': dir_paths['已检出_分类模型_黑框_正确未上报']
    }

    for category_name, groups in classified_groups.items():
        if not groups:
            continue

        print(f"\n处理分类: {category_name} ({len(groups)}组)")

        if category_name not in category_to_dir:
            print(f"  警告: 未找到目录路径 for {category_name}")
            continue

        target_dir = category_to_dir[category_name]

        for file_list in groups:
            base_name = file_list[0]['base_name'] if file_list else ""
            file_count = len(file_list)

            # 分析文件组
            analysis = analyze_file_group(file_list)

            print(f"  组 {group_idx}: 基本名称='{base_name}', 文件数={file_count}, "
                  f"类型={analysis['type']}, 分类ID={analysis['classification_id']}, "
                  f"检测来源={analysis['detection_source']}")

            group_files = []
            for file_info in file_list:
                src_path = file_info['path']
                dst_path = os.path.join(target_dir, file_info['name'])

                try:
                    shutil.copy2(src_path, dst_path)
                    copied_count += 1
                    group_files.append(file_info['name'])
                except Exception as e:
                    print(f"    复制失败 {file_info['name']}: {e}")

            group_info.append({
                'group_num': group_idx,
                'category': category_name,
                'base_name': base_name,
                'file_count': file_count,
                'type': analysis['type'],
                'classification_id': analysis['classification_id'],
                'detection_source': analysis['detection_source'],
                'target_dir': target_dir,
                'files': group_files,
                'has_wide_original': analysis['has_wide_original'],
                'has_narrow_jpg': analysis['has_narrow_jpg'],
                'has_speckle_jpg': analysis['has_speckle_jpg'],
                'has_drone_jpg': analysis['has_drone_jpg']
            })

            group_idx += 1

    return copied_count, group_info


def create_operation_log(output_dir, group_info, classified_groups, total_files, target_dir, dir_paths):
    """
    创建操作日志
    :param output_dir: 日志文件要保存的输出目录
    :param group_info: 包含分组信息的列表
    :param classified_groups: 分类后的文件组
    :param total_files: 总共复制的文件数量
    :param target_dir: 操作的源目录
    :param dir_paths: 目录路径字典
    :return: log_path
    """
    log_path = os.path.join(output_dir, "操作日志.txt")

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("文件分类操作日志\n")
        f.write("=" * 60 + "\n\n")

        # 使用datetime获取当前时间
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"操作时间: {current_time}\n")
        f.write(f"源目录: {target_dir}\n")
        f.write(f"输出目录: {output_dir}\n\n")

        # 输出目录结构
        f.write("创建的目录结构:\n")
        f.write("-" * 40 + "\n")
        for dir_name, dir_path in dir_paths.items():
            relative_path = os.path.relpath(dir_path, output_dir)
            f.write(f"{dir_name}: {relative_path}\n")
        f.write("\n")

        # 分类统计
        f.write("分类统计:\n")
        f.write("-" * 40 + "\n")
        for category_name, groups in classified_groups.items():
            f.write(f"{category_name}: {len(groups)} 组\n")

        # 计算文件组总数和文件总数
        total_groups = sum(len(groups) for groups in classified_groups.values())
        f.write(f"\n文件组总数: {total_groups}\n")
        f.write(f"复制的文件总数: {total_files}\n\n")

        f.write("操作详情:\n")
        f.write("=" * 60 + "\n")

        for info in group_info:
            f.write(f"\n第 {info['group_num']} 组:\n")
            f.write(f"  分类: {info['category']}\n")
            f.write(f"  基本名称: '{info['base_name']}'\n")
            f.write(f"  文件数量: {info['file_count']}\n")
            f.write(f"  检测类型: {info['type']}\n")
            f.write(f"  分类ID: {info['classification_id']}\n")
            f.write(f"  检测来源: {info['detection_source']}\n")
            f.write(f"  宽视场原图: {'有' if info['has_wide_original'] else '无'}\n")
            f.write(f"  窄视场图像: {'有' if info['has_narrow_jpg'] else '无'}\n")
            f.write(f"  目标目录: {os.path.relpath(info['target_dir'], output_dir)}\n")
            f.write("  文件列表:\n")
            for file_name in info['files']:
                f.write(f"    - {file_name}\n")
            f.write("\n")

    print(f"\n已生成操作日志: {log_path}")
    return log_path


def main():
    """主函数"""
    print("=" * 60)
    print("文件自动分类工具")
    print("=" * 60)
    print("分类规则:")
    print("  1. 有斑点检测JSON且type为speckle -> 已检出_斑点")
    print("  2. 有无人机检测JSON且type为drone且classification_ID为drone -> 已检出_分类模型_红框正确上报")
    print("  3. 有无人机检测JSON且type为drone但classification_ID不为drone -> 已检出_分类模型_黑框正确未上报")
    print("  4. 同时有斑点和无人机检测时，优先按无人机检测分类")
    print("  5. 没有有效JSON或解析失败 -> 未检出_背景")
    print("=" * 60)

    # 获取用户输入的目录路径
    target_dir = input("请输入完整目录路径: ").strip().strip('"').strip("'")

    # 检查目录是否存在
    if not os.path.exists(target_dir):
        print(f"错误: 目录 '{target_dir}' 不存在")
        return

    if not os.path.isdir(target_dir):
        print(f"错误: '{target_dir}' 不是一个目录")
        return

    print(f"\n开始处理目录: {target_dir}")

    # 获取最后一个目录名
    last_dir_name = os.path.basename(target_dir)
    if not last_dir_name:
        last_dir_name = os.path.basename(os.path.dirname(target_dir))

    # 创建输出目录
    output_dir_name = f"{last_dir_name}_classified"
    output_dir = os.path.join(target_dir, output_dir_name)

    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"已创建输出文件夹: {output_dir}")
    except Exception as e:
        print(f"创建输出文件夹失败: {e}")
        return

    # 步骤1: 查找并解压压缩文件
    print("\n" + "=" * 60)
    print("步骤1: 查找并解压7z压缩文件")
    print("=" * 60)
    extracted_dirs = find_and_extract_archives(target_dir, output_dir)
    if extracted_dirs:
        print(f"已解压 {len(extracted_dirs)} 个7z文件")
    else:
        print("未找到7z压缩文件")

    # 步骤2: 收集所有文件
    print("\n" + "=" * 60)
    print("步骤2: 收集目录中的所有文件")
    print("=" * 60)
    all_files = collect_all_files(target_dir, output_dir)
    print(f"共找到 {len(all_files)} 个jpg和json文件")

    if not all_files:
        print("目录中没有找到符合条件的jpg和json文件")
        return

    # 步骤3: 按基本名称分组
    print("\n" + "=" * 60)
    print("步骤3: 按文件基本名称分组")
    print("=" * 60)
    file_groups = group_files_by_base_name(all_files)
    print(f"共分为 {len(file_groups)} 组")

    # 步骤4: 创建目录结构
    print("\n" + "=" * 60)
    print("步骤4: 创建目录结构")
    print("=" * 60)
    dir_paths = create_directory_structure(output_dir)

    # 步骤5: 分类文件组
    print("\n" + "=" * 60)
    print("步骤5: 分类文件组")
    print("=" * 60)
    classified_groups = classify_file_groups(file_groups)

    # 统计分类结果
    total_groups = 0
    for category_name, groups in classified_groups.items():
        group_count = len(groups)
        print(f"{category_name}: {group_count} 组")
        total_groups += group_count

    print(f"\n分类组总数: {total_groups}")

    # 步骤6: 复制文件到对应分类目录
    print("\n" + "=" * 60)
    print("步骤6: 复制文件到对应分类目录")
    print("=" * 60)
    total_copied, group_info = copy_files_to_categories(classified_groups, dir_paths)

    # 步骤7: 创建操作日志
    print("\n" + "=" * 60)
    print("步骤7: 生成操作日志")
    print("=" * 60)
    create_operation_log(output_dir, group_info, classified_groups, total_copied, target_dir, dir_paths)

    # 最终统计
    print("\n" + "=" * 60)
    print("操作完成!")
    print("=" * 60)
    print(f"扫描的文件总数: {len(all_files)}")
    print(f"文件组总数: {len(file_groups)}")
    print(f"分类后的组数: {total_groups}")
    print(f"复制的文件总数: {total_copied}")
    print(f"所有文件已分类复制到: {output_dir}")
    print(f"操作日志已生成: {os.path.join(output_dir, '操作日志.txt')}")

    # 显示分类结果摘要
    print("\n" + "=" * 60)
    print("分类结果摘要:")
    print("=" * 60)
    for category_name, groups in classified_groups.items():
        print(f"{category_name}: {len(groups)} 组")


if __name__ == "__main__":
    main()