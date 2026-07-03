import os
import shutil
from collections import defaultdict


def main():
    # 获取用户输入的目录路径
    target_dir = input("请输入完整目录路径: ").strip()

    # 检查目录是否存在
    if not os.path.exists(target_dir):
        print(f"错误: 目录 '{target_dir}' 不存在")
        return

    if not os.path.isdir(target_dir):
        print(f"错误: '{target_dir}' 不是一个目录")
        return

    # 创建目标文件夹
    output_dir = os.path.join(target_dir, "已筛选文件")
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"已创建文件夹: {output_dir}")
    except Exception as e:
        print(f"创建文件夹失败: {e}")
        return

    # 获取目录下所有文件（排除目录本身）
    files = []
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.isfile(item_path):  # 只处理文件，不处理文件夹
                files.append(item)
    except Exception as e:
        print(f"读取目录内容失败: {e}")
        return

    if not files:
        print("目录中没有文件")
        return

    print(f"找到 {len(files)} 个文件，开始分组...")

    # 按文件名前55个字符分组
    file_groups = defaultdict(list)
    for filename in files:
        # 如果文件名不足55个字符，使用整个文件名
        key = filename[:55] if len(filename) >= 55 else filename
        file_groups[key].append(filename)

    print(f"共分为 {len(file_groups)} 组")

    # 筛选每组3-4个文件的组并复制
    copied_count = 0
    copied_groups = []

    for prefix, file_list in file_groups.items():
        file_count = len(file_list)

        if file_count == 3 or file_count == 4:
            copied_groups.append((prefix, file_list))
            print(f"组 '{prefix}': {file_count} 个文件 - 符合条件")

            # 复制该组所有文件
            for filename in file_list:
                src_path = os.path.join(target_dir, filename)
                dst_path = os.path.join(output_dir, filename)

                try:
                    shutil.copy2(src_path, dst_path)  # copy2会保留文件元数据
                    print(f"  已复制: {filename}")
                    copied_count += 1
                except Exception as e:
                    print(f"  复制失败 {filename}: {e}")
        else:
            print(f"组 '{prefix}': {file_count} 个文件 - 不符合条件")

    # 输出统计信息
    print("\n" + "=" * 50)
    print("操作完成!")
    print(f"符合条件的组数: {len(copied_groups)}")
    print(f"复制的文件总数: {copied_count}")
    print(f"所有文件已复制到: {output_dir}")

    # 显示符合条件的组详情
    if copied_groups:
        print("\n符合条件的文件组详情:")
        for i, (prefix, file_list) in enumerate(copied_groups, 1):
            print(f"第 {i} 组 (前缀: '{prefix}'):")
            for filename in file_list:
                print(f"  - {filename}")
    else:
        print("没有找到符合条件的文件组")


if __name__ == "__main__":
    main()