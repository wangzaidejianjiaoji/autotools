"""
作用：批量重命名工具。把指定目录顶层 *.json 文件名中最后一个下划线之后为
      "drone" 或 "speckle" 的后缀去掉，使 json 与同名原图对齐（如 000001_drone.json -> 000001.json）。
用法：python "json对应原图去除最后下划线命名部分.py" [目录路径]
      也可不带参数运行，按交互提示输入目录路径。
关键参数：
  - dir_path (位置参数 / 交互输入)：待处理的目录（仅顶层 *.json，不递归）
  - 触发条件：文件名最后一个下划线之后的子串必须等于 "drone" 或 "speckle"
  - 目标已存在则跳过该文件并打印警告，不会覆盖
"""


def batch_rename_json_files():
    # 获取目录路径（优先使用命令行参数，否则使用用户输入）
    if len(sys.argv) > 1:
        dir_path = sys.argv[1].strip()
    else:
        dir_path = input("请输入要处理的目录路径: ").strip()

    # 检查目录是否存在
    if not os.path.isdir(dir_path):
        print(f"错误：目录 '{dir_path}' 不存在。")
        return

    # 获取所有 .json 文件
    json_files = glob.glob(os.path.join(dir_path, "*.json"))
    if not json_files:
        print(f"目录 '{dir_path}' 中没有找到 .json 文件。")
        return

    print(f"找到 {len(json_files)} 个 .json 文件。")

    # 存储重命名操作，用于最后确认
    rename_ops = []

    for filepath in json_files:
        basename = os.path.basename(filepath)
        name, ext = os.path.splitext(basename)

        # 查找最后一个下划线的位置
        last_underscore = name.rfind('_')
        if last_underscore == -1:
            print(f"跳过：'{basename}' 中没有下划线，无需处理。")
            continue

        # 检查最后一个下划线后的内容是否为 'drone' 或 'speckle'
        suffix = name[last_underscore+1:]
        if suffix not in ['drone', 'speckle']:
            print(f"跳过：'{basename}' 最后下划线后不是 'drone' 或 'speckle'，无需处理。")
            continue

        # 构建新文件名
        new_name = name[:last_underscore] + ext
        new_filepath = os.path.join(dir_path, new_name)

        # 检查目标文件是否已存在
        if os.path.exists(new_filepath):
            print(f"警告：无法重命名 '{basename}' -> '{new_name}'，因为目标文件已存在。")
            continue

        rename_ops.append((filepath, new_filepath, new_name))

    if not rename_ops:
        print("没有需要重命名的文件。")
        return

    # 显示将要执行的操作
    print("\n将执行以下重命名操作：")
    for old, new, new_name in rename_ops:
        print(f"  {os.path.basename(old)} -> {new_name}")

    # 执行重命名
    for old, new, _ in rename_ops:
        try:
            os.rename(old, new)
            print(f"已重命名：{os.path.basename(old)} -> {os.path.basename(new)}")
        except Exception as e:
            print(f"重命名失败：{os.path.basename(old)}，错误：{e}")

    print("批量重命名完成。")


if __name__ == "__main__":
    batch_rename_json_files()