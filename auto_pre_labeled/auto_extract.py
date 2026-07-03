import os              # 操作系统交互，文件路径操作
import py7zr           # 7z压缩文件解压


def extract_7z_file(file_path, extract_to=None):
    """
    解压7z文件
    :param file_path: 7z文件路径
    :param extract_to: 解压目标路径（可选，默认使用原文件名）
    :return:
    """
    try:
        # 如果没有指定解压路径，使用7z文件的主干名作为文件夹名
        if extract_to is None:
            extract_to = os.path.splitext(file_path)[0]     #splitext() 返回一个元组，包含两个部分：[0]: 文件名的主干部分（不含扩展名）[1]: 扩展名（包含点号）

        # 如果目标文件夹已存在，先删除
        if os.path.exists(extract_to):
            print(f"文件夹已存在: {extract_to}")
            return extract_to

        os.makedirs(extract_to, exist_ok=True)

        with py7zr.SevenZipFile(file_path, mode='r') as archive:
            archive.extractall(path=extract_to) #extractall(): 解压所有文件到指定路径

        print(f"成功解压: {os.path.basename(file_path)} -> {os.path.basename(extract_to)}")
        return extract_to
    except Exception as e:
        print(f"解压失败 {file_path}: {e}")
        return None


def find_and_extract_archives(root_dir, output_dir):
    """
    在目录中查找并解压所有7z压缩文件
    :param root_dir: 当前目录路径
    :param output_dir: 输出目录路径
    :return:extracted_dirs已经解压后的目录路径
    """

    extracted_dirs = []
    # root：当前目录路径；dirs：当前目录下的子目录列表；files：当前目录下的文件列表；os.walk遍历
    for root, dirs, files in os.walk(root_dir):
        # 跳过输出目录
        # 统一转换为绝对路径再比较
        output_dir_abs = os.path.abspath(output_dir)
        root_abs = os.path.abspath(root)

        if root_abs.startswith(output_dir_abs + os.sep) or root_abs == output_dir_abs:
            continue

        for file in files:
            file_path = os.path.join(root, file)

            # 只处理7z文件
            valid_extensions = ('.7z')
            if file.lower().endswith(valid_extensions):
                print(f"\n找到7z文件: {file}")  # 输出日志信息
                extracted_path = extract_7z_file(file_path)  # 调用解压函数
                if extracted_path:  # 如果解压成功
                    extracted_dirs.append(extracted_path)  # 添加到结果列表

    return extracted_dirs
def main():
    """主函数"""
    print("=" * 60)
    print("自动解压工具")
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
        # 如果路径以斜杠结尾，获取前一个目录
        last_dir_name = os.path.basename(os.path.dirname(target_dir))

    ## 创建输出目录
    output_dir_name = f"{last_dir_name}_已筛选文件"
    output_dir = os.path.join(target_dir, output_dir_name)


    # 步骤1: 查找并解压压缩文件
    print("\n" + "=" * 60)
    print("步骤1: 查找并解压7z压缩文件")
    print("=" * 60)
    extracted_dirs = find_and_extract_archives(target_dir, output_dir)
    if extracted_dirs:
        print(f"已解压 {len(extracted_dirs)} 个7z文件")
    else:
        print("未找到7z压缩文件")
if __name__ == "__main__":
    main()