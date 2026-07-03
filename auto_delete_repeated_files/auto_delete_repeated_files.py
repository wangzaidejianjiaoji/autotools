import os
import hashlib
import shutil


def get_file_hash(filepath):
    """计算文件的MD5哈希值"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"读取文件失败 {filepath}: {e}")
        return None


def find_duplicate_files(dir_a, dir_b):
    """查找两个目录中重复的文件"""
    # 存储目录B中文件的哈希值和路径
    dir_b_hashes = {}

    # 遍历目录B，建立哈希值映射
    for root, dirs, files in os.walk(dir_b):
        for file in files:
            filepath = os.path.join(root, file)
            file_hash = get_file_hash(filepath)
            if file_hash:
                dir_b_hashes[file_hash] = filepath

    duplicates = []

    # 遍历目录A，查找重复文件
    for root, dirs, files in os.walk(dir_a):
        for file in files:
            filepath = os.path.join(root, file)
            file_hash = get_file_hash(filepath)
            if file_hash and file_hash in dir_b_hashes:
                duplicates.append(filepath)

    return duplicates


def remove_duplicates_from_a(dir_a, dir_b, dry_run=False):
    """
    从目录A中删除与目录B重复的文件

    参数:
    dir_a: 需要清理的目录
    dir_b: 作为参考的目录
    dry_run: 如果为True，只显示将要删除的文件而不实际删除
    """
    # 验证目录是否存在
    if not os.path.exists(dir_a):
        print(f"错误: 目录A '{dir_a}' 不存在")
        return

    if not os.path.exists(dir_b):
        print(f"错误: 目录B '{dir_b}' 不存在")
        return

    print(f"正在扫描目录...")
    print(f"目录A: {os.path.abspath(dir_a)}")
    print(f"目录B: {os.path.abspath(dir_b)}")

    duplicates = find_duplicate_files(dir_a, dir_b)

    if not duplicates:
        print("未找到重复文件。")
        return

    print(f"\n找到 {len(duplicates)} 个重复文件:")
    for i, filepath in enumerate(duplicates, 1):
        print(f"{i}. {filepath}")

    if dry_run:
        print("\n(模拟运行模式 - 未实际删除任何文件)")
        return

    # 确认删除
    print(f"\n确定要从目录A中删除这 {len(duplicates)} 个文件吗？")
    response = input("输入 'yes' 确认删除，其他任意键取消: ")

    if response.lower() != 'yes':
        print("操作已取消。")
        return

    # 执行删除
    deleted_count = 0
    for filepath in duplicates:
        try:
            os.remove(filepath)
            print(f"已删除: {filepath}")
            deleted_count += 1
        except Exception as e:
            print(f"删除失败 {filepath}: {e}")

    print(f"\n完成！成功删除了 {deleted_count}/{len(duplicates)} 个重复文件。")

    # 可选：删除空目录
    try:
        for root, dirs, files in os.walk(dir_a, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"已删除空目录: {dir_path}")
    except Exception as e:
        print(f"删除空目录时出错: {e}")


def main():
    """主函数，处理命令行输入"""
    import sys

    if len(sys.argv) != 3:
        print("用法: python script.py <目录A> <目录B>")
        print("示例: python script.py ./folder1 ./folder2")
        print("\n选项:")
        print("  目录A: 需要删除重复文件的目录")
        print("  目录B: 作为参考的目录（不会修改此目录）")
        return

    dir_a = sys.argv[1]
    dir_b = sys.argv[2]

    # 首先进行模拟运行，显示将要删除的文件
    remove_duplicates_from_a(dir_a, dir_b, dry_run=True)

    # 询问是否执行实际删除
    print("\n是否要执行实际删除？")
    response = input("输入 'yes' 执行实际删除，其他任意键退出: ")

    if response.lower() == 'yes':
        remove_duplicates_from_a(dir_a, dir_b, dry_run=False)


if __name__ == "__main__":
    # 如果要直接运行，可以修改下面的路径
    remove_duplicates_from_a("path/to/dir_a", "path/to/dir_b", dry_run=False)

    # 或者使用命令行参数
    main()