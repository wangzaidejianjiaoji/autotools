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