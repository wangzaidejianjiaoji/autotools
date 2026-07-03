import os
import json
import shutil
import re


def replace_drone_in_json(root_dir):
    """
    遍历目录下的子文件夹，将子文件夹下的.json文件内容中的"drone"替换为"similar"
    """
    if not os.path.exists(root_dir):
        print(f"错误: 目录 '{root_dir}' 不存在")
        return

    files_processed = 0
    files_modified = 0

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith('.json'):
                json_file_path = os.path.join(root, file)
                files_processed += 1

                try:
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    drone_count_before = content.count('drone')

                    if drone_count_before > 0:
                        new_content = re.sub(r'\bdrone\b', 'similar', content, flags=re.IGNORECASE)

                        with open(json_file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)

                        files_modified += 1
                        print(f"已替换: {json_file_path}")

                except Exception as e:
                    print(f"错误处理 {json_file_path}: {e}")

    print(f"JSON文件处理完成: 处理了 {files_processed} 个文件，修改了 {files_modified} 个文件")


def copy_files_by_groups(root_dir):
    """
    根据文件分组规则复制文件
    """
    if not os.path.exists(root_dir):
        print(f"错误: 目录 '{root_dir}' 不存在")
        return

    # 修改点：直接在输入目录下创建文件夹
    # 创建目标文件夹
    background_dir = os.path.join(root_dir, "纯背景图片")
    annotated_dir = os.path.join(root_dir, "已预标注处理")

    # 确保目标目录存在
    os.makedirs(background_dir, exist_ok=True)
    os.makedirs(annotated_dir, exist_ok=True)

    print(f"纯背景图片将复制到: {background_dir}")
    print(f"已预标注处理将复制到: {annotated_dir}")

    # 用于统计的文件计数器
    background_count = 0
    annotated_count = 0
    total_files_copied = 0
    skipped_files = 0  # 新增：记录跳过的文件数

    # 遍历所有子文件夹
    for subdir, dirs, files in os.walk(root_dir):
        # 跳过根目录本身和新创建的文件夹，避免复制自己到自己的子文件夹
        if subdir == root_dir or subdir == background_dir or subdir == annotated_dir:
            continue

        print(f"\n处理子文件夹: {subdir}")

        # 按文件名分组（不含后缀）
        file_groups = {}

        # 收集当前文件夹的所有文件
        for file in files:
            # 获取文件名（不含后缀）
            file_name_without_ext = os.path.splitext(file)[0]

            if file_name_without_ext not in file_groups:
                file_groups[file_name_without_ext] = []

            file_groups[file_name_without_ext].append(file)

        # 处理每个文件组
        for base_name, file_list in file_groups.items():
            print(f"  处理文件组 '{base_name}': 包含 {len(file_list)} 个文件")

            # 检查是否有.jpg和.json文件
            has_jpg = any(file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')) for file in file_list)
            has_json = any(file.lower().endswith('.json') for file in file_list)

            # 根据规则处理
            if has_jpg and not has_json:
                # 只有图片文件，没有.json文件
                for file in file_list:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                        src_path = os.path.join(subdir, file)
                        dst_path = os.path.join(background_dir, file)

                        # 检查文件是否已存在，如果存在则跳过
                        if os.path.exists(dst_path):
                            skipped_files += 1
                            print(f"    跳过纯背景图片(文件已存在): {file}")
                            continue

                        try:
                            # 复制文件
                            shutil.copy2(src_path, dst_path)
                            background_count += 1
                            total_files_copied += 1
                            print(f"    已复制纯背景图片: {file}")
                        except Exception as e:
                            print(f"    复制文件失败 {file}: {e}")

            elif has_jpg and has_json:
                # 同时有图片和.json文件
                for file in file_list:
                    src_path = os.path.join(subdir, file)

                    # 如果是图片文件
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                        dst_path = os.path.join(annotated_dir, file)

                        # 检查文件是否已存在，如果存在则跳过
                        if os.path.exists(dst_path):
                            skipped_files += 1
                            print(f"    跳过已标注图片(文件已存在): {file}")
                            continue

                        try:
                            shutil.copy2(src_path, dst_path)
                            annotated_count += 1
                            total_files_copied += 1
                            print(f"    已复制已标注图片: {file}")
                        except Exception as e:
                            print(f"    复制图片文件失败 {file}: {e}")
                    # 如果是JSON文件
                    elif file.lower().endswith('.json'):
                        dst_path = os.path.join(annotated_dir, file)

                        # 检查文件是否已存在，如果存在则跳过
                        if os.path.exists(dst_path):
                            skipped_files += 1
                            print(f"    跳过JSON文件(文件已存在): {file}")
                            continue

                        try:
                            shutil.copy2(src_path, dst_path)
                            total_files_copied += 1
                            print(f"    已复制JSON文件: {file}")
                        except Exception as e:
                            print(f"    复制JSON文件失败 {file}: {e}")
                    # 其他文件类型也复制到已标注文件夹
                    else:
                        dst_path = os.path.join(annotated_dir, file)

                        # 检查文件是否已存在，如果存在则跳过
                        if os.path.exists(dst_path):
                            skipped_files += 1
                            print(f"    跳过其他文件(文件已存在): {file}")
                            continue

                        try:
                            shutil.copy2(src_path, dst_path)
                            total_files_copied += 1
                            print(f"    已复制其他文件: {file}")
                        except Exception as e:
                            print(f"    复制其他文件失败 {file}: {e}")

            else:
                # 其他情况（只有.json文件或其他文件）
                print(f"    跳过文件组 '{base_name}': 不符合处理规则")

    print(f"\n文件复制完成!")
    print(f"复制到纯背景图片文件夹: {background_count} 个文件")
    print(f"复制到已预标注处理文件夹: {annotated_count} 个文件")
    print(f"总共复制了: {total_files_copied} 个文件")
    print(f"跳过了: {skipped_files} 个已存在的文件")

    return background_dir, annotated_dir


def main():
    """主函数"""
    # 获取用户输入的目录路径
    directory = input("请输入目录路径 : ").strip()

    # 移除可能的引号
    if directory.startswith('"') and directory.endswith('"'):
        directory = directory[1:-1]
    elif directory.startswith("'") and directory.endswith("'"):
        directory = directory[1:-1]

    # 检查目录是否存在
    if not os.path.exists(directory):
        print(f"错误: 目录 '{directory}' 不存在")
        return

    print(f"输入目录: {directory}")
    print("\n即将执行以下操作:")
    print("1. 替换所有JSON文件中的'drone'为'similar'")
    print("2. 按规则复制文件到输入目录下的两个新文件夹中")


    # 步骤1: 替换JSON文件中的内容
    print("\n" + "=" * 50)
    print("步骤1: 替换JSON文件中的'drone'为'similar'")
    print("=" * 50)
    replace_drone_in_json(directory)

    # 步骤2: 按规则复制文件
    print("\n" + "=" * 50)
    print("步骤2: 按规则复制文件")
    print("=" * 50)
    background_dir, annotated_dir = copy_files_by_groups(directory)

    # 显示最终结果
    print("\n" + "=" * 50)
    print("处理完成!")
    print("=" * 50)

    # 显示新的路径结构
    print(f"处理结果:")
    print(f"输入目录: {directory}")
    print(f"├── 纯背景图片文件夹: {background_dir}")

    if os.path.exists(background_dir):
        bg_files = os.listdir(background_dir)
        print(f"│   包含文件数: {len(bg_files)}")
        if len(bg_files) > 0:
            print(f"│   示例文件: {bg_files[:5]}")

    print(f"└── 已预标注处理文件夹: {annotated_dir}")
    if os.path.exists(annotated_dir):
        ann_files = os.listdir(annotated_dir)
        print(f"     包含文件数: {len(ann_files)}")
        if len(ann_files) > 0:
            print(f"     示例文件: {ann_files[:5]}")


if __name__ == "__main__":
    main()