"""
作用：扫描指定目录，将所有文件按"主文件名（去扩展名）"分组，
     删除那些"同组只有 1 个文件"、即没有同名同主名伙伴的孤立文件。

用法：
    python auto_delete_single_files.py [目录路径]
    # 示例：python auto_delete_single_files.py "D:/data/train"
    # 不传参时，程序会交互式要求输入路径（支持拖拽带引号路径）。

关键参数：
    - input_path（sys.argv[1]）：要处理的目录路径，仅扫描该目录直接包含的文件，
      不递归进子目录。
    - 分组规则：以"文件名去后缀"为 key 分组，例如 a.jpg、a.json 被视作同一组。
    - 删除条件：某组内文件数 == 1 的全部删除；>=2 的整组保留。
    - 确认机制：列出待删文件后需输入 y 确认才会执行删除。
"""


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