#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

def validate_directory(directory_path):
    if not directory_path or directory_path.strip() == "":
        return False, None, "错误：路径不能为空"
    
    normalized_path = os.path.normpath(os.path.expanduser(os.path.expandvars(directory_path.strip())))
    
    if not os.path.exists(normalized_path):
        return False, normalized_path, f"错误：目录不存在 -> {normalized_path}"
    
    if not os.path.isdir(normalized_path):
        return False, normalized_path, f"错误：路径不是目录 -> {normalized_path}"
    
    try:
        os.listdir(normalized_path)
    except PermissionError:
        return False, normalized_path, f"错误：无权限访问目录 -> {normalized_path}"
    except Exception as e:
        return False, normalized_path, f"错误：读取目录失败 -> {normalized_path}, {str(e)}"
    
    return True, normalized_path, None

def get_all_subdirectories(directory_path, recursive=True):
    """
    获取指定目录下的所有子目录（包括嵌套子目录）
    recursive: 是否递归遍历，True表示递归遍历所有层级，False仅遍历直接子目录
    返回子目录相对路径的集合
    """
    subdirs = set()
    try:
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                subdirs.add(item)
                if recursive:
                    nested_subdirs = get_all_subdirectories(item_path, recursive)
                    for nested in nested_subdirs:
                        subdirs.add(os.path.join(item, nested))
    except Exception as e:
        print(f"错误：读取目录失败 -> {directory_path}, {e}")
        return None
    
    return subdirs

def get_valid_directory(prompt):
    while True:
        directory_path = input(prompt).strip()
        is_valid, normalized_path, error_msg = validate_directory(directory_path)
        if is_valid:
            return normalized_path
        print(error_msg)
        retry = input("是否重新输入? (y/n): ").strip().lower()
        if retry != 'y' and retry != 'yes':
            print("退出程序")
            sys.exit(0)

def main():
    print("=" * 60)
    print("目录对比工具")
    print("=" * 60)
    
    dir_a = get_valid_directory("请输入目录 A 的路径: ")
    dir_b = get_valid_directory("请输入目录 B 的路径: ")
    
    recursive_input = input("是否递归遍历所有子目录? (y/n，默认y): ").strip().lower()
    recursive = True if recursive_input == "" or recursive_input == 'y' or recursive_input == 'yes' else False
    
    print(f"\n目录 A: {dir_a}")
    print(f"目录 B: {dir_b}")
    print(f"递归模式: {'是' if recursive else '否'}")
    print()
    
    subdirs_a = get_all_subdirectories(dir_a, recursive)
    if subdirs_a is None:
        sys.exit(1)
    
    subdirs_b = get_all_subdirectories(dir_b, recursive)
    if subdirs_b is None:
        sys.exit(1)
    
    count_a = len(subdirs_a)
    count_b = len(subdirs_b)
    
    intersection = subdirs_a & subdirs_b
    only_in_a = subdirs_a - subdirs_b
    only_in_b = subdirs_b - subdirs_a
    
    count_intersection = len(intersection)
    count_only_in_a = len(only_in_a)
    count_only_in_b = len(only_in_b)
    
    print("=" * 60)
    print("对比结果")
    print("=" * 60)
    print(f"目录 A 共有: {count_a} 个子目录")
    print(f"目录 B 共有: {count_b} 个子目录")
    print(f"交集（共同拥有）: {count_intersection} 个子目录")
    print(f"A 相比 B 缺少: {count_only_in_b} 个子目录")
    print(f"B 相比 A 缺少: {count_only_in_a} 个子目录")
    print("=" * 60)
    
    if count_only_in_b > 0:
        print(f"\nA 相比 B 缺少的目录列表 ({count_only_in_b} 个):")
        for name in sorted(only_in_b):
            print(f"  - {name}")
    
    if count_only_in_a > 0:
        print(f"\nB 相比 A 缺少的目录列表 ({count_only_in_a} 个):")
        for name in sorted(only_in_a):
            print(f"  - {name}")
    
    if count_intersection > 0:
        print(f"\n交集目录列表 ({count_intersection} 个):")
        for name in sorted(intersection):
            print(f"  - {name}")

if __name__ == "__main__":
    main()