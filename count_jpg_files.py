#!/usr/bin/env python3
"""
作用：递归统计指定目录及其所有子目录下的 .jpg 文件总数（交互式命令行工具）。
用法：
    python count_jpg_files.py
    运行后按提示输入目录路径（输入 'quit' 退出）；脚本会逐个目录打印总 jpg 数。
关键参数/变量：
    input_path    运行时交互输入的待遍历根目录；输入 'quit' 时退出主循环。
    root_path     count_jpg_files() 的参数，即要递归遍历的目录。
    后缀匹配      filename.lower().endswith('.jpg')，大小写不敏感。
"""

import os

def count_jpg_files(root_path):
    jpg_count = 0
    for dirpath, dirnames, filenames in os.walk(root_path):
        for filename in filenames:
            if filename.lower().endswith('.jpg'):
                jpg_count += 1
    return jpg_count

def main():
    print("JPG文件统计工具")
    print("=" * 30)
    
    while True:
        input_path = input("请输入要遍历的路径（输入 'quit' 退出）：").strip()
        
        if input_path.lower() == 'quit':
            print("退出程序。")
            break
        
        if not os.path.exists(input_path):
            print(f"错误：路径 '{input_path}' 不存在！")
            continue
        
        if not os.path.isdir(input_path):
            print(f"错误：'{input_path}' 不是一个有效的目录！")
            continue
        
        print(f"\n正在遍历目录: {input_path}")
        print("请稍候...")
        
        try:
            count = count_jpg_files(input_path)
            print(f"\n统计完成！")
            print(f"在路径 '{input_path}' 及其所有子目录中，共找到 {count} 个 .jpg 文件。")
        except PermissionError:
            print(f"错误：无法访问路径 '{input_path}'，请检查权限。")
        except Exception as e:
            print(f"发生未知错误：{e}")
        
        print("-" * 30)

if __name__ == "__main__":
    main()
