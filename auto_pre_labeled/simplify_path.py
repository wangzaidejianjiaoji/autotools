import os
import shutil
import sys


def get_directory_from_user():
    """从用户获取目录路径"""
    while True:
        # 提示用户输入目录路径
        directory = input("请输入要处理的目录路径 (或输入 'q' 退出): ").strip()

        if directory.lower() == 'q':
            print("程序退出")
            sys.exit(0)

        # 检查目录是否存在
        if not os.path.exists(directory):
            print(f"错误: 目录不存在 - {directory}")
            continue

        if not os.path.isdir(directory):
            print(f"错误: 不是有效的目录 - {directory}")
            continue

        return directory


def shorten_folder_paths(root_dir):
    """
    缩短文件夹路径，将重复的子文件夹名称合并
    例如：.../images1/images1 -> .../images1
    """

    # 收集所有需要处理的文件夹（从最深层开始处理）
    folders_to_process = []

    # 使用深度优先遍历，从最深层开始处理
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # 获取当前目录的父目录和当前目录名
        parent_dir = os.path.dirname(dirpath)
        current_dir_name = os.path.basename(dirpath)
        parent_dir_name = os.path.basename(parent_dir)

        # 如果当前目录名与父目录名相同，则需要处理
        if current_dir_name == parent_dir_name:
            # 获取父目录的父目录
            grandparent_dir = os.path.dirname(parent_dir)

            # 计算目标路径（父目录的路径）
            target_path = parent_dir
            # 源路径（当前路径）
            source_path = dirpath

            folders_to_process.append((source_path, target_path, grandparent_dir))

    if not folders_to_process:
        print("未找到需要处理的文件夹")
        return

    print(f"找到 {len(folders_to_process)} 个需要处理的文件夹:")
    for source, target, grandparent in folders_to_process:
        print(f"  {source}")
        print(f"  -> {target}")

    # 询问用户确认
    response = input("\n是否继续执行移动操作？(y/n): ").strip().lower()
    if response != 'y':
        print("操作已取消")
        return

    # 处理每个需要移动的文件夹
    for source_path, target_path, grandparent_dir in folders_to_process:
        try:
            print(f"\n处理: {source_path}")

            # 检查源目录是否存在
            if not os.path.exists(source_path):
                print(f"  源目录不存在: {source_path}")
                continue

            # 检查目标目录是否已经存在（如果存在，需要合并）
            if os.path.exists(target_path):
                print(f"  目标目录已存在，进行合并操作...")

                # 合并源目录内容到目标目录
                for item in os.listdir(source_path):
                    source_item = os.path.join(source_path, item)
                    target_item = os.path.join(target_path, item)

                    # 如果目标位置已存在同名文件/文件夹
                    if os.path.exists(target_item):
                        # 如果是文件夹，递归处理
                        if os.path.isdir(source_item) and os.path.isdir(target_item):
                            # 这里简单处理，跳过已有文件夹（实际可能需要递归合并）
                            print(f"    跳过已存在的文件夹: {item}")
                        else:
                            # 对于文件，可以选择覆盖或跳过
                            print(f"    覆盖文件: {item}")
                            if os.path.isdir(source_item):
                                shutil.rmtree(target_item)
                            else:
                                os.remove(target_item)
                            shutil.move(source_item, target_item)
                    else:
                        shutil.move(source_item, target_path)
            else:
                # 目标目录不存在，直接重命名
                print(f"  移动文件夹...")
                shutil.move(source_path, target_path)

            # 删除移动后的空文件夹（源文件夹）
            if os.path.exists(source_path):
                # 如果源文件夹为空，则删除
                if not os.listdir(source_path):
                    print(f"  删除空文件夹: {source_path}")
                    os.rmdir(source_path)
                else:
                    print(f"  警告: 源文件夹非空，未删除: {source_path}")

            print(f"  完成!")

        except Exception as e:
            print(f"  处理失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n操作完成!")

    # 可选：清理所有空文件夹（包括移动后可能产生的其他空文件夹）
    print("\n正在清理其他空文件夹...")
    cleanup_empty_folders(root_dir)


def cleanup_empty_folders(root_dir):
    """
    递归清理指定目录下的所有空文件夹
    """
    empty_folders = []

    # 从最深层开始遍历
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # 如果当前目录为空
        if not dirnames and not filenames:
            # 尝试删除空目录
            try:
                os.rmdir(dirpath)
                empty_folders.append(dirpath)
            except OSError as e:
                # 如果删除失败（可能目录不为空），忽略
                pass

    if empty_folders:
        print(f"清理了 {len(empty_folders)} 个空文件夹:")
        for folder in empty_folders:
            print(f"  {folder}")
    else:
        print("未发现其他空文件夹")


if __name__ == "__main__":
    print("=== 文件夹路径缩略工具 ===")
    print("功能：递归处理，将类似 .../folder_name/folder_name 的路径缩略为 .../folder_name")
    print("示例：D:\\path\\images1\\images1 -> D:\\path\\images1")
    print("-" * 60)

    # 获取用户输入的目录
    root_directory = get_directory_from_user()

    print(f"\n处理根目录: {root_directory}")
    print("-" * 60)

    # 执行文件夹路径缩略操作
    shorten_folder_paths(root_directory)