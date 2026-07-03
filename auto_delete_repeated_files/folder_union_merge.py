#!/usr/bin/env python3
import os
import hashlib
import shutil
import sys


def get_file_hash(filepath):
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"读取文件失败 {filepath}: {e}")
        return None


def get_all_files_with_hash(directory):
    files_info = {}
    total_files = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, directory)
            file_hash = get_file_hash(filepath)
            if file_hash:
                files_info[file_hash] = {
                    'abs_path': filepath,
                    'rel_path': rel_path,
                    'hash': file_hash
                }
                total_files += 1
                print(f"\r  扫描进度: {total_files} 个文件", end='', flush=True)
    
    print()
    return files_info


def merge_folders_union(dir_a, dir_b, output_dir):
    if not os.path.exists(dir_a):
        print(f"错误: 目录A '{dir_a}' 不存在")
        return False
    
    if not os.path.exists(dir_b):
        print(f"错误: 目录B '{dir_b}' 不存在")
        return False
    
    if os.path.exists(output_dir):
        print(f"警告: 输出目录 '{output_dir}' 已存在")
        response = input("是否覆盖？(y/n): ").strip().lower()
        if response != 'y':
            print("操作已取消")
            return False
        shutil.rmtree(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n目录A: {os.path.abspath(dir_a)}")
    print(f"目录B: {os.path.abspath(dir_b)}")
    print(f"输出目录: {os.path.abspath(output_dir)}")
    
    print("\n正在扫描目录A...")
    files_a = get_all_files_with_hash(dir_a)
    print(f"目录A共有 {len(files_a)} 个唯一文件")
    
    print("\n正在扫描目录B...")
    files_b = get_all_files_with_hash(dir_b)
    print(f"目录B共有 {len(files_b)} 个唯一文件")
    
    union_files = {}
    union_files.update(files_a)
    
    new_from_b = 0
    for file_hash, info in files_b.items():
        if file_hash not in union_files:
            union_files[file_hash] = info
            new_from_b += 1
    
    print(f"\n并集统计:")
    print(f"  目录A唯一文件: {len(files_a)}")
    print(f"  目录B唯一文件: {len(files_b)}")
    print(f"  目录B中新增文件: {new_from_b}")
    print(f"  重复文件(已去重): {len(files_a) + len(files_b) - len(union_files)}")
    print(f"  并集总文件数: {len(union_files)}")
    
    print("\n正在复制文件到输出目录...")
    copied_count = 0
    error_count = 0
    
    for file_hash, info in union_files.items():
        src_path = info['abs_path']
        rel_path = info['rel_path']
        dst_path = os.path.join(output_dir, rel_path)
        
        dst_dir = os.path.dirname(dst_path)
        if dst_dir:
            os.makedirs(dst_dir, exist_ok=True)
        
        try:
            shutil.copy2(src_path, dst_path)
            copied_count += 1
            print(f"\r  复制进度: {copied_count}/{len(union_files)}", end='', flush=True)
        except Exception as e:
            print(f"\n复制失败 {src_path} -> {dst_path}: {e}")
            error_count += 1
    
    print(f"\n\n完成！成功复制 {copied_count} 个文件")
    if error_count > 0:
        print(f"失败 {error_count} 个文件")
    
    return True


def interactive_mode():
    print("=" * 60)
    print("文件夹并集合并工具 (去重)")
    print("=" * 60)
    print("功能: 将两个文件夹的内容合并，去除重复文件，输出到新文件夹")
    print("说明: 通过文件内容MD5哈希值判断是否重复")
    print("=" * 60)
    
    while True:
        dir_a = input("\n请输入目录A路径: ").strip()
        if dir_a:
            dir_a = os.path.expanduser(dir_a)
            if os.path.isdir(dir_a):
                break
            print(f"错误: '{dir_a}' 不是有效的目录")
        else:
            print("路径不能为空")
    
    while True:
        dir_b = input("请输入目录B路径: ").strip()
        if dir_b:
            dir_b = os.path.expanduser(dir_b)
            if os.path.isdir(dir_b):
                break
            print(f"错误: '{dir_b}' 不是有效的目录")
        else:
            print("路径不能为空")
    
    while True:
        output_dir = input("请输入输出目录路径: ").strip()
        if output_dir:
            output_dir = os.path.expanduser(output_dir)
            break
        print("路径不能为空")
    
    print(f"\n确认信息:")
    print(f"  目录A: {os.path.abspath(dir_a)}")
    print(f"  目录B: {os.path.abspath(dir_b)}")
    print(f"  输出: {os.path.abspath(output_dir)}")
    
    response = input("\n确认执行？(y/n): ").strip().lower()
    if response == 'y':
        merge_folders_union(dir_a, dir_b, output_dir)
    else:
        print("操作已取消")


def main():
    if len(sys.argv) == 4:
        dir_a = os.path.expanduser(sys.argv[1])
        dir_b = os.path.expanduser(sys.argv[2])
        output_dir = os.path.expanduser(sys.argv[3])
        merge_folders_union(dir_a, dir_b, output_dir)
    elif len(sys.argv) == 1:
        interactive_mode()
    else:
        print("用法:")
        print("  交互模式: python folder_union_merge.py")
        print("  命令行模式: python folder_union_merge.py <目录A> <目录B> <输出目录>")
        print("\n示例:")
        print("  python folder_union_merge.py ./folder_a ./folder_b ./output")


if __name__ == "__main__":
    main()
