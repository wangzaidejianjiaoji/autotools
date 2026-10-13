#!/usr/bin/env python3
"""
作用：批量删除指定目录下常见的模型推理/标注结果文件
     （*.result.txt、*_vis.jpg、*_gt.jpg、t.list），支持可选的递归子目录遍历。

用法：
    python "auto_delete.result.txt&_vis.jpg&_gt.jpg&t.list.py"
    # 然后按提示输入路径与是否递归子目录（0/1）

关键参数：
    - 待清理目录路径：交互式输入（input()），为根目录路径字符串。
    - recursive：是否递归遍历子目录，输入 0 表示不递归，1 表示递归。
    - patterns：脚本内部固定的删除模式列表：
        * *.result.txt   —— 模型推理结果文本
        * *_vis.jpg      —— 可视化结果图片
        * *_gt.jpg       —— 真值/GT 对比图片
        * t.list         —— 任务列表文件
"""

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