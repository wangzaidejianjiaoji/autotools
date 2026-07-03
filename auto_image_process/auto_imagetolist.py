import os

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