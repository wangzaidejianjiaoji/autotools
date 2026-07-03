import os
import json
import re

def extract_number_from_filename(filename):
    base_name = os.path.splitext(filename)[0]
    match = re.search(r'(\d+)$', base_name)
    if match:
        return int(match.group(1))
    return 0

def update_json_content(file_path, new_base_name):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        updated = False
        if 'imagePath' in data:
            old_image_path = data['imagePath']
            dir_part = os.path.dirname(old_image_path)
            new_image_path = os.path.join(dir_part, new_base_name + '.jpg').replace('\\', '/')
            data['imagePath'] = new_image_path
            updated = True
        
        if updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True, old_image_path, data['imagePath']
        
        return False, None, None
    except Exception as e:
        print(f"  警告：更新文件内容失败 - {e}")
        return False, None, None

def rename_json_files(folder_path, frame_digits, start_frame):
    if not os.path.isdir(folder_path):
        print(f"错误：路径 '{folder_path}' 不是有效的文件夹")
        return

    json_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.json')]
    
    if not json_files:
        print("该文件夹下没有找到任何.json文件")
        return

    json_files.sort(key=extract_number_from_filename)

    print(f"找到 {len(json_files)} 个json文件：")
    for i, file in enumerate(json_files[:5], 1):
        print(f"  {i}. {file}")
    if len(json_files) > 5:
        print(f"  ... 还有 {len(json_files) - 5} 个文件")

    for old_name in json_files:
        original_num = extract_number_from_filename(old_name)
        new_num = original_num + start_frame
        new_base_name = f"{new_num:0{frame_digits}d}"
        new_name = new_base_name + '.json'

        old_path = os.path.join(folder_path, old_name)
        
        content_updated, old_ip, new_ip = update_json_content(old_path, new_base_name)
        
        new_path = os.path.join(folder_path, new_name)

        if old_path != new_path:
            os.rename(old_path, new_path)
            print(f"重命名: {old_name} -> {new_name}")
            if content_updated:
                print(f"  内容更新: imagePath {old_ip} -> {new_ip}")
        else:
            print(f"跳过（文件名不变）: {old_name}")
            if content_updated:
                print(f"  内容更新: imagePath {old_ip} -> {new_ip}")

    print("\n处理完成！")

if __name__ == "__main__":
    print("=" * 50)
    print("          json文件批量重命名工具")
    print("=" * 50)
    print("说明：该工具会提取文件名末尾的数字序号，")
    print("      根据选择的格式重命名文件。")
    print("      同时更新文件内容中的imagePath字段。")
    print("=" * 50)

    while True:
        print("\n请选择目标命名格式：")
        print("  1. 五位帧号 (例如：00001.json)")
        print("  2. 六位帧号 (例如：000001.json)")
        format_choice = input("请输入选择 (1 或 2): ").strip()
        
        if format_choice in ['1', '2']:
            frame_digits = 5 if format_choice == '1' else 6
            break
        print("无效选择，请输入 1 或 2")

    while True:
        print("\n请选择目标起始帧号：")
        print("  0. 从0开始 (原序号+0)")
        print("  1. 从1开始 (原序号+1)")
        start_choice = input("请输入选择 (0 或 1): ").strip()
        
        if start_choice in ['0', '1']:
            start_frame = int(start_choice)
            break
        print("无效选择，请输入 0 或 1")

    print(f"\n您的选择：{frame_digits}位帧号，起始帧号+{start_frame}")
    print(f"例如：cb_tree_260128_mavic2_02990.json -> {2990 + start_frame:0{frame_digits}d}.json")

    folder_path = input("\n请输入文件夹路径: ").strip()
    
    if not folder_path:
        print("错误：路径不能为空")
        exit(1)

    rename_json_files(folder_path, frame_digits, start_frame)