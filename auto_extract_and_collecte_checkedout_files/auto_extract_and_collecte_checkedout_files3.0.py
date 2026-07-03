import os              # 操作系统交互，文件路径操作
import shutil          # 文件复制和移动操作
import py7zr           # 7z压缩文件解压
from collections import defaultdict  # 带默认值的字典
import subprocess      # 执行系统命令


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


def collect_all_files(root_dir, output_dir):
    """
    :param root_dir:要搜索的根目录路径
    :param output_dir:需要跳过的输出目录路径
    :return:all_files
    """
    """收集目录中所有指定类型的文件"""
    image_extensions = {'.jpg'}
    data_extensions = {'.json'}

    all_files = []

    for root, dirs, files in os.walk(root_dir):
        # 跳过输出目录
        # 统一转换为绝对路径再比较
        output_dir_abs = os.path.abspath(output_dir)
        root_abs = os.path.abspath(root)

        if root_abs.startswith(output_dir_abs + os.sep) or root_abs == output_dir_abs:
            continue

        for file in files:
            file_ext = os.path.splitext(file)[1].lower()    #分割文件名和扩展名，返回(filename, extension)

            # 只收集jpg和json文件
            if file_ext in image_extensions or file_ext in data_extensions:
                file_path = os.path.join(root, file)
                all_files.append({
                    'path': file_path,
                    'name': file,   # 这里是完整的文件名，包括后缀
                    'ext': file_ext,
                    'source_dir': root  # 记录来源目录
                })

    return all_files


def group_and_filter_files(files):
    """按文件名前55个字符分组并筛选"""
    file_groups = defaultdict(list) #创建默认值为空列表的字典，有值后格式如下
    # 键：文件名前55个字符
    # 值：该前缀对应的文件信息列表
    for file_info in files:
        filename = file_info['name']
        # 按文件名前55个字符分组
        key = filename[:55]
        file_groups[key].append(file_info)  #增加V的值

    # 筛选出每组大于等于3个文件数量的组。拿K：V，看file_groups的V数量是否>=3
    filtered_groups = {}
    for prefix, file_list in file_groups.items():
        file_count = len(file_list)
        if file_count >= 3:
            filtered_groups[prefix] = file_list #字典键值对赋值

    return filtered_groups


def copy_filtered_files(filtered_groups, output_dir, target_dir):
    #待优化dst_path
    """
    复制筛选后的文件到目标目录
    :param filtered_groups:dict：K：文件名 V：文件信息列表
    :param output_dir:目标输出目录路径
    :return:
    """
    copied_count = 0
    group_info = []

    for group_idx, (prefix, file_list) in enumerate(filtered_groups.items(), 1):
        # 同一组内的文件来源目录相同，取第一个文件的来源目录
        source_dir = file_list[0]['source_dir']

        print(f"\n组 {group_idx}:")
        print(f"  文件名前缀: '{prefix}'")
        print(f"  来源目录: {source_dir}")

        group_files = []
        for file_info in file_list:
            src_path = file_info['path']    # 源文件完整路径
            dst_path = os.path.join(output_dir, file_info['name'])  # 目标路径

            try:
                # 直接覆盖，不检查是否已存在
                shutil.copy2(src_path, dst_path)    # 复制文件并保留元数据
                print(f"  已复制: {file_info['name']}")
                copied_count += 1
                group_files.append(file_info['name'])
            except Exception as e:
                print(f"  复制失败 {file_info['name']}: {e}")

        # 记录组信息
        group_info.append({
            'group_num': group_idx,  # 组编号
            'prefix': prefix,  # 文件名前缀
            'source_dir': source_dir,  # 来源目录
            'file_count': len(file_list),  # 组内文件总数
            'files': group_files  # 成功复制的文件名列表
        })

    return copied_count, group_info


def create_operation_log(output_dir, group_info, total_groups, total_files, target_dir):
    """
    创建操作日志
    :param output_dir:日志文件要保存的输出目录
    :param group_info:包含分组信息的列表，每个元素是一个字典
    :param total_groups:符合条件的组数
    :param total_files:总共复制的文件数量
    :param target_dir:操作的源目录（目标目录）
    :return:log_path
    """
    log_path = os.path.join(output_dir, "操作日志.txt")

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("文件筛选操作日志\n")
        f.write("=" * 60 + "\n\n")

        # 获取当前日期时间
        if os.name == 'nt':  # Windows
            date_time = subprocess.getoutput('date /t && time /t')
        else:  # Linux/Mac
            date_time = subprocess.getoutput('date')

        f.write(f"操作时间: {date_time}\n")
        f.write(f"源目录: {target_dir}\n")
        f.write(f"输出目录: {output_dir}\n")
        f.write(f"符合条件的组数: {total_groups}\n")
        f.write(f"复制的文件总数: {total_files}\n\n")

        f.write("操作详情:\n")
        f.write("=" * 60 + "\n")

        for info in group_info:
            f.write(f"\n第 {info['group_num']} 组:\n")
            f.write(f"  文件名前缀: '{info['prefix']}'\n")
            f.write(f"  来源目录: {info['source_dir']}\n")
            f.write(f"  文件数量: {info['file_count']}\n")
            f.write("  文件列表:\n")
            for file_name in info['files']:
                f.write(f"    - 文件名: {file_name}\n")
            f.write("\n")

    print(f"\n已生成操作日志: {log_path}")
    return log_path


def main():
    """主函数"""
    print("=" * 60)
    print("自动解压与文件筛选工具")
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

    # 创建输出目录
    output_dir_name = f"{last_dir_name}_ckeckedout"
    output_dir = os.path.join(target_dir, output_dir_name)

    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\n已创建输出文件夹: {output_dir}")
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

    # 步骤3: 分组和筛选
    print("\n" + "=" * 60)
    print("步骤3: 按文件名分组并筛选")
    print("=" * 60)
    filtered_groups = group_and_filter_files(all_files)
    print(f"共分为 {len(filtered_groups)} 组符合条件 (每组>=3个文件)")

    if not filtered_groups:
        print("没有找到符合条件的文件组")
        return

    # 步骤4: 复制文件
    print("\n" + "=" * 60)
    print("步骤4: 复制筛选后的文件")
    print("=" * 60)
    total_copied, group_info = copy_filtered_files(filtered_groups, output_dir, target_dir)

    # 步骤5: 创建操作日志
    print("\n" + "=" * 60)
    print("步骤5: 生成操作日志")
    print("=" * 60)
    create_operation_log(output_dir, group_info, len(filtered_groups), total_copied, target_dir)

    # 最终统计
    print("\n" + "=" * 60)
    print("操作完成!")
    print("=" * 60)
    print(f"扫描的文件总数: {len(all_files)}")
    print(f"符合条件的组数: {len(filtered_groups)}")
    print(f"复制的文件总数: {total_copied}")
    print(f"所有文件已复制到: {output_dir}")
    print(f"操作日志已生成: {os.path.join(output_dir, '操作日志.txt')}")


if __name__ == "__main__":
    main()