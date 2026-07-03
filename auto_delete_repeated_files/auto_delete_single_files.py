import os
import sys
from collections import defaultdict


def delete_single_files(input_path):
    """
    删除指定路径下同一组中只有单个文件的文件

    Args:
        input_path: 输入路径
    """
    # 检查路径是否存在
    if not os.path.exists(input_path):
        print(f"错误：路径 '{input_path}' 不存在")
        return

    # 获取路径下所有文件
    files = [f for f in os.listdir(input_path) if os.path.isfile(os.path.join(input_path, f))]

    if not files:
        print(f"路径 '{input_path}' 下没有文件")
        return

    # 按文件名（不含扩展名）分组
    file_groups = defaultdict(list)

    for file in files:
        # 获取文件名和扩展名
        base_name = os.path.splitext(file)[0]
        file_groups[base_name].append(file)

    # 统计分组情况
    print("文件分组情况:")
    for base_name, group_files in file_groups.items():
        print(f"  {base_name}: {len(group_files)} 个文件 - {group_files}")

    # 查找并删除单独的文件
    files_to_delete = []

    for base_name, group_files in file_groups.items():
        if len(group_files) == 1:
            files_to_delete.extend(group_files)

    if not files_to_delete:
        print("\n没有需要删除的单独文件")
        return

    print(f"\n需要删除的单独文件 ({len(files_to_delete)} 个):")
    for file in files_to_delete:
        print(f"  {file}")

    # 确认删除
    print(f"\n确认要删除以上 {len(files_to_delete)} 个文件吗？(y/n): ")
    confirm = input().strip().lower()

    if confirm != 'y':
        print("操作已取消")
        return

    # 执行删除
    deleted_count = 0
    for file in files_to_delete:
        try:
            file_path = os.path.join(input_path, file)
            os.remove(file_path)
            print(f"已删除: {file}")
            deleted_count += 1
        except Exception as e:
            print(f"删除 {file} 时出错: {e}")

    print(f"\n完成！已删除 {deleted_count} 个文件")


def main():
    # 获取输入路径
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = input("请输入路径: ").strip()

    # 处理路径中的引号（如果用户拖拽文件夹到命令行可能会包含引号）
    input_path = input_path.strip('"').strip("'")

    # 执行删除操作
    delete_single_files(input_path)


if __name__ == "__main__":
    main()