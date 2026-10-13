"""
作用：遍历指定目录下所有子目录，识别属于无人机拍摄分组（文件名带 wide_capture、
     命名形如 NN.NNNN_p…t…z…_wide_capture）的 .jpg/.json 文件，并把成对的（同组
     同时存在 jpg 和 json 的）复制到该目录下的 drone/ 子文件夹，便于集中处理。
用法：
    python move_drone_files.py
    运行后按提示输入要遍历的根目录路径即可。
关键参数/变量：
    source_path            用户在运行时输入的遍历根目录。
    drone_folder           在 source_path 下创建的 'drone' 子目录（目标收集位置）。
    get_group_key()        正则 r'(\d{2}\.\d{4}_p[\d.]+t[\d.]+z[\d.]+_wide_capture)'
                           用来提取分组键，把同名组内的 jpg/json 聚合到一起。
    is_drone_file()        判断条件：后缀 _drone.jpg/_drone.json，或含 'wide_capture' 的 .jpg。
    has_jpg / has_json     只有成对存在的分组才执行复制；只拷贝文件（shutil.copy2），
                           不移动，已存在的同名文件会跳过。
"""

import os
import shutil
import re

def get_group_key(filename):
    match = re.search(r'(\d{2}\.\d{4}_p[\d.]+t[\d.]+z[\d.]+_wide_capture)', filename)
    if match:
        return match.group(1)
    return filename

def is_drone_file(filename):
    return filename.lower().endswith('_drone.jpg') or filename.lower().endswith('_drone.json') or \
           (filename.lower().endswith('.jpg') and 'wide_capture' in filename.lower())

def main():
    source_path = input("请输入要遍历的路径: ").strip()
    
    if not os.path.isdir(source_path):
        print(f"错误: 路径 '{source_path}' 不存在或不是目录")
        return
    
    drone_folder = os.path.join(source_path, 'drone')
    if not os.path.exists(drone_folder):
        os.makedirs(drone_folder)
        print(f"已创建目录: {drone_folder}")
    
    drone_files = {}
    
    for root, dirs, files in os.walk(source_path):
        if root == drone_folder:
            continue
        
        for filename in files:
            if is_drone_file(filename):
                file_path = os.path.join(root, filename)
                group_key = get_group_key(filename)
                
                if group_key not in drone_files:
                    drone_files[group_key] = []
                drone_files[group_key].append(file_path)
    
    moved_count = 0
    skipped_count = 0
    
    for group_key, files in drone_files.items():
        has_jpg = any(f.lower().endswith('.jpg') for f in files)
        has_json = any(f.lower().endswith('.json') for f in files)
        
        if has_jpg and has_json:
            for file_path in files:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(drone_folder, filename)
                
                if os.path.exists(dest_path):
                    print(f"跳过 (已存在): {filename}")
                    skipped_count += 1
                    continue
                
                try:
                    shutil.copy2(file_path, dest_path)
                    print(f"复制成功: {file_path} -> {dest_path}")
                    moved_count += 1
                except Exception as e:
                    print(f"复制失败 {file_path}: {e}")
                    skipped_count += 1
    
    print(f"\n操作完成!")
    print(f"成功复制: {moved_count} 个文件")
    print(f"跳过: {skipped_count} 个文件")

if __name__ == "__main__":
    main()