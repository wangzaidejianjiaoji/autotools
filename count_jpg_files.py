#!/usr/bin/env python3

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
