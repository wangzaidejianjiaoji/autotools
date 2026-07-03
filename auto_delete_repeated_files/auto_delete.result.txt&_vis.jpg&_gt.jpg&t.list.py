#!/usr/bin/env python3
import os
import glob

def delete_files():
    path = input("请输入要清理的路径: ").strip()
    
    if not os.path.isdir(path):
        print(f"错误：路径 '{path}' 不存在或不是目录")
        return
    
    while True:
        recursive = input("是否迭代循环访问子目录？(0=不迭代, 1=迭代): ").strip()
        if recursive in ['0', '1']:
            recursive = int(recursive)
            break
        print("请输入有效的选项 (0 或 1)")
    
    patterns = ['*.result.txt', '*_vis.jpg', '*_gt.jpg', 't.list']
    deleted_count = 0
    
    for pattern in patterns:
        if recursive:
            search_pattern = os.path.join(path, '**', pattern)
            files = glob.glob(search_pattern, recursive=True)
        else:
            search_pattern = os.path.join(path, pattern)
            files = glob.glob(search_pattern)
        
        for file_path in files:
            try:
                os.remove(file_path)
                print(f"已删除: {file_path}")
                deleted_count += 1
            except Exception as e:
                print(f"删除失败 {file_path}: {e}")
    
    print(f"\n清理完成！共删除 {deleted_count} 个文件")

if __name__ == "__main__":
    delete_files()