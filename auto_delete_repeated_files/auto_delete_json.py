import os
from pathlib import Path


def delete_all_json_files(directory_path):
    """
    删除指定目录及其子目录中的所有 .json 文件
    """
    target_dir = Path(directory_path)

    if not target_dir.exists() or not target_dir.is_dir():
        print(f"错误: '{directory_path}' 不是有效的目录")
        return

    deleted_count = 0
    # os.walk() 递归遍历目录树
    # root: 当前目录路径
    # dirs: 当前目录下的子目录列表
    # files: 当前目录下的文件列表
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = Path(root) / file
                try:
                    file_path.unlink()  # unlink() 方法删除文件
                    deleted_count += 1
                    print(f"已删除: {file_path}")
                except Exception as e:
                    print(f"删除失败 {file_path}: {e}")

    print(f"\n完成! 共删除 {deleted_count} 个 .json 文件")


if __name__ == "__main__":
    directory = input("请输入目录路径: ")
    delete_all_json_files(directory)