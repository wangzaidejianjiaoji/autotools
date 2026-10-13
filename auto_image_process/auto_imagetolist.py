"""
作用：扫描指定文件夹中的常见图片文件（jpg/jpeg/png/gif/bmp/tiff/webp），
     排序后生成一个 t.list 文本文件，每行一个图片的固定绝对路径，
     通常用于模型推理/评测的输入列表。

用法：
    python auto_imagetolist.py
    # 按提示输入目标文件夹路径即可在该目录下生成 t.list

关键参数：
    - folder_path：交互式输入的文件夹路径，仅扫描该目录直接包含的图片，
      不递归进子目录。
    - image_extensions：图片后缀白名单（.jpg/.jpeg/.png/.gif/.bmp/.tiff/.webp），
      不区分大小写匹配。
    - 输出文件：folder_path/t.list，每行为硬编码前缀 + 文件名：
        /data/vsg/Datasets/zhangty/test_pack_v0.0.5/test_set/<文件名>
      该前缀路径在源码中写死，若环境不同需手动修改源码。
"""

def get_image_files(folder_path):
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')
    image_files = []
    
    for entry in os.listdir(folder_path):
        entry_path = os.path.join(folder_path, entry)
        if os.path.isfile(entry_path) and entry.lower().endswith(image_extensions):
            image_files.append(entry)
    
    return image_files

def generate_list_file(folder_path):
    image_files = get_image_files(folder_path)
    
    if not image_files:
        print("No image files found in the specified folder.")
        return
    
    list_file_path = os.path.join(folder_path, 't.list')
    
    with open(list_file_path, 'w', encoding='utf-8') as f:
        for image_file in sorted(image_files):
            full_path = f"/data/vsg/Datasets/zhangty/test_pack_v0.0.5/test_set/{image_file}"
            f.write(full_path + '\n')
    
    print(f"Successfully generated {list_file_path}")
    print(f"Total {len(image_files)} image files listed.")

if __name__ == "__main__":
    folder_path = input("Please enter the folder path: ").strip()
    
    if not os.path.isdir(folder_path):
        print("Error: The specified path is not a valid directory.")
    else:
        generate_list_file(folder_path)