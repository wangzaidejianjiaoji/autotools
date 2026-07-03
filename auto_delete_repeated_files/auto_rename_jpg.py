import os

def rename_jpg_files(folder_path):
    if not os.path.isdir(folder_path):
        print(f"错误：路径 '{folder_path}' 不是有效的文件夹")
        return

    jpg_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.jpg')]
    
    if not jpg_files:
        print("该文件夹下没有找到任何.jpg文件")
        return

    print(f"找到 {len(jpg_files)} 个jpg文件：")
    for i, file in enumerate(jpg_files[:5], 1):
        print(f"  {i}. {file}")
    if len(jpg_files) > 5:
        print(f"  ... 还有 {len(jpg_files) - 5} 个文件")

    for old_name in jpg_files:
        parts = old_name.rsplit('_', 1)
        if len(parts) >= 2:
            new_name = parts[-1]
            if not new_name.lower().endswith('.jpg'):
                new_name = new_name + '.jpg'
        else:
            new_name = old_name

        old_path = os.path.join(folder_path, old_name)
        new_path = os.path.join(folder_path, new_name)

        if old_path != new_path:
            os.rename(old_path, new_path)
            print(f"重命名: {old_name} -> {new_name}")
        else:
            print(f"跳过（文件名不变）: {old_name}")

    print("\n重命名完成！")

if __name__ == "__main__":
    print("=" * 50)
    print("          JPG文件批量重命名工具")
    print("=" * 50)
    print("说明：该工具会将文件名按照最后一个下划线进行分割，")
    print("      并使用下划线后的部分作为新文件名。")
    print("      例如：20260121_15-34-12_00001.jpg -> 00001.jpg")
    print("=" * 50)

    folder_path = input("\n请输入文件夹路径: ").strip()
    
    if not folder_path:
        print("错误：路径不能为空")
        exit(1)

    rename_jpg_files(folder_path)